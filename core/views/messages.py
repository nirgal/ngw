'''
Messages managing views
'''

import email
import json
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formatdate
from importlib import import_module

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import filters
from django.contrib.admin.widgets import AdminDateWidget
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import translation
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.generic import DetailView, FormView

from ngw.core import perms
from ngw.core.models import Contact, ContactInGroup, ContactMsg
from ngw.core.views.generic import InGroupAcl, NgwListView

#######################################################################
#
# Messages list
#
#######################################################################


class MessageDirectionFilter(filters.SimpleListFilter):
    title = ugettext_lazy('direction')
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


class MessageReadFilter(filters.SimpleListFilter):
    title = ugettext_lazy('read status')
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


class MessageContactFilter(filters.SimpleListFilter):
    title = ugettext_lazy('contact')
    parameter_name = 'contact'
    template = 'admin/filter_select.html'

    def lookups(self, request, view):
        result = []
        contacts = Contact.objects.all()
        try:
            group_id = view.kwargs.get('gid', None)
        except AttributeError:
            group_id = None
        if group_id:
            contacts = contacts.extra(
                tables=('v_c_appears_in_cg',),
                where=(
                    'v_c_appears_in_cg.contact_id=contact.id',
                    'v_c_appears_in_cg.group_id={}'.format(group_id)))
        for contact in contacts:
            result.append((contact.id, contact.name))
        return result

    def queryset(self, request, queryset):
        val = self.value()
        if val is None:
            return queryset
        return queryset.filter(contact_id=val)


class MessageListView(InGroupAcl, NgwListView):
    list_display = 'nice_flags', 'nice_date', 'contact', 'subject'
    list_display_links = 'subject',
    template_name = 'message_list.html'
    list_filter = (
        MessageDirectionFilter, MessageReadFilter, MessageContactFilter)
    append_slash = False
    search_fields = 'subject', 'text',

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.VIEW_MSGS:
            raise PermissionDenied

    def get_root_queryset(self):
        return ContactMsg.objects \
            .filter(group_id=self.contactgroup.id)

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Messages for {}').format(cg)
        context['nav'] = cg.get_smart_navbar()
        context['nav'].add_component(('messages', _('messages')))
        context['active_submenu'] = 'messages'
        context.update(kwargs)
        return super().get_context_data(**context)


#######################################################################
#
# Messages sending
#
#######################################################################

try:
    EXTERNAL_MESSAGE_BACKEND_NAME = settings.EXTERNAL_MESSAGE_BACKEND
except AttributeError as e:
    raise ImproperlyConfigured(('You need to add an "EXTERNAL_MESSAGE_BACKEND"'
                                ' handler in your settings.py: "{}"'
                                .format(e)))
try:
    EXTERNAL_MESSAGE_BACKEND = import_module(EXTERNAL_MESSAGE_BACKEND_NAME)
except ImportError as e:
    raise ImproperlyConfigured(('Error importing external messages backend'
                                ' module {}: "{}"'
                                .format(EXTERNAL_MESSAGE_BACKEND_NAME, e)))


def MimefyMessage(subject, text, files):
    policy = email.policy.EmailPolicy(utf8=True, linesep='\r\n')
    msg = EmailMessage(policy)
    msg['Date'] = formatdate()
    msg['Subject'] = subject
    msg.set_content(text, 'utf-8')
    for f in files:
        maintype, subtype = f.content_type.split('/')
        msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                           filename=f.name)

    str = msg.as_string()
    return str


