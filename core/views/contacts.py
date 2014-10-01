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
    StreamingHttpResponse, HttpResponse, HttpResponseRedirect,
    Http404)
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.utils.six import iteritems
from django.utils import html
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from django.template import loader, RequestContext
from django.core.urlresolvers import reverse
from django import forms
from django.views.generic import View, TemplateView, FormView, UpdateView, CreateView, DetailView
from django.views.generic.edit import ModelFormMixin
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from ngw.core.models import (
    GROUP_EVERYBODY, GROUP_USER, GROUP_USER_NGW,
    Config, Contact, ContactGroup, ContactField, ContactFieldValue,
    ContactInGroup, Log,
    LOG_ACTION_ADD, LOG_ACTION_CHANGE,
    FIELD_COLUMNS, FIELD_FILTERS, FIELD_DEFAULT_GROUP)
from ngw.core.nav import Navbar
from ngw.core.mailmerge import ngw_mailmerge
from ngw.core.contactsearch import parse_filterstring
from ngw.core import perms
from ngw.core.views.generic import NgwUserAcl, InGroupAcl, NgwListView, NgwDeleteView

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

    def filter(self, extrawhere=None, pk__in=None):
        if extrawhere is not None:
            self.qry_where.append(extrawhere)
        if pk__in:
            self.qry_where.append('contact.id IN (%s)' % ','.join(pk__in))
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
        self.fields['selected_fields'] = forms.MultipleChoiceField(
            required=False, widget=FilteredSelectMultiple(_('Fields'), False),
            choices=get_available_columns(user.id))



def membership_to_text(contact_with_extra_fields, group_id):
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % group_id)
    if flags is None:
        flags = 0
    flags_inherited = getattr(contact_with_extra_fields, 'group_%s_inherited_flags' % group_id)
    if flags_inherited is None:
        flags_inherited = 0
    flags_ainherited = getattr(contact_with_extra_fields, 'group_%s_inherited_aflags' % group_id)
    if flags_ainherited is None:
        flags_ainherited = 0

    return perms.int_to_text(
        flags,
        (flags_inherited & ~perms.ADMIN_ALL) | (flags_ainherited & perms.ADMIN_ALL))


def membership_to_text_factory(group_id):
    return lambda contact_with_extra_fields: \
        membership_to_text(contact_with_extra_fields, group_id)


def membership_extended_widget(request, contact_with_extra_fields, contact_group):
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % contact_group.id)
    if flags is None:
        flags = 0
    if flags & perms.MEMBER:
        membership = 'member'
    elif flags & perms.INVITED:
        membership = 'invited'
    elif flags & perms.DECLINED:
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


def field_widget(contact_field, contact_with_extra_fields):
    attrib_name = DISP_FIELD_PREFIX + force_text(contact_field.id)
    raw_value = getattr(contact_with_extra_fields, attrib_name)
    if raw_value:
        return contact_field.format_value_html(raw_value)
    else:
        return ''

def field_widget_factory(contact_field):
    return lambda contact_with_extra_fields: \
        field_widget(contact_field, contact_with_extra_fields)



