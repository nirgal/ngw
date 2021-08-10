import json
import logging

from django.core.management.base import BaseCommand

from ngw.extensions.matrix.matrix import get_user_info


class Command(BaseCommand):
    help = 'update matrix user information'

    def add_arguments(self, parser):
        parser.add_argument(
            'login',
            help="Login name")

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', '1')
        if verbosity == 3:
            loglevel = logging.DEBUG
        elif verbosity == 2:
            loglevel = logging.INFO
        elif verbosity == 1:
            loglevel = logging.WARNING
        else:
            loglevel = logging.ERROR

        logging.basicConfig(level=loglevel,
                            format='{asctime} {levelname} {message}',
                            style='{')

        login = options['login']
        info = get_user_info(login)

        print(json.dumps(info, indent=4))
