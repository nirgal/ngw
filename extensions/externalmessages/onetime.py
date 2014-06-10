#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import datetime
import httplib
import urllib
import json
import logging
from django.conf import settings
from django.core.mail import send_mass_mail
from ngw.core.models import ContactMsg

NOTIFICATION_SUBJECT = 'You have a message'
NOTIFICATION_TEXT = '''Hello

You can read your message at https://onetime.info/%s

Warning, that message will be displayed exactly once, and then be deleted. Have
a pen ready before clicking the link. :)'''

logger = logging.getLogger('msgsync')

# Synchronisation information stored in json (ContactMsg.sync_info):
# otid: Onetime ID
# answer_password: Onetime password to get answers
# email_sent: True if notification email was sent
# deleted: True if remote server returns 404 (deleted on remote end)

def do_sync():
    #logger.error('ERROR')
    #logger.warning('WARNING')
    #logger.info('INFO')
    #logger.debug('DEBUG')

    ot_conn = None
    messages = ContactMsg.objects.filter(is_answer=False)

    # step 1 : Send message to final storage
    for msg in messages:
        try:
            sync_info = json.loads(msg.sync_info)
        except ValueError:
            sync_info = {}
        
        logger.debug("%s %s", msg.id, sync_info)

        if 'otid' not in sync_info:
            if not ot_conn:
                ot_conn = httplib.HTTPSConnection('onetime.info')

            logger.info('Storing message for %s.', msg.cig.contact)
            ot_conn.request('POST', '/', urllib.urlencode({
                'message': msg.text.encode(settings.DEFAULT_CHARSET),
                'once': True,
                'expiration': '1',
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
                continue # Try next message
            jresponse = json.load(response)
            #logger.debug("%s", jresponse)

            sync_info['otid'] = jresponse['url'][1:]
            sync_info['answer_password'] = jresponse['answer_password']
            msg.sync_info = json.dumps(sync_info)
            msg.save()
    
    # step 2 : Send email notification
    masssmail_args = []
    for msg in messages:
        sync_info = json.loads(msg.sync_info)
        if 'email_sent' not in sync_info:
            c_mails = msg.cig.contact.get_fieldvalues_by_type('EMAIL')
            if c_mails:
                logger.info('Sending email notification to %s.', c_mails[0])
                masssmail_args.append((NOTIFICATION_SUBJECT, NOTIFICATION_TEXT % sync_info['otid'], None, (c_mails[0],)))
    #logger.debug(masssmail_args)
    if masssmail_args and send_mass_mail(masssmail_args):
        for msg in messages:
            sync_info = json.loads(msg.sync_info)
            if 'email_sent' not in sync_info:
                sync_info['email_sent'] = True
                msg.sync_info = json.dumps(sync_info)
                msg.save()
        

    # step 3 : Fetch answers
    for msg in messages:
        sync_info = json.loads(msg.sync_info)
        if 'answer_password' not in  sync_info:
            continue
        if 'deleted' in sync_info:
            # Ignore message that were deleted on remote storage
            continue
        if not ot_conn:
            ot_conn = httplib.HTTPSConnection('onetime.info')

        ot_conn.request('POST', '/'+sync_info['otid']+'/answers', urllib.urlencode({
            'password': sync_info['answer_password']
        }), {
            'Content-type': 'application/x-www-form-urlencoded',
            'X_REQUESTED_WITH': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        })
        response = ot_conn.getresponse()
        if response.status == 404:
            logger.info("Message is gone: %s %s" % (response.status, response.reason))
            # tag the message as deleted, so we stop trying to synchronise again and again
            sync_info['deleted'] = True
            msg.sync_info = json.dumps(sync_info)
            msg.save()
            continue
        if response.status != 200:
            logger.error("Temporary storage server error: %s %s" % (response.status, response.reason))
            logger.error("%s", response.read())
            continue # Try next message
        jresponse = json.load(response)
        logger.debug(jresponse)
        for response_text in jresponse:
            logger.info('Received answer from %s.', msg.cig.contact)
            answer_msg = ContactMsg(cig_id=msg.cig_id,
                send_date = datetime.datetime.utcnow(),
                text = response_text,
                is_answer = True,
                sync_info = json.dumps({'otid': sync_info['otid']}),
                )
            answer_msg.save()
