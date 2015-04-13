"""
Permission read functions.
This is a simple proxy to the permission system implemented in SQL.
See sql/functions.sql

c_can_see_cg              C can view existence of CG
c_can_change_cg           C can change/delete CG itself,
                          including add/edit/delete fields
c_can_see_members_cg      C can view members of CG
c_can_change_members_cg   C can change/delete membership in CG (+note)
c_can_view_fields_cg      C can view C-fields of CG
                          (existence, content for members it can see)
c_can_write_fields_cg     C can write C-fields of CG
c_can_see_news_cg         C can view news of CG
c_can_change_news_cg      C can change/delete news of CG
c_can_see_files_cg        C can view files of CG
c_can_change_files_cg     C can change/delete files of CG
"""

from collections import OrderedDict

from django.db import connection
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

MEMBER = 1            # 'm'ember
INVITED = 2           # 'i'nvited
DECLINED = 4          # 'd'eclined invitation
OPERATOR = 8          # 'o'pertor
VIEWER = 16           # 'v'iewer
SEE_CG = 32           # 'e'xistance
CHANGE_CG = 64        # 'E'
SEE_MEMBERS = 128     # 'c'ontent
CHANGE_MEMBERS = 256  # 'C'
VIEW_FIELDS = 512     # 'f'ields
WRITE_FIELDS = 1024   # 'F'
VIEW_NEWS = 2048      # 'n'ews
WRITE_NEWS = 4096     # 'N'
VIEW_FILES = 8192     # 'u'ploaded
WRITE_FILES = 16384   # 'U'
VIEW_MSGS = 32768     # 'x'ternal messages
WRITE_MSGS = 65536    # 'X'


FLAGTOINT = OrderedDict()  # dict for translation 1 letter -> int
FLAGTOTEXT = OrderedDict()  # dict for translation 1 letter -> txt
INTTOTEXT = OrderedDict()  # dict for translation int -> text
FLAGDEPENDS = OrderedDict()  # flag dependencies
FLAGCONFLICTS = OrderedDict()
FLAGGROUPLABEL = OrderedDict()  # dict for translation 1 letter -> group label
FLAGGROUPHELP = OrderedDict()  # dict for translation 1 letter -> group label


def _register_flag(intval, code, requires, conflicts, text, group_label,
                   group_help):
    FLAGTOINT[code] = intval
    FLAGTOTEXT[code] = text
    INTTOTEXT[intval] = text
    FLAGGROUPLABEL[code] = group_label
    FLAGGROUPHELP[code] = group_help
    FLAGDEPENDS[code] = requires
    FLAGCONFLICTS[code] = conflicts

