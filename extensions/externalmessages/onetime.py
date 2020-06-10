#!/usr/bin/env python3

import datetime
import email
import http.client
import json
import logging
import smtplib
import subprocess
import traceback
import urllib

from django.conf import settings
from django.core import mail
from django.forms import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.encoding import force_str, force_text
from django.utils.translation import activate as language_activate
from django.utils.translation import ugettext as _

import ngw.core.contactfield  # noqa required for polymorphic upgrades
from ngw.core.models import ContactMsg

SUPPORTS_EXPIRATION = True

SMTP_CONNECTION = None  # Permanent connection accross calls (within cron job)
SMTP_SERVER_CONGESTION = False

logger = logging.getLogger('msgsync')

# Synchronisation information stored in json (ContactMsg.sync_info):
# otid: Onetime ID
# answer_password: Onetime password to get answers
# email_sent: True if notification email was sent
#             False if we should give up (User unknown)
# deleted: True if remote server returns 404 (deleted on remote end)

TIMEOUT = 30  # seconds


def clean_expiration_date(expiration_date):
    MAXEXPIRATION = 90
    if expiration_date <= datetime.date.today():
        raise ValidationError(_('The expiration date must be in the future.'))
    if (expiration_date >= datetime.date.today()
       + datetime.timedelta(days=MAXEXPIRATION)):
        raise ValidationError(
            _("The expiration date can't be more that {} days in the future.")
            .format(MAXEXPIRATION))
    return expiration_date


