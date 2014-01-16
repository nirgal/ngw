#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import subprocess
from django.conf import settings
from django.http import HttpResponse

GPG_HOME = getattr(settings, 'GPG_HOME', None)

# TODO: use --edit-key deluid to keep only one uid per key ?

def subprocess_run(*args):
    args = [ arg.encode('utf8') for arg in args ]
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    out, err = process.communicate()
    return process.returncode, unicode(out, 'utf8', 'replace'), unicode(err, 'utf8', 'replace')

#def _split_uid(uid):
#    p1 = uid.find('<')
#    p2 = uid.find('>')
#    #print(p1, p2, len(uid))
#    if p1==-1 or p2==-1 or p2!=len(uid)-1:
#        print('Error parsing uid uid in gpg --list-keys')
#        continue
#    mail = uid[p1+1:p2]
#    name = uid[:p1].strip()
#    #print('*', mail, '*', name, '*', id)
#    return name, mail


def parse_pgp_listkey(output):
    keyring = {}
    for line in output.split('\n'):
        #print(repr(line))
        items = line.split(':')
        #print(items)
        if items[0] == 'pub':
            id = items[4]
            keyring[id] = { 'uids': [ items[9] ], 'length': items[2], 'algo': items[3], 'date': items[5] }
        elif items[0] == 'uid':
            keyring[id]['uids'].append(items[9])
    return keyring


def is_email_secure(mail_address):
    '''
    Returns True if a GPG public key is available in the local keyring.
    '''
    if not GPG_HOME:
        return False
    ret, out, err = subprocess_run('gpg', '--homedir', GPG_HOME, '--list-keys', '--with-colons', '--no-auto-check-trustdb', '<'+mail_address+'>')
    if ret:
        return False # gpg error
    keyring_1 = parse_pgp_listkey(out)
    return len(keyring_1) > 0
    
def loadkeyring():
    if not GPG_HOME:
        print('WARNING: No keyring available')
        return {}
    ret, out, err = subprocess_run('gpg', '--homedir', GPG_HOME, '--list-keys', '--with-colons', '--no-auto-check-trustdb')
    if ret:
        print(err)
        print('gpg failed.')
    return parse_pgp_listkey(out)


def __build_content(title, body):
    return '<title>'+title+'</title><p><h1>'+title+'</h1><p>'+body

# HKP views
def lookup(request):
    if not GPG_HOME:
        return HttpResponse('Keyring is disabled. Check your GPG_HOME settings', 'text/html', 404)
    op = request.GET.get('op', '')
    search = request.GET.get('search', '')
    options = request.GET.get('options', '').split(',')
    title = 'Public Key Server -- Error' # default title
    if not op:
        return HttpResponse(__build_content(title, 'pks request did not include a <b>op</b> property'), 'text/html', 200)
    if not search:
        return HttpResponse(__build_content(title, 'pks request did not include a <b>search</b> property'), 'text/html', 200)
    if search.startswith('-'):
        return HttpResponse(__build_content(title, 'pks request had an invalid <b>search</b> value'), 'text/html', 403)
    if op == 'get':
        title = 'Public Key Server -- Get "'+search+'"'
        if request.GET.get('exact', '') == 'on':
            title += ' exact'
            search = '=' + search
        ret, out, err = subprocess_run('gpg', '--homedir', GPG_HOME, '--export', '--armor', search)
        if ret:
            return HttpResponse(__build_content(title, 'Internal error running gpg'), 'text/html', 500)
        if not out:
            return HttpResponse(__build_content(title, 'No matching keys in database'), 'text/html', 404)
        if 'mr' in options:
            return HttpResponse(out, 'application/pgp-keys', 200)
        return HttpResponse(__build_content(title, '<pre>'+out+'</pre>'), 'text/html', 200)

    return HttpResponse(__build_content(title, 'pks request had an invalid <b>op</b> property'), 'text/html', 501)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    options, args = parser.parse_args()
    print(loadkeyring())
