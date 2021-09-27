import pprint
from datetime import datetime, timedelta

from django import forms
from django.conf import settings
from django.utils.translation import ugettext as _
from django.views.generic import FormView, TemplateView

from ngw.core.models import Contact, MatrixRoom
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

        request_params = self.request.GET
        rooms = matrix.get_rooms(
                show_empty=request_params.get('empty', False),
                show_private=request_params.get('private', False),
                )

        rooms = [room for room in rooms]
        for room in rooms:
            room['pretty'] = pprint.pformat(room)
            room['contact_group'] = _get_contact_group(room['room_id'])
            autoredact_maxage = _get_autoredact_maxage(room)
            if autoredact_maxage:
                room['autoredact'] = autoredact_maxage
        context['rooms'] = rooms
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

        try:
            power_levels = room['state']['m.room.power_levels']
            default_pl = power_levels.get('users_default', 0)
            for member in room['state']['members']:
                member['power_level'] = (
                    power_levels['users'].get(member['user_id'], default_pl))
        except KeyError:
            pass

        autoredact_maxage = _get_autoredact_maxage(room)
        if autoredact_maxage:
            room['autoredact'] = autoredact_maxage

        if self.request.GET.get('debug', False):
            room['pretty'] = pprint.pformat(room)

        context['room'] = room

        return context


class MatrixUserView(NgwUserAcl, TemplateView):
    '''
    User details view
    '''
    template_name = 'user.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_id = context['user_id']
        context['title'] = _('Matrix user') + ' ' + user_id

        user = matrix.get_user_info(user_id)
        context['mat_user'] = user

        if 'creation_ts' in user:
            context['creation_dt'] = (
                datetime.fromtimestamp(user['creation_ts'])
                )

        login = matrix.localpart(user_id)
        try:
            ngw_user = Contact.objects.get_by_natural_key(login)
            context['ngw_user'] = ngw_user
            context['ngw_user_url'] = (
                    f'/contactgroups/{settings.MATRIX_SYNC_GROUP}'
                    f'/members/{ngw_user.id}/'
                    )
        except Contact.DoesNotExist:
            pass

        if self.request.GET.get('debug', False):
            if user['password_hash']:
                user['password_hash'] = '********'
            context['pretty'] = pprint.pformat(user)

        return context


class ConfirmForm(forms.Form):
    def __init__(self, room_id, *args, **kargs):
        self.room_id = room_id
        super().__init__(*args, **kargs)

    def close_room(self):
        matrix.room_delete(self.room_id)


class MatrixRoomCloseView(NgwUserAcl, FormView):
    '''
    '''
    template_name = 'room_close.html'
    form_class = ConfirmForm
    success_url = '/matrix/room/'

    def get(self, request, room_id):
        self.room_id = room_id
        return super().get(request)

    def post(self, request, room_id):
        self.room_id = room_id
        return super().post(request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['room_id'] = self.room_id
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Please confirm matrix room shutdown')
        context['room_id'] = self.room_id
        return context

    def form_valid(self, form):
        form.close_room()
        return super().form_valid(form)
