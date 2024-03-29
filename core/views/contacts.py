'''
Contact managing views
'''

import json
from datetime import date, datetime, timedelta

from django import forms
from django.contrib import messages
from django.contrib.admin import filters
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import password_validation
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.db.models.query import RawQuerySet, sql
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template import loader
from django.urls import reverse
from django.utils import formats, html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.generic import (CreateView, FormView, TemplateView,
                                  UpdateView, View)
from django.views.generic.edit import ModelFormMixin

from ngw.core import perms
from ngw.core.contactsearch import parse_filterstring
from ngw.core.models import (FIELD_BIRTHDAY, FIELD_COLUMNS,
                             FIELD_DEFAULT_GROUP, GROUP_EVERYBODY, GROUP_USER,
                             GROUP_USER_NGW, LOG_ACTION_ADD, LOG_ACTION_CHANGE,
                             Config, Contact, ContactField, ContactFieldValue,
                             ContactGroup, ContactInGroup, Log)
from ngw.core.nav import Navbar
from ngw.core.views.generic import (InGroupAcl, NgwDeleteView, NgwListView,
                                    NgwUserAcl)
from ngw.core.widgets import FlagsField

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
        super().__init__('', *args, **kargs)
        self.qry_fields = {'id': 'contact.id', 'name': 'name'}
        self.qry_from = ['contact']
        self.qry_where = []
        self.qry_orderby = []
        self.offset = None
        self.limit = None
        self.__hack_for_changelist()

    def __hack_for_changelist(self):
        self.query.select_related = True
        # raw_query = self
        # def get_order_by(self, value):
        #     return raw_query.qry_orderby
        # def set_order_by(self, value):
        #     raw_query.qry_orderby = value
        # self.query.order_by = property(get_order_by, set_order_by)
        self.query.order_by = []

    def __repr__(self):
        self.compile()
        return super().__repr__()

    def add_field(self, fieldid):
        '''
        Add a field to query.
        The caller is reponsible for checking requesting user is authorized to
        query that field.
        '''
        fieldid = str(fieldid)
        self.qry_from.append(
            'LEFT JOIN contact_field_value AS cfv{fid}'
            ' ON (contact.id = cfv{fid}.contact_id'
            '     AND cfv{fid}.contact_field_id = {fid})'
            .format(fid=fieldid))
        self.qry_fields[DISP_FIELD_PREFIX+fieldid] = 'cfv{fid}.value'.format(
            fid=fieldid)

    def add_group(self, group_id):
        '''
        Add a group to query.
        The caller is reponsible for checking requesting user is authorized to
        view that group's members.
        '''
        group_flags_key = 'group_{}_flags'.format(group_id)
        if group_flags_key in self.qry_fields:
            # We already have these fields
            return

        # Add column for direct membership / admin
        self.qry_fields[group_flags_key] = 'cig_{}.flags'.format(group_id)
        self.qry_from.append(
            'LEFT JOIN contact_in_group AS cig_{gid}'
            ' ON (contact.id = cig_{gid}.contact_id'
            '     AND cig_{gid}.group_id={gid}'
            ')'
            .format(gid=group_id))

        # Add column for indirect membership
        self.qry_fields['group_{}_inherited_flags'.format(group_id)] = (
            'cig_inherited_{}.flags'.format(group_id))
        self.qry_from.append('''
            LEFT JOIN (
                SELECT contact_id, bit_or(flags) AS flags
                FROM contact_in_group
                WHERE contact_in_group.group_id
                        IN (SELECT self_and_subgroups({gid}))
                    AND contact_in_group.group_id<>{gid}
                GROUP BY contact_id) AS cig_inherited_{gid}
            ON (contact.id = cig_inherited_{gid}.contact_id)
            '''.format(gid=group_id))

        # Add column for inherited admin
        self.qry_fields['group_{}_inherited_aflags'.format(group_id)] = (
            'gmg_inherited_{}.flags'.format(group_id))
        self.qry_from.append('''
            LEFT JOIN (
                SELECT contact_id, bit_or(gmg_perms.flags) AS flags
                FROM contact_in_group
                JOIN (
                    SELECT self_and_subgroups(father_id) AS group_id,
                        bit_or(flags) AS flags
                    FROM group_manage_group
                    WHERE subgroup_id={gid}
                    GROUP BY group_id
                ) AS gmg_perms
                ON contact_in_group.group_id=gmg_perms.group_id
                    AND contact_in_group.flags & 1 <> 0
                GROUP BY contact_id
            ) AS gmg_inherited_{gid}
            ON contact.id=gmg_inherited_{gid}.contact_id
            '''.format(gid=group_id))

        self.qry_fields['group_{}_note'.format(group_id)] = (
            'cig_{}.note'.format(group_id))

    def add_messages(self, group_id):
        '''
        Add column with how many messages are there.
        '''

        self.qry_fields['group_{}_msgcount'.format(group_id)] = '''(
            SELECT count(*)
            FROM contact_message
            WHERE contact_message.contact_id = contact.id
            AND group_id = {group_id}
        )'''.format(group_id=group_id)
        self.qry_fields['group_{}_unreadcount'.format(group_id)] = '''(
            SELECT count(*)
            FROM contact_message
            WHERE contact_message.contact_id = contact.id
            AND group_id = {group_id}
            AND is_answer
            AND read_date IS NULL
        )'''.format(group_id=group_id)

    def add_busy(self, group_id=None):
        '''
        Add a "busy" column with a summary of availability of that contact.
        Use the date of the group, if any.
        Use current date otherwith.
        '''
        colname = 'busy'
        if colname in self.qry_fields:
            return  # already there!
        if group_id is not None:
            self.qry_from.append('''
                LEFT JOIN (
                    SELECT
                        contact_id,
                        bit_or(flags) & 3 AS busy
                    FROM v_cig_membership_inherited
                    JOIN contact_group
                        ON v_cig_membership_inherited.group_id=contact_group.id
                        AND contact_group.busy  -- Only "busy" group
                    WHERE contact_group.date IS NOT NULL
                    AND daterange(contact_group.date,
                                  contact_group.end_date,
                                  '[]')
                        -- && daterange('2017-08-01', '2017-08-31', '[]')
                        && ( SELECT daterange(date, end_date, '[]')
                             FROM contact_group WHERE id={gid})
                    AND v_cig_membership_inherited.group_id != {gid}
                    GROUP BY contact_id
                ) AS busy_sub
                ON contact.id=busy_sub.contact_id
                '''.format(gid=group_id))
        else:
            self.qry_from.append('''
                LEFT JOIN (
                    SELECT
                        contact_id,
                        bit_or(flags) & 3 AS busy
                    FROM v_cig_membership_inherited
                    JOIN contact_group
                        ON v_cig_membership_inherited.group_id=contact_group.id
                        AND contact_group.busy  -- Only "busy" group
                    WHERE contact_group.date IS NOT NULL
                    AND daterange(contact_group.date,
                                  contact_group.end_date,
                                  '[]')
                        @> current_date
                    GROUP BY contact_id
                ) AS busy_sub
                ON contact.id=busy_sub.contact_id
                ''')
        self.qry_fields[colname] = 'COALESCE(busy, 0)'

    def add_birthday(self, cg=None):
        '''
        Add a "birthday" column for that that contact.
        Use the date of the group, if any.
        Use current date otherwith.
        '''
        colname = 'birthday'
        if colname in self.qry_fields:
            return  # already there!
        if cg is not None:
            self.qry_from.append(
                '''
                LEFT JOIN contact_field_value AS cfvbirthday
                ON (contact.id = cfvbirthday.contact_id
                    AND cfvbirthday.contact_field_id = {fid}
                    AND daterange('{startdate}'::date,
                                  '{enddate}'::date,
                                 '[]')
                        @> birthday_after_date(value::date,
                                               '{startdate}'::date)
                    )
                '''.format(
                    startdate=cg.date,
                    enddate=cg.end_date,
                    fid=FIELD_BIRTHDAY))
        else:
            self.qry_from.append(
                '''
                LEFT JOIN contact_field_value AS cfvbirthday
                 ON (contact.id = cfvbirthday.contact_id
                     AND cfvbirthday.contact_field_id = {fid}
                     AND to_char(value::date, 'MM-DD')
                       = to_char(current_date, 'MM-DD')
                     )
                '''.format(fid=FIELD_BIRTHDAY))
        self.qry_fields[colname] = 'cfvbirthday.value'

    def filter(self, extrawhere=None, pk__in=None):
        if extrawhere is not None:
            self.qry_where.append(extrawhere)
        if pk__in:
            self.qry_where.append('contact.id IN ({})'.format(
                ','.join(pk__in)))
        return self

    def add_params(self, params):
        if self.params:
            self.params.update(params)
        else:
            self.params = params
        return self

    def order_by(self, *names):
        # print('qs.order_by', repr(names))
        for name in names:
            if name != 'pk' and name != '-pk':
                self.qry_orderby.append(name)
        return self

    def compile(self):
        qry = 'SELECT '
        qry += ', '.join(['{} AS "{}"'.format(v, k)
                          for k, v in self.qry_fields.items()])
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

        if self.offset:
            qry += ' OFFSET {}'.format(self.offset)

        if self.limit:
            qry += ' LIMIT {}'.format(self.limit)

        self.raw_query = qry
        self.query = sql.RawQuery(sql=qry, using=self.db, params=self.params)
        self.__hack_for_changelist()
        # print(repr(self.raw_query), repr(self.params))

    def count(self):
        qry = 'SELECT '
        qry += ', '.join(['{} AS {}'.format(v, k)
                          for k, v in self.qry_fields.items()])
        qry += ' FROM ' + ' '.join(self.qry_from)
        if self.qry_where:
            qry += ' WHERE (' + ') AND ('.join(self.qry_where) + ')'

        countqry = 'SELECT COUNT(*) FROM ('+qry+') AS qry_count'
        for count, in sql.RawQuery(sql=countqry,
                                   using=self.db,
                                   params=self.params):
            return count

    def __iter__(self):
        self.compile()
        for x in RawQuerySet.__iter__(self):
            yield x

    def __getitem__(self, k):
        if isinstance(k, slice):
            self.offset = k.start or 0
            if k.stop is not None:
                self.limit = k.stop - self.offset
            if k.step:
                raise NotImplementedError
            return self

        # return only one:
        self.offset = k
        self.limit = 1
        for contact in self:
            return contact

    def _clone(self):
        return self  # FIXME ugly hack for ChangeList


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
        if fname == 'name' or fname == 'busy':
            pass
        elif fname.startswith(DISP_GROUP_PREFIX):
            try:
                groupid = int(fname[len(DISP_GROUP_PREFIX):])
            except ValueError:
                print('Error in default fields: {} has invalid syntax.'
                      .format(fname))
                continue
            try:
                ContactGroup.objects.get(pk=groupid)
            except ContactGroup.DoesNotExist:
                print('Error in default fields: There is no group #{}.'
                      .format(groupid))
                continue
        elif fname.startswith(DISP_FIELD_PREFIX):
            try:
                fieldid = int(fname[len(DISP_FIELD_PREFIX):])
            except ValueError:
                print('Error in default fields: {} has invalid syntax.'
                      .format(fname))
                continue
            try:
                ContactField.objects.get(pk=fieldid)
            except ContactField.DoesNotExist:
                print('Error in default fields: There is no field #{}.'
                      .format(fieldid))
                continue
        else:
            print('Error in default fields: Invalid syntax in "{}".'
                  .format(fname))
            continue
        result.append(fname)
    if not result:
        result = [DISP_NAME]
    return result


