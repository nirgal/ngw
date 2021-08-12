import json
import logging
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

    logger.debug(url)

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


def get_version():
    return _matrix_request(
        f'{URL}_synapse/admin/v1/server_version'
        )


def get_users():
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


def get_user_info(login):
    try:
        return _matrix_request(
            f'{URL}_synapse/admin/v2/users/@{login}:{DOMAIN}',
            headers=_auth_header(),
            )
    except HTTPError as e:
        if e.code == 404:
            raise NoSuchUser
        else:
            raise e


def put_user(login, data):
    '''
    Low level interface to /_synapse/admin/v2/users/<USER>.
    '''
    return _matrix_request(
        f'{URL}_synapse/admin/v2/users/@{login}:{DOMAIN}',
        headers=_auth_header(),
        data=data,
        method='PUT',
        )


def set_user_info(login, name=None, emails=None, create=False):
    '''
    High level interface to create/modify account.
    '''
    logger = logging.getLogger('matrix')

    try:
        olddata = get_user_info(login)
    except NoSuchUser as e:
        if not create:
            logger.error(f"User {login} doesn't exists and create=False")
            raise e
        olddata = {}

    data = {}

    if name is not None:
        if name != olddata['displayname']:
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
    if data:
        put_user(login, data)
    else:
        logger.info(f'{login}: No change.')


def deactivate_account(login, erase=True):
    try:
        data = {'erase': erase}
        return _matrix_request(
            url=f'{URL}_synapse/admin/v1/deactivate/@{login}:{DOMAIN}',
            headers=_auth_header(),
            data=data,
            )
    except HTTPError as e:
        if e.code == 404:
            raise NoSuchUser
        else:
            raise e


def reset_password(login, password):
    data = {
        'new_password': password,
        'logout_devices': True,
        }
    return _matrix_request(
        f'{URL}_synapse/admin/v1/reset_password/@{login}:{DOMAIN}',
        headers=_auth_header(),
        data=data,
        )
