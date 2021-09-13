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
        # TODO: change login by user
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
            '--admin',
            action='store_true',
            help="Make admin, skipping NGW sync.")
        parser.add_argument(
            '--no-create',
            action='store_true',
            help="Don't create missing matrix accounts")
        parser.add_argument(
            '--no-delete',
            action='store_true',
            help="Don't delete missing matrix accounts")

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
        admin = options['admin']
        ocreate = not options['no_create']
        odelete = not options['no_delete']

        if login:  # process a single account
            user_id = f'@{login}:{matrix.DOMAIN}'
            if odelete:
                raise CommandError('--delete and --login are incompatible')
            if name or email or admin:  # ngw info is overriden
                matrix.set_user_info(
                        user_id,
                        name=name,
                        emails=email,
                        admin=admin,
                        create=ocreate)
            else:  # synchronise a single account
                try:
                    contact = Contact.objects.get_by_natural_key(login)
                except Contact.DoesNotExist:
                    raise CommandError(f'User "{login}" does not exist')
                name = get_contact_displayname(contact)
                emails = contact.get_fieldvalues_by_type('EMAIL')
                if matrix.set_user_info(
                        user_id,
                        name=name,
                        emails=email,
                        admin=admin,
                        create=ocreate):
                    logger.debug(f'Updated {login}')
                else:
                    logger.debug(f'No change for {login}')
            return

        if name:
            raise CommandError('--name is only allowed if --login is defined')
        if email:
            raise CommandError('--email is only allowed if --login is defined')
        if admin:
            raise CommandError('--admin is only allowed if --login is defined')

        # So here login/name/email/admin are undefined: Process all the group

        logger.debug('Checking ngw users against matrix users')

        matrix_group = ContactGroup.objects.get(
                pk=settings.MATRIX_SYNC_GROUP)
        for contact in matrix_group.get_all_members():
            login = contact.get_username()
            name = get_contact_displayname(contact)
            emails = contact.get_fieldvalues_by_type('EMAIL')
            user_id = f'@{login}:{matrix.DOMAIN}'
            if matrix.set_user_info(
                    user_id,
                    name=name,
                    emails=emails,
                    create=ocreate):
                logger.debug(f'Updated {user_id}')
            else:
                logger.debug(f'No change for {user_id}')

        if odelete:
            logger.debug('Checking matrix users against ngw users')

            for user in matrix.get_users():
                user_id = user['name']  # localpart + domain
                login = matrix.localpart(user_id)

                delete = False
                try:
                    contact = Contact.objects.get_by_natural_key(login)
                except Contact.DoesNotExist:
                    logger.warning(
                            f'{login} is defined by matrix but not in ngw')
                    delete = True
                else:
                    if not contact.is_member_of(settings.MATRIX_SYNC_GROUP):
                        logger.warning(
                            f'{login} is not member of group {matrix_group}')
                        delete = True

                if delete:
                    logger.info(f'Deactivating matrix account {user_id}')
                    matrix.deactivate_account(user_id)
                else:
                    logger.debug(f'Account {login} is ok')
