# This file is unused
from __future__ import print_function
from django.contrib import admin
from ngw.core.models import (Config, Contact, ContactGroup, GroupInGroup,
    ContactInGroup, Choice, ChoiceGroup, ContactGroupNews, ContactField,
    ContactFieldValue, ContactSysMsg )

admin.site.register(Config)


class ContactAdmin(admin.ModelAdmin):
    fields = 'name',
admin.site.register(Contact, ContactAdmin)

admin.site.register(ContactGroup)
admin.site.register(GroupInGroup)
admin.site.register(ContactInGroup)

class ChoiceAdminInLine(admin.TabularInline):
    model = Choice
class ChoiceGroupAdmin(admin.ModelAdmin):
    inlines = [ ChoiceAdminInLine ]
admin.site.register(ChoiceGroup, ChoiceGroupAdmin)


class ContactGroupNewsAdmin(admin.ModelAdmin):
    list_display = 'title', 'date', 'author'
admin.site.register(ContactGroupNews, ContactGroupNewsAdmin)

class ContactFieldAdmin(admin.ModelAdmin):
    pass
admin.site.register(ContactField, ContactFieldAdmin)

class ContactFieldValueAdmin(admin.ModelAdmin):
    list_display = 'contact', 'contact_field', 'value'
admin.site.register(ContactFieldValue, ContactFieldValueAdmin)

admin.site.register(ContactSysMsg)
