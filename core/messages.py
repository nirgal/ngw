# -*- encoding: utf-8 -*-

from __future__ import print_function, unicode_literals
from django.contrib.messages.storage.base import BaseStorage
from ngw.core.models import ContactSysMsg

class NgwMessageStorage(BaseStorage):
    """
    Django 1.0 style for storing messages in the database.
    Compatible with latest versions.
    """
    
    def _get(self, *args, **kwargs):
        messages = []
        try:
            contact_id = self.request.user.id
        except AttributeError:
            pass # No message if no user is loggued in
        else:
            for csm in ContactSysMsg.objects.filter(contact_id=contact_id):
                messages.append(csm.message)
                csm.delete()
        return messages, True # Returned everything
    
    def _store(self, messages, response, *args, **kwargs):
        contact_id = self.request.user.id
        for message in messages:
            csm = ContactSysMsg(contact_id=contact_id, message=message)
            csm.save()
        return [] # No unstored messages left
