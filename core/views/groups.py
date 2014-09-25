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
from django.utils.translation import ugettext_lazy as _, string_concat
from django.utils.encoding import force_text
from django.utils import formats
from django.utils import six
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django import forms
from django.views.generic import View, TemplateView, FormView, UpdateView, CreateView
from django.views.generic.edit import ModelFormMixin
from django.contrib import messages
from ngw.core.models import (
    GROUP_EVERYBODY, GROUP_USER_NGW,
    FIELD_DEFAULT_GROUP,
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
        (_('Name'), None, 'name', 'name'),
        (_('Description'), None, 'description_not_too_long', 'description'),
        #(_('Contact fields'), None, 'rendered_fields', 'field_group'),
        (_('Super groups'), None, 'visible_direct_supergroups_5', None),
        (_('Sub groups'), None, 'visible_direct_subgroups_5', None),
        #(_('Budget\u00a0code'), None, 'budget_code', 'budget_code'),
        #(_('Members'), None, 'visible_member_count', None),
        #(_('System\u00a0locked'), None, 'system', 'system'),
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
            wanted_flags |= perms.MEMBER
        if 'i' in display:
            wanted_flags |= perms.INVITED
        if 'd' in display:
            wanted_flags |= perms.DECLINED
        if 'a' in display:
            wanted_flags |= perms.ADMIN_ALL

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
                % (cg.id, wanted_flags & (perms.MEMBER|perms.INVITED|perms.DECLINED)))
            # The inherited admins
            or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(father_id) FROM group_manage_group WHERE subgroup_id=%s AND group_manage_group.flags & %s <> 0) AND contact_in_group.flags & 1 <> 0)'
                % (cg.id, wanted_flags & perms.ADMIN_ALL))

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
                    for group in ContactGroup.objects.filter(date__isnull=1).extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % user.id]).order_by('name')]),
                (_('Events'), [
                    (group.id, group.name_with_date())
                    for group in ContactGroup.objects.filter(date__isnull=0).extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % user.id]).order_by('-date', 'name')]),
                ],
            )
        for flag, longname in six.iteritems(perms.FLAGTOTEXT):
            field_name = 'membership_' + flag

            oncheck_js = ''.join([
                'this.form.membership_%s.checked=true;' % code
                for code in perms.FLAGDEPENDS[flag]])
            oncheck_js += ''.join([
                'this.form.membership_%s.checked=false;' % code
                for code in perms.FLAGCONFLICTS[flag]])

            onuncheck_js = ''
            for flag1, depflag1 in six.iteritems(perms.FLAGDEPENDS):
                if flag in depflag1:
                    onuncheck_js += 'this.form.membership_%s.checked=false;' % flag1

            self.fields[field_name] = forms.BooleanField(
                label=longname, required=False,
                widget=forms.widgets.CheckboxInput(attrs={
                    'onchange': 'if (this.checked) {%s} else {%s}' % (oncheck_js, onuncheck_js),
                }))


    def clean(self):
        if 'group' in self.cleaned_data:
            for flag in six.iterkeys(perms.FLAGTOTEXT):
                if self.cleaned_data['membership_' + flag]:
                    if perms.FLAGTOINT[flag] & perms.ADMIN_ALL and not perms.c_operatorof_cg(self.user.id, self.cleaned_data['group']):
                        raise forms.ValidationError(_('You need to be operator of the target group to add this kind of membership.'))

        for flag in six.iterkeys(perms.FLAGTOTEXT):
            if self.cleaned_data['membership_' + flag]:
                return super(GroupAddManyForm, self).clean()
        raise forms.ValidationError(_('You must select at least one mode'))


    def add_them(self, request):
        group_id = self.cleaned_data['group']
        target_group = get_object_or_404(ContactGroup, pk=group_id)

        contact_ids = self.cleaned_data['ids'].split(',')
        contacts = Contact.objects.filter(pk__in=contact_ids)

        modes = ''
        for flag in six.iterkeys(perms.FLAGTOTEXT):
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
        context['title'] = _('Add %s contact(s) to a group') % len(ids)
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

