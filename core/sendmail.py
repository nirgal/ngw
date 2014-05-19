#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import httplib
import urllib
import json
import logging
from django.conf import settings
from django.core.mail import send_mass_mail



def send_mail1(addresses, text):
    subject = 'You have a message'
    send_mass_mail([(subject, text, None, [recipient])
        for recipient in addresses])


def send_mail2(addresses, message):
    conn = httplib.HTTPSConnection('onetime.info')
    for address in addresses:
        conn.request('POST', '/', urllib.urlencode({
            'message': message.encode(settings.DEFAULT_CHARSET),
            'once': True,
            'expiration': '1',
        }), {
            'Content-type': 'application/x-www-form-urlencoded',
            'X_REQUESTED_WITH': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        })
        response = conn.getresponse()
        if response.status != 200:
            logging.error("Temporary storage server error: %s %s" % (response.status, response.reason))
            logging.error("%s", response.read())
        jresponse = json.load(response)

        send_mail1([address], '''Hello

You can read your message at https://onetime.info%s

Warning, that message will be displayed exactly once, and then be deleted. Have
a pen ready before clicking the link. :)''' % jresponse['url'])


if __name__ == '__main__':
    send_mail2([settings.DEFAULT_FROM_EMAIL], '''Hello

This is yet another test.''')
