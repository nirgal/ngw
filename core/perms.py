# -*- encoding: utf8 -*-

"""
Permission read functions.
This is a simple proxy to the permission system implemented in SQL.
See sql/functions.sql
"""

from __future__ import print_function, unicode_literals
from django.db import connection


def c_can_see_cg(cid, gid):
    '''
    Returns True if contact cid can see existence of contact_group gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_see_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_change_cg(cid, gid):
    '''
    Returns True if contact cid can change/delete contact_group gid itself.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_change_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_see_members_cg(cid, gid):
    '''
    Returns True if contact cid can view members of contact_group gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_see_members_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_change_members_cg(cid, gid):
    '''
    Returns True if contact cid can change/delete memberships in contact_group
    gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_change_members_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_view_fields_cg(cid, gid):
    '''
    Returns True if contact cid can view contact_fields of contact_group gid.
    This is both for existence and content (for member it can see only).
    Here gid is the group that owns the fields, and grants its usage to other
    groups.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_view_fields_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_write_fields_cg(cid, gid):
    '''
    Returns True if contact cid can write contact_fields of contact_group gid.
    Here gid is the group that owns the fields, and grants its usage to other
    groups.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_write_fields_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_change_fields_cg(cid, gid):
    '''
    Returns True if contact cid can add / change type / delete contact_fields
    of contact_group gid.
    Here gid is the group that owns the fields, and grants its usage to other
    groups.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_change_fields_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_see_news_cg(cid, gid):
    '''
    Returns True if contact cid can see news of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_see_news_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_change_news_cg(cid, gid):
    '''
    Returns True if contact cid can add/change/delete news of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_change_news_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_see_files_cg(cid, gid):
    '''
    Returns True if contact cid can see files of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_see_files_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_change_filess_cg(cid, gid):
    '''
    Returns True if contact cid can add/change/delete files of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_change_files_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False