class ContactGroupForm(forms.ModelForm):
    class Meta:
        model = ContactGroup
        fields = ['name', 'description', 'date', 'budget_code', 'sticky', 'field_group',
            'mailman_address']
        widgets = {
            'date': NgwCalendarWidget(attrs={'class':'vDateField'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        self.user = user
        instance = kwargs.get('instance', None)

        super(ContactGroupForm, self).__init__(*args, **kwargs)

        # Only show visible groups
        visible_groups_choices = [
            (g.id, g.name_with_date())
            for g in ContactGroup.objects.extra(
                where=['perm_c_can_see_cg(%s, contact_group.id)' % user.id]
                ).order_by('-date', 'name')]

        # Super groups
        if instance:
            field_initial = instance.get_visible_direct_supergroups_ids(user.id)
        else:
            field_initial = None
        self.fields['direct_supergroups'] = forms.MultipleChoiceField(
            label=_('Direct supergroups'),
            required=False,
            help_text=_('Members will automatically be granted membership in these groups.'),
            widget=FilterMultipleSelectWidget('groups', False),
            choices = visible_groups_choices,
            initial = field_initial)

        # Add fields for kind of permissions
        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_%s_groups' % flag
            if instance:
                intflag = perms.FLAGTOINT[flag]
                field_initial = instance.get_visible_mananger_groups_ids(user.id, intflag)
            else:
                if flag == 'o':
                    default_group_id = user.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
                    assert default_group_id, "User doesn't have a default group"
                    field_initial = int(default_group_id),
                else:
                    field_initial = None
            self.fields[field_name] = forms.MultipleChoiceField(
                label=perms.FLAGGROUPLABEL[flag],
                required=False,
                help_text=perms.FLAGGROUPHELP[flag],
                widget=FilterMultipleSelectWidget('groups', False),
                choices = visible_groups_choices,
                initial = field_initial)

    def save(self):
        is_creation = self.instance.pk is None
        data = self.cleaned_data

        # Save the base fields
        cg = super(ContactGroupForm, self).save()

        # Update the super groups
        old_direct_supergroups_ids = set(cg.get_visible_direct_supergroups_ids(self.user.id))
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
            intflag = perms.FLAGTOINT[flag]
            old_groups_ids = set(cg.get_visible_mananger_groups_ids(self.user.id, intflag))
            new_groups_ids = set([int(ogid) for ogid in data[field_name]])
            groups_added = new_groups_ids - old_groups_ids
            groups_removed = old_groups_ids - new_groups_ids
            print('flag', flag, 'groups_added=', groups_added)
            print('flag', flag, 'groups_removed=', groups_removed)
            if not is_creation and (groups_added or groups_removed) and not perms.c_operatorof_cg(self.user.id, cg.id):
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

        return cg


class GroupEditMixin(ModelFormMixin):
    template_name = 'edit.html'
    form_class = ContactGroupForm
    model = ContactGroup
    pk_url_kwarg = 'gid'

    def get_form_kwargs(self):
        kwargs = super(GroupEditMixin, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        request = self.request
        cg = form.save()

        messages.add_message(request, messages.SUCCESS, _('Group %s has been changed sucessfully!') % cg.name_with_date())

        cg.check_static_folder_created()
        Contact.check_login_created(request) # subgroups change

        if request.POST.get('_continue', None):
            return HttpResponseRedirect(cg.get_absolute_url() + 'edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect(cg.get_class_absolute_url() + 'add')
        else:
                return HttpResponseRedirect(cg.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing %s') % self.object.name_with_date()
            id = self.object.id
        else:
            title = _('Adding a new %s') % ContactGroup.get_class_verbose_name()
            id = None

        context['title'] = title
        context['id'] = id
        context['objtype'] = ContactGroup

        if id:
            context['nav'] = self.object.get_smart_navbar() \
                             .add_component(('edit', _('edit')))
        else:
            context['nav'] = Navbar(ContactGroup.get_class_navcomponent()) \
                             .add_component(('add', _('add')))

        context.update(kwargs)
        return super(GroupEditMixin, self).get_context_data(**context)


class GroupEditView(InGroupAcl, GroupEditMixin, UpdateView):
    def check_perm_groupuser(self, group, user):
        if not perms.c_can_change_cg(user.id, group.id):
            raise PermissionDenied


class GroupCreateView(NgwUserAcl, GroupEditMixin, CreateView):
    def get(self, request, *args, **kwargs):
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

        return super(GroupCreateView, self).get(request, *args, **kwargs)


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


class ContactInGroupForm(forms.ModelForm):
    class Meta:
        model = ContactInGroup
        fields = ['note']
    def __init__(self, *args, **kargs):
        instance = kargs.get('instance', None)
        self.user = kargs.pop('user')
        self.contact = kargs.pop('contact')
        self.group = kargs.pop('group')
        super(ContactInGroupForm, self).__init__(*args, **kargs)
        for flag, longname in six.iteritems(perms.FLAGTOTEXT):
            field_name = 'membership_' + flag

            oncheck_js = ''.join([
                'this.form.membership_%s.checked=true;' % code
                for code in perms.FLAGDEPENDS[flag]])
            oncheck_js += ''.join([
                'this.form.membership_%s.checked=false;' % code
                for code in perms.FLAGCONFLICTS[flag]])

            onuncheck_js = ''
            for flag1, depflag1 in six.iteritems(perms.FLAGDEPENDS):
                if flag in depflag1:
                    onuncheck_js += 'this.form.membership_%s.checked=false;' % flag1

            if instance:
                initial = bool(perms.FLAGTOINT[flag] & instance.flags)
            else:
                initial = False
            self.fields.insert(
                len(self.fields)-1,  # just before the note
                field_name,
                forms.BooleanField(
                    label=longname, required=False,
                    widget=forms.widgets.CheckboxInput(attrs={
                        'onchange': 'if (this.checked) {%s} else {%s}' % (oncheck_js, onuncheck_js),
                    }),
                    initial = initial))

    def clean(self):
        # TODO: improve conflicts/dependencies checking
        # Currently gets best resolution in set_member_1
        data = self.cleaned_data
        if   (data['membership_i'] and data['membership_d']) \
          or (data['membership_d'] and data['membership_m']) \
          or (data['membership_i'] and data['membership_m']):
            raise forms.ValidationError('Invalid flags combinaison')

        newflags = 0
        for flag, intvalue in six.iteritems(perms.FLAGTOINT):
            if data['membership_' + flag]:
                newflags |= intvalue
        if newflags == 0 and data['note']:
            raise forms.ValidationError(_('You cannot have a note unless you select some flags too'))
        return data


    def save(self):
        oldflags = self.instance.flags or 0
        is_creation = self.instance.pk is None
        cig = super(ContactInGroupForm, self).save(commit=False)
        if is_creation:
            cig.contact = self.contact
            cig.group = self.group

        data = self.cleaned_data

        newflags = 0
        for flag, intvalue in six.iteritems(perms.FLAGTOINT):
            if data['membership_' + flag]:
                newflags |= intvalue
        if (oldflags ^ newflags) & perms.ADMIN_ALL \
            and not perms.c_operatorof_cg(self.user.id, self.group.id):
            # If you change any permission flags of that group, you must be a group operator
            raise PermissionDenied
        if not newflags:
            cig.delete()
            return None
        cig.flags = newflags
        cig.save()
        # TODO: use set_member_1 for logs
        return cig


class ContactInGroupView(InGroupAcl, FormView):
    form_class = ContactInGroupForm
    template_name = 'contact_in_group.html'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_change_cg(user.id, group.id):
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super(ContactInGroupView, self).get_form_kwargs()
        kwargs['group'] = self.contactgroup
        kwargs['contact'] = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        kwargs['user'] = self.request.user
        try:
            instance = ContactInGroup.objects.get(
                contact_id=int(self.kwargs['cid']),
                group_id=self.contactgroup.id)
        except ContactInGroup.DoesNotExist:
            instance = None
        kwargs['instance'] = instance
        return kwargs

    def form_valid(self, form):
        cig = form.save()
        cg = self.contactgroup
        contact = form.contact
        if cig:
            messages.add_message(
                self.request, messages.SUCCESS,
                _('Member %(contact)s of group %(group)s has been changed.') % {
                    'contact': contact.name,
                    'group': cg.name})
        else:
            messages.add_message(
                self.request, messages.SUCCESS,
                _('%(contact)s has been removed from group %(group)s.') % {
                    'contact': contact.name,
                    'group': cg.name})
        Contact.check_login_created(self.request)
        hooks.membership_changed(self.request, contact, cg)
        return HttpResponseRedirect(cg.get_absolute_url())

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        gid = int(self.kwargs['gid'])
        contact = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        cg = self.contactgroup

        context = {}
        context['title'] = _('Contact %(contact)s in group %(group)s') % {
            'contact': force_text(contact),
            'group': cg.name_with_date()}
        context['contact'] = contact
        context['objtype'] = ContactInGroup
        inherited_info = ''

        automember_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, perms.MEMBER)]).exclude(id=gid).order_by('-date', 'name')
        visible_automember_groups = automember_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % self.request.user.id])
        invisible_automember_groups = automember_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % self.request.user.id])
        #print(automember_groups.query)
        if automember_groups:
            inherited_info = string_concat(
                    inherited_info,
                    _('Automatically member because member of subgroup(s)'),
                    ':<ul>')
            for sub_cg in visible_automember_groups:
                inherited_info = string_concat(
                    inherited_info,
                    '<li><a href=\"%(url)s\">%(name)s</a>' % {'name': sub_cg.name_with_date(), 'url': sub_cg.get_absolute_url()})
            if invisible_automember_groups:
                inherited_info = string_concat(
                    inherited_info,
                    '<li>',
                    _('Hidden group(s)...'))
            inherited_info = string_concat(inherited_info, '</ul>')

        autoinvited_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, perms.INVITED)]).exclude(id=gid).order_by('-date', 'name')
        visible_autoinvited_groups = autoinvited_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % self.request.user.id])
        invisible_autoinvited_groups = autoinvited_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % self.request.user.id])
        if autoinvited_groups:
            inherited_info = string_concat(
                inherited_info,
                _('Automatically invited because invited in subgroup(s)'),
                ':<ul>')
            for sub_cg in visible_autoinvited_groups:
                inherited_info = string_concat(
                    inherited_info,
                    '<li><a href=\"%(url)s\">%(name)s</a>' % {'name': sub_cg.name_with_date(), 'url': sub_cg.get_absolute_url()})
            if invisible_autoinvited_groups:
                inherited_info = string_concat(
                    inherited_info,
                    '<li>',
                    _('Hidden group(s)...'))
            inherited_info = string_concat(inherited_info, '</ul>')

        context['inherited_info'] = mark_safe(inherited_info)

        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members'))) \
                         .add_component(contact.get_navcomponent()) \
                         .add_component(('membership', _('membership')))
        context.update(kwargs)
        return super(ContactInGroupView, self).get_context_data(**context)


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
