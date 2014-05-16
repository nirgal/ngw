#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import socket
import smtplib
import ssl
import httplib
import urllib
import json
import logging
import socks # You need package python-socksipy
from email.mime.text import MIMEText
from django.conf import settings


def validate_ssl_hostname(cert, expected_sslhostname):
    '''
    Tests whether certificate provides expected_sslhostname
    Returns a boolean
    TODO: Does not support wildcards.
    '''
    for line in cert['subject']:
        key, value = line[0]
        if key == 'commonName':
            if value == expected_sslhostname:
                return True
    for line in cert.get('subjectAltName', ()):
        key, value = line
        if key == 'DNS':
            if value == expected_sslhostname:
                return True
    return False


class SMTP_SSL_TOR(smtplib.SMTP_SSL):
    '''
    This is a smtplib.SMTP like object, but that use local TOR.
    Only support smtps, sslv3. Does enforce certificate validation.
    '''

    def _get_socket(self, host, port, timeout):
        
        s = socks.socksocket()
        s.setproxy(socks.PROXY_TYPE_SOCKS5, '127.0.0.1', 9050, True)

        s.connect((host, port))
        if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            s.settimeout(timeout)

        new_socket = ssl.wrap_socket(s, self.keyfile, self.certfile,
            ssl_version=ssl.PROTOCOL_SSLv3, # v2 is insecure
            ca_certs='/etc/ssl/certs/ca-certificates.crt',
            cert_reqs=ssl.CERT_REQUIRED)
        cert = new_socket.getpeercert()
        if not cert:
            raise smtplib.SMTPException("Ssl certificate of remote smtp server was not validated by any known authority.")

        # Allow the use of EMAIL_EXPECTED_SSLHOSTNAME to override default
        # value of settings.EMAIL_HOST
        try:
            expected_sslhostname = settings.EMAIL_EXPECTED_SSLHOSTNAME
        except AttributeError:
            expected_sslhostname = settings.EMAIL_HOST
        if not validate_ssl_hostname(cert, expected_sslhostname):
            raise smtplib.SMTPException('Ssl certificate is valid but does not match %s.' % expected_sslhostname)

        self.file = smtplib.SSLFakeFile(new_socket)
        return new_socket


def send_mail(addresses, message):
    assert settings.EMAIL_PORT==465, 'Sorry we only support smtps connections right now'

    charset = settings.DEFAULT_CHARSET
    msg = MIMEText(message.encode(charset), _charset=charset)
    msg['Subject'] = 'You have a message'
    msg['From'] = settings.DEFAULT_FROM_EMAIL
    msg['To'] = 'undisclosed-recipients:;'

    if b'.onion' in settings.EMAIL_HOST:
        s = SMTP_SSL_TOR(settings.EMAIL_HOST, settings.EMAIL_PORT, local_hostname='[::1]')
    else:
        s = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT)
    s.set_debuglevel(1)
    if settings.EMAIL_HOST_USER:
        s.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
    s.sendmail(settings.DEFAULT_FROM_EMAIL, addresses, msg.as_string())
    s.quit()

def send_mail2(addresses, message):
    conn = httplib.HTTPSConnection('onetime.info')
    for address in addresses:
        conn.request('POST', '/', urllib.urlencode({
            'message': message.encode(settings.DEFAULT_CHARSET),
            'once': True,
            'expiration': '7',
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

        send_mail([address], '''Hello

You can read your message at https://onetime.info%s

Warning, that message will be displayed exactly once, and then be deleted. Have
a pen ready before clicking the link. :)''' % jresponse['url'])


if __name__ == '__main__':
    send_mail2(['user@localhost'], '''Hello

This is yet another test.''')
