import logging

from django.core.management.base import BaseCommand, CommandError

from ngw.extensions.matrix import matrix


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'login',
            )
        parser.add_argument(
            'room',
            help='room id (starting with !) or room alias (starting with #)',
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

        login = options['login']
        if not login.startswith('@'):
            raise CommandError(f'login should start with "@".')
        if not login.endswith(f':{matrix.DOMAIN}'):
            raise CommandError(f'login should ends with ":{matrix.DOMAIN}".')

        room = options['room']
        if not room.startswith('#') and not room.startswith('!'):
            raise CommandError('room should be and id (starting with !) or an'
                               ' alias (starting with #).')
        if not room.endswith(f':{matrix.DOMAIN}'):
            raise CommandError(f'room should ends with ":{matrix.DOMAIN}".')

        matrix.room_join(login, room)
