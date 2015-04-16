import logging
from optparse import make_option

from django.conf import settings
from django.core.management.base import NoArgsCommand
from django.db import connections

from ngw.core.models import FIELD_LOGIN, ContactFieldValue, ContactGroup

logger = logging.getLogger('ejabberd_cmd')


def get_cursor():
    return connections['jabber'].cursor()


def cross_subscribe(login1, login2):
    '''
    login1 & 2 must exists.
    Check before calling.
    '''
    cursor = get_cursor()
    login1 = login1.lower()
    login2 = login2.lower()

    def _subscribe1(login1, login2):
        params = {
            'username': login1,
            'jid': login2+'@'+settings.XMPP_DOMAIN,
            'nick': login2}

        sql = """
            INSERT INTO rosterusers
                (username, jid, nick, subscription, ask, askmessage, server)
            SELECT %(username)s, %(jid)s, %(nick)s, 'B', 'N', '', 'N'
            WHERE NOT EXISTS (
                SELECT *
                FROM rosterusers
                WHERE username=%(username)s
                AND jid=%(jid)s
            )"""
        cursor.execute(sql, params)

        sql = """
            UPDATE rosterusers
            SET subscription='B', ask='N', server='N', type='item'
            WHERE username=%(username)s AND jid=%(jid)s
        """
        cursor.execute(sql, params)
    _subscribe1(login1, login2)
    _subscribe1(login2, login1)


def clean_rostergroup(login):
    cursor = get_cursor()
    params = {'username': login}
    sql = 'SELECT min(grp) FROM rostergroups WHERE username=%(username)s'
    cursor.execute(sql, params)
    row = cursor.fetchone()
    if row and row[0]:
        grp = row[0]
    else:
        grp = 'GP'
    logging.debug('group for %s is %s.', login, grp)

    params['grp'] = grp
    sql = '''
        INSERT INTO "rostergroups" (username, jid, grp)
        SELECT username, jid, %(grp)s
        FROM rosterusers
        WHERE username=%(username)s
        AND NOT EXISTS (
            SELECT *
            FROM rostergroups
            WHERE rostergroups.username=rosterusers.username
            AND rostergroups.jid=rosterusers.jid)'''
    cursor.execute(sql, params)


def subscribe_everyone(baseusername, allusers, exclude=None):
    logging.debug('subscribe_everyone for %s. Exclude=%s',
                  baseusername, exclude)
    exclude = exclude or []
    # Check baseusername exists:
    baseuser = (ContactFieldValue
                .objects
                .filter(contact_field_id=FIELD_LOGIN)
                .filter(value=baseusername))
    assert len(baseuser), ("User %s not found" % baseusername)

    baseusername = baseusername.lower()
    for user in allusers:
        username = user.get_fieldvalue_by_id(FIELD_LOGIN)
        username = username.lower()
        if username == baseusername or username in exclude:
            continue  # skip
        logging.debug('Cross subscribe %s:%s', baseusername, username)
        cross_subscribe(baseusername, username)


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
        make_option(
            '-d', '--debug',
            action='store_true', dest='debug', default=False,
            help="debug mode"),
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
                            format='%(asctime)s %(levelname)s %(message)s')

        # if options.debug_sql:
        #    sql_setdebug(True)

        logging.info("Sync'ing databases...")
        user_set = (ContactGroup.objects.get(pk=settings.XMPP_GROUP)
                                        .get_all_members())

        for l1l2 in options.add_subs:
            l1, l2 = l1l2.split(':')
            # Check the logins do exists in the database
            login1 = ContactFieldValue.objects.get(
                contact_field_id=FIELD_LOGIN, value=l1)
            login2 = ContactFieldValue.objects.get(
                contact_field_id=FIELD_LOGIN, value=l2)
            cross_subscribe(login1, login2)

        if options.suball:
            subscribe_everyone(baseusername=options.suball,
                               allusers=user_set,
                               exclude=options.exclude)

        # clean up roster group
        for u in user_set:
            clean_rostergroup(u.get_fieldvalue_by_id(FIELD_LOGIN).lower())