class BaseContactListView(NgwListView):
    '''
    Base view for contact list.
    That view should NOT be called directly since there is no user check.
    '''
    template_name = 'contact_list.html'

    actions = (
        'action_csv_export',
        'action_vcard_export',
        'action_bcc',
    )

    def contact_make_query_with_fields(self, request, fields):
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
                cols.append((_('Name'), 'name_with_relative_link', 'name'))
            elif prop.startswith(DISP_GROUP_PREFIX):
                groupid = int(prop[len(DISP_GROUP_PREFIX):])

                if not perms.c_can_see_members_cg(user_id, groupid):
                    continue # just ignore groups that aren't allowed to be seen

                q.add_group_withnote(groupid)

                cg = ContactGroup.objects.get(pk=groupid)

                #attribute_name = 'text_'+prop
                #setattr(self, attribute_name, membership_to_text_factory(groupid))
                #cols.append((cg.name, attribute_name, None))

                attribute_name = 'html_'+prop
                setattr(self, attribute_name, membership_extended_widget_factory(request, cg))
                cols.append((cg.name, attribute_name, None))

                #cols.append( ('group_%s_flags' % groupid, 'group_%s_flags' % groupid, None))

            elif prop.startswith(DISP_FIELD_PREFIX):
                fieldid = prop[len(DISP_FIELD_PREFIX):]
                cf = ContactField.objects.get(pk=fieldid)

                if not perms.c_can_view_fields_cg(user_id, cf.contact_group_id):
                    continue # Just ignore fields that can't be seen

                q.add_field(fieldid)

                cols.append((cf.name, field_widget_factory(cf), prop))
            else:
                raise ValueError('Invalid field '+prop)

        current_cg = self.contactgroup
        if current_cg is not None:
            q.add_group_withnote(current_cg.id)
            self.group_status = membership_extended_widget_factory(request, current_cg)
            cols.append((_('Status'), "group_status", None))
            #cols.append(('group_%s_flags' % current_cg.id, 'group_%s_flags' % current_cg.id, None))
            #cols.append(('group_%s_inherited_flags' % current_cg.id, 'group_%s_inherited_flags' % current_cg.id, None))
            #cols.append(('group_%s_inherited_aflags' % current_cg.id, 'group_%s_inherited_aflags' % current_cg.id, None))

        return q, cols


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

        if request.REQUEST.get('savecolumns'):
            request.user.set_fieldvalue(request, FIELD_COLUMNS, strfields)

        # Make sure self.contactgroup is defined:
        if not hasattr(self, 'contactgroup'):
            self.contactgroup = None

        q, cols = self.contact_make_query_with_fields(request, fields)

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


    def action_csv_export(self, request, queryset):
        result = ''
        def _quote_csv(col_html):
            u = html.strip_tags(force_text(col_html))
            return '"' + u.replace('\\', '\\\\').replace('"', '\\"') + '"'
        for i, col in enumerate(self.cols):
            if i: # not first column
                result += ','
            result += _quote_csv(col[0])
        result += '\n'
        for row in queryset:
            for i, col_html in enumerate(self.row_to_items(row)):
                if i: # not first column
                    result += ','
                if col_html == None:
                    continue
                result += _quote_csv(col_html)
            result += '\n'
        return HttpResponse(result, content_type='text/csv; charset=utf-8')
    action_csv_export.short_description = _("CSV format export (Spreadsheet format)")


    def action_bcc(self, request, queryset):
        emails = []
        noemails = []
        for contact in queryset:
            c_emails = contact.get_fieldvalues_by_type('EMAIL')  # only the first email
            if c_emails:
                emails.append(c_emails[0])
            else:
                noemails.append(contact.name)

        messages.add_message(request, messages.WARNING, _('The following people do not have an email address: %s') %
            ', '.join(noemails))

        response = HttpResponse(status=303)
        response['Location'] = 'mailto:?bcc=' + ','.join(emails)
        return response
    action_bcc.short_description = _("Send email locally (thunderbird or similar)")


    def action_vcard_export(self, request, queryset):
        result = ''
        for contact in queryset:
            result += contact.vcard()
        return HttpResponse(result, content_type='text/x-vcard')
    action_vcard_export.short_description = _("Vcard format export")


class ContactListView(NgwUserAcl, BaseContactListView):
    '''
    This is just like the base contact list, but with user access check.
    '''
    def check_perm_user(self, user):
        if not perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
            raise PermissionDenied


#######################################################################
#
# Contact details
#
#######################################################################


