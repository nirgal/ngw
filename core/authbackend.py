from django.contrib.auth.models import update_last_login
from django.contrib.auth.signals import user_logged_in

from ngw.core.models import Contact

# Ugly work around for NOT using update_last_login that is hardcoded in
# crontrib.auth :
user_logged_in.disconnect(update_last_login)


class NgwAuthBackend(object):
    """
    Authenticate a user
    """

    # required by contrib.auth:
    supports_inactive_user = False

    def authenticate(self, request, username=None, password=None):
        if not username or not password:
            return None

        try:
            contact = Contact.objects.get_by_natural_key(username)
        except (Contact.DoesNotExist, Contact.MultipleObjectsReturned):
            return None

        if contact.check_password(password):
            contact.update_lastconnection()
            return contact
        return None  # authentification failed

    def get_user(self, user_id):
        try:
            return Contact.objects.get(pk=user_id)
        except Contact.DoesNotExist:
            return None
