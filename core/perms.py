# -*- encoding: utf-8 -*-

"""
Permission read functions.
This is a simple proxy to the permission system implemented in SQL.
See sql/functions.sql

c_can_see_cg              C can view existence of CG
c_can_change_cg           C can change/delete CG itself
c_can_see_members_cg      C can view members of CG
c_can_change_members_cg   C can change/delete membership in CG (+note)
c_can_view_fields_cg      C can view C-fields of CG (existence, content for members it can see)
c_can_write_fields_cg     C can write C-fields of CG
c_can_see_news_cg         C can view news of CG
c_can_change_news_cg      C can change/delete news of CG
c_can_see_files_cg        C can view files of CG
c_can_change_files_cg     C can change/delete files of CG
"""

from __future__ import division, absolute_import, print_function, unicode_literals
from django.db import connection


def c_flags_cg_int(cid, gid):
    '''
    Return the integer value of flags (midoveE...)
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT cig_flags(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    return row[0]


def c_operatorof_cg(cid, gid):
    '''
    Returns True if contact cid is an operator of contact_group gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_operatorof_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False

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


def c_can_change_files_cg(cid, gid):
    '''
    Returns True if contact cid can add/change/delete files of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_change_files_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_view_msgs_cg(cid, gid):
    '''
    Returns True if contact cid can see files of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_view_msgs_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False


def c_can_write_msgs_cg(cid, gid):
    '''
    Returns True if contact cid can add/change/delete files of contactgroup gid.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT perm_c_can_write_msgs_cg(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False
