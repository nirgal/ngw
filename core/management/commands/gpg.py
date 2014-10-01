# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
import json
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import NoArgsCommand
from django.utils.importlib import import_module
from ngw.core.gpg import loadkeyring

class Command(NoArgsCommand):
    help = 'Gpg dump'

    def handle_noargs(self, **options):
        logger = logging.getLogger('gpgdump')
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s'))
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

        print(loadkeyring())