from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from ngw.core import mailman
from ngw.core.models import ContactGroup

class Command(BaseCommand):
    help = 'Synchronise with an external mailman mailing list'
    args = 'filename dump|normalize|check'
    option_list = BaseCommand.option_list + (
        make_option('-g', '--group',
            action = 'store',
            dest = 'groupid',
            type = 'int',
            help = 'specify groupid'),
        )

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError('Need exactly 2 arguments')

        action = args[1]

        filecontent = open(args[0]).read()

        if action == 'dump':
            mailman_members = mailman.parse_who_result(filecontent)
            for name, email in mailman_members:
                if name:
                    print(name, '->', mailman.normalize_name(name), end=' ')
                print('<%s>' % email)
        elif action == 'normalize':
            mailman_members = mailman.parse_who_result(filecontent)
            print('*')
            print('unscrubsribe:')
            for name, email in mailman_members:
                if name != mailman.normalize_name(name):
                    print(name, end=' ')
                    print('<%s>' % email)
            print('*')
            print('scrubsribe:')
            for name, email in mailman_members:
                if name != mailman.normalize_name(name):
                    print(mailman.normalize_name(name), end=' ')
                    print('<%s>' % email)

        elif action == 'check':
            groupid = options['groupid']
            if not groupid:
                raise CommandError('You must use -g option')
            cg = ContactGroup.objects.get(pk=groupid)
            print('Synching', cg.name)
            
            msg, unsubscribe_list, subscribe_list = mailman.synchronise_group(cg, filecontent)

            print(msg)

            print('*'*80)
            print('unscubscribe')
            for cmd in unsubscribe_list:
                print(cmd)
            print()
            print()
            print('*'*80)
            print('subscribe')
            for cmd in subscribe_list:
                print(cmd)
            print()
            print()

        else:
            raise CommandError('Unknown action')
