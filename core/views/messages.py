# -*- encoding: utf-8 -*-
'''
Messages managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, Http404
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.contrib import messages
from ngw.core.models import (
    GROUP_USER_NGW,
    FIELD_EMAIL,
    CIGFLAG_MEMBER, CIGFLAG_INVITED, CIGFLAG_DECLINED,
    ContactMsg, ContactGroup, ContactInGroup)
from ngw.core import perms
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import NgwUserMixin, NgwListView

#from django.views.generic.base import ContextMixin
#class IngroupMixin(ContextMixin):
#    '''
#    Views using that mixin must define a "gid" url pattern.
#    Mixin will setup a self.contactgroup and set up context.
#    '''
#    def dispatch(self, request, *args, **kwargs): # FIXME dispatch is view only stuff
#        group_id = self.kwargs.get('gid', None)
#        try:
#            group_id = int(group_id)
#        except (ValueError, TypeError):
#            raise Http404
#        contactgroup = get_object_or_404(ContactGroup, pk=group_id)
#        self.contactgroup = contactgroup
#        return super(IngroupMixin, self).get(request, *args, **kwargs)
#
#    def get_context_data(self, **kwargs):
#        cg = self.contactgroup
#        context['cg'] = cg
#        context['cg_perms'] = cg.get_contact_perms(self.request.user.id)
#        return super(IngroupMixin, self).get_context_data(**context)


#######################################################################
#
# Messages list
#
#######################################################################


class MessageListView(NgwUserMixin, NgwListView):
    cols = [
        (_('Date UTC'), None, 'nice_date', 'send_date'),
        (_('Direction'), None, 'direction', 'is_answer'),
        (_('Read'), None, 'nice_read', None),
        (_('Contact'), None, 'contact', 'contact__name'),
        (_('Subject'), None, 'subject', 'subject'),
        #(_('Move'), None, lambda cf: '<a href='+str(cf.id)+'/moveup>Up</a> <a href='+str(cf.id)+'/movedown>Down</a>', None),
    ]
    template_name = 'message_list.html'

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        group_id = self.kwargs.get('gid', None)
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            raise Http404
        contactgroup = get_object_or_404(ContactGroup, pk=group_id)
        if not perms.c_can_view_msgs_cg(request.user.id, group_id):
            raise PermissionDenied
        self.contactgroup = contactgroup
        return super(MessageListView, self).dispatch(request, *args, **kwargs)


    def get_root_queryset(self):
        return ContactMsg.objects \
            .filter(group_id=self.contactgroup.id) \
            .order_by('-send_date')

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Messages for %s') % cg.name_with_date()
        context['cg'] = cg
        context['cg_perms'] = cg.get_contact_perms(self.request.user.id)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('messages', _('messages')))
        context['active_submenu'] = 'messages'
        context.update(kwargs)
        return super(MessageListView, self).get_context_data(**context)


class MessageDetailView(NgwUserMixin, DetailView):
    pk_url_kwarg = 'mid'
    model = ContactMsg
    template_name = 'message_detail.html'

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        group_id = self.kwargs.get('gid', None)
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            raise Http404
        contactgroup = get_object_or_404(ContactGroup, pk=group_id)
        if not perms.c_can_view_msgs_cg(request.user.id, group_id):
            raise PermissionDenied
        self.contactgroup = contactgroup
        return super(MessageDetailView, self).dispatch(request, *args, **kwargs)

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
                messages.add_message(self.request, messages.WARNING,
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
        context['cg'] = cg
        context['cg_perms'] = cg.get_contact_perms(self.request.user.id)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('messages', _('messages')))
        context['cig_url'] = self.contactgroup.get_absolute_url() + 'members/' + force_text(self.object.contact_id)
        context['active_submenu'] = 'messages'

        try:
            cig = ContactInGroup.objects.get(
                contact_id=self.object.contact.id,
                group_id=cg.id)
            if cig.flags & CIGFLAG_MEMBER:
                membership = 'member'
                membership_str = _('Member')
            elif cig.flags & CIGFLAG_INVITED:
                membership = 'invited'
                membership_str = _('Invited')
            elif cig.flags & CIGFLAG_DECLINED:
                membership = 'declined'
                membership_str = _('Declined invitation')
            else:
                membership = ''
                membership_str = _('Nil')
        except ContactInGroup.DoesNotExist:
            membership = ''
            membership_str = _('Nil')
        context['membership'] = membership
        context['membership_str'] = membership_str
        context['membership_title'] = _('%(contactname)s in group %(groupname)s') % {
            'contactname': self.object.contact.name,
            'groupname': cg.name_with_date()}
        if perms.c_can_write_msgs_cg(self.request.user.id, self.contactgroup.id):
            email = self.object.contact.get_fieldvalue_by_id(FIELD_EMAIL)
            if email:
                context['reply_url'] = "../members/emails?display=midag&filter=ffilter(%(fieldid)s,eq,'%(email)s')" % {
                    'fieldid': FIELD_EMAIL,
                    'email': email,
                }
        context.update(kwargs)
        return super(MessageDetailView, self).get_context_data(**context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get('unread', None):
            self.object.read_date = None
            self.object.read_by = None
            self.object.save()
            return HttpResponseRedirect(self.contactgroup.get_absolute_url() + 'messages/?&_order=-0')
        raise Http404


#######################################################################
#
# Messages toggle
#
#######################################################################


#from ngw.core.response import JsonHttpResponse
#class MessageToggleReadView(NgwUserMixin, View):
#    @method_decorator(login_required)
#    @method_decorator(require_group(GROUP_USER_NGW))
#    def dispatch(self, request, *args, **kwargs):
#        group_id = self.kwargs.get('gid', None)
#        try:
#            group_id = int(group_id)
#        except (ValueError, TypeError):
#            raise Http404
#        contactgroup = get_object_or_404(ContactGroup, pk=group_id)
#        if not perms.c_can_write_msgs_cg(request.user.id, group_id):
#            raise PermissionDenied
#        self.contactgroup = contactgroup
#        return super(MessageToggleReadView, self).dispatch(request, *args, **kwargs)
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
