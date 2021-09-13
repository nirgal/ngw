import json
import logging

from django.core.management.base import BaseCommand, CommandError

from ngw.extensions.matrix import matrix


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'user',
            help="Login name")

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
        if not user_id.startswith('@'):
            raise CommandError(f'user_id should start with "@".')
        if not user_id.endswith(f':{matrix.DOMAIN}'):
            raise CommandError(f'user_id should ends with ":{matrix.DOMAIN}".')

        try:
            info = matrix.get_user_info(user_id)
            print(json.dumps(info, indent=4))
        except matrix.NoSuchUser:
            raise CommandError(f'User {user_id} does not exist')
