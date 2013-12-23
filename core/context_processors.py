# -*- encoding utf-8 -*-

from alchemy_models import *

def banner(request):
    """
    This context processor just add a "banner" key that's allways available
    """
    return {'banner': Query(Config).get('banner').text }

def contactcount(request):
    """
    This context processor just add a "contactcount" key
    """
    return {'contactcount': Query(Contact).count() }
