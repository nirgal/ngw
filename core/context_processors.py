# -*- encoding utf-8 -*-

from __future__ import print_function, unicode_literals
from ngw.core.models import Config, Contact

def banner(request):
    """
    This context processor just add a "banner" key that's allways available
    """
    return {'banner': Config.objects.get(pk='banner').text }

def contactcount(request):
    """
    This context processor just add a "contactcount" key
    """
    if hasattr(request, 'user') and request.user.is_authenticated():
        return {'contactcount': Contact.objects.count() }
    else:
        return ()
