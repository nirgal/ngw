# -*- coding: utf-8 -*-
#
#Example usage:
#def auth(username, password):
#    return (username,password)==('me', 'secret')
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
            passwd_checker(username,password): function that must return True if the username is recognised.
            realm: string with the realm. See rfc1945.
    """
    def __init__(self, passwd_checker, realm):
        self.passwd_checker = passwd_checker
        self.realm = realm

    def __call__(self, func):
        def _wrapper(*args, **kwargs):
            request = args[0]
            if not 'HTTP_AUTHORIZATION' in request.META:
                username, password = "", ""
                if not self.passwd_checker(username, password):
                    return HttpResponseAuthenticate("Password requiered", realm=self.realm)
            else:
                auth = request.META['HTTP_AUTHORIZATION']
                assert auth.startswith('Basic '), "Invalid authentification scheme"
                username, password = base64.decodestring(auth[len('Basic '):]).split(':', 2)
                user =  self.passwd_checker(username, password)
                if not user:
                    return HttpResponseAuthenticate("Invalid username/password", realm=self.realm)
 
            request.user = user
            return func(*args, **kwargs)

        _wrapper.__name__ = func.__name__
        return _wrapper
