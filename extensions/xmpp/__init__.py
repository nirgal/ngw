#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Database settings is defined in ~/.pgpass

if __name__ != "__main__":
    print "XMPP synchronisation extension for NGW loading."

import sys
import os
import psycopg2
import psycopg2.extensions
import logging
if __name__ == "__main__":
    sys.path += [ '/usr/lib/' ]
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ngw.settings'
from ngw.core.models import ( ContactFieldValue, ContactGroup,
    FIELD_LOGIN, FIELD_PASSWORD_PLAIN )
from ngw.extensions import hooks

DATABASE_NAME = u'ejabberd'
    
__db = None
def get_common_db():
    global __db
    if not __db:
        psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
        for line in file(os.path.sep.join([os.getenv('HOME', '/var/www'), '.pgpass'])):
            line = line[:-1] # remove \n
            host, port, user, database, password = line.split(':')
            if database == DATABASE_NAME:
                __db = psycopg2.connect(database=database, user=user, password=password, host=host, port=port)
                __db.set_client_encoding('UTF8')
                break
    return __db

__cursor = None
def get_common_cursor():
    global __cursor
    if not __cursor:
        __cursor = get_common_db().cursor()
    return __cursor

def sync_user(u):
    f_login = u.get_fieldvalue_by_id(FIELD_LOGIN)
    logging.debug("Sync'ing %s", f_login)
    f_login = f_login.lower()
    f_password = ContactFieldValue.objects.get(contact_id=u.id, contact_field_id=FIELD_PASSWORD_PLAIN).value
    sql = u'INSERT INTO users (username, password) SELECT %s, %s WHERE NOT EXISTS (SELECT * FROM users WHERE username=%s)' 
    get_common_cursor().execute(sql, (f_login, f_password, f_login))

    sql = u'UPDATE users SET password=%s WHERE username=%s'
    get_common_cursor().execute(sql, (f_password, f_login))
    return f_login

def remove_unknown(login_set):
    #TODO
    pass

def cross_subscribe(login1, login2):
    '''
    login1 & 2 must exists.
    Check before calling.
    '''
    login1 = login1.lower()
    login2 = login2.lower()

    def _subscribe1(login1, login2):
        params = { 'username': login1, 'jid': login2+'@hp.greenpeace.fr', 'nick': login2 }
        sql = u"INSERT INTO rosterusers (username, jid, nick, subscription, ask, askmessage, server) SELECT %(username)s, %(jid)s, %(nick)s, 'B', 'N', '', 'N' WHERE NOT EXISTS (SELECT * FROM rosterusers WHERE username=%(username)s AND jid=%(jid)s)"
        get_common_cursor().execute(sql, params)
        sql = u"UPDATE rosterusers SET subscription='B', ask='N', server='N', type='item' WHERE username=%(username)s AND jid=%(jid)s"
        get_common_cursor().execute(sql, params)
    _subscribe1(login1, login2)
    _subscribe1(login2, login1)


def clean_rostergroup(login):
    params = { 'username': login }
    sql = 'SELECT min(grp) FROM rostergroups WHERE username=%(username)s'
    get_common_cursor().execute(sql, params)
    row = get_common_cursor().fetchone()
    if row and row[0]:
        grp = row[0]
    else:
        grp = 'GP'
    logging.debug('group for %s is %s.', login, grp)

    params['grp'] = grp
    sql = 'INSERT INTO "rostergroups" (username, jid, grp) SELECT username, jid, %(grp)s FROM rosterusers WHERE username=%(username)s AND NOT EXISTS (SELECT * FROM rostergroups WHERE rostergroups.username=rosterusers.username AND rostergroups.jid=rosterusers.jid)'
    get_common_cursor().execute(sql, params)
    

def subscribe_everyone(baseusername, allusers, exclude=None):
    logging.debug('subscribe_everyone for %s. Exclude=%s', baseusername, exclude)
    exclude = exclude or []
    # Check baseusername exists:
    baseuser = ContactFieldValue.objects.filter(contact_field_id=FIELD_LOGIN).filter(value=baseusername)
    baseusername = baseusername.lower()
    for user in allusers:
        username = user.get_fieldvalue_by_id(FIELD_LOGIN)
        username = username.lower()
        if username == baseusername or username in exclude:
            continue # skip
        logging.debug('Cross subscribe %s:%s', baseusername, username)
        cross_subscribe(baseusername, username)
        


#######
## MAIN
#######

GROUP_USER_XMPP = 284

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-x', '--exclude',
        action='append', dest='exclude', default=[],
        metavar='USERNAME',
        help="exclude username from suball")
    parser.add_option('--subs',
        action='append', dest='add_subs', default=[],
        metavar='USERNAME1:USERNAME2',
        help="user1:user2 cross subscribe user1 and user2")
    parser.add_option('--suball',
        action='store', dest='suball',
        metavar='USERNAME',
        help="Subscribe a user to everyone")
    parser.add_option('-d', '--debug',
        action='store_true', dest='debug', default=False,
        help="debug mode")
    options, args = parser.parse_args()

    if options.debug:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO
    logging.basicConfig(level=loglevel, format='%(asctime)s %(levelname)s %(message)s')

    #if options.debug_sql:
    #    sql_setdebug(True)

    if len(args):
        print >> sys.stderr, "That script takes not argument\n"
        parser.print_help(file=sys.stderr)
        sys.exit(1)
    
    logging.info("Sync'ing databases...")
   
    user_set = ContactGroup.objects.get(pk=GROUP_USER_XMPP).get_all_members()
    login_set = set()
    for u in user_set:
        login = sync_user(u)
        login_set.add(login)
        get_common_db().commit()
    remove_unknown(login_set)

    for l1l2 in options.add_subs:
        l1, l2 = l1l2.split(u':')
        # Check the logins do exists in the database
        login1 = ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN, value=l1)
        login2 = ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN, value=l2)
        cross_subscribe(l1, l2)
    get_common_db().commit()

    if options.suball:
        subscribe_everyone(baseusername=options.suball, allusers = user_set, exclude = options.exclude)
        get_common_db().commit()

    # clean up roster group
    for u in user_set:
        clean_rostergroup(u.get_fieldvalue_by_id(FIELD_LOGIN).lower())
    get_common_db().commit()

if __name__ != "__main__":
    print "XMPP synchronisation extension for NGW loaded."