def get_available_columns(user_id):
    '''
    Return all available columns on contact list, based on user permission.
    Used in column selection.
    '''
    result = [(DISP_NAME, _('Name')),
              ('busy', _('Busy'))]
    for cf in ContactField.objects.with_user_perms(user_id):
        result.append((DISP_FIELD_PREFIX+str(cf.id), cf.name))
    for cg in (
        ContactGroup.objects
                    .with_user_perms(user_id,
                                     wanted_flags=perms.SEE_MEMBERS,
                                     add_column=False)
                    .order_by('-date', 'name')):
        result.append((DISP_GROUP_PREFIX+str(cg.id), str(cg)))
    return result


class FieldSelectForm(forms.Form):
    '''
    Forms to select fields & groups to display. Only displays:
    - readable field
    - groups whose members can be viewed
    '''
    def __init__(self, user, *args, **kargs):
        super().__init__(*args, **kargs)
        self.fields['fields'] = forms.MultipleChoiceField(
            required=False, widget=FilteredSelectMultiple(_('Fields'), False),
            choices=get_available_columns(user.id))


def membership_to_text(contact_with_extra_fields, group_id):
    flags = getattr(contact_with_extra_fields,
                    'group_{}_flags'.format(group_id))
    if flags is None:
        flags = 0
    flags_inherited = getattr(contact_with_extra_fields,
                              'group_{}_inherited_flags'.format(group_id))
    if flags_inherited is None:
        flags_inherited = 0
    flags_ainherited = getattr(contact_with_extra_fields,
                               'group_{}_inherited_aflags'.format(group_id))
    if flags_ainherited is None:
        flags_ainherited = 0

    return perms.int_to_text(
        flags,
        (flags_inherited & ~perms.ADMIN_ALL)
        | (flags_ainherited & perms.ADMIN_ALL))


