'''
ChoiceGroup & Choice managing views
'''

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.views.generic import UpdateView
from django.views.generic.edit import ModelFormMixin

from ngw.core import perms
from ngw.core.models import ChoiceGroup, ContactField
from ngw.core.views.generic import InGroupAcl

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
        super().__init__(widgets, attrs)
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
        super().__init__(fields, *args, **kwargs)
        self.ndisplay = ndisplay

    def compress(self, data_list):
        if data_list:
            return '\u001f'.join(data_list)
        return None

    def clean(self, value):
        keys = []
        raw_values = forms.MultiValueField.clean(self, value)
        if raw_values:
            possibles_values = raw_values.split('\u001f')
        else:
            possibles_values = []
        # print('possibles_values=', repr(possibles_values))
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        for i in range(len(possibles_values)//2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue  # ignore lines without values
            if not k:
                continue  # empty keys are ok
            if k in keys:
                raise forms.ValidationError(_(
                    'You cannot have two keys with the same value. Leave empty'
                    ' for automatic generation.'))
            keys.append(k)
        return possibles_values


class ChoiceGroupForm(forms.ModelForm):
    class Meta:
        model = ChoiceGroup
        fields = ['sort_by_key']

    def __init__(self, *args, **kwargs):
        choicegroup = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)

        ndisplay = 0
        self.initial['possible_values'] = []

        if choicegroup:
            choices = choicegroup.ordered_choices
            for c in choices:
                self.initial['possible_values'].append(c[1])
                self.initial['possible_values'].append(c[0])
                ndisplay += 1

        for i in range(3):  # add 3 blank lines to add data
            self.initial['possible_values'].append('')
            self.initial['possible_values'].append('')
            ndisplay += 1
        self.fields['possible_values'] = ChoicesField(
            label=_('Possible values'),
            required=False,
            widget=ChoicesWidget(ndisplay=ndisplay),
            ndisplay=ndisplay)

    def save(self):
        choicegroup = super().save()

        possibles_values = self.cleaned_data['possible_values']
        choices = {}

        # first ignore lines with empty keys, and update auto_key
        auto_key = 0
        for i in range(len(possibles_values)//2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue  # ignore lines whose value is empty
            if k:  # key is not left empty for automatic generation
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
                continue  # ignore lines whose value is empty
            if not k:  # key is left empty for automatic generation
                k = str(auto_key)
                auto_key += 1
                choices[k] = v

        # print('choices=', choices)

        for c in choicegroup.choices.all():
            k = c.key
            if k in choices.keys():
                # print('UPDATING', k)
                c.value = choices[k]
                c.save()
                del choices[k]
            else:  # that key has be deleted
                # print('DELETING', k)
                c.delete()
        for k, v in choices.items():
            # print('ADDING', k)
            choicegroup.choices.create(key=k, value=v)

        return choicegroup


class ChoiceEditMixin(ModelFormMixin):
    template_name = 'choice_edit.html'
    form_class = ChoiceGroupForm
    model = ChoiceGroup
    # pk_url_kwarg = 'id'

    def get_object(self):
        fid = self.kwargs.get('id')
        field = ContactField.objects.get(pk=fid)
        if field.contact_group_id != self.contactgroup.id:
            raise PermissionDenied
        self.field = field
        return field.choice_group

    def form_valid(self, form):
        request = self.request
        # choicegroup = form.save()
        form.save()

        # TODO show field name
        messages.add_message(request, messages.SUCCESS,
                             _('Choices have been saved successfully.'))

        return HttpResponseRedirect('..')

    def get_context_data(self, **kwargs):
        context = {}
        cg = self.contactgroup
        if self.object:
            title = _('Editing choices for {}').format(self.field)
            id = self.object.id
        else:
            title = _('Adding a new {}').format(
                ChoiceGroup.get_class_verbose_name())
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = ChoiceGroup
        context['nav'] = cg.get_smart_navbar()
        context['nav'].add_component(('fields', _('contact fields')))
        if id:
            context['nav'].add_component(self.object.get_navcomponent())
            context['nav'].add_component(('choices', _('choices')))
        else:
            context['nav'].add_component(('add', _('add')))  # obsolete
        context['active_submenu'] = 'fields'

        context.update(kwargs)
        return super().get_context_data(**context)


class ChoiceEditView(InGroupAcl, ChoiceEditMixin, UpdateView):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied


class Choice2EditView(ChoiceEditView):
    def get_object(self):
        fid = self.kwargs.get('id')
        field = ContactField.objects.get(pk=fid)
        if field.contact_group_id != self.contactgroup.id:
            raise PermissionDenied
        self.field = field
        return field.choice_group2
