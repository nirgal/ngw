import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

DOMAIN = settings.MATRIX_DOMAIN
URL = settings.MATRIX_URL
ADMIN_TOKEN = settings.MATRIX_ADMIN_TOKEN


class NoSuchUser(Exception):
    pass


def _auth_header():
    return {'Authorization': f'Bearer {ADMIN_TOKEN}'}


def _matrix_request(url, *args, **kargs):

    # convert data from dict to json
    if 'data' in kargs:
        data = kargs['data']
        data = json.dumps(data).encode('utf-8')
        kargs['data'] = data

    req = Request(url, *args, **kargs)

    try:
        response = urlopen(req)
    except HTTPError as e:
        logging.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        raise e
    except URLError as e:
        logging.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        raise e

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
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


def set_user_info(login, data, create=False):
    info = get_user_info(login)
    if not info and not create:
        logging.error(f"User {login} doesn't exist.")
        return

    return _matrix_request(
        f'{URL}_synapse/admin/v2/users/@{login}:{DOMAIN}',
        headers=_auth_header(),
        data=data,
        method='PUT',
        )


def set_user_displayname(login, displayname, create=False):
    logger = logging.getLogger('matrix')

    try:
        get_user_info(login)
    except NoSuchUser as e:
        if not create:
            logger.error(f"User {login} doesn't exists and create=False")
            raise e
    data = {
        "displayname": displayname,
        }
    return set_user_info(login, data, create)


def set_user_emails(login, emails, create=False):
    logger = logging.getLogger('matrix')

    try:
        user = get_user_info(login)
        old_emails = [
            threepid['address']
            for threepid in user.get('threepids', [])
            if threepid['medium'] == 'email'
            ]
    except NoSuchUser as e:
        if not create:
            logger.error(f"User {login} doesn't exists and create=False")
            raise e
        old_emails = []

    old_emails = set(old_emails)
    emails = set(emails)

    emails = old_emails | emails

    if old_emails == emails:
        logger.info(f'{login}: No change')
        return  # no change
    else:
        logger.info(f'{login}: {old_emails} => {emails}')

    data = {
        'threepids':
            [{'medium': 'email', 'address': email} for email in emails],
        }
    return set_user_info(login, data, create)


def deactivate_account(login, erase=False):
    data = {'erase': erase}
    return _matrix_request(
        url=f'{URL}_synapse/admin/v1/deactivate/@{login}:{DOMAIN}',
        headers=_auth_header(),
        data=data,
        )


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
