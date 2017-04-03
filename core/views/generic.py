'''
Base view class; View helpers
'''

import operator
import re
from collections import OrderedDict
from functools import reduce

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.templatetags.admin_static import static
from django.contrib.admin.utils import (display_for_field, display_for_value,
                                        label_for_field, lookup_field)
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.db.models.fields import BLANK_CHOICE_DASH
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.http.response import HttpResponseBase
from django.utils import html
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.cache import never_cache
from django.views.generic import DeleteView, TemplateView
from django.views.generic.base import ContextMixin

from ngw.core import perms
from ngw.core.models import (GROUP_ADMIN, GROUP_USER_NGW, LOG_ACTION_DEL,
                             Config, ContactGroup, Log)
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group


#######################################################################
#
# Access Control Lists
#
#######################################################################

class NgwUserAcl(object):
    '''
    This simple mixin check the user is authenticated and member of
    GROUP_USER_NGW.
    '''
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        self.check_perm_user(request.user)
        return super().dispatch(request, *args, **kwargs)

    def check_perm_user(self, user):
        '''
        That function give the opportunity to specialise clas to add extra
        permission checks.
        '''


class NgwAdminAcl(NgwUserAcl):
    '''
    This simple mixin check the user is authenticated and member of GROUP_ADMIN
    '''
    def check_perm_user(self, user):
        super().check_perm_user(user)
        if not user.is_member_of(GROUP_ADMIN):
            raise PermissionDenied


class InGroupAcl(ContextMixin):
    '''
    This mixin integrates GROUP_USER_NGW membership checks
    Views using that mixin must define a "gid" url pattern.
    Mixin will setup a self.contactgroup and set up context.
    '''

    # Class whose gid parameter is optionnal should set is_group_required to
    # False.
    is_group_required = True

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        group_id = self.kwargs.get('gid', None)
        if group_id:
            try:
                group_id = int(group_id)
                group = (ContactGroup.objects
                         .with_user_perms(user.id)
                         .with_counts()
                         .get(pk=group_id))
            except (ValueError, TypeError, ContactGroup.DoesNotExist):
                raise Http404
        else:
            group = None
        self.contactgroup = group
        self.check_perm_groupuser(group, user)
        return super().dispatch(request, *args, **kwargs)

    def check_perm_groupuser(self, group, user):
        '''
        That function give the opportunity to specialise class to add extra
        permission checks.
        '''
        group = self.contactgroup
        if group and not group.userperms & perms.SEE_CG:
            raise PermissionDenied
        try:
            super().check_perm_groupuser(group, user)
        except AttributeError:
            pass

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['cg'] = cg
        if cg:
            context['cg_perms'] = perms.int_to_flags(cg.userperms)
        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Basic list view
#
#######################################################################

# List of things to do in order to use admin.views.main.ChangeList:
# model_admin.get_preserved_filters
# model_admin.to_field_allowed


class MyChangeList(ChangeList):
    '''
    This is a clone of ChangeList, but urls are relative
    '''
    def __init__(self, append_slash=True, *args, **kwargs):
        self.append_slash = append_slash
        super().__init__(*args, **kwargs)

    def url_for_result(self, result):
        pk = getattr(result, self.pk_attname)
        url = str(pk)
        if self.append_slash:
            url += '/'
        return url


