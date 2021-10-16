import json
import logging
import re
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

DOMAIN = settings.MATRIX_DOMAIN
URL = settings.MATRIX_URL


class NoSuchUser(Exception):
    pass


def _auth_header():
    return {'Authorization': f'Bearer {settings.MATRIX_ADMIN_TOKEN}'}


def _matrix_request(url, *args, **kargs):
    logger = logging.getLogger('matrix')

    method = kargs.get('method', 'GET')
    logger.debug('%s %s', method, url)

    # convert data from dict to json
    if len(args) > 0:
        data = args[0]
        data = json.dumps(data).encode('utf-8')
        args[0] = data
    if 'data' in kargs:
        data = kargs['data']
        data = json.dumps(data).encode('utf-8')
        kargs['data'] = data

    req = Request(url, *args, **kargs)

    try:
        response = urlopen(req)
    except HTTPError as e:
        logger.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        raise e
    except URLError as e:
        logger.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        raise e

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
    logger.debug(json.dumps(result_json, indent=4))
    return result_json


# ##########
# Non-Admin commands
# ##########

def generate_eventid():
    import random
    letters = '_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    eventid = '$'
    for _ in range(42):
        eventid += letters[random.randint(0, len(letters)-1)]
    return eventid


def get_event(eventid):
    '''
    Warning: you need to be in the room, or 403
    '''
    eventid = urllib.parse.quote(eventid)
    return _matrix_request(
        f'{URL}_matrix/client/r0/events/{eventid}',
        headers=_auth_header(),
        )


def get_room_event(roomid, eventid):
    roomid = urllib.parse.quote(roomid)
    eventid = urllib.parse.quote(eventid)
    return _matrix_request(
        f'{URL}_matrix/client/r0/rooms/{roomid}/event/{eventid}',
        headers=_auth_header(),
        )


def redact_event(roomid, eventid, txnid=None):
    if txnid is None:
        txnid = generate_eventid()
    roomid = urllib.parse.quote(roomid)
    eventid = urllib.parse.quote(eventid)
    txnid = urllib.parse.quote(txnid)

    data = {'reason': 'test'}

    return _matrix_request(
        f'{URL}_matrix/client/r0/rooms/{roomid}/redact/{eventid}/{txnid}',
        method='PUT',
        headers=_auth_header(),
        data=data,
        )


# ##########
# Admin commands
# ##########

def get_version():
    return _matrix_request(
        f'{URL}_synapse/admin/v1/server_version'
        )


def get_users_quick():
    '''
    Yields all users
    '''
    next_token = '0'
    limit = '10'
    while next_token:
        result = _matrix_request(
            f'{URL}_synapse/admin/v2/users'
            f'?deactivated=true&limit={limit}&from={next_token}',
            headers=_auth_header(),
            )
        for user in result['users']:
            yield user
        next_token = result.get('next_token', None)


def localpart(user_id):
    re_search = re.compile(f'@(.*):{DOMAIN}')
    login = re_search.search(user_id).groups()[0]
    return login


def get_users(include_deleted=False):
    '''
    Yields all users, detailed version
    '''
    next_token = '0'
    limit = '10'
    while next_token:
        result = _matrix_request(
            f'{URL}_synapse/admin/v2/users'
            f'?deactivated=true&limit={limit}&from={next_token}',
            headers=_auth_header(),
            )
        for user in result['users']:
            user_id = user['name']
            user = get_user_info(user_id)
            if not include_deleted:
                if not user['password_hash'] and not user['threepids']:
                    # logger.debug(f'{login} is disabled')
                    continue
            yield user

        next_token = result.get('next_token', None)


def get_user_info(user_id):
    assert user_id.endswith(f':{DOMAIN}')
    try:
        return _matrix_request(
            f'{URL}_synapse/admin/v2/users/{user_id}',
            headers=_auth_header(),
            )
    except HTTPError as e:
        if e.code == 404:
            raise NoSuchUser
        else:
            raise e


