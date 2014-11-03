# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import sys
import os
import fcntl
import logging
import json
from importlib import import_module
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import NoArgsCommand
from ngw.core.models import ContactMsg

class Command(NoArgsCommand):
    help = 'External message synchronisation'

    def handle_noargs(self, **options):
        self.setup_logger(**options)
        self.acquire_lock()
        try:
            self.process_all_messages()
        finally:
            self.release_lock()

    def setup_logger(self, **options):
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
        self.logger = logger

    def get_pid_filename(self):
        return os.path.join(settings.BASE_DIR, 'msgsync.pid')

    def acquire_lock(self):
        pid_filename = self.get_pid_filename()

        try:
            pid_file = open(pid_filename, 'a+')
        except:
            self.logger.critical(
                "Can't open file %s in read/write mode" % pid_filename)
            sys.exit(1)

        try:
            fcntl.flock(pid_file, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except:
            # Another process is currently modifying the pid file.
            self.logger.critical(
                "Can't lock pid file %s. Aborting." % pid_filename)
            sys.exit(1)

        pid_file.seek(0)
        pid = pid_file.read()
        if pid:
            # pid file is not empty!
            self.logger.warning(
                "PID file found. Checking process %s." % pid)
            if os.path.exists('/proc/%s' % pid):
                self.logger.critical(
                    "Process %s is running. Aborting." % pid)
                sys.exit(1)
            else:
                self.logger.error(
                    "Process %s is not running. Ignoring stalled pid file."
                     % pid)

        pid_file.seek(0)
        pid_file.write('%s' % os.getpid())
        pid_file.close()  # This releases the lock, leaving the pid file: success

    def release_lock(self):
        os.unlink(self.get_pid_filename())

    def process_all_messages(self):
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
