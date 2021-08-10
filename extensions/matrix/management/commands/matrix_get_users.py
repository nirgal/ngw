import json
import logging

from django.core.management.base import BaseCommand

from ngw.extensions.matrix.matrix import get_users


class Command(BaseCommand):
    help = 'list matrix users'

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

        for user in get_users():
            print(json.dumps(user, indent=4))