class SendMessageForm(forms.Form):
    def __init__(self, contactgroup, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['ids'] = forms.CharField(widget=forms.widgets.HiddenInput)
        if self.support_expiration_date():
            if contactgroup.date:
                initial_date = contactgroup.date
            else:
                initial_date = date.today() + timedelta(days=21)
            self.fields['expiration_date'] = forms.DateField(
                label=_('Expiration date'),
                widget=AdminDateWidget,
                initial=initial_date)
        self.fields['subject'] = forms.CharField(
            label=_('Subject'), max_length=64,
            widget=forms.widgets.Input(attrs={'size': '64'}))
        self.fields['message'] = forms.CharField(
            label=_('Message'),
            widget=forms.Textarea(attrs={'style': 'width:100%', 'rows': '20'}))
        self.fields['files'] = forms.FileField(
            required=False,
            widget=forms.ClearableFileInput(attrs={'multiple': True}))

    def support_expiration_date(self):
        return getattr(EXTERNAL_MESSAGE_BACKEND, 'SUPPORTS_EXPIRATION', False)

    def clean_expiration_date(self):
        expiration_date = self.cleaned_data['expiration_date']
        date_cleaner = getattr(
            EXTERNAL_MESSAGE_BACKEND, 'clean_expiration_date', None)
        if date_cleaner:
            expiration_date = date_cleaner(expiration_date)
        return expiration_date

    def clean_files(self):
        # Hack for multiple files
        if self.files:
            return self.files.getlist('files')
        else:
            return []

    def send_message(self, group):
        contacts_noemail = []

        language = translation.get_language()
        sync_info = {
            'backend': EXTERNAL_MESSAGE_BACKEND_NAME,
            'language': language,
        }
        if self.support_expiration_date():
            delta = self.cleaned_data['expiration_date'] - date.today()
            expiration = delta.days
            sync_info['expiration'] = expiration
        json_sync_info = json.dumps(sync_info)

        for contact_id in self.cleaned_data['ids'].split(','):
            contact = get_object_or_404(Contact, pk=contact_id)
            if not contact.get_fieldvalues_by_type('EMAIL'):
                contacts_noemail.append(contact)
            contact_msg = ContactMsg(contact=contact, group=group)
            contact_msg.send_date = now()
            contact_msg.subject = self.cleaned_data['subject']
            contact_msg.text = MimefyMessage(self.cleaned_data['subject'],
                                             self.cleaned_data['message'],
                                             self.cleaned_data['files'])
            contact_msg.sync_info = json_sync_info
            contact_msg.save()
        return contacts_noemail


class SendMessageView(InGroupAcl, FormView):
    form_class = SendMessageForm
    template_name = 'message_send.html'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.WRITE_MSGS:
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contactgroup'] = self.contactgroup
        return kwargs

    def get_initial(self):
        if self.request.method == 'POST':
            querydict = self.request.POST
        else:
            querydict = self.request.GET
        return {'ids': querydict['ids']}

    def form_valid(self, form):
        contacts_noemail = form.send_message(self.contactgroup)
        nbmessages = len(form.cleaned_data['ids'].split(','))
        if nbmessages == 1:
            success_msg = _('Message stored.')
        else:
            success_msg = _('{} messages stored.').format(nbmessages)
        messages.add_message(self.request, messages.SUCCESS, success_msg)
        if contacts_noemail:
            nb_noemail = len(contacts_noemail)
            if nb_noemail == 1:
                error_msg = _("One contact doesn't have an email address.")
            else:
                error_msg = (_("{} contacts don't have an email address.")
                             .format(nb_noemail))
            messages.add_message(
                self.request, messages.WARNING,
                translation.string_concat(
                    error_msg,
                    _(" The message will be kept here until you define his"
                      " email address.")))
        return super().form_valid(form)

    def get_success_url(self):
        return self.contactgroup.get_absolute_url()+'messages/'

    def get_context_data(self, **kwargs):
        cg = self.contactgroup

        # if group.date and group.date <= now().date():
        #    return HttpResponse('Date error. Event is over.')

        if self.request.method == 'POST':
            querydict = self.request.POST
        else:
            querydict = self.request.GET
        ids = querydict['ids'].split(',')
        nbcontacts = len(ids)
        noemails = []
        for contact in Contact.objects.filter(id__in=ids):
            c_emails = contact.get_fieldvalues_by_type('EMAIL')
            if not c_emails:
                noemails.append(contact)

        context = {}
        context['title'] = _('Send message in {}').format(cg)
        context['nbcontacts'] = nbcontacts
        context['noemails'] = noemails
        context['nav'] = cg.get_smart_navbar() \
            .add_component(('members', _('members'))) \
            .add_component(('send_message', _('send message')))
        context['active_submenu'] = 'messages'

        context.update(kwargs)
        return super().get_context_data(**context)


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
        if not group.userperms & perms.VIEW_MSGS:
            raise PermissionDenied

    def get_object(self, queryset=None):
        msg = super().get_object(queryset)
        # Check the group match the one of the url
        if msg.group_id != self.contactgroup.id:
            raise PermissionDenied
        return msg

    def get_context_data(self, **kwargs):
        if self.object.group != self.contactgroup:
            # attempt to read an object from another group
            raise PermissionDenied
        if self.object.is_answer and self.object.read_date is None:
            if self.contactgroup.userperms & perms.WRITE_MSGS:
                self.object.read_date = now()
                self.object.read_by = self.request.user
                self.object.save()
            else:
                messages.add_message(
                    self.request, messages.WARNING,
                    _("You don't have the permission to mark that message as"
                      " read."))
        cg = self.contactgroup
        context = {}
        if self.object.is_answer:
            context['title'] = _(
                'Message from {contactname} in group {groupname}').format(
                contactname=self.object.contact.name,
                groupname=cg)
        else:
            context['title'] = _(
                'Message to {contactname} in group {groupname}').format(
                contactname=self.object.contact.name,
                groupname=cg)
        try:
            context['sync_info'] = json.loads(self.object.sync_info)
        except ValueError:
            context['sync_info'] = {}
        context['nav'] = cg.get_smart_navbar()
        context['nav'].add_component(('messages', _('messages')))
        context['cig_url'] = (
            self.contactgroup.get_absolute_url()
            + 'members/'
            + str(self.object.contact_id))
        context['active_submenu'] = 'messages'

        # 201505
        try:
            cig = ContactInGroup.objects.get(
                    contact_id=self.object.contact.id,
                    group_id=cg.id)
        except ContactInGroup.DoesNotExist:
            pass
        else:
            context['membership_note'] = cig.note
        flags = perms.cig_flags_int(self.object.contact.id, cg.id)
        flags_direct = perms.cig_flags_direct_int(self.object.contact.id,
                                                  cg.id)

        membership_str = perms.int_to_text(flags_direct, flags & ~flags_direct)
        context['membership'] = perms.int_to_flags(flags_direct)
        context['membership_str'] = membership_str
        context['membership_title'] = _(
            '{contactname} in group {groupname}').format(
            contactname=self.object.contact.name,
            groupname=cg)
        if self.contactgroup.userperms & perms.WRITE_MSGS:
            context['reply_url'] = "../members/send_message?ids={}".format(
                self.object.contact_id)
        context.update(kwargs)
        return super().get_context_data(**context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get('unread', None):
            self.object.read_date = None
            self.object.read_by = None
            self.object.save()
            return HttpResponseRedirect(
                self.contactgroup.get_absolute_url() + 'messages/')
        raise Http404


#######################################################################
#
# Messages toggle
#
#######################################################################


# from django.http.response import JsonResponse
# from django.shortcuts import get_object_or_404
# class MessageToggleReadView(InGroupAcl, View):
#     def check_perm_groupuser(self, group, user):
#         if not group.userperms & perms.WRITE_MSGS:
#             raise PermissionDenied
#
#     def get(self, request, *args, **kwargs):
#         message_id = self.kwargs.get('mid', None)
#         try:
#             message_id = int(message_id)
#         except (ValueError, TypeError):
#             raise Http404
#         message = get_object_or_404(ContactMsg, pk=message_id)
#         if message.group_id != self.contactgroup.id:
#             return HttpResponse('Bad group')
#
#         return JsonResponse({'test': 'ok'})
