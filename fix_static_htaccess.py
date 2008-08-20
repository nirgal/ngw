#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys, os
sys.path += [ '/usr/lib/' ]
os.environ['DJANGO_SETTINGS_MODULE'] = 'ngw.settings'

from ngw.gp.alchemy_models import *

for g in Query(ContactGroup):
    dirname = "/usr/lib/ngw/static/static/g/"+str(g.id)
    if not os.path.isdir(dirname):
        print "Creating missing directory for group %i" % g.id
        os.mkdir(dirname)
    htaccess_path = os.path.join(dirname, ".htaccess")
    if not os.path.isfile(htaccess_path):
        print "Creating missing .htaccess file for group %i" % g.id
        f = open(htaccess_path, 'w')
        f.write("Require group %i\n" % g.id)
        f.close()
