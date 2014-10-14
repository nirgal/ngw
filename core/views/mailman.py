# -*- encoding: utf-8 -*-
'''
External mailman managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _
from django.views.generic import FormView
from django import forms
from ngw.core import perms
from ngw.core.mailman import synchronise_group
from ngw.core.views.generic import InGroupAcl

#######################################################################
#
# External mailman synchronisation
#
#######################################################################

class MailmanSyncForm(forms.Form):
    '''
    Simple form with a textarea
    '''
    mail = forms.CharField(widget=forms.Textarea)


class MailmanSyncView(InGroupAcl, FormView):
    '''
    View to synchronize a group with an external mailman address
    '''
    form_class = MailmanSyncForm
    initial = {'mail': '''
Les résultats de vos commandes courriels sont fournies ci-dessous.
Ci-joint votre message original.

- Résultats :
    Abonnés en mode non-groupé (normaux) :
        user1@example.com (John DOE)
        user2@example.com

- Fait.
    '''}
    template_name = 'group_mailman.html'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.SEE_MEMBERS:
            raise PermissionDenied

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
        context['active_submenu'] = 'mailman'
        context.update(kwargs)
        return super(MailmanSyncView, self).get_context_data(**context)