def get_user_rooms(user_id):
    '''
    List the rooms that user is in
    '''
    assert user_id.endswith(f':{DOMAIN}')
    try:
        return _matrix_request(
            f'{URL}_synapse/admin/v1/users/{user_id}/joined_rooms',
            headers=_auth_header(),
            )
    except HTTPError as e:
        if e.code == 404:
            raise NoSuchUser
        else:
            raise e


def put_user(user_id, data):
    '''
    Low level interface to /_synapse/admin/v2/users/<USER>.
    '''
    assert user_id.endswith(f':{DOMAIN}')
    return _matrix_request(
        f'{URL}_synapse/admin/v2/users/{user_id}',
        headers=_auth_header(),
        data=data,
        method='PUT',
        )


def set_user_info(user_id, name=None, emails=None, admin=None, create=False):
    '''
    High level interface to create/modify account.
    @returns server new information if changed, None otherwise
    '''
    logger = logging.getLogger('matrix')
    assert user_id.endswith(f':{DOMAIN}')

    try:
        olddata = get_user_info(user_id)
    except NoSuchUser as e:
        if not create:
            logger.error(f"User {user_id} doesn't exists and create=False")
            raise e
        olddata = {}

    data = {}

    if name is not None:
        if name != olddata.get('displayname', None):
            data['displayname'] = name

    if emails is not None:
        old_emails = [
            threepid['address']
            for threepid in olddata.get('threepids', [])
            if threepid['medium'] == 'email'
            ]
        old_emails = set(old_emails)
        emails = set(emails)

        # preserve the emails added by the user:
        emails = old_emails | emails

        if old_emails != emails:
            data['threepids'] = [
                {'medium': 'email', 'address': email} for email in emails
                ]

    if admin is not None:
        data['admin'] = admin

    if data:
        return put_user(user_id, data)
    else:
        logger.debug(f'{user_id}: No change.')
        return None


def deactivate_account(user_id, erase=True):
    assert user_id.endswith(f':{DOMAIN}')
    try:
        data = {'erase': erase}
        return _matrix_request(
            url=f'{URL}_synapse/admin/v1/deactivate/{user_id}',
            headers=_auth_header(),
            data=data,
            )
    except HTTPError as e:
        if e.code == 404:
            raise NoSuchUser
        else:
            raise e


def reset_password(user_id, password):
    assert user_id.endswith(f':{DOMAIN}')
    data = {
        'new_password': password,
        'logout_devices': True,
        }
    return _matrix_request(
        f'{URL}_synapse/admin/v1/reset_password/{user_id}',
        headers=_auth_header(),
        data=data,
        )


def room_join(user_id, room):
    '''
    room is either a id (starting with '!') or an alias (starting with '#')
    admin must be in the room...
    '''
    assert user_id.endswith(f':{DOMAIN}')
    data = {
        'user_id': user_id,
    }
    room = urllib.parse.quote(room)
    return _matrix_request(
        f'{URL}_synapse/admin/v1/join/{room}',
        # Example: !636q39766251:server.com, #niceroom:server.com
        headers=_auth_header(),
        data=data,
        )


def get_rooms_quick():
    '''
    Yields all rooms
    '''
    next_batch = '0'
    limit = '10'
    while next_batch:
        result = _matrix_request(
            f'{URL}_synapse/admin/v1/rooms'
            f'?limit={limit}&from={next_batch}',
            headers=_auth_header(),
            )
        for room in result['rooms']:
            yield room

        next_batch = result.get('next_batch', None)


def get_rooms(show_empty=False, show_private=False):
    '''
    Yields all rooms
    '''
    next_batch = '0'
    limit = '10'
    while next_batch:
        result = _matrix_request(
            f'{URL}_synapse/admin/v1/rooms'
            f'?limit={limit}&from={next_batch}',
            headers=_auth_header(),
            )
        for room in result['rooms']:
            nb_members = room.get('joined_members', 0)
            if nb_members == 0:
                if not show_empty:
                    continue
            elif nb_members <= 2:
                if not show_private:
                    continue
            room_id = room['room_id']
            room = get_room_info(room_id)
            state = get_room_state(room_id)['state']
            room['state'] = _room_state_clean(state)
            yield room

        next_batch = result.get('next_batch', None)


