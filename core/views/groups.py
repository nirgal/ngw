'''
ContactGroup managing views
'''

import calendar
import decimal
import json
import logging
import re
import time
from datetime import date, datetime, timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import filters
from django.contrib.admin.widgets import (AdminDateWidget,
                                          FilteredSelectMultiple)
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import formats, html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ungettext
from django.views.generic import (CreateView, DetailView, FormView,
                                  TemplateView, UpdateView, View)
from django.views.generic.edit import ModelFormMixin

from ngw.core import perms
from ngw.core.models import (FIELD_DEFAULT_GROUP, GROUP_EVERYBODY, Config,
                             Contact, ContactGroup, ContactInGroup,
                             GroupInGroup, GroupManageGroup)
from ngw.core.nav import Navbar
from ngw.core.views.contacts import BaseContactListView
from ngw.core.views.generic import (InGroupAcl, NgwDeleteView, NgwListView,
                                    NgwUserAcl)
from ngw.core.widgets import FlagsField

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
    list_display = (
        'name', 'description_not_too_long',
        # 'rendered_fields',
        # 'visible_direct_supergroups_5',
        # 'visible_direct_subgroups_5',
        # 'budget_code',
        # 'visible_member_count',
        'flags'
        )
    list_display_links = 'name',
    search_fields = 'name', 'description'

    def visible_direct_supergroups_5(self, group):
        supergroups = group.get_direct_supergroups()
        supergroups = supergroups.with_user_perms(self.request.user.id,
                                                  perms.SEE_CG)
        supergroups = supergroups[:LIST_PREVIEW_LEN+1]
        return ', '.join(_truncate_list(
            [str(sg) for sg in supergroups]))
    visible_direct_supergroups_5.short_description = ugettext_lazy(
        'Super groups')

    def visible_direct_subgroups_5(self, group):
        subgroups = group.get_direct_subgroups()
        subgroups = subgroups.with_user_perms(self.request.user.id,
                                              perms.SEE_CG)
        subgroups = subgroups[:LIST_PREVIEW_LEN+1]
        return ', '.join(_truncate_list([str(sg) for sg in subgroups]))
    visible_direct_subgroups_5.short_description = ugettext_lazy(
        'Sub groups')

    def rendered_fields(self, group):
        if group.field_group:
            fields = group.contactfield_set.all()
            if fields:
                return html.format_html_join(
                        ', ',
                        '<a href="{}">{}</a>',
                        ((f.get_absolute_url(), f.name) for f in fields))

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

    def flags(self, group):
        res = ''
        if group.system:
            res += (
                '<img src="{static}ngw/lock.png" alt="{title}"'
                ' title="{title}:\n{title_long}" width="10" height="10"'
                ' style="margin-left:2px">'
                .format(static=settings.STATIC_URL,
                        title=_('Locked'),
                        title_long=_('System is using that group.'
                                     ' Changes are restricted.')))
        if group.sticky:
            res += (
                '<img src="{static}ngw/sticky.png" alt="{title}"'
                ' title="{title}:\n{title_long}" width="10" height="10"'
                ' style="margin-left:2px">'
                .format(static=settings.STATIC_URL,
                        title=_('Sticky'),
                        title_long=_('Inherited membership is permanent.')))
        if group.virtual:
            res += (
                '<img src="{static}ngw/virtual.png" alt="{title}"'
                ' title="{title}:\n{title_long}" width="10" height="10"'
                ' style="margin-left:2px">'
                .format(static=settings.STATIC_URL,
                        title=_('Virtual'),
                        title_long=_("That group doesn't have direct members.")
                        ))
        if group.field_group:
            res += (
                '<img src="{static}ngw/has_fields.png" alt="{title}"'
                ' title="{title}:\n{title_long}" width="10" height="10"'
                ' style="margin-left:2px">'
                .format(static=settings.STATIC_URL,
                        title=_('Has fields'),
                        title_long=_('Being a members yields new fields.')))

        return mark_safe(res)
    flags.short_description = ugettext_lazy('Flags')

    def get_root_queryset(self):
        return (ContactGroup
                .objects.filter(date=None)
                .with_user_perms(self.request.user.id, perms.SEE_CG))

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

class EventListView(NgwUserAcl, NgwListView):
    list_display = (
        'name', 'date', 'days', 'description_not_too_long',
        'busy_nice',
        'budget_code',
        'visible_member_count',
        )
    list_display_links = 'name',
    search_fields = 'name', 'description', 'budget_code', 'date'

    actions = (
        'action_mark_busy',
        'action_mark_available',
        'action_csv_export',  # See NgwListView
    )

    # def get_list_display(self, request):
    #    columns = [
    #        'name', 'date', 'days', 'description_not_too_long',
    #        'budget_code']
    #    if request.method == 'POST':
    #        querydict = request.POST
    #    else:
    #        querydict = request.GET
    #    if querydict.get('showmembers', 0):
    #        columns += ['visible_member_count']
    #    return columns

    def days(self, group):
        delta = group.end_date - group.date
        return delta.days + 1
    days.short_description = ugettext_lazy('Days')
    days.admin_order_field = 'days'

    def busy_nice(self, group):
        if group.busy:
            return mark_safe('<span class=iconbusy></span>')
    busy_nice.short_description = ugettext_lazy('Members unavailable')
    busy_nice.admin_order_field = 'busy'

    def visible_member_count(self, group):
        if group.userperms & perms.SEE_MEMBERS:
            # This is inefficient (about 2 extra seconds):
            return group.get_members_count()
            # return group.member_count
        else:
            return _('Not available')
    visible_member_count.short_description = ugettext_lazy('Members')

    def get_root_queryset(self):
        return (ContactGroup.objects
                .filter(date__isnull=False)
                .filter(perso_unavail=False)
                # .with_counts() is too slow
                .with_user_perms(self.request.user.id, perms.SEE_CG)
                # days is used by sort:
                .extra(select={
                    'days': 'contact_group.end_date - contact_group.date'})
                )

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Select an event')
        context['objtype'] = ContactGroup
        context['nav'] = Navbar(('events', _('events')))

        context.update(kwargs)
        return super().get_context_data(**context)

    def action_mark_busy(self, request, queryset):
        queryset_ok = queryset.extra(where=(
            "v_cig_perm.flags & 128 != 0".format(perms.CHANGE_CG),
            "not busy"))
        ids = [row.id for row in queryset_ok]
        if ids:
            ContactGroup.objects.filter(id__in=ids).update(busy=True)
            messages.add_message(
                request, messages.SUCCESS,
                ungettext('One group was updated.',
                          '{nb} groups were updated.',
                          len(ids))
                    .format(nb=len(ids)))
        queryset_nok = queryset.extra(where=(
            "v_cig_perm.flags & 128 = 0".format(perms.CHANGE_CG),
            "not busy"))
        ids = [row.id for row in queryset_nok]
        if ids:
            messages.add_message(
                request, messages.ERROR,
                ungettext("One group was not updated because you don't have"
                          " the permission to change it.",
                          "{nb} groups were not updated because you don't"
                          " have the permission to change then.",
                          len(ids))
                    .format(nb=len(ids)))
    action_mark_busy.short_description = ugettext_lazy(
            "Update: members are unavailable")

    def action_mark_available(self, request, queryset):
        queryset_ok = queryset.extra(where=(
            "v_cig_perm.flags & 128 != 0".format(perms.CHANGE_CG),
            "busy"))
        ids = [row.id for row in queryset_ok]
        if ids:
            ContactGroup.objects.filter(id__in=ids).update(busy=False)
            messages.add_message(
                request, messages.SUCCESS,
                ungettext('One group was updated.',
                          '{nb} groups were updated.',
                          len(ids))
                    .format(nb=len(ids)))
        queryset_nok = queryset.extra(where=(
            "v_cig_perm.flags & 128 = 0".format(perms.CHANGE_CG),
            "busy"))
        ids = [row.id for row in queryset_nok]
        if ids:
            messages.add_message(
                request, messages.ERROR,
                ungettext("One group was not updated because you don't have"
                          " the permission to change it.",
                          "{nb} groups were not updated because you don't"
                          " have the permission to change then.",
                          len(ids))
                    .format(nb=len(ids)))
    action_mark_available.short_description = ugettext_lazy(
            "Update: members are available")


