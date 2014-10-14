"""
WSGI config for ngw project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

"""

from __future__ import division, absolute_import, print_function, unicode_literals
import sys
import os

sys.path.append('/usr/lib')

# We defer to a DJANGO_SETTINGS_MODULE already in the environment. This breaks
# if running multiple sites in the same mod_wsgi process. To fix this, use
# mod_wsgi daemon mode with each site in its own daemon process, or use
# os.environ["DJANGO_SETTINGS_MODULE"] = "ngw.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ngw.settings")

from django import db
from django.utils.encoding import force_bytes
from django.contrib import auth
from django.contrib.auth.handlers.modwsgi import check_password
from ngw.core.models import ContactGroup
from ngw.core import perms

def groups_for_user(environ, username):
    """
    Authorizes a user based on groups
    """
    UserModel = auth.get_user_model()
    db.reset_queries()

    try:
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            return []
        if not user.is_active:
            return []
        groups = ContactGroup.objects.with_user_perms(
            user.id, wanted_flags=perms.VIEW_FILES, add_column=False)
        return [force_bytes(group.id) for group in groups]
    finally:
        db.close_old_connections()

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
from django.core.handlers.wsgi import WSGIHandler
application = WSGIHandler()

# Apply WSGI middleware here.
# from helloworld.wsgi import HelloWorldApplication
# application = HelloWorldApplication(application)
