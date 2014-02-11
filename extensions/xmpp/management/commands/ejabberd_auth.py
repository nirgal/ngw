#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
import sys
import logging
import struct
from django.core.management.base import NoArgsCommand
from django.conf import settings
from django.contrib.auth.hashers import check_password
from ngw.core.models import ( ContactFieldValue,
    FIELD_LOGIN, FIELD_PASSWORD )

print('In ejabberd auth', file=sys.stderr)

def send_result(result):
    logging.debug('Sending result: %s', result)
    sys.stdout.write(struct.pack(b'>hh', 2, result and 1 or 0))
    sys.stdout.flush()
    logging.debug('Result sent')


def cmd_auth(login, domain, password):
    try:
        login_value = ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN, value=login)
    except ContactFieldValue.DoesNotExist:
        logging.info('No user with login %s', login)
        return False

    cid = login_value.contact_id
    contact = login_value.contact
    if not contact.is_member_of(settings.XMPP_GROUP):
        logging.info('User %s is not member of group XMPP', login)
        return False

    try:
        dbpassword = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=FIELD_PASSWORD).value
    except ContactFieldValue.DoesNotExist:
        logging.info('User %s has no password', login)
        return False

    logging.debug('Checking passord for user %s', login)
    if check_password(password, dbpassword):
        logging.info('User %s auth successful', login)
        return True
    else:
        logging.info('Bad password for user %s', login)
        return False

def cmd_isuser(login, domain):
    try:
        login_value = ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN, value=login)
    except ContactFieldValue.DoesNotExist:
        logging.info('No user with login %s', login)
        return False

    cid = login_value.contact_id
    contact = login_value.contact
    if not contact.is_member_of(settings.XMPP_GROUP):
        logging.info('User %s is not member of group XMPP', login)
        return False
    return True

def main():
    logging.debug('Incoming connection. Reading command length...')
    cmdlength = sys.stdin.read(2)
    logging.debug('Received %s', repr(cmdlength))
    cmdlength, = struct.unpack(b'>h', cmdlength)

    logging.debug('Reading %s bytes long command...', cmdlength)
    bindata = sys.stdin.read(cmdlength)

    logging.debug('Received command: %s', repr(bindata))
    data = unicode(bindata, 'utf-8', 'strict')

    data = data.split(b':', 1)
    if len(data) != 2:
        logging.error('Command %s has no arguments', data)
    cmd, args = data
    args = args.split(':')
    if cmd == 'auth':
        send_result(cmd_auth(*args))
    elif cmd == 'isuser':
        send_result(cmd_isuser(*args))
    else:
        send_result(False)
    

class Command(NoArgsCommand):
    help = 'Authentication module for ejabberd'
    
    def handle_noargs(self, **options):
        #print(repr(options), file=sys.stderr)
        verbosity = options.get('verbosity', '1')
        #print('v=', repr(verbosity), file=sys.stderr)
        if verbosity == '3':
            logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(levelname)s %(message)s',
                filename='/tmp/jabauth.log')
        while True:
            main()
