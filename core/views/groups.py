# -*- encoding: utf-8 -*-
'''
ContactGroup managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from datetime import date, datetime, timedelta
import json
from decoratedstr import remove_decoration
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.utils.safestring import mark_safe
from django.utils import html
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils import formats
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django import forms
from django.views.generic import TemplateView
from django.contrib import messages
from ngw.core.models import (
    GROUP_EVERYBODY, GROUP_USER_NGW,
    FIELD_DEFAULT_GROUP,
    CIGFLAG_MEMBER, CIGFLAG_INVITED, CIGFLAG_DECLINED,
    ADMIN_CIGFLAGS,
    TRANS_CIGFLAG_CODE2INT, TRANS_CIGFLAG_CODE2TXT,
    Config, Contact, ContactMsg, ContactGroup, ContactInGroup, GroupInGroup,
    GroupManageGroup,
    hooks)
from ngw.core.widgets import NgwCalendarWidget, FilterMultipleSelectWidget
from ngw.core.nav import Navbar
from ngw.core.contactsearch import parse_filterstring
from ngw.core import perms
from ngw.core.views.contacts import BaseContactListView, BaseCsvContactListView, BaseVcardContactListView
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import generic_delete, NgwUserMixin, NgwListView


#######################################################################
#
# Groups list
#
#######################################################################

def get_UContactGroup(userid):
    '''
    This make a user specific ContactGroup model proxy
    with additionnal method for filtering out hidden objects
    '''
    LIST_PREVIEW_LEN = 5
    def _truncate_list(lst, maxlen=LIST_PREVIEW_LEN):
        'Utility function to truncate text longer that LIST_PREVIEW_LEN'
        if len(lst) > maxlen:
            return lst[:maxlen] + ['…']
        return lst
    class UContactGroup(ContactGroup):
        'User specific ContactGroup proxy'
        class Meta(ContactGroup.Meta):
            proxy = True
        def visible_direct_supergroups_5(self):
            return ', '.join(_truncate_list([sg.name_with_date() for sg in self.get_direct_supergroups().extra(where=['perm_c_can_see_cg(%s, id)' % userid])[:LIST_PREVIEW_LEN+1]]))
        def visible_direct_subgroups_5(self):
            return ', '.join(_truncate_list([sg.name_with_date() for sg in self.get_direct_subgroups().extra(where=['perm_c_can_see_cg(%s, id)' % userid])[:LIST_PREVIEW_LEN+1]]))
        def rendered_fields(self):
            if self.field_group:
                fields = self.contactfield_set.all()
                if fields:
                    return ', '.join(['<a href="' + f.get_absolute_url() + '">'+html.escape(f.name) + '</a>' for f in fields])
                else:
                    return 'Yes (but none yet)'
            else:
                return 'No'
        def visible_member_count(self):
            # This is totally ineficient
            if perms.c_can_see_members_cg(userid, self.id):
                return self.get_members_count()
            else:
                return 'Not available'
    return UContactGroup


class ContactGroupListView(NgwUserMixin, NgwListView):
    cols = [
        ( _('Name'), None, 'name', 'name' ),
        ( _('Description'), None, 'description_not_too_long', 'description' ),
        #( _('Contact fields'), None, 'rendered_fields', 'field_group' ),
        ( _('Super groups'), None, 'visible_direct_supergroups_5', None ),
        ( _('Sub groups'), None, 'visible_direct_subgroups_5', None ),
        #( _('Budget\u00a0code'), None, 'budget_code', 'budget_code' ),
        #( _('Members'), None, 'visible_member_count', None ),
        #( _('System\u00a0locked'), None, 'system', 'system' ),
    ]

    def get_root_queryset(self):
        UContactGroup = get_UContactGroup(self.request.user.id)

        return UContactGroup.objects.filter(date=None).extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % self.request.user.id])


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Select a contact group')
        context['objtype'] = ContactGroup
        context['nav'] = Navbar(ContactGroup.get_class_navcomponent())

        context.update(kwargs)
        return super(ContactGroupListView, self).get_context_data(**context)


#######################################################################
#
# Event list
#
#######################################################################

class WeekDate:
    def __init__(self, date, events):
        self.date = date
        self.events = events

    def days(self):
        for i in range(7):
            dt = self.date + timedelta(days=i)
            events = self.events.get(dt, [])
            yield dt, events

class YearMonthCal:
    def __init__(self, year, month, events):
        self.year = year
        self.month = month
        self.events = events

    def prev_month(self):
        year, month = self.year, self.month
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        return '%s-%s' % (year, month)

    def next_month(self):
        year, month = self.year, self.month
        month += 1
        if month > 12:
            month = 1
            year += 1
        return '%s-%s' % (year, month)

    def prev_year(self):
        return '%s-%s' % (self.year-1, self.month)

    def next_year(self):
        return '%s-%s' % (self.year+1, self.month)

    def weeks(self):
        first_day_of_week = formats.get_format('FIRST_DAY_OF_WEEK')

        first_day_of_month = date(self.year, self.month, 1)
        first_day_of_month_isocal = first_day_of_month.isocalendar()
        #firstweeknumber = first_day_of_month_isocal[1]

        first_day_of_month_isoweekday = first_day_of_month_isocal[2] # 1=monday, 7=sunday
        first_week_date = first_day_of_month - timedelta(days=(first_day_of_month_isoweekday-first_day_of_week)%7)

        nextyear, nextmonth = self.year, self.month
        nextmonth += 1
        if nextmonth > 12:
            nextmonth = 1
            nextyear += 1
        next_month_start = date(nextyear, nextmonth, 1)

        dt = first_week_date
        while dt < next_month_start:
            yield WeekDate(dt, self.events)
            dt += timedelta(days=7)

    def first_day(self):
        return datetime(self.year, self.month, 1)


class EventListView(NgwUserMixin, TemplateView):
    '''
    Calendar with all the user-visible events of selected month
    '''

    template_name = 'event_list.html'

    def get_context_data(self, **kwargs):
        request = self.request

        dt = request.REQUEST.get('dt', None)
        year = month = None
        if dt is not None:
            try:
                year, month = dt.split('-')
                year = int(year)
                month = int(month)
            except ValueError:
                year = month = None
            else:
                if year < 2000 or year > 2100 \
                 or month < 1 or month > 12:
                    year = month = None

        if year is None or month is None:
            now = datetime.utcnow()
            month = now.month
            year = now.year

        min_date = datetime(year, month, 1) - timedelta(days=6)
        min_date = min_date.strftime('%Y-%m-%d')
        max_date = datetime(year, month, 1) + timedelta(days=31+6)
        max_date = max_date.strftime('%Y-%m-%d')

        q = ContactGroup.objects.filter(date__gte=min_date, date__lte=max_date).extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])

        month_events = {}
        for cg in q:
            if cg.date not in month_events:
                month_events[cg.date] = []
            month_events[cg.date].append(cg)

        context = {}
        context['title'] = _('Events')
        context['nav'] = Navbar(('events', _('events')))
        context['year_month'] = YearMonthCal(year, month, month_events)
        context['today'] = date.today()

        context.update(kwargs)
        return super(EventListView, self).get_context_data(**context)



#######################################################################
#
# Group index (redirect)
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_index(request, gid):
    '''
    Redirect to members list, if allowed.
    Otherwise, try to find some authorized page.
    '''
    gid = gid and int(gid) or None
    cg = get_object_or_404(ContactGroup, pk=gid)
    if perms.c_can_see_members_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'members/')
    if perms.c_can_see_news_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'news/')
    if perms.c_can_see_files_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'files/')
    if perms.c_can_view_msgs_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'messages/?&_order=-0')
    raise PermissionDenied


#######################################################################
#
# Member list / email / csv / vcard
#
#######################################################################

class GroupMemberListView(BaseContactListView):
    template_name = 'group_detail.html'

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        user_id = request.user.id
        if not perms.c_can_see_members_cg(user_id, self.kwargs['gid']):
            raise PermissionDenied
        return super(GroupMemberListView, self).dispatch(request, *args, **kwargs)


    def get_root_queryset(self):
        q = super(GroupMemberListView, self).get_root_queryset()

        cg = self.cg

        display = self.request.REQUEST.get('display', None)
        if display is None:
            display = cg.get_default_display()
        self.display = display

        wanted_flags = 0
        if 'm' in display:
            wanted_flags |= CIGFLAG_MEMBER
        if 'i' in display:
            wanted_flags |= CIGFLAG_INVITED
        if 'd' in display:
            wanted_flags |= CIGFLAG_DECLINED
        if 'a' in display:
            wanted_flags |= ADMIN_CIGFLAGS

        if not wanted_flags:
            # Show nothing
            q = q.filter('FALSE')
        elif not 'g' in display:
            # Not interested in inheritance:
            q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%s AND flags & %s <> 0)'
                % (cg.id, wanted_flags))
        else:
            # We want inherited people
            or_conditions = []
            # The local flags
            or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%s AND flags & %s <> 0)'
                % (cg.id, wanted_flags))
            # The inherited memberships/invited/declined
            or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)'
                % (cg.id, wanted_flags & (CIGFLAG_MEMBER|CIGFLAG_INVITED|CIGFLAG_DECLINED)))
            # The inherited admins
            or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(father_id) FROM group_manage_group WHERE subgroup_id=%s AND group_manage_group.flags & %s <> 0) AND contact_in_group.flags & 1 <> 0)'
                % (cg.id, wanted_flags & ADMIN_CIGFLAGS))

            q = q.filter('(' + ') OR ('.join(or_conditions) + ')')

        self.baseurl += '&display=' + self.display
        return q


    def get_context_data(self, **kwargs):
        cg = self.cg
        context = {}
        context['title'] = _('Contacts of group %s') % cg.name_with_date()

        context['nav'] = cg.get_smart_navbar() \
                           .add_component(('members', _('members')))
        context['active_submenu'] = 'members'

        context['display'] = self.display

        context.update(kwargs)
        return super(GroupMemberListView, self).get_context_data(**context)


class CsvGroupMemberListView(GroupMemberListView, BaseCsvContactListView):
    pass


class VcardGroupMemberListView(GroupMemberListView, BaseVcardContactListView):
    pass


class EmailGroupMemberListView(GroupMemberListView):
    template_name = 'emails.html'

    def get_context_data(self, **kwargs):
        #TODO: field permission validation
        cg = self.cg
        emails = []
        noemails = []
        for contact in self.get_queryset():
            c_emails = contact.get_fieldvalues_by_type('EMAIL')
            if c_emails:
                emails.append((contact.id, contact, c_emails[0])) # only the first email
            else:
                noemails.append(contact)
        emails.sort(key=lambda x: remove_decoration(x[1].name.lower()))

        context = {}
        context['title'] = _('Emails for %s') % cg.name
        context['emails'] = emails
        context['noemails'] = noemails
        context['nav'] = cg.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component(('emails', _('emails')))
        context['active_submenu'] = 'members'

        context.update(kwargs)
        return super(EmailGroupMemberListView, self).get_context_data(**context)


    def post(self, request, *args, **kwargs):
        # Note that dispatch is already checking GROUP_USER_NGW membership
        # and c_can_see_members_cg
        view_params = self.kwargs
        gid =  view_params['gid']
        cg = get_object_or_404(ContactGroup, pk=view_params['gid'])

        if not perms.c_can_write_msgs_cg(request.user.id, gid):
            raise PermissionDenied
        message = request.POST.get('message', '')
        language = translation.get_language()
        for param in request.POST:
            if not param.startswith('contact_'):
                continue
            contact_id = param[len('contact_'):]
            contact = get_object_or_404(Contact, pk=contact_id)
            contact_msg = ContactMsg(contact=contact, group=cg)
            contact_msg.send_date = datetime.utcnow()
            contact_msg.text = message
            contact_msg.sync_info = json.dumps({'language': language})
            contact_msg.save()
            messages.add_message(request, messages.SUCCESS, _('Message stored.'))
        return HttpResponseRedirect(cg.get_absolute_url())


#######################################################################
#
# Add to another group
#
#######################################################################


class GroupAddManyView(GroupMemberListView):
    template_name = 'group_add_contacts_to.html'

    def get_context_data(self, **kwargs):
        cg = self.cg
        context = {}
        context['title'] = _('Add contacts to a group')
        context['nav'] = cg.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component(('add_contacts_to', _('add contacts to')))
        context['groups'] = ContactGroup.objects.extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % self.request.user.id]).order_by('-date', 'name')
        context['active_submenu'] = 'members'
        context.update(kwargs)
        return super(GroupAddManyView, self).get_context_data(**context)


    def post(self, request, *args, **kwargs):
        # Note that dispatch is already checking GROUP_USER_NGW membership
        # and c_can_see_members_cg
        view_params = self.kwargs
        gid =  view_params['gid']
        cg = get_object_or_404(ContactGroup, pk=view_params['gid'])

        target_gid = request.POST['group']
        if not target_gid:
            messages.add_message(request, messages.ERROR, _('You must select a target group'))
            return self.get(self, request, *args, **kwargs)

        if not perms.c_can_change_members_cg(request.user.id, target_gid):
            raise PermissionDenied
        target_group = get_object_or_404(ContactGroup, pk=target_gid)

        modes = ''
        for flag, propname in TRANS_CIGFLAG_CODE2TXT.items():
            field_name = 'membership_' + propname
            if request.REQUEST.get(field_name, False):
                modes += '+' + flag
                intflag = TRANS_CIGFLAG_CODE2INT[flag]
                if intflag & ADMIN_CIGFLAGS and not perms.c_operatorof_cg(request.user.id, target_gid):
                    # Only operator can grant permissions
                    raise PermissionDenied
        if not modes:
            raise ValueError(_('You must select at least one mode'))

        contacts = []
        for param in request.POST:
            if not param.startswith('contact_'):
                continue
            contact_id = param[len('contact_'):]
            #TODO: Check contact_id can be seen by user
            contact = get_object_or_404(Contact, pk=contact_id)
            contacts.append(contact)
        target_group.set_member_n(request, contacts, modes)

        return HttpResponseRedirect(target_group.get_absolute_url())


#######################################################################
#
# Group edit
#
#######################################################################

class ContactGroupForm(forms.Form):
    name = forms.CharField(label=_('Name'),
        max_length=255)
    description = forms.CharField(label=_('Description'),
        required=False, widget=forms.Textarea)
    date = forms.DateField(label=_('Date'),
        required=False,
        help_text=_('Leave empty for permanent groups.'), widget=NgwCalendarWidget(attrs={'class':'vDateField'}))
    budget_code = forms.CharField(label=_('Budget code'),
        required=False, max_length=10)
    sticky = forms.BooleanField(label=_('Sticky'),
        required=False,
        help_text=_('If set, automatic membership because of subgroups becomes permanent. Use with caution.'))
    field_group = forms.BooleanField(label=_('Field group'),
        required=False,
        help_text=_('Does that group yield specific fields to its members?'))
    mailman_address = forms.CharField(label=_('Mailman address'),
        required=False, max_length=255,
        help_text=_('Mailing list address, if the group is linked to a mailing list.'))
    direct_supergroups = forms.MultipleChoiceField(label=_('Direct supergroups'),
        required=False,
        help_text=_('Members will automatically be granted membership in these groups.'), widget=FilterMultipleSelectWidget('groups', False))
    operator_groups = forms.MultipleChoiceField(label=_('Operator groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted administrative priviledges.'),
        widget=FilterMultipleSelectWidget('groups', False))
    viewer_groups = forms.MultipleChoiceField(label=_('Viewer groups'),
        required=False,
        help_text=_("Members of these groups will automatically be granted viewer priviledges: They can see everything but can't change things."),
        widget=FilterMultipleSelectWidget('groups', False))
    see_group_groups = forms.MultipleChoiceField(label=_('Existence seer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to know that current group exists.'),
        widget=FilterMultipleSelectWidget('groups', False))
    change_group_groups = forms.MultipleChoiceField(label=_('Editor groups'),
        required=False, 
        help_text=_('Members of these groups will automatically be granted priviledge to change/delete the current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    see_members_groups = forms.MultipleChoiceField(label=_('Members seer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to see the list of members.'),
        widget=FilterMultipleSelectWidget('groups', False))
    change_members_groups = forms.MultipleChoiceField(label=_('Members changing groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to change members of current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_fields_groups = forms.MultipleChoiceField(label=_('Fields viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to read the fields associated to current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_fields_groups = forms.MultipleChoiceField(label=_('Fields writer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to write to fields associated to current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_news_groups = forms.MultipleChoiceField(label=_('News viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permisson to read news of current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_news_groups = forms.MultipleChoiceField(label=_('News writer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to write news in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_files_groups = forms.MultipleChoiceField(label=_('File viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to view uploaded files in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_files_groups = forms.MultipleChoiceField(label=_('File uploader groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to upload files.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_msgs_groups = forms.MultipleChoiceField(label=_('Message viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to view messages in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_msgs_groups = forms.MultipleChoiceField(label=_('Message sender groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to send messages.'),
        widget=FilterMultipleSelectWidget('groups', False))

    def __init__(self, for_user, *args, **kargs):
        super(ContactGroupForm, self).__init__(*args, **kargs)
        visible_groups_choices = [(g.id, g.name_with_date()) for g in ContactGroup.objects.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % for_user]).order_by('-date', 'name')]
        self.fields['direct_supergroups'].choices = visible_groups_choices
        for flag in 'oveEcCfFnNuUxX':
            field_name = TRANS_CIGFLAG_CODE2TXT[flag] + '_groups'
            self.fields[field_name].choices = visible_groups_choices



@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_edit(request, id):
    id = id and int(id) or None
    objtype = ContactGroup
    if id:
        cg = get_object_or_404(ContactGroup, pk=id)
        if not perms.c_can_change_cg(request.user.id, id):
            raise PermissionDenied
        title = _('Editing %s') % cg.name_with_date()
    else:
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactGroupForm(request.user.id, request.POST)
        if form.is_valid():
            # record the values

            data = form.clean()
            if not id:
                cg = ContactGroup()
            cg.name = data['name']
            cg.description = data['description']
            cg.field_group = data['field_group']
            cg.sticky = data['sticky']
            cg.date = data['date']
            cg.budget_code = data['budget_code']
            cg.mailman_address = data['mailman_address']
            cg.save()

            # Update the super groups
            old_direct_supergroups_ids = set(cg.get_visible_direct_supergroups_ids(request.user.id))
            new_direct_supergroups_id = set([int(i) for i in data['direct_supergroups']])
            if cg.id != GROUP_EVERYBODY and not new_direct_supergroups_id:
                new_direct_supergroups_id = {GROUP_EVERYBODY}

            supergroup_added = new_direct_supergroups_id - old_direct_supergroups_ids
            supergroup_removed = old_direct_supergroups_ids - new_direct_supergroups_id

            print('supergroup_added=', supergroup_added)
            print('supergroup_removed=', supergroup_removed)
            for sgid in supergroup_added:
                GroupInGroup(father_id=sgid, subgroup_id=cg.id).save()
            for sgid in supergroup_removed:
                GroupInGroup.objects.get(father_id=sgid, subgroup_id=cg.id).delete()

            # Update the administrative groups
            for flag in 'oveEcCfFnNuUxX':
                field_name = TRANS_CIGFLAG_CODE2TXT[flag] + '_groups'
                intflag = TRANS_CIGFLAG_CODE2INT[flag]
                old_groups_ids = set(cg.get_visible_mananger_groups_ids(request.user.id, intflag))
                new_groups_ids = set([int(ogid) for ogid in data[field_name]])
                groups_added = new_groups_ids - old_groups_ids
                groups_removed = old_groups_ids - new_groups_ids
                print('flag', flag, 'groups_added=', groups_added)
                print('flag', flag, 'groups_removed=', groups_removed)
                if id and (groups_added or groups_removed) and not perms.c_operatorof_cg(request.user.id, id):
                    # Only operators can change permissions
                    raise PermissionDenied
                for ogid in groups_added:
                    try:
                        gmg = GroupManageGroup.objects.get(father_id=ogid, subgroup_id=cg.id)
                    except GroupManageGroup.DoesNotExist:
                        gmg = GroupManageGroup(father_id=ogid, subgroup_id=cg.id, flags=0)
                    gmg.flags |= intflag
                    gmg.save()
                for ogid in groups_removed:
                    gmg = GroupManageGroup.objects.get(father_id=ogid, subgroup_id=cg.id)
                    gmg.flags &= ~ intflag
                    if gmg.flags:
                        gmg.save()
                    else:
                        gmg.delete()

            messages.add_message(request, messages.SUCCESS, _('Group %s has been changed sucessfully!') % cg.name_with_date())

            cg.check_static_folder_created()
            Contact.check_login_created(request) # subgroups change

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cg.get_absolute_url() + 'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cg.get_class_absolute_url() + 'add')
            else:
                return HttpResponseRedirect(cg.get_absolute_url())

    else: # GET
        if id:
            initialdata = {
                'name': cg.name,
                'description': cg.description,
                'field_group': cg.field_group,
                'sticky': cg.sticky,
                'date': cg.date,
                'budget_code': cg.budget_code,
                'mailman_address': cg.mailman_address,
                'direct_supergroups': cg.get_visible_direct_supergroups_ids(request.user.id),
            }
            for flag in 'ovveEcCfFnNuUxX':
                field_name = TRANS_CIGFLAG_CODE2TXT[flag] + '_groups'
                intflag = TRANS_CIGFLAG_CODE2INT[flag]
                initialdata[field_name] = cg.get_visible_mananger_groups_ids(request.user.id, intflag)
        else: # add new one
            default_group_id = request.user.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
            if not default_group_id:
                messages.add_message(request, messages.WARNING,
                    _('You must define a default group before you can create a group.'))
                return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
            default_group_id = int(default_group_id)
            if not request.user.is_member_of(default_group_id):
                messages.add_message(request, messages.WARNING,
                    _('You no longer are member of your default group. Please define a new default group.'))
                return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
            if not perms.c_can_see_cg(request.user.id, default_group_id):
                messages.add_message(request, messages.WARNING,
                    _('You no longer are authorized to see your default group. Please define a new default group.'))
                return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
            initialdata = {
                TRANS_CIGFLAG_CODE2TXT['o'] + '_groups': (default_group_id,)}
        form = ContactGroupForm(request.user.id, initial=initialdata)
    context = {}
    context['title'] = title
    context['id'] = id
    context['objtype'] = objtype
    context['form'] = form
    if id:
        context['object'] = cg
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('edit', _('edit')))
    else:
        context['nav'] = Navbar(ContactGroup.get_class_navcomponent()) \
                         .add_component(('add', _('add')))

    return render_to_response('edit.html', context, RequestContext(request))


#######################################################################
#
# Group delete
#
#######################################################################

def on_contactgroup_delete(cg):
    """
    All subgroups will now have their fathers' fathers as direct fathers
    """
    supergroups_ids = set(cg.get_direct_supergroups_ids())
    for subcg in cg.get_direct_subgroups():
        sub_super = set(subcg.get_direct_supergroups_ids())
        #print(repr(subcg), "had these fathers:", sub_super)
        sub_super = sub_super | supergroups_ids - {cg.id}
        if not sub_super:
            sub_super = {GROUP_EVERYBODY}
        #print(repr(subcg), "new fathers:", sub_super)
        subcg.set_direct_supergroups_ids(sub_super)
        #print(repr(subcg), "new fathers double check:", subcg.get_direct_supergroups_ids())
    # TODO: delete static folder


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_delete(request, id):
    id = id and int(id) or None
    if not perms.c_can_change_cg(request.user.id, id):
        raise PermissionDenied
    obj = get_object_or_404(ContactGroup, pk=id)
    if obj.date:
        next_url = reverse('event_list')
    else:
        next_url = reverse('group_list')
    if obj.system:
        messages.add_message(request, messages.ERROR, _('Group %s is locked and CANNOT be deleted.') % obj.name)
        return HttpResponseRedirect(next_url)
    return generic_delete(request, obj, next_url, ondelete_function=on_contactgroup_delete)# args=(p.id,)))


#######################################################################
#
# Contact In Group: Membership edition
#
#######################################################################


class ContactInGroupForm(forms.Form):
    invited = forms.BooleanField(label=_('Invited'), required=False)
    declined = forms.BooleanField(label=_('Declined'), required=False)
    member = forms.BooleanField(label=_('Member'), required=False)
    operator = forms.BooleanField(label=_('Operator'), required=False,
        help_text=_('Full administrator of that group.'))
    viewer = forms.BooleanField(label=_('Viewer'), required=False,
        help_text=_('Can see everything, but read only access.'))
    see_group = forms.BooleanField(label=_('Can see group exists'), required=False)
    change_group = forms.BooleanField(label=_('Can change group'), required=False,
        help_text=_('Can change the group itself, delete it.'))
    see_members = forms.BooleanField(label=_('Can see members'), required=False)
    change_members = forms.BooleanField(label=_('Can change members'), required=False)
    view_fields = forms.BooleanField(label=_('Can view fields'), required=False,
        help_text=_('Can view the fields (like "address" or "email") associated with that group. Few groups support that.'))
    write_fields = forms.BooleanField(label=_('Can write fields'), required=False)
    view_news = forms.BooleanField(label=_('Can view news'), required=False,
        help_text=_('View the news of that group.'))
    write_news = forms.BooleanField(label=_('Can write news'), required=False)
    view_files = forms.BooleanField(label=_('Can view uploaded files'), required=False,
        help_text=_('View the uploaded files. Few group supports that.'))
    write_files = forms.BooleanField(label=_('Can upload files'), required=False)
    view_msgs = forms.BooleanField(label=_('Can view messages'), required=False)
    write_msgs = forms.BooleanField(label=_('Can write messages'), required=False)
    note = forms.CharField(required=False)

    def __init__(self, *args, **kargs):
        super(ContactInGroupForm, self).__init__(*args, **kargs)
        self.fields['invited'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.declined.checked=false;
                this.form.member.checked=false;
            }'''}
        self.fields['declined'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.invited.checked=false;
                this.form.member.checked=false;
            }'''}
        self.fields['member'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.invited.checked=false;
                this.form.declined.checked=false;
            }'''}
        self.fields['operator'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.viewer.checked=true;
                this.form.see_group.checked=true;
                this.form.change_group.checked=true;
                this.form.see_members.checked=true;
                this.form.change_members.checked=true;
                this.form.view_fields.checked=true;
                this.form.write_fields.checked=true;
                this.form.view_news.checked=true;
                this.form.write_news.checked=true;
                this.form.view_files.checked=true;
                this.form.write_files.checked=true;
                this.form.view_msgs.checked=true;
                this.form.write_msgs.checked=true;
            }'''}
        self.fields['viewer'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.see_members.checked=true;
                this.form.view_fields.checked=true;
                this.form.view_news.checked=true;
                this.form.view_files.checked=true;
                this.form.view_msgs.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['see_group'].widget.attrs = {'onchange': '''
            if (!this.checked) {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.change_group.checked=false;
                this.form.see_members.checked=false;
                this.form.change_members.checked=false;
                this.form.view_fields.checked=false;
                this.form.write_fields.checked=false;
                this.form.view_news.checked=false;
                this.form.write_news.checked=false;
                this.form.view_files.checked=false;
                this.form.write_files.checked=false;
                this.form.view_msgs.checked=false;
                this.form.write_msgs.checked=false;
            }'''}
        self.fields['change_group'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['see_members'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.change_members.checked=false;
            }'''}
        self.fields['change_members'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.see_members.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_fields'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_fields.checked=false;
            }'''}
        self.fields['write_fields'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_fields.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_news'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_news.checked=false;
            }'''}
        self.fields['write_news'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_news.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_files'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_files.checked=false;
            }'''}
        self.fields['write_files'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_files.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_msgs'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_msgs.checked=false;
            }'''}
        self.fields['write_msgs'].widget.attrs = {'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_msgs.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}

    def clean(self):
        data = self.cleaned_data
        if   (data['invited'] and data['declined']) \
          or (data['declined'] and data['member']) \
          or (data['invited'] and data['member']):
            raise forms.ValidationError('Invalid flags combinaison')
        return data


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit(request, gid, cid):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    try:
        cig = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        cig = ContactInGroup(contact_id=cid, group_id=gid, flags=0)
    cg = ContactGroup.objects.get(pk=gid)
    contact = Contact.objects.get(pk=cid)
    context = {}
    context['title'] = _('Contact %(contact)s in group %(group)s') % {
        'contact': force_text(contact),
        'group': cg.name_with_date()}
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['contact'] = contact
    context['objtype'] = ContactInGroup

    initial = {}
    for code, intval in TRANS_CIGFLAG_CODE2INT.items():
        if cig.flags & intval:
            field_name = TRANS_CIGFLAG_CODE2TXT[code]
            initial[field_name] = True
    initial['note'] = cig.note

    if request.method == 'POST':
        form = ContactInGroupForm(request.POST, initial=initial)
        if form.is_valid():
            data = form.cleaned_data
            newflags = 0
            for code, field_name in TRANS_CIGFLAG_CODE2TXT.items():
                if data[field_name]:
                    newflags |= TRANS_CIGFLAG_CODE2INT[code]
            if not newflags:
                return HttpResponseRedirect(reverse('ngw.core.views.groups.contactingroup_delete', args=(force_text(cg.id), cid)))
            if (cig.flags ^ newflags) & ADMIN_CIGFLAGS \
                and not perms.c_operatorof_cg(request.user.id, cg.id):
                # If you change any permission flags of that group, you must be a group operator
                raise PermissionDenied
            cig.flags = newflags
            cig.note = data['note']
            # TODO: use set_member_1 for logs
            messages.add_message(
                request, messages.SUCCESS,
                _('Member %(contact)s of group %(group)s has been changed sucessfully!') % {'contact':contact.name, 'group':cg.name})
            Contact.check_login_created(request)
            cig.save()
            hooks.membership_changed(request, contact, cg)
            return HttpResponseRedirect(cg.get_absolute_url())
    else:
        form = ContactInGroupForm(initial=initial)

    context['form'] = form

    inherited_info = ''

    automember_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, CIGFLAG_MEMBER)]).exclude(id=gid).order_by('-date', 'name')
    visible_automember_groups = automember_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    invisible_automember_groups = automember_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    #print(automember_groups.query)
    if automember_groups:
        inherited_info += 'Automatically member because member of subgroup(s):' + '<br>'
        for sub_cg in visible_automember_groups:
            inherited_info += '<li><a href=\"%(url)s\">%(name)s</a>' % {'name': sub_cg.name_with_date(), 'url': sub_cg.get_absolute_url()}
        if invisible_automember_groups:
            inherited_info += '<li>Hidden group(s)...'
        inherited_info += '<br>'

    autoinvited_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, CIGFLAG_INVITED)]).exclude(id=gid).order_by('-date', 'name')
    visible_autoinvited_groups = autoinvited_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    invisible_autoinvited_groups = autoinvited_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    if autoinvited_groups:
        inherited_info += 'Automatically invited because invited in subgroup(s):<br>'
        for sub_cg in visible_autoinvited_groups:
            inherited_info += '<li><a href=\"%(url)s\">%(name)s</a>' % {'name': sub_cg.name_with_date(), 'url': sub_cg.get_absolute_url()}
        if invisible_autoinvited_groups:
            inherited_info += '<li>Hidden group(s)...'

    context['inherited_info'] = mark_safe(inherited_info)

    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('members', _('members'))) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('membership', _('membership')))
    return render_to_response('contact_in_group.html', context, RequestContext(request))


