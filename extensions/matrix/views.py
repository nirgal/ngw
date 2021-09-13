import pprint

from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from ngw.core.views.generic import NgwUserAcl

from . import matrix


class MatrixRoomsView(NgwUserAcl, TemplateView):
    '''
    Home page view
    '''
    template_name = 'rooms_list.html'

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Matrix rooms')
        rooms = matrix.get_rooms()
        rooms2 = [room for room in rooms]
        for room in rooms2:
            room['pretty'] = pprint.pformat(room)
        context['rooms'] = rooms2
        context.update(kwargs)
        return super().get_context_data(**context)


class MatrixAllRoomsView(NgwUserAcl, TemplateView):
    '''
    Home page view
    '''
    template_name = 'rooms_list.html'

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Matrix rooms')
        rooms = matrix.get_rooms(show_empty=True, show_private=True)
        rooms2 = [room for room in rooms]
        for room in rooms2:
            room['pretty'] = pprint.pformat(room)
        context['rooms'] = rooms2
        context.update(kwargs)
        return super().get_context_data(**context)
