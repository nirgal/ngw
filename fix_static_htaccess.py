#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys, os
sys.path += [ '/usr/lib/' ]
os.environ['DJANGO_SETTINGS_MODULE'] = 'ngw.settings'

from ngw.gp.alchemy_models import *

for g in Query(ContactGroup):
    g.check_static_folder_created()
