"""
WSGI config for ngw project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/howto/deployment/wsgi/
"""

import os
import sys

sys.path.append('/usr/lib')

# We defer to a DJANGO_SETTINGS_MODULE already in the environment. This breaks
# if running multiple sites in the same mod_wsgi process. To fix this, use
# mod_wsgi daemon mode with each site in its own daemon process, or use
# os.environ["DJANGO_SETTINGS_MODULE"] = "ngw.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ngw.settings")

from django import db
from django.contrib import auth
from django.contrib.auth.handlers.modwsgi import check_password
from django.core.wsgi import get_wsgi_application
from django.utils.encoding import force_bytes

from ngw.core import perms
from ngw.core.models import ContactGroup

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

application = get_wsgi_application()
