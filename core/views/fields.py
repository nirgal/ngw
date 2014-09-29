# -*- encoding: utf-8 -*-
'''
ContactField managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.encoding import force_text
from django.utils import six
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django import forms
from django.core.urlresolvers import reverse
from django.views.generic import View, UpdateView, CreateView
from django.views.generic.edit import ModelFormMixin
from django.contrib import messages
from ngw.core.models import ContactField, ContactGroup, ChoiceGroup
from ngw.core.nav import Navbar
from ngw.core.views.generic import NgwAdminAcl, NgwListView, NgwDeleteView

###############################################################################
#
# List of fields
#
###############################################################################


class FieldListView(NgwAdminAcl, NgwListView):
    cols = [
        (ugettext_lazy('Name'), None, 'name', 'name'),
        (ugettext_lazy('Type'), None, 'type_as_html', 'type'),
        (ugettext_lazy('Only for'), None, 'contact_group', 'contact_group__name'),
        (ugettext_lazy('System locked'), None, 'system', 'system'),
        #(ugettext_lazy('Move'), None, lambda cf: '<a href='+str(cf.id)+'/moveup>Up</a> <a href='+str(cf.id)+'/movedown>Down</a>', None),
    ]
    default_sort = 'sort_weight'

    def get_root_queryset(self):
        return ContactField.objects.extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % self.request.user.id])

    def get_context_data(self, **kwargs):
        context = {}
        context['title'] = _('Select an optionnal field')
        context['objtype'] = ContactField
        context['nav'] = Navbar(ContactField.get_class_navcomponent())
        context.update(kwargs)
        return super(FieldListView, self).get_context_data(**context)


###############################################################################
#
# Fields re-ordering
#
###############################################################################


class FieldMoveUpView(NgwAdminAcl, View):
    def get(self, request, *args, **kwargs):
        id = self.kwargs['id']
        id = id and int(id) or None
        cf = get_object_or_404(ContactField, pk=id)
        cf.sort_weight -= 15
        cf.save()
        ContactField.renumber()
        return HttpResponseRedirect(reverse('field_list'))


class FieldMoveDownView(NgwAdminAcl, View):
    def get(self, request, *args, **kwargs):
        id = self.kwargs['id']
        id = id and int(id) or None
        cf = get_object_or_404(ContactField, pk=id)
        cf.sort_weight += 15
        cf.save()
        ContactField.renumber()
        return HttpResponseRedirect(reverse('field_list'))


###############################################################################
#
# Field edit
#
###############################################################################


class FieldEditForm(forms.ModelForm):
    class Meta:
        model = ContactField
        fields = ['name', 'hint', 'contact_group', 'type', 'choice_group',
            'default']
        widgets = {
            'type': forms.Select,
            'default': forms.widgets.Input,
        }

    class IncompatibleData(Exception if six.PY3 else StandardError):
        def __init__(self, deletion_details, *args, **kwargs):
            super(FieldEditForm.IncompatibleData, self).__init__(*args, **kwargs)
            self.deletion_details = deletion_details

    move_after = forms.IntegerField(label=ugettext_lazy('Move after'), widget=forms.Select)

    def __init__(self, *args, **kargs):
        instance = kargs.get('instance', None)
        initial = kargs.get('initial', {})
        if instance:
            initial['move_after'] = instance.sort_weight-10
        kargs['initial'] = initial
        super(FieldEditForm, self).__init__(*args, **kargs)

        self.delete_incompatible = bool(self.data.get('confirm', None))

        contacttypes = ContactGroup.objects.filter(field_group=True)
        self.fields['contact_group'].widget.choices = [(g.id, g.name) for g in contacttypes]

        self.fields['type'].widget.choices = [(cls.db_type_id, cls.human_type_id)
            for cls in six.itervalues(ContactField.types_classes)] # TODO: Sort
        js_test_type_has_choice = ' || '.join(["this.value=='" + cls.db_type_id + "'"
            for cls in ContactField.types_classes.values()
            if cls.has_choice])
        self.fields['type'].widget.attrs = {'onchange':
            mark_safe('if (0 || '+js_test_type_has_choice+") { document.forms['objchange']['choice_group'].disabled = 0; } else { document.forms['objchange']['choice_group'].value = ''; document.forms['objchange']['choice_group'].disabled = 1; }")}

        self.fields['choice_group'].widget.choices = [('', '---')] + [(c.id, c.name) for c in ChoiceGroup.objects.order_by('name')]

        t = self.data.get('type', '') or self.initial.get('type', '')
        if t:
            cls_contact_field = ContactField.get_contact_field_type_by_dbid(t)
        else:
            cls_contact_field = ContactField.get_contact_field_type_by_dbid('TEXT')
        if cls_contact_field.has_choice:
            if 'disabled' in self.fields['choice_group'].widget.attrs:
                del self.fields['choice_group'].widget.attrs['disabled']
            self.fields['choice_group'].required = True
        else:
            self.fields['choice_group'].widget.attrs['disabled'] = 1
            self.fields['choice_group'].required = False

        self.fields['default'].widget.attrs['disabled'] = 1

        self.fields['move_after'].widget.choices = [(0, _('Name'))] + [(field.sort_weight, field.name) for field in ContactField.objects.order_by('sort_weight')]

        if instance and instance.system:
            self.fields['contact_group'].widget.attrs['disabled'] = 1
            self.fields['type'].widget.attrs['disabled'] = 1
            self.fields['type'].required = False
            self.fields['choice_group'].widget.attrs['disabled'] = 1

    def clean(self):
        if self.instance.system:
            # If this is a system locked field, some attributes may not be
            # changed:
            self.cleaned_data['contact_group'] = self.instance.contact_group
            self.cleaned_data['type'] = self.instance.type
            self.cleaned_data['choice_group'] = self.instance.choice_group

        new_cls_id = self.cleaned_data['type']
        choice_group_id = self.cleaned_data.get('choice_group', None)
        new_cls = ContactField.get_contact_field_type_by_dbid(new_cls_id)

        if new_cls.has_choice and not choice_group_id:
            raise forms.ValidationError(_('You must select a choice group for that type.'))

        if not self.delete_incompatible:
            deletion_details = []
            for cfv in self.instance.values.all():
                if not new_cls.validate_unicode_value(cfv.value, choice_group_id):
                    deletion_details.append((cfv.contact, force_text(cfv)))
            if deletion_details:
                raise FieldEditForm.IncompatibleData(deletion_details)

        return self.cleaned_data

    def save(self):
        if self.instance.pk:
            # we are changing an existing field
            deletion_details = []
            new_cls_id = self.cleaned_data['type']
            choice_group_id = self.cleaned_data.get('choice_group', None)

            if self.delete_incompatible:
                new_cls = ContactField.get_contact_field_type_by_dbid(new_cls_id)
                for cfv in self.instance.values.all():
                    if not new_cls.validate_unicode_value(cfv.value, choice_group_id):
                        cfv.delete()
            else:  # delete_incompatible==False
                new_cls = ContactField.get_contact_field_type_by_dbid(new_cls_id)
                for cfv in self.instance.values.all():
                    if not new_cls.validate_unicode_value(cfv.value, choice_group_id):
                        deletion_details.append((cfv.contact, cfv))
                if deletion_details:
                    raise FieldEditForm.IncompatibleData(deletion_details)

        result = super(FieldEditForm, self).save(commit=False)
        self.instance.sort_weight = self.cleaned_data['move_after'] + 5
        self.instance.save()
        ContactField.renumber()
        return result


class FieldEditMixin(ModelFormMixin):
    template_name = 'edit.html'
    form_class = FieldEditForm
    model = ContactField
    pk_url_kwarg = 'id'

    def form_valid(self, form):
        request = self.request
        cf = form.save()

        messages.add_message(request, messages.SUCCESS, _('Field %s has been saved sucessfully.') % cf.name)

        if request.POST.get('_continue', None):
            return HttpResponseRedirect('edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect('add')
        else:
            return HttpResponseRedirect('..')

    def get_context_data(self, **kwargs):
        context = {}
        if self.object:
            title = _('Editing %s') % self.object
            id = self.object.id
        else:
            title = _('Adding a new %s') % ContactField.get_class_verbose_name()
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = ChoiceGroup
        context['nav'] = Navbar(ContactField.get_class_navcomponent())
        if id:
            context['nav'].add_component(self.object.get_navcomponent()) \
                          .add_component(('edit', _('edit')))
        else:
            context['nav'].add_component(('add', _('add')))

        context.update(kwargs)
        return super(FieldEditMixin, self).get_context_data(**context)


class FieldEditView(NgwAdminAcl, FieldEditMixin, UpdateView):
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        try:
            if form.is_valid():
                return self.form_valid(form)
            else:
                return self.form_invalid(form)
        except FieldEditForm.IncompatibleData as err:
            cf = form.instance
            context = {}
            context['title'] = _('Type incompatible with existing data')
            context['id'] = cf.id
            context['cf'] = cf
            context['deletion_details'] = err.deletion_details
            for k in ('name', 'hint', 'contact_group', 'type', 'move_after'):
                context[k] = form.cleaned_data[k]
            context['contact_group'] = form.cleaned_data['contact_group'].id
            if form.cleaned_data['choice_group']:
                context['choice_group'] = form.cleaned_data['choice_group'].id
            context['nav'] = Navbar(cf.get_class_navcomponent(), cf.get_navcomponent(), ('edit', _('delete incompatible data')))
            return render_to_response('type_change.html', context, RequestContext(request))


class FieldCreateView(NgwAdminAcl, FieldEditMixin, CreateView):
    pass


###############################################################################
#
# Field delete
#
###############################################################################


class FieldDeleteView(NgwAdminAcl, NgwDeleteView):
    model = ContactField
    pk_url_kwarg = 'id'

    def get_object(self, *args, **kwargs):
        field = super(FieldDeleteView, self).get_object(*args, **kwargs)
        if field.system:
            messages.add_message(
                self.request, messages.ERROR,
                _('Field %s is locked and CANNOT be deleted.') % field.name)
            raise PermissionDenied
        return field
