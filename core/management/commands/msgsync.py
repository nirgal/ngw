import fcntl
import logging
import os
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand

from ngw.core.models import ContactMsg


class Command(BaseCommand):
    help = 'External message synchronisation'

    def handle(self, *args, **options):
        self.setup_logger(**options)
        self.acquire_lock()
        try:
            self.process_all_messages()
        finally:
            self.release_lock()

    def setup_logger(self, **options):
        logger = logging.getLogger('msgsync')
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
        self.logger = logger

    def get_pid_filename(self):
        return os.path.join(settings.BASE_DIR, 'msgsync.pid')

    def acquire_lock(self):
        pid_filename = self.get_pid_filename()

        try:
            pid_file = open(pid_filename, 'a+')
        except:
            self.logger.critical(
                "Can't open file {} in read/write mode".format(pid_filename))
            sys.exit(1)

        try:
            fcntl.flock(pid_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except:
            # Another process is currently modifying the pid file.
            self.logger.critical(
                "Can't lock pid file {}. Aborting.".format(pid_filename))
            sys.exit(1)

        pid_file.seek(0)
        pid = pid_file.read()
        if pid:
            # pid file is not empty!
            self.logger.warning(
                "PID file found. Checking process {}.".format(pid))
            if os.path.exists('/proc/{}'.format(pid)):
                self.logger.critical(
                    "Process {} is running. Aborting.".format(pid))
                sys.exit(1)
            else:
                self.logger.error(
                    "Process {} is not running. Ignoring stalled pid file."
                    .format(pid))

        pid_file.seek(0)
        pid_file.write(str(os.getpid()))
        # This releases the lock, leaving the pid file: success:
        pid_file.close()

    def release_lock(self):
        os.unlink(self.get_pid_filename())

    def process_all_messages(self):
        n = 0
        for msg in ContactMsg.objects.filter():
            backend = msg.get_backend()
            func_name = 'sync_msg'
            try:
                func = getattr(backend, func_name)
            except AttributeError:
                raise ImproperlyConfigured((
                    'Module "{}" does not define a "{}" function'
                    .format(backend, func_name)))
            func(msg)
            n = n + 1
        if n:
            self.logger.debug('Processed {} message(s).'.format(n))