#######################################################################
#
# Calendar
#
#######################################################################

class CalendarView(NgwUserAcl, TemplateView):
    template_name = 'calendar.html'

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Calendar')
        context['nav'] = Navbar(('events', _('events')))
        context['nav'].add_component(('calendar', _('calendar')))
        context['weekdaystart'] = formats.get_format('FIRST_DAY_OF_WEEK')
        context.update(kwargs)
        return super().get_context_data(**context)


# ----------------------------------------------------------------------


def safe_new_datetime(d):
    kw = [d.year, d.month, d.day]
    if isinstance(d, datetime):
        kw.extend([d.hour, d.minute, d.second, d.microsecond, d.tzinfo])
    return datetime(*kw)


def safe_new_date(d):
    return date(d.year, d.month, d.day)


def get_date_stamp(d):
    """获取当前日期和1970年1月1日之间的毫秒数"""
    return int(time.mktime(d.timetuple())*1000)


def get_ms_json_date_format(d):
    """获取MS Ajax Json Data Format /Date(@tickets)/"""
    stamp = get_date_stamp(d)
    return '/Date({})/'.format(stamp)


class DatetimeJSONEncoder(json.JSONEncoder):
    """可以序列化时间的JSON"""
    # DATE_FORMAT = "%Y-%m-%d"
    TIME_FORMAT = "%H:%M:%S"

    def default(self, o):
        if isinstance(o, datetime):
            d = safe_new_datetime(o)
            return get_ms_json_date_format(d)
        elif isinstance(o, date):
            d = safe_new_date(o)
            return get_ms_json_date_format(d)
        # elif isinstance(o, time):
        #    return o.strftime(self.TIME_FORMAT)
        elif isinstance(o, decimal.Decimal):
            return str(o)
        else:
            return super().default(o)

# ----------------------------------------------------------------------


class CalendarQueryView(View):
    def post(self, request, *args, **kwargs):
        '''
        parameters are:
        showdate: 12/18/2014
        viewtype: week
        timezone: 1
        '''

        if request.method == 'POST':
            querydict = request.POST
        else:
            querydict = request.GET

        # Show only events relative to that contact:
        cid = self.kwargs.get('cid', None)
        if cid:
            cid = int(cid)

        showdate = querydict.get('showdate')
        # print('showdate:', showdate)
        # showdate = datetime.strptime(showdate, '%d/%m/%Y').date()
        showdate = datetime.strptime(showdate, '%m/%d/%Y').date()
        # print('showdate:', showdate)

        viewtype = querydict.get('viewtype', 'month')

        year = showdate.year
        month = showdate.month
        dow_first, nb_days = calendar.monthrange(year, month)
        first_day_of_week = formats.get_format('FIRST_DAY_OF_WEEK')

        if viewtype == 'month':
            # min_date = date(year, month, 1)
            # max_date = date(year, month, nb_days)
            min_date = date(year, month, 1) - timedelta(
                days=(dow_first-first_day_of_week+8) % 7)
            extra_days = (34-(nb_days+dow_first-first_day_of_week)) % 7
            max_date = date(year, month, nb_days) + timedelta(days=extra_days)
        elif viewtype == 'week':
            weekday = calendar.weekday(year, month, showdate.day)
            min_date = showdate - timedelta(
                days=(weekday-first_day_of_week+8) % 7)
            max_date = min_date + timedelta(days=6)
        else:  # viewtype == 'day':
            min_date = showdate
            max_date = showdate

        str_min_date = min_date.strftime('%Y-%m-%d')
        str_max_date = max_date.strftime('%Y-%m-%d')
        # print(str_min_date, str_max_date)

        qs = ContactGroup.objects.with_user_perms(request.user.id,
                                                  perms.SEE_CG)

        if cid is not None:
            qs = qs.with_member(cid)

        # Don't show personnal unavailability events
        qs = qs.filter(perso_unavail=False)

        qs = qs.filter(
            # start within boundaries:
            Q(date__gte=str_min_date, date__lte=str_max_date)
            # or end within boundaries:
            | Q(end_date__gte=str_min_date, end_date__lte=str_max_date)
            # or start before and end after (this is a long event):
            | Q(date__lte=str_min_date, end_date__gte=str_max_date))
        qs = qs.order_by('date')
        # qs = qs.distinct()

        events = []
        for group in qs:
            end_date = group.end_date
            if not end_date:
                end_date = group.date
            events.append([
                group.id,
                group.name,
                group.date,
                end_date,
                True,  # all day event
                bool(end_date) and group.date != group.end_date,  # crossday
                0,  # recurring
                group.id % 22,  # theme id
                0,  # can be drag
                None,  # location
                '',  # participants
            ])
            # print(events[-1])
        response = {
            'events': events,
            'issort': True,
            'start': min_date,
            'end': max_date,
            'error': None,
        }
        jsonresponse = json.dumps(response, cls=DatetimeJSONEncoder)

        # dates must be transformed in pseuso-regular expressions
        jsonresponse = (
            re.compile(r'"/Date\((\d+)\)/"')
              .sub('"\\/Date(\\1)\\/"', jsonresponse))
        return HttpResponse(jsonresponse, content_type='application/json')
    get = post


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
        if cg.perso_unavail:
            return HttpResponseRedirect(cg.get_absolute_url() + 'summary')
        if cg.userperms & perms.SEE_MEMBERS:
            return HttpResponseRedirect(cg.get_absolute_url() + 'members/')
        if cg.userperms & perms.VIEW_NEWS:
            return HttpResponseRedirect(cg.get_absolute_url() + 'news/')
        if cg.userperms & perms.VIEW_FILES:
            return HttpResponseRedirect(cg.get_absolute_url() + 'files/')
        if cg.userperms & perms.VIEW_MSGS:
            return HttpResponseRedirect(cg.get_absolute_url() + 'messages/')
        return HttpResponseRedirect(cg.get_absolute_url() + 'summary')


