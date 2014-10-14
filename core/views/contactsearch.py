# -*- encoding: utf-8 -*-
'''
ajax views for building contact filter
'''

from __future__ import division, print_function, unicode_literals

from django.utils import six
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.http import Http404
from django.views.generic import View
from ngw.core.models import (
    ContactField, ContactGroup, ChoiceGroup)
from ngw.core import perms
from ngw.core.contactfield import ContactNameMetaField, AllEventsMetaField
from ngw.core.response import JsonHttpResponse
from ngw.core.views.generic import NgwUserAcl


class ContactSearchColumnsView(NgwUserAcl, View):
    def get(self, request, *args, **kwargs):
        column_type = self.kwargs['column_type']
        if column_type == 'fields':
            fields = ContactField.objects.with_user_perms(request.user.id)
            choices = [{'id': 'name', 'text': force_text(_('Name'))}]
            for field in fields:
                choices.append({'id': force_text(field.id), 'text': field.name})

        elif column_type == 'groups':
            groups = ContactGroup.objects.filter(date=None)
            groups = groups.with_user_perms(
                request.user.id,
                wanted_flags=perms.SEE_MEMBERS)
            #groups = groups.order_by('name')
            choices = []
            for group in groups:
                choices.append({'id': force_text(group.id), 'text': group.name})

        elif column_type == 'events':
            groups = ContactGroup.objects.exclude(date=None)
            groups = groups.with_user_perms(
                request.user.id,
                wanted_flags=perms.SEE_MEMBERS)
            #groups = groups.order_by('-date', 'name')
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


class ContactSearchColumnFiltersView(NgwUserAcl, View):
    def get(self, request, *args, **kwargs):
        column_type = self.kwargs['column_type']
        column_id = self.kwargs['column_id']
        column, submit_prefix = get_column(column_type, column_id)

        filters = column.get_filters()

        choices = []
        for filter in filters:
            choices.append({'id': filter.internal_name, 'text': force_text(filter.human_name)})
        return JsonHttpResponse({'params' : [choices]})


class ContactSearchCustomFiltersView(NgwUserAcl, View):
    '''
    This is a special version of ajax_get_filters for saved filters
    '''
    def get(self, request, *args, **kwargs):
        filter_list = request.user.get_customfilters()
        choices = []
        for i, filterpair in enumerate(filter_list):
            filtername, filterstr = filterpair
            choices.append({'id': force_text(i), 'text': filtername})
        return JsonHttpResponse({'params' : [choices]})


class ContactSearchFilterParamsView(NgwUserAcl, View):
    def get(self, request, *args, **kwargs):
        column_type = self.kwargs['column_type']
        column_id = self.kwargs['column_id']
        filter_id = self.kwargs['filter_id']

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


class ContactSearchCustomFilterParamsView(NgwUserAcl, View):
    '''
    This is a special version of ajax_get_filters_params for saved filters
    '''
    def get(self, request, *args, **kwargs):
        filter_id = self.kwargs['filter_id']
        filter_list = request.user.get_customfilters()
        filter_id = int(filter_id)
        customname, filter = filter_list[filter_id]
        assert filter[-1] == ')', "Custom filter %s should end with a ')'" % customname
        return JsonHttpResponse({'submit_prefix': filter[:-1], 'params' : []})
