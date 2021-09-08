import json
import logging

from django.core.management.base import BaseCommand, CommandError

from ngw.extensions.matrix import matrix


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'room',
            help='room id (starting with !) or room alias (starting with #)',
            )
        parser.add_argument(
            'event',
            help='event if (starting with $)',
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

        roomid = options['room']
        eventid = options['event']

        if not roomid.startswith('#') and not roomid.startswith('!'):
            raise CommandError('room should be and id (starting with !) or an'
                               ' alias (starting with #).')
        # if ':' in roomid:
        #     raise CommandError('room should not include the domain.')

        # event = matrix.get_event(eventid)
        # event = matrix.get_room_event(roomid, eventid)
        # print(json.dumps(event, indent=4))

        res = matrix.redact_event(roomid, eventid)
        print(json.dumps(res, indent=4))
