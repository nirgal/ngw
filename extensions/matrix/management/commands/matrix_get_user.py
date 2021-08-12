import json
import logging

from django.core.management.base import BaseCommand, CommandError

from ngw.extensions.matrix.matrix import NoSuchUser, get_user_info


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'login',
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

        login = options['login']

        try:
            info = get_user_info(login)
            print(json.dumps(info, indent=4))
        except NoSuchUser:
            raise CommandError(f'User {login} does not exist')