def get_room_info(roomid):
    return _matrix_request(
        f'{URL}_synapse/admin/v1/rooms/{roomid}',
        headers=_auth_header(),
        )


def get_room_state(roomid):
    '''
    consider using _room_state_clean on the return value
    '''
    return _matrix_request(
        f'{URL}_synapse/admin/v1/rooms/{roomid}/state',
        headers=_auth_header(),
        )


def _room_state_clean(states):
    result = {}
    for state in states:
        statetype = state['type']
        content = state['content']
        content_length = len(content)
        if content_length == 0:
            # occurs for redacted events and
            # some im.vector.modular.widgets events
            continue

        if statetype == 'm.room.create':
            for key in content:
                assert key in ('room_version', 'creator', 'm.federate')
            result.update(content)
        elif statetype == 'm.room.member':
            if 'members' not in result:
                result['members'] = []
            member = {
                'user_id': state['state_key']
            }
            member.update(content)
            result['members'].append(member)
        else:
            result[statetype] = content

        # elif statetype == 'm.room.power_levels':
        #     result['m.room.power_levels'] = content
        # elif statetype in ('m.room.topic', 'm.room.name',
        #                    'm.room.history_visibility',
        #                    'm.room.guest_access'):
        #     assert content_length == 1, \
        #          f"Unexpected keys {content.keys()} in content"
        #          f" for event type {statetype}"
        #     key = statetype.split('.')[-1]
        #     result[statetype] = content[key]
        # elif statetype == 'm.room.join_rules':
        #     content_length = len(content)
        #     assert content_length == 1, f"Unexpected keys {content.keys()}
        #                 in content for event type {statetype}"
        #     result[statetype] = content['join_rule']  # not join_rules
        # elif statetype == 'm.room.canonical_alias':
        #     for key in content.keys():
        #         if key not in ('alias', 'alt_aliases'):
        #             logger.warning(
        #                   f"Unexpected keys {content.keys()} in content"
        #                   f"for event type {statetype}")
        #     result.update(content)
        # elif statetype == 'm.room.encryption':
        #     assert content_length == 1, f"Unexpected keys
        #        {content.keys()} in content for event type {statetype}"
        #     result[statetype] = content['algorithm']  # not encryption
        # elif statetype == 'im.vector.modular.widgets':
        #     logger.warning(f'event type {statetype}: {content}')
        # else:
        #     logger.warning(
        #        f'Unsupported state type {statetype} in room states.')
    return result


def room_get_members(roomid):
    '''
    Return members (invited are NOT included)
    '''
    return _matrix_request(
        f'{URL}_synapse/admin/v1/rooms/{roomid}/members',
        headers=_auth_header(),
        )


def room_delete(room):
    '''
    room is either a id (starting with '!') or an alias (starting with '#')
    '''
    data = {
    }
    room = urllib.parse.quote(room)
    return _matrix_request(
        f'{URL}_synapse/admin/v1/rooms/{room}',
        # Example: !636q39766251:server.com, #niceroom:server.com
        method='DELETE',
        headers=_auth_header(),
        data=data,
        )


def room_makeadmin(room, user_id=None):
    '''
    room is either a id (starting with '!') or an alias (starting with '#')
    '''
    data = {}
    if user_id:
        assert user_id.endswith(f':{DOMAIN}')
        data['user_id'] = user_id
    room = urllib.parse.quote(room)
    return _matrix_request(
        f'{URL}_synapse/admin/v1/rooms/{room}/make_room_admin',
        # Example: !636q39766251:server.com, #niceroom:server.com
        method='POST',
        headers=_auth_header(),
        data=data,
        )

# #####################
# Regular user commands
# #####################


def room_invite(room, user_id):
    room = urllib.parse.quote(room)
    return _matrix_request(
        f'{URL}_matrix/client/r0/rooms/{room}/invite',
        method='POST',
        headers=_auth_header(),
        data={"user_id": user_id},
        )


def room_kick(room, user_id):
    room = urllib.parse.quote(room)
    return _matrix_request(
        f'{URL}_matrix/client/r0/rooms/{room}/kick',
        method='POST',
        headers=_auth_header(),
        data={"user_id": user_id},
        )
