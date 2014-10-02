# -*- encoding: utf-8 -*-
'''
ChoiceGroup & Choice managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils import html
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.six import iteritems
from django.utils.safestring import mark_safe
from django import forms
from django.views.generic import UpdateView, CreateView
from django.views.generic.edit import ModelFormMixin
from django.contrib import messages
from ngw.core.models import ChoiceGroup
from ngw.core.nav import Navbar
from ngw.core.views.generic import NgwAdminAcl, NgwListView, NgwDeleteView


#######################################################################
#
# Choice groups list
#
#######################################################################


class ChoiceListView(NgwAdminAcl, NgwListView):
    root_queryset = ChoiceGroup.objects.all()
    list_display = 'name', 'htmlchoices'


    def htmlchoices(self, choice_group):
        return mark_safe(', '.join([
            html.escape(c[1])
            for c in choice_group.ordered_choices]))
    htmlchoices.short_description = ugettext_lazy('Choices')


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
        attrs_key['style'] = 'width:7%; margin-left:1ex;'

        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs_value))
            widgets.append(forms.TextInput(attrs=attrs_key))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay

    def decompress(self, value):
        if value:
            return value.split('\u001f')
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
            return '\u001f'.join(data_list)
        return None

    def clean(self, value):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = forms.MultiValueField.clean(self, value).split('\u001f')
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


class ChoiceGroupForm(forms.ModelForm):
    class Meta:
        model = ChoiceGroup
        fields = ['name', 'sort_by_key']

    def __init__(self, *args, **kwargs):
        choicegroup = kwargs.get('instance', None)
        super(ChoiceGroupForm, self).__init__(*args, **kwargs)

        ndisplay = 0
        self.initial['possible_values'] = []

        if choicegroup:
            choices = choicegroup.ordered_choices
            for c in choices:
                self.initial['possible_values'].append(c[1])
                self.initial['possible_values'].append(c[0])
                ndisplay += 1

        for i in range(3): # add 3 blank lines to add data
            self.initial['possible_values'].append('')
            self.initial['possible_values'].append('')
            ndisplay += 1
        self.fields['possible_values'] = ChoicesField(
            label=_('Possible values'),
            required=False,
            widget=ChoicesWidget(ndisplay=ndisplay),
            ndisplay=ndisplay)

    def save(self):
        choicegroup = super(ChoiceGroupForm, self).save()

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

        for c in choicegroup.choices.all():
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
            choicegroup.choices.create(key=k, value=v)

        return choicegroup


class ChoiceEditMixin(ModelFormMixin):
    template_name = 'edit.html'
    form_class = ChoiceGroupForm
    model = ChoiceGroup
    pk_url_kwarg = 'id'

    def form_valid(self, form):
        request = self.request
        choicegroup = form.save()
        messages.add_message(request, messages.SUCCESS, _('Choice %s has been saved sucessfully.') % choicegroup.name)
        choicegroup = self.object
        if request.POST.get('_continue', None):
            return HttpResponseRedirect(choicegroup.get_absolute_url()+'edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect(choicegroup.get_class_absolute_url()+'add')
        else:
            return HttpResponseRedirect(reverse('choice_list'))

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing %s') % self.object
            id = self.object.id
        else:
            title = _('Adding a new %s') % ChoiceGroup.get_class_verbose_name()
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = ChoiceGroup
        context['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())
        if id:
            context['nav'].add_component(self.object.get_navcomponent()) \
                          .add_component(('edit', _('edit')))
        else:
            context['nav'].add_component(('add', _('add')))

        context.update(kwargs)
        return super(ChoiceEditMixin, self).get_context_data(**context)


class ChoiceEditView(NgwAdminAcl, ChoiceEditMixin, UpdateView):
    pass


class ChoiceCreateView(NgwAdminAcl, ChoiceEditMixin, CreateView):
    pass


#######################################################################
#
# Choice groups delete
#
#######################################################################


class ChoiceGroupDeleteView(NgwAdminAcl, NgwDeleteView):
    model = ChoiceGroup
    pk_url_kwarg = 'id'
