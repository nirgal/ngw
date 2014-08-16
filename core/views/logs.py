# -*- encoding: utf-8 -*-
'''
Log managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from ngw.core.models import GROUP_USER_NGW, Log
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import render_query


@login_required()
@require_group(GROUP_USER_NGW)
def log_list(request):
    if not request.user.is_admin():
        raise PermissionDenied

    context = {}
    context['title'] = _('Global log')
    context['nav'] = Navbar(Log.get_class_navcomponent())
    context['objtype'] = Log
    context['query'] = Log.objects.all()
    context['cols'] = [
        (_('Date UTC'), None, 'small_date', 'dt'),
        (_('User'), None, 'contact', 'contact__name'),
        (_('Action'), None, 'action_txt', 'action'),
        (_('Target'), None, 'target_repr', 'target_repr'),
        (_('Property'), None, 'property_repr', 'property_repr'),
        (_('Change'), None, 'change', 'change'),
    ]
    return render_query('log_list.html', context, request)