class ContactDetailView(InGroupAcl, TemplateView):
    is_group_required = False
    template_name = 'contact_detail.html'

    def check_perm_groupuser(self, group, user):
        cid = int(self.kwargs['cid'])
        if self.contactgroup:
            if not perms.c_can_see_members_cg(user.id, group.id):
                raise PermissionDenied
        else:  # No group specified
            if cid == user.id:
                # The user can see himself
                pass
            elif perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
                pass
            else:
                raise PermissionDenied

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        contact = get_object_or_404(Contact, pk=cid)

        rows = []
        for cf in contact.get_all_visible_fields(self.request.user.id):
            try:
                cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
                rows.append((cf.name, mark_safe(cfv.as_html())))
            except ContactFieldValue.DoesNotExist:
                pass # ignore blank values

        context = {}
        context['title'] = _('Details for %s') % contact
        cg = self.contactgroup
        if cg:
            #context['title'] += ' in group '+cg.name_with_date()
            context['nav'] = cg.get_smart_navbar() \
                             .add_component(('members', _('members')))
            context['active_submenu'] = 'members'
        else:
            context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['objtype'] = Contact
        context['contact'] = contact
        context['rows'] = rows
        context['group_user_perms'] = ContactGroup.objects.get(pk=GROUP_USER).get_contact_perms(self.request.user.id)
        context['group_user_ngw_perms'] = ContactGroup.objects.get(pk=GROUP_USER_NGW).get_contact_perms(self.request.user.id)

        context.update(kwargs)
        return super(ContactDetailView, self).get_context_data(**context)


#######################################################################
#
# Contact vcard
#
#######################################################################


class ContactVcardView(InGroupAcl, View):
    '''
    Returns vcf file for specified user
    '''

    is_group_required = False

    def check_perm_groupuser(self, group, user):
        cid = int(self.kwargs['cid'])
        if self.contactgroup:
            if not perms.c_can_see_members_cg(user.id, group.id):
                raise PermissionDenied
        else:  # No group specified
            if cid == user.id:
                # The user can see himself
                pass
            elif perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
                pass
            else:
                raise PermissionDenied

    def get(self, request, *args, **kwargs):
        # TODO: We should also check the specific fields (email, address, phone,
        # ...) are readable by user

        cid = int(self.kwargs['cid'])
        contact = get_object_or_404(Contact, pk=cid)
        return HttpResponse(contact.vcard(), content_type='text/x-vcard')


#######################################################################
#
# Contact edit /add
#
#######################################################################


class ContactEditForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name']

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance', None)
        contactgroup = kwargs.pop('contactgroup')
        user = kwargs.pop('user')  # contact making the query, not the edited one
        super(ContactEditForm, self).__init__(*args, **kwargs)

        self.contactgroup = contactgroup

        if not perms.c_can_write_fields_cg(user.id, GROUP_EVERYBODY):
            del self.fields['name'] # = forms.CharField(label=_('Name'))
        if instance:
            cfields = instance.get_all_writable_fields(user.id)
            # Here we have all the writable fields, including the one from
            # other groups that the user can see
        elif contactgroup:
            contactgroupids = [g.id for g in contactgroup.get_self_and_supergroups()]
            cfields = ContactField.objects.filter(contact_group_id__in=contactgroupids).extra(where=['perm_c_can_write_fields_cg(%s, contact_field.contact_group_id)' % user.id]).order_by('sort_weight')
            # Here we have the fields from contact_group and all its super
            # groups, IF user can write to them
        else: # FIXME
            cfields = []

        # store dbfields
        self.cfields = cfields

        for cf in cfields:
            f = cf.get_form_fields()
            if f:
                try:
                    cfv = ContactFieldValue.objects.get(contact=instance, contact_field=cf)
                    f.initial = cf.db_value_to_formfield_value(cfv.value)
                except ContactFieldValue.DoesNotExist:
                    initial = cf.default
                    if cf.type == FTYPE_DATE and initial == 'today':
                        initial = date.today()
                    f.initial = initial
                self.fields[force_text(cf.id)] = f


    def save(self, request):
        is_creation = self.instance.pk is None

        contact = super(ContactEditForm, self).save()
        data = self.cleaned_data

        # 1/ The contact name

        if is_creation:
            if not perms.c_can_write_fields_cg(request.user.id, GROUP_EVERYBODY):
                # If user can't write name, we have a problem creating a new contact
                raise PermissionDenied

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

            cig = ContactInGroup(contact_id=contact.id, group_id=self.contactgroup.id)
            cig.flags = perms.MEMBER
            cig.save()
            # TODO: Log new cig
            # TODO: Check can add members in super groups
        else:
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

        # 2/ In ContactFields
        for cf in self.cfields:
            if cf.type == FTYPE_PASSWORD:
                continue
            #cfname = cf.name
            newvalue = data[force_text(cf.id)]
            if newvalue != None:
                newvalue = cf.formfield_value_to_db_value(newvalue)
            contact.set_fieldvalue(request, cf, newvalue)

        return contact


