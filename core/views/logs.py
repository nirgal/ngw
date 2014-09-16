# -*- encoding: utf-8 -*-
'''
Log managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.utils.translation import ugettext_lazy as _, pgettext_lazy
from ngw.core.models import Log
from ngw.core.nav import Navbar
from ngw.core.views.generic import NgwAdminAcl, NgwListView

__all__ = ['LogListView']

class LogListView(NgwAdminAcl, NgwListView):
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
        (pgettext_lazy('noun', 'Change'), None, 'change', 'change'),
    ]


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Global log')
        context['objtype'] = Log
        context['nav'] = Navbar(Log.get_class_navcomponent())

        context.update(kwargs)
        return super(LogListView, self).get_context_data(**context)
