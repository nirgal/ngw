'''
ContactGroup managing views
'''

from datetime import date, datetime, timedelta
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils import html
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils import formats
from django.shortcuts import get_object_or_404
from django import forms
from django.views.generic import View, TemplateView, FormView, UpdateView, CreateView
from django.views.generic.edit import ModelFormMixin
from django.contrib.admin import filters
from django.contrib.admin.widgets import FilteredSelectMultiple, AdminDateWidget
from django.contrib import messages
from ngw.core.models import (
    GROUP_EVERYBODY,
    FIELD_DEFAULT_GROUP,
    Contact, ContactGroup, ContactInGroup, GroupInGroup,
    GroupManageGroup,
    hooks)
from ngw.core.nav import Navbar
from ngw.core import perms
from ngw.core.views.contacts import BaseContactListView
from ngw.core.views.generic import NgwUserAcl, InGroupAcl, NgwListView, NgwDeleteView
from ngw.core.widgets import OnelineCheckboxSelectMultiple, FlagsField


#######################################################################
#
# Groups list
#
#######################################################################

LIST_PREVIEW_LEN = 5
def _truncate_list(lst, maxlen=LIST_PREVIEW_LEN):
    'Utility function to truncate text longer that LIST_PREVIEW_LEN'
    if len(lst) > maxlen:
        return lst[:maxlen] + ['…']
    return lst

class ContactGroupListView(NgwUserAcl, NgwListView):
    list_display = ('name', 'description_not_too_long',
        # 'rendered_fields',
        'visible_direct_supergroups_5',
        'visible_direct_subgroups_5',
        # 'budget_code',
        # 'visible_member_count',
        'locked'
        )
    list_display_links = 'name',
    search_fields = 'name', 'description'

    def visible_direct_supergroups_5(self, group):
        supergroups = group.get_direct_supergroups()
        supergroups = supergroups.with_user_perms(self.request.user.id, perms.SEE_CG)
        supergroups = supergroups[:LIST_PREVIEW_LEN+1]
        return ', '.join(_truncate_list([sg.name_with_date() for sg in supergroups]))
    visible_direct_supergroups_5.short_description = ugettext_lazy('Super groups')

    def visible_direct_subgroups_5(self, group):
        subgroups = group.get_direct_subgroups()
        subgroups = subgroups.with_user_perms(self.request.user.id, perms.SEE_CG)
        subgroups = subgroups[:LIST_PREVIEW_LEN+1]
        return ', '.join(_truncate_list([sg.name_with_date() for sg in subgroups]))
    visible_direct_subgroups_5.short_description = ugettext_lazy('Sub groups')

    def rendered_fields(self, group):
        if group.field_group:
            fields = group.contactfield_set.all()
            if fields:
                return ', '.join(['<a href="' + f.get_absolute_url() + '">'+html.escape(f.name) + '</a>' for f in fields])
            else:
                return _('Yes (but none yet)')
        else:
            return _('No')
    rendered_fields.short_description = ugettext_lazy('Contact fields')

    def visible_member_count(self, group):
        # This is totally ineficient
        if perms.c_can_see_members_cg(self.request.user.id, group.id):
            return group.get_members_count()
        else:
            return _('Not available')
    visible_member_count.short_description = ugettext_lazy('Members')


    def locked(self, group):
        if group.system:
            return '<img src="%sngw/lock.png" alt="locked" width="10" height="10">' % settings.STATIC_URL
        return ''
    locked.short_description = ugettext_lazy('Locked')
    locked.admin_order_field = 'system'
    locked.allow_tags = True

    def get_root_queryset(self):
        return ContactGroup.objects.filter(date=None).with_user_perms(self.request.user.id, perms.SEE_CG)


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Select a contact group')
        context['objtype'] = ContactGroup
        context['nav'] = Navbar(ContactGroup.get_class_navcomponent())

        context.update(kwargs)
        return super().get_context_data(**context)


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

        min_date = date(year, month, 1) - timedelta(days=6)
        str_min_date = min_date.strftime('%Y-%m-%d')
        max_date = date(year, month, 1) + timedelta(days=31+6)
        str_max_date = max_date.strftime('%Y-%m-%d')

        qs = ContactGroup.objects.with_user_perms(request.user.id, perms.SEE_CG)
        qs = qs.filter(Q(date__gte=str_min_date, date__lte=str_max_date)
            | Q(end_date__gte=str_min_date, end_date__lte=str_max_date))

        month_events = {}
        dt = min_date
        while dt <= max_date:
            month_events[dt] = []
            dt += timedelta(days=1)

        for cg in qs:
            if cg.end_date:
                dt = cg.date
                while dt <= cg.end_date:
                    if dt >= min_date and dt <= max_date:
                        month_events[dt].append(cg)
                    dt += timedelta(days=1)
            else:
                month_events[cg.date].append(cg)

        context = {}
        context['title'] = _('Events')
        context['nav'] = Navbar(('events', _('events')))
        context['year_month'] = YearMonthCal(year, month, month_events)
        context['today'] = date.today()

        context.update(kwargs)
        return super().get_context_data(**context)



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
        if cg.userperms & perms.SEE_MEMBERS:
            return HttpResponseRedirect(cg.get_absolute_url() + 'members/')
        if cg.userperms & perms.VIEW_NEWS:
            return HttpResponseRedirect(cg.get_absolute_url() + 'news/')
        if cg.userperms & perms.VIEW_FILES:
            return HttpResponseRedirect(cg.get_absolute_url() + 'files/')
        if cg.userperms & perms.VIEW_MSGS:
            return HttpResponseRedirect(cg.get_absolute_url() + 'messages/')
        raise PermissionDenied


