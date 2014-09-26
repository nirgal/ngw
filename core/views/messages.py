# -*- encoding: utf-8 -*-
'''
Messages managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

import json
from datetime import date, timedelta
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, Http404
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.timezone import now
from django.utils.importlib import import_module
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, FormView
from django import forms
from django.contrib import messages
from ngw.core.models import Contact, ContactMsg
from ngw.core import perms
from ngw.core.views.generic import InGroupAcl, NgwListView, BaseListFilter
from ngw.core.widgets import NgwCalendarWidget


#######################################################################
#
# Messages list
#
#######################################################################


class MessageDirectionFilter(BaseListFilter):
    title = _('direction')
    parameter_name = 'answer'
    def lookups(self, request, view):
        return (
            ('1', _('Received')),
            ('0', _('Sent')),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val is None:
            return queryset
        filter_answer = val == '1'
        return queryset.filter(is_answer=filter_answer)


class MessageReadFilter(BaseListFilter):
    title = _('read status')
    parameter_name = 'unread'
    def lookups(self, request, view):
        return (
            ('1', _('Unread')),
            ('0', _('Read')),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val is None:
            return queryset
        filter_unread = val == '1'
        return queryset.filter(read_date__isnull=filter_unread)


class MessageListView(InGroupAcl, NgwListView):
    cols = [
        (_('Flags'), None, 'nice_flags', None),
        (_('Date UTC'), None, 'nice_date', 'send_date'),
        (_('Contact'), None, 'contact', 'contact__name'),
        (_('Subject'), None, 'subject', 'subject'),
    ]
    template_name = 'message_list.html'
    filter_list = (MessageDirectionFilter, MessageReadFilter)

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_view_msgs_cg(user.id, group.id):
            raise PermissionDenied

    def get_root_queryset(self):
        return ContactMsg.objects \
            .filter(group_id=self.contactgroup.id) \
            .order_by('-send_date')

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Messages for %s') % cg.name_with_date()
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('messages', _('messages')))
        context['active_submenu'] = 'messages'
        context.update(kwargs)
        return super(MessageListView, self).get_context_data(**context)


#######################################################################
#
# Messages sending
#
#######################################################################

try:
    EXTERNAL_MESSAGE_BACKEND_NAME = settings.EXTERNAL_MESSAGE_BACKEND
except AttributeError as e:
    raise ImproperlyConfigured(('You need to add an "EXTERNAL_MESSAGE_BACKEND" handler in your settings.py: "%s"'
        % e))
try:
    EXTERNAL_MESSAGE_BACKEND = import_module(EXTERNAL_MESSAGE_BACKEND_NAME)
except ImportError as e:
    raise ImproperlyConfigured(('Error importing external messages backend module %s: "%s"'
        % (EXTERNAL_MESSAGE_BACKEND_NAME, e)))


class SendMessageForm(forms.Form):
    def __init__(self, contactgroup, *args, **kwargs):
        super(SendMessageForm, self).__init__(*args, **kwargs)

        self.fields['ids'] = forms.CharField(widget=forms.widgets.HiddenInput)
        if self.support_expiration_date():
            if contactgroup.date:
                initial_date = contactgroup.date
            else:
                initial_date = date.today() + timedelta(days=21)
            self.fields['expiration_date'] = forms.DateField(
                label=_('Expiration date'),
                widget=NgwCalendarWidget(attrs={'class':'vDateField'}),
                initial=initial_date)
        self.fields['subject'] = forms.CharField(
            label=_('Subject'), max_length=64,
            widget=forms.widgets.Input(attrs={'size': '64'}))
        self.fields['message'] = forms.CharField(
            label=_('Message'),
            widget=forms.Textarea(attrs={'style': 'width:100%', 'rows': '20'}))


    def support_expiration_date(self):
        return getattr(EXTERNAL_MESSAGE_BACKEND, 'SUPPORTS_EXPIRATION', False)


    def clean_expiration_date(self):
        expiration_date = self.cleaned_data['expiration_date']
        if expiration_date <= date.today():
            raise forms.ValidationError(_('The expiration date must be in the future.'))
        return expiration_date


    def send_message(self, group):
        contacts_noemail = []

        language = translation.get_language()
        sync_info = {
            'backend': EXTERNAL_MESSAGE_BACKEND_NAME,
            'language': language,
        }
        if self.support_expiration_date():
            expiration = (self.cleaned_data['expiration_date'] - date.today()).days
            sync_info['expiration'] = expiration
        json_sync_info = json.dumps(sync_info)

        for contact_id in self.cleaned_data['ids'].split(','):
            contact = get_object_or_404(Contact, pk=contact_id)
            if not contact.get_fieldvalues_by_type('EMAIL'):
                contacts_noemail.append(contact)
            contact_msg = ContactMsg(contact=contact, group=group)
            contact_msg.send_date = now()
            contact_msg.subject = self.cleaned_data['subject']
            contact_msg.text = self.cleaned_data['message']
            contact_msg.sync_info = json_sync_info
            contact_msg.save()
        return contacts_noemail


class SendMessageView(InGroupAcl, FormView):
    form_class = SendMessageForm
    template_name = 'message_send.html'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_write_msgs_cg(user.id, group.id):
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super(SendMessageView, self).get_form_kwargs()
        kwargs['contactgroup'] = self.contactgroup
        return kwargs

    def get_initial(self):
        return {'ids': self.request.REQUEST['ids']}

    def form_valid(self, form):
        contacts_noemail = form.send_message(self.contactgroup)
        nbmessages = len(form.cleaned_data['ids'].split(','))
        if nbmessages == 1:
            success_msg = _('Message stored.')
        else:
            success_msg = _('%s messages stored.') % nbmessages
        messages.add_message(self.request, messages.SUCCESS, success_msg)
        if contacts_noemail:
            nb_noemail = len(contacts_noemail)
            if nb_noemail == 1:
                error_msg = _("One contact doesn't have an email address.")
            else:
                error_msg = (_("%s contacts don't have an email address.")
                    % nb_noemail)
            messages.add_message(self.request, messages.WARNING,
                translation.string_concat(error_msg,
                    _(" The message will be kept here until you define his email address.")))
        return super(SendMessageView, self).form_valid(form)

    def get_success_url(self):
        return self.contactgroup.get_absolute_url()+'messages/'

    def get_context_data(self, **kwargs):
        cg = self.contactgroup

        #if group.date and group.date <= now().date():
        #    return HttpResponse('Date error. Event is over.')

        ids = self.request.REQUEST['ids'].split(',')
        nbcontacts = len(ids)
        noemails = []
        for contact in Contact.objects.filter(id__in=ids):
            c_emails = contact.get_fieldvalues_by_type('EMAIL')
            if not c_emails:
                noemails.append(contact)

        context = {}
        context['title'] = _('Send message in %s') % cg.name_with_date()
        context['nbcontacts'] = nbcontacts
        context['noemails'] = noemails
        context['nav'] = cg.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component(('send_message', _('send message')))
        context['active_submenu'] = 'messages'

        context.update(kwargs)
        return super(SendMessageView, self).get_context_data(**context)


#######################################################################
#
# Message detail
#
#######################################################################


class MessageDetailView(InGroupAcl, DetailView):
    pk_url_kwarg = 'mid'
    model = ContactMsg
    template_name = 'message_detail.html'

    def check_perm_groupuser(self, group, user):
        if not perms.c_can_view_msgs_cg(user.id, group.id):
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        if self.object.group != self.contactgroup:
            # attempt to read an object from another group
            raise PermissionDenied
        if self.object.is_answer and self.object.read_date is None:
            if perms.c_can_write_msgs_cg(self.request.user.id, self.contactgroup.id):
                self.object.read_date = now()
                self.object.read_by = self.request.user
                self.object.save()
            else:
                messages.add_message(
                    self.request, messages.WARNING,
                    _("You don't have the permission to flag that message as read."))
        cg = self.contactgroup
        context = {}
        if self.object.is_answer:
            context['title'] = _('Message from %(contactname)s in group %(groupname)s') % {
                'contactname': self.object.contact.name,
                'groupname': cg.name_with_date(),
            }
        else:
            context['title'] = _('Message to %(contactname)s in group %(groupname)s') % {
                'contactname': self.object.contact.name,
                'groupname': cg.name_with_date(),
            }
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('messages', _('messages')))
        context['cig_url'] = self.contactgroup.get_absolute_url() + 'members/' + force_text(self.object.contact_id)
        context['active_submenu'] = 'messages'

        flags = perms.cig_flags_int(self.object.contact.id, cg.id)
        flags_direct = perms.cig_flags_direct_int(self.object.contact.id, cg.id)

        membership_str =  perms.int_to_text(flags_direct, flags & ~flags_direct)
        if flags_direct & perms.MEMBER:
            membership = 'member'
        elif flags_direct & perms.INVITED:
            membership = 'invited'
        elif flags_direct & perms.DECLINED:
            membership = 'declined'
        else:
            membership = ''
        context['membership'] = membership
        context['membership_str'] = membership_str
        context['membership_title'] = _('%(contactname)s in group %(groupname)s') % {
            'contactname': self.object.contact.name,
            'groupname': cg.name_with_date()}
        if perms.c_can_write_msgs_cg(self.request.user.id, self.contactgroup.id):
            context['reply_url'] = "../members/send_message?ids=%s" % \
                self.object.contact_id
        context.update(kwargs)
        return super(MessageDetailView, self).get_context_data(**context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get('unread', None):
            self.object.read_date = None
            self.object.read_by = None
            self.object.save()
            return HttpResponseRedirect(self.contactgroup.get_absolute_url() + 'messages/?&_order=-1')
        raise Http404


#######################################################################
#
# Messages toggle
#
#######################################################################


#from ngw.core.response import JsonHttpResponse
#from django.shortcuts import get_object_or_404
#class MessageToggleReadView(InGroupAcl, View):
#    def check_perm_groupuser(self, group, user):
#        if not perms.c_can_write_msgs_cg(user.id, group.id):
#            raise PermissionDenied
#
#    def get(self, request, *args, **kwargs):
#        message_id = self.kwargs.get('mid', None)
#        try:
#            message_id = int(message_id)
#        except (ValueError, TypeError):
#            raise Http404
#        message = get_object_or_404(ContactMsg, pk=message_id)
#        if message.group_id != self.contactgroup.id:
#            return HttpResponse('Bad group')
#
#        return JsonHttpResponse({'test': 'ok'})
