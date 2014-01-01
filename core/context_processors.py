# -*- encoding utf-8 -*-

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
    return {'contactcount': Contact.objects.count() }