#######################################################################
#######################################################################

class GroupDetailView(InGroupAcl, DetailView):
    pk_url_kwarg = 'gid'
    model = ContactGroup
    template_name = 'group_summary.html'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.SEE_CG:
            raise PermissionDenied

    # def get_object(self, queryset=None):
    #     msg = super().get_object(queryset)
    #     # Check the group match the one of the url
    #     if msg.group_id != self.contactgroup.id:
    #         raise PermissionDenied
    #     return msg

    def get_context_data(self, **kwargs):
        cg = self.contactgroup

        context = {}

        context['title'] = _(
            'Summary of group {groupname}').format(
            groupname=cg.name)

        if cg.perso_unavail:
            membership = ContactInGroup.objects.get(group_id=cg.id)
            contact = membership.contact

            context['contact'] = contact
            context['contactlink'] = '/contacts/{}/'.format(contact.id)

        context['nav'] = cg.get_smart_navbar()
        context['nav'].add_component(('summary', _('summary')))
        context['active_submenu'] = 'summary'

        context.update(kwargs)
        return super().get_context_data(**context)


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
            ('D', _('Canceled members')),
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
                    'display': newdisplay}),
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
        if 'D' in display:
            wanted_flags |= perms.CANCELED
        if 'a' in display:
            wanted_flags |= perms.ADMIN_ALL

        if not wanted_flags:
            # Show nothing
            q = q.filter('FALSE')
        elif 'g' not in display:
            # Not interested in inheritance:
            q = q.filter(
                'EXISTS ('
                '   SELECT *'
                '   FROM contact_in_group'
                '   WHERE contact_id=contact.id'
                '   AND group_id={}'
                '   AND flags & {} <> 0'
                ')'
                .format(cg.id, wanted_flags))
        else:
            # We want inherited people
            or_conditions = []
            # The local flags
            or_conditions.append(
                'EXISTS ('
                '   SELECT *'
                '   FROM contact_in_group'
                '   WHERE contact_id=contact.id'
                '   AND group_id={}'
                '   AND flags & {} <> 0'
                ')'
                .format(cg.id, wanted_flags))
            # The inherited memberships/invited/declined
            or_conditions.append(
                'EXISTS ('
                '   SELECT *'
                '   FROM contact_in_group'
                '   WHERE contact_id=contact.id'
                '   AND group_id IN (SELECT self_and_subgroups({}))'
                '   AND flags & {} <> 0'
                ')'
                .format(cg.id, wanted_flags & (perms.MEMBER
                                               | perms.INVITED
                                               | perms.DECLINED
                                               | perms.CANCELED)))
            # The inherited admins
            or_conditions.append(
                'EXISTS ('
                '   SELECT *'
                '   FROM contact_in_group'
                '   WHERE contact_in_group.contact_id=contact.id'
                '   AND group_id IN (SELECT self_and_subgroups(father_id)'
                '   FROM group_manage_group WHERE subgroup_id={}'
                '   AND group_manage_group.flags & {} <> 0'
                '   )'
                ' AND contact_in_group.flags & 1 <> 0)'
                .format(cg.id, wanted_flags & perms.ADMIN_ALL))

            q = q.filter('(' + ') OR ('.join(or_conditions) + ')')
            return q


class AvailableFilter(filters.SimpleListFilter):
    '''
    Filter people according to their availability (member/invited in another
    group...)
    '''
    title = ugettext_lazy('availability')
    parameter_name = 'busy'

    def __init__(self, request, params, model, view):
        super().__init__(request, params, model, view)
        self.contactgroup = view.contactgroup

    def lookups(self, request, view):
        # busy query value can be:
        #   0: for not in another full-time group
        #   1: perms.MEMBER
        #   2: perms.INVITED
        #   3: perms.MEMBER | perms.INVITED (both over several groups)
        return (
            ('02', _('Available')),
            ('0', _('Available and not invited elsewhere')),
            ('2', _('Available but invited elsewhere')),
            ('13', _('Unavailable')),
        )

    def queryset(self, request, q):
        busy = self.value()
        if not busy:  # doesn't match '0'
            return q
        gid = self.contactgroup.id
        q.add_busy(gid)
        colname = 'COALESCE(busy,0)'
        or_conditions = []
        for digit in busy:
            or_conditions.append('{} = {}'.format(colname, digit))
        q = q.filter('(' + ') OR ('.join(or_conditions) + ')')
        print('(' + ') OR ('.join(or_conditions) + ')')
        return q


