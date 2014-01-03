# -*- coding: utf-8 -*-

"""
This module implements RFC2617 "http basic auth"
"""
import base64
from functools import wraps
from django.contrib.auth import authenticate as auth_authenticate
from django.http import HttpResponse


class HttpResponseAuthenticate(HttpResponse):
    """ Http response that trigger a basic http authentification on the client.
        parameter: http realm (string)"""
    def __init__(self, *args, **kwargs):
        if 'realm' in kwargs:
            realm =  kwargs['realm']
            del kwargs['realm']
        else:
            realm = 'ngw'
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 401
        self.mimetype = "text/html; charset=utf-8"
        if '"' in realm:
            raise Exception("Invalid realm \""+realm+"\" violates RFC1945")
        self['WWW-Authenticate'] = 'Basic realm="'+realm+'"'


# Decorator to check a user is loged in
# Blocks requests if not and returns a 401 code that triggers browser input
# Note that it does NOT verify the membership of any groups, not even users
# Do use @require_group
def login_required():
    def decorator(f):
        @wraps(f)
        def wrapper(request, *args, **kargs):
            if not hasattr(request, 'user'):
                return HttpResponseAuthenticate(u'Password required')
            return f(request, *args, **kargs)
        return wrapper
    return decorator


class AuthenticationMiddleware:
    """
    Check user credidentials and setup request.user
    Authentication is done using settings.AUTHENTICATION_BACKENDS
    Warning, if no user is logged in, user will NOT be set (unlike django)
    """
    def process_request(self, request):
        if request.path == u'/logout':
            return # special hack, so that //logout@exemple.net/logout will work
        try:
            auth = request.META.pop('HTTP_AUTHORIZATION')
            # key gets removed, so it's not displayed in error 500 handler
        except KeyError:
            return # It is ok not to be logged in (logout view, ...)
        assert auth.startswith('Basic '), "Invalid authentification scheme"
        username, password = base64.decodestring(auth[len('Basic '):]).split(':', 2)
        username = unicode(username, 'utf-8', 'replace')
        password = unicode(password, 'utf-8', 'replace')
        user = auth_authenticate(username=username, password=password)
        if not user:
            return HttpResponseAuthenticate("Invalid username/password")
        request.user = user
