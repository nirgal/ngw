# This file is unused

from __future__ import division, absolute_import, print_function, unicode_literals
from django.contrib import admin
from ngw.core.models import (Config, Contact, ContactGroup, GroupInGroup,
    ContactInGroup, Choice, ChoiceGroup, ContactGroupNews, ContactField,
    ContactFieldValue)

class ConfigAdmin(admin.ModelAdmin):
    list_display = 'id',
admin.site.register(Config, ConfigAdmin)


class ContactAdmin(admin.ModelAdmin):
    list_display = 'name',
admin.site.register(Contact, ContactAdmin)

class ContactGroupAdmin(admin.ModelAdmin):
    list_display = 'name', 'description'
    search_fields = 'name',
admin.site.register(ContactGroup, ContactGroupAdmin)

#admin.site.register(GroupInGroup)
#admin.site.register(ContactInGroup)

class ChoiceAdminInLine(admin.TabularInline):
    model = Choice
class ChoiceGroupAdmin(admin.ModelAdmin):
    list_display = 'name', 'choices'
    inlines = [ ChoiceAdminInLine ]
admin.site.register(ChoiceGroup, ChoiceGroupAdmin)


class ContactGroupNewsAdmin(admin.ModelAdmin):
    list_display = 'title', 'date', 'author'
admin.site.register(ContactGroupNews, ContactGroupNewsAdmin)

class ContactFieldAdmin(admin.ModelAdmin):
    list_display = 'name', 'type', 'contact_group', 'system'
admin.site.register(ContactField, ContactFieldAdmin)

class ContactFieldValueAdmin(admin.ModelAdmin):
    list_display = 'contact', 'contact_field', 'value'
admin.site.register(ContactFieldValue, ContactFieldValueAdmin)

