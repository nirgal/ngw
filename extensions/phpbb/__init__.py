from __future__ import print_function

import subprocess
import sys
from time import time as timestamp

from django.contrib import messages
from django.db import connection, connections

from ngw.core import contactfield  # Need polymorphic upgrades  # noqa
from ngw.core.models import (FIELD_LOGIN, FIELD_PHPBB_USERID, GROUP_USER_PHPBB,
                             ContactFieldValue)
from ngw.extensions import hooks

DEFAULT_USER_PERMISSIONS = '00000000006xv1ssxs'


def get_cursor():
    return connections['phpbb3'].cursor()


def get_phpbb_acl_dictionary():
    """
    Return a list of tupple of matches between phpbb acl groups and ngw groups
    It's read from ngw config table, key 'phpbb acl dictionary':
    For example: '10,55;7,5;8,6;9,54;11,56'
    returns [ (10,55), (7,5), (8,6), (9,54), (11,56) ]
    this means phpbb usergroup 10 matches ngw group 55, phpbb group 7 matches
    ngw 5, and so on...
    """
    cursor = connection.cursor()
    cursor.execute("SELECT text FROM config WHERE id='phpbb acl dictionary'")
    row = cursor.fetchone()
    if not row or not row[0]:
        return []
    strdict = row[0]
    return [[int(i) for i in pair.split(',')] for pair in strdict.split(';')]


def get_config(key):
    cursor = get_cursor()
    sql = "SELECT config_value FROM phpbb_config WHERE config_name='%s'" % key
    cursor.execute(sql)
    row = cursor.fetchone()
    return row[0]


def set_config(key, value):
    cursor = get_cursor()
    sql = ("UPDATE phpbb_config SET config_value='%s' WHERE config_name='%s'"
           % (value, key))
    # print(sql, file=sys.stderr)
    cursor.execute(sql)


def print_and_call(*args):
    print("Subprocess call:", args, file=sys.stderr)
    args = [arg.encode('utf8') for arg in args]
    subprocess.call(args)


def sync_user_base(u):
    """ Check the PHPBB account has been created, and create it if necessary.
        Check the PHPBB login matches and modify it if necessary.
        Returns (int phpbb_user_id, bool phpbb_changed)
    """
    cursor = get_cursor()
    phpbb_changed = False

    f_login = u.get_fieldvalue_by_id(FIELD_LOGIN)
    assert f_login, "Login is empty for user " + u.name
    phpbb_user_id = u.get_fieldvalue_by_id(FIELD_PHPBB_USERID)
    print("Checking", f_login, " :", end=' ', file=sys.stderr)
    if not phpbb_user_id:
        print("Creating PHPBB user", f_login, file=sys.stderr)

        sql = "SELECT * from nextval('phpbb_users_seq')"
        cursor.execute(sql)
        phpbb_user_id, = cursor.fetchone()
        # print("new user id = ", phpbb_user_id, file=sys.stderr)

        cfv = ContactFieldValue()
        cfv.contact_id = u.id
        cfv.contact_field_id = FIELD_PHPBB_USERID
        cfv.value = str(phpbb_user_id)
        cfv.save()

        sql = """
            INSERT INTO phpbb_users (user_id, group_id, user_permissions,
                user_regdate, username, username_clean, user_email, user_lang,
                user_timezone, user_dst, user_dateformat)
            VALUES(%(phpbb_user_id)d, 2, '%(user_permissions)s', %(regtime)d,
                '%(f_login)s', '%(f_login)s', 'noemail', '%(lang)s',
                %(timezone)s, %(dst)s, '%(dateformat)s')""" % {
            'phpbb_user_id': phpbb_user_id,
            'user_permissions': DEFAULT_USER_PERMISSIONS,
            'f_login': f_login,
            'regtime': int(timestamp()),
            'lang': get_config('default_lang'),
            'timezone': get_config('board_timezone'),
            'dst': get_config('board_dst'),
            'dateformat': get_config('default_dateformat')}
        # print(sql, file=sys.stderr)
        cursor.execute(sql)
        phpbb_changed = True

        sql = """
            INSERT INTO phpbb_user_group (user_id, group_id, user_pending)
            VALUES(%(phpbb_user_id)d, 2, 0)""" % {
            'phpbb_user_id': phpbb_user_id}
        # print(sql, file=sys.stderr)
        cursor.execute(sql)
        phpbb_changed = True

        set_config('newest_user_id', str(phpbb_user_id))
        set_config('newest_username', str(f_login))
        set_config('num_users', str(int(get_config('num_users'))+1))

    print("user ids are PHPBB", phpbb_user_id, "and NGW", u.id,
          file=sys.stderr)
    phpbb_user_id = int(phpbb_user_id)

    # fix logins
    sql = "SELECT username FROM phpbb_users WHERE user_id='%d'" % phpbb_user_id
    cursor.execute(sql)
    # TODO: might crash if databases sync was lost
    phpbb_username = cursor.fetchone()[0]
    if phpbb_username != f_login:
        print("Changing PHPBB user name from", phpbb_username, "to", f_login,
              file=sys.stderr)
        sql = """
            UPDATE phpbb_users
            SET (username, username_clean) = ('%(sql_login)s', '%(sql_login)s')
            WHERE user_id=%(user_id)d""" % {
            'user_id': phpbb_user_id,
            'sql_login': f_login.replace("'", "''")}
        print(sql, file=sys.stderr)
        cursor.execute(sql)
        phpbb_changed = True

    return phpbb_user_id, phpbb_changed


