# -*- encoding: utf-8 -*-
'''
ContactGroup managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from datetime import date, datetime, timedelta
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils import html
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils import formats
from django.utils import six
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django import forms
from django.views.generic import View, TemplateView, FormView
from django.contrib import messages
from ngw.core.models import (
    GROUP_EVERYBODY, GROUP_USER_NGW,
    FIELD_DEFAULT_GROUP,
    CIGFLAG_MEMBER, CIGFLAG_INVITED, CIGFLAG_DECLINED,
    ADMIN_CIGFLAGS,
    TRANS_CIGFLAG_CODE2INT, TRANS_CIGFLAG_CODE2TEXT,
    CIGFLAGS_CODEDEPENDS, CIGFLAGS_CODEONDELETE,
    Contact, ContactGroup, ContactInGroup, GroupInGroup,
    GroupManageGroup,
    hooks)
from ngw.core.widgets import NgwCalendarWidget, FilterMultipleSelectWidget
from ngw.core.nav import Navbar
from ngw.core import perms
from ngw.core.views.contacts import BaseContactListView
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import generic_delete, NgwUserAcl, InGroupAcl, NgwListView


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

        def can_see_messages(self):
            return perms.c_can_view_msgs_cg(userid, self.id)

    return UContactGroup


class ContactGroupListView(NgwUserAcl, NgwListView):
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


class EventListView(NgwUserAcl, TemplateView):
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

        UContactGroup = get_UContactGroup(self.request.user.id)
        q = UContactGroup.objects.filter(date__gte=min_date, date__lte=max_date).extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])

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

class ContactGroupView(InGroupAcl, View):
    '''
    Redirect to members list, if allowed.
    Otherwise, try to find some authorized page.
    '''
    def get(self, request, *args, **kwargs):
        cg = self.contactgroup
        gid = cg.id
        uid = request.user.id
        if perms.c_can_see_members_cg(uid, gid):
            return HttpResponseRedirect(cg.get_absolute_url() + 'members/')
        if perms.c_can_see_news_cg(uid, gid):
            return HttpResponseRedirect(cg.get_absolute_url() + 'news/')
        if perms.c_can_see_files_cg(uid, gid):
            return HttpResponseRedirect(cg.get_absolute_url() + 'files/')
        if perms.c_can_view_msgs_cg(uid, gid):
            return HttpResponseRedirect(cg.get_absolute_url() + 'messages/?&_order=-1')
        raise PermissionDenied


#######################################################################
#
# Member list
#
#######################################################################

class GroupMemberListView(InGroupAcl, BaseContactListView):
    template_name = 'group_detail.html'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_see_members_cg(user.id, group.id):
            raise PermissionDenied


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

        self.url_params['display'] = self.display
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


    def get_actions(self, request):
        for action in super(GroupMemberListView, self).get_actions(request):
            yield action
        if perms.c_can_write_msgs_cg(request.user.id, self.contactgroup.id):
            yield 'action_send_message'
        yield 'add_to_group'


    def action_send_message(self, request, queryset):
        ids = request.POST.getlist('_selected_action')
        return HttpResponseRedirect('send_message?ids=' + ','.join(ids))
    action_send_message.short_description = _("Send a message (external storage)")


    def add_to_group(self, request, queryset):
        ids = request.POST.getlist('_selected_action')
        return HttpResponseRedirect('add_contacts_to?ids=' + ','.join(ids))
    add_to_group.short_description = _("Add to another group")


#######################################################################
#
# Add to another group
#
#######################################################################


class GroupAddManyForm(forms.Form):
    ids = forms.CharField(widget=forms.widgets.HiddenInput)

    def __init__(self, user, *args, **kwargs):
        super(GroupAddManyForm, self).__init__(*args, **kwargs)
        self.user = user
        self.fields['group'] = forms.ChoiceField(
            label=_('Target group'),
            choices = [
                ('', _('Choose a group')),
                (_('Permanent groups'), [
                    (group.id, group.name)
                    for group in ContactGroup.objects.filter(date__isnull=1).extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % user.id])]),
                (_('Events'), [
                    (group.id, group.name_with_date())
                    for group in ContactGroup.objects.filter(date__isnull=0).extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % user.id])]),
                ],
            )
        for flag, longname in six.iteritems(TRANS_CIGFLAG_CODE2TEXT):
            field_name = 'membership_' + flag

            oncheck_js = ''.join([
                'this.form.membership_%s.checked=true;' % code
                for code in CIGFLAGS_CODEDEPENDS[flag]])
            oncheck_js += ''.join([
                'this.form.membership_%s.checked=false;' % code
                for code in CIGFLAGS_CODEONDELETE[flag]])

            onuncheck_js = ''
            for flag1, depflag1 in six.iteritems(CIGFLAGS_CODEDEPENDS):
                if flag in depflag1:
                    onuncheck_js += 'this.form.membership_%s.checked=false;' % flag1

            self.fields[field_name] = forms.BooleanField(
                label=longname, required=False,
                widget=forms.widgets.CheckboxInput(attrs={
                    'onchange': 'if (this.checked) {%s} else {%s}' % (oncheck_js, onuncheck_js),
                }))


    def clean(self):
        if 'group' in self.cleaned_data:
            for flag in six.iterkeys(TRANS_CIGFLAG_CODE2TEXT):
                if self.cleaned_data['membership_' + flag]:
                    if TRANS_CIGFLAG_CODE2INT[flag] & ADMIN_CIGFLAGS and not perms.c_operatorof_cg(self.user.id, self.cleaned_data['group']):
                        raise forms.ValidationError(_('You need to be operator of the target group to add this kind of membership.'))

        for flag in six.iterkeys(TRANS_CIGFLAG_CODE2TEXT):
            if self.cleaned_data['membership_' + flag]:
                return super(GroupAddManyForm, self).clean()
        raise forms.ValidationError(_('You must select at least one mode'))


    def add_them(self, request):
        group_id = self.cleaned_data['group']
        target_group = get_object_or_404(ContactGroup, pk=group_id)

        contact_ids = self.cleaned_data['ids']
        contacts = Contact.objects.filter(pk__in=contact_ids)

        modes = ''
        for flag in six.iterkeys(TRANS_CIGFLAG_CODE2TEXT):
            field_name = 'membership_' + flag
            if self.cleaned_data[field_name]:
                modes += '+' + flag

        target_group.set_member_n(request, contacts, modes)


class GroupAddManyView(InGroupAcl, FormView):
    form_class = GroupAddManyForm
    template_name = 'group_add_contacts_to.html'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_see_members_cg(user.id, group.id):
            raise PermissionDenied

    def get_initial(self):
        return {'ids': self.request.REQUEST['ids']}

    def get_form_kwargs(self):
        kwargs = super(GroupAddManyView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        ids = self.request.REQUEST['ids'].split(',')
        context['title'] = _('Add %s contact(s) to a group' % len(ids))
        context['nav'] = cg.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component(('add_contacts_to', _('add contacts to')))
        context['groups'] = ContactGroup.objects.extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % self.request.user.id]).order_by('-date', 'name')
        context['active_submenu'] = 'members'
        context.update(kwargs)
        return super(GroupAddManyView, self).get_context_data(**context)


    def form_valid(self, form):
        form.add_them(self.request)
        self.form = form
        return super(GroupAddManyView, self).form_valid(form)

    def get_success_url(self):
        group_id = self.form.cleaned_data['group']
        target_group = get_object_or_404(ContactGroup, pk=group_id)
        return target_group.get_absolute_url() + 'members/'


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

    admin_o_groups = forms.MultipleChoiceField(label=_('Operator groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted administrative priviledges.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_v_groups = forms.MultipleChoiceField(label=_('Viewer groups'),
        required=False,
        help_text=_("Members of these groups will automatically be granted viewer priviledges: They can see everything but can't change things."),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_e_groups = forms.MultipleChoiceField(label=_('Existence seer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to know that current group exists.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_E_groups = forms.MultipleChoiceField(label=_('Editor groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to change/delete the current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_c_groups = forms.MultipleChoiceField(label=_('Members seer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to see the list of members.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_C_groups = forms.MultipleChoiceField(label=_('Members changing groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to change members of current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_f_groups = forms.MultipleChoiceField(label=_('Fields viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to read the fields associated to current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_F_groups = forms.MultipleChoiceField(label=_('Fields writer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to write to fields associated to current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_n_groups = forms.MultipleChoiceField(label=_('News viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permisson to read news of current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_N_groups = forms.MultipleChoiceField(label=_('News writer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to write news in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_u_groups = forms.MultipleChoiceField(label=_('File viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to view uploaded files in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_U_groups = forms.MultipleChoiceField(label=_('File uploader groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to upload files.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_x_groups = forms.MultipleChoiceField(label=_('Message viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to view messages in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    admin_X_groups = forms.MultipleChoiceField(label=_('Message sender groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to send messages.'),
        widget=FilterMultipleSelectWidget('groups', False))

    def __init__(self, for_user, *args, **kargs):
        super(ContactGroupForm, self).__init__(*args, **kargs)
        visible_groups_choices = [(g.id, g.name_with_date()) for g in ContactGroup.objects.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % for_user]).order_by('-date', 'name')]
        self.fields['direct_supergroups'].choices = visible_groups_choices
        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_%s_groups' % flag
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
                field_name = 'admin_%s_groups' % flag
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
                field_name = 'admin_%s_groups' % flag
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
                'admin_o_groups': (default_group_id,)}
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
    def __init__(self, *args, **kargs):
        super(ContactInGroupForm, self).__init__(*args, **kargs)
        for flag, longname in six.iteritems(TRANS_CIGFLAG_CODE2TEXT):
            field_name = 'membership_' + flag

            oncheck_js = ''.join([
                'this.form.membership_%s.checked=true;' % code
                for code in CIGFLAGS_CODEDEPENDS[flag]])
            oncheck_js += ''.join([
                'this.form.membership_%s.checked=false;' % code
                for code in CIGFLAGS_CODEONDELETE[flag]])

            onuncheck_js = ''
            for flag1, depflag1 in six.iteritems(CIGFLAGS_CODEDEPENDS):
                if flag in depflag1:
                    onuncheck_js += 'this.form.membership_%s.checked=false;' % flag1

            self.fields[field_name] = forms.BooleanField(
                label=longname, required=False,
                widget=forms.widgets.CheckboxInput(attrs={
                    'onchange': 'if (this.checked) {%s} else {%s}' % (oncheck_js, onuncheck_js),
                }))
        self.fields['note'] = forms.CharField(required=False)

    def clean(self):
        # TODO: improve conflicts/dependencies checking
        # Currently gets best resolution in set_member_1
        data = self.cleaned_data
        if   (data['membership_i'] and data['membership_d']) \
          or (data['membership_d'] and data['membership_m']) \
          or (data['membership_i'] and data['membership_m']):
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
    for flag, intval in six.iteritems(TRANS_CIGFLAG_CODE2INT):
        if cig.flags & intval:
            initial['membership_' + flag] = True
    initial['note'] = cig.note

    if request.method == 'POST':
        form = ContactInGroupForm(request.POST, initial=initial)
        if form.is_valid():
            data = form.cleaned_data
            newflags = 0
            for flag, intvalue in six.iteritems(TRANS_CIGFLAG_CODE2INT):
                if data['membership_' + flag]:
                    newflags |= intvalue
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
                _('Member %(contact)s of group %(group)s has been changed.') % {
                    'contact': contact.name,
                    'group': cg.name})
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
