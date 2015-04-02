'''
ContactField managing views
'''

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.utils import html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django import forms
from django.core.urlresolvers import reverse
from django.views.generic import View, UpdateView, CreateView
from django.views.generic.edit import ModelFormMixin
from django.contrib.admin import filters
from django.contrib import messages
from ngw.core.models import ContactField, ContactGroup, ChoiceGroup
from ngw.core.nav import Navbar
from ngw.core import perms
from ngw.core.views.generic import NgwAdminAcl, InGroupAcl, NgwListView, NgwDeleteView

###############################################################################
#
# List of fields
#
###############################################################################


class FieldGroupFilter(filters.SimpleListFilter):
    title = ugettext_lazy('group')
    parameter_name = 'group'
    def lookups(self, request, view):
        self.view = view
        return (
            ('parents', _('Include parent groups')),
            ('all', _('All groups')),
        )
    def queryset(self, request, queryset):
        val = self.value()
        if val == 'all':
            return queryset
        elif val == 'parents':
            return queryset.extra(where=[
                'contact_group_id in (SELECT self_and_supergroups(%s))' % self.view.contactgroup.id])
        return queryset.filter(contact_group=self.view.contactgroup.id)

    def choices(self, cl):
        # This override the parent default "All"
        for i, choice in enumerate(super().choices(cl)):
            if i == 0:
                choice['display'] = _('Current group')
                yield choice
            else:
                yield choice


class FieldListView(InGroupAcl, NgwListView):
    template_name = 'group_fields.html'
    list_display = (
        'name_with_link',
        'clean_type_as_html',
        'contact_group',
        'locked',
        #'move_it', 'sort_weight',
        )
    list_display_links = None
    search_fields = 'name', 'hint'
    default_sort = 'sort_weight'
    list_filter = FieldGroupFilter,

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied

    def move_it(self, field):
        return '<a href='+str(field.id)+'/moveup>Up</a> <a href='+str(field.id)+'/movedown>Down</a>'
    move_it.short_description = ugettext_lazy('Move')
    move_it.allow_tags = True


    def get_root_queryset(self):
        qs = ContactField.objects \
            .with_user_perms(self.request.user.id)
        return qs


    def get_context_data(self, **kwargs):
        cg = self.contactgroup
        context = {}
        context['title'] = _('Select a field')
        context['objtype'] = ContactField
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('fields', _('fields')))
        context['active_submenu'] = 'fields'
        context.update(kwargs)
        return super().get_context_data(**context)

    def name_with_link(self, field):
        html_name = html.escape(field.name)
        if field.perm & perms.CHANGE_CG:
            return '<a href="../../%s/fields/%s/">%s</a>' % (field.contact_group.id, field.id, html_name)
        else:
            return html_name
    name_with_link.short_description = ugettext_lazy('Name')
    name_with_link.admin_order_field = 'name'
    name_with_link.allow_tags = True

    def clean_type_as_html(self, field):
        html_type = field.type_as_html()
        if not field.perm & perms.CHANGE_CG:
            html_type = html.strip_tags(str(html_type)) # ugly hack to remove links
        return html_type
    clean_type_as_html.short_description = ugettext_lazy('Type')
    clean_type_as_html.admin_order_field = 'type'
    clean_type_as_html.allow_tags = True

    def locked(self, field):
        if field.system:
            return '<img src="%sngw/lock.png" alt="locked" width="10" height="10">' % settings.STATIC_URL
        return ''
    locked.short_description = ugettext_lazy('Locked')
    locked.admin_order_field = 'system'
    locked.allow_tags = True


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
        return HttpResponseRedirect(reverse('field_list'))


class FieldMoveDownView(NgwAdminAcl, View):
    def get(self, request, *args, **kwargs):
        id = self.kwargs['id']
        id = id and int(id) or None
        cf = get_object_or_404(ContactField, pk=id)
        cf.sort_weight += 15
        cf.save()
        return HttpResponseRedirect(reverse('field_list'))


###############################################################################
#
# Field edit
#
###############################################################################


