# This file is unused

from django.contrib import admin
from django.utils.translation import ugettext_lazy
from ngw.core.models import (Config, Contact, ContactGroup, GroupInGroup,
    ContactInGroup, Choice, ChoiceGroup, ContactGroupNews, ContactField,
    ContactFieldValue, ContactMsg)

# Globally disable delete selected
admin.site.disable_action('delete_selected')


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = 'id', 'text'
    list_editable = 'text',


from ngw.core.views.contacts import ContactEditForm
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = 'name',
    search_fields = 'name',
    def get_form(self, request, obj=None, **kwargs):
        class TheForm(ContactEditForm):
            def __init__(self, *args, **kwargs):
                super(TheForm, self).__init__(
                    user=request.user,
                    contactgroup=None,
                    *args, **kwargs)
        return TheForm

    def get_fields(self, request, obj=None):
        Form = self.get_form(request, obj)
        form = Form(instance=obj)
        return list(form.fields)


from ngw.core.views.groups import ContactGroupForm
@admin.register(ContactGroup)
class ContactGroupAdmin(admin.ModelAdmin):
    list_display = 'name', 'description'
    search_fields = 'name',
    def get_form(self, request, obj=None, **kwargs):
        class TheForm(ContactGroupForm):
            def __init__(self, *args, **kwargs):
                super(TheForm, self).__init__(
                    user=request.user,
                    *args, **kwargs)
        return TheForm

    def get_fields(self, request, obj=None):
        Form = self.get_form(request, obj)
        form = Form(instance=obj)
        return list(form.fields)


from ngw.core.views.choices import ChoiceListView
class ChoiceAdminInLine(admin.TabularInline):
    model = Choice
    fields = 'value', 'key'
@admin.register(ChoiceGroup)
class ChoiceGroupAdmin(admin.ModelAdmin, ChoiceListView):
    list_display = ChoiceListView.list_display
    inlines = [ChoiceAdminInLine]


@admin.register(ContactGroupNews)
class ContactGroupNewsAdmin(admin.ModelAdmin):
    list_display = 'title', 'date', 'author', 'contact_group'


from ngw.core.views.fields import FieldEditForm
@admin.register(ContactField)
class ContactFieldAdmin(admin.ModelAdmin):
    list_display = 'name', 'nice_case_type', 'contact_group', 'system'
    list_display_links = None
    form = FieldEditForm

    def nice_case_type(self, field):
        return field.type[0].upper() + field.type[1:].lower()
    nice_case_type.short_description = ugettext_lazy('type')
    nice_case_type.admin_order_field = 'type'

    def changelist_view(self, request):
        return super(ContactFieldAdmin, self).changelist_view(request)
    #def get_urls(self):
    #    urls = super(MyModelAdmin, self).get_urls()
    #    my_urls = patterns('',
    #        (r'^my_view/$', self.my_view)
    #    )
    #    return my_urls + urls

    #def my_view(self, request):
    #    # custom view which should return an HttpResponse
    #    pass


@admin.register(ContactFieldValue)
class ContactFieldValueAdmin(admin.ModelAdmin):
    list_display = 'contact', 'contact_field', 'value'

################################

from ngw.core.views.messages import MessageDirectionFilter, MessageReadFilter, MessageContactFilter
@admin.register(ContactMsg)
class ContactMsgAdmin(admin.ModelAdmin):
    list_display = 'nice_flags', 'group', 'send_date', 'contact', 'subject'
    #list_filter = 'is_answer', 'contact'
    list_filter = MessageDirectionFilter, MessageReadFilter, MessageContactFilter
    search_fields = 'subject', 'text'

