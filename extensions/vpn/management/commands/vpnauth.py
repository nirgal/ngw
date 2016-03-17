import logging

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import FIELD_LOGIN, ContactFieldValue


class Command(BaseCommand):
    help = 'Plugin for openvpn --auth-user-pass-verify via-file'

    def handle(self, *args, **options):
        logger = logging.getLogger('vpn')
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{asctime} {name} {levelname!s:8} {message}', style='{'))
        logger.addHandler(handler)
        verbosity = int(options['verbosity'])
        if verbosity == 0:
            logger.setLevel(logging.ERROR)
        elif verbosity == 1:
            logger.setLevel(logging.WARNING)
        elif verbosity == 2:
            logger.setLevel(logging.INFO)
        elif verbosity == 3:
            logger.setLevel(logging.DEBUG)

        logger.debug('vpnauth.handle starts.')

        try:
            vpn_group = settings.VPN_GROUP
        except AttributeError:
            msg = 'Settings must define VPN_GROUP'
            logger.critical(msg)
            raise CommandError(msg)
        try:
            vpn_field_password = settings.VPN_FIELD_PASSWORD
        except AttributeError:
            msg = 'Settings must define VPN_FIELD_PASSWORD'
            logger.critical(msg)
            raise CommandError(msg)

        if len(args) != 1:
            msg = ("This script takes exactly one argument. Are you really "
                   "using openvpn --auth-user-pass-verify via-file?")
            logger.critical(msg)
            raise CommandError(msg)

        filename = args[0]
        logger.debug('processing file {}'.format(filename))
        try:
            f = open(filename)
        except FileNotFoundError:
            msg = "Error opening temporary file {}".format(filename)
            logger.critical(msg)
            raise CommandError(msg)

        try:
            login, password, dummy = f.read().split('\n')
        except ValueError:
            msg = "File {} should be exactly 2 lines long.".format(filename)
            logger.critical(msg)
            raise CommandError(msg)

        f.close()

        logging.debug('Authenticating {}'.format(login))

        try:
            login_value = ContactFieldValue.objects.get(
                contact_field_id=FIELD_LOGIN, value=login)
        except ContactFieldValue.DoesNotExist:
            msg = 'Contact with login "{}" not found.'.format(login)
            logger.info(msg)
            raise CommandError(msg)

        cid = login_value.contact_id
        contact = login_value.contact

        if not contact.is_member_of(vpn_group):
            msg = 'User {} is not member of group VPN'.format(login)
            logger.info(msg)
            raise CommandError(msg)

        try:
            dbpassword = ContactFieldValue.objects.get(
                contact_id=cid, contact_field_id=vpn_field_password).value
        except ContactFieldValue.DoesNotExist:
            msg = 'User {} has no password'.format(login)
            logger.info(msg)
            raise CommandError(msg)

        logger.debug('Checking passord for user %s', login)
        if check_password(password, dbpassword):
            logger.info('User %s auth successful', login)
        else:
            msg = 'Bad password for user {}'.format(login)
            logger.info(msg)
            raise CommandError(msg)
