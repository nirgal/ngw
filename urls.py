# -*- encoding: utf-8 -*-

from django.conf import settings
from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView
from django.conf.urls.static import static


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from ngw.core.models import ContactField, ContactGroup
admin.autodiscover()

from ngw.core.views.misc import HomeView, LogoutView, TestView
from ngw.core.views.contacts import ContactListView, GroupAddManyView, ContactDetailView, ContactEditView, ContactCreateView, ContactDeleteView, ContactVcardView, PasswordView, HookPasswordView, PassLetterView, FilterAddView, FilterEditView, FilterListView, FilterDeleteView, DefaultGroupView
from ngw.core.views.groups import ContactGroupListView, GroupMemberListView, EventListView, ContactGroupView, GroupEditView, GroupCreateView, GroupDeleteView, ContactInGroupView, ContactInGroupInlineView, ContactInGroupDelete
from ngw.core.views.news import NewsListView, NewsEditView, NewsCreateView, NewsDeleteView
from ngw.core.views.files import FileListView, GroupMediaFileView
from ngw.core.views.mailman import MailmanSyncView
from ngw.core.views.messages import MessageListView, SendMessageView, MessageDetailView
from ngw.core.views.fields import FieldListView, FieldMoveUpView, FieldMoveDownView, FieldEditView, FieldCreateView, FieldDeleteView
from ngw.core.views.choices import ChoiceListView, ChoiceEditView, ChoiceCreateView, ChoiceGroupDeleteView
from ngw.core.views.logs import LogListView
from ngw.core.views.contactsearch import ContactSearchColumnsView, ContactSearchColumnFiltersView, ContactSearchCustomFiltersView, ContactSearchFilterParamsView, ContactSearchCustomFilterParamsView
from ngw.core.gpg import GpgLookupView

# These patterns are valid with both /contactgroups and /events prefixes
groups_urlpatterns = patterns('',
    url(r'^add$', GroupCreateView.as_view()),
    url(r'^(?P<gid>\d+)/$', ContactGroupView.as_view()),
    url(r'^(?P<gid>\d+)/edit$', GroupEditView.as_view()),
    url(r'^(?P<gid>\d+)/delete$', GroupDeleteView.as_view()),
    url(r'^(?P<gid>\d+)/members/$', GroupMemberListView.as_view(), name='group_members'),
    url(r'^(?P<gid>\d+)/members/send_message$', SendMessageView.as_view()),
    url(r'^(?P<gid>\d+)/members/add$', ContactCreateView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/$', ContactDetailView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/vcard$', ContactVcardView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/edit$', ContactEditView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/pass$', PasswordView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/pass_letter$', PassLetterView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/delete$', ContactDeleteView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/membership$', ContactInGroupView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/membershipinline$', ContactInGroupInlineView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/remove$', ContactInGroupDelete.as_view()),
    url(r'^(?P<gid>\d+)/files(?P<path>/.*)$', FileListView.as_view()),
    url(r'^(?P<gid>\d+)/messages/$', MessageListView.as_view(), name='message_list'),
    url(r'^(?P<gid>\d+)/messages/(?P<mid>\d+)$', MessageDetailView.as_view(), name='message_detail'),
    url(r'^(?P<gid>\d+)/news/$', NewsListView.as_view(), name='news_list'),
    url(r'^(?P<gid>\d+)/news/add$', NewsCreateView.as_view()),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/edit$', NewsEditView.as_view()),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/delete$', NewsDeleteView.as_view()),
    url(r'^(?P<gid>\d+)/mailman$', MailmanSyncView.as_view()),
)


js_info_dict = {
    'packages': ('ngw.core','django.contrib.admin',),
    }