def membership_to_text_factory(group_id):
    return lambda contact_with_extra_fields: \
        membership_to_text(contact_with_extra_fields, group_id)


def membership_extended_widget(request, contact_with_extra_fields,
                               contact_group):
    flags = getattr(contact_with_extra_fields,
                    'group_{}_flags'.format(contact_group.id))
    msg_count = getattr(contact_with_extra_fields,
                        'group_{}_msgcount'.format(contact_group.id),
                        0)
    msg_count_unread = getattr(contact_with_extra_fields,
                               'group_{}_unreadcount'.format(contact_group.id),
                               0)
    return loader.render_to_string('membership_widget.html', {
        'cid': contact_with_extra_fields.id,
        'gid': contact_group.id,
        'virtual_group': contact_group.virtual,  # TODO: use this
        'membership_str': membership_to_text(contact_with_extra_fields,
                                             contact_group.id),
        'note': getattr(contact_with_extra_fields,
                        'group_{}_note'.format(contact_group.id)) or '',
        'membership': perms.int_to_flags(flags or 0),
        'cig_url': contact_group.get_absolute_url()
        + 'members/'
        + str(contact_with_extra_fields.id),
        'title': _('{contact} in group {group}').format(
            contact=contact_with_extra_fields,
            group=contact_group),
        'msg_count': msg_count,
        'msg_count_unread': msg_count_unread,
        })


def membership_extended_widget_factory(request, contact_group):
    return lambda contact_with_extra_fields: \
        membership_extended_widget(
            request, contact_with_extra_fields, contact_group)


def field_widget(contact_field, contact_with_extra_fields):
    attrib_name = DISP_FIELD_PREFIX + str(contact_field.id)
    raw_value = getattr(contact_with_extra_fields, attrib_name)
    if raw_value:
        html_value = contact_field.format_value_html(raw_value)
        return mark_safe(html_value)
    else:
        try:
            default_html_func = getattr(contact_field, 'default_value_html')
            html_value = default_html_func()
            return mark_safe(html_value)
        except AttributeError:
            return ''


def field_widget_factory(contact_field):
    return lambda contact_with_extra_fields: \
        field_widget(contact_field, contact_with_extra_fields)


class CustomColumnsFilter(filters.ListFilter):
    '''
    This is not really a filter. This acutally adds columns to the query.
    '''
    title = ugettext_lazy('Change columns')
    template = 'choose_columns.html'

    def __init__(self, request, params, model, view):
        super().__init__(request, params, model, view)
        params.pop('fields', None)
        params.pop('savecolumns', None)

    def has_output(self):
        return True  # This is required so that queryset is called

    def choices(self, cl):
        # This is an ugly hack to recover all the non-fields django-filters, to
        # build the select column base return url
        # We do it here because we need the cl.
        return cl.get_query_string({}, ['fields', 'savecolumns']),

    def queryset(self, request, q):
        return q

    def expected_parameters(self):
        return ['fields']