class GroupMemberListView(InGroupAcl, BaseContactListView):
    template_name = 'group_members.html'
    list_filter = BaseContactListView.list_filter + (
            MemberFilter,
            AvailableFilter
            )

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.SEE_MEMBERS:
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Contacts of group {}').format(cg)

        context['nav'] = cg.get_smart_navbar() \
                           .add_component(('members', _('members')))
        context['active_submenu'] = 'members'
        context.update(kwargs)
        result = super().get_context_data(**context)
        return result

        # context = InGroupAcl.get_context_data(self, **context)
        # context = BaseContactListView.get_context_data(self, **context)
        # return context

    def get_actions(self, request):
        actions = super().get_actions(request)
        send_message = self.get_action('action_send_message')
        actions[send_message[1]] = send_message
        if self.contactgroup.id != GROUP_EVERYBODY:
            remove_from_group = self.get_action('action_remove_from_group')
            actions[remove_from_group[1]] = remove_from_group
        return actions

    def action_send_message(self, request, queryset):
        ids = request.POST.getlist('_selected_action')
        return HttpResponseRedirect('send_message?ids=' + ','.join(ids))
    action_send_message.short_description = ugettext_lazy(
        "Send a message (external storage)")

    def action_remove_from_group(self, request, queryset):
        ids = request.POST.getlist('_selected_action')
        return HttpResponseRedirect('remove_many?ids=' + ','.join(ids))
    action_remove_from_group.short_description = ugettext_lazy(
            "Force remove members from this group")


#######################################################################
#
# Group edit
#
#######################################################################

