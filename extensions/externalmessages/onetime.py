#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import datetime
import json
import logging
import smtplib
import traceback
import urllib
import http
from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import ugettext as _, activate as language_activate
from django.utils.timezone import now
from django.utils.encoding import force_str
from django.core import mail
from ngw.core.models import ContactMsg
import ngw.core.contactfield

SUPPORTS_EXPIRATION = True

SMTP_CONNECTION = None  # Permanent connection accross calls (within cron job)
SMTP_SERVER_CONGESTION = False

logger = logging.getLogger('msgsync')

# Synchronisation information stored in json (ContactMsg.sync_info):
# otid: Onetime ID
# answer_password: Onetime password to get answers
# email_sent: True if notification email was sent
# deleted: True if remote server returns 404 (deleted on remote end)

TIMEOUT = 30 # seconds

def clean_expiration_date(expiration_date):
    MAXEXPIRATION = 90
    if expiration_date <= datetime.date.today():
        raise ValidationError(_('The expiration date must be in the future.'))
    if expiration_date >= datetime.date.today() + datetime.timedelta(days=MAXEXPIRATION):
        raise ValidationError(
            _("The expiration date can't be more that %s days in the future.") % MAXEXPIRATION)
    return expiration_date

def send_to_onetime(msg):
    "step 1 : Send message to final storage"
    try:
        sync_info = json.loads(msg.sync_info)
    except ValueError:
        sync_info = {}

    #logger.debug("%s %s", msg.id, sync_info)

    if 'otid' in sync_info:
        return # Already sent

    ot_conn = http.client.HTTPSConnection('onetime.info', timeout=TIMEOUT)

    logger.info('Storing message for %s.', msg.contact)

    try:
        days = sync_info['expiration']
    except KeyError:
        logger.warning("Message %s doesn't have an expiration date." % msg.id)
        dt = msg.group.date
        if dt:
            days = (dt - now().date()).days
        else:
            days = 21
    ot_conn.request('POST', '/', urllib.parse.urlencode({
        'subject': msg.subject.encode(settings.DEFAULT_CHARSET),
        'message': msg.text.encode(settings.DEFAULT_CHARSET),
        'once': True,
        'expiration': days,
        'allow_answers': 1
    }), {
        'Content-type': 'application/x-www-form-urlencoded',
        'X_REQUESTED_WITH': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    })
    response = ot_conn.getresponse()
    if response.status != 200:
        logger.error("Temporary storage server error: %s %s" % (response.status, response.reason))
        logger.error("%s", response.read())
        return
    #jresponse = json.load(response)
    #logger.debug("%s", jresponse)
    sresponse = response.read()
    jresponse = json.loads(force_str(sresponse))

    sync_info['otid'] = jresponse['url'][1:]
    sync_info['answer_password'] = jresponse['answer_password']
    msg.sync_info = json.dumps(sync_info)
    msg.save()


def send_notification(msg):
    "step 2 : Send email notification"

    global SMTP_CONNECTION, SMTP_SERVER_CONGESTION

    if SMTP_SERVER_CONGESTION:
        return

    sync_info = json.loads(msg.sync_info)
    if 'email_sent' in sync_info:
        return  # already sent
    if 'otid' not in sync_info:
        return  # Message is not ready on external storage

    if 'language' in sync_info:
        logger.warning('Switch to language: %s' % sync_info['language'])
        language_activate(sync_info['language'])

    c_mails = msg.contact.get_fieldvalues_by_type('EMAIL')
    if not c_mails:
        logger.warning('%s does not has an email address.', msg.contact.name)
        return
    mail_addr = c_mails[0]

    if SMTP_CONNECTION is None:
        logger.debug('Opening SMTP connection')
        SMTP_CONNECTION = mail.get_connection()

    logger.info('Sending email notification to %s.', mail_addr)

    notification_text = _('''Hello

You can read your message at https://onetime.info/%s

Warning, that message will be displayed only once, and then deleted. Have a pen
ready before clicking the link.

Do not reply to that email: Use the link above.
If the link doesn't work, please try again.
If you get an error saying the message was already read, but you were not the
one to read it, please repport that.''')

    message = mail.EmailMessage(
        subject=msg.subject,
        body=notification_text % sync_info['otid'],
        to=(mail_addr,),
        connection=SMTP_CONNECTION)
    try:
        message.send()
    except smtplib.SMTPException as err:
        logger.critical('%s' % err)
        if err.smtp_code // 100 == 4:
            logger.warning('Temporarary SMTP failure: %s' % err)
        if err.smtp_code == 450:
            logger.info('Message rate exceeded: giving up for now')
            SMTP_SERVER_CONGESTION = True
        return

    sync_info['email_sent'] = True
    msg.sync_info = json.dumps(sync_info)
    msg.save()


def read_answers(msg):
    "step 3 : Fetch answers"

    sync_info = json.loads(msg.sync_info)
    if 'answer_password' not in  sync_info:
        return
    if 'deleted' in sync_info:
        # Ignore message that were deleted on remote storage
        return
    # We have to open a new connection each time
    # since we can't handle keep-alive yet
    ot_conn = http.client.HTTPSConnection('onetime.info', timeout=TIMEOUT)

    ot_conn.request('POST', '/'+sync_info['otid']+'/answers', urllib.parse.urlencode({
        'password': sync_info['answer_password']
    }), {
        'Content-type': 'application/x-www-form-urlencoded',
        'X_REQUESTED_WITH': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    })
    response = ot_conn.getresponse() # TODO: except httplib.BadStatusLine
    if response.status == 404:
        logger.info("Message is gone: %s %s" % (response.status, response.reason))
        # tag the message as deleted, so we stop trying to synchronise again and again
        sync_info['deleted'] = True
        msg.sync_info = json.dumps(sync_info)
        msg.save()
        return
    if response.status != 200:
        logger.error("Temporary storage server error: %s %s" % (response.status, response.reason))
        logger.error("%s", response.read())
        return
    #jresponse = json.load(response)
    sresponse = response.read()
    jresponse = json.loads(force_str(sresponse))
    logger.debug(jresponse)
    if 'read_date' in jresponse and not msg.read_date:
        msg.read_date = jresponse.get('read_date', None)
        msg.save()
    for response_text in jresponse['answers']:
        logger.info('Received answer from %s.', msg.contact)
        answer_msg = ContactMsg(
            group_id=msg.group_id,
            contact_id=msg.contact_id,
            send_date=datetime.datetime.utcnow(),
            subject=jresponse['subject'],
            text=response_text,
            is_answer=True,
            sync_info=json.dumps({
                'backend': __name__,
                'otid': sync_info['otid'],
                }),
            )
        answer_msg.save()


def sync_msg(msg):
    if msg.is_answer:
        # Nothing to do for answers
        return
    try:
        send_to_onetime(msg)
    except BaseException as err:
        logger.critical(err)
        logger.critical(traceback.format_exc())

    try:
        send_notification(msg)
    except BaseException as err:
        logger.critical(err)
        logger.critical(traceback.format_exc())

    try:
        read_answers(msg)
    except BaseException as err:
        logger.critical(err)
        logger.critical(traceback.format_exc())
