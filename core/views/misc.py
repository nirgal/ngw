# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
import os
from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render_to_response
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template import RequestContext
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from ngw.core.models import (
    GROUP_USER_NGW, CIGFLAG_OPERATOR, Contact, ContactGroup, ContactGroupNews)
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group


#######################################################################
#
# Login / Logout
#
#######################################################################

def logout(request):
    auth_logout(request)
    return render_to_response('message.html', {
        'message': mark_safe(_('Have a nice day!<br><br><a href="%s">Login again</a>.') % settings.LOGIN_URL)
        }, RequestContext(request))


#######################################################################
#
# Home
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def home(request):
    operator_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.group_id = contact_group.id AND contact_in_group.contact_id=%s AND contact_in_group.flags & %s <> 0)' % (request.user.id, CIGFLAG_OPERATOR)])

    qry_news = ContactGroupNews.objects.extra(where=['perm_c_can_see_news_cg(%s, contact_group_news.contact_group_id)' % request.user.id])
    paginator = Paginator(qry_news, 7)

    page = request.GET.get('page')
    try:
        news = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        news = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        news = paginator.page(paginator.num_pages)

    return render_to_response('home.html', {
        'title': _('Lastest news'),
        'nav': Navbar(),
        'operator_groups': operator_groups,
        'news': news,
    }, RequestContext(request))


#######################################################################
#
# Test
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def test(request):
    context = {
        'title': 'Test',
        'env': os.environ,
        'objtype': Contact,
        'nav': Navbar('test'),
    }
    messages.add_message(request, messages.INFO, 'This is a test')
    return render_to_response('test.html', context, RequestContext(request))

