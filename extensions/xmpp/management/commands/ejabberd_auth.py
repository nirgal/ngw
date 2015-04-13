from __future__ import print_function

import logging
import struct
import sys

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.management.base import NoArgsCommand

from ngw.core.models import FIELD_LOGIN, FIELD_PASSWORD, ContactFieldValue


print('In ejabberd auth', file=sys.stderr)

logger = logging.getLogger('ejabberd_auth')


def send_result(result):
    logger.debug('Sending result: %s', result)
    sys.stdout.write(struct.pack(b'>hh', 2, result and 1 or 0))
    sys.stdout.flush()
    logger.debug('Result sent')


def cmd_auth(login, domain, password):
    try:
        login_value = ContactFieldValue.objects.get(
            contact_field_id=FIELD_LOGIN, value=login)
    except ContactFieldValue.DoesNotExist:
        logger.info('No user with login %s', login)
        return False

    cid = login_value.contact_id
    contact = login_value.contact
    if not contact.is_member_of(settings.XMPP_GROUP):
        logger.info('User %s is not member of group XMPP', login)
        return False

    try:
        dbpassword = ContactFieldValue.objects.get(
            contact_id=cid, contact_field_id=FIELD_PASSWORD).value
    except ContactFieldValue.DoesNotExist:
        logger.info('User %s has no password', login)
        return False

    logger.debug('Checking passord for user %s', login)
    if check_password(password, dbpassword):
        logger.info('User %s auth successful', login)
        return True
    else:
        logger.info('Bad password for user %s', login)
        return False


def cmd_isuser(login, domain):
    try:
        login_value = ContactFieldValue.objects.get(
            contact_field_id=FIELD_LOGIN, value=login)
    except ContactFieldValue.DoesNotExist:
        logger.info('No user with login %s', login)
        return False

    # cid = login_value.contact_id
    contact = login_value.contact
    if not contact.is_member_of(settings.XMPP_GROUP):
        logger.info('User %s is not member of group XMPP', login)
        return False
    return True


def cmd_setpass(login, domain, newpass):
    try:
        login_value = ContactFieldValue.objects.get(
            contact_field_id=FIELD_LOGIN, value=login)
    except ContactFieldValue.DoesNotExist:
        logger.info('No user with login %s', login)
        return False

    cid = login_value.contact_id
    contact = login_value.contact
    if not contact.is_member_of(settings.XMPP_GROUP):
        logger.info('User %s is not member of group XMPP', login)
        return False

    cfv = ContactFieldValue.objects.get(
        contact_id=cid, contact_field_id=FIELD_PASSWORD)
    cfv.value = make_password(newpass)
    cfv.save()

    logger.info('Password changed for user %s', login)
    return True


def process_line():
    logger.debug('Incoming connection. Reading command length...')
    cmdlength = sys.stdin.read(2)
    logger.debug('Received %s', repr(cmdlength))
    cmdlength, = struct.unpack(b'>H', cmdlength)

    logger.debug('Reading %s bytes long command...', cmdlength)
    bindata = sys.stdin.read(cmdlength)

    logger.debug('Received command: %s', repr(bindata))
    data = str(bindata, 'utf-8')

    data = data.split(':', 1)
    if len(data) != 2:
        logger.error('Command %s has no arguments', data)
    cmd, args = data
    args = args.split(':')
    if cmd == 'auth':
        send_result(cmd_auth(*args))
    elif cmd == 'isuser':
        send_result(cmd_isuser(*args))
    elif cmd == 'setpass':
        send_result(cmd_setpass(*args))
    else:
        logger.warning('Unknown command %s', repr(cmd))
        send_result(False)


class Command(NoArgsCommand):
    help = 'Authentication module for ejabberd'

    def handle_noargs(self, **options):
        # print(repr(options), file=sys.stderr)
        verbosity = options.get('verbosity', '1')
        # print('v=', repr(verbosity), file=sys.stderr)
        if verbosity == '3':
            logger.setLevel(logging.DEBUG)
        elif verbosity == '2':
            logger.setLevel(logging.INFO)
        elif verbosity == '1':
            logger.setLevel(logging.WARNING)
        else:
            logger.setLevel(logging.ERROR)
        hdlr = logging.FileHandler('/tmp/jabauth.log')
        hdlr.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr)

        # python3:
        sys.stdin = open(0, 'rb')  # reopen stdin in binary mode
        sys.stdout = open(1, 'wb')  # reopen stdout in binary mode

        while True:
            process_line()
