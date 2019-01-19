import logging
import sys

from django.core.management.base import BaseCommand, CommandError

from ngw.core.models import GROUP_USER_PHPBB, Contact, ContactGroup
from ngw.extensions.phpbb import print_and_call, sync_user_all


class Command(BaseCommand):
    help = 'PHPBB3 synchronisation tool'

    def add_arguments(self, parser):
        parser.add_argument(
            '-u', '--user',
            action="append", type="int",
            help="Synchronisation only acts on specified NGW user id."
        )

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

        if len(args) != 1:
            raise CommandError('Need exactly one argument')

        if args[0] == "full":
            # We don't want to delete phpbb users. We can revoke acces, but we
            # don't want to remove existing messages.

            main_phpbb_changed = False

            if not options['user']:
                user_set = (ContactGroup
                            .objects
                            .get(pk=GROUP_USER_PHPBB)
                            .get_all_members())
            else:
                user_set = []
                for ngw_user_id in options['user']:
                    u = Contact.objects.get(pk=ngw_user_id)
                    if not u:
                        print("No user", ngw_user_id, file=sys.stderr)
                        sys.exit(1)
                    # TODO: if not member of @users must have a phpbb_user_id
                    user_set.append(u)

            for u in user_set:
                main_phpbb_changed = sync_user_all(u) or main_phpbb_changed

            if main_phpbb_changed:
                print_and_call(
                    "sudo", "-u",  "www-data",
                    "/usr/lib/ngw/extensions/phpbb/clearcache.php")
