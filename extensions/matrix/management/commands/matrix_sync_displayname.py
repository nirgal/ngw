import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact, ContactGroup
from ngw.extensions.matrix.matrix import set_user_displayname

FIELD_MATRIX_DISPLAYNAME = 99


def get_contact_displayname(contact):
    displayname = contact.get_fieldvalue_by_id(FIELD_MATRIX_DISPLAYNAME)
    if not displayname:
        displayname = contact.get_name_anon()
    return displayname


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
        displayname = options['name']
        if login:
            if not displayname:
                try:
                    contact = Contact.objects.get_by_natural_key(login)
                except Contact.DoesNotExist:
                    raise CommandError(f'User "{login}" does not exist')
                displayname = contact.get_name_anon()

            result = set_user_displayname(login, displayname)
            if result:
                print(json.dumps(result, indent=4))
            return

        if displayname:
            raise CommandError('--name is only allowed if --login is defined')

        # So here login is undefined: Process all the group

        matrix_group = ContactGroup.objects.get(
                pk=settings.MATRIX_SYNC_GROUP)
        for contact in matrix_group.get_all_members():
            name = contact.name
            login = contact.get_username()
            displayname = get_contact_displayname(contact)
            print(f'{name} ( {login} ) => {displayname}')
            result = set_user_displayname(login, displayname)
            if result:
                print(json.dumps(result, indent=4))
