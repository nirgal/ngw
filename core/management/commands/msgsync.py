# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
import json
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import NoArgsCommand
from django.utils.importlib import import_module
from ngw.core.models import ContactMsg

class Command(NoArgsCommand):
    help = 'External message synchronisation'

    def handle_noargs(self, **options):
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

        known_backends = {}

        for msg in ContactMsg.objects.filter():
            sync_info = json.loads(msg.sync_info)
            backend_name = sync_info['backend']
            try:
                backend = known_backends[backend_name]
            except KeyError:
                try:
                    backend = import_module(backend_name)
                except ImportError as e:
                    raise ImproperlyConfigured(('Error importing external messages backend module %s: "%s"'
                        % (mod_name, e)))
                known_backends[backend_name] = backend

            func_name = 'sync_msg'
            try:
                func = getattr(backend, func_name)
            except AttributeError:
                raise ImproperlyConfigured(('Module "%s" does not define a '
                    '"%s" function' % (backend_name, func_name)))
            func(msg)
