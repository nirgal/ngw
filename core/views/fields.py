# -*- encoding: utf-8 -*-
'''
ContactField managing views
'''

from __future__ import division, absolute_import, print_function, unicode_literals
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text, smart_text
from django.utils.six import itervalues
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django import forms
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.contrib import messages
from ngw.core.models import GROUP_USER_NGW, ContactField, ContactGroup, ChoiceGroup
from ngw.core.nav import Navbar
from ngw.core.views.decorators import login_required, require_group
from ngw.core.views.generic import generic_delete, NgwAdminAcl, NgwListView

###############################################################################
#
# List of fields
#
###############################################################################


class FieldListView(NgwAdminAcl, NgwListView):
    cols = [
        (_('Name'), None, 'name', 'name'),
        (_('Type'), None, 'type_as_html', 'type'),
        (_('Only for'), None, 'contact_group', 'contact_group__name'),
        (_('System locked'), None, 'system', 'system'),
        #(_('Move'), None, lambda cf: '<a href='+str(cf.id)+'/moveup>Up</a> <a href='+str(cf.id)+'/movedown>Down</a>', None),
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
    move_after = forms.IntegerField(label=_('Move after'), widget=forms.Select)

    def __init__(self, *args, **kargs):
        instance = kargs.get('instance', None)
        initial = kargs.get('initial', {})
        if instance:
            initial['move_after'] = instance.sort_weight-10
        kargs['initial'] = initial
        super(FieldEditForm, self).__init__(*args, **kargs)

        contacttypes = ContactGroup.objects.filter(field_group=True)
        self.fields['contact_group'].widget.choices = [(g.id, g.name) for g in contacttypes]

        self.fields['type'].widget.choices = [(cls.db_type_id, cls.human_type_id)
            for cls in itervalues(ContactField.types_classes)] # TODO: Sort
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
        t = self.cleaned_data.get('type', None)
        if t:
            # system fields have type disabled, this is ok
            cls_contact_field = ContactField.get_contact_field_type_by_dbid(t)
            if cls_contact_field.has_choice and not self.cleaned_data.get('choice_group'):
                raise forms.ValidationError(_('You must select a choice group for that type.'))
        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def field_edit(request, id):
    if not request.user.is_admin():
        raise PermissionDenied
    id = id and int(id) or None
    objtype = ContactField
    if id:
        cf = get_object_or_404(ContactField, pk=id)
        title = _('Editing %s') % smart_text(cf)
    else:
        cf = None
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = FieldEditForm(request.POST, instance=cf)
        #print(request.POST)
        if form.is_valid():
            data = form.clean()
            if not id:
                cf = ContactField(name=data['name'],
                                  hint=data['hint'],
                                  contact_group_id=data['contact_group'].id,
                                  type=data['type'],
                                  choice_group_id=data['choice_group'] and data['choice_group'].id or None,
                                  sort_weight=int(data['move_after']+5))
                cf.save()
            else:
                if not cf.system and (cf.type != data['type'] or force_text(cf.choice_group_id) != data['choice_group']):
                    deletion_details = []
                    newcls = ContactField.get_contact_field_type_by_dbid(data['type'])
                    choice_group_id = None
                    if data['choice_group']:
                        choice_group_id = data['choice_group']
                    for cfv in cf.values.all():
                        if not newcls.validate_unicode_value(cfv.value, choice_group_id):
                            deletion_details.append((cfv.contact, cfv))

                    if deletion_details:
                        if request.POST.get('confirm', None):
                            for cfv in [dd[1] for dd in deletion_details]:
                                cfv.delete()
                        else:
                            context = {}
                            context['title'] = _('Type incompatible with existing data')
                            context['id'] = id
                            context['cf'] = cf
                            context['deletion_details'] = deletion_details
                            for k in ('name', 'hint', 'contact_group', 'type', 'choice_group', 'move_after'):
                                context[k] = data[k]
                            context['nav'] = Navbar(cf.get_class_navcomponent(), cf.get_navcomponent(), ('edit', _('delete imcompatible data')))
                            return render_to_response('type_change.html', context, RequestContext(request))

                    cf.type = data['type']
                    cf.polymorphic_upgrade() # This is needed after changing type
                    cf.save()
                cf.name = data['name']
                cf.hint = data['hint']
                if not cf.system:
                    # system fields have some properties disabled
                    cf.contact_group_id = data['contact_group'].id
                    cf.type = data['type']
                    if data['choice_group']:
                        cf.choice_group_id = data['choice_group'].id
                    else:
                        cf.choice_group_id = None
                cf.sort_weight = int(data['move_after'])+5
                cf.save()

            ContactField.renumber()
            messages.add_message(request, messages.SUCCESS, _('Field %s has been changed sucessfully.') % cf.name)
            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cf.get_absolute_url()+'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cf.get_class_absolute_url()+'add')
            else:
                return HttpResponseRedirect(reverse('field_list'))
        # else validation error
    else:
        if id: # modify
            form = FieldEditForm(instance=cf)
        else: # add
            form = FieldEditForm()


    context = {}
    context['form'] = form
    context['title'] = title
    context['id'] = id
    context['objtype'] = objtype
    if id:
        context['object'] = cf
    context['nav'] = Navbar(ContactField.get_class_navcomponent())
    if id:
        context['nav'].add_component(cf.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))
    return render_to_response('edit.html', context, RequestContext(request))


###############################################################################
#
# Field delete
#
###############################################################################


@login_required()
@require_group(GROUP_USER_NGW)
def field_delete(request, id):
    if not request.user.is_admin():
        raise PermissionDenied
    obj = get_object_or_404(ContactField, pk=id)
    id = id and int(id) or None
    next_url = reverse('field_list')
    if obj.system:
        messages.add_message(request, messages.ERROR, _('Field %s is locked and CANNOT be deleted.') % obj.name)
        return HttpResponseRedirect(next_url)
    return generic_delete(request, obj, next_url)
