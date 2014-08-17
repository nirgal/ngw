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
from django.views.generic import View, ListView
from django.views.generic.base import TemplateResponseMixin, ContextMixin
from django.contrib import messages
from ngw.core.models import GROUP_USER_NGW, Config, Log, LOG_ACTION_DEL
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group


class ProtectedView(View):
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, *args, **kwargs):
        return super(ProtectedView, self).dispatch(*args, **kwargs)


class TemplateProtectedView(TemplateResponseMixin, ContextMixin, ProtectedView):
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

class NgwListView(ListView):
    template_name = 'list.html'
    context_object_name = 'query'
    page_kwarg = '_page'

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
            if defaultsort:
                order = ''
                intorder = None
                query = query.order_by(defaultsort)
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

class ProtectedNgwListView(NgwListView):
    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, *args, **kwargs):
        return super(ProtectedNgwListView, self).dispatch(*args, **kwargs)


def render_query(template_name, context, request, defaultsort=''):
    '''
    This function renders the query, paginated
    '''
    q = context['query']
    cols = context['cols']

    # get sort column name
    order = request.REQUEST.get('_order', '')
    try:
        intorder = int(order)
    except ValueError:
        if defaultsort:
            order = ''
            intorder = None
            q = q.order_by(defaultsort)
        else:
            order = '0'
            intorder = 0
    if intorder is not None:
        sort_col = cols[abs(intorder)][3]
        if not order or order[0] != '-':
            q = q.order_by(sort_col)
        else:
            q = q.order_by('-'+sort_col)

    paginator = Paginator(q, Config.get_object_query_page_length())
    page = request.REQUEST.get('_page', 1)
    try:
        q = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        q = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        q = paginator.page(paginator.num_pages)

    context['query'] = q
    context['cols'] = cols
    context['order'] = order

    context['paginator'] = paginator
    context['page_obj'] = q

    if 'baseurl' not in context:
        context['baseurl'] = '?'
    return render_to_response(template_name, context, RequestContext(request))


##class ProtectedListView(MultipleObjectTemplateResponseMixin, BaseListView):
#class ProtectedListView(ListView):
#    @method_decorator(login_required)
#    @method_decorator(require_group(GROUP_USER_NGW))
#    def dispatch(self, *args, **kwargs):
#        return super(ProtectedListView, self).dispatch(*args, **kwargs)

# Helper function that is never call directly, hence the lack of authentification check
def generic_delete(request, o, next_url, base_nav=None, ondelete_function=None):
    title = _('Please confirm deletetion')

    confirm = request.GET.get('confirm', '')
    if confirm:
        if ondelete_function:
            ondelete_function(o)
        name = force_text(o)
        log = Log()
        log.contact_id = request.user.id
        log.action = LOG_ACTION_DEL
        pk_names = (o._meta.pk.attname,) # default django pk name
        log.target = force_text(o.__class__.__name__) + ' ' + ' '.join([force_text(o.__getattribute__(fieldname)) for fieldname in pk_names])
        log.target_repr = o.get_class_verbose_name() + ' '+name
        o.delete()
        log.save()
        messages.add_message(request, messages.SUCCESS, _('%s has been deleted sucessfully!') % name)
        return HttpResponseRedirect(next_url)
    else:
        nav = base_nav or Navbar(o.get_class_navcomponent())
        nav.add_component(o.get_navcomponent()) \
           .add_component(('delete', _('delete')))
        return render_to_response('delete.html', {'title':title, 'o': o, 'nav': nav}, RequestContext(request))



