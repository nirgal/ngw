# -*- encoding: utf-8 -*-
'''
Contact managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
import os
from datetime import date
import crack
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import (
    CompatibleStreamingHttpResponse, HttpResponse, HttpResponseRedirect)
from django.utils.safestring import mark_safe
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.six import iteritems
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, RequestContext
from django.core.urlresolvers import reverse
from django import forms
from django.contrib import messages
from ngw.core.models import (
    GROUP_EVERYBODY, GROUP_USER, GROUP_USER_NGW,
    CIGFLAG_MEMBER, CIGFLAG_INVITED, CIGFLAG_DECLINED,
    ADMIN_CIGFLAGS,
    TRANS_CIGFLAG_CODE2INT, TRANS_CIGFLAG_CODE2TXT,
    Config, Contact, ContactGroup, ContactField, ContactFieldValue,
    ContactInGroup, Log,
    LOG_ACTION_ADD, LOG_ACTION_CHANGE,
    FIELD_COLUMNS, FIELD_FILTERS, FIELD_DEFAULT_GROUP)
from ngw.core.widgets import FilterMultipleSelectWidget
from ngw.core.nav import Navbar
from ngw.core.mailmerge import ngw_mailmerge
from ngw.core.contactsearch import parse_filterstring
from ngw.core import perms
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import NgwUserAcl, generic_delete, NgwListView
from ngw.core.templatetags.ngwtags import ngw_display #FIXME: not nice to import tempate tags here

from django.db.models.query import RawQuerySet, sql

DISP_NAME = 'name'
DISP_FIELD_PREFIX = 'field_'
DISP_GROUP_PREFIX = 'group_'

FTYPE_TEXT = 'TEXT'
FTYPE_LONGTEXT = 'LONGTEXT'
FTYPE_NUMBER = 'NUMBER'
FTYPE_DATE = 'DATE'
FTYPE_EMAIL = 'EMAIL'
FTYPE_PHONE = 'PHONE'
FTYPE_RIB = 'RIB'
FTYPE_CHOICE = 'CHOICE'
FTYPE_MULTIPLECHOICE = 'MULTIPLECHOICE'
FTYPE_PASSWORD = 'PASSWORD'


#######################################################################
#
# Contact list
#
#######################################################################


def membership_to_text(contact_with_extra_fields, group_id):
    debug_memberships = False
    automatic_member_indicator = '⁂'
    automatic_admin_indicator = '⁑'

    memberships = []
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % group_id)
    if flags is None:
        flags = 0
    flags_inherited = getattr(contact_with_extra_fields, 'group_%s_inherited_flags' % group_id)
    if flags_inherited is None:
        flags_inherited = 0
    flags_ainherited = getattr(contact_with_extra_fields, 'group_%s_inherited_aflags' % group_id)
    if flags_ainherited is None:
        flags_ainherited = 0

    if debug_memberships:
        # That version show everything, even when obvious like
        # Inherited member + member
        for code in 'midoveEcCfFnNuUxX':
            if flags & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm)
        for code in 'mid':
            if flags_inherited & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm + ' ' + automatic_member_indicator)
        for code in 'oveEcCfFnNuUxX':
            if flags_ainherited & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm + ' ' + automatic_admin_indicator)
    else:
        if flags & CIGFLAG_MEMBER:
            memberships.append(_("Member"))
        elif flags_inherited & CIGFLAG_MEMBER:
            memberships.append(_("Member") + " " + automatic_member_indicator)
        elif flags & CIGFLAG_INVITED:
            memberships.append(_("Invited"))
        elif flags_inherited & CIGFLAG_INVITED:
            memberships.append(_("Invited") + " " + automatic_member_indicator)
        elif flags & CIGFLAG_DECLINED:
            memberships.append(_("Declined"))

        for code in 'ovEcCfFnNuUexX':
            if flags & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm)
                if code == 'o':
                    break # Don't show more details then
            elif flags_ainherited & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm + ' ' + automatic_admin_indicator)
                if code == 'o':
                    break # Don't show more details then

    if memberships:
        result = ''
        for membership in memberships:
            if result:
                result = translation.string_concat(result, ', ')
            result = translation.string_concat(result, membership)
        return result
    else:
        return _('Nil')

def membership_to_text_factory(group_id):
    return lambda contact_with_extra_fields: \
        membership_to_text(contact_with_extra_fields, group_id)


def membership_extended_widget(request, contact_with_extra_fields, contact_group):
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % contact_group.id)
    if flags is None:
        flags = 0
    if flags & CIGFLAG_MEMBER:
        membership = 'member'
    elif flags & CIGFLAG_INVITED:
        membership = 'invited'
    elif flags & CIGFLAG_DECLINED:
        membership = 'declined'
    else:
        membership = ''

    return loader.render_to_string('membership_widget.html', {
        'cid': contact_with_extra_fields.id,
        'gid': contact_group.id,
        'membership_str': membership_to_text(contact_with_extra_fields, contact_group.id),
        'note': getattr(contact_with_extra_fields, 'group_%s_note' % contact_group.id),
        'membership': membership,
        'cig_url': contact_group.get_absolute_url()+'members/'+force_text(contact_with_extra_fields.id),
        'title': _('%(contactname)s in group %(groupname)s') % {
            'contactname':contact_with_extra_fields.name,
            'groupname': contact_group.name_with_date()},
        }, RequestContext(request))


def membership_extended_widget_factory(request, contact_group):
    return lambda contact_with_extra_fields: \
        membership_extended_widget(request, contact_with_extra_fields, contact_group)


class ContactQuerySet(RawQuerySet):
    def __init__(self, *args, **kargs):
        super(ContactQuerySet, self).__init__('', *args, **kargs)
        self.qry_fields = {'id':'contact.id', 'name':'name'}
        self.qry_from = ['contact']
        self.qry_where = []
        self.qry_orderby = []

    def add_field(self, fieldid):
        '''
        Add a field to query.
        The caller is reponsible for checking requesting user is authorized to query that field.
        '''
        fieldid = str(fieldid)
        self.qry_from.append('LEFT JOIN contact_field_value AS cfv%(fid)s ON (contact.id = cfv%(fid)s.contact_id AND cfv%(fid)s.contact_field_id = %(fid)s)' % {'fid':fieldid})
        self.qry_fields[DISP_FIELD_PREFIX+fieldid] = 'cfv%(fid)s.value' % {'fid':fieldid}

    def add_group(self, group_id):
        '''
        Add a group to query.
        The caller is reponsible for checking requesting user is authorized to view that group's members.
        '''
        group_flags_key = 'group_%s_flags' % group_id
        if group_flags_key in self.qry_fields:
            # We already have these fields
            return

        # Add column for direct membership / admin
        self.qry_fields[group_flags_key] = 'cig_%s.flags' % group_id
        self.qry_from.append('LEFT JOIN contact_in_group AS cig_%(gid)s ON (contact.id = cig_%(gid)s.contact_id AND cig_%(gid)s.group_id=%(gid)s)' % {'gid': group_id})

        # Add column for indirect membership
        self.qry_fields['group_%s_inherited_flags' % group_id] = 'cig_inherited_%s.flags' % group_id
        self.qry_from.append('''
            LEFT JOIN (
                SELECT contact_id, bit_or(flags) AS flags
                FROM contact_in_group
                WHERE contact_in_group.group_id IN (SELECT self_and_subgroups(%(gid)s))
                    AND contact_in_group.group_id<>%(gid)s
                GROUP BY contact_id) AS cig_inherited_%(gid)s
            ON (contact.id = cig_inherited_%(gid)s.contact_id)''' % {'gid': group_id})

        # Add column for inherited admin
        self.qry_fields['group_%s_inherited_aflags' % group_id] = 'gmg_inherited_%s.flags' % group_id
        self.qry_from.append('''
            LEFT JOIN (
                SELECT contact_id, bit_or(gmg_perms.flags) AS flags
                FROM contact_in_group
                JOIN (
                    SELECT self_and_subgroups(father_id) AS group_id,
                        bit_or(flags) AS flags
                    FROM group_manage_group
                    WHERE subgroup_id=%(gid)s
                    GROUP BY group_id
                ) AS gmg_perms
                ON contact_in_group.group_id=gmg_perms.group_id
                    AND contact_in_group.flags & 1 <> 0
                GROUP BY contact_id
            ) AS gmg_inherited_%(gid)s
            ON contact.id=gmg_inherited_%(gid)s.contact_id''' % {'gid': group_id})

    def add_group_withnote(self, group_id):
        '''
        Like add_group, but also adds the note in the list of columns to be returned.
        The caller is reponsible for checking requesting user is authorized to view that group's members.
        '''
        self.add_group(group_id)
        self.qry_fields['group_%s_note' % group_id] = 'cig_%s.note' % group_id

    def filter(self, extrawhere):
        self.qry_where.append(extrawhere)
        return self

    def add_params(self, params):
        if self.params:
            self.params.update(params)
        else:
            self.params = params
        return self

    def order_by(self, name):
        self.qry_orderby.append(name)
        return self

    def compile(self):
        qry = 'SELECT '
        qry += ', '.join(['%s AS "%s"' % (v, k) for k, v in iteritems(self.qry_fields)])
        qry += ' FROM ' + ' '.join(self.qry_from)
        if self.qry_where:
            qry += ' WHERE ( ' + ') AND ('.join(self.qry_where) + ' )'
        if self.qry_orderby:
            order = []
            for by in self.qry_orderby:
                if by[0] == '-':
                    order.append(by[1:]+' DESC')
                else:
                    order.append(by)
            qry += ' ORDER BY ' + ', '.join(order)

        self.raw_query = qry
        self.query = sql.RawQuery(sql=qry, using=self.db, params=self.params)

    def count(self):
        qry = 'SELECT '
        qry += ', '.join(['%s AS %s' % (v, k) for k, v in iteritems(self.qry_fields)])
        qry += ' FROM ' + ' '.join(self.qry_from)
        if self.qry_where:
            qry += ' WHERE (' + ') AND ('.join(self.qry_where) + ')'

        countqry = 'SELECT COUNT(*) FROM ('+qry+') AS qry_count'
        for count, in sql.RawQuery(sql=countqry, using=self.db, params=self.params):
            return count

    def __iter__(self):
        self.compile()
        #print(repr(self.raw_query), repr(self.params))
        for x in RawQuerySet.__iter__(self):
            yield x


def contact_make_query_with_fields(request, fields, current_cg=None, format='html'):
    '''
    Creates an iterable objects with all the required fields (including groups).
    returns a tupple (query, columns)
    Permissions are checked for the fields. Forbidden field/groups are skiped.
    '''

    q = ContactQuerySet(Contact._default_manager.model, using=Contact._default_manager._db)
    cols = []

    user_id = request.user.id
    for prop in fields:
        if prop == 'name':
            if format == 'html':
                cols.append((_('Name'), None, 'name_with_relative_link', 'name'))
            else:
                cols.append((_('Name'), None, 'name', 'name'))
        elif prop.startswith(DISP_GROUP_PREFIX):
            groupid = int(prop[len(DISP_GROUP_PREFIX):])

            if not perms.c_can_see_members_cg(user_id, groupid):
                continue # just ignore groups that aren't allowed to be seen

            q.add_group_withnote(groupid)

            cg = ContactGroup.objects.get(pk=groupid)

            if format == 'html':
                #cols.append((cg.name, None, membership_to_text_factory(groupid), None))
                cols.append((cg.name, None, membership_extended_widget_factory(request, cg), None))
                #cols.append( ('group_%s_flags' % groupid, None, 'group_%s_flags' % groupid, None))
            else:
                cols.append((cg.name, None, lambda c: membership_to_text(c, cg.id), None))
                cols.append((_('Note'), None, 'group_%s_note' % cg.id, None))

        elif prop.startswith(DISP_FIELD_PREFIX):
            fieldid = prop[len(DISP_FIELD_PREFIX):]
            cf = ContactField.objects.get(pk=fieldid)

            if not perms.c_can_view_fields_cg(user_id, cf.contact_group_id):
                continue # Just ignore fields that can't be seen

            q.add_field(fieldid)
            # TODO
            # add_field should create as_html and as_text attributes
            # then here is the last place where col[1] is ever used

            if format == 'html':
                cols.append((cf.name, cf.format_value_html, prop, prop))
            else:
                cols.append((cf.name, cf.format_value_text, prop, prop))
        else:
            raise ValueError('Invalid field '+prop)

    if current_cg is not None:
        q.add_group_withnote(current_cg.id)
        if format == 'html':
            cols.append((_('Status'), None, membership_extended_widget_factory(request, current_cg), None))
            #cols.append(('group_%s_flags' % current_cg.id, None, 'group_%s_flags' % current_cg.id, None))
            #cols.append(('group_%s_inherited_flags' % current_cg.id, None, 'group_%s_inherited_flags' % current_cg.id, None))
            #cols.append(('group_%s_inherited_aflags' % current_cg.id, None, 'group_%s_inherited_aflags' % current_cg.id, None))
        else:
            cols.append((_('Status'), None, lambda c: membership_to_text(c, current_cg.id), None))
            cols.append((_('Note'), None, 'group_%s_note' % current_cg.id, None))
    return q, cols


def get_default_columns(user):
    # check the field still exists
    result = []
    default_fields = user.get_fieldvalue_by_id(FIELD_COLUMNS)
    if not default_fields:
        try:
            default_fields = Config.objects.get(pk='columns').text
        except Config.DoesNotExist:
            pass
    if not default_fields:
        default_fields = ''
    for fname in default_fields.split(','):
        if fname == 'name':
            pass
        elif fname.startswith(DISP_GROUP_PREFIX):
            try:
                groupid = int(fname[len(DISP_GROUP_PREFIX):])
            except ValueError:
                print('Error in default fields: %s has invalid syntax.' % fname)
                continue
            try:
                ContactGroup.objects.get(pk=groupid)
            except ContactGroup.DoesNotExist:
                print('Error in default fields: There is no group #%d.' % groupid)
                continue
        elif fname.startswith(DISP_FIELD_PREFIX):
            try:
                fieldid = int(fname[len(DISP_FIELD_PREFIX):])
            except ValueError:
                print('Error in default fields: %s has invalid syntax.' % fname)
                continue
            try:
                ContactField.objects.get(pk=fieldid)
            except ContactField.DoesNotExist:
                print('Error in default fields: There is no field #%d.' % fieldid)
                continue
        else:
            print('Error in default fields: Invalid syntax in "%s".' % fname)
            continue
        result.append(fname)
    if not result:
        result = [DISP_NAME]
    return result


def get_available_columns(user_id):
    '''
    Return all available columns on contact list, based on user permission. Used in column selection.
    '''
    result = [(DISP_NAME, 'Name')]
    for cf in ContactField.objects.extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % user_id]).order_by('sort_weight'):
        result.append((DISP_FIELD_PREFIX+force_text(cf.id), cf.name))
    for cg in ContactGroup.objects.extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % user_id]).order_by('-date', 'name'):
        result.append((DISP_GROUP_PREFIX+force_text(cg.id), cg.name_with_date()))
    return result


class FieldSelectForm(forms.Form):
    '''
    Forms to select fields & groups to display. Only displays:
    - readable field
    - groups whose members can be viewed
    '''
    def __init__(self, user, *args, **kargs):
        super(FieldSelectForm, self).__init__(*args, **kargs)
        self.fields['selected_fields'] = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget('Fields', False), choices=get_available_columns(user.id))



class BaseContactListView(NgwListView):
    '''
    Base view for contact list.
    That view should NOT be called directly since there is no user check.
    '''
    template_name = 'contact_list.html'

    # contact_make_query_with_fields and Csv views
    # can be text
    query_format = 'html'

    def get_root_queryset(self):
        request = self.request
        strfilter = request.REQUEST.get('filter', '')
        filter = parse_filterstring(strfilter, request.user.id)
        self.url_params['filter'] = strfilter

        strfields = request.REQUEST.get('fields', None)
        if strfields:
            fields = strfields.split(',')
            self.url_params['fields'] = strfields
        else:
            fields = get_default_columns(request.user)
            strfields = ','.join(fields)
        #print('contact_list:', fields)

        if request.REQUEST.get('savecolumns'):
            request.user.set_fieldvalue(request, FIELD_COLUMNS, strfields)

        view_params = self.kwargs
        if 'gid' in view_params:
            cg = get_object_or_404(ContactGroup, pk=view_params['gid'])
        else:
            cg = None

        q, cols = contact_make_query_with_fields(request, fields, current_cg=cg, format=self.query_format)

        q = filter.apply_filter_to_query(q)

        # TODO:
        # We need to select only members who are in a group whose members the
        # request.user can see:
        #q.qry_where.append('')

        self.cols = cols
        self.filter = strfilter
        self.filter_html = filter.to_html()
        self.strfields = strfields
        self.fields = fields
        self.cg = cg
        return q


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Contact list')
        context['objtype'] = Contact
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['filter'] = self.filter
        context['filter_html'] = self.filter_html
        context['fields'] = self.strfields
        context['fields_form'] = FieldSelectForm(self.request.user, initial={'selected_fields': self.fields})
        context.update(kwargs)
        return super(BaseContactListView, self).get_context_data(**context)


class ContactListView(NgwUserAcl, BaseContactListView):
    '''
    This is just like the base contact list, but with user access check.
    '''
    def check_perm_user(self, user):
        if not perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
            raise PermissionDenied


#######################################################################
#
# Export contact list
#
#######################################################################

class BaseCsvContactListView(BaseContactListView):
    query_format = 'text'

    def get_paginate_by(self, queryset):
        return None

    def render_to_response(self, *args, **kwargs):
        result = ''
        def _quote_csv(u):
            return '"' + u.replace('"', '\\"') + '"'
        for i, col in enumerate(self.cols):
            if i: # not first column
                result += ','
            result += _quote_csv(col[0])
        result += '\n'
        for row in self.get_queryset():
            for i, col in enumerate(self.cols):
                if i: # not first column
                    result += ','
                v = ngw_display(row, col)
                if v == None:
                    continue
                result += _quote_csv(v)
            result += '\n'
        return HttpResponse(result, mimetype='text/csv; charset=utf-8')


class CsvContactListView(BaseCsvContactListView):
    '''
    This is just like the base CSV contact list, but with user access check.
    '''
    def check_perm_user(self, user):
        if not perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
            raise PermissionDenied


class BaseVcardContactListView(BaseContactListView):
    query_format = 'text'

    def get_paginate_by(self, queryset):
        return None

    def render_to_response(self, *args, **kwargs):
        #TODO: field permission validation
        #FIXME: This works but is really inefficient (try it on a large group!)
        result = ''
        for contact in self.get_queryset():
            result += contact.vcard()
        return HttpResponse(result, mimetype='text/x-vcard')


class VcardContactListView(BaseVcardContactListView):
    '''
    This is just like the base CSV contact list, but with user access check.
    '''
    def check_perm_user(self, user):
        if not perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
            raise PermissionDenied


#######################################################################
#
# Contact details
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_detail(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        if not perms.c_can_see_members_cg(request.user.id, gid):
            raise PermissionDenied
    else:
        # gid is undefined: access through global contact list
        if cid != request.user.id and not perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
            raise PermissionDenied
    c = get_object_or_404(Contact, pk=cid)

    rows = []
    for cf in c.get_all_visible_fields(request.user.id):
        try:
            cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            rows.append((cf.name, mark_safe(cfv.as_html())))
        except ContactFieldValue.DoesNotExist:
            pass # ignore blank values

    context = {}
    context['title'] = _('Details for %s') % force_text(c)
    if gid:
        #context['title'] += ' in group '+cg.name_with_date()
        context['cg'] = cg
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
        context['cg_perms'] = cg.get_contact_perms(request.user.id)
        context['active_submenu'] = 'members'
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['nav'].add_component(c.get_navcomponent())
    context['objtype'] = Contact
    context['contact'] = c
    context['rows'] = rows
    context['group_user_perms'] = ContactGroup.objects.get(pk=GROUP_USER).get_contact_perms(request.user.id)
    context['group_user_ngw_perms'] = ContactGroup.objects.get(pk=GROUP_USER_NGW).get_contact_perms(request.user.id)
    return render_to_response('contact_detail.html', context, RequestContext(request))


#######################################################################
#
# Contact vcard
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_vcard(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if cid == request.user.id:
        # The user can see himself
        pass
    elif gid != None and perms.c_can_see_members_cg(request.user.id, gid):
        pass
    elif gid != None and perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
        pass
    else:
        raise PermissionDenied

    # TODO: We should also check the specific fields (email, address, phone,
    # ...) are readable by user

    contact = get_object_or_404(Contact, pk=cid)
    return HttpResponse(contact.vcard(), mimetype='text/x-vcard')



#######################################################################
#
# Contact edit /add
#
#######################################################################


class ContactEditForm(forms.Form):
    def __init__(self, user_id, cid=None, contactgroup=None, *args, **kargs):
        # Note that user_id is the id of the contact making the query, not the
        # one beeing edited
        super(ContactEditForm, self).__init__(*args, **kargs)

        if perms.c_can_write_fields_cg(user_id, GROUP_EVERYBODY):
            self.fields['name'] = forms.CharField(label=_('Name'))
        if cid:
            contact = get_object_or_404(Contact, pk=cid)
            cfields = contact.get_all_writable_fields(user_id)
            # Here we have all the writable fields, including the one from
            # other groups that the user can see
        elif contactgroup:
            contactgroupids = [g.id for g in contactgroup.get_self_and_supergroups()]
            cfields = ContactField.objects.filter(contact_group_id__in=contactgroupids).extra(where=['perm_c_can_write_fields_cg(%s, contact_field.contact_group_id)' % user_id]).order_by('sort_weight')
            # Here we have the fields from contact_group and all its super
            # groups, IF user can write to them
        else: # FIXME
            cfields = []

        # store dbfields
        self.cfields = cfields

        # Add all extra forms.fields from ContactFields
        for cf in cfields:
            f = cf.get_form_fields()
            if f:
                self.fields[force_text(cf.id)] = f


@login_required()
@require_group(GROUP_USER_NGW)
def contact_edit(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if gid: # edit/add in a group
        if not perms.c_can_see_members_cg(request.user.id, gid):
            raise PermissionDenied
        cg = get_object_or_404(ContactGroup, pk=gid)
    else: # edit out of a group
        if request.user.id == cid:
            # Everybody can edit his own data
            pass
        elif not perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
            raise PermissionDenied
        cg = None

    if cid: # edit existing contact
        cid = int(cid)
    else: # record a new contact
        assert gid, 'Missing required parameter gid' # FIXME: remove from urls.py

    objtype = Contact
    if cid:
        contact = get_object_or_404(Contact, pk=cid)
        title = _('Editing %s') % force_text(contact)
    else:
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactEditForm(request.user.id, cid=cid, data=request.POST, contactgroup=cg)
        # TODO: New forms system, when bound to a models, should provide a save() method
        if form.is_valid():
            data = form.clean()
            #print('saving', repr(form.data))

            # record the values

            # 1/ The contact name
            if cid:
                if perms.c_can_write_fields_cg(request.user.id, GROUP_EVERYBODY):
                    if contact.name != data['name']:
                        log = Log(contact_id=request.user.id)
                        log.action = LOG_ACTION_CHANGE
                        log.target = 'Contact ' + force_text(contact.id)
                        log.target_repr = 'Contact ' + contact.name
                        log.property = 'Name'
                        log.property_repr = 'Name'
                        log.change = 'change from ' + contact.name + ' to ' + data['name']
                        log.save()

                    contact.name = data['name']
                    contact.save()

            else:
                if not perms.c_can_write_fields_cg(request.user.id, GROUP_EVERYBODY):
                    # If user can't write name, we have a problem creating a new contact
                    raise PermissionDenied
                contact = Contact(name=data['name'])
                contact.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_ADD
                log.target = 'Contact ' + force_text(contact.id)
                log.target_repr = 'Contact ' + contact.name
                log.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'Contact ' + force_text(contact.id)
                log.target_repr = 'Contact ' + contact.name
                log.property = 'Name'
                log.property_repr = 'Name'
                log.change = 'new value is ' + contact.name
                log = Log(request.user.id)

                cig = ContactInGroup(contact_id=contact.id, group_id=gid)
                cig.flags = CIGFLAG_MEMBER
                cig.save()
                # TODO: Log new cig
                # TODO: Check can add members in super groups


            # 2/ In ContactFields
            for cf in form.cfields:
                if cf.type == FTYPE_PASSWORD:
                    continue
                #cfname = cf.name
                cfid = cf.id
                newvalue = data[force_text(cfid)]
                if newvalue != None:
                    newvalue = cf.formfield_value_to_db_value(newvalue)
                contact.set_fieldvalue(request, cf, newvalue)

            messages.add_message(request, messages.SUCCESS, _('Contact %s has been saved sucessfully!') % contact.name)

            if cg:
                base_url = cg.get_absolute_url() + 'members/' + force_text(contact.id) + '/'
            else:
                base_url = contact.get_class_absolute_url() + force_text(contact.id) + '/'

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(base_url + 'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(base_url + '../add')
            elif perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
                return HttpResponseRedirect(base_url)
            else:
                return HttpResponseRedirect('/')

        # else add/update failed validation
    else: # GET /  HEAD
        initialdata = {}
        if cid: # modify existing
            initialdata['name'] = contact.name

            for cfv in contact.values.all():
                cf = cfv.contact_field
                if cf.type != FTYPE_PASSWORD:
                    initialdata[force_text(cf.id)] = cf.db_value_to_formfield_value(cfv.value)
            form = ContactEditForm(request.user.id, cid=cid, initial=initialdata, contactgroup=cg)

        else:
            for cf in ContactField.objects.all():
                if cf.default:
                    if cf.type == FTYPE_DATE and cf.default == 'today':
                        initialdata[force_text(cf.id)] = date.today()
                    else:
                        initialdata[force_text(cf.id)] = cf.db_value_to_formfield_value(cf.default)

            if cg:
                initialdata['groups'] = [cg.id]
                form = ContactEditForm(request.user.id, cid=cid, initial=initialdata, contactgroup=cg)
            else:
                form = ContactEditForm(request.user.id, cid=cid)

    context = {}
    context['form'] = form
    context['title'] = title
    context['id'] = cid
    context['objtype'] = objtype
    if gid:
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    if cid:
        context['nav'].add_component(contact.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))
    if cid:
        context['object'] = contact

    return render_to_response('edit.html', context, RequestContext(request))


#######################################################################
#
# Contact change password
#
#######################################################################


class ContactPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', '') != self.cleaned_data.get('confirm_password', ''):
            raise forms.ValidationError(_('The passwords must match!'))

        try:
            crack.FascistCheck(self.cleaned_data.get('new_password', ''))
        except ValueError as err:
            raise forms.ValidationError(err.message)

        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    context = {}
    context['title'] = _('Change password')
    context['contact'] = contact
    if request.method == 'POST':
        form = ContactPasswordForm(request.POST)
        if form.is_valid():
            # record the value
            password = form.clean()['new_password']
            contact.set_password(password, request=request)
            messages.add_message(request, messages.SUCCESS, _('Password has been changed sucessfully!'))
            if gid:
                cg = get_object_or_404(ContactGroup, pk=gid)
                return HttpResponseRedirect(cg.get_absolute_url() + 'members/' + force_text(cid) + '/')
            else:
                return HttpResponseRedirect(reverse('contact_detail', args=(cid,)))
    else: # GET
        form = ContactPasswordForm()
    context['form'] = form
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['nav'].add_component(contact.get_navcomponent()) \
                  .add_component(('password', _('password')))
    try:
        context['PASSWORD_LETTER'] = settings.PASSWORD_LETTER
        # So here the 'reset by letter' button will be enabled
    except AttributeError:
        pass # it's ok not to have a letter
    return render_to_response('password.html', context, RequestContext(request))


#######################################################################
#
# Contact change password hook
#
#######################################################################


@login_required()
@require_group(GROUP_USER) # not GROUP_USER_NGW
def hook_change_password(request):
    newpassword_plain = request.POST.get('password')
    if not newpassword_plain:
        return HttpResponse('Missing password POST parameter')
    #TODO: check strength
    request.user.set_password(newpassword_plain, request=request)
    return HttpResponse('OK')


#######################################################################
#
# Contact change password with pdf
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass_letter(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    context = {}
    context['title'] = _('Generate a new password and print a letter')
    context['contact'] = contact
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['nav'].add_component(contact.get_navcomponent()) \
                  .add_component(('password letter', _('password letter')))

    if request.method == 'POST':
        new_password = Contact.generate_password()

        # record the value
        contact.set_password(new_password, '2', request=request) # Generated and mailed
        messages.add_message(request, messages.SUCCESS, _('Password has been changed sucessfully!'))

        fields = {}
        for cf in contact.get_all_visible_fields(request.user.id):
            try:
                cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            except ContactFieldValue.DoesNotExist:
                continue
            fields[cf.name] = force_text(cfv).replace('\r', '')
            #if cfv:
            #    rows.append((cf.name, mark_safe(cfv.as_html())))
        fields['name'] = contact.name
        fields['password'] = new_password

        filename = ngw_mailmerge(settings.PASSWORD_LETTER, fields, '/usr/lib/ngw/mailing/generated/')
        if not filename:
            return HttpResponse(_('File generation failed'))

        fullpath = os.path.join('/usr/lib/ngw/mailing/generated/', filename)
        response = CompatibleStreamingHttpResponse(open(fullpath, 'rb'), content_type='application/pdf')
        os.unlink(fullpath)
        return response
    return render_to_response('password_letter.html', context, RequestContext(request))


#######################################################################
#
# Contact delete
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_delete(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not request.user.is_admin():
        raise PermissionDenied
    obj = get_object_or_404(Contact, pk=cid)
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        base_nav = cg.get_smart_navbar() \
                     .add_component(('members', _('members')))
        next_url = cg.get_absolute_url() + 'members/'
    else:
        next_url = reverse('contact_list')
        base_nav = None
    return generic_delete(request, obj, next_url, base_nav=base_nav)


#######################################################################
#
# Add contact filter
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_add(request, cid=None):
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_str = request.GET['filterstr']
    filter_list = contact.get_customfilters()
    filter_list.append((_('No name'), filter_str))
    filter_list_str = ','.join(['"' + force_text(name) + '","' + force_text(filterstr) + '"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)
    messages.add_message(request, messages.SUCCESS, _('Filter has been added sucessfully!'))
    return HttpResponseRedirect(reverse('filter_edit', args=(cid, len(filter_list)-1)))


#######################################################################
#
# List contact filters
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_list(request, cid=None):
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_view_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list = contact.get_customfilters()
    filters = [filtername for filtername, filter_str in filter_list]
    context = {}
    context['title'] = _('User custom filters')
    context['contact'] = contact
    context['filters'] = filters
    context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('filters', _('custom filters')))
    return render_to_response('filter_list.html', context, RequestContext(request))


#######################################################################
#
# Rename contact filter
#
#######################################################################


class FilterEditForm(forms.Form):
    name = forms.CharField(max_length=50)

@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_edit(request, cid=None, fid=None):
    cid = cid and int(cid) or None
    fid = int(fid)
    # Warning, here fid is the index in the filter list of a given user
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list = contact.get_customfilters()
    try:
        filtername, filterstr = filter_list[fid]
    except (IndexError, ValueError):
        return HttpResponse(_("ERROR: Can't find filter #%s") % fid)

    if request.method == 'POST':
        form = FilterEditForm(request.POST)
        if form.is_valid():
            #print(repr(filter_list))
            #print(repr(filter_list_str))
            filter_list[int(fid)] = (form.clean()['name'], filterstr)
            #print(repr(filter_list))
            filter_list_str = ','.join(['"' + name + '","' + filterstr + '"' for name, filterstr in filter_list])
            #print(repr(filter_list_str))
            contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)
            messages.add_message(request, messages.SUCCESS, _('Filter has been renamed.'))
            return HttpResponseRedirect(reverse('contact_detail', args=(cid,)))
    else:
        form = FilterEditForm(initial={'name': filtername})
    context = {}
    context['title'] = _('User custom filter renaming')
    context['contact'] = contact
    context['form'] = form
    context['filtername'] = filtername
    try:
        filter_html = parse_filterstring(filterstr, request.user.id).to_html()
    except PermissionDenied:
        filter_html = _("[Permission was denied to explain that filter. You probably don't have access to the fields / group names it is using.]<br>Raw filter=%s") % filterstr
    except ContactField.DoesNotExist:
        filter_html = _("Unparsable filter: Field does not exist.")
    context['filter_html'] = filter_html
    context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('filters', _('custom filters'))) \
                     .add_component((force_text(fid), filtername))

    return render_to_response('filter_form.html', context, RequestContext(request))


#######################################################################
#
# Delete contact filter
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_delete(request, cid=None, fid=None):
    cid = cid and int(cid) or None
    fid = int(fid)
    # Warning, here fid is the index in the filter list of a given user
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list = contact.get_customfilters()
    del filter_list[fid]
    filter_list_str = ','.join(['"' + name + '","' + filterstr + '"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)
    messages.add_message(request, messages.SUCCESS, _('Filter has been deleted.'))
    return HttpResponseRedirect(contact.get_absolute_url())


#######################################################################
#
# Set default group of contact
#
#######################################################################


class DefaultGroupForm(forms.Form):
    def __init__(self, contact, *args, **kargs):
        super(DefaultGroupForm, self).__init__(*args, **kargs)
        available_groups = contact.get_allgroups_member().filter(date__isnull=True)
        choices = [('', _('Create new personnal group'))] + [(cg.id, cg.name) for cg in available_groups
            if not cg.date and perms.c_can_see_cg(contact.id, cg.id)]
        self.fields['default_group'] = forms.ChoiceField(
            label=_('Default group'), choices=choices, required=False)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_default_group(request, cid=None):
    cid = cid and int(cid) or None
    contact = get_object_or_404(Contact, pk=cid)
    if not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW) and cid != request.user.id:
        raise PermissionDenied

    if request.method == 'POST':
        form = DefaultGroupForm(contact, request.POST)
        if form.is_valid():
            default_group = form.cleaned_data['default_group']
            if not default_group:
                cg = ContactGroup(
                    name=_('Group of %s') % contact.name,
                    description=_('This is the default group of %s') % contact.name,
                    )
                cg.save()
                cg.check_static_folder_created()

                cig = ContactInGroup(
                    contact_id=cid,
                    group_id=cg.id,
                    flags=CIGFLAG_MEMBER|ADMIN_CIGFLAGS,
                    )
                cig.save()
                messages.add_message(request, messages.SUCCESS, _('Personnal group created.'))
                default_group = str(cg.id)

            contact.set_fieldvalue(request, FIELD_DEFAULT_GROUP, default_group)
            messages.add_message(request, messages.SUCCESS, _('Default group has been changed sucessfully.'))
            return HttpResponseRedirect(contact.get_absolute_url())
    else:
        default_group = contact.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
        form = DefaultGroupForm(contact, initial={'default_group': default_group})
    context = {}
    context['title'] = _('User default group')
    context['contact'] = contact
    context['form'] = form
    context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('default_group', _('default group')))
    return render_to_response('contact_default_group.html', context, RequestContext(request))


#######################################################################
#
# Make batch pdf for password generation
#
#######################################################################


#@login_required()
#@require_group(GROUP_ADMIN)
#def contact_make_login_mailing(request):
#    # select contacts whose password is in state 'Registered', with both 'Adress' and 'City' not null
#    q = Contact.objects
#    q = q.extra(where=["EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value='%(value)s')" % { 'field_id': FIELD_PASSWORD_STATUS, 'value': '1' }])
#    q = q.extra(where=['EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i)' % { 'field_id': FIELD_STREET}])
#    q.extra(where=['EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i)' % { 'field_id': FIELD_CITY}])
#    ids = [ row.id for row in q ]
#    #print(ids)
#    if not ids:
#        return HttpResponse('No waiting mail')
#
#    result = ngw_mailmerge('/usr/lib/ngw/mailing/forms/welcome.odt', [str(id) for id in ids])
#    if not result:
#        return HttpResponse('File generation failed')
#    #print(result)
#    filename = os.path.basename(result)
#    if subprocess.call(['sudo', '/usr/bin/mvoomail', os.path.splitext(filename)[0], '/usr/lib/ngw/mailing/generated/']):
#        return HttpResponse('File move failed')
#    for row in q:
#        contact = row[0]
#        contact.set_fieldvalue(request, FIELD_PASSWORD_STATUS, '2')
#
#    return HttpResponse('File generated in /usr/lib/ngw/mailing/generated/')

