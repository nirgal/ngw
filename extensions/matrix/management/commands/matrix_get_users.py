import json
import logging

from django.core.management.base import BaseCommand

from ngw.extensions.matrix.matrix import get_users


class Command(BaseCommand):
    help = 'list matrix users'

    def handle(self, **options):
        verbosity = options.get('verbosity', '1')
        if verbosity == '3':
            loglevel = logging.DEBUG
        elif verbosity == '2':
            loglevel = logging.INFO
        elif verbosity == '1':
            loglevel = logging.WARNING
        else:
            loglevel = logging.ERROR

        logging.basicConfig(level=loglevel,
                            format='{asctime} {levelname} {message}',
                            style='{')
        for user in get_users():
            print(json.dumps(user, indent=4))
