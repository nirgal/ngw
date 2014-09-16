UPDATE contact_message SET sync_info = '{"backend": "ngw.extensions.externalmessages.onetime", ' || substr(sync_info,2);
