# -*- encoding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

from collections import OrderedDict
import json
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.http import HttpResponse, Http404
from ngw.core.models import (
    GROUP_USER_NGW,
    ContactField, ContactGroup, ChoiceGroup)
from ngw.core.contactfield import ContactNameMetaField, AllEventsMetaField
from ngw.core.views.decorators import *



class JsonHttpResponse(HttpResponse):
    '''
    HttpResponse subclass that json encode content, with default content_type
    '''
    def __init__(self, content, content_type='application/json', *args, **kwargs):
        super(JsonHttpResponse, self).__init__(json.dumps(content), content_type, *args, **kwargs)


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_columns(request, column_type):
    if column_type == 'fields':
        fields = ContactField.objects.order_by('sort_weight').extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % request.user.id])
        choices = [{'id': 'name', 'text': force_text(_('Name'))}]
        for field in fields:
            choices.append({'id': force_text(field.id), 'text': field.name})

    elif column_type == 'groups':
        groups = ContactGroup.objects.filter(date=None).extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % request.user.id]).order_by('name')
        choices = []
        for group in groups:
            choices.append({'id': force_text(group.id), 'text': group.name})

    elif column_type == 'events':
        groups = ContactGroup.objects.exclude(date=None).extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % request.user.id]).order_by('-date', 'name')
        choices = []
        choices.append({'id': 'allevents', 'text': force_text(_('All events'))})
        for group in groups:
            choices.append({'id': force_text(group.id), 'text': group.name_with_date()})

    elif column_type == 'custom':
        choices = [{'id': 'user', 'text': request.user.name}]

    else:
        raise Http404

    return JsonHttpResponse({'params' : [choices]})


def get_column(column_type, column_id):
    '''
    returns a 2-tuple:
    - First component has a get_filter event
    - second component is the prefix to build the text version of the filter
    '''
    if column_type == 'fields':
        if column_id == 'name':
            return ContactNameMetaField, 'nfilter('
        else:
            return ContactField.objects.get(pk=column_id), 'ffilter('+column_id

    if column_type == 'groups':
        return ContactGroup.objects.get(pk=column_id), 'gfilter('+column_id

    if column_type == 'events':
        if column_id == 'allevents':
            return AllEventsMetaField, 'allevents('
        else:
            return ContactGroup.objects.get(pk=column_id), 'gfilter('+column_id

    if column_type == 'custom':
        raise NotImplementedError # We might make a MetaField

    raise Http404


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_filters(request, column_type, column_id):
    column, submit_prefix = get_column(column_type, column_id)

    filters = column.get_filters()

    choices = []
    for filter in filters:
        choices.append({'id': filter.internal_name, 'text': force_text(filter.human_name)})
    return JsonHttpResponse({'params' : [choices]})


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_customfilters(request):
    '''
    This is a special version of ajax_get_filters for saved filters
    '''
    filter_list = request.user.get_customfilters()
    choices = []
    for i, filterpair in enumerate(filter_list):
        filtername, filterstr = filterpair
        choices.append({'id': force_text(i), 'text': filtername})
    return JsonHttpResponse({'params' : [choices]})


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_filters_params(request, column_type, column_id, filter_id):
    column, submit_prefix = get_column(column_type, column_id)
    filter = column.get_filter_by_name(filter_id)
    parameter_types = filter.get_param_types()
    jsparams = []
    for param_type in parameter_types:
        if param_type == six.text_type:
            jsparams.append('string')
        elif param_type == int:
            jsparams.append('number')
        elif isinstance(param_type, ChoiceGroup):
            choices = []
            for key, value in param_type.ordered_choices:
                choices.append({'id': key, 'text': value})
            jsparams.append(choices)
        else:
            assert False, "Unsupported filter parameter of type " + force_text(param_type)
    if submit_prefix[-1] != '(':
        submit_prefix += ','
    submit_prefix += filter_id
    return JsonHttpResponse({'submit_prefix': submit_prefix, 'params' : jsparams})


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_customfilters_params(request, filter_id):
    '''
    This is a special version of ajax_get_filters_params for saved filters
    '''
    filter_list = request.user.get_customfilters()
    filter_id = int(filter_id)
    customname, filter = filter_list[filter_id]
    assert filter[-1] == ')', "Custom filter %s should end with a ')'" % customname
    return JsonHttpResponse({'submit_prefix': filter[:-1], 'params' : []})
