# -*- encoding: utf-8 -*-
'''
Base view class; View helpers
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.http import HttpResponseRedirect, Http404
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.decorators import method_decorator
from django.utils import six
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

class NgwListView(ListView):
    '''
    This function renders the query, paginated.
    http query parameter _order is used to sort on a column
    '''
    template_name = 'list.html'
    context_object_name = 'query'
    page_kwarg = '_page'
    default_sort = None

    def __init__(self, *args, **kwargs):
        super(NgwListView, self).__init__(*args, **kwargs)
        # keep track of parameters that need to be given back after
        # page/order change:
        self.url_params = {}

    def get_root_queryset(self):
        return self.root_queryset

    def get_paginate_by(self, queryset):
        return Config.get_object_query_page_length()

    def get_queryset(self):
        query = self.get_root_queryset()

        # Handle sorts
        order = self.request.REQUEST.get('_order', '')
        try:
            intorder = int(order)
        except ValueError:
            if self.default_sort:
                order = ''
                intorder = None
                query = query.order_by(self.default_sort)
            else:
                order = '0'
                intorder = 0
        if intorder is not None:
            sort_col = self.cols[abs(intorder)][3]
            if not order or order[0] != '-':
                query = query.order_by(sort_col)
            else:
                query = query.order_by('-'+sort_col)

        self.order = order

        return query

    def get_context_data(self, **kwargs):
        context = {}
        context['cols'] = self.cols
        baseurl = '&'.join([ "%s=%s" % (key, value)
            for key, value in six.iteritems(self.url_params)
            if value != ''])
        context['baseurl'] = '?' + baseurl
        context['order'] = self.order
        context.update(kwargs)
        return super(NgwListView, self).get_context_data(**context)


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