class FieldEditForm(forms.ModelForm):
    class Meta:
        model = ContactField
        fields = ['name', 'hint', 'contact_group', 'type',
            #'choice_group', 'choice_group2',
            'default']
        widgets = {
            'type': forms.Select,
            'default': forms.widgets.Input,
        }

    class IncompatibleData(Exception):
        def __init__(self, deletion_details, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.deletion_details = deletion_details

    move_after = forms.IntegerField(label=ugettext_lazy('Move after'), widget=forms.Select)

    def __init__(self, *args, **kargs):
        instance = kargs.get('instance', None)
        initial = kargs.get('initial', {})
        userid = kargs.pop('userid')
        if instance:
            initial['move_after'] = instance.sort_weight-10
        kargs['initial'] = initial
        super().__init__(*args, **kargs)

        self.delete_incompatible = bool(self.data.get('confirm', None))

        allowedgroups = ContactGroup.objects.filter(field_group=True) \
            .with_user_perms(userid, perms.CHANGE_CG)
        self.fields['contact_group'].widget.choices = [(g.id, g.name) for g in allowedgroups]

        types = [(cls.db_type_id, str(cls.human_type_id))
            for cls in  ContactField.types_classes.values()]
        types.sort(key=lambda cls: cls[1])
        self.fields['type'].widget.choices = types

        self.fields['default'].widget.attrs['disabled'] = 1

        self.fields['move_after'].widget.choices = [(0, _('Name'))] + [(field.sort_weight, field.name) for field in ContactField.objects.order_by('sort_weight')]

        if instance and instance.system:
            self.fields['contact_group'].widget.attrs['disabled'] = 1
            self.fields['type'].widget.attrs['disabled'] = 1
            self.fields['type'].required = False

    def clean(self):
        if self.instance.system:
            # If this is a system locked field, some attributes may not be
            # changed:
            self.cleaned_data['contact_group'] = self.instance.contact_group
            self.cleaned_data['type'] = self.instance.type

        new_cls_id = self.cleaned_data['type']
        new_cls = ContactField.get_contact_field_type_by_dbid(new_cls_id)

        if self.instance:
            choice_group_id = self.instance.choice_group_id
            choice_group2_id = self.instance.choice_group2_id
        else:
            choice_group_id = None
            choice_group2_id = None

        if not self.delete_incompatible:
            deletion_details = []
            for cfv in self.instance.values.all():
                if not new_cls.validate_unicode_value(cfv.value, choice_group_id, choice_group2_id) \
                   or self.instance.has_choice != new_cls.has_choice:
                    deletion_details.append((cfv.contact, str(cfv)))
            if deletion_details:
                raise FieldEditForm.IncompatibleData(deletion_details)

        return self.cleaned_data

    def save(self):
        new_cls_id = self.cleaned_data['type']

        if self.instance:
            choice_group_id = self.instance.choice_group_id
            choice_group2_id = self.instance.choice_group2_id
        else:
            choice_group_id = None
            choice_group2_id = None

        if self.instance.pk:
            # we are changing an existing field
            deletion_details = []

            if self.delete_incompatible:
                new_cls = ContactField.get_contact_field_type_by_dbid(new_cls_id)
                for cfv in self.instance.values.all():
                    if not new_cls.validate_unicode_value(cfv.value, choice_group_id, choice_group2_id) \
                        or self.instance.has_choice != new_cls.has_choice:
                        cfv.delete()
            else:  # delete_incompatible==False
                new_cls = ContactField.get_contact_field_type_by_dbid(new_cls_id)
                for cfv in self.instance.values.all():
                    if not new_cls.validate_unicode_value(cfv.value, choice_group_id, choice_group2_id) \
                        or self.instance.has_choice != new_cls.has_choice:
                        deletion_details.append((cfv.contact, cfv))
                if deletion_details:
                    raise FieldEditForm.IncompatibleData(deletion_details)


        cf = super().save(commit=False)

        # Hack to set up cf.__class__ without saving it
        cf.polymorphic_upgrade()

        # Create choicegroups when missing, delete it when no longer needed
        if type(cf).has_choice >= 1:
            if not cf.choice_group:
                choice_group = ChoiceGroup()
                choice_group.save()
                cf.choice_group_id = choice_group.id
        else:
            if cf.choice_group:
                cf.choice_group.delete()
                cf.choice_group_id = None

        if type(cf).has_choice == 2:
            if not cf.choice_group2:
                choice_group2 = ChoiceGroup()
                choice_group2.save()
                cf.choice_group2_id = choice_group2.id
        else:
            if cf.choice_group2:
                cf.choice_group2.delete()
                cf.choice_group2_id = None

        cf.sort_weight = self.cleaned_data['move_after'] + 5
        cf.save()

        return cf


class FieldEditMixin(ModelFormMixin):
    template_name = 'field_edit.html'
    form_class = FieldEditForm
    model = ContactField
    pk_url_kwarg = 'id'

    def get_object(self, queryset=None):
        cf = super().get_object(queryset)
        if cf.contact_group_id != self.contactgroup.id:
            raise PermissionDenied
        return cf

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if 'initial' not in kwargs:
            kwargs['initial'] = {}
        kwargs['initial']['contact_group'] = self.contactgroup
        kwargs['userid'] = self.request.user.id
        return kwargs

    def form_valid(self, form):
        request = self.request
        cf = form.save()

        messages.add_message(request, messages.SUCCESS, _('Field %s has been saved successfully.') % cf.name)

        if self.pk_url_kwarg not in self.kwargs: # new added instance
            base_url = '.'
        else:
            base_url = '..'
        if request.POST.get('_continue', None):
            return HttpResponseRedirect(
                base_url + '/' + str(cf.id) + '/edit')
        elif request.POST.get('_addanother', None):
            return HttpResponseRedirect(base_url + '/add')
        else:
            return HttpResponseRedirect(base_url)

    def get_context_data(self, **kwargs):
        context = {}
        cg = self.contactgroup
        if self.object:
            title = _('Editing %s') % self.object
            id = self.object.id
        else:
            title = _('Adding a new %s') % ContactField.get_class_verbose_name()
            id = None
        context['title'] = title
        context['id'] = id
        context['objtype'] = ContactField
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('fields', _('contact fields')))
        if id:
            context['nav'].add_component(self.object.get_navcomponent()) \
                          .add_component(('edit', _('edit')))
        else:
            context['nav'].add_component(('add', _('add')))
        context['active_submenu'] = 'fields'

        context.update(kwargs)
        return super().get_context_data(**context)


