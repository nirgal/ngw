import logging
import subprocess
from optparse import make_option

from django.conf import settings
from django.core.management.base import CommandError, NoArgsCommand

from ngw.core.models import FIELD_LOGIN, ContactFieldValue, ContactGroup


def check_login_exists(login):
    try:
        ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN,
                                      value=login)
    except ContactFieldValue.DoesNotExist:
        raise CommandError('User "{}" does not exist'.format(login))


def call(*args):
    'Call subprocess with arguments, log'
    logging.debug("Subprocess call: %s", args)
    return subprocess.check_output(args)


def get_roster(login):
    raw = call('sudo', '/usr/sbin/ejabberdctl',
               'get_roster', login, settings.XMPP_DOMAIN)
    raw = str(raw, encoding='utf-8')
    return [line.split('\t')
            for line in raw.split('\n')]


def cross_subscribe(login1, login2):
    '''
    login1 & 2 must exists.
    Check before calling.
    '''
    def _subscribe1(login1, login2):
        call('sudo', '/usr/sbin/ejabberdctl',
             'add_rosteritem',
             login1, settings.XMPP_DOMAIN,
             login2, settings.XMPP_DOMAIN,
             login2+'@'+settings.XMPP_DOMAIN,
             settings.XMPP_ROSTERNAME,
             'both')

    _subscribe1(login1, login2)
    _subscribe1(login2, login1)


def subscribe_everyone(login, allusers, exclude=None):
    logging.info('subscribe_everyone for %s. Exclude=%s', login, exclude)
    exclude = exclude or []

    check_login_exists(login)

    for user in allusers:
        username = user.get_fieldvalue_by_id(FIELD_LOGIN)
        if username == login or username in exclude:
            continue  # skip
        logging.debug('Cross subscribe %s:%s', login, username)
        cross_subscribe(login, username)


class Command(NoArgsCommand):
    help = 'ngw/ejabberd synchronisation tools'
    option_list = NoArgsCommand.option_list + (
        make_option(
            '-x', '--exclude',
            action='append', dest='exclude', default=[],
            metavar='USERNAME',
            help="exclude username from suball"),
        make_option(
            '--subs',
            action='append', dest='add_subs', default=[],
            metavar='USERNAME1:USERNAME2',
            help="user1:user2 cross subscribe user1 and user2"),
        make_option(
            '--suball',
            action='store', dest='suball',
            metavar='USERNAME',
            help="Subscribe a user to everyone"),
        )

    def handle_noargs(self, **options):
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

        user_set = (ContactGroup.objects.get(pk=settings.XMPP_GROUP)
                                        .get_all_members())

        for logins in options['add_subs']:
            login1, login2 = logins.split(':')
            check_login_exists(login1)
            check_login_exists(login2)
            cross_subscribe(login1, login2)

        if options['suball']:
            subscribe_everyone(login=options['suball'],
                               allusers=user_set,
                               exclude=options['exclude'])