#######################################################################
#
# Member list
#
#######################################################################

class MemberFilter(filters.SimpleListFilter):
    '''
    Filter people according to their membership (invited/declined...)
    '''
    title = ugettext_lazy('membership')
    parameter_name = 'display'

    def __init__(self, request, params, model, view):
        super().__init__(request, params, model, view)
        self.view = view
        self.contactgroup = view.contactgroup
        display = params.pop('display', None)
        if display is None:
            display = self.contactgroup.get_default_display()
        self.display = display


    def lookups(self, request, view):
        return (
            ('m', _('Members')),
            ('i', _('Invited people')),
            ('d', _('Declined invitations')),
            ('g', _('Include subgroups')),
            ('a', _('Admins')),
        )

    def value(self):
        value = super().value()
        if value is None:
            value = self.contactgroup.get_default_display()
        return value

    def choices(self, cl):
        display = self.value()
        for flag, title in self.lookup_choices:
            selected = flag in display
            if selected:
                newdisplay = display.replace(flag, '')
            else:
                newdisplay = display + flag
            yield {
                'selected': selected,
                'query_string': cl.get_query_string({
                    'display': newdisplay }),
                'display': title,
            }

    def queryset(self, request, q):
        display = self.value()
        cg = self.contactgroup

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
            return q


class GroupMemberListView(InGroupAcl, BaseContactListView):
    template_name = 'group_members.html'
    list_filter = BaseContactListView.list_filter + (MemberFilter,)
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.SEE_MEMBERS:
            raise PermissionDenied


    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Contacts of group %s') % cg.name_with_date()

        context['nav'] = cg.get_smart_navbar() \
                           .add_component(('members', _('members')))
        context['active_submenu'] = 'members'

        context.update(kwargs)
        result = super().get_context_data(**context)
        return result


    def get_actions(self, request):
        actions = super().get_actions(request)
        send_message = self.get_action('action_send_message')
        actions[send_message[1]] = send_message
        return actions


    def action_send_message(self, request, queryset):
        ids = request.POST.getlist('_selected_action')
        return HttpResponseRedirect('send_message?ids=' + ','.join(ids))
    action_send_message.short_description = ugettext_lazy("Send a message (external storage)")


#######################################################################
#
# Group edit
#
#######################################################################

