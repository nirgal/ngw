# This file was unused

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList

from ngw.core.models import (Config, Contact, ContactField, ContactFieldValue,
                             ContactGroup, ContactGroupNews, ContactMsg)
from ngw.core.views.contacts import ContactEditForm
from ngw.core.views.fields import FieldEditForm, FieldListView
from ngw.core.views.groups import ContactGroupForm, ContactGroupListView
from ngw.core.views.messages import (MessageContactFilter,
                                     MessageDirectionFilter, MessageListView,
                                     MessageReadFilter)

# Globally disable delete selected
admin.site.disable_action('delete_selected')


class MyChangeList(ChangeList):
    '''
    This is a clone of ChangeList, but urls are relative
    '''
    def url_for_result(self, result):
        pk = getattr(result, self.pk_attname)
        return str(pk)+'/'


class MyModelAdmin(admin.ModelAdmin):
    '''
    This is a clone of admin.ModelAdmin, but uses MyChangeList
    '''
    def get_changelist(self, request, **kwargs):
        return MyChangeList


@admin.register(Config)
class ConfigAdmin(MyModelAdmin):
    list_display = 'id', 'text'
    list_editable = 'text',


@admin.register(Contact)
class ContactAdmin(MyModelAdmin):
    list_display = 'name',
    search_fields = 'name',

    def get_form(self, request, obj=None, **kwargs):
        class TheForm(ContactEditForm):
            def __init__(self, *args, **kwargs):
                super().__init__(
                    user=request.user,
                    contactgroup=None,
                    *args, **kwargs)
        return TheForm

    def get_fields(self, request, obj=None):
        Form = self.get_form(request, obj)
        form = Form(instance=obj)
        return list(form.fields)


@admin.register(ContactGroup)
class ContactGroupAdmin(MyModelAdmin, ContactGroupListView):
    list_display = ContactGroupListView.list_display
    search_fields = 'name',

    def get_form(self, request, obj=None, **kwargs):
        class TheForm(ContactGroupForm):
            def __init__(self, *args, **kwargs):
                super().__init__(
                    user=request.user,
                    *args, **kwargs)
        return TheForm

    def get_fields(self, request, obj=None):
        Form = self.get_form(request, obj)
        form = Form(instance=obj)
        return list(form.fields)

    def get_queryset(self, request):
        self.request = request
        return self.get_root_queryset()


# from ngw.core.views.choices import ChoiceListView
# class ChoiceAdminInLine(admin.TabularInline):
#     model = Choice
#     fields = 'value', 'key'
# @admin.register(ChoiceGroup)
# class ChoiceGroupAdmin(MyModelAdmin, ChoiceListView):
#     list_display = ChoiceListView.list_display
#     inlines = [ChoiceAdminInLine]


@admin.register(ContactGroupNews)
class ContactGroupNewsAdmin(MyModelAdmin):
    list_display = 'title', 'date', 'author', 'contact_group'


@admin.register(ContactField)
class ContactFieldAdmin(MyModelAdmin, FieldListView):
    list_display = FieldListView.list_display
    form = FieldEditForm

    def changelist_view(self, request):
        return super().changelist_view(request)
    # def get_urls(self):
    #     urls = super().get_urls()
    #     my_urls = patterns('',
    #         (r'^my_view/$', self.my_view)
    #     )
    #     return my_urls + urls

    # def my_view(self, request):
    #     # custom view which should return an HttpResponse
    #     pass


@admin.register(ContactFieldValue)
class ContactFieldValueAdmin(MyModelAdmin):
    list_display = 'contact', 'contact_field', 'value'


@admin.register(ContactMsg)
class ContactMsgAdmin(MyModelAdmin, MessageListView):
    list_display = MessageListView.list_display
    list_display_links = 'subject',
    # list_filter = 'is_answer', 'contact'
    list_filter = (
        MessageDirectionFilter, MessageReadFilter, MessageContactFilter)
    search_fields = 'subject', 'text'
