# -*- encoding utf-8 -*-
"""
This context processor just add a "contactcount" key
"""

from alchemy_models import *

def contactcount(request):
    return {'contactcount': Query(Contact).count() }