class ContactGroupForm(forms.ModelForm):
    class Meta:
        model = ContactGroup
        fields = [
            'name', 'description', 'date', 'end_date', 'budget_code', #'sticky',
            'field_group', 'mailman_address']
        widgets = {
            'date': AdminDateWidget,
            'end_date': AdminDateWidget,
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        self.user = user
        instance = kwargs.get('instance', None)

        super().__init__(*args, **kwargs)

        # Only show visible groups
        visible_groups_choices = [
            (g.id, g.name_with_date())
            for g in ContactGroup.objects.with_user_perms(user.id, perms.SEE_CG)]

        # Super groups
        if instance:
            field_initial = instance.get_visible_direct_supergroups_ids(user.id)
        else:
            field_initial = None
        self.fields['direct_supergroups'] = forms.MultipleChoiceField(
            label=_('Direct supergroups'),
            required=False,
            help_text=_('Members will automatically be granted membership in these groups.'),
            widget=FilteredSelectMultiple(_('groups'), False),
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
                widget=FilteredSelectMultiple(_('groups'), False),
                choices = visible_groups_choices,
                initial = field_initial)

    def clean(self):
        data = super().clean()
        start_date = data.get('date', None)
        end_date = data.get('end_date', None)
        if end_date:
            if not start_date:
                self.add_error('date', _('That field is required when you have an end date.'))
            elif end_date < start_date:
                self.add_error('end_date', _('The end date must be after the start date.'))

    def save(self, commit=True):
        is_creation = self.instance.pk is None
        data = self.cleaned_data

        # Save the base fields
        cg = super().save(commit)

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
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        request = self.request
        cg = form.save()

        messages.add_message(request, messages.SUCCESS, _('Group %s has been changed successfully!') % cg.name_with_date())

        cg.check_static_folder_created()
        Contact.objects.check_login_created(request) # subgroups change

        if self.pk_url_kwarg not in self.kwargs: # new added instance
            base_url = '.'
        else:
            base_url = '..'
        if request.POST.get('_continue', None):
            return HttpResponseRedirect(
                base_url + '/' + str(cg.id) + '/edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect(base_url + '/add')
        else:
            return HttpResponseRedirect(base_url + '/' + str(cg.id) + '/')

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
        return super().get_context_data(**context)


class GroupEditView(InGroupAcl, GroupEditMixin, UpdateView):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied


class GroupCreateView(NgwUserAcl, GroupEditMixin, CreateView):
    def get(self, request, *args, **kwargs):
        default_group_id = request.user.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
        if not default_group_id:
            messages.add_message(
                request, messages.WARNING,
                _('You must define a default group before you can create a group.'))
            return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
        default_group_id = int(default_group_id)
        if not request.user.is_member_of(default_group_id):
            messages.add_message(
                request, messages.WARNING,
                _('You no longer are member of your default group. Please define a new default group.'))
            return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
        if not perms.c_can_see_cg(request.user.id, default_group_id):
            messages.add_message(
                request, messages.WARNING,
                _('You no longer are authorized to see your default group. Please define a new default group.'))
            return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')

        return super().get(request, *args, **kwargs)


#######################################################################
#
# Group delete
#
#######################################################################


class GroupDeleteView(InGroupAcl, NgwDeleteView):
    model = ContactGroup
    pk_url_kwarg = 'gid'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied

    def get_object(self, *args, **kwargs):
        cg = super().get_object(*args, **kwargs)
        if cg.system:
            messages.add_message(
                self.request, messages.ERROR,
                _('Group %s is locked and CANNOT be deleted.') % cg.name)
            raise PermissionDenied
        return cg

    def get_context_data(self, **kwargs):
        context = {}
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar() \
                     .add_component(('delete', _('delete')))
        context.update(kwargs)
        return super().get_context_data(**context)

    def delete(self, request, *args, **kwargs):
        cg = self.get_object()
        # All subgroups will now have their fathers' fathers as direct fathers
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
        return super().delete(request, *args, **kwargs)


#######################################################################
#
# Contact In Group: Membership edition
#
#######################################################################


class ContactInGroupForm(forms.ModelForm):
    flags = FlagsField(label=ugettext_lazy('Membership'))
    class Meta:
        model = ContactInGroup
        fields = ['flags', 'note']
        widgets = {
            'note': forms.TextInput(attrs={'size': 100}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance', None)
        self.user = kwargs.pop('user')
        self.contact = kwargs.pop('contact')
        self.group = kwargs.pop('group')
        super().__init__(*args, **kwargs)



    def clean(self):
        # TODO: improve conflicts/dependencies checking
        # Currently gets best resolution in set_member_1
        data = super().clean()
        flags = data['flags']
        if ((flags & perms.INVITED and flags & perms.DECLINED)
            or (flags & perms.DECLINED and flags & perms.MEMBER)
            or (flags & perms.INVITED and flags & perms.MEMBER)):
            raise forms.ValidationError('Invalid flags combinaison')

        if flags == 0 and data['note']:
            raise forms.ValidationError(_('You cannot have a note unless you select some flags too'))
        return data


    def save(self):
        oldflags = self.instance.flags or 0
        is_creation = self.instance.pk is None
        cig = super().save(commit=False)
        if is_creation:
            cig.contact = self.contact
            cig.group = self.group

        data = self.cleaned_data

        newflags = self.cleaned_data['flags']
        if (oldflags ^ newflags) & perms.ADMIN_ALL \
            and not perms.c_operatorof_cg(self.user.id, self.group.id):
            # If you change any permission flags of that group, you must be a group operator
            raise PermissionDenied
        if not newflags:
            cig.delete()
            return None
        cig.flags = newflags
        cig.save()
        # TODO: use set_member_1 for logs:  cg.set_member_1(request, contact, flags)
        return cig


class ContactInGroupView(InGroupAcl, FormView):
    form_class = ContactInGroupForm
    template_name = 'contact_in_group.html'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_MEMBERS:
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
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
        Contact.objects.check_login_created(self.request)
        hooks.membership_changed(self.request, contact, cg)
        return HttpResponseRedirect(cg.get_absolute_url())

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        gid = int(self.kwargs['gid'])
        contact = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        cg = self.contactgroup

        context = {}
        context['title'] = _('Contact %(contact)s in group %(group)s') % {
            'contact': str(contact),
            'group': cg.name_with_date()}
        context['contact'] = contact
        context['objtype'] = ContactInGroup
        inherited_info = ''

        automember_groups = ContactGroup.objects.extra(
            where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, perms.MEMBER)]).exclude(id=gid).order_by('-date', 'name')

        visible_automember_groups = automember_groups.with_user_perms(
            self.request.user.id, wanted_flags=perms.SEE_CG)

        invisible_automember_groups = automember_groups.extra(where=[
            'NOT EXISTS ('
            ' SELECT * FROM v_cig_perm'
            ' WHERE v_cig_perm.contact_id=%s'
            ' AND v_cig_perm.group_id=contact_group.id'
            ' AND v_cig_perm.flags & %s <> 0)'
            % (self.request.user.id, perms.SEE_CG)])

        if automember_groups:
            inherited_info += _('Automatically member because member of subgroup(s)') + ':<ul>'
            for sub_cg in visible_automember_groups:
                inherited_info += '<li><a href=\"%(url)s\">%(name)s</a>' % {
                    'name': sub_cg.name_with_date(),
                    'url': sub_cg.get_absolute_url()}
            if invisible_automember_groups:
                inherited_info += '<li>' + _('Hidden group(s)...')
            inherited_info += '</ul>'

        autoinvited_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, perms.INVITED)]).exclude(id=gid).order_by('-date', 'name')

        visible_autoinvited_groups = autoinvited_groups.with_user_perms(
            self.request.user.id, wanted_flags=perms.SEE_CG)

        invisible_autoinvited_groups = autoinvited_groups.extra(where=[
            'NOT EXISTS ('
            ' SELECT * FROM v_cig_perm'
            ' WHERE v_cig_perm.contact_id=%s'
            ' AND v_cig_perm.group_id=contact_group.id'
            ' AND v_cig_perm.flags & %s <> 0)'
            % (self.request.user.id, perms.SEE_CG)])

        if autoinvited_groups:
            inherited_info += _('Automatically invited because invited in subgroup(s)') + ':<ul>'
            for sub_cg in visible_autoinvited_groups:
                inherited_info += '<li><a href=\"%(url)s\">%(name)s</a>' % {
                    'name': sub_cg.name_with_date(),
                    'url': sub_cg.get_absolute_url()}
            if invisible_autoinvited_groups:
                inherited_info += '<li>' + _('Hidden group(s)...')
            inherited_info += '</ul>'

        context['inherited_info'] = mark_safe(inherited_info)

        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members'))) \
                         .add_component(contact.get_navcomponent()) \
                         .add_component(('membership', _('membership')))
        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Contact In Group: Membership inline edition
#
#######################################################################


class ContactInGroupInlineView(InGroupAcl, View):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_MEMBERS:
            raise PermissionDenied

    def post(self, request, gid, cid):
        cg = self.contactgroup
        contact = get_object_or_404(Contact, pk=int(cid))
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


class ContactInGroupDelete(InGroupAcl, NgwDeleteView):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_MEMBERS:
            raise PermissionDenied

    def get_object(self, *args, **kwargs):
        if not hasattr(self, 'object'):
            cid = int(self.kwargs['cid'])
            self.object = ContactInGroup.objects.get(
                contact_id=cid, group_id=self.contactgroup.id)
        return self.object

    def get_context_data(self, **kwargs):
        contact = self.object.contact
        print(self.contactgroup.get_smart_navbar())
        context = {}
        context['nav'] = self.contactgroup.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component((str(contact.id), contact.name)) \
            .add_component(('remove', _('delete')))
        context.update(kwargs)
        return super().get_context_data(**context)

    def get(self, request, gid, cid):
        try:
            self.get_object()
        except ContactInGroup.DoesNotExist:
            return HttpResponse(_('Error, that contact is not a direct member. Please check subgroups'))
        return super().get(self, request, gid, cid)
