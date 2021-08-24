import json
import logging

from django.core.management.base import BaseCommand

from ngw.extensions.matrix import matrix


class Command(BaseCommand):
    help = 'list matrix users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detail',
            action='store_true',
            help="don't include")

    def handle(self, **options):
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

        detail = options['detail']

        if detail:
            for room in matrix.get_rooms():
                print(json.dumps(room, indent=4))
        else:
            for room in matrix.get_rooms_quick():
                print(json.dumps(room, indent=4))
