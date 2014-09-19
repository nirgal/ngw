# -*- encoding: utf-8 -*-
'''
Miscalaneous views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
import os
from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import TemplateView
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from ngw.core.models import Contact, ContactGroup, ContactGroupNews
from ngw.core import perms
from ngw.core.nav import Navbar
from ngw.core.views.generic import NgwUserAcl

__all__ = ['LogoutView', 'HomeView', 'TestView']


class LogoutView(TemplateView):
    '''
    Logout view
    '''

    template_name = 'message.html'

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return super(LogoutView, self).get(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = {
            'message': mark_safe(_('Have a nice day!<br><br><a href="%s">Login again</a>.') % settings.LOGIN_URL)
        }
        context.update(kwargs)
        return super(LogoutView, self).get_context_data(**context)


class HomeView(NgwUserAcl, TemplateView):
    '''
    Home page view
    '''

    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        operator_groups = ContactGroup.objects.extra(where=[
            '''EXISTS (SELECT *
                       FROM contact_in_group
                       WHERE contact_in_group.group_id = contact_group.id
                         AND contact_in_group.contact_id=%s AND contact_in_group.flags & %s <> 0)'''
            % (self.request.user.id, perms.OPERATOR)])

        qry_news = ContactGroupNews.objects.extra(where=[
            'perm_c_can_see_news_cg(%s, contact_group_news.contact_group_id)'
            % self.request.user.id])
        paginator = Paginator(qry_news, 7)

        page = self.request.GET.get('page')
        try:
            news = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            news = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            news = paginator.page(paginator.num_pages)

        unread_groups = ContactGroup.objects.raw('''
            SELECT *
            FROM contact_group
            JOIN (SELECT group_id, count(*) AS unread_count FROM contact_message WHERE is_answer AND read_date IS NULL GROUP BY group_id) AS msg_info
            ON contact_group.id=msg_info.group_id
            AND perm_c_can_view_msgs_cg(%s, group_id)''' % self.request.user.id)

        context = {
            'title': _('Lastest news'),
            'nav': Navbar(),
            'operator_groups': operator_groups,
            'news': news,
            'unread_groups': unread_groups,
        }
        context.update(kwargs)
        return super(HomeView, self).get_context_data(**context)


class TestView(NgwUserAcl, TemplateView):
    '''
    Test page view (debug)
    '''

    template_name = 'test.html'

    def get_context_data(self, **kwargs):
        messages.add_message(self.request, messages.INFO, 'This is a test')
        context = {
            'title': 'Test',
            'env': os.environ,
            'objtype': Contact,
            'nav': Navbar('test'),
        }
        context.update(kwargs)
        return super(TestView, self).get_context_data(**context)
