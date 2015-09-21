'''
ajax views for building contact filter
'''

import decoratedstr
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django.views.generic import View

from ngw.core import perms
from ngw.core.contactfield import AllEventsMetaField, ContactNameMetaField
from ngw.core.models import (FIELD_FILTERS, ChoiceGroup, Contact, ContactField,
                             ContactGroup)
from ngw.core.views.generic import NgwUserAcl


class ContactSearchAutocompleteView(NgwUserAcl, View):
    def get(self, request, *args, **kwargs):
        term = request.GET['term']
        choices = []
        contacts = Contact.objects.filter(
            name__iregex=decoratedstr.decorated_match(term))
        contacts = contacts.extra(
            tables=['v_c_can_see_c'],
            where=[
                'v_c_can_see_c.contact_id_1={}'.format(request.user.id),
                'v_c_can_see_c.contact_id_2=contact.id'])

        for contact in contacts:
            choices.append({'label': contact.name, 'value': contact.id})
        return JsonResponse(choices, safe=False)


class ContactSearchColumnsView(NgwUserAcl, View):
    def get(self, request, *args, **kwargs):
        column_type = self.kwargs['column_type']
        if column_type == 'fields':
            fields = ContactField.objects.with_user_perms(request.user.id)
            choices = [{'id': 'name', 'text': _('Name')}]
            for field in fields:
                choices.append({'id': str(field.id), 'text': field.name})

        elif column_type == 'groups':
            groups = ContactGroup.objects.filter(date=None)
            groups = groups.with_user_perms(
                request.user.id,
                wanted_flags=perms.SEE_MEMBERS)
            # groups = groups.order_by('name')
            choices = []
            for group in groups:
                choices.append({'id': str(group.id), 'text': group.name})

        elif column_type == 'events':
            groups = ContactGroup.objects.exclude(date=None)
            groups = groups.with_user_perms(
                request.user.id,
                wanted_flags=perms.SEE_MEMBERS)
            # groups = groups.order_by('-date', 'name')
            choices = []
            choices.append({'id': 'allevents', 'text': str(_('All events'))})
            for group in groups:
                choices.append({'id': str(group.id), 'text': str(group)})

        elif column_type == 'saved':
            choices = [{'id': str(request.user.id), 'text': request.user.name}]
            contacts = Contact.objects.extra(
                tables=['contact_field_value', ],
                where=[
                    'contact_field_value.contact_id = contact.id',
                    'contact_field_value.contact_field_id = {fid}'.format(
                        fid=FIELD_FILTERS),
                    "value LIKE %s",
                    ],
                params=['%"shared": true%'],
            )
            for contact in contacts:
                if contact.id != request.user.id:
                    choices += [{'id': str(contact.id), 'text': contact.name}]

        else:
            raise Http404

        return JsonResponse({'params': [choices]})


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

    if column_type == 'saved':
        raise NotImplementedError  # We might make a MetaField

    raise Http404


class ContactSearchColumnFiltersView(NgwUserAcl, View):
    def get(self, request, *args, **kwargs):
        column_type = self.kwargs['column_type']
        column_id = self.kwargs['column_id']
        column, submit_prefix = get_column(column_type, column_id)

        filters = column.get_filters()

        choices = []
        for filter in filters:
            choices.append({'id': filter.internal_name,
                            'text': str(filter.human_name)})
        return JsonResponse({'params': [choices]})


class ContactSearchSavedFiltersView(NgwUserAcl, View):
    '''
    This is a special version of ajax_get_filters for saved filters
    (common version)
    '''
    def get(self, request, cid, *args, **kwargs):
        if cid == 'user':
            filter_list = request.user.get_saved_filters()
        else:
            cid = int(cid)
            contact = get_object_or_404(Contact, pk=cid)
            filter_list = contact.get_saved_filters()
        choices = []
        for i, info in enumerate(filter_list):
            choices.append({'id': str(i), 'text': info['name']})
        return JsonResponse({'params': [choices]})


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
            if param_type == str:
                jsparams.append('string')
            elif param_type == int:
                jsparams.append('number')
            elif isinstance(param_type, ChoiceGroup):
                choices = []
                if len(parameter_types) > 1:
                    # Allow empty if double choice
                    choices = [{'id': '', 'text': _('Any')}]
                for key, value in param_type.ordered_choices:
                    choices.append({'id': key, 'text': value})
                jsparams.append(choices)
            else:
                assert False, \
                    ("Unsupported filter parameter of type "
                     + str(param_type))
        if submit_prefix[-1] != '(':
            submit_prefix += ','
        submit_prefix += filter_id
        return JsonResponse({'submit_prefix': submit_prefix,
                             'params': jsparams})


class ContactSearchSavedFilterParamsView(NgwUserAcl, View):
    '''
    This is a special version of ajax_get_filters_params for saved filters
    '''
    def get(self, request, cid, *args, **kwargs):
        filter_id = self.kwargs['filter_id']
        cid = int(cid)
        contact = get_object_or_404(Contact, pk=cid)
        filter_list = contact.get_saved_filters()
        filter_id = int(filter_id)
        info = filter_list[filter_id]
        filter_string = info['filter_string']
        assert filter_string[-1] == ')', \
            "Custom filter {} should end with a ')'".format(info['name'])
        return JsonResponse({'submit_prefix': filter_string[:-1],
                             'params': []})
