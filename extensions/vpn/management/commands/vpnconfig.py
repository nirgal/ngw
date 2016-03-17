import logging
import os

from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import FIELD_LOGIN, ContactFieldValue

NETBASE16 = '10.241'


class Command(BaseCommand):
    help = 'Plugin for openvpn --client-connect'

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

        logger.debug('vpnconfig.handle starts.')

        # logger.debug('vpnconfig args: {}'.format(args))
        # logger.debug('vpnconfig environment: {}'.format(os.environ))

        if len(args) != 1:
            msg = ("This script takes exactly one argument. Are you really "
                   "using openvpn --client-connect?")
            logger.critical(msg)
            raise CommandError(msg)

        filename = args[0]
        logger.debug('Appending configuration to file {}'.format(filename))
        try:
            f = open(filename, 'a')
        except FileNotFoundError:
            msg = "Error opening temporary file {}".format(filename)
            logger.critical(msg)
            raise CommandError(msg)

        try:
            login = os.environ['common_name']
        except KeyError:
            msg = "Environment doesn't contains common_name."
            logger.critical(msg)
            raise CommandError(msg)

        logger.debug('Setting up network for {}'.format(login))

        try:
            login_value = ContactFieldValue.objects.get(
                contact_field_id=FIELD_LOGIN, value=login)
        except ContactFieldValue.DoesNotExist:
            msg = 'Contact with login "{}" not found.'.format(login)
            logger.info(msg)
            raise CommandError(msg)

        cid = login_value.contact_id
        # contact = login_value.contact

        output = 'ifconfig-push {}.{}.{} {}.{}.{}'.format(
            NETBASE16, (cid*4+1)//255, (cid*4+1) % 255,
            NETBASE16, (cid*4+2)//255, (cid*4+2) % 255)
        logger.debug('{} ({}): {}'.format(login, cid, output))
        f.write(output+'\n')

        f.close()