def sync_user_in_group(ngwuser, phpbb_user_id, php_group_id, ngw_group_id):
    cursor = get_cursor()
    phpbb_changed = False

    # Test whether phpbb allready is ok
    sql = """
        SELECT * FROM phpbb_user_group WHERE user_id=%s AND group_id=%d
        """ % (phpbb_user_id, php_group_id)
    # print(sql, file=sys.stderr)
    cursor.execute(sql)
    was_member = cursor.fetchone() is not None

    if ngwuser.is_member_of(ngw_group_id):
        if not was_member:
            print("user PHPBB", phpbb_user_id, "( NGW", ngwuser.id,
                  ") was not found in group PHPBB", php_group_id, "( NGW",
                  ngw_group_id, "). Adding.",
                  file=sys.stderr)
            sql = """
                INSERT INTO phpbb_user_group (user_id, group_id, user_pending)
                VALUES(%(phpbb_user_id)d, %(group_id)d, 0)""" % {
                'phpbb_user_id': phpbb_user_id,
                'group_id': php_group_id}
            print(sql, file=sys.stderr)
            cursor.execute(sql)
            phpbb_changed = True
    else:
        if was_member:
            print("user PHPBB", phpbb_user_id, "( NGW", ngwuser.id,
                  ") was found in group PHPBB", php_group_id, "( NGW",
                  ngw_group_id, "). Removing.",
                  file=sys.stderr)
            sql = """
                DELETE FROM phpbb_user_group
                WHERE user_id=%(phpbb_user_id)d
                AND group_id=%(group_id)d""" % {
                'phpbb_user_id': phpbb_user_id,
                'group_id': php_group_id}
            print(sql, file=sys.stderr)
            cursor.execute(sql)
            phpbb_changed = True
    return phpbb_changed


def sync_user_all(u):
    phpbb_user_id, phpbb_changed = sync_user_base(u)
    for (phpbb_group_id, ngw_group_id) in get_phpbb_acl_dictionary():
        phpbb_changed = sync_user_in_group(u, phpbb_user_id, phpbb_group_id,
                                           ngw_group_id) or phpbb_changed
    return phpbb_changed


##########
# Hooks

def phpbb_hook_membership_changed(request, contact, ngw_group):
    print("phpbb extension is receiving notification membership_changed:",
          contact, ngw_group, file=sys.stderr)

    if (not contact.is_member_of(GROUP_USER_PHPBB)
       and not contact.get_fieldvalue_by_id(FIELD_PHPBB_USERID)):
        print("Contact is not member of GROUP_USER_PHPBB, and phpbb_user_id is"
              " undefined: nothing to do!",
              file=sys.stderr)
        return  # nothing to do

    if not contact.get_fieldvalue_by_id(FIELD_LOGIN):
        print("Error: Can't synchronise user with empty login",
              file=sys.stderr)  # FIXME
        messages.add_message(
            request, messages.ERROR,
            "Can't synchronise PHPBB user %s with empty login."
            % contact.name)
        return

    phpbb_user_id, phpbb_changed = sync_user_base(contact)
    ngw_group_id = ngw_group.id
    for phpbb_id, ngw_id in get_phpbb_acl_dictionary():
        if ngw_id != ngw_group_id:
            continue
        print("CALLING sync_user_in_group",
              contact, phpbb_user_id, phpbb_id, ngw_group_id, file=sys.stderr)
        phpbb_changed = (
            sync_user_in_group(contact, phpbb_user_id, phpbb_id, ngw_group_id)
            or phpbb_changed)

    if phpbb_changed:
        print_and_call("sudo", "-u", "www-data",
                       "/usr/lib/ngw/extensions/phpbb/clearcache.php")
        messages.add_message(request, messages.INFO,
                             "PHPBB database updated; Cache flushed.")
    # TODO commit ?


# Register all groups hooks
for (phpbb_group_id, ngw_group_id) in get_phpbb_acl_dictionary():
    hooks.add_hook_membership_changed(ngw_group_id,
                                      phpbb_hook_membership_changed)
hooks.add_hook_membership_changed(GROUP_USER_PHPBB,
                                  phpbb_hook_membership_changed)


@hooks.on_contact_field_changed(FIELD_LOGIN)
def login_updated(request, contact):
    login = contact.get_fieldvalue_by_id(FIELD_LOGIN)
    if not login:
        # FIXME
        print("Error: Can't synchronise user with empty login",
              file=sys.stderr)
        messages.add_message(
            request, messages.ERROR,
            "Can't synchronise PHPBB user %s with empty login." % contact.name
            )
        return

    main_phpbb_changed = sync_user_all(contact)
    if main_phpbb_changed:
        print_and_call(
            "sudo", "-u", "www-data",
            "/usr/lib/ngw/extensions/phpbb/clearcache.php")
        messages.add_message(
            request, messages.INFO, "PHPBB database updated; Cache flushed.")
