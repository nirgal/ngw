import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact, ContactGroup
from ngw.extensions.matrix.matrix import get_user_info, set_user_info


def sync_login_emails(login, emails=None):
    logger = logging.getLogger('command')

    matuser = get_user_info(login)
    if not matuser:
        raise CommandError(f'User "{login}" does not exist in matrix')
    mat_emails = [
        threepid['address']
        for threepid in matuser.get('threepids', [])
        if threepid['medium'] == 'email'
        ]

    if emails is None:
        try:
            contact = Contact.objects.get_by_natural_key(login)
        except Contact.DoesNotExist:
            raise CommandError(f'User "{login}" does not exist in ngw')
        emails = contact.get_fieldvalues_by_type('EMAIL')

    mat_emails = set(mat_emails)
    emails = set(emails)
    if mat_emails == emails:
        logger.info(f'{login}: No change')
    else:
        emails = mat_emails | emails
        logger.info(f'{login}: {mat_emails} => {emails}')
        data = {
            'threepids': [
                {'medium': 'email', 'address': email}
                for email in emails
                ]
            }
        result = set_user_info(login, data)
        if result:
            logger.debug(json.dumps(result, indent=4))


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
        if login:
            sync_login_emails(login, email)
            return

        if email:
            raise CommandError('--email is only allowed if --login is defined')

        # So here login is undefined: Process all the group

        matrix_group = ContactGroup.objects.get(
                pk=settings.MATRIX_SYNC_GROUP)
        for contact in matrix_group.get_all_members():
            login = contact.get_username()
            matuser = get_user_info(login)
            if not matuser:
                logger.error(f'User "{login}" does not exist in matrix')
                continue
            sync_login_emails(login)
