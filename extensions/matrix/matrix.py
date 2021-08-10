import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

DOMAIN = settings.MATRIX_DOMAIN
URL = settings.MATRIX_URL
ADMIN_TOKEN = settings.MATRIX_ADMIN_TOKEN


def _auth_header():
    return {'Authorization': f'Bearer {ADMIN_TOKEN}'}


def get_version():
    url = f'{URL}_synapse/admin/v1/server_version'
    req = Request(
        url,
        )
    try:
        response = urlopen(req)
    except HTTPError as e:
        logging.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        return
    except URLError as e:
        logging.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        return

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
    return result_json


def get_users():
    next_token = '0'
    limit = '10'
    while next_token:
        url = f'{URL}_synapse/admin/v2/users' \
              f'?deactivated=true&limit={limit}&from={next_token}'
        req = Request(
            url,
            headers=_auth_header(),
            )
        try:
            response = urlopen(req)
        except HTTPError as e:
            logging.error(
                'The server couldn\'t fulfill the request. Error code: %s',
                e.code)
            return
        except URLError as e:
            logging.error(
                'We failed to reach a server. Reason: %s',
                e.reason)
            return
        result_bytes = response.read()
        result_str = str(result_bytes, encoding='utf-8')
        result_json = json.loads(result_str)
        for user in result_json['users']:
            yield user
        next_token = result_json.get('next_token', None)


def get_user_info(login):
    url = f'{URL}_synapse/admin/v2/users/@{login}:{DOMAIN}'
    req = Request(
        url,
        headers=_auth_header(),
        )
    try:
        response = urlopen(req)
    except HTTPError as e:
        logging.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        return
    except URLError as e:
        logging.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        return

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
    return result_json


def set_user_info(login, data, create=False):
    info = get_user_info(login)
    if not info and not create:
        logging.error("User %s doesn't exist.", login)
        return

    url = f'{URL}_synapse/admin/v2/users/@{login}:{DOMAIN}'
    req = Request(
        url,
        headers=_auth_header(),
        data=json.dumps(data).encode('utf-8'),
        method='PUT',
        )

    try:
        response = urlopen(req)
    except HTTPError as e:
        logging.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        return
    except URLError as e:
        logging.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        return

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
    return result_json


def set_user_displayname(login, displayname, create=False):
    data = {
        "displayname": displayname,
        }
    return set_user_info(login, data, create)


def set_user_emails(login, emails, create=False):
    logger = logging.getLogger('matrix')

    data = {}

    user = get_user_info(login)
    if not user:
        if not create:
            logger.error(f"User {login} doesn't exists and create=False")
            return
        user = {}
        data['deactivated'] = False

    old_emails = [
        threepid['address']
        for threepid in user.get('threepids', [])
        if threepid['medium'] == 'email'
        ]
    old_emails = set(old_emails)
    emails = set(emails)

    emails = old_emails | emails

    if old_emails == emails:
        logger.info(f'{login}: No change')
        return  # no change
    else:
        logger.info(f'{login}: {old_emails} => {emails}')

    data['threepids'] = [
        {'medium': 'email', 'address': email}
        for email in emails
        ]
    return set_user_info(login, data, create)


def deactivate_account(login, erase=False):
    url = f'{URL}_synapse/admin/v1/deactivate/@{login}:{DOMAIN}'
    data = {'erase': erase}
    req = Request(
        url,
        headers=_auth_header(),
        data=json.dumps(data).encode('utf-8'),
        )

    try:
        response = urlopen(req)
    except HTTPError as e:
        logging.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        return
    except URLError as e:
        logging.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        return

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
    return result_json


def reset_password(login, password):
    url = f'{URL}_synapse/admin/v1/reset_password/@{login}:{DOMAIN}'
    data = {
        'new_password': password,
        'logout_devices': True,
        }
    req = Request(
        url,
        headers=_auth_header(),
        data=json.dumps(data).encode('utf-8'),
        )

    try:
        response = urlopen(req)
    except HTTPError as e:
        logging.error(
            'The server couldn\'t fulfill the request. Error code: %s',
            e.code)
        return
    except URLError as e:
        logging.error(
            'We failed to reach a server. Reason: %s',
            e.reason)
        return

    result_bytes = response.read()
    result_str = str(result_bytes, encoding='utf-8')
    result_json = json.loads(result_str)
    return result_json
