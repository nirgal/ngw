import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import Contact, ContactGroup, MatrixRoom
from ngw.extensions.matrix import matrix

FIELD_MATRIX_DISPLAYNAME = 99
FIELD_MATRIX_DISABLED = 100    # matrix users
MATRIX_ADMIN_ID = f'@adminatrix:{matrix.DOMAIN}'  # admin user, never kick out
MATRIX_MOD_GROUP = settings.MATRIX_MOD_GROUP


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
            disabled = contact.get_fieldvalue_by_id(FIELD_MATRIX_DISABLED)
            if disabled:
                continue

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
                    disabled = contact.get_fieldvalue_by_id(
                            FIELD_MATRIX_DISABLED)
                    if disabled:
                        logger.warning(
                            f'{login} emergency disabled is set.'
                            ' Deleting account.')
                        delete = True

                if delete:
                    logger.info(f'Deactivating matrix account {user_id}')
                    matrix.deactivate_account(user_id)
                else:
                    logger.debug(f'Account {login} is ok')

        # Synchronize the rooms

        logger.debug('Checking room members')

        for ngw_room in MatrixRoom.objects.all():
            room_id = ngw_room.id
            logger.debug(f'Checking room {room_id} against'
                         f' {ngw_room.contact_group}')
            # room_info = matrix.get_room_info(room_id)
            # print(room_info)
            room_state = matrix._room_state_clean(
                    matrix.get_room_state(room_id)['state'])
            mat_members = room_state['members']
            # print(mat_members)

            ngw_members = ngw_room.contact_group.get_all_members()
            # print(ngw_members)

            # Check for room members who shouln't be there
            for mat_member in mat_members:
                user_id = mat_member['user_id']
                login = matrix.localpart(user_id)
                membership = mat_member['membership']
                if membership != 'leave' and user_id != MATRIX_ADMIN_ID:
                    kick_request = False
                    try:
                        contact = Contact.objects.get_by_natural_key(login)
                    except Contact.DoesNotExist:
                        logger.error(
                                f'{login} is defined by matrix but not in ngw')
                        kick_request = True
                    else:
                        if (
                           not contact.is_member_of(ngw_room.contact_group_id)
                           # moderator are never kicked out:
                           and not contact.is_member_of(MATRIX_MOD_GROUP)
                           ):
                            logger.info(f'{login} is not a member of'
                                        f' {ngw_room.contact_group}: kicking'
                                        ' out!')
                            kick_request = True

                    if kick_request:
                        matrix.room_kick(room_id, user_id)

            # Check for missing room members
            for contact in ngw_members:
                login = contact.get_username()
                user_id = f'@{login}:{matrix.DOMAIN}'
                membership = None
                for mat_member in mat_members:
                    if mat_member['user_id'] == user_id:
                        membership = mat_member['membership']
                        break  # no use scaning the other entries

                if not contact.is_member_of(settings.MATRIX_SYNC_GROUP):
                    continue  # no matrix account, this is ok

                if contact.get_fieldvalue_by_id(FIELD_MATRIX_DISABLED):
                    continue  # Matrix account disabled: this is ok

                if not membership:
                    logger.info(f'{login} is missing in {room_id}: inviting.')
                    matrix.room_invite(room_id, user_id)
