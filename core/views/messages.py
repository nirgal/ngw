# -*- encoding: utf-8 -*-
'''
Messages managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.utils.translation import ugettext_lazy as _
#from django.utils.encoding import force_text
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.views.generic import View, DetailView
from django.views.generic.base import ContextMixin
from django.contrib import messages
from ngw.core.models import (
    GROUP_USER_NGW,
    Config, ContactMsg, ContactGroup)
from ngw.core import perms
from ngw.core.response import JsonHttpResponse
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import NgwUserMixin, NgwListView


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
        if self.object.is_answer:
            if perms.c_can_write_msgs_cg(self.request.user.id, self.contactgroup.id):
                self.object.read_date = now()
                self.object.read_by = self.request.user
                self.object.save()
            else:
                messages.add_message(request, messages.WARNING,
                    _("You don't have the permission to flag that message as read."))
        cg = self.contactgroup
        context = {}
        context['title'] = _('Message in %s') % cg.name_with_date() #TODO
        context['cg'] = cg
        context['cg_perms'] = cg.get_contact_perms(self.request.user.id)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('messages', _('messages')))
        context['active_submenu'] = 'messages'
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
