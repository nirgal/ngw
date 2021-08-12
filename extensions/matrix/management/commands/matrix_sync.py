import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact, ContactGroup
from ngw.extensions.matrix import matrix

FIELD_MATRIX_DISPLAYNAME = 99


def get_contact_displayname(contact):
    displayname = contact.get_fieldvalue_by_id(FIELD_MATRIX_DISPLAYNAME)
    if not displayname:
        displayname = contact.get_name_anon()
    return displayname


class Command(BaseCommand):
    help = 'update matrix user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--login',
            help="Login name")
        parser.add_argument(
            '--name',
            help="Force Matrix display name, skipping NGW sync.")
        parser.add_argument(
            '--email',
            nargs='+',
            help="Force Matrix display emails, skipping NGW sync.")
        parser.add_argument(
            '--create',
            action='store_true',
            help="Create missing accounts")

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
        name = options['name']
        email = options['email']
        create = options['create']

        if login:  # process a single account
            if name or email:  # name or email is overridden
                matrix.set_user_info(
                        login,
                        name=name,
                        emails=email,
                        create=create)
            else:  # synchronise a single account
                try:
                    contact = Contact.objects.get_by_natural_key(login)
                except Contact.DoesNotExist:
                    raise CommandError(f'User "{login}" does not exist')
                name = get_contact_displayname(contact)
                emails = contact.get_fieldvalues_by_type('EMAIL')
                matrix.set_user_info(
                        login,
                        name=name,
                        emails=email,
                        create=create)
            return

        if name:
            raise CommandError('--name is only allowed if --login is defined')
        if email:
            raise CommandError('--email is only allowed if --login is defined')

        # So here login is undefined: Process all the group

        matrix_group = ContactGroup.objects.get(
                pk=settings.MATRIX_SYNC_GROUP)
        for contact in matrix_group.get_all_members():
            login = contact.get_username()
            name = get_contact_displayname(contact)
            emails = contact.get_fieldvalues_by_type('EMAIL')
            matrix.set_user_info(
                    login,
                    name=name,
                    emails=emails,
                    create=create)