class ContactGroupForm(forms.ModelForm):
    class Meta:
        model = ContactGroup
        fields = [
            'name', 'description', 'date', 'end_date', 'busy',
            # 'perso_unavail',
            'budget_code',
            'sticky',
            'virtual',
            'field_group', 'mailman_address']
        widgets = {
            'date': AdminDateWidget,
            # (attrs={'onchange': mark_safe("alert('ok');")}),
            'end_date': AdminDateWidget,
            'busy': forms.widgets.RadioSelect(
                choices=(
                    (
                        True,
                        _('Yes: Members become unavailable')
                    ), (
                        False,
                        _('No: Allow other events at the same time')
                    )),
                ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        self.user = user
        self.request = kwargs.pop('request')
        instance = kwargs.get('instance', None)
        unavail_cid = kwargs.pop('unavail_cid', None)
        assert unavail_cid is None, \
            'unavail_cid is not empty for regular ContactGroupForm'
        super().__init__(*args, **kwargs)

        # Only show visible groups
        visible_groups_choices = [
            (g.id, str(g))
            for g in ContactGroup.objects.with_user_perms(
                user.id, perms.SEE_CG)]

        # Super groups
        if instance:
            field_initial = instance.get_visible_direct_supergroups_ids(
                user.id)
        else:
            field_initial = None
        self.fields['direct_supergroups'] = forms.MultipleChoiceField(
            label=_('Direct supergroups'),
            required=False,
            help_text=_('Members will automatically be granted membership in'
                        ' these groups.'),
            widget=FilteredSelectMultiple(_('groups'), False),
            choices=visible_groups_choices,
            initial=field_initial)

        # Add fields for kind of permissions
        event_default_perms = Config.get_event_default_perms()

        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_{}_groups'.format(flag)
            if instance:
                intflag = perms.FLAGTOINT[flag]
                field_initial = instance.get_visible_mananger_groups_ids(
                    user.id, intflag)
            else:
                if flag == 'o':
                    default_group_id = user.get_fieldvalue_by_id(
                        FIELD_DEFAULT_GROUP)
                    assert default_group_id, \
                        "User doesn't have a default group"
                    field_initial = int(default_group_id),
                else:
                    field_initial = event_default_perms.get(flag, None)
            self.fields[field_name] = forms.MultipleChoiceField(
                label=perms.FLAGGROUPLABEL[flag],
                required=False,
                help_text=perms.FLAGGROUPHELP[flag],
                widget=FilteredSelectMultiple(_('groups'), False),
                choices=visible_groups_choices,
                initial=field_initial)

    def clean(self):
        data = super().clean()
        start_date = data.get('date', None)
        end_date = data.get('end_date', None)
        if end_date:
            if not start_date:
                self.add_error(
                    'date',
                    _('That field is required when you have an end date.'))
            elif end_date < start_date:
                self.add_error(
                    'end_date',
                    _('The end date must be after the start date.'))
        else:
            # There is no end date
            if start_date:
                # use start date is available
                data['end_date'] = data['date']
            # else this is a permanent group without any date

        # busy check
        busy = data.get('busy', None)
        if start_date:
            if 'busy' not in self.data:  # do use uncleaned data from self
                self.add_error('busy', forms.ValidationError(
                    _('This field is required'),
                    code='required'))
        else:
            # Be permissive about choices not made for groups
            if busy is None:
                data['busy'] = False
            elif busy:
                self.add_error('busy', forms.ValidationError(
                    _('Busy flag requires dates.'),
                    code='invalid'))

        return data

    def save(self, commit=True):
        is_creation = self.instance.pk is None
        data = self.cleaned_data

        if is_creation:
            was_sticky = False
        else:
            was_sticky = ContactGroup.objects.get(pk=self.instance.pk).sticky

        # Save the base fields
        cg = super().save(commit)

        # Update the members if it's now sticky
        if cg.sticky and not was_sticky:
            logging.warning("Group %s has become sticky.", cg)
            members = cg.get_all_members()
            members = members.extra(where=["""
                NOT EXISTS (
                    SELECT *
                    FROM contact_in_group
                    WHERE contact_in_group.contact_id=contact.id
                        AND contact_in_group.group_id={group_id}
                        AND flags & {member_flag} <> 0
                )""".format(group_id=cg.id,
                            member_flag=perms.MEMBER)])
            cg.set_member_n(self.request, members, '+m')

        # Update the super groups
        old_direct_supergroups_ids = set(
            cg.get_visible_direct_supergroups_ids(self.user.id))
        new_direct_supergroups_id = set(
            [int(i) for i in data['direct_supergroups']])
        if cg.id != GROUP_EVERYBODY and not new_direct_supergroups_id:
            new_direct_supergroups_id = {GROUP_EVERYBODY}

        supergroup_added = (new_direct_supergroups_id
                            - old_direct_supergroups_ids)
        supergroup_removed = (old_direct_supergroups_ids
                              - new_direct_supergroups_id)

        print('supergroup_added=', supergroup_added)
        print('supergroup_removed=', supergroup_removed)
        for sgid in supergroup_added:
            GroupInGroup(father_id=sgid, subgroup_id=cg.id).save()
        for sgid in supergroup_removed:
            (GroupInGroup.objects
             .get(father_id=sgid, subgroup_id=cg.id).delete())

        # Update the administrative groups
        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_{}_groups'.format(flag)
            intflag = perms.FLAGTOINT[flag]
            old_groups_ids = set(
                cg.get_visible_mananger_groups_ids(self.user.id, intflag))
            new_groups_ids = set([int(ogid) for ogid in data[field_name]])
            # print('flag', flag, 'old_groups_ids', old_groups_ids)
            # print('flag', flag, 'new_groups_ids', new_groups_ids)
            groups_added = new_groups_ids - old_groups_ids
            groups_removed = old_groups_ids - new_groups_ids
            print('flag', flag, 'groups_added=', groups_added)
            print('flag', flag, 'groups_removed=', groups_removed)
            if (not is_creation
               and (groups_added or groups_removed)
               and not perms.c_operatorof_cg(self.user.id, cg.id)):
                # Only operators can change permissions
                raise PermissionDenied
            for ogid in groups_added:
                try:
                    gmg = GroupManageGroup.objects.get(
                        father_id=ogid, subgroup_id=cg.id)
                except GroupManageGroup.DoesNotExist:
                    gmg = GroupManageGroup(
                        father_id=ogid, subgroup_id=cg.id, flags=0)
                gmg.flags |= intflag
                gmg.save()
            for ogid in groups_removed:
                gmg = GroupManageGroup.objects.get(father_id=ogid,
                                                   subgroup_id=cg.id)
                gmg.flags &= ~ intflag
                if gmg.flags:
                    gmg.save()
                else:
                    gmg.delete()

        return cg


class EventForm(forms.ModelForm):
    class Meta:
        model = ContactGroup
        fields = [
            'name', 'description', 'date', 'end_date', 'busy',
            # 'perso_unavail',
            'budget_code',
            # 'sticky',
            # 'virtual',
            # 'field_group',
            'mailman_address']
        widgets = {
            'date': AdminDateWidget,
            # (attrs={'onchange': mark_safe("alert('ok');")}),
            'end_date': AdminDateWidget,
            'busy': forms.widgets.RadioSelect(
                choices=(
                    (
                        True,
                        _('Yes: Members become unavailable')
                    ), (
                        False,
                        _('No: Allow other events at the same time')
                    )),
                ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        self.user = user
        self.request = kwargs.pop('request')
        instance = kwargs.get('instance', None)
        unavail_cid = kwargs.pop('unavail_cid', None)
        assert unavail_cid is None, \
            'unavail_cid is not empty for regular ContactGroupForm'
        super().__init__(*args, **kwargs)

        # Only show visible groups
        visible_groups_choices = [
            (g.id, str(g))
            for g in ContactGroup.objects.with_user_perms(
                user.id, perms.SEE_CG)]

        # Super groups
        if instance:
            field_initial = instance.get_visible_direct_supergroups_ids(
                user.id)
        else:
            field_initial = None
        self.fields['direct_supergroups'] = forms.MultipleChoiceField(
            label=_('Direct supergroups'),
            required=False,
            help_text=_('Members will automatically be granted membership in'
                        ' these groups.'),
            widget=FilteredSelectMultiple(_('groups'), False),
            choices=visible_groups_choices,
            initial=field_initial)

        # Add fields for kind of permissions
        event_default_perms = Config.get_event_default_perms()

        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_{}_groups'.format(flag)
            if instance:
                intflag = perms.FLAGTOINT[flag]
                field_initial = instance.get_visible_mananger_groups_ids(
                    user.id, intflag)
            else:
                if flag == 'o':
                    default_group_id = user.get_fieldvalue_by_id(
                        FIELD_DEFAULT_GROUP)
                    assert default_group_id, \
                        "User doesn't have a default group"
                    field_initial = int(default_group_id),
                else:
                    field_initial = event_default_perms.get(flag, None)
            self.fields[field_name] = forms.MultipleChoiceField(
                label=perms.FLAGGROUPLABEL[flag],
                required=False,
                help_text=perms.FLAGGROUPHELP[flag],
                widget=FilteredSelectMultiple(_('groups'), False),
                choices=visible_groups_choices,
                initial=field_initial)

    def clean(self):
        data = super().clean()
        start_date = data.get('date', None)
        end_date = data.get('end_date', None)
        if end_date:
            if not start_date:
                self.add_error(
                    'date',
                    _('That field is required when you have an end date.'))
            elif end_date < start_date:
                self.add_error(
                    'end_date',
                    _('The end date must be after the start date.'))
        else:
            # There is no end date
            if start_date:
                # use start date is available
                data['end_date'] = data['date']
            # else this is a permanent group without any date

        # busy check
        busy = data.get('busy', None)
        if start_date:
            if 'busy' not in self.data:  # do use uncleaned data from self
                self.add_error('busy', forms.ValidationError(
                    _('This field is required'),
                    code='required'))
        else:
            # Be permissive about choices not made for groups
            if busy is None:
                data['busy'] = False
            elif busy:
                self.add_error('busy', forms.ValidationError(
                    _('Busy flag requires dates.'),
                    code='invalid'))

        return data

    def save(self, commit=True):
        is_creation = self.instance.pk is None
        data = self.cleaned_data

        if is_creation:
            was_sticky = False
        else:
            was_sticky = ContactGroup.objects.get(pk=self.instance.pk).sticky

        # Save the base fields
        cg = super().save(commit)

        # Update the members if it's now sticky
        if cg.sticky and not was_sticky:
            logging.warning("Group %s has become sticky.", cg)
            members = cg.get_all_members()
            members = members.extra(where=["""
                NOT EXISTS (
                    SELECT *
                    FROM contact_in_group
                    WHERE contact_in_group.contact_id=contact.id
                        AND contact_in_group.group_id={group_id}
                        AND flags & {member_flag} <> 0
                )""".format(group_id=cg.id,
                            member_flag=perms.MEMBER)])
            cg.set_member_n(self.request, members, '+m')

        # Update the super groups
        old_direct_supergroups_ids = set(
            cg.get_visible_direct_supergroups_ids(self.user.id))
        new_direct_supergroups_id = set(
            [int(i) for i in data['direct_supergroups']])
        if cg.id != GROUP_EVERYBODY and not new_direct_supergroups_id:
            new_direct_supergroups_id = {GROUP_EVERYBODY}

        supergroup_added = (new_direct_supergroups_id
                            - old_direct_supergroups_ids)
        supergroup_removed = (old_direct_supergroups_ids
                              - new_direct_supergroups_id)

        print('supergroup_added=', supergroup_added)
        print('supergroup_removed=', supergroup_removed)
        for sgid in supergroup_added:
            GroupInGroup(father_id=sgid, subgroup_id=cg.id).save()
        for sgid in supergroup_removed:
            (GroupInGroup.objects
             .get(father_id=sgid, subgroup_id=cg.id).delete())

        # Update the administrative groups
        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_{}_groups'.format(flag)
            intflag = perms.FLAGTOINT[flag]
            old_groups_ids = set(
                cg.get_visible_mananger_groups_ids(self.user.id, intflag))
            new_groups_ids = set([int(ogid) for ogid in data[field_name]])
            # print('flag', flag, 'old_groups_ids', old_groups_ids)
            # print('flag', flag, 'new_groups_ids', new_groups_ids)
            groups_added = new_groups_ids - old_groups_ids
            groups_removed = old_groups_ids - new_groups_ids
            print('flag', flag, 'groups_added=', groups_added)
            print('flag', flag, 'groups_removed=', groups_removed)
            if (not is_creation
               and (groups_added or groups_removed)
               and not perms.c_operatorof_cg(self.user.id, cg.id)):
                # Only operators can change permissions
                raise PermissionDenied
            for ogid in groups_added:
                try:
                    gmg = GroupManageGroup.objects.get(
                        father_id=ogid, subgroup_id=cg.id)
                except GroupManageGroup.DoesNotExist:
                    gmg = GroupManageGroup(
                        father_id=ogid, subgroup_id=cg.id, flags=0)
                gmg.flags |= intflag
                gmg.save()
            for ogid in groups_removed:
                gmg = GroupManageGroup.objects.get(father_id=ogid,
                                                   subgroup_id=cg.id)
                gmg.flags &= ~ intflag
                if gmg.flags:
                    gmg.save()
                else:
                    gmg.delete()

        return cg


class PersonalUnavailForm(forms.ModelForm):
    class Meta:
        model = ContactGroup
        fields = [
            'name',
            'date', 'end_date',
            'description',
            ]
        widgets = {
            'date': AdminDateWidget,
            'end_date': AdminDateWidget,
        }
        # Note that fieldsets looks unimplemented for simple FormMixin
        # They are admin-specific
        # fieldsets = [
        #         ('TEST', {
        #             'fields': [
        #                 'name',
        #                 'date', 'end_date',
        #                 ]}),
        #         ('Permissions', {
        #             'fields': [
        #                 'description',
        #                 ]}),
        #         ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        self.user = user
        self.request = kwargs.pop('request')
        instance = kwargs.get('instance', None)
        unavail_cid = kwargs.pop('unavail_cid', None)
        self.contact_id = unavail_cid
        super().__init__(*args, **kwargs)

        self.fields['date'].required = True
        self.fields['end_date'].required = True

        # Only show visible groups
        visible_groups_choices = [
            (g.id, str(g))
            for g in ContactGroup.objects.with_user_perms(
                user.id, perms.SEE_CG)]

        # Add fields for kind of permissions
        event_default_perms = Config.get_event_default_perms()

        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_{}_groups'.format(flag)
            if instance:
                intflag = perms.FLAGTOINT[flag]
                field_initial = instance.get_visible_mananger_groups_ids(
                    user.id, intflag)
            else:
                if flag == 'o':
                    default_group_id = user.get_fieldvalue_by_id(
                        FIELD_DEFAULT_GROUP)
                    assert default_group_id, \
                        "User doesn't have a default group"
                    field_initial = int(default_group_id),
                else:
                    field_initial = event_default_perms.get(flag, None)
            self.fields[field_name] = forms.MultipleChoiceField(
                label=perms.FLAGGROUPLABEL[flag],
                required=False,
                help_text=perms.FLAGGROUPHELP[flag],
                widget=FilteredSelectMultiple(_('groups'), False),
                choices=visible_groups_choices,
                initial=field_initial)

    def clean(self):
        data = super().clean()
        data['busy'] = True
        data['perso_unavail'] = True
        return data

    def save(self, commit=True):
        is_creation = self.instance.pk is None
        data = self.cleaned_data

        # Save the base fields
        cg = super().save(commit)

        if is_creation:
            cg.busy = True
            cg.perso_unavail = True
            cg.save()

            # Super group: Only "Contacts"
            GroupInGroup(father_id=GROUP_EVERYBODY, subgroup_id=cg.id).save()
            # Add the one member:
            ContactInGroup(
                contact_id=self.contact_id,
                group_id=cg.id,
                flags=perms.MEMBER
                ).save()

        # Update the administrative groups
        for flag in 'oveEcCfFnNuUxX':
            field_name = 'admin_{}_groups'.format(flag)
            intflag = perms.FLAGTOINT[flag]
            old_groups_ids = set(
                cg.get_visible_mananger_groups_ids(self.user.id, intflag))
            new_groups_ids = set([int(ogid) for ogid in data[field_name]])
            # print('flag', flag, 'old_groups_ids', old_groups_ids)
            # print('flag', flag, 'new_groups_ids', new_groups_ids)
            groups_added = new_groups_ids - old_groups_ids
            groups_removed = old_groups_ids - new_groups_ids
            print('flag', flag, 'groups_added=', groups_added)
            print('flag', flag, 'groups_removed=', groups_removed)
            if (not is_creation
               and (groups_added or groups_removed)
               and not perms.c_operatorof_cg(self.user.id, cg.id)):
                # Only operators can change permissions
                raise PermissionDenied
            for ogid in groups_added:
                try:
                    gmg = GroupManageGroup.objects.get(
                        father_id=ogid, subgroup_id=cg.id)
                except GroupManageGroup.DoesNotExist:
                    gmg = GroupManageGroup(
                        father_id=ogid, subgroup_id=cg.id, flags=0)
                gmg.flags |= intflag
                gmg.save()
            for ogid in groups_removed:
                gmg = GroupManageGroup.objects.get(father_id=ogid,
                                                   subgroup_id=cg.id)
                gmg.flags &= ~ intflag
                if gmg.flags:
                    gmg.save()
                else:
                    gmg.delete()

        return cg


class GroupEditMixin(ModelFormMixin):
    template_name = 'edit.html'
    model = ContactGroup
    pk_url_kwarg = 'gid'

    def get_form_class(self):
        if self.object:
            cg = self.object
            if cg.perso_unavail:
                return PersonalUnavailForm
            if cg.date:
                return EventForm
        if getattr(self.request, 'unavail_cid', None):
            return PersonalUnavailForm
        return ContactGroupForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['request'] = self.request
        # For personnal unavailabilities:
        kwargs['unavail_cid'] = self.request.unavail_cid
        return kwargs

    def form_valid(self, form):
        request = self.request
        cg = form.save()

        messages.add_message(
            request, messages.SUCCESS,
            _('Group {} has been changed successfully.').format(cg))

        cg.check_static_folder_created()
        Contact.objects.check_login_created(request)  # subgroups change

        if self.pk_url_kwarg not in self.kwargs:  # new added instance
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

    def get_initial(self):
        result = super().get_initial()
        if self.object is None:
            result['busy'] = None  # Force no default value
        return result

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing {}').format(self.object)
            id = self.object.id
        else:
            title = (_('Adding a new {}')
                     .format(ContactGroup.get_class_verbose_name()))
            id = None

        context['title'] = title
        context['id'] = id
        context['objtype'] = ContactGroup

        if id:
            context['nav'] = self.object.get_smart_navbar()
            context['nav'].add_component(('edit', _('edit')))
        else:
            context['nav'] = Navbar(ContactGroup.get_class_navcomponent())
            context['nav'].add_component(('add', _('add')))

        context.update(kwargs)
        return super().get_context_data(**context)


class GroupEditView(InGroupAcl, GroupEditMixin, UpdateView):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied

    def get(self, request, *args, **kwargs):
        contact_id = kwargs.get('cid', None)  # personnal unavailabilities
        request.unavail_cid = contact_id
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        contact_id = kwargs.get('cid', None)  # personnal unavailabilities
        request.unavail_cid = contact_id
        return super().post(request, *args, **kwargs)


class GroupCreateView(NgwUserAcl, GroupEditMixin, CreateView):
    def get(self, request, *args, **kwargs):
        contact_id = kwargs.get('cid', None)  # personnal unavailabilities
        request.unavail_cid = contact_id

        default_group_id = request.user.get_fieldvalue_by_id(
            FIELD_DEFAULT_GROUP)
        if not default_group_id:
            messages.add_message(request, messages.WARNING, _(
                'You must define a default group before you can create a'
                ' group.'))
            return HttpResponseRedirect(
                request.user.get_absolute_url()+'default_group')
        default_group_id = int(default_group_id)
        if not request.user.is_member_of(default_group_id):
            messages.add_message(request, messages.WARNING, _(
                'You no longer are member of your default group.'
                ' Please define a new default group.'))
            return HttpResponseRedirect(
                request.user.get_absolute_url()+'default_group')
        if not perms.c_can_see_cg(request.user.id, default_group_id):
            messages.add_message(request, messages.WARNING, _(
                'You no longer are authorized to see your default group.'
                ' Please define a new default group.'))
            return HttpResponseRedirect(
                request.user.get_absolute_url()+'default_group')

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        contact_id = kwargs.get('cid', None)  # personnal unavailabilities
        request.unavail_cid = contact_id

        return super().post(request, *args, **kwargs)


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
                _('Group {} is locked and CANNOT be deleted.').format(cg.name))
            raise PermissionDenied
        return cg

    def get_context_data(self, **kwargs):
        context = {}
        if self.contactgroup:
            context['nav'] = self.contactgroup.get_smart_navbar()
            context['nav'].add_component(('delete', _('delete')))
        context.update(kwargs)
        return super().get_context_data(**context)

    def delete(self, request, *args, **kwargs):
        cg = self.get_object()
        # All subgroups will now have their fathers' fathers as direct fathers
        supergroups_ids = set(cg.get_direct_supergroups_ids())
        for subcg in cg.get_direct_subgroups():
            sub_super = set(subcg.get_direct_supergroups_ids())
            # print(repr(subcg), "had these fathers:", sub_super)
            sub_super = sub_super | supergroups_ids - {cg.id}
            if not sub_super:
                sub_super = {GROUP_EVERYBODY}
            # print(repr(subcg), "new fathers:", sub_super)
            subcg.set_direct_supergroups_ids(sub_super)
            # print(repr(subcg), "new fathers double check:",
            #       subcg.get_direct_supergroups_ids())
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
        # instance = kwargs.get('instance', None)
        self.request = kwargs.pop('request')
        self.user = kwargs.pop('user')
        self.contact = kwargs.pop('contact')
        self.group = kwargs.pop('group')
        super().__init__(*args, **kwargs)

    def clean(self):
        # TODO: improve conflicts/dependencies checking
        data = super().clean()
        flags = data['flags']
        membership_count = 0
        if flags & perms.MEMBER:
            membership_count += 1
        if flags & perms.INVITED:
            membership_count += 1
        if flags & perms.DECLINED:
            membership_count += 1
        if flags & perms.CANCELED:
            membership_count += 1
        if membership_count > 1:
            raise forms.ValidationError('Invalid flags combinaison')

        if flags == 0 and data['note']:
            raise forms.ValidationError(_(
                'You cannot have a note unless you select some flags too'))
        return data

    def save(self):
        newflags = self.cleaned_data['flags']

        flags_change_request = perms.int_to_flags(newflags)

        # cig = super().save(commit=False)  # Not called!
        self.group.set_member_n(
            self.request,
            [self.contact],
            flags_change_request)

        if newflags:
            cig = ContactInGroup.objects.get(
                    contact_id=self.contact.id,
                    group_id=self.group.id)
            cig.note = self.cleaned_data['note']
            cig.save()
            return cig
        else:
            return None


class ContactInGroupView(InGroupAcl, FormView):
    form_class = ContactInGroupForm
    template_name = 'contact_in_group.html'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_MEMBERS:
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group'] = self.contactgroup
        kwargs['contact'] = get_object_or_404(Contact,
                                              pk=int(self.kwargs['cid']))
        kwargs['request'] = self.request
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
        form.save()
        cg = self.contactgroup
        return HttpResponseRedirect(cg.get_absolute_url())

    def get_context_data(self, **kwargs):
        cid = int(self.kwargs['cid'])
        gid = int(self.kwargs['gid'])
        contact = get_object_or_404(Contact, pk=int(self.kwargs['cid']))
        cg = self.contactgroup

        context = {}
        context['title'] = _('Contact {contact} in group {group}').format(
            contact=contact,
            group=cg)
        context['contact'] = contact
        context['objtype'] = ContactInGroup
        inherited_info = ''

        automember_groups = (ContactGroup.objects.extra(where=[
            'EXISTS ('
            '   SELECT *'
            '   FROM contact_in_group'
            '   WHERE group_id IN (SELECT self_and_subgroups({}))'
            '   AND contact_id={} AND flags & {} <> 0'
            '   AND group_id=contact_group.id'
            ')'.format(gid, cid, perms.MEMBER)])
            .exclude(id=gid)
            .order_by('-date', 'name'))

        visible_automember_groups = automember_groups.with_user_perms(
            self.request.user.id, wanted_flags=perms.SEE_CG)

        invisible_automember_groups = automember_groups.extra(where=[
            'NOT EXISTS ('
            ' SELECT * FROM v_cig_perm'
            ' WHERE v_cig_perm.contact_id={}'
            ' AND v_cig_perm.group_id=contact_group.id'
            ' AND v_cig_perm.flags & {} <> 0)'
            .format(self.request.user.id, perms.SEE_CG)])

        if automember_groups:
            inherited_info += (
                _('Automatically member because member of subgroup(s)')
                + ':<ul>')
            for sub_cg in visible_automember_groups:
                inherited_info += '<li><a href=\"{url}\">{name}</a>'.format(
                    name=sub_cg,
                    url=sub_cg.get_absolute_url())
            if invisible_automember_groups:
                inherited_info += '<li>' + _('Hidden group(s)...')
            inherited_info += '</ul>'

        autoinvited_groups = (ContactGroup.objects.extra(where=[
            'EXISTS ('
            '   SELECT *'
            '   FROM contact_in_group'
            '   WHERE group_id IN (SELECT self_and_subgroups({}))'
            '   AND contact_id={}'
            '   AND flags & {} <> 0'
            '   AND group_id=contact_group.id'
            ')'.format(gid, cid, perms.INVITED)])
            .exclude(id=gid)
            .order_by('-date', 'name'))

        visible_autoinvited_groups = autoinvited_groups.with_user_perms(
            self.request.user.id, wanted_flags=perms.SEE_CG)

        invisible_autoinvited_groups = autoinvited_groups.extra(where=[
            'NOT EXISTS ('
            ' SELECT * FROM v_cig_perm'
            ' WHERE v_cig_perm.contact_id={}'
            ' AND v_cig_perm.group_id=contact_group.id'
            ' AND v_cig_perm.flags & {} <> 0)'
            .format(self.request.user.id, perms.SEE_CG)])

        if autoinvited_groups:
            inherited_info += (
                _('Automatically invited because invited in subgroup(s)')
                + ':<ul>')
            for sub_cg in visible_autoinvited_groups:
                inherited_info += '<li><a href=\"{url}\">{name}</a>'.format(
                    name=sub_cg,
                    url=sub_cg.get_absolute_url())
            if invisible_autoinvited_groups:
                inherited_info += '<li>' + _('Hidden group(s)...')
            inherited_info += '</ul>'

        context['inherited_info'] = mark_safe(inherited_info)

        context['nav'] = cg.get_smart_navbar()
        context['nav'].add_component(('members', _('members')))
        context['nav'].add_component(contact.get_navcomponent())
        context['nav'].add_component(('membership', _('membership')))
        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Contact In Group: Membership inline edition
#
#######################################################################


class ContactInGroupInlineView(InGroupAcl, View):
    # This is a small version that does NOT enable changes of administrative
    # permissions.

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_MEMBERS:
            raise PermissionDenied

    def post(self, request, gid, cid):
        cg = self.contactgroup
        contact = get_object_or_404(Contact, pk=int(cid))
        if request.POST.get('membership_i', False):
            flags = '+i'
        elif request.POST.get('membership_m', False):
            flags = '+m'
        elif request.POST.get('membership_d', False):
            flags = '+d'
        elif request.POST.get('membership_D', False):
            flags = '+D'
        else:
            flags = '-midD'
        cg.set_member_n(request, [contact], flags)
        note = request.POST.get('note', '')
        try:
            cig = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
        except ContactInGroup.DoesNotExist:
            print('FIXME: No note possible when no direct membership')
        else:
            cig.note = note
            cig.save()
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
        # print(self.contactgroup.get_smart_navbar())
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
            return HttpResponse(_('Error, that contact is not a direct member.'
                                  ' Please check subgroups'))
        return super().get(self, request, gid, cid)

    def delete(self, request, *args, **kwargs):
        obj = self.object = self.get_object()
        success_url = self.get_success_url()

        obj.group.set_member_n(
                request,
                [obj.contact],
                '-' + perms.int_to_flags(obj.flags))
        return HttpResponseRedirect(success_url)


#######################################################################
#
# Group mass remove
#
#######################################################################

class GroupRemoveManyForm(forms.Form):
    ids = forms.CharField(widget=forms.widgets.HiddenInput)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def get_contacts(self, user, group):
        contact_ids = self.initial['ids'].split(',')
        contacts = Contact.objects.filter(pk__in=contact_ids)
        contacts = contacts.extra(
            tables=('v_c_can_see_c',),
            where=(
                'v_c_can_see_c.contact_id_1={}'.format(user.id),
                'v_c_can_see_c.contact_id_2=contact.id'))
        return contacts


class GroupRemoveMany(InGroupAcl, FormView):

    form_class = GroupRemoveManyForm
    template_name = 'group_remove_many.html'
    success_url = '.'

    def get(self, request, gid):
        self.group = ContactGroup.objects.get(pk=gid)
        return super().get(request)

    def post(self, request, gid):
        self.group = ContactGroup.objects.get(pk=gid)
        return super().post(request)

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_MEMBERS:
            raise PermissionDenied

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
        context['title'] = _('Please confirm removal')
        context['group'] = self.group
        context['nav'] = self.group.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component(('remove_many', _('remove many')))
        context.update(kwargs)
        context = super().get_context_data(**context)  # adds the form

        form = context['form']
        contacts = form.get_contacts(self.request.user, self.group)
        context['contacts'] = list(contacts)

        msg_remove = self.group.check_remove_members(self.request, contacts)
        for cid, contact_info_msg in msg_remove.items():
            for contact in contacts:
                if contact.id == cid:
                    contact.remove_info = contact_info_msg.get(
                            'info', ())
                    contact.remove_warning = contact_info_msg.get(
                            'warning', ())
                    contact.remove_error = contact_info_msg.get(
                            'error', ())

        return context

    def form_valid(self, form):
        contacts = form.get_contacts(self.request.user, self.group)
        self.group.set_member_n(self.request, contacts, '-midD',
                                force_removal=True)
        return super().form_valid(form)
