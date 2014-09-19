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
from collections import OrderedDict
from django.db import connection
from django.utils import six
from django.utils.translation import ugettext_lazy as _

MEMBER         =     1 # 'm'ember
INVITED        =     2 # 'i'nvited
DECLINED       =     4 # 'd'eclined invitation
OPERATOR       =     8 # 'o'pertor
VIEWER         =    16 # 'v'iewer
SEE_CG         =    32 # 'e'xistance
CHANGE_CG      =    64 # 'E'
SEE_MEMBERS    =   128 # 'c'ontent
CHANGE_MEMBERS =   256 # 'C'
VIEW_FIELDS    =   512 # 'f'ields
WRITE_FIELDS   =  1024 # 'F'
VIEW_NEWS      =  2048 # 'n'ews
WRITE_NEWS     =  4096 # 'N'
VIEW_FILES     =  8192 # 'u'ploaded
WRITE_FILES    = 16384 # 'U'
VIEW_MSGS      = 32768 # 'x'ternal messages
WRITE_MSGS     = 65536 # 'X'

# That information contains:
# int value (see above)
# character letter value, kinda human friendly
# human friendly text, sometimes used in forms field names
# dependency: 'u':'e' means viewing files implies viewing group existence
# conflicts: 'F':'f' means can't write to fields unless can read them too
__cig_flag_info__ = (
    (MEMBER, 'm', '', 'id', _('Member')),
    (INVITED, 'i', '', 'md', _('Invited')),
    (DECLINED, 'd', '', 'mi', _('Declined')),
    (OPERATOR, 'o', 'veEcCfFnNuUxX', '', _('Operator')),
    (VIEWER, 'v', 'ecfnux', '', _('Viewer')),
    (SEE_CG, 'e', '', '', _('Can see group exists')),
    (CHANGE_CG, 'E', 'e', '', _('Can change group')),
    (SEE_MEMBERS, 'c', 'e', '', _('Can see members')),
    (CHANGE_MEMBERS, 'C', 'ec', '', _('Can change members')),
    (VIEW_FIELDS, 'f', 'e', '', _('Can view fields')),
    (WRITE_FIELDS, 'F', 'ef', '', _('Can write fields')),
    (VIEW_NEWS, 'n', 'e', '', _('Can view news')),
    (WRITE_NEWS, 'N', 'en', '', _('Can write news')),
    (VIEW_FILES, 'u', 'e', '', _('Can view uploaded files')),
    (WRITE_FILES, 'U', 'eu', '', _('Can upload files')),
    (VIEW_MSGS, 'x', 'e', '', _('Can view messages')),
    (WRITE_MSGS, 'X', 'ex', '', _('Can write messages')),
)

ADMIN_ALL = (
    OPERATOR | VIEWER
    | SEE_CG | CHANGE_CG
    | SEE_MEMBERS | CHANGE_MEMBERS
    | VIEW_FIELDS | WRITE_FIELDS
    | VIEW_NEWS | WRITE_NEWS
    | VIEW_FILES | WRITE_FILES
    | VIEW_MSGS | WRITE_MSGS)

FLAGTOINT = OrderedDict()  # dict for quick translation 1 letter -> int
FLAGTOTEXT = OrderedDict()  # dict for quick translation 1 letter -> txt
FLAGDEPENDS = {}  # flag dependencies
FLAGCONFLICTS = {}

def __initialise_cigflags_constants():
    if FLAGTOINT:
        print('Warning flags were already initialized')
        return # already initialized
    for intval, code, requires, conflicts, text in __cig_flag_info__:
        FLAGTOINT[code] = intval
        FLAGTOTEXT[code] = text
        FLAGDEPENDS[code] = requires
        FLAGCONFLICTS[code] = conflicts

    for intval, code, txt, requires, conflicts in __cig_flag_info__:
        print ('+%s => +%s-%s' % (
            code, FLAGDEPENDS[code], FLAGCONFLICTS[code]))

# This is run on module loading:
__initialise_cigflags_constants()


def int_to_flags(intflags):
    '''
    Converts a membership / permission interger such as MEMBER|SEE_CG|CHANGE_CG
    into a flag strig such as 'meE'
    '''
    result = ''
    for flag, intflag in six.iteritems(FLAGTOINT):
        if intflags & intflag:
            result += flag
    return result


def cig_flags_int(cid, gid):
    '''
    Return the integer value of flags (midoveE...)
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT cig_flags(%s, %s)", [cid, gid])
    row = cursor.fetchone()
    return row[0]


def cig_flags_direct_int(cid, gid):
    '''
    Return the integer value of flags (midoveE...) without inheritance.
    Returns 0 if contact_in_group doesn't exists
    '''
    cursor = connection.cursor()
    cursor.execute("SELECT cig_flags_direct(%s, %s)", [cid, gid])
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
