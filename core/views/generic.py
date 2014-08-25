# -*- encoding: utf-8 -*-
'''
Base view class; View helpers
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.generic import View, TemplateView, ListView
from django.views.generic.base import TemplateResponseMixin, ContextMixin
from django.contrib import messages
from ngw.core.models import GROUP_ADMIN, GROUP_USER_NGW, Config, Log, LOG_ACTION_DEL
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group


class NgwUserMixin(object):
    '''
    This simple mixin check the user is authenticated and member of GROUP_USER_NGW
    '''
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, *args, **kwargs):
        return super(NgwUserMixin, self).dispatch(*args, **kwargs)


class NgwAdminMixin(object):
    '''
    This simple mixin check the user is authenticated and member of GROUP_ADMIN
    '''
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_ADMIN))
    def dispatch(self, *args, **kwargs):
        return super(NgwAdminMixin, self).dispatch(*args, **kwargs)



class NgwListView(ListView):
    '''
    This function renders the query, paginated.
    http query parameter _order is used to sort on a column
    '''
    template_name = 'list.html'
    context_object_name = 'query'
    page_kwarg = '_page'
    default_sort = None

    def get_root_queryset(self):
        return self.root_queryset

    def get_paginate_by(self, queryset):
       return Config.get_object_query_page_length()

    def get_queryset(self):
        query = self.get_root_queryset()

        # Handle sorts
        defaultsort = ''
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
        context['baseurl'] = '?'
        context['order'] = self.order
        context.update(kwargs)
        return super(NgwListView, self).get_context_data(**context)



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
        pk_names = (obj._meta.pk.attname,) # default django pk name
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
        return render_to_response('delete.html', {'title':title, 'object': obj, 'nav': nav}, RequestContext(request))
