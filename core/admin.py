# This file is unused

from __future__ import division, absolute_import, print_function, unicode_literals
from django.contrib import admin
from django.utils.translation import ugettext_lazy
from ngw.core.models import (Config, Contact, ContactGroup, GroupInGroup,
    ContactInGroup, Choice, ChoiceGroup, ContactGroupNews, ContactField,
    ContactFieldValue, ContactMsg)

# Globally disable delete selected
#admin.site.disable_action('delete_selected')

class ConfigAdmin(admin.ModelAdmin):
    list_display = 'id', 'text'
    list_editable = 'text',
admin.site.register(Config, ConfigAdmin)


#from ngw.core.views.contacts import ContactEditForm
class ContactAdmin(admin.ModelAdmin):
    list_display = 'name',
    search_fields = 'name',
    #form = ContactEditForm
    #def get_form(self, request, obj=None, **kwargs):
    #    BaseForm = super(ContactAdmin, self).get_form(request, obj=None, **kwargs)
    #    class TheForm(BaseForm):
    #        def __init__(self, *args, **kwargs):
    #            super(TheForm, self).__init__(
    #                user=request.user,
    #                *args, **kwargs)
    #    return TheForm

admin.site.register(Contact, ContactAdmin)

class ContactGroupAdmin(admin.ModelAdmin):
    list_display = 'name', 'description'
    search_fields = 'name',
admin.site.register(ContactGroup, ContactGroupAdmin)

#admin.site.register(GroupInGroup)
#admin.site.register(ContactInGroup)

class ChoiceAdminInLine(admin.TabularInline):
    model = Choice
    fields = 'value', 'key'
class ChoiceGroupAdmin(admin.ModelAdmin):
    list_display = 'name', 'ordered_choices'
    inlines = [ChoiceAdminInLine]
admin.site.register(ChoiceGroup, ChoiceGroupAdmin)


class ContactGroupNewsAdmin(admin.ModelAdmin):
    list_display = 'title', 'date', 'author', 'contact_group'
admin.site.register(ContactGroupNews, ContactGroupNewsAdmin)

from ngw.core.views.fields import FieldEditForm
class ContactFieldAdmin(admin.ModelAdmin):
    list_display = 'name', 'nice_case_type', 'contact_group', 'system'
    #list_display_links = 'name',
    #list_editable = 'name', 'contact_group',
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

admin.site.register(ContactField, ContactFieldAdmin)

class ContactFieldValueAdmin(admin.ModelAdmin):
    list_display = 'contact', 'contact_field', 'value'
admin.site.register(ContactFieldValue, ContactFieldValueAdmin)

class ContactMsgAdmin(admin.ModelAdmin):
    list_display = 'nice_flags', 'group', 'send_date', 'contact', 'subject'
    list_filter = 'is_answer', 'contact'
    search_fields = 'subject', 'text'
admin.site.register(ContactMsg, ContactMsgAdmin)

