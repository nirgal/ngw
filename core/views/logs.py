'''
Log managing views
'''

from django.utils.translation import ugettext as _, ugettext_lazy, pgettext_lazy
from django.utils import formats
from ngw.core.models import Log
from ngw.core.nav import Navbar
from ngw.core.views.generic import NgwAdminAcl, NgwListView

__all__ = ['LogListView']

class LogListView(NgwAdminAcl, NgwListView):
    '''
    Display full log list (history).
    '''
    template_name = 'log_list.html'
    list_display = (
        'small_date', 'contact', 'action_txt', 'target_repr', 'property_repr',
        'change')

    def small_date(self, log):
        return formats.date_format(log.dt, "SHORT_DATETIME_FORMAT")
    small_date.short_description = ugettext_lazy('Date UTC')
    small_date.admin_order_field = 'dt'


    def get_root_queryset(self):
        return Log.objects.all()

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Global log')
        context['objtype'] = Log
        context['nav'] = Navbar(Log.get_class_navcomponent())

        context.update(kwargs)
        return super(LogListView, self).get_context_data(**context)
