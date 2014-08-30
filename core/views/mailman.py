# -*- encoding: utf-8 -*-
'''
External mailman managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.views.generic import FormView
from django import forms
from ngw.core.models import (
    GROUP_USER_NGW,
    ContactGroup)
from ngw.core import perms
from ngw.core.mailman import synchronise_group
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import NgwUserMixin

#######################################################################
#
# External mailman synchronisation
#
#######################################################################

class MailmanSyncForm(forms.Form):
    mail = forms.CharField(widget=forms.Textarea)


class MailmanSyncView(FormView):
    form_class = MailmanSyncForm
    initial = { 'mail': '''
Les résultats de vos commandes courriels sont fournies ci-dessous.
Ci-joint votre message original.

- Résultats :
    Abonnés en mode non-groupé (normaux) :
        user1@example.com (John DOE)
        user2@example.com

- Fait.
    '''}
    template_name = 'group_mailman.html'

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        user_id = request.user.id
        group_id = self.kwargs['gid']
        self.contactgroup = get_object_or_404(ContactGroup, pk=group_id)
        if not perms.c_can_see_members_cg(user_id, self.contactgroup.id):
            raise PermissionDenied
        return super(MailmanSyncView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        res = synchronise_group(self.contactgroup, form.cleaned_data['mail'])
        self.template_name = 'group_mailman_result.html'
        return self.render_to_response(
            self.get_context_data(sync_res=res))

    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Mailman synchronisation')
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('mailman', _('mailman')))
        context['cg'] = cg
        context['cg_perms'] = cg.get_contact_perms(self.request.user.id)
        context['active_submenu'] = 'mailman'
        context.update(kwargs)
        return super(MailmanSyncView, self).get_context_data(**context)