urlpatterns = patterns('',
    url(r'^$', HomeView.as_view()),
    
    url(r'^test$', TestView.as_view()),

    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog', js_info_dict),
    url(r'^jsi18n/(?P<packages>\S+?)/$', 'django.views.i18n.javascript_catalog'),

    url(r'session_security/', include('session_security.urls')),

    url(r'^hook_change_password$', HookPasswordView.as_view()),

    url(r'^login$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^logout$', LogoutView.as_view(), name='logout'),

    url(r'^logs$', LogListView.as_view(), name='log_list'),

    url(r'^contacts/$', ContactListView.as_view(), name='contact_list'),
    url(r'^contacts/ajaxsearch/(?P<column_type>\w+)$', ContactSearchColumnsView.as_view()),
    url(r'^contacts/ajaxsearch/custom/user$', ContactSearchCustomFiltersView.as_view()),
    url(r'^contacts/ajaxsearch/(?P<column_type>\w+)/(?P<column_id>\w+)$', ContactSearchColumnFiltersView.as_view()),
    url(r'^contacts/ajaxsearch/custom/user/(?P<filter_id>[^/]+)$', ContactSearchCustomFilterParamsView.as_view()),
    url(r'^contacts/ajaxsearch/(?P<column_type>\w+)/(?P<column_id>\w+)/(?P<filter_id>[^/]+)$', ContactSearchFilterParamsView.as_view()),
#    url(r'^contacts/make_login_mailing$', 'ngw.core.views.contacts.contact_make_login_mailing'),

    url(r'^contacts/(?P<cid>\d+)/$', ContactDetailView.as_view(), name='contact_detail'),
    url(r'^contacts/add_to_group$', GroupAddManyView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/edit$', ContactEditView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/pass$', PasswordView.as_view(), name='contact_pass'),
    url(r'^contacts/(?P<cid>\d+)/pass_letter$', PassLetterView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/delete$', ContactDeleteView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/vcard$', ContactVcardView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/filters/$', FilterListView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/filters/add$', FilterAddView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/$', FilterEditView.as_view(), name='filter_edit'),
    url(r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/delete$', FilterDeleteView.as_view(), name='filter_delete'),
    url(r'^contacts/(?P<cid>\d+)/default_group$', DefaultGroupView.as_view()),

    url(r'^contactgroups/$', ContactGroupListView.as_view(), name='group_list'),
    url(r'^contactgroups/', include(groups_urlpatterns)),
    #url(r'^contactgroups2/$', admin.site.admin_view(admin.site._registry[ContactGroup].changelist_view)),
    #url(r'^contactgroups2/(?P<object_id>\d+)/edit$', admin.site.admin_view(admin.site._registry[ContactGroup].change_view)),
    url(r'^events/$', EventListView.as_view(), name='event_list'),
    url(r'^events/', include(groups_urlpatterns)),

    url(r'^contactfields/$', FieldListView.as_view(), name='field_list'),
    url(r'^contactfields/add$', FieldCreateView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^contactfields/(?P<id>\d+)/edit$', FieldEditView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/moveup$', FieldMoveUpView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/movedown$', FieldMoveDownView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/delete$', FieldDeleteView.as_view()),

    #url(r'^contactfields2/$', admin.site.admin_view(admin.site._registry[ContactField].changelist_view)),
    #url(r'^contactfields2/(\d+)/$', RedirectView.as_view(url='edit')),
    #url(r'^contactfields2/(?P<object_id>\d+)/edit$', admin.site.admin_view(admin.site._registry[ContactField].change_view)),

    url(r'^choicegroups/$', ChoiceListView.as_view(), name='choice_list'),
    url(r'^choicegroups/add$', ChoiceCreateView.as_view(), name='choice_add'),
    url(r'^choicegroups/(?P<id>\d+)/$', RedirectView.as_view(url='edit'), ),
    url(r'^choicegroups/(?P<id>\d+)/edit$', ChoiceEditView.as_view(), name='choice_edit'),
    url(r'^choicegroups/(?P<id>\d+)/delete$', ChoiceGroupDeleteView.as_view(), name='choice_delete'),

    url(r'^media/g/(?P<gid>\d+)/(?P<filename>.+)$', GroupMediaFileView.as_view()),

    url(r'^pks/lookup$', GpgLookupView.as_view()),

    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
