# -*- encoding: utf-8 -*-

from django.contrib.messages.storage.base import BaseStorage
from ngw.core.alchemy_models import Session, Query, ContactSysMsg

class NgwMessageStorage(BaseStorage):
    """
    Django 1.0 style for storing messages in the database.
    Compatible with latest versions.
    """
    
    def _get(self, *args, **kwargs):
        contact_id = self.request.user.id
        messages = []
        for sm in Query(ContactSysMsg).filter(ContactSysMsg.contact_id==contact_id):
            messages.append(sm.message)
            Session.delete(sm)
        return messages, True # Returned everything
    
    def _store(self, messages, response, *args, **kwargs):
        contact_id = self.request.user.id
        for message in messages:
            ContactSysMsg(contact_id, message.message)
        #N# Session.commit()
        return [] # Unstored messages