class NgwListView(TemplateView):
    # '''
    # This function renders the query, paginated.
    # http query parameter _order is used to sort on a column
    # '''
    template_name = 'list.html'

    list_display = ('__str__',)
    list_display_links = None
    list_filter = ()
    date_hierarchy = None
    search_fields = ()
    list_select_related = False
    list_per_page = None
    list_max_show_all = 1000
    list_editable = ()
    ordering = None
    paginator = Paginator
    preserve_filters = True

    # Actions
    actions = []
    action_form = helpers.ActionForm
    actions_on_top = True
    actions_on_bottom = False
    actions_selection_counter = True

    append_slash = True

    @property
    def media(self):
        extra = '' if settings.DEBUG else '.min'
        js = []
        if self.actions is not None:
            js.append('actions{}.js'.format(extra))
        return forms.Media(js=[static('admin/js/{}'.format(url))
                               for url in js])

    def get_ordering(self, request):
        # This method is copied exactly fom BaseModelAdmin
        return self.ordering or ()

    def get_paginator(self, request, queryset, per_page, orphans=0,
                      allow_empty_first_page=True):
        # This method is copied exactly fom BaseModelAdmin
        return self.paginator(queryset, per_page, orphans,
                              allow_empty_first_page)

    def action_checkbox(self, obj):
        """
        A list_display column containing a checkbox widget.
        """
        return helpers.checkbox.render(
            helpers.ACTION_CHECKBOX_NAME, str(obj.pk))
    action_checkbox.short_description = mark_safe(
        '<input type="checkbox" id="action-toggle" />')
    action_checkbox.allow_tags = True

    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        """
        Return a list of choices for use in a form object.  Each choice is a
        tuple (name, description).
        """
        choices = [] + default_choices
        for func, name, description in self.get_actions(request).values():
            choice = (name, description)  # % model_format_dict(self.opts))
            choices.append(choice)
        return choices

    def get_actions(self, request):
        """
        Return a dictionary mapping the names of all actions for this
        ModelAdmin to a tuple of (callable, name, description) for each action.
        """
        # If self.actions is explicitly set to None that means that we don't
        # want *any* actions enabled on this page.
        from django.contrib.admin.views.main import _is_changelist_popup
        if self.actions is None or _is_changelist_popup(request):
            return OrderedDict()

        actions = []

        # Gather actions from the admin site first
        # for (name, func) in self.admin_site.actions:
        #    description = getattr(func, 'short_description',
        #                          name.replace('_', ' '))
        #    actions.append((func, name, description))

        # Then gather them from the model admin and all parent classes,
        # starting with self and working back up.
        for klass in self.__class__.mro()[::-1]:
            class_actions = getattr(klass, 'actions', [])
            # Avoid trying to iterate over None
            if not class_actions:
                continue
            actions.extend(self.get_action(action) for action in class_actions)

        # get_action might have returned None, so filter any of those out.
        actions = filter(None, actions)

        # Convert the actions into an OrderedDict keyed by name.
        actions = OrderedDict(
            (name, (func, name, desc))
            for func, name, desc in actions
        )

        return actions

    def get_action(self, action):
        """
        Return a given action from a parameter, which can either be a callable,
        or the name of a method on the ModelAdmin.  Return is a tuple of
        (callable, name, description).
        """
        # If the action is a callable, just use it.
        if callable(action):
            func = action
            action = action.__name__

        # Next, look for a method. Grab it off self.__class__ to get an unbound
        # method instead of a bound one; this ensures that the calling
        # conventions are the same for functions and methods.
        elif hasattr(self.__class__, action):
            func = getattr(self.__class__, action)

        # Here was some code for global admin site actions

        if hasattr(func, 'short_description'):
            description = func.short_description
        else:
            description = capfirst(action.replace('_', ' '))
        return func, action, description

    def get_list_display(self, request):
        '''
        Overridable method. Returns self.list_display
        '''
        return self.list_display

    def get_queryset(self, request):
        # Used by ChangeList
        qs = self.get_root_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_search_fields(self, request):
        # This method is copied exactly fom ModelAdmin
        """
        Returns a sequence containing the fields to be searched whenever
        somebody submits a search query.
        """
        return self.search_fields

    def get_search_results(self, request, queryset, search_term):
        # This method is copied exactly fom ModelAdmin
        """
        Returns a tuple containing a queryset to implement the search,
        and a boolean indicating if the results may contain duplicates.
        """
        # Apply keyword searches.
        def construct_search(field_name):
            if field_name.startswith('^'):
                return "{}__istartswith".format(field_name[1:])
            elif field_name.startswith('='):
                return "{}__iexact".format(field_name[1:])
            elif field_name.startswith('@'):
                return "{}__search".format(field_name[1:])
            else:
                return "{}__icontains".format(field_name)

        use_distinct = False
        search_fields = self.get_search_fields(request)
        if search_fields and search_term:
            orm_lookups = [construct_search(str(search_field))
                           for search_field in search_fields]
            for bit in search_term.split():
                or_queries = [models.Q(**{orm_lookup: bit})
                              for orm_lookup in orm_lookups]
                queryset = queryset.filter(reduce(operator.or_, or_queries))
            # if not use_distinct:
            # from django.contrib.admin.utils import lookup_needs_distinct
            #    for search_spec in orm_lookups:
            #        if lookup_needs_distinct(self.opts, search_spec):
            #            use_distinct = True
            #            break

        return queryset, use_distinct

    def get_preserved_filters(self, request):
        # Used by ChangeList
        return ''

    def lookup_allowed(self, lookup, value):
        # TODO
        return True

    def response_action(self, request, queryset):
        """
        Handle an admin action. This is called if a request is POSTed to the
        changelist; it returns an HttpResponse if the action was handled, and
        None otherwise.
        """

        # There can be multiple action forms on the page (at the top
        # and bottom of the change list, for example). Get the action
        # whose button was pushed.
        try:
            action_index = int(request.POST.get('index', 0))
        except ValueError:
            action_index = 0

        # Construct the action form.
        data = request.POST.copy()
        data.pop(helpers.ACTION_CHECKBOX_NAME, None)
        data.pop("index", None)

        # Use the action whose button was pushed
        try:
            data.update({'action': data.getlist('action')[action_index]})
        except IndexError:
            # If we didn't get an action from the chosen form that's invalid
            # POST data, so by deleting action it'll fail the validation check
            # below. So no need to do anything here
            pass

        action_form = self.action_form(data, auto_id=None)
        action_form.fields['action'].choices = self.get_action_choices(request)

        # If the form's valid we can handle the action.
        if action_form.is_valid():
            action = action_form.cleaned_data['action']
            select_across = action_form.cleaned_data['select_across']
            func = self.get_actions(request)[action][0]

            # Get the list of selected PKs. If nothing's selected, we can't
            # perform an action on it, so bail. Except we want to perform
            # the action explicitly on all objects.
            selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            if not selected and not select_across:
                # Reminder that something needs to be selected or nothing will
                # happen
                msg = _("Items must be selected in order to perform "
                        "actions on them. No items have been changed.")
                messages.add_message(request, messages.WARNING, msg)
                return None

            if not select_across:
                # Perform the action only on the selected objects
                queryset = queryset.filter(pk__in=selected)

            response = func(self, request, queryset)

            # Actions may return an HttpResponse-like object, which will be
            # used as the response from the POST. If not, we'll be a good
            # little HTTP citizen and redirect back to the changelist page.
            if isinstance(response, HttpResponseBase):
                return response
            else:
                return HttpResponseRedirect(request.get_full_path())
        else:
            msg = _("No action selected.")
            messages.add_message(request, messages.WARNING, msg)
            return None

    def theview(self, request, *args, **kwargs):
        qs = self.get_root_queryset()
        request = self.request

        list_display = self.get_list_display(request)
        list_per_page = self.list_per_page
        if list_per_page is None:
            list_per_page = Config.get_object_query_page_length()

        # Check actions to see if any are available on this changelist
        actions = self.get_actions(request)
        if actions:
            # Add the action checkboxes if there are any actions available.
            list_display = ['action_checkbox'] + list(list_display)

        self.cl = cl = MyChangeList(
            self.append_slash,
            self.request, qs.model,
            list_display, self.list_display_links, self.list_filter,
            self.date_hierarchy, self.search_fields, self.list_select_related,
            list_per_page, self.list_max_show_all, self.list_editable,
            self)

        # If the request was POSTed, this might be a bulk action or a bulk
        # edit. Try to look up an action or confirmation first, but if this
        # isn't an action the POST will fall through to the bulk edit check,
        # below.
        action_failed = False
        selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)

        # Actions with no confirmation
        if (actions and request.method == 'POST' and
                'index' in request.POST and '_save' not in request.POST):
            if selected:
                response = self.response_action(
                    request, queryset=cl.get_queryset(request))
                if response:
                    return response
                else:
                    action_failed = True
            else:
                msg = _("Items must be selected in order to perform "
                        "actions on them. No items have been changed.")
                messages.add_message(request, messages.WARNING, msg)
                action_failed = True

        # Actions with confirmation
        if (actions and request.method == 'POST' and
                helpers.ACTION_CHECKBOX_NAME in request.POST and
                'index' not in request.POST and '_save' not in request.POST):
            if selected:
                # queryset=cl.get_queryset(request))
                response = self.response_action(request, qs)
                if response:
                    return response
                else:
                    action_failed = True

        # Build the list of media to be used by the formset.
        # if formset:
        #     media = self.media + formset.media
        # else:
        #     media = self.media
        media = self.media

        # Build the action form and populate it with available actions.
        if actions:
            action_form = self.action_form(auto_id=None)
            action_form.fields['action'].choices = (
                self.get_action_choices(request))
        else:
            action_form = None

        context = {}
        context['cl'] = cl
        context['media'] = media
        context['action_form'] = action_form
        context['actions_on_top'] = self.actions_on_top
        context['actions_on_bottom'] = self.actions_on_bottom

        cl.formset = None
        context.update(kwargs)
        context = self.get_context_data(**context)
        if action_failed:
            print('action failed')
        return self.render_to_response(context)

    get = post = theview

    def action_csv_export(self, request, queryset):
        result = ''

        def _quote_csv(col_html):
            u = html.strip_tags(str(col_html))
            u = u.rstrip('\n\r')  # remove trailing \n
            # drop spaces at the begining of the line:
            u = re.sub('^[ \t\n\r\f\v]+', '', u, flags=re.MULTILINE)
            u = re.sub('[ \t\n\r\f\v]*\n', '\n', u)  # remove duplicates \n
            # Do the actual escaping/quoting
            return '"' + u.replace('\\', '\\\\').replace('"', '\\"') + '"'

        header_done = False
        for row in queryset:
            if not header_done:
                for i, field_name in enumerate(self.list_display):
                    text, attr = label_for_field(
                        field_name, type(row), self, True)
                    if i:  # not first column
                        result += ','
                    result += _quote_csv(text)
                result += '\n'
                header_done = True
            for i, field_name in enumerate(self.list_display):
                if i:  # not first column
                    result += ','
                f, attr, value = lookup_field(field_name, row, self)
                if value is None:
                    continue
                if f is None:
                    col_html = display_for_value(value, False)
                else:
                    col_html = display_for_field(value, f)

                result += _quote_csv(col_html)
            result += '\n'
        return HttpResponse(result, content_type='text/csv; charset=utf-8')
    action_csv_export.short_description = ugettext_lazy(
        "CSV format export (Spreadsheet format)")

#######################################################################
#
# Basic delete view
#
#######################################################################

# Helper function that is never call directly, hence the lack of
# authentification check


class NgwDeleteView(DeleteView):
    template_name = 'delete.html'
    success_url = '../'

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Please confirm deletetion')
        if 'nav' not in kwargs:
            # Don't bother if it's overrident
            context['nav'] = Navbar(self.object.get_class_navcomponent()) \
                .add_component(self.object.get_navcomponent()) \
                .add_component(('delete', _('delete')))
        context.update(kwargs)
        return super().get_context_data(**context)

    def delete(self, request, *args, **kwargs):
        obj = self.object = self.get_object()
        success_url = self.get_success_url()

        name = str(obj)
        log = Log()
        log.contact_id = self.request.user.id
        log.action = LOG_ACTION_DEL
        pk_names = (obj._meta.pk.attname,)  # default django pk name
        log.target = obj.__class__.__name__ + ' ' + ' '.join(
            [str(obj.__getattribute__(fieldname)) for fieldname in pk_names])
        log.target_repr = obj.get_class_verbose_name() + ' '+name
        log.save()

        self.object.delete()
        messages.add_message(request, messages.SUCCESS,
                             _('{} has been deleted.').format(name))
        return HttpResponseRedirect(success_url)
