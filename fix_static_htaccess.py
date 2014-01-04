#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys, os
sys.path += [ '/usr/lib/' ]
os.environ['DJANGO_SETTINGS_MODULE'] = 'ngw.settings'

from ngw.core.models import ContactGroup

for g in ContactGroup.objects.all():
    g.check_static_folder_created()
