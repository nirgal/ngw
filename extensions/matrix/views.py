import pprint

from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from ngw.core.models import MatrixRoom
from ngw.core.views.generic import NgwUserAcl

from . import matrix


class MatrixRoomsView(NgwUserAcl, TemplateView):
    '''
    Room list view
    '''
    template_name = 'rooms_list.html'

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Matrix rooms')
        rooms = matrix.get_rooms()
        rooms2 = [room for room in rooms]
        for room in rooms2:
            room['pretty'] = pprint.pformat(room)
            try:
                ngwroom = MatrixRoom.objects.get(pk=room['room_id'])
                cg = ngwroom.contact_group
            except MatrixRoom.DoesNotExist:
                cg = None
            room['contact_group'] = cg
        context['rooms'] = rooms2
        context.update(kwargs)
        return super().get_context_data(**context)


class MatrixAllRoomsView(NgwUserAcl, TemplateView):
    '''
    Room list view
    '''
    template_name = 'rooms_list.html'

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Matrix rooms')
        rooms = matrix.get_rooms(show_empty=True, show_private=True)
        rooms2 = [room for room in rooms]
        for room in rooms2:
            room['pretty'] = pprint.pformat(room)
            try:
                ngwroom = MatrixRoom.objects.get(pk=room['room_id'])
                cg = ngwroom.contact_group
            except MatrixRoom.DoesNotExist:
                cg = None
            room['contact_group'] = cg
        context['rooms'] = rooms2
        context.update(kwargs)
        return super().get_context_data(**context)


class MatrixRoomView(NgwUserAcl, TemplateView):
    '''
    Room details view
    '''
    template_name = 'room.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        room_id = context['room_id']
        context['title'] = _('Matrix room') + ' ' + room_id

        room = matrix.get_room_info(room_id)

        try:
            ngwroom = MatrixRoom.objects.get(pk=room['room_id'])
            cg = ngwroom.contact_group
        except MatrixRoom.DoesNotExist:
            cg = None
        room['contact_group'] = cg

        state = matrix.get_room_state(room_id)['state']
        room['state'] = matrix._room_state_clean(state)

        try:
            room['autoredact'] = (
                    room['state']['m.room.autoredact']['autoredact'])
        except KeyError:
            pass

        room['pretty'] = pprint.pformat(room)

        context['room'] = room

        return context
