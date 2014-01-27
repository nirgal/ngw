# -*- encoding: utf8 -*-

"""
Permission read functions.
This is a simple proxy to the permission system implemented in SQL.
See sql/functions.sql

c_can_see_CG              C can view existence of CG
c_can_change_CG           C can change/delete CG itself
c_can_see_members_CG      C can view members of CG
c_can_change_members_CG   C can change/delete membership in CG (+note)
c_can_view_fields_CG      C can view C-fields of CG (existence, content for members it can see)
c_can_write_fields_CG     C can write C-fields of CG
c_can_see_news_CG N       C can view news of CG
c_can_change_news_CG      C can change/delete news of CG
c_can_see_files_CG        C can view files of CG
c_can_change_files_CG     C can change/delete files of CG
"""

from __future__ import print_function, unicode_literals
from django.db import connection


def c_has_cg_permany(cid, gid, flags):
    '''
    Returns True if contact cid has any permission flags on contact_group gid,
    either through contact_in_group table or because he's a member of a group
    that has admin priviledges though group_manage_group.
    Test is run on any flag: 128|8192 will return users that can view members
    or files.
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT c_has_cg_permany(%s, %s, %s)", [cid, gid, flags])
    row = cursor.fetchone()
    if row:
        return row[0]
    return False

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
