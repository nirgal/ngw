# -*- encoding: utf-8 -*-
'''
Base view class; View helpers
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from collections import OrderedDict
from django.http import HttpResponseRedirect, Http404
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.decorators import method_decorator
from django.utils import six
from django.utils.text import capfirst
from django.utils.http import urlencode
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.views.generic.base import ContextMixin
from django.views.generic import ListView
from django.contrib import messages
from ngw.core.models import (
    GROUP_ADMIN, GROUP_USER_NGW,
    ContactGroup, Config, Log,
    LOG_ACTION_DEL)
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group


#######################################################################
#
# Access Control Lists
#
#######################################################################

class NgwUserAcl(object):
    '''
    This simple mixin check the user is authenticated and member of GROUP_USER_NGW
    '''
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        self.check_perm_user(request.user)
        return super(NgwUserAcl, self).dispatch(request, *args, **kwargs)

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
        super(NgwAdminAcl, self).check_perm_user(user)
        if not user.is_member_of(GROUP_ADMIN):
            raise PermissionDenied


class InGroupAcl(ContextMixin):
    '''
    This mixin integrates GROUP_USER_NGW membership checks
    Views using that mixin must define a "gid" url pattern.
    Mixin will setup a self.contactgroup and set up context.
    '''
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        group_id = self.kwargs.get('gid', None)
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            raise Http404
        contactgroup = get_object_or_404(ContactGroup, pk=group_id)
        self.contactgroup = contactgroup
        self.check_perm_groupuser(contactgroup, request.user)
        return super(InGroupAcl, self).dispatch(request, *args, **kwargs)

    def check_perm_groupuser(self, group, user):
        '''
        That function give the opportunity to specialise clas to add extra
        permission checks.
        '''

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['cg'] = cg
        context['cg_perms'] = cg.get_contact_perms(self.request.user.id)
        context.update(kwargs)
        return super(InGroupAcl, self).get_context_data(**context)


#######################################################################
#
# Basic list view
#
#######################################################################

class BaseListFilter(object):
    '''
    This is a basic filter, with a admin-like compatible interface
    '''
    def __init__(self, request):
        param = request.GET.get(self.parameter_name, None)
        if param == '':
            param = None
        self.thevalue = param
        self.request = request

    def value(self):
        return self.thevalue

    def choices(self, view):
        # we preserver the order, but not the page
        extra_params = {}
        if view.order:
            extra_params['_order'] = view.order
        yield {
            'selected': self.value() is None,
            'query_string': view.get_query_string(extra_params, remove=(self.parameter_name,)),
            'display': _('All'),
        }
        for value, display_value in self.lookups(self.request, view):
            ep = extra_params.copy()
            ep[self.parameter_name] = value
            yield {
                'selected': self.value() == value,
                'query_string': view.get_query_string(ep),
                'display': display_value,
            }


class NgwListView(ListView):
    '''
    This function renders the query, paginated.
    http query parameter _order is used to sort on a column
    '''
    template_name = 'list.html'
    context_object_name = 'query'
    page_kwarg = '_page'
    default_sort = None
    filter_list = ()
    actions = ()

    def __init__(self, *args, **kwargs):
        super(NgwListView, self).__init__(*args, **kwargs)
        # keep track of parameters that need to be given back after
        # page/order change:
        self.url_params = {}
        self.simplefilters = []

    def get_root_queryset(self):
        return self.root_queryset

    def get_paginate_by(self, queryset):
        return Config.get_object_query_page_length()

    def get_queryset(self):
        queryset = self.get_root_queryset()

        # Handle admin-like filters
        for filter_class in self.filter_list:
            filter = filter_class(self.request)
            self.simplefilters.append(filter)
            queryset = filter.queryset(self.request, queryset)
            if filter.value() is not None:
                self.url_params[filter_class.parameter_name] = filter.value()

        # Handle sorts
        order = self.request.REQUEST.get('_order', '')
        try:
            intorder = int(order)
        except ValueError:
            if self.default_sort:
                order = ''
                intorder = None
                queryset = queryset.order_by(self.default_sort)
            elif self.cols[0][3] is not None:
                order = '0'
                intorder = 0
            else:
                order = ''
                intorder = None
        if intorder is not None:
            sort_col = self.cols[abs(intorder)][3]
            if not order or order[0] != '-':
                queryset = queryset.order_by(sort_col)
            else:
                queryset = queryset.order_by('-'+sort_col)

        self.order = order

        return queryset

    def get_query_string(self, new_params={}, remove=[]):
        p = self.url_params.copy()
        for r in remove:
            for k in list(p):
                if k.startswith(r):
                    del p[k]
        for k, v in new_params.items():
            if v is None:
                if k in p:
                    del p[k]
            else:
                p[k] = v
        return '?%s' % urlencode(sorted(p.items()))


    def get_actions(self, request):
        '''
        Get the list of available action names. Specific classes may overwrite
        that method to yield user-specfic list.
        '''
        return self.actions


    def get_context_data(self, **kwargs):
        def _get_action_desc(function):
            print(function)
            try:
                return function.short_description
            except AttributeError:
                return capfirst(function.__name__.replace('_', ' '))
        context = {}
        context['cols'] = self.cols
        context['baseurl'] = self.get_query_string()
        context['order'] = self.order
        context['simplefilters'] = [ (filter,filter.choices(self)) for filter in self.simplefilters ]
        context['actions'] = [
            (funcname, _get_action_desc(getattr(self, funcname)))
            for funcname in self.get_actions(self.request)]
        context.update(kwargs)
        return super(NgwListView, self).get_context_data(**context)


    def post(self, request, *args, **kwargs):
        selected_pk = request.POST.getlist('_selected_action')
        if selected_pk:
            action_name = request.POST['action']
            if action_name not in self.get_actions(request):
                raise PermissionDenied
            action_func = getattr(self, action_name)

            queryset = self.get_queryset()
            queryset = queryset.filter(pk__in=selected_pk)

            result = action_func(request, queryset)
            if result is not None:
                return result
        else:
            messages.add_message(request, messages.ERROR, _('You must select some items in order to perform the action.'))
        return self.get(self, request, *args, **kwargs)

#######################################################################
#
# Generic delete
#
#######################################################################

# Helper function that is never call directly, hence the lack of authentification check
def generic_delete(request, obj, next_url, base_nav=None, ondelete_function=None):
    title = _('Please confirm deletetion')

    confirm = request.GET.get('confirm', '')
    if confirm:
        if ondelete_function:
            ondelete_function(obj)
        name = force_text(obj)
        log = Log()
        log.contact_id = request.user.id
        log.action = LOG_ACTION_DEL
        pk_names = (obj._meta.pk.attname,)  # default django pk name
        log.target = force_text(obj.__class__.__name__) + ' ' + ' '.join([force_text(obj.__getattribute__(fieldname)) for fieldname in pk_names])
        log.target_repr = obj.get_class_verbose_name() + ' '+name
        obj.delete()
        log.save()
        messages.add_message(request, messages.SUCCESS, _('%s has been deleted sucessfully!') % name)
        return HttpResponseRedirect(next_url)
    else:
        nav = base_nav or Navbar(obj.get_class_navcomponent())
        nav.add_component(obj.get_navcomponent()) \
           .add_component(('delete', _('delete')))
        return render_to_response('delete.html', {
            'title': title,
            'object': obj,
            'nav': nav}, RequestContext(request))