class BaseContactListView(NgwListView):
    '''
    Base view for contact list.
    That view should NOT be called directly since there is no user check.
    '''
    template_name = 'contact_list.html'
    list_filter = CustomColumnsFilter,

    actions = (
        'action_csv_export',  # See NgwListView
        'action_vcard_export',
        'action_bcc',
        'add_to_group',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_display = []

    def get_root_queryset(self):
        # Make sure self.contactgroup is defined:
        if not hasattr(self, 'contactgroup'):
            self.contactgroup = None

        q = ContactQuerySet(Contact._default_manager.model,
                            using=Contact._default_manager._db)

        current_cg = self.contactgroup

        list_display = []

        request = self.request
        user = request.user

        fields = request.GET.getlist('fields', None)
        if not fields:
            fields = get_default_columns(user)

        strfields = ','.join(fields)
        fields = strfields.split(',')

        if request.GET.get('savecolumns', False):
            user.set_fieldvalue(request, FIELD_COLUMNS, strfields)

        self.strfields = strfields
        self.fields = fields

        for prop in self.fields:
            if prop == 'name':
                if current_cg is not None and current_cg.date:
                    q.add_busy(current_cg.id)
                    q.add_birthday(current_cg)
                else:
                    q.add_busy()
                    q.add_birthday()
                list_display.append('name_with_relative_link')
            elif prop.startswith(DISP_GROUP_PREFIX):
                groupid = int(prop[len(DISP_GROUP_PREFIX):])

                if not perms.c_can_see_members_cg(user.id, groupid):
                    # just ignore groups that aren't allowed to be seen
                    continue

                q.add_group(groupid)

                cg = ContactGroup.objects.get(pk=groupid)

                # attribute_name = 'text_'+prop
                # setattr(self, attribute_name,
                #         membership_to_text_factory(groupid))
                # cols.append((cg.name, attribute_name, None))

                attribute_name = 'html_'+prop
                attribute = membership_extended_widget_factory(request, cg)
                attribute.short_description = str(cg)
                setattr(self, attribute_name, attribute)
                list_display.append(attribute_name)

                # cols.append(('group_{}_flags'.format(groupid),
                #              'group_{}_flags'.format(groupid), None))

            elif prop.startswith(DISP_FIELD_PREFIX):
                fieldid = prop[len(DISP_FIELD_PREFIX):]
                cf = ContactField.objects.get(pk=fieldid)

                if not perms.c_can_view_fields_cg(
                   user.id, cf.contact_group_id):
                    continue  # Just ignore fields that can't be seen

                q.add_field(fieldid)

                attribute_name = 'html_'+prop
                attribute = field_widget_factory(cf)
                attribute.short_description = cf.name
                attribute.admin_order_field = prop
                # TODO: Investigate why there are so many warnings:
                # attribute.allow_tags = True
                setattr(self, attribute_name, attribute)
                list_display.append(attribute_name)
            elif prop == 'busy':
                if current_cg is not None:
                    if current_cg.date:
                        q.add_busy(current_cg.id)
                        list_display.append('agenda')
            else:
                raise ValueError('Invalid field '+prop)

        if current_cg is not None:
            q.add_group(current_cg.id)
            q.add_messages(current_cg.id)
            self.group_status = membership_extended_widget_factory(
                request, current_cg)
            self.group_status.short_description = _('Status')
            list_display.append('group_status')
            # cols.append(('group_{}_flags'.format(current_cg.id),
            #              'group_{}_flags'.format(current_cg.id), None))
            # cols.append(('group_{}_inherited_flags'.format(current_cg.id),
            #              'group_{}_inherited_flags'.format(current_cg.id),
            #              None))
            # cols.append(('group_{}_inherited_aflags'.format(current_cg.id),
            #              'group_{}_inherited_aflags'.format(current_cg.id),
            #              None))

        self.list_display = list_display
        return q

    def get_search_results(self, request, queryset, search_term):
        '''
        Contact list views handle the search in a very special way.
        Returns a tuple containing a queryset to implement the search,
        and a boolean indicating if the results may contain duplicates.
        '''
        self.filter_str = search_term
        filter = parse_filterstring(search_term, request.user.id)
        self.filter_html = filter.to_html()
        return filter.apply_filter_to_query(queryset), False

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Contact list')
        context['objtype'] = Contact
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context.update(kwargs)
        result = super().get_context_data(**context)
        result['fields_form'] = FieldSelectForm(
            self.request.user, initial={'fields': self.fields})
        result['display'] = self.cl.params.get('display', 'mg')  # TODO
        result['filter'] = self.filter_str
        result['filter_html'] = self.filter_html
        result['reset_filter_link'] = self.cl.get_query_string({}, 'q')
        return result

    def name_with_relative_link(self, contact):
        current_cg = self.contactgroup
        flags = ''

        birthday = getattr(contact, 'birthday', None)
        if birthday is not None:
            birthday = date(*[int(c) for c in birthday.split('-')])
            if current_cg is not None and current_cg.date:
                event_length = current_cg.end_date - current_cg.date
                bseml = Config.get_birthday_show_event_max_length()
                if event_length < timedelta(days=bseml):  # interval means +1
                    # Next aniversary after event start date:
                    anniversary = date(
                        current_cg.date.year,
                        birthday.month,
                        birthday.day)
                    if anniversary < current_cg.date:
                        try:
                            anniversary = date(
                                anniversary.year + 1,
                                anniversary.month,
                                anniversary.day)
                        except ValueError:  # Febuary 29th
                            anniversary = date(
                                anniversary.year + 1,
                                anniversary.month,
                                anniversary.day - 1)
                    age = anniversary.year - birthday.year
                    # Translators: This is the next birthday strftime(3)
                    # format, detailled, but without the year
                    stranniv = anniversary.strftime(_('%A %B %e'))
                    hint = _('{age} years on {date}').format(
                            date=stranniv,
                            age=age)
                    flags += (' <span class=iconbirthday title="{}"></span>'
                              .format(html.escape(hint)))
            else:
                age = date.today().year - birthday.year
                hint = _('{age} years today').format(age=age)
                flags += ' <span class=iconbirthday title="{}"></span>'.format(
                        html.escape(hint))

        busy = getattr(contact, 'busy', None)
        if busy is not None and busy & perms.MEMBER:
            hint = _('That contact is busy. Click here for details.')
            if current_cg:
                excluded_gid = current_cg.id
            else:
                excluded_gid = GROUP_EVERYBODY
            flags += ' <span class=iconbusy title="{}" ' \
                'data-contactid="{}" data-groupid={}>' \
                '</span>'.format(
                    html.escape(hint),
                    contact.id,
                    excluded_gid)

        return html.format_html(
                mark_safe('<a href="{id}/"><b>{name}</a></b> {flags}'),
                id=contact.id,
                name=html.escape(contact.name),
                flags=mark_safe(flags),
                )
    name_with_relative_link.short_description = ugettext_lazy('Name')
    name_with_relative_link.admin_order_field = 'name'

    def agenda(self, contact):
        busy = getattr(contact, 'busy')
        if busy & perms.MEMBER:
            return _('Busy')
        elif busy & perms.INVITED:
            return _('Invited')
        elif busy == 0:
            return _('Available')
        else:
            return 'Error {}'.format(busy)
    agenda.short_description = ugettext_lazy('Agenda')
    agenda.admin_order_field = 'busy'

    def action_bcc(self, request, queryset):
        emails = []
        noemails = []
        for contact in queryset:
            # only the first email of each contact
            c_emails = contact.get_fieldvalues_by_type('EMAIL')
            if c_emails:
                emails.append(c_emails[0])
            else:
                noemails.append(contact.name)

        if emails:
            messages.add_message(
                request, messages.SUCCESS,
                mark_safe('<a href="{}">{}</a>'.format(
                          'mailto:?bcc=' + ','.join(emails),
                          _('List generated. Click here.'))))

        if noemails:
            messages.add_message(
                request, messages.WARNING,
                _('The following people do not have an email address: {}')
                .format(', '.join(noemails)))

        return None
    action_bcc.short_description = ugettext_lazy(
        "Send email locally (thunderbird or similar)")

    def action_vcard_export(self, request, queryset):
        result = ''
        for contact in queryset:
            result += contact.vcard()
        return HttpResponse(result, content_type='text/x-vcard')
    action_vcard_export.short_description = ugettext_lazy(
        "Vcard format export")

    def add_to_group(self, request, queryset):
        ids = request.POST.getlist('_selected_action')
        return HttpResponseRedirect(
            '/contacts/add_to_group?ids=' + ','.join(ids))
    add_to_group.short_description = ugettext_lazy("Add to another group")


class ContactListView(NgwUserAcl, BaseContactListView):
    '''
    Only show visible contacts
    '''
    def get_root_queryset(self):
        qs = super().get_root_queryset()

        qs.qry_from.append(
            'JOIN v_c_can_see_c ON contact.id=v_c_can_see_c.contact_id_2')
        qs.filter('v_c_can_see_c.contact_id_1 = {}'.format(
            self.request.user.id))

        return qs


#######################################################################
#
# Add to another group
#
#######################################################################


class GroupAddManyForm(forms.Form):
    ids = forms.CharField(widget=forms.widgets.HiddenInput)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['group'] = forms.ChoiceField(
            label=_('Target group'),
            choices=[
                ('', _('Choose a group')),
                (_('Permanent groups'), [
                    (group.id, group.name)
                    for group in ContactGroup
                    .objects
                    .filter(date__isnull=1)
                    .with_user_perms(user.id, perms.CHANGE_MEMBERS)
                    .order_by('name')]),
                (_('Events'), [
                    (group.id, str(group))
                    for group in ContactGroup
                    .objects
                    .filter(date__isnull=0)
                    .filter(perso_unavail=False)
                    .with_user_perms(user.id, perms.CHANGE_MEMBERS)
                    .order_by('-date', 'name')]),
                ],
            )
        self.fields['flags'] = FlagsField(label=ugettext_lazy('Membership'))

        contact_ids = kwargs['initial']['ids'].split(',')
        contacts = Contact.objects.filter(pk__in=contact_ids)
        contacts = contacts.extra(
            tables=('v_c_can_see_c',),
            where=(
                'v_c_can_see_c.contact_id_1={}'.format(self.user.id),
                'v_c_can_see_c.contact_id_2=contact.id'))
        self.fields['contacts'] = forms.MultipleChoiceField(
                label=_('Contacts'),
                choices=[(contact.id, contact.name) for contact in contacts],
                initial=contact_ids,
                widget=forms.widgets.CheckboxSelectMultiple(
                    attrs={'class': 'contactchoices'}))

    def clean(self):
        data = super().clean()
        if 'group' in data:
            flags = data['flags']
            if (flags & ~perms.ADMIN_ALL):
                group = get_object_or_404(
                    ContactGroup, pk=self.cleaned_data['group'])
                if group.virtual:
                    self.add_error('group', _(
                        'This is a virtual group. It cannot have members.'))
            if (flags & perms.ADMIN_ALL
               and not perms.c_operatorof_cg(self.user.id,
                                             self.cleaned_data['group'])):
                self.add_error('group', _(
                    'You need to be operator of the target group to add this'
                    ' kind of membership.'))

        if data['flags'] == 0:
            self.add_error('flags', _('You must select at least one mode'))
        return data

    def add_them(self, request):
        group_id = self.cleaned_data['group']
        target_group = get_object_or_404(ContactGroup, pk=group_id)

        contact_ids = self.cleaned_data['contacts']
        contacts = Contact.objects.filter(pk__in=contact_ids)

        # Check selected contacts are visible
        contacts = contacts.extra(
            tables=('v_c_can_see_c',),
            where=(
                'v_c_can_see_c.contact_id_1={}'.format(self.user.id),
                'v_c_can_see_c.contact_id_2=contact.id'))

        modes = ''
        intvalue = self.cleaned_data['flags']
        for flag, anint in perms.FLAGTOINT.items():
            if anint & intvalue:
                modes += '+' + flag

        target_group.set_member_n(request, contacts, modes)


class GroupAddManyView(NgwUserAcl, FormView):
    form_class = GroupAddManyForm
    template_name = 'group_add_contacts_to.html'

    def get_initial(self):
        if self.request.method == 'POST':
            querydict = self.request.POST
        else:
            querydict = self.request.GET
        return {'ids': querydict['ids']}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = {}
        if self.request.method == 'POST':
            querydict = self.request.POST
        else:
            querydict = self.request.GET
        ids = [int(id) for id in querydict['ids'].split(',')]
        context['title'] = _('Add {} contact(s) to a group').format(len(ids))
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(('add_to_group', _('add contacts to')))
        context['json_ids'] = mark_safe(json.dumps(ids))
        context.update(kwargs)
        return super().get_context_data(**context)

    def form_valid(self, form):
        form.add_them(self.request)
        self.gid = form.cleaned_data['group']
        self.success_form = form  # Used by get_success_url
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)

    def get_success_url(self):
        group_id = self.gid  # from form_valid()
        target_group = get_object_or_404(ContactGroup, pk=group_id)
        return target_group.get_absolute_url() + 'members/'


