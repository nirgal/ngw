import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact, ContactGroup
from ngw.extensions.matrix import matrix


def sync_login_emails(login, emails=None, create=False):
    if emails is None:
        try:
            contact = Contact.objects.get_by_natural_key(login)
        except Contact.DoesNotExist:
            raise CommandError(f'User "{login}" does not exist in ngw')
        emails = contact.get_fieldvalues_by_type('EMAIL')

    matrix.set_user_info(
            login,
            emails=emails,
            create=create)


class Command(BaseCommand):
    help = 'update matrix emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--login',
            help="Login name")
        parser.add_argument(
            '--email',
            nargs='+',
            help="Force emails")
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
        email = options['email']
        create = options['create']

        if login:
            sync_login_emails(login, email, create)
            return

        if email:
            raise CommandError('--email is only allowed if --login is defined')

        # So here login is undefined: Process all the group

        matrix_group = ContactGroup.objects.get(
                pk=settings.MATRIX_SYNC_GROUP)
        for contact in matrix_group.get_all_members():
            login = contact.get_username()
            sync_login_emails(login, None, create)
