#!/usr/bin/env python3

import subprocess

from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View
from gnupg import GPG

GPG_HOME = getattr(settings, 'GPG_HOME', None)

# TODO: use --edit-key deluid to keep only one uid per key ?

def get_instance():
    return GPG(gnupghome=GPG_HOME, options=['--no-auto-check-trustdb'], verbose=False)

def is_email_secure(mail_address):
    '''
    Returns True if a GPG public key is available in the local keyring.
    '''
    gpg = get_instance()
    return bool(gpg.export_keys(mail_address))

def loadkeyring():
    if not GPG_HOME:
        print('WARNING: No keyring available')
        return {}
    return get_instance().list_keys()


class GpgLookupView(View):
    def _build_content(title, body):
        return '<title>'+title+'</title><p><h1>'+title+'</h1><p>'+body

    def get(self, request):
        if not GPG_HOME:
            return HttpResponse('Keyring is disabled. Check your GPG_HOME settings', 'text/html', 404)
        op = request.GET.get('op', '')
        search = request.GET.get('search', '')
        options = request.GET.get('options', '').split(',')
        title = 'Public Key Server -- Error' # default title
        if not op:
            return HttpResponse(_build_content(title, 'pks request did not include a <b>op</b> property'), 'text/html', 200)
        if not search:
            return HttpResponse(_build_content(title, 'pks request did not include a <b>search</b> property'), 'text/html', 200)
        if search.startswith('-'):
            return HttpResponse(_build_content(title, 'pks request had an invalid <b>search</b> value'), 'text/html', 403)
        if op == 'get':
            title = 'Public Key Server -- Get "'+search+'"'
            if request.GET.get('exact', '') == 'on':
                title += ' exact'
                search = '=' + search
            key = get_instance().export_keys(search)
            if not key:
                return HttpResponse(_build_content(title, 'No matching keys in database'), 'text/html', 404)
            if 'mr' in options:
                return HttpResponse(key, 'application/pgp-keys', 200)
            return HttpResponse(_build_content(title, '<pre>'+key+'</pre>'), 'text/html', 200)
    
        return HttpResponse(_build_content(title, 'pks request had an invalid <b>op</b> property'), 'text/html', 501)