class ContactCheckAvailableView(NgwUserAcl, View):
    def post(self, request, *args, **kwargs):
        if self.request.method == 'POST':
            querydict = self.request.POST
        else:
            querydict = self.request.GET
        ids = querydict['ids']
        gid = querydict['group']
        ids = querydict['ids'].split(',')
        contacts = ContactQuerySet(Contact._default_manager.model,
                                   using=Contact._default_manager._db)
        contacts = contacts.filter(pk__in=ids)
        cg = ContactGroup.objects.get(pk=gid)
        resp_contacts = []
        if cg.is_event():
            contacts.add_busy(gid)
            for contact in contacts:
                resp_contacts.append({
                    'id': contact.id,
                    'busy': contact.busy or 0,
                    })
        else:
            for contact in contacts:
                resp_contacts.append({
                    'id': contact.id,
                    'busy': 0,
                    })
        jsonresponse = json.dumps({
            'event_busy': cg.busy,
            'contacts': resp_contacts,
            })
        return HttpResponse(jsonresponse, content_type='application/json')

    get = post


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
            if not self.contactgroup.userperms & perms.SEE_MEMBERS:
                raise PermissionDenied
        else:  # No group specified
            if cid == user.id:
                # The user can see himself
                pass
            elif perms.c_can_see_members_cg(user.id, GROUP_EVERYBODY):
                pass
            elif perms.c_can_see_c(user.id, cid):
                pass
            else:
                raise PermissionDenied

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        contact = get_object_or_404(Contact, pk=cid)

        rows = []
        for cf in contact.get_contactfields(self.request.user.id):
            try:
                cfv = ContactFieldValue.objects.get(
                    contact_id=cid, contact_field_id=cf.id)
                rows.append((cf.name, mark_safe(cfv.as_html())))
            except ContactFieldValue.DoesNotExist:
                pass  # ignore blank values

        context = {}
        context['title'] = _('Details for {}').format(contact)
        cg = self.contactgroup
        if cg:
            # context['title'] += ' in group '+str(cg)
            context['nav'] = cg.get_smart_navbar()
            context['nav'].add_component(('members', _('members')))
            context['active_submenu'] = 'members'
        else:
            context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['objtype'] = Contact
        context['contact'] = contact
        context['rows'] = rows
        context['group_user_perms'] = (
            ContactGroup.objects
                        .get(pk=GROUP_USER)
                        .get_contact_perms(self.request.user.id))
        context['group_user_ngw_perms'] = (
            ContactGroup.objects
                        .get(pk=GROUP_USER_NGW)
                        .get_contact_perms(self.request.user.id))

        context.update(kwargs)
        return super().get_context_data(**context)


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
            if not self.contactgroup.userperms & perms.SEE_MEMBERS:
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
        # TODO: We should also check the specific fields (email, address,
        # phone, ...) are readable by user

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
        user = kwargs.pop('user')  # contact making the query, not the edited
        super().__init__(*args, **kwargs)

        self.contactgroup = contactgroup

        if not perms.c_can_write_fields_cg(user.id, GROUP_EVERYBODY):
            del self.fields['name']  # = forms.CharField(label=_('Name'))
        if instance:
            cfields = instance.get_contactfields(user.id, writable=True)
            # Here we have all the writable fields, including the one from
            # other groups that the user can see
        elif contactgroup:
            contactgroupids = [
                g.id for g in contactgroup.get_self_and_supergroups()]
            cfields = (
                ContactField.objects
                            .filter(contact_group_id__in=contactgroupids)
                            .with_user_perms(user.id, writable=True))
            # Here we have the fields from contact_group and all its super
            # groups, IF user can write to them
        else:  # FIXME (new contact without any contactgroup)
            cfields = []

        # store dbfields
        self.cfields = cfields

        for cf in cfields:
            f = cf.get_form_fields()
            if f:
                try:
                    cfv = ContactFieldValue.objects.get(contact=instance,
                                                        contact_field=cf)
                    f.initial = cf.db_value_to_formfield_value(cfv.value)
                except ContactFieldValue.DoesNotExist:
                    initial = cf.default
                    if cf.type == FTYPE_DATE and initial == 'today':
                        initial = date.today()
                    f.initial = initial
                self.fields[str(cf.id)] = f

    def save(self, request):
        is_creation = self.instance.pk is None

        contact = super().save()
        data = self.cleaned_data

        # 1/ The contact name

        if is_creation:
            if not perms.c_can_write_fields_cg(
               request.user.id, GROUP_EVERYBODY):
                # If user can't write name, we have a problem creating a new
                # contact
                raise PermissionDenied

            log = Log(contact_id=request.user.id)
            log.action = LOG_ACTION_ADD
            log.target = 'Contact ' + str(contact.id)
            log.target_repr = 'Contact ' + contact.name
            log.save()

            log = Log(contact_id=request.user.id)
            log.action = LOG_ACTION_CHANGE
            log.target = 'Contact ' + str(contact.id)
            log.target_repr = 'Contact ' + contact.name
            log.property = 'Name'
            log.property_repr = 'Name'
            log.change = 'new value is ' + contact.name
            log = Log(request.user.id)

            cig = ContactInGroup(contact_id=contact.id,
                                 group_id=self.contactgroup.id)
            cig.flags = perms.MEMBER
            cig.save()
            # TODO: Log new cig
            # TODO: Check can add members in super groups
        else:
            if perms.c_can_write_fields_cg(request.user.id, GROUP_EVERYBODY):
                if contact.name != data['name']:
                    log = Log(contact_id=request.user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = 'Contact ' + str(contact.id)
                    log.target_repr = 'Contact ' + contact.name
                    log.property = 'Name'
                    log.property_repr = 'Name'
                    log.change = (
                        'change from ' + contact.name + ' to ' + data['name'])
                    log.save()

        # 2/ In ContactFields
        for cf in self.cfields:
            newvalue = data[str(cf.id)]
            if cf.type == FTYPE_PASSWORD and not newvalue:
                continue  # Ignore entries when password is empty (no change)
            # if cf.type == 'FILE' && newvalue == False:
            #    TODO: delete the old file
            if isinstance(newvalue, UploadedFile):
                newvalue = cf.save_file(contact.id, newvalue)
            if newvalue is not None:
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
            if not group.userperms & perms.SEE_MEMBERS:
                # CHANGE_MEMBERS is for adding new members, removing them
                # SEE_MEMBERS is enough here
                messages.add_message(
                    self.request, messages.ERROR,
                    _('You are not authorized to see members of that'
                      ' group.'))
                raise PermissionDenied
            if group.virtual:
                messages.add_message(
                    self.request, messages.ERROR,
                    _('This is a virtual group. It cannot have members.'))
                raise PermissionDenied
        else:
            cid = int(self.kwargs['cid'])  # ok to crash if create & no group
            if cid == user.id:
                # The user can change himself
                pass
            elif perms.c_can_see_c(user.id, cid):
                pass
            else:
                raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['contactgroup'] = self.contactgroup
        return kwargs

    def form_valid(self, form):
        request = self.request
        contact = form.save(request)

        messages.add_message(
            request, messages.SUCCESS,
            _('Contact {} has been saved.').format(contact.name))

        if self.pk_url_kwarg not in self.kwargs:  # new added instance
            base_url = '.'
        else:
            base_url = '..'
        if request.POST.get('_continue', None):
            return HttpResponseRedirect(
                base_url + '/' + str(contact.id) + '/edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect(base_url + '/add')
        else:
            return HttpResponseRedirect(base_url)

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing {}').format(self.object)
            id = self.object.id
        else:
            title = _('Adding a new {}').format(
                Contact.get_class_verbose_name())
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = Contact
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar()
            context['nav'].add_component(('members', _('members')))
        else:
            context['nav'] = Navbar(Contact.get_class_navcomponent())

        if id:
            context['nav'].add_component(self.object.get_navcomponent())
            context['nav'].add_component(('edit', _('edit')))
        else:
            context['nav'].add_component(('add', _('add')))

        context.update(kwargs)
        return super().get_context_data(**context)


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
    # TODO: Use admin SetPasswordForm ?
    class Meta:
        model = Contact
        fields = []
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        new_password = self.cleaned_data.get('new_password', '')
        if (new_password
           != self.cleaned_data.get('confirm_password', '')):
            raise forms.ValidationError(_('The passwords must match!'))
        password_validation.validate_password(new_password)
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
            _('Password has been changed successfully!'))
        if self.contactgroup:
            return HttpResponseRedirect(
                self.contactgroup.get_absolute_url()
                + 'members/'
                + str(contact.id) + '/')
        else:
            return HttpResponseRedirect(contact.get_absolute_url())

    def get_context_data(self, **kwargs):
        contact = self.object
        context = {}
        context['title'] = _('Change password')
        context['contact'] = contact
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar()
            context['nav'].add_component(('members', _('members')))
        else:
            context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['nav'].add_component(('password', _('password')))
        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Contact change password hook
#
#######################################################################

# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# class HookPasswordView(View):
#     '''
#     This view allow a user to change his password through a post.
#     That view allow other modules to change the central password.
#     '''
#     @method_decorator(csrf_exempt)
#     def dispatch(self, request, *args, **kwargs):
#         username = request.META['REMOTE_USER']  # Apache external auth
#         request.user = Contact.objects.get_by_natural_key(username)
#         return super().dispatch(request, *args, **kwargs)
#
#     def post(self, request):
#         # TODO check password strength
#         newpassword_plain = request.POST['password']
#         request.user.set_password(newpassword_plain, request=request)
#         return HttpResponse('OK')


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
            context['nav'] = self.contactgroup.get_smart_navbar()
            context['nav'].add_component(('members', _('members')))
            context['nav'].add_component(('delete', _('delete')))
        context.update(kwargs)
        return super().get_context_data(**context)


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
        filter_list = contact.get_saved_filters()
        filter_list.append({'name': _('No name'), 'filter_string': filter_str})
        contact.set_saved_filters(request, filter_list)
        messages.add_message(request, messages.SUCCESS,
                             _('Filter has been added successfully!'))
        return HttpResponseRedirect(
            reverse('filter_edit', args=(cid, len(filter_list)-1)))


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
        filter_list = contact.get_saved_filters()
        filters = [finfo['name'] for finfo in filter_list]
        context = {}
        context['title'] = _('User custom filters')
        context['contact'] = contact
        context['filters'] = filters
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['nav'].add_component(('filters', _('custom filters')))

        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Rename custom filter
#
#######################################################################


class FilterEditForm(forms.Form):
    name = forms.CharField(label=_('Name'), max_length=50)
    shared = forms.BooleanField(
        required=False,
        label=ugettext_lazy('Shared'),
        help_text=ugettext_lazy(
            'Allow other users to use that filter.'))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        contact = kwargs.pop('contact')
        fid = int(kwargs.pop('fid'))
        super().__init__(*args, **kwargs)

        self.contact = contact
        self.fid = fid
        self.filter_list = contact.get_saved_filters()
        try:
            filterinfo = self.filter_list[fid]
        except (IndexError, ValueError):
            raise Http404
        self.fields['name'].initial = filterinfo['name']
        self.fields['shared'].initial = filterinfo.get('shared', False)
        filterstr = filterinfo['filter_string']
        try:
            self.filter_html = parse_filterstring(filterstr, user.id).to_html()
        except PermissionDenied:
            self.filter_html = _(
                "[Permission was denied to explain that filter. You probably"
                " don't have access to the fields / group names it is using.]"
                "<br>Raw filter={}").format(filterstr)
        except ContactField.DoesNotExist:
            self.filter_html = _(
                "[This filter uses a field that doesn't exist anymore.]")

    def save(self, request):
        filter_list = self.filter_list
        filter_list[self.fid] = {
            'name': self.cleaned_data['name'],
            'shared': self.cleaned_data['shared'],
            'filter_string': filter_list[self.fid]['filter_string']}
        self.contact.set_saved_filters(request, filter_list)


class FilterEditView(NgwUserAcl, FormView):
    form_class = FilterEditForm
    template_name = 'filter_form.html'

    def check_perm_user(self, user):
        if int(self.kwargs['cid']) == user.id:
            return  # Ok for oneself
        if not perms.c_can_write_fields_cg(user.id, GROUP_USER_NGW):
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['contact'] = get_object_or_404(
            Contact, pk=int(self.kwargs['cid']))
        kwargs['fid'] = self.kwargs['fid']
        return kwargs

    def get_context_data(self, **kwargs):
        contact = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        context = {}
        context['title'] = _('User custom filter renaming')
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['nav'].add_component(('filters', _('custom filters')))
        # context['nav'].add_component(
        #     (self.kwargs['fid'], self.form.filtername))
        context.update(kwargs)
        return super().get_context_data(**context)

    def form_valid(self, form):
        form.save(self.request)
        messages.add_message(self.request, messages.SUCCESS,
                             _('Filter has been renamed.'))
        return super().form_valid(form)

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
        filter_list = contact.get_saved_filters()
        del filter_list[fid]
        contact.set_saved_filters(request, filter_list)
        messages.add_message(request, messages.SUCCESS,
                             _('Filter has been deleted.'))
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
        # FIXME Problem when changing the default group for another user:
        user = contact
        super().__init__(*args, **kwargs)
        available_groups = (
            ContactGroup.objects
                        .with_user_perms(user.id, wanted_flags=perms.SEE_CG)
                        .with_member(contact.id)
                        .filter(date__isnull=True))
        choices = (
            [('', _('Create new personnal group'))]
            + [(cg.id, cg.name) for cg in available_groups
               if not cg.date and perms.c_can_see_cg(contact.id, cg.id)])
        default_group = contact.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
        self.fields['default_group'] = forms.ChoiceField(
            label=_('Default group'), choices=choices, required=False,
            initial=default_group)

    def save(self, request):
        default_group = self.cleaned_data['default_group']
        contact = self.instance
        if not default_group:
            cg = ContactGroup(
                name=_('Group of {}').format(contact.name),
                description=_('This is the default group of {}').format(
                    contact.name),
                )
            cg.save()
            cg.check_static_folder_created()

            cig = ContactInGroup(
                contact=contact,
                group_id=cg.id,
                flags=perms.MEMBER | perms.ADMIN_ALL,
                )
            cig.save()
            messages.add_message(
                request, messages.SUCCESS,
                _('Personnal group created.'))
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
        messages.add_message(
            self.request, messages.SUCCESS,
            _('Default group has been changed successfully.'))
        return HttpResponseRedirect(contact.get_absolute_url())

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        contact = get_object_or_404(Contact, pk=cid)
        context = {}
        context['title'] = _('User default group')
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['nav'].add_component(('default_group', _('default group')))

        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Contact Calendar
#
#######################################################################

class ContactCalendarView(NgwUserAcl, TemplateView):
    template_name = 'calendar.html'

    def check_perm_user(self, user):
        if int(self.kwargs.get('cid', 0)) == user.id:
            return  # Ok for oneself
        if not user.is_admin():
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        contact = get_object_or_404(Contact, pk=cid)

        context = {}
        context['title'] = _("{name}'s Calendar").format(
            name=contact.name)
        context['nav'] = Navbar(Contact.get_class_navcomponent())
        context['nav'].add_component(contact.get_navcomponent())
        context['nav'].add_component(('calendar', _('calendar')))
        context['weekdaystart'] = formats.get_format('FIRST_DAY_OF_WEEK')
        context['contactid'] = cid
        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Contact unavail calendar: json
#
#######################################################################

class ContactUnavailDetailView(NgwUserAcl, View):
    def get(self, request, cid, dfrom=None, dto=None, gid=None):

        contact = Contact.objects.get(pk=cid)
        if gid is not None:
            gid = int(gid)
            assert dfrom is None and dto is None, \
                "dfrom+dto and gid parameters are mutualy exclusive"
            group = ContactGroup.objects.get(pk=gid)
            user = self.request.user
            if not perms.c_can_see_cg(user.id, group.id):
                raise PermissionDenied
            dfrom = group.date
            dto = group.end_date
        else:
            if dfrom is not None:
                dfrom = datetime.strptime(dfrom, '%Y-%m-%d')
            if dto is not None:
                dto = datetime.strptime(dto, '%Y-%m-%d')
        if dfrom is None:
            dfrom = date.today()
        if dto is None:
            dto = date.today()

        # Look for "busy" events that contact is member of
        # even those that are secrets
        # Add permissions columns for the requester
        events = (
            ContactGroup.objects
            .with_user_perms(
                request.user.id,
                wanted_flags=None,
                add_column=True)
            .with_member(contact.id)
            .filter(busy=True)
            .filter(
                # start within boundaries:
                Q(date__gte=dfrom, date__lte=dto)
                # or end within boundaries:
                | Q(end_date__gte=dfrom, end_date__lte=dto)
                # or start before and end after (this is a long event):
                | Q(date__lte=dfrom, end_date__gte=dto))
            )

        visible_events = {}
        invisible_events = False
        for e in events:
            if e.id == gid:
                continue  # Ignore self
            if e.userperms & perms.SEE_MEMBERS:
                visible_events[e.id] = e
            else:
                invisible_events = True
        result = {
                'contact': contact.id,
                'from': dfrom.strftime('%Y-%m-%d'),
                'to': dto.strftime('%Y-%m-%d'),
                'result': loader.render_to_string(
                    'contact_unavail_detail.html', {
                        'visible_events': visible_events,
                        'invisible_events': invisible_events,
                    }),
                }
        jsonresponse = json.dumps(result)
        return HttpResponse(jsonresponse, content_type='application/json')
