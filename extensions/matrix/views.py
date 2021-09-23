import pprint
from datetime import timedelta

from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from ngw.core.models import MatrixRoom
from ngw.core.views.generic import NgwUserAcl

from . import matrix


def _get_contact_group(room_id):
    try:
        ngwroom = MatrixRoom.objects.get(pk=room_id)
    except MatrixRoom.DoesNotExist:
        return None
    return ngwroom.contact_group


def _check_state_filled(room):
    '''
    Check that room.state is define.
    Query the server if needed.
    '''
    if 'state' not in room:
        state = matrix.get_room_state(room['room_id'])['state']
        room['state'] = matrix._room_state_clean(state)


def _get_autoredact_maxage(room):
    _check_state_filled(room)
    try:
        seconds = room['state']['m.room.autoredact']['autoredact']
        return timedelta(seconds=seconds)
    except KeyError:
        return None


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
            room['contact_group'] = _get_contact_group(room['room_id'])
            autoredact_maxage = _get_autoredact_maxage(room)
            if autoredact_maxage:
                room['autoredact'] = autoredact_maxage
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
            room['contact_group'] = _get_contact_group(room['room_id'])
            autoredact_maxage = _get_autoredact_maxage(room)
            if autoredact_maxage:
                room['autoredact'] = autoredact_maxage
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

        room['contact_group'] = _get_contact_group(room_id)

        _check_state_filled(room)

        # try:
        #     power_levels = room['state']['m.room.power_levels']
        # except KeyError:
        #     power_levels = {}

        autoredact_maxage = _get_autoredact_maxage(room)
        if autoredact_maxage:
            room['autoredact'] = autoredact_maxage

        room['pretty'] = pprint.pformat(room)

        context['room'] = room

        return context
