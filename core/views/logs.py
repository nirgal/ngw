# -*- encoding: utf-8 -*-
'''
Log managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from ngw.core.models import GROUP_USER_NGW, Log
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group
from django.utils.decorators import method_decorator
from ngw.core.views.generic import NgwListView

__all__ = ['LogListView']

class LogListView(NgwListView):
    '''
    Display full log list (history).
    '''
    template_name = 'log_list.html'
    root_queryset = Log.objects.all()
    cols = [
        (_('Date UTC'), None, 'small_date', 'dt'),
        (_('User'), None, 'contact', 'contact__name'),
        (_('Action'), None, 'action_txt', 'action'),
        (_('Target'), None, 'target_repr', 'target_repr'),
        (_('Property'), None, 'property_repr', 'property_repr'),
        (_('Change'), None, 'change', 'change'),
    ]

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        if not user.is_admin():
            raise PermissionDenied
        return super(LogListView, self).dispatch(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Global log')
        context['objtype'] = Log
        context['nav'] = Navbar(Log.get_class_navcomponent())

        context.update(kwargs)
        return super(LogListView, self).get_context_data(**context)
