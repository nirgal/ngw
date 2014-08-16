# -*- encoding: utf-8 -*-
'''
ContactGroupNews managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from datetime import datetime
from django.core.exceptions import PermissionDenied
from django.http import (HttpResponse, HttpResponseRedirect)
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django import forms
from django.contrib import messages
from ngw.core.models import (GROUP_USER_NGW, ContactGroup, ContactGroupNews)
from ngw.core import perms
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import generic_delete


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news(request, gid):
    gid = gid and int(gid) or None
    if not perms.c_can_see_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    context = {}
    context['title'] = _('News for group %s') % cg.name
    context['news'] = ContactGroupNews.objects.filter(contact_group=gid)
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['objtype'] = ContactGroupNews
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('news', _('news')))
    context['active_submenu'] = 'news'
    return render_to_response('news.html', context, RequestContext(request))


class NewsEditForm(forms.Form):
    title = forms.CharField(max_length=50)
    text = forms.CharField(widget=forms.Textarea)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_edit(request, gid, nid):
    gid = gid and int(gid) or None
    nid = nid and int(nid) or None
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    if nid:
        news = get_object_or_404(ContactGroupNews, pk=nid)
        if news.contact_group_id != gid:
            return HttpResponse(_('ERROR: Group mismatch'))

    if request.method == 'POST':
        form = NewsEditForm(request.POST)
        if form.is_valid():
            data = form.clean()
            if not nid:
                news = ContactGroupNews()
                news.author_id = request.user.id
                news.contact_group = cg
                news.date = datetime.now()
            news.title = data['title']
            news.text = data['text']
            news.save()
            messages.add_message(request, messages.SUCCESS, _('News %s has been changed sucessfully!') % news)

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(news.get_absolute_url())
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(reverse('ngw.core.views.news.contactgroup_news_edit', args=(cg.id,))) # 2nd parameter is None
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.news.contactgroup_news', args=(cg.id,)))
    else:
        initial = {}
        if nid:
            initial['title'] = news.title
            initial['text'] = news.text
        form = NewsEditForm(initial=initial)
    context = {}
    context['title'] = _('News edition')
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['form'] = form
    if nid:
        context['o'] = news
        context['id'] = nid
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('news', ('news')))
    if nid:
        context['nav'].add_component(news.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))

    return render_to_response('edit.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_delete(request, gid, nid):
    gid = gid and int(gid) or None
    nid = nid and int(nid) or None
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    o = get_object_or_404(ContactGroupNews, pk=nid)
    return generic_delete(request, o, cg.get_absolute_url() + 'news/')