def send_to_onetime(msg):
    "step 1 : Send message to final storage"
    try:
        sync_info = json.loads(msg.sync_info)
    except ValueError:
        sync_info = {}

    # logger.debug("%s %s", msg.id, sync_info)

    if 'otid' in sync_info:
        return  # Already sent

    ot_conn = http.client.HTTPSConnection('onetime.info', timeout=TIMEOUT)

    logger.info('Storing message for %s.', msg.contact)

    try:
        days = sync_info['expiration']
    except KeyError:
        logger.warning("Message %s doesn't have an expiration date.", msg.id)
        dt = msg.group.date
        if dt:
            days = (dt - timezone.now().date()).days
        else:
            days = 21

    # Hack into headers: The TO value doesn't need to be stored remotely
    message = email.message_from_string(msg.text, policy=email.policy.SMTP)
    try:
        del message['to']
    except KeyError:
        logger.warning("Message %s doesn't have a To:", msg.id)
    msg_text = message.as_string()

    msg_text = msg_text.encode(settings.DEFAULT_CHARSET)
    passphrase = get_random_string(
        16, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')
    msg_text = subprocess.check_output(
        ['openssl', 'enc', '-aes-256-cbc',
         '-pass', 'pass:{}'.format(passphrase),
         '-e', '-base64',
         '-md', 'md5'],
        input=msg_text)

    ot_conn.request('POST', '/', urllib.parse.urlencode({
        'message': msg_text,
        'once': True,
        'expiration': days,
        'allow_answers': 1
    }), {
        'Content-type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    })
    response = ot_conn.getresponse()
    if response.status != 200:
        logger.error(
            "onetime.info error while storing message %s: %s %s",
            msg.id, response.status, response.reason)
        logger.error("%s", response.read())
        return
    # jresponse = json.load(response)
    # logger.debug("%s", jresponse)
    sresponse = response.read()
    jresponse = json.loads(force_str(sresponse))

    sync_info['otid'] = jresponse['url'][1:]
    sync_info['answer_password'] = jresponse['answer_password']
    sync_info['passphrase_out'] = passphrase
    msg.sync_info = json.dumps(sync_info)
    msg.save()


def send_notification(msg):
    "step 2 : Send email notification"

    global SMTP_CONNECTION, SMTP_SERVER_CONGESTION

    if SMTP_SERVER_CONGESTION:
        return

    sync_info = json.loads(msg.sync_info)
    if 'email_sent' in sync_info:
        return  # already sent or gave up
    if 'otid' not in sync_info:
        return  # Message is not ready on external storage

    if 'language' in sync_info:
        logger.warning('Switch to language: %s', sync_info['language'])
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

    if 'passphrase_out' not in sync_info:
        # Temporary set empty passphrase during upgrade
        # This can be removed:
        sync_info['passphrase_out'] = ''

    notification_text = _('''Hello

You can read your message at https://onetime.info/{otid}#{passphrase_out}
or http://7z4nl4ojzggwicx5.onion/{otid}#{passphrase_out} if you are using
tor [1].

Warning, that message will be displayed only once, and then deleted. Have a pen
ready before clicking the link.

Do not reply to that email: Use the link above.
If the link doesn't work, please try again.
If you get an error saying the message was already read, but you were not the
one to read it, please repport that.

[1] https://www.torproject.org/''')

    notification_html = _('''<p>Hello</p>

<p>You can read your message at
<a href="https://onetime.info/{otid}#{passphrase_out}">
https://onetime.info/{otid}#{passphrase_out}</a><br>
or <a href="http://7z4nl4ojzggwicx5.onion/{otid}#{passphrase_out}">
http://7z4nl4ojzggwicx5.onion/{otid}#{passphrase_out}</a> if you are using
<a href="https://www.torproject.org/">tor</a>.</p>

<p>Warning, that message will be displayed only once, and then deleted. Have a
pen ready before clicking the link.</p>

<p>Do not reply to that email: Use the link above.<br>
If the link doesn't work, please try again.<br>
If you get an error saying the message was already read, but you were not the
one to read it, please repport that.</p>''')

    message = mail.EmailMultiAlternatives(
        subject=msg.subject,
        body=notification_text.format(**sync_info),
        to=(mail_addr,),
        connection=SMTP_CONNECTION)
    message.attach_alternative(notification_html.format(**sync_info),
                               "text/html")

    try:
        message.send()
        sync_info['email_sent'] = True

    except smtplib.SMTPRecipientsRefused as err:
        # Here, err.recipients is a dictionary with a single entry, like
        # { 'toto@riseup.net': (550, b'5.1.1 <eliandre@riseup.net>:
        # Recipient address rejected: User unknown')}
        errmsg = str(err.recipients.popitem()[1][1], 'utf-8', 'replace')
        logger.warning(
            'Giving up on onetime message notification for message %s: %s',
            msg.id, errmsg)
        sync_info['email_sent'] = False
        # no return here

    except smtplib.SMTPResponseException as err:
        logger.critical('SMTPResponseException: %s', err)
        if err.smtp_code // 100 == 4:
            logger.warning('Temporarary SMTP failure: %s', err)
        if err.smtp_code == 450:
            logger.info('Message rate exceeded: giving up for now')
            SMTP_SERVER_CONGESTION = True
        return

    except smtplib.SMTPException as err:  # All other errors
        # including smtplib.SMTPServerDisconnected
        logger.critical('SMTPException %s', err)
        return

    msg.sync_info = json.dumps(sync_info)
    msg.save()


def read_answers(msg):
    "step 3 : Fetch answers"

    sync_info = json.loads(msg.sync_info)
    if 'answer_password' not in sync_info:
        return
    if 'deleted' in sync_info:
        # Ignore message that were deleted on remote storage
        return
    # We have to open a new connection each time
    # since we can't handle keep-alive yet
    ot_conn = http.client.HTTPSConnection('onetime.info', timeout=TIMEOUT)

    ot_conn.request(
        'POST',
        '/'+sync_info['otid']+'/answers',
        urllib.parse.urlencode(
            {'password': sync_info['answer_password']}),
        {
            'Content-type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        })
    response = ot_conn.getresponse()  # TODO: except httplib.BadStatusLine
    if response.status == 404:
        logger.info("Message is gone: %s %s",
                    response.status, response.reason)
        # tag the message as deleted, so we stop trying to synchronise again
        # and again
        sync_info['deleted'] = True
        msg.sync_info = json.dumps(sync_info)
        msg.save()
        return
    if response.status != 200:
        logger.error("Temporary storage server error: %s %s",
                     response.status, response.reason)
        logger.error("%s", response.read())
        return
    # jresponse = json.load(response)
    sresponse = response.read()
    jresponse = json.loads(force_str(sresponse))
    logger.debug(jresponse)
    if 'read_date' in jresponse and not msg.read_date:
        read_date = jresponse.get('read_date', None)
        read_date = datetime.datetime.strptime(read_date, '%Y-%m-%d %H:%M:%S')
        if settings.USE_TZ:
            read_date = timezone.make_aware(
                read_date, timezone.get_default_timezone())
        msg.read_date = read_date
        msg.save()
    passphrase = sync_info.get('passphrase_out', None)
    for response_text in jresponse['answers']:
        logger.info('Received answer from %s.', msg.contact)
        if passphrase:
            try:
                response_text += '\n'  # openssl limitation
                response_text = response_text.encode(settings.DEFAULT_CHARSET)
                response_text = subprocess.check_output(
                    ['openssl', 'enc', '-aes-256-cbc',
                     '-pass', 'pass:{}'.format(passphrase),
                     '-d', '-base64', '-A',
                     '-md', 'md5'],
                    input=response_text)
                response_text = force_text(response_text)
            except subprocess.CalledProcessError:
                # Retry with an empty passphrase
                try:
                    response_text = subprocess.check_output(
                        ['openssl', 'enc', '-aes-256-cbc',
                         '-pass', 'pass:',
                         '-d', '-base64', '-A',
                         '-md', 'md5'],
                        input=response_text)
                    response_text = force_text(response_text)
                except subprocess.CalledProcessError:
                    logger.error("Message decryption failed.")

        # Hack into headers: Add the "From"
        mailmessage = email.message_from_string(response_text,
                                                policy=email.policy.SMTP)
        mailmessage['From'] = msg.contact.get_email_to()
        if not mailmessage.get('Subject', None):
            mailmessage['Subject'] = 'Re: ' + msg.subject
        response_text = mailmessage.as_string(
                mailmessage.policy.clone(linesep='\r\n'))

        answer_msg = ContactMsg(
            group_id=msg.group_id,
            contact_id=msg.contact_id,
            send_date=timezone.now(),
            subject='Re: ' + msg.subject,
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


def get_related_messages(msg):
    sync_info = json.loads(msg.sync_info)
    if 'otid' not in sync_info:
        return ()
    otid = sync_info['otid']
    results = ContactMsg.objects
    results = results.filter(
        sync_info__contains=json.dumps({'otid': otid})[1:-1])
    results = results.filter(
        sync_info__contains=json.dumps({'backend': __name__})[1:-1])
    results = results.exclude(pk=msg.pk)
    results = results.order_by('-send_date')
    return results
