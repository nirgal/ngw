from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from ngw.core import mailman
from ngw.core.models import ContactGroup


class Command(BaseCommand):
    help = 'Synchronise with an external mailman mailing list'
    args = 'filename dump|normalize|check'
    option_list = BaseCommand.option_list + (
        make_option(
            '-g', '--group',
            action='store',
            dest='groupid',
            type='int',
            help='specify groupid'),
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
                    self.stdout.write(name, '->', mailman.normalize_name(name),
                                      ending=' ')
                self.stdout.write('<{email}>'.format(email=email))
        elif action == 'normalize':
            mailman_members = mailman.parse_who_result(filecontent)
            self.stdout.write('*')
            self.stdout.write('unscrubsribe:')
            for name, email in mailman_members:
                if name != mailman.normalize_name(name):
                    self.stdout.write(name, ending=' ')
                    self.stdout.write('<{email}>'.format(email=email))
            self.stdout.write('*')
            self.stdout.write('scrubsribe:')
            for name, email in mailman_members:
                if name != mailman.normalize_name(name):
                    self.stdout.write(mailman.normalize_name(name), ending=' ')
                    self.stdout.write('<{email}>'.format(email=email))

        elif action == 'check':
            groupid = options['groupid']
            if not groupid:
                raise CommandError('You must use -g option')
            cg = ContactGroup.objects.get(pk=groupid)
            self.stdout.write('Synching {}'.format(cg))

            msg, unsubscribe_list, subscribe_list = mailman.synchronise_group(
                cg, filecontent)

            self.stdout.write(str(msg))

            self.stdout.write('*'*80)
            self.stdout.write('unscubscribe')
            for cmd in unsubscribe_list:
                self.stdout.write(str(cmd))
            self.stdout.write('')
            self.stdout.write('')
            self.stdout.write('*'*80)
            self.stdout.write('subscribe')
            for cmd in subscribe_list:
                self.stdout.write(str(cmd))
            self.stdout.write('')
            self.stdout.write('')

        else:
            raise CommandError('Unknown action')
