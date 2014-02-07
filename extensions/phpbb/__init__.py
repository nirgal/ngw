#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Database settings is defined in ~/.pgpass

from __future__ import division, absolute_import, print_function, unicode_literals
import sys
import os
import subprocess
from time import time as timestamp

if __name__ != '__main__':
    print('PHPBB forum synchronisation extension for NGW loading.', file=sys.stderr)

if __name__ == '__main__':
    # TODO: This should be called from top level manage.py
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ngw.settings')
    sys.path.append('/usr/lib')
from django.db import connections
from ngw.extensions import hooks
from ngw.core.models import ( Config, Contact, ContactGroup, ContactFieldValue,
    GROUP_USER_PHPBB, FIELD_LOGIN, FIELD_PHPBB_USERID )
from ngw.core import contactfield # Need polymorphic upgrades

DEFAULT_USER_PERMISSIONS = '00000000006xv1ssxs'
    
__cursor__ = None
def get_common_cursor():
    global __cursor__
    if not __cursor__:
        __cursor__ = connections['phpbb3'].cursor()
    return __cursor__

def get_phpbb_acl_dictionary():
    """
    Return a list of tupple of matches between phpbb acl groups and ngw groups
    It's read from ngw config table, key 'phpbb acl dictionary':
    For example: '10,55;7,5;8,6;9,54;11,56'
    returns [ (10,55), (7,5), (8,6), (9,54), (11,56) ]
    this means phpbb usergroup 10 matches ngw group 55, phpbb group 7 matches ngw 5, and so on...
    """
    strdict = Config.objects.get(pk='phpbb acl dictionary').text
    if not strdict:
        return []
    return [ [ int(i) for i in pair.split(',')] for pair in strdict.split(';') ]


def get_config(key):
    c = get_common_cursor()
    sql = "SELECT config_value FROM phpbb_config WHERE config_name='%s'" % key
    c.execute(sql)
    row = c.fetchone()
    return row[0]

def set_config(key, value):
    c = get_common_cursor()
    sql = "UPDATE phpbb_config SET config_value='%s' WHERE config_name='%s'" % (value, key)
    #print(sql)
    c.execute(sql)

def print_and_call(*args):
    print("Appel de sous-processus:", args)
    args = [ arg.encode('utf8') for arg in args ]
    subprocess.call(args)


def sync_user_base(u):
    """ Check the PHPBB account has been created, and create it if necessary.
        Check the PHPBB login matches and modify it if necessary.
        Returns (int phpbb_user_id, bool phpbb_changed)
    """
    c = get_common_cursor()
    phpbb_changed = False

    f_login = u.get_fieldvalue_by_id(FIELD_LOGIN)
    assert f_login, "Login is empty for user " + u.name
    phpbb_user_id = u.get_fieldvalue_by_id(FIELD_PHPBB_USERID)
    print("Checking", f_login, " :", end=' ')
    if not phpbb_user_id:
        print("Creating PHPBB user", f_login)

        sql = "SELECT * from nextval('phpbb_users_seq')"
        c.execute(sql)
        phpbb_user_id, = c.fetchone()
        #print("new user id = ", phpbb_user_id)

        cfv = ContactFieldValue()
        cfv.contact_id = u.id
        cfv.contact_field_id = FIELD_PHPBB_USERID
        cfv.value = str(phpbb_user_id)
        cfv.save()

        sql = "INSERT INTO phpbb_users (user_id, group_id, user_permissions, user_regdate, username, username_clean, user_email, user_lang, user_timezone, user_dst, user_dateformat) VALUES(%(phpbb_user_id)d, 2, '%(user_permissions)s', %(regtime)d, '%(f_login)s', '%(f_login)s', 'noemail', '%(lang)s', %(timezone)s, %(dst)s, '%(dateformat)s')" % {'phpbb_user_id': phpbb_user_id, 'user_permissions': DEFAULT_USER_PERMISSIONS, 'f_login': f_login, 'regtime': int(timestamp()), 'lang': get_config('default_lang'), 'timezone': get_config('board_timezone'), 'dst': get_config('board_dst'), 'dateformat': get_config('default_dateformat')}
        #print(sql)
        c.execute(sql)
        phpbb_changed = True
        
        sql = "INSERT INTO phpbb_user_group (user_id, group_id, user_pending) VALUES(%(phpbb_user_id)d, 2, 0)" % {'phpbb_user_id': phpbb_user_id}
        #print(sql)
        c.execute(sql)
        phpbb_changed = True

        set_config('newest_user_id', str(phpbb_user_id))
        set_config('newest_username', str(f_login))
        set_config('num_users', str(int(get_config('num_users'))+1))
        
    print("user ids are PHPBB", phpbb_user_id, "and NGW", u.id)
    phpbb_user_id = int(phpbb_user_id)

    
    # fix logins
    sql = "SELECT username FROM phpbb_users WHERE user_id='%d'" % phpbb_user_id
    c.execute(sql)
    phpbb_username = c.fetchone()[0] # might crash if databases sync was lost
    if phpbb_username != f_login:
        print("Changing PHPBB user name from", phpbb_username, "to", f_login)
        sql = "UPDATE phpbb_users SET (username, username_clean) = ( '%(sql_login)s', '%(sql_login)s' ) WHERE user_id=%(user_id)d" % { 'user_id': phpbb_user_id, 'sql_login': f_login.replace("'", "''") }
        print(sql)
        c.execute(sql)
        phpbb_changed = True

    return phpbb_user_id, phpbb_changed


