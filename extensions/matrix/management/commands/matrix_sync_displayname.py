import json
import logging

from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact
from ngw.extensions.matrix.matrix import set_user_displayname


class Command(BaseCommand):
    help = 'update matrix displayname'

    def add_arguments(self, parser):
        parser.add_argument(
            '--login',
            help="Login name")
        parser.add_argument(
            '--name',
            help="Matrix display name")

    def handle(self, *args, **options):
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

        login = options['login']
        displayname = options['name']
        if not login or not displayname:
            raise CommandError(
                    'You currently need login and display name options')

        try:
            contact = Contact.objects.get_by_natural_key(login)
        except Contact.DoesNotExist:
            raise CommandError(f'User "{login}" does not exist')

        name = contact.name
        tokens = name.strip().split(' ')
        shortname = tokens[0]
        reminder = ''.join(tokens[1:])
        if reminder:
            shortname += ' ' + reminder[0]
        print(name, '=>', shortname)

        return
        result = set_user_displayname(login, displayname)

        if result:
            print(json.dumps(result, indent=4))
