# -*- encoding: utf8 -*-

from __future__ import print_function, unicode_literals
from django.contrib.auth.hashers import check_password
from ngw.core.models import ( Contact, ContactFieldValue,
    FIELD_LOGIN, FIELD_PASSWORD )

class NgwAuthBackend(object):
    """
    Authenticate a user
    """

    # required by contrib.auth:
    supports_inactive_user = False
    
    # Set to True if apache doesn't do it by itself
    enable_lastconnection_updates = False

    def authenticate(self, username=None, password=None):
        if not username or not password:
            return None
        
        #TODO: skip auth/lastconnection update if REMOTE_USER is set by httpd
        try:
            login_value = ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN, value=username)
        except ContactFieldValue.DoesNotExist:
            return None
        contact = login_value.contact
        dbpassword = ContactFieldValue.objects.get(contact_id=contact.id, contact_field_id=FIELD_PASSWORD).value
        if not dbpassword:
            return None
        if check_password(password, 'crypt$$'+dbpassword):
            if self.enable_lastconnection_updates:
                contact.update_lastconnection()
            return contact
        return None # authentification failed

    def get_user(self, user_id):
        try:
            return Contact.objects.get(pk=user_id)
        except Contact.DoesNotExist:
            return None