def sync_user_in_group(ngwuser, phpbb_user_id, php_group_id, ngw_group_id):
    c = get_common_cursor()
    phpbb_changed = False

    # Test whether phpbb allready is ok
    sql = "SELECT * FROM phpbb_user_group WHERE user_id=%s AND group_id=%d" % (phpbb_user_id, php_group_id)
    #print(sql)
    c.execute(sql)
    was_member = c.fetchone() is not None

    if ngwuser.is_member_of(ngw_group_id):
        if not was_member:
            print("user PHPBB", phpbb_user_id, "( NGW", ngwuser.id, ") was not found in group PHPBB", php_group_id, "( NGW", ngw_group_id, "). Adding.")
            sql = "INSERT INTO phpbb_user_group (user_id, group_id, user_pending) VALUES(%(phpbb_user_id)d, %(group_id)d, 0)" % {'phpbb_user_id': phpbb_user_id, 'group_id': php_group_id}
            print(sql)
            c.execute(sql)
            phpbb_changed = True
    else:
        if was_member:
            print("user PHPBB", phpbb_user_id, "( NGW", ngwuser.id, ") was found in group PHPBB", php_group_id, "( NGW", ngw_group_id, "). Removing.")
            sql = "DELETE FROM phpbb_user_group WHERE user_id=%(phpbb_user_id)d AND group_id=%(group_id)d" % {'phpbb_user_id': phpbb_user_id, 'group_id': php_group_id}
            print(sql)
            c.execute(sql)
            phpbb_changed = True
    return phpbb_changed

def sync_user_all(u):
    phpbb_user_id, phpbb_changed = sync_user_base(u)
    for (phpbb_group_id, ngw_group_id) in get_phpbb_acl_dictionary():
        phpbb_changed = sync_user_in_group(u, phpbb_user_id, phpbb_group_id, ngw_group_id) or phpbb_changed
    return phpbb_changed

##########
# Hooks

def phpbb_hook_membership_changed(user, contact, ngw_group):
    print("phpbb extension is receiving notification membership_changed:", contact, ngw_group)

    if not contact.is_member_of(GROUP_USER_PHPBB) and not contact.get_fieldvalue_by_id(FIELD_PHPBB_USERID):
        print("Contact is not member of GROUP_USER_PHPBB, and phpbb_user_id is undefined: nothing to do!")
        return # nothing to do
    
    if not contact.get_fieldvalue_by_id(FIELD_LOGIN):
        print("Error: Can't synchronise user with empty login") # FIXME
        user.push_message("ERROR: Can't synchronise PHPBB user " + contact.name + " with empty login.")
        return
        
    phpbb_user_id, phpbb_changed = sync_user_base(contact)
    ngw_group_id = ngw_group.id
    for phpbb_id, ngw_id in get_phpbb_acl_dictionary():
        if ngw_id != ngw_group_id:
            continue
        print("CALLING sync_user_in_group", contact, phpbb_user_id, phpbb_id, ngw_group_id)
        phpbb_changed = sync_user_in_group(contact, phpbb_user_id, phpbb_id, ngw_group_id) or phpbb_changed
     
    if phpbb_changed:
        print_and_call("sudo", "-u", "www-data", "/usr/lib/ngw/extensions/phpbb/clearcache.php")
        user.push_message("PHPBB database updated; Cache flushed.")
    # TODO commit ?


# Register all groups hooks
for (phpbb_group_id, ngw_group_id) in get_phpbb_acl_dictionary():
    hooks.add_hook_membership_changed(ngw_group_id, phpbb_hook_membership_changed)
hooks.add_hook_membership_changed(GROUP_USER_PHPBB, phpbb_hook_membership_changed)


@hooks.on_contact_field_changed(FIELD_LOGIN)
def login_updated(user, contact):
    login = contact.get_fieldvalue_by_id(FIELD_LOGIN)
    if not login:
        print("Error: Can't synchronise user with empty login") # FIXME
        user.push_message("ERROR: Can't synchronise PHPBB user with empty login.")
        return

    main_phpbb_changed = sync_user_all(contact)
    if main_phpbb_changed:
        print_and_call("sudo", "-u", "www-data", "/usr/lib/ngw/extensions/phpbb/clearcache.php")
        user.push_message("PHPBB database updated; Cache flushed.")

#######
## MAIN
#######

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] action\nActions:\n  full")
    # parser.add_option("-v", "--verbose", help="enable verbose", action="store_true", dest="verbose", default=False)
    parser.add_option("-u", "--user", action="append", type="int", help="Synchronisation only acts on specified NGW user id.")
    
    (options, args) = parser.parse_args()

    if len(args)!=1:
        print("Need exactly one argument\n", file=sys.stderr)
        parser.print_help(file=sys.stderr)
        sys.exit(1)
    
    if args[0] == "full":
        print("Sync'ing databases...")
        
        # We don't want to delete phpbb users. We can revoke acces, but we don't want to remove existing messages.
        
        main_phpbb_changed = False

        if not options.user:
            user_set = ContactGroup.objects.get(pk=GROUP_USER_PHPBB).get_all_members()
        else:
            user_set = []
            for ngw_user_id in options.user:
                u = Contact.objects.get(pk=ngw_user_id)
                if not u:
                    print("No user", ngw_user_id, file=sys.stderr)
                    sys.exit(1)
                # TODO: if not member of @users must have a phpbb_user_id ....
                user_set.append(u)

        for u in user_set:
            main_phpbb_changed = sync_user_all(u) or main_phpbb_changed
        
        if main_phpbb_changed:
            print_and_call("sudo", "-u", "www-data", "/usr/lib/ngw/extensions/phpbb/clearcache.php")

if __name__ != '__main__':
    print('PHPBB forum synchronisation extension for NGW loaded.', file=sys.stderr)

