import logging

from django.core.management.base import BaseCommand

from ngw.extensions.matrix import matrix


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'user',
            )
        parser.add_argument(
            'password',
            )

    def handle(self, *args, **options):
        logger = logging.getLogger('command')
        verbosity = options.get('verbosity', None)
        if verbosity == 3:
            logger.setLevel(logging.DEBUG)
        elif verbosity == 2:
            logger.setLevel(logging.INFO)
        elif verbosity == 1:
            logger.setLevel(logging.WARNING)
        elif verbosity == 0:
            logger.setLevel(logging.ERROR)
        # else value settings['LOGGING']['command']['level'] is used

        user_id = options['user']
        password = options['password']

        matrix.reset_password(
                user_id,
                password)
