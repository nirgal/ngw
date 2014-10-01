# -*- encoding: utf-8 -*-
'''
Log managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.utils.translation import ugettext as _, ugettext_lazy, pgettext_lazy
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
        (ugettext_lazy('Date UTC'), 'small_date', 'dt'),
        (ugettext_lazy('User'), 'contact', 'contact__name'),
        (ugettext_lazy('Action'), 'action_txt', 'action'),
        (ugettext_lazy('Target'), 'target_repr', 'target_repr'),
        (ugettext_lazy('Property'), 'property_repr', 'property_repr'),
        (pgettext_lazy('noun', 'Change'), 'change', 'change'),
    ]


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Global log')
        context['objtype'] = Log
        context['nav'] = Navbar(Log.get_class_navcomponent())

        context.update(kwargs)
        return super(LogListView, self).get_context_data(**context)