class ContactEditMixin(ModelFormMixin):
    template_name = 'edit.html'
    form_class = ContactEditForm
    model = Contact
    pk_url_kwarg = 'cid'

    def check_perm_groupuser(self, group, user):
        if group:
            if not perms.c_can_change_members_cg(user.id, group.id):
                raise PermissionDenied
        else:
            cid = int(self.kwargs['cid'])  # ok to crash if create & no group
            if cid == user.id:
                # The user can change himself
                pass
            elif perms.c_can_change_members_cg(user.id, GROUP_EVERYBODY):
                pass
            else:
                raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super(ContactEditMixin, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['contactgroup'] = self.contactgroup
        return kwargs

    def form_valid(self, form):
        request = self.request
        contact = form.save(request)

        messages.add_message(request, messages.SUCCESS, _('Contact %s has been saved.') % contact.name)

        if request.POST.get('_continue', None):
            return HttpResponseRedirect('edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect('../add')
        else:
            return HttpResponseRedirect('.')

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing %s') % self.object
            id = self.object.id
        else:
            title = _('Adding a new %s') % Contact.get_class_verbose_name()
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = Contact
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar() \
                             .add_component(('members', _('members')))
        else:
            context['nav'] = Navbar(Contact.get_class_navcomponent())

        if id:
            context['nav'].add_component(self.object.get_navcomponent()) \
                          .add_component(('edit', _('edit')))
        else:
            context['nav'].add_component(('add', _('add')))

        context.update(kwargs)
        return super(ContactEditMixin, self).get_context_data(**context)


class ContactEditView(InGroupAcl, ContactEditMixin, UpdateView):
    pass


class ContactCreateView(InGroupAcl, ContactEditMixin, CreateView):
    pass


#######################################################################
#
# Contact change password
#
#######################################################################


class ContactPasswordForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = []
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', '') != self.cleaned_data.get('confirm_password', ''):
            raise forms.ValidationError(_('The passwords must match!'))

        try:
            crack.FascistCheck(self.cleaned_data.get('new_password', ''))
        except ValueError as err:
            raise forms.ValidationError("%s" % err)

        return self.cleaned_data

    def save(self, request):
        data = self.cleaned_data
        self.instance.set_password(data['new_password'], request=request)
        return self.instance


class PasswordView(InGroupAcl, UpdateView):
    '''
    Change contact password
    '''

    is_group_required = False
    template_name = 'password.html'
    form_class = ContactPasswordForm
    model = Contact
    pk_url_kwarg = 'cid'

    def check_perm_groupuser(self, group, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER):
            raise PermissionDenied

    def form_valid(self, form):
        contact = form.save(self.request)
        messages.add_message(
            self.request, messages.SUCCESS,
            _('Password has been changed sucessfully!'))
        if self.contactgroup:
            return HttpResponseRedirect(
                self.contactgroup.get_absolute_url() + 'members/' + force_text(contact.id) + '/')
        else:
            return HttpResponseRedirect(contact.get_absolute_url())

    def get_context_data(self, **kwargs):
        contact = self.object
        context = {}
        context['title'] = _('Change password')
        context['contact'] = contact
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar() \
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
        context.update(kwargs)
        return super(PasswordView, self).get_context_data(**context)


#######################################################################
#
# Contact change password hook
#
#######################################################################


class HookPasswordView(View):
    '''
    This view allow a user to change his password through a post.
    That view allow other modules to change the central password.
    '''
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        username = request.META['REMOTE_USER']  # Apache external auth
        request.user = Contact.objects.get_by_natural_key(username)
        return super(HookPasswordView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        newpassword_plain = request.POST['password']
        request.user.set_password(newpassword_plain, request=request)
        return HttpResponse('OK')


#######################################################################
#
# Contact change password with pdf
#
#######################################################################


class PassLetterView(InGroupAcl, DetailView):
    '''
    Reset the password and generate a ready to print pdf letter with it.
    '''
    is_group_required = False
    model = Contact
    pk_url_kwarg = 'cid'
    template_name = 'password_letter.html'

    def check_perm_groupuser(self, group, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER):
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        contact = self.object
        context = {}
        context['title'] = _('Generate a new password and print a letter')
        context['contact'] = contact
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar() \
                             .add_component(('members', _('members')))
        else:
            context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent()) \
                  .add_component(('password letter', _('password letter')))
        context.update(kwargs)
        return super(PassLetterView, self).get_context_data(**context)

    def post(self, request, *args, **kwargs):
        contact = self.get_object()

        new_password = Contact.objects.make_random_password()

        # record the value
        contact.set_password(new_password, '2', request=request) # Generated and mailed
        messages.add_message(request, messages.SUCCESS, _('Password has been changed sucessfully!'))

        fields = {}
        for cf in contact.get_all_visible_fields(request.user.id):
            try:
                cfv = ContactFieldValue.objects.get(contact_id=contact.id, contact_field_id=cf.id)
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
        response = StreamingHttpResponse(open(fullpath, 'rb'), content_type='application/pdf')
        os.unlink(fullpath)
        return response


#######################################################################
#
# Contact delete
#
#######################################################################


class ContactDeleteView(InGroupAcl, NgwDeleteView):
    is_group_required = False
    model = Contact
    pk_url_kwarg = 'cid'

    def check_perm_groupuser(self, group, user):
        if not user.is_admin():
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        context = {}
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar() \
                     .add_component(('members', _('members'))) \
                     .add_component(('delete', _('delete')))
        context.update(kwargs)
        return super(ContactDeleteView, self).get_context_data(**context)


#######################################################################
#
# Add contact filter
#
#######################################################################


class FilterAddView(NgwUserAcl, View):
    def check_perm_user(self, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER_NGW):
            raise PermissionDenied

    def get(self, request, cid):
        cid = int(cid)
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


class FilterListView(InGroupAcl, TemplateView):
    '''
    List user custom filters
    '''
    is_group_required = False
    template_name = 'filter_list.html'

    def check_perm_groupuser(self, group, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_view_fields_cg(user.id, GROUP_USER_NGW):
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
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

        context.update(kwargs)
        return super(FilterListView, self).get_context_data(**context)


#######################################################################
#
# Rename custom filter
#
#######################################################################


class FilterEditForm(forms.Form):
    name = forms.CharField(max_length=50)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        contact = kwargs.pop('contact')
        fid = int(kwargs.pop('fid'))
        super(FilterEditForm, self).__init__(*args, **kwargs)

        self.contact = contact
        self.fid = fid
        self.filter_list = contact.get_customfilters()
        try:
            self.filtername, filterstr = self.filter_list[fid]
        except (IndexError, ValueError):
            raise Http404
        self.fields['name'].initial = self.filtername
        try:
            self.filter_html = parse_filterstring(filterstr, user.id).to_html()
        except PermissionDenied:
            self.filter_html = _("[Permission was denied to explain that filter. You probably don't have access to the fields / group names it is using.]<br>Raw filter=%s") % filterstr

    def save(self, request):
        filter_list = self.filter_list
        filter_list[self.fid] = self.cleaned_data['name'], filter_list[self.fid][1]
        filter_list_str = ','.join(
            ['"%s","%s"' % filterdata for filterdata in filter_list])
        self.contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)


class FilterEditView(NgwUserAcl, FormView):
    form_class = FilterEditForm
    template_name = 'filter_form.html'

    def check_perm_user(self, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER_NGW):
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super(FilterEditView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['contact'] = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        kwargs['fid'] = self.kwargs['fid']
        return kwargs

    def get_context_data(self, **kwargs):
        contact = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        context = {}
        context['title'] = _('User custom filter renaming')
        context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                         .add_component(contact.get_navcomponent()) \
                         .add_component(('filters', _('custom filters')))
        #                 .add_component((self.kwargs['fid'], self.form.filtername))
        context.update(kwargs)
        return super(FilterEditView, self).get_context_data(**context)

    def form_valid(self, form):
        form.save(self.request)
        messages.add_message(self.request, messages.SUCCESS, _('Filter has been renamed.'))
        return super(FilterEditView, self).form_valid(form)

    def get_success_url(self):
        return reverse('contact_detail', args=(self.kwargs['cid'],))


#######################################################################
#
# Delete contact filter
#
#######################################################################


class FilterDeleteView(NgwUserAcl, View):
    def check_perm_user(self, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER_NGW):
            raise PermissionDenied

    def get(self, request, cid, fid):
        cid = int(cid)
        fid = int(fid)
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


class DefaultGroupForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = []
    def __init__(self, *args, **kwargs):
        contact = kwargs.get('instance')
        super(DefaultGroupForm, self).__init__(*args, **kwargs)
        available_groups = contact.get_allgroups_member().filter(date__isnull=True)
        choices = [('', _('Create new personnal group'))] + [(cg.id, cg.name) for cg in available_groups
            if not cg.date and perms.c_can_see_cg(contact.id, cg.id)]
        default_group = contact.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
        self.fields['default_group'] = forms.ChoiceField(
            label=_('Default group'), choices=choices, required=False,
            initial=default_group)

    def save(self, request):
        default_group = self.cleaned_data['default_group']
        contact = self.instance
        if not default_group:
            cg = ContactGroup(
                name=_('Group of %s') % contact.name,
                description=_('This is the default group of %s') % contact.name,
                )
            cg.save()
            cg.check_static_folder_created()

            cig = ContactInGroup(
                contact=contact,
                group_id=cg.id,
                flags=perms.MEMBER|perms.ADMIN_ALL,
                )
            cig.save()
            messages.add_message(request, messages.SUCCESS, _('Personnal group created.'))
            default_group = str(cg.id)
        contact.set_fieldvalue(request, FIELD_DEFAULT_GROUP, default_group)
        return contact


class DefaultGroupView(NgwUserAcl, UpdateView):
    '''
    Change the default group
    '''
    template_name = 'contact_default_group.html'
    form_class = DefaultGroupForm
    model = Contact
    pk_url_kwarg = 'cid'

    def check_perm_user(self, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER_NGW):
            raise PermissionDenied

    def form_valid(self, form):
        contact = form.save(self.request)
        messages.add_message(self.request, messages.SUCCESS, _('Default group has been changed sucessfully.'))
        return HttpResponseRedirect(contact.get_absolute_url())

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        contact = get_object_or_404(Contact, pk=cid)
        context = {}
        context['title'] = _('User default group')
        context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                         .add_component(contact.get_navcomponent()) \
                         .add_component(('default_group', _('default group')))

        context.update(kwargs)
        return super(DefaultGroupView, self).get_context_data(**context)


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

