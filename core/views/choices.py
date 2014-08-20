# -*- encoding: utf-8 -*-
'''
ChoiceGroup & Choice managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils import html
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils.six import iteritems
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django import forms
from django.contrib import messages
from ngw.core.models import GROUP_USER_NGW, ChoiceGroup
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import generic_delete, NgwListView


#######################################################################
#
# Choice groups list
#
#######################################################################


class ChoiceListView(NgwListView):
    root_queryset = ChoiceGroup.objects.all()
    cols = [
        (_('Name'), None, 'name', 'name'),
        (_('Choices'), None, lambda cg: ', '.join([html.escape(c[1]) for c in cg.ordered_choices]), None),
    ]

    @method_decorator(login_required)
    @method_decorator(require_group(GROUP_USER_NGW))
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_admin():
            raise PermissionDenied
        return super(ChoiceListView, self).dispatch(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Select a choice group')
        context['objtype'] = ChoiceGroup
        context['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())

        context.update(kwargs)
        return super(ChoiceListView, self).get_context_data(**context)


#######################################################################
#
# Choice groups edit / add
#
#######################################################################


class ChoicesWidget(forms.MultiWidget):
    def __init__(self, ndisplay, attrs=None):
        widgets = []
        attrs_value = attrs or {}
        attrs_key = attrs or {}
        attrs_value['style'] = 'width:90%'
        attrs_key['style'] = 'width:9%; margin-left:1ex;'

        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs_value))
            widgets.append(forms.TextInput(attrs=attrs_key))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay
    def decompress(self, value):
        if value:
            return value.split(',')
        nonelist = []
        for i in range(self.ndisplay):
            nonelist.append(None)
        return nonelist


class ChoicesField(forms.MultiValueField):
    def __init__(self, ndisplay, *args, **kwargs):
        fields = []
        for i in range(ndisplay):
            fields.append(forms.CharField())
            fields.append(forms.CharField())
        super(ChoicesField, self).__init__(fields, *args, **kwargs)
        self.ndisplay = ndisplay
    def compress(self, data_list):
        if data_list:
            return ','.join(data_list)
        return None
    def clean(self, value):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = forms.MultiValueField.clean(self, value).split(',')
        #print('possibles_values=', repr(possibles_values))
        keys = []
        for i in range(len(possibles_values)//2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines without values
            if not k:
                continue # empty keys are ok
            if k in keys:
                raise forms.ValidationError(_('You cannot have two keys with the same value. Leave empty for automatic generation.'))
            keys.append(k)
        return possibles_values



class ChoiceGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    sort_by_key = forms.BooleanField(required=False)

    def __init__(self, cg=None, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)

        ndisplay = 0
        self.initial['possible_values'] = []

        if cg:
            self.initial['name'] = cg.name
            self.initial['sort_by_key'] = cg.sort_by_key
            choices = cg.ordered_choices
            for c in choices:
                self.initial['possible_values'].append(c[1])
                self.initial['possible_values'].append(c[0])
                ndisplay += 1

        for i in range(3): # add 3 blank lines to add data
            self.initial['possible_values'].append('')
            self.initial['possible_values'].append('')
            ndisplay += 1
        self.fields['possible_values'] = ChoicesField(required=False, widget=ChoicesWidget(ndisplay=ndisplay), ndisplay=ndisplay)


    def save(self, cg, request):
        if cg:
            oldid = cg.id
        else:
            cg = ChoiceGroup()
            oldid = None
        cg.name = self.clean()['name']
        cg.sort_by_key = self.clean()['sort_by_key']
        cg.save()

        possibles_values = self.cleaned_data['possible_values']
        choices = {}

        # first ignore lines with empty keys, and update auto_key
        auto_key = 0
        for i in range(len(possibles_values)//2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines whose value is empty
            if k: # key is not left empty for automatic generation
                if k.isdigit():
                    intk = int(k)
                    if intk > auto_key:
                        auto_key = intk
                choices[k] = v

        auto_key += 1

        # now generate key for empty ones
        for i in range(len(possibles_values)//2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines whose value is empty
            if not k: # key is left empty for automatic generation
                k = str(auto_key)
                auto_key += 1
                choices[k] = v

        #print('choices=', choices)

        for c in cg.choices.all():
            k = c.key
            if k in choices.keys():
                #print('UPDATING', k)
                c.value = choices[k]
                c.save()
                del choices[k]
            else: # that key has be deleted
                #print('DELETING', k)
                c.delete()
        for k, v in iteritems(choices):
            #print('ADDING', k)
            cg.choices.create(key=k, value=v)

        messages.add_message(request, messages.SUCCESS, _('Choice %s has been saved sucessfully.') % cg.name)
        return cg


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_edit(request, id=None):
    if not request.user.is_admin():
        raise PermissionDenied
    objtype = ChoiceGroup
    id = id and int(id) or None
    if id:
        cg = get_object_or_404(ChoiceGroup, pk=id)
        title = _('Editing %s') % force_text(cg)
    else:
        cg = None
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, request.POST)
        if form.is_valid():
            cg = form.save(cg, request)
            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cg.get_absolute_url()+'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cg.get_class_absolute_url()+'add')
            else:
                return HttpResponseRedirect(reverse('choice_list'))
    else:
        form = ChoiceGroupForm(cg)

    context = {}
    context['title'] = title
    context['id'] = id
    context['objtype'] = objtype
    context['form'] = form
    if id:
        context['o'] = cg
    context['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())
    if id:
        context['nav'].add_component(cg.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))
    return render_to_response('edit.html', context, RequestContext(request))


#######################################################################
#
# Choice groups delete
#
#######################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_delete(request, id):
    if not request.user.is_admin():
        raise PermissionDenied
    id = id and int(id) or None
    o = get_object_or_404(ChoiceGroup, pk=id)
    return generic_delete(request, o, reverse('choice_list'))
