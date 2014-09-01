# -*- encoding: utf-8 -*-
'''
ContactGroupNews managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from datetime import datetime
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, UpdateView, CreateView
from django.views.generic.edit import ModelFormMixin
from django import forms
from django.forms import widgets
from django.contrib import messages
from ngw.core.models import (GROUP_USER_NGW, ContactGroup, ContactGroupNews)
from ngw.core import perms
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import InGroupAcl, generic_delete


#######################################################################
#
# News list
#
#######################################################################


class NewsListView(InGroupAcl, ListView):
    template_name = 'news.html'
    context_object_name = 'news'
    paginate_by = 20
    page_kwarg = '_page'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_see_news_cg(user.id, group.id):
            raise PermissionDenied

    def get_queryset(self):
        return ContactGroupNews.objects \
            .filter(contact_group=self.contactgroup.id) \
            .order_by('-date')

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('News for group %s') % cg.name
        context['objtype'] = ContactGroupNews
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('news', _('news')))
        context['active_submenu'] = 'news'
        context['baseurl'] = '?'  # for paginator
        context.update(kwargs)
        return super(NewsListView, self).get_context_data(**context)


#######################################################################
#
# News edit / add
#
#######################################################################


class NewsEditForm(forms.ModelForm):
    class Meta:
        model = ContactGroupNews
        fields = ['title', 'text']
        widgets = {
            'title': widgets.TextInput(attrs={'max_length': 50}),
        }


class NewsEditMixin(ModelFormMixin):
    template_name = 'edit.html'
    form_class = NewsEditForm
    model = ContactGroupNews
    pk_url_kwarg = 'nid'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_change_news_cg(user.id, group.id):
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing %s') % self.object
            id = self.object.id
        else:
            title = _('Adding a new %s') % \
                ContactGroupNews.get_class_verbose_name()
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = ContactGroupNews
        context['nav'] = self.contactgroup.get_smart_navbar()
        context['nav'].add_component(('news', ('news')))
        if self.object:
            context['nav'].add_component(self.object.get_navcomponent())
            context['nav'].add_component(('edit', _('edit')))
        else:
            context['nav'].add_component(('add', _('add')))

        context.update(kwargs)
        return super(NewsEditMixin, self).get_context_data(**context)

    def form_valid(self, form):
        request = self.request
        cg = self.contactgroup
        response = super(NewsEditMixin, self).form_valid(form)
        messages.add_message(
            request, messages.SUCCESS,
            _('News %s has been saved.') % self.object)
        if request.POST.get('_continue', None):
            return HttpResponseRedirect(self.object.get_absolute_url())
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect(request.get_full_path())
        else:
            return HttpResponseRedirect(cg.get_absolute_url() + 'news/')
        return response


class NewsEditView(InGroupAcl, NewsEditMixin, UpdateView):
    pass


class NewsCreateView(InGroupAcl, NewsEditMixin, CreateView):
    def form_valid(self, form):
        form.instance.date = datetime.now()
        form.instance.author = self.request.user
        form.instance.contact_group = self.contactgroup
        return super(NewsCreateView, self).form_valid(form)


#######################################################################
#
# News delete
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_delete(request, gid, nid):
    gid = gid and int(gid) or None
    nid = nid and int(nid) or None
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    obj = get_object_or_404(ContactGroupNews, pk=nid)
    return generic_delete(request, obj, cg.get_absolute_url() + 'news/')
