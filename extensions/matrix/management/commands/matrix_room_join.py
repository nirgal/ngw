import logging

from django.core.management.base import BaseCommand, CommandError

from ngw.extensions.matrix import matrix


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'user',
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

        user_id = options['user']
        if not user_id.startswith('@'):
            raise CommandError(f'user_id should start with "@".')
        if not user_id.endswith(f':{matrix.DOMAIN}'):
            raise CommandError(f'user_id should ends with ":{matrix.DOMAIN}".')

        room_id = options['room']
        if not room_id.startswith('#') and not room_id.startswith('!'):
            raise CommandError('room_id should be and id (starting with !) or'
                               'an alias (starting with #).')
        if not room_id.endswith(f':{matrix.DOMAIN}'):
            raise CommandError(f'room_id should ends with ":{matrix.DOMAIN}".')

        matrix.room_join(user_id, room_id)