# That information contains:
# int value (see above)
# character letter value, kinda human friendly
# human friendly text, sometimes used in forms field names
# dependency: 'u':'e' means viewing files implies viewing group existence
# conflicts: 'F':'f' means can't write to fields unless can read them too
_register_flag(MEMBER, 'm', '', 'id', ugettext_lazy('Member'), None, None)
_register_flag(INVITED, 'i', '', 'md', ugettext_lazy('Invited'), None, None)
_register_flag(DECLINED, 'd', '', 'mi', ugettext_lazy('Declined'), None, None)
_register_flag(
    OPERATOR, 'o', 'veEcCfFnNuUxX', '', ugettext_lazy('Operator'),
    ugettext_lazy('Operator groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' administrative priviledges.'))
_register_flag(
    VIEWER, 'v', 'ecfnux', '', ugettext_lazy('Viewer'),
    ugettext_lazy('Viewer groups'),
    ugettext_lazy("Members of these groups will automatically be granted"
                  " viewer priviledges: They can see everything but can't"
                  " change things."))
_register_flag(
    SEE_CG, 'e', '', '', ugettext_lazy('Can see group exists'),
    ugettext_lazy('Existence seer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' priviledge to know that current group exists.'))
_register_flag(
    CHANGE_CG, 'E', 'e', '', ugettext_lazy('Can change group'),
    ugettext_lazy('Editor groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' priviledge to change/delete the current group.'))
_register_flag(
    SEE_MEMBERS, 'c', 'e', '', ugettext_lazy('Can see members'),
    ugettext_lazy('Members seer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' priviledge to see the list of members.'))
_register_flag(
    CHANGE_MEMBERS, 'C', 'ec', '', ugettext_lazy('Can change members'),
    ugettext_lazy('Members changing groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to change members of current group.'))
_register_flag(
    VIEW_FIELDS, 'f', 'e', '', ugettext_lazy('Can view fields'),
    ugettext_lazy('Fields viewer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to read the fields associated to current'
                  ' group.'))
_register_flag(
    WRITE_FIELDS, 'F', 'ef', '', ugettext_lazy('Can write fields'),
    ugettext_lazy('Fields writer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' priviledge to write to fields associated to current'
                  ' group.'))
_register_flag(
    VIEW_NEWS, 'n', 'e', '', ugettext_lazy('Can view news'),
    ugettext_lazy('News viewer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permisson to read news of current group.'))
_register_flag(
    WRITE_NEWS, 'N', 'en', '', ugettext_lazy('Can write news'),
    ugettext_lazy('News writer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to write news in that group.'))
_register_flag(
    VIEW_FILES, 'u', 'e', '', ugettext_lazy('Can view uploaded files'),
    ugettext_lazy('File viewer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to view uploaded files in that group.'))
_register_flag(
    WRITE_FILES, 'U', 'eu', '', ugettext_lazy('Can upload files'),
    ugettext_lazy('File uploader groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to upload files.'))
_register_flag(
    VIEW_MSGS, 'x', 'ec', '', ugettext_lazy('Can view messages'),
    ugettext_lazy('Message viewer groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to view messages in that group.'))
_register_flag(
    WRITE_MSGS, 'X', 'ex', '', ugettext_lazy('Can write messages'),
    ugettext_lazy('Message sender groups'),
    ugettext_lazy('Members of these groups will automatically be granted'
                  ' permission to send messages.'))

ADMIN_ALL = (
    OPERATOR | VIEWER
    | SEE_CG | CHANGE_CG
    | SEE_MEMBERS | CHANGE_MEMBERS
    | VIEW_FIELDS | WRITE_FIELDS
    | VIEW_NEWS | WRITE_NEWS
    | VIEW_FILES | WRITE_FILES
    | VIEW_MSGS | WRITE_MSGS)


def int_to_flags(intflags):
    '''
    Converts a membership / permission integer such as MEMBER|SEE_CG|CHANGE_CG
    into a flag string such as 'meE'
    '''
    result = ''
    for flag, intflag in FLAGTOINT.items():
        if intflags & intflag:
            result += flag
    return result


def int_to_text(flags, inherited_flags):
    '''
    Converts a membership / permission integers such as MEMBER|SEE_CG|CHANGE_CG
    into a string such as "Member, Can see group exists, Can change group"
    '''
    debug_memberships = False
    automatic_member_indicator = '⁂'
    automatic_admin_indicator = '⁑'

    memberships = []
    if debug_memberships:
        # That version show everything, even when obvious like
        # Inherited member + member
        for code in 'midoveEcCfFnNuUxX':
            if flags & FLAGTOINT[code]:
                nice_perm = FLAGTOTEXT[code]
                memberships.append(nice_perm)
        for code in 'mid':
            if inherited_flags & FLAGTOINT[code]:
                nice_perm = FLAGTOTEXT[code]
                memberships.append(
                    nice_perm + ' ' + automatic_member_indicator)
        for code in 'oveEcCfFnNuUxX':
            if inherited_flags & FLAGTOINT[code]:
                nice_perm = FLAGTOTEXT[code]
                memberships.append(nice_perm + ' ' + automatic_admin_indicator)
    else:
        if flags & MEMBER:
            memberships.append(_("Member"))
        elif inherited_flags & MEMBER:
            memberships.append(_("Member") + " " + automatic_member_indicator)
        elif flags & INVITED:
            memberships.append(_("Invited"))
        elif inherited_flags & INVITED:
            memberships.append(_("Invited") + " " + automatic_member_indicator)
        elif flags & DECLINED:
            memberships.append(_("Declined"))

        for code in 'ovEcCfFnNuUexX':
            if flags & FLAGTOINT[code]:
                nice_perm = FLAGTOTEXT[code]
                memberships.append(nice_perm)
                if code == 'o':
                    break  # Don't show more details then
            elif inherited_flags & FLAGTOINT[code]:
                nice_perm = FLAGTOTEXT[code]
                memberships.append(nice_perm + ' ' + automatic_admin_indicator)
                if code == 'o':
                    break  # Don't show more details then

    return ', '.join(str(membership) for membership in memberships) or _('Nil')


def cig_flags_int(cid, gid):
    '''
    Return the integer value of flags (midoveE...)
    '''
    cursor = connection.cursor()
    cursor.execute(
        'SELECT flags FROM v_cig_flags WHERE contact_id=%s AND group_id=%s' % (
            cid, gid))
    row = cursor.fetchone()
    return row[0] or 0


def cig_flags_direct_int(cid, gid):
    '''
    Return the integer value of flags (midoveE...) without inheritance.
    Returns 0 if contact_in_group doesn't exists
    '''
    cursor = connection.cursor()
    cursor.execute(
        'SELECT flags'
        ' FROM contact_in_group'
        ' WHERE contact_id=%s AND group_id=%s'
        % (cid, gid))
    row = cursor.fetchone()
    return row[0] or 0


def cig_perms_int(cid, gid):
    '''
    Return the integer value of flags (oveE...) *excluding* m/i/d
    '''
    cursor = connection.cursor()
    cursor.execute(
        'SELECT flags FROM v_cig_perm WHERE contact_id=%s AND group_id=%s' % (
            cid, gid))
    row = cursor.fetchone()
    return row[0] or 0


def c_operatorof_cg(cid, gid):
    '''
    Returns True if contact cid is an operator of contact_group gid.
    '''
    return bool(cig_perms_int(cid, gid) & OPERATOR)


def c_can_see_cg(cid, gid):
    '''
    Returns True if contact cid can see existence of contact_group gid.
    '''
    return bool(cig_perms_int(cid, gid) & SEE_CG)


def c_can_change_cg(cid, gid):
    '''
    Returns True if contact cid can change/delete contact_group gid itself.
    '''
    return bool(cig_perms_int(cid, gid) & CHANGE_CG)


def c_can_see_members_cg(cid, gid):
    '''
    Returns True if contact cid can view members of contact_group gid.
    '''
    return bool(cig_perms_int(cid, gid) & SEE_MEMBERS)


def c_can_change_members_cg(cid, gid):
    '''
    Returns True if contact cid can change/delete memberships in contact_group
    gid.
    '''
    return bool(cig_perms_int(cid, gid) & CHANGE_MEMBERS)


def c_can_view_fields_cg(cid, gid):
    '''
    Returns True if contact cid can view contact_fields of contact_group gid.
    This is both for existence and content (for member it can see only).
    Here gid is the group that owns the fields, and grants its usage to other
    groups.
    '''
    return bool(cig_perms_int(cid, gid) & VIEW_FIELDS)


def c_can_write_fields_cg(cid, gid):
    '''
    Returns True if contact cid can write contact_fields of contact_group gid.
    Here gid is the group that owns the fields, and grants its usage to other
    groups.
    '''
    return bool(cig_perms_int(cid, gid) & WRITE_FIELDS)


def c_can_see_news_cg(cid, gid):
    '''
    Returns True if contact cid can see news of contactgroup gid.
    '''
    return bool(cig_perms_int(cid, gid) & VIEW_NEWS)


# def c_can_change_news_cg(cid, gid):
#     '''
#     Returns True if contact cid can add/change/delete news of contactgroup
#     gid.
#     '''
#     return bool(cig_perms_int(cid, gid) & WRITE_NEWS)


# def c_can_see_files_cg(cid, gid):
#     '''
#     Returns True if contact cid can see files of contactgroup gid.
#     '''
#     return bool(cig_perms_int(cid, gid) & VIEW_FILES)


# def c_can_change_files_cg(cid, gid):
#     '''
#     Returns True if contact cid can add/change/delete files of contactgroup
#     gid.
#     '''
#     return bool(cig_perms_int(cid, gid) & WRITE_FILES)


# def c_can_view_msgs_cg(cid, gid):
#     '''
#     Returns True if contact cid can see files of contactgroup gid.
#     '''
#     return bool(cig_perms_int(cid, gid) & VIEW_MSGS)


# def c_can_write_msgs_cg(cid, gid):
#     '''
#     Returns True if contact cid can add/change/delete files of contactgroup
#     gid.
#     '''
#     return bool(cig_perms_int(cid, gid) & WRITE_MSGS)


def c_can_see_c(cid1, cid2):
    '''
    Returns True if contact cid1 can see contact cid2.
    '''
    cursor = connection.cursor()
    cursor.execute(
        "SELECT EXISTS("
        "   SELECT *"
        "   FROM v_c_can_see_c"
        "   WHERE contact_id_1=%s"
        "   AND contact_id_2=%s)",
        [cid1, cid2])
    row = cursor.fetchone()
    return row[0]
