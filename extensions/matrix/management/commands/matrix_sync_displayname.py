import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact, ContactGroup
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
        if login:
            if displayname:
                result = set_user_displayname(login, displayname)
                if result:
                    print(json.dumps(result, indent=4))

            try:
                contact = Contact.objects.get_by_natural_key(login)
            except Contact.DoesNotExist:
                raise CommandError(f'User "{login}" does not exist')

            result = set_user_displayname(login, contact.get_name_anon())
            if result:
                print(json.dumps(result, indent=4))
            return

        if displayname:
            raise CommandError('--name is only allowed if --login is defined')

        # So here login is undefined: Process all the group

        matrix_group = ContactGroup.objects.get(
                pk=settings.MATRIX_SYNC_GROUP)
        print(matrix_group)
        for contact in matrix_group.get_all_members():
            print(contact.name, '=>', contact.get_name_anon())
