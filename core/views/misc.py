'''
Miscalaneous views
'''

import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from ngw.core import perms
from ngw.core.models import Contact, ContactGroup, ContactGroupNews
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
        return super().get(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = {
            'message': mark_safe(
                _('Have a nice day!<br><br><a href="{}">Login again</a>.')
                .format(settings.LOGIN_URL))
        }
        context.update(kwargs)
        return super().get_context_data(**context)


class HomeView(NgwUserAcl, TemplateView):
    '''
    Home page view
    '''

    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        operator_groups = ContactGroup.objects.extra(where=[
            'EXISTS (SELECT *'
            '           FROM contact_in_group'
            '           WHERE contact_in_group.group_id = contact_group.id'
            '             AND contact_in_group.contact_id={}'
            '             AND contact_in_group.flags & {} <> 0)'
            .format(self.request.user.id, perms.OPERATOR)])

        qry_news = ContactGroupNews.objects.extra(
            tables={'v_cig_perm': 'v_cig_perm'},
            where=[
                'v_cig_perm.contact_id = {}'
                ' AND v_cig_perm.group_id '
                '     = contact_group_news.contact_group_id'
                ' AND v_cig_perm.flags & {} <> 0'
                .format(self.request.user.id, perms.VIEW_NEWS)])
        paginator = Paginator(qry_news, 7)

        page = self.request.GET.get('page')
        try:
            news = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            news = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of
            # results.
            news = paginator.page(paginator.num_pages)

        unread_groups = ContactGroup.objects.raw(
            '''
            SELECT *
            FROM contact_group
            JOIN (SELECT group_id, count(*) AS unread_count
                  FROM contact_message
                  WHERE is_answer AND read_date IS NULL GROUP BY group_id
                ) AS msg_info
                ON contact_group.id=msg_info.group_id
            JOIN v_cig_perm
                ON v_cig_perm.contact_id = {}
                AND v_cig_perm.group_id = contact_group.id
                AND v_cig_perm.flags & {} <> 0
            ORDER BY date DESC,name'''
            .format(self.request.user.id, perms.VIEW_MSGS))
        context = {
            'title': _('Lastest news'),
            'nav': Navbar(),
            'operator_groups': operator_groups,
            'news': news,
            'unread_groups': unread_groups,
        }
        context.update(kwargs)
        return super().get_context_data(**context)


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
        return super().get_context_data(**context)