#######################################################################
#
# Contact In Group: Membership inline edition
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit_inline(request, gid, cid):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    contact = get_object_or_404(Contact, pk=cid)
    if request.method == 'GET':
        # This occurs when there is a timeout (logout)
        # Fall back to detailed membership:
        return HttpResponseRedirect(cg.get_absolute_url()+'members/'+cid+'/membership')
    newmembership = request.POST['membership']
    if newmembership == 'invited':
        flags = '+i'
    elif newmembership == 'member':
        flags = '+m'
    elif newmembership == 'declined':
        flags = '+d'
    else:
        raise Exception('invalid membership %s' % newmembership)
    cg.set_member_1(request, contact, flags)
    hooks.membership_changed(request, contact, cg)
    return HttpResponseRedirect(request.POST['next_url'])


#######################################################################
#
# Contact In Group: Membership deletion (remove from group)
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_delete(request, gid, cid):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    try:
        obj = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        return HttpResponse(_('Error, that contact is not a direct member. Please check subgroups'))
    #messages.add_message(request, messages.SUCCESS, _('%s has been removed for group %s.') % (cig.contact.name, cig.group.name))
    base_nav = cg.get_smart_navbar() \
                  .add_component(('members', _('members')))
    return generic_delete(request, obj, next_url=cg.get_absolute_url()+'members/', base_nav=base_nav)
    # TODO: realnav bar is 'remove', not 'delete'



#######################################################################
#
# Mailman synchronisation
#
#######################################################################

class MailmanSyncForm(forms.Form):
    mail = forms.CharField(widget=forms.Textarea)

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_mailman(request, id):
    id = id and int(id) or None
    initial_value = '''
Les résultats de vos commandes courriels sont fournies ci-dessous.
Ci-joint votre message original.

- Résultats :
    Abonnés en mode non-groupé (normaux) :
        user1@example.com (John DOE)
        user2@example.com

- Fait.
    '''
    from ngw.core.mailman import synchronise_group
    if not perms.c_can_see_members_cg(request.user.id, id):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=id)

    context = {}
    context['title'] = _('Mailman synchronisation')
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('mailman', _('mailman')))
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['active_submenu'] = 'mailman'

    if request.method == 'POST':
        form = MailmanSyncForm(request.POST)
        if form.is_valid():
            data = form.clean()
            context['sync_res'] = synchronise_group(cg, data['mail'])
            return render_to_response('group_mailman_result.html', context, RequestContext(request))
    else:
        form = MailmanSyncForm(initial={'mail': initial_value})

    context['form'] = form
    return render_to_response('group_mailman.html', context, RequestContext(request))
