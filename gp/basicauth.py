# -*- coding: utf-8 -*-
#
#Example usage:
#def auth(user, pass):
#    return (user,pass)==('me', 'secret')
#
#@http_authenticate(auth, 'myrealm')
#def myview(request):
#    return HttpResponse("Hello world!")

from django.http import *
import base64


class HttpResponseAuthenticate(HttpResponse):
    """ Http response that trigger a basic http authentification on the client.
        parameter: http realm (string)"""
    def __init__(self, *args, **kwargs):
        realm = 'DOL'
        if 'realm' in kwargs:
            realm =  kwargs['realm']
            del kwargs['realm']
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 401
        self.mimetype = "text/html; charset=utf-8"
        if '"' in realm:
            raise Exception("Invalid realm \""+realm+"\" violates RFC1945")
        self['WWW-Authenticate'] = 'Basic realm="'+realm+'"'


class http_authenticate:
    """ Decorator that check authorization.
        Parameters:
            passwd_checker(user,password): function that must return True if the user is recognised.
            realm: string with the realm. See rfc1945.
    """
    def __init__(self, passwd_checker, realm):
        self.passwd_checker = passwd_checker
        self.realm = realm

    def __call__(self, func):
        def _wrapper(*args, **kwargs):
            request = args[0]
            if not 'HTTP_AUTHORIZATION' in request.META:
                user, password = "", ""
                if not self.passwd_checker(user, password):
                    return HttpResponseAuthenticate("Password requiered", realm=self.realm)
            else:
                auth = request.META['HTTP_AUTHORIZATION']
                assert auth.startswith('Basic '), "Invalid authentification scheme"
                user, password = base64.decodestring(auth[len('Basic '):]).split(':', 2)
 
                if not self.passwd_checker(user, password):
                    return HttpResponseAuthenticate("Invalid user/password", realm=self.realm)
 
            request.username = user
            return func(*args, **kwargs)

        _wrapper.__name__ = func.__name__
        return _wrapper