class FieldEditView(InGroupAcl, FieldEditMixin, UpdateView):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied

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
            cg = self.contactgroup
            cf = form.instance
            context = {}
            context['title'] = _('Type incompatible with existing data')
            context['id'] = cf.id
            context['cf'] = cf
            context['deletion_details'] = err.deletion_details
            for k in ('name', 'hint', 'contact_group', 'type', 'move_after'):
                context[k] = form.cleaned_data[k]
            context['contact_group'] = form.cleaned_data['contact_group'].id
            context['nav'] = cg.get_smart_navbar()
            context['nav'].add_component(('fields', _('contact fields')))
            context['nav'].add_component(cf.get_navcomponent())
            context['nav'].add_component(('edit', _('delete incompatible data')))
            return render_to_response('type_change.html', context, RequestContext(request))


class FieldCreateView(InGroupAcl, FieldEditMixin, CreateView):
    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied


###############################################################################
#
# Field delete
#
###############################################################################


class FieldDeleteView(InGroupAcl, NgwDeleteView):
    model = ContactField
    pk_url_kwarg = 'id'

    def check_perm_groupuser(self, group, user):
        if not group.userperms & perms.CHANGE_CG:
            raise PermissionDenied

    def get_object(self, *args, **kwargs):
        field = super().get_object(*args, **kwargs)
        if field.contact_group_id != self.contactgroup.id:
            raise PermissionDenied
        if field.system:
            messages.add_message(
                self.request, messages.ERROR,
                _('Field %s is locked and CANNOT be deleted.') % field.name)
            raise PermissionDenied
        return field
