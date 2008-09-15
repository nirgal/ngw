# -*- encoding utf-8 -*-
"""
This context processor just add a "banner" key that's allways available
"""

from gp.alchemy_models import *

def banner(request):
    return {'banner': Query(Config).get('banner').text }
