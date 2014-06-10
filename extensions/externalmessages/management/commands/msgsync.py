#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import NoArgsCommand
from django.utils.importlib import import_module
from django.conf import settings

class Command(NoArgsCommand):
    help = 'External message synchronisation'

    def handle_noargs(self, **options):
        try:
            mod_name = settings.EXTERNAL_MESSAGE_BACKEND
        except AttributeError as e:
            raise ImproperlyConfigured(('You need to add an "EXTERNAL_MESSAGE_BACKEND" handler in your settings.py: "%s"'
                % e))
        try:
            mod = import_module(mod_name)
        except ImportError as e:
            raise ImproperlyConfigured(('Error importing external messages backend module %s: "%s"'
                % (mod_name, e)))

        func_name = 'do_sync'
        try:
            func = getattr(mod, func_name)
        except AttributeError:
            raise ImproperlyConfigured(('Module "%s" does not define a '
                '"%s" function' % (mod_name, func_name)))

        logger = logging.getLogger('msgsync')
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
        func()
