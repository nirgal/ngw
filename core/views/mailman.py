# -*- encoding: utf-8 -*-
'''
External mailman managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals

from django.core.exceptions import PermissionDenied
#from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
#from django.utils.encoding import force_text
#from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django import forms
from ngw.core.models import (
    GROUP_USER_NGW,
    ContactGroup)
from ngw.core import perms
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import NgwUserMixin

#######################################################################
#
# Mailman synchronisation
#
#######################################################################

class MailmanSyncForm(forms.Form):
    mail = forms.CharField(widget=forms.Textarea)

@login_required()
@require_group(GROUP_USER_NGW)
def synchronize(request, id):
    id = id and int(id) or None
    initial_value = '''
Les résultats de vos commandes courriels sont fournies ci-dessous.
Ci-joint votre message original.

- Résultats :
    Abonnés en mode non-groupé (normaux) :
        user1@example.com (John DOE)
        user2@example.com

- Fait.
    '''
    from ngw.core.mailman import synchronise_group
    if not perms.c_can_see_members_cg(request.user.id, id):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=id)

    context = {}
    context['title'] = _('Mailman synchronisation')
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('mailman', _('mailman')))
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['active_submenu'] = 'mailman'

    if request.method == 'POST':
        form = MailmanSyncForm(request.POST)
        if form.is_valid():
            data = form.clean()
            context['sync_res'] = synchronise_group(cg, data['mail'])
            return render_to_response('group_mailman_result.html', context, RequestContext(request))
    else:
        form = MailmanSyncForm(initial={'mail': initial_value})

    context['form'] = form
    return render_to_response('group_mailman.html', context, RequestContext(request))
