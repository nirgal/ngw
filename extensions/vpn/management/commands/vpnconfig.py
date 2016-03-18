import logging
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import FIELD_LOGIN, ContactFieldValue


def ip_int_to_str(val):
    """
    That function takes a 0..2**32 interger and converts it into a string IP
    address.
    For example: 16909060 aka (1<<24)+(2<<16)+(3<<8)+4 will return 1.2.3.4
    """

    if not isinstance(val, int):
        raise TypeError('ip_int_to_str expects a number')
    if val < 0 or val >= (1 << 32):
        raise ValueError('Out of range')

    return '{}.{}.{}.{}'.format(
        (val >> 24) & 255,
        (val >> 16) & 255,
        (val >> 8) & 255,
        val & 255)


def ip_str_to_int(val):
    """
    That function takes a string with a IP address and converts it to a integer
    For example: 1.2.3.4 returns 16909060 aka (1<<24)+(2<<16)+(3<<8)+4
    """

    split = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)\.(\d+)', val)
    if split is None:
        raise ValueError('Not an IP address')
    result = 0
    for idx in range(1, 5):
        frag = int(split.group(idx))
        if frag < 0 or frag > 255:
            raise ValueError('Out of range')
        result = (result << 8) + frag
    return result


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

        try:
            baseip = settings.VPN_BASEIP
        except AttributeError:
            msg = 'Settings must define VPN_BASEIP'
            logger.critical(msg)
            raise CommandError(msg)
        baseip = ip_str_to_int(baseip)

        try:
            maxip = settings.VPN_MAXIP
        except AttributeError:
            msg = 'Settings must define VPN_MAXIP'
            logger.critical(msg)
            raise CommandError(msg)
        maxip = ip_str_to_int(maxip)

        addr = baseip+cid*4+1
        gate_addr = baseip+cid*4+2

        if addr > maxip:
            msg = 'IP range is too small to have client #{}'.format(cid)
            logger.critical(msg)
            raise CommandError(msg)

        addr = ip_int_to_str(addr)
        gate_addr = ip_int_to_str(gate_addr)

        output = 'ifconfig-push {} {}'.format(addr, gate_addr)
        logger.debug('{} ({}): {}'.format(login, cid, output))
        f.write(output+'\n')

        f.close()
