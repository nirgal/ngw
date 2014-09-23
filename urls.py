# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
from django.conf import settings
from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView
from django.conf.urls.static import static


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from ngw.core.views.misc import HomeView, LogoutView, TestView
from ngw.core.views.contacts import ContactListView, ContactDetailView, ContactEditView, ContactCreateView, ContactVcardView, PasswordView, HookPasswordView, PassLetterView, FilterListView
from ngw.core.views.groups import ContactGroupListView, GroupMemberListView, EventListView, GroupAddManyView, ContactGroupView, GroupEditView, GroupCreateView
from ngw.core.views.news import NewsListView, NewsEditView, NewsCreateView
from ngw.core.views.files import FileListView, GroupMediaFileView
from ngw.core.views.mailman import MailmanSyncView
from ngw.core.views.messages import MessageListView, SendMessageView, MessageDetailView
from ngw.core.views.fields import FieldListView, FieldMoveUpView, FieldMoveDownView, FieldEditView, FieldCreateView
from ngw.core.views.choices import ChoiceListView, ChoiceEditView, ChoiceCreateView
from ngw.core.views.logs import LogListView
from ngw.core.views.contactsearch import ContactSearchColumnsView, ContactSearchColumnFiltersView, ContactSearchCustomFiltersView, ContactSearchFilterParamsView, ContactSearchCustomFilterParamsView

# These patterns are valid with both /contactgroups and /events prefixes
groups_urlpatterns = patterns('',
    url(r'^add$', GroupCreateView.as_view()),
    url(r'^(?P<gid>\d+)/$', ContactGroupView.as_view()),
    url(r'^(?P<gid>\d+)/edit$', GroupEditView.as_view()),
    url(r'^(?P<id>\d+)/delete$', 'ngw.core.views.groups.contactgroup_delete'),
    url(r'^(?P<gid>\d+)/members/$', GroupMemberListView.as_view(), name='group_members'),
    url(r'^(?P<gid>\d+)/members/send_message$', SendMessageView.as_view()),
    url(r'^(?P<gid>\d+)/members/add$', ContactCreateView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/$', ContactDetailView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/vcard$', ContactVcardView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/edit$', ContactEditView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/pass$', PasswordView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/pass_letter$', PassLetterView.as_view()),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/delete$', 'ngw.core.views.contacts.contact_delete'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/membership$', 'ngw.core.views.groups.contactingroup_edit'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/membershipinline$', 'ngw.core.views.groups.contactingroup_edit_inline'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/remove$', 'ngw.core.views.groups.contactingroup_delete'),
    url(r'^(?P<gid>\d+)/members/add_contacts_to$', GroupAddManyView.as_view()),
    url(r'^(?P<gid>\d+)/files(?P<path>/.*)$', FileListView.as_view()),
    url(r'^(?P<gid>\d+)/messages/$', MessageListView.as_view(), name='message_list'),
    url(r'^(?P<gid>\d+)/messages/(?P<mid>\d+)$', MessageDetailView.as_view(), name='message_detail'),
    url(r'^(?P<gid>\d+)/news/$', NewsListView.as_view(), name='news_list'),
    url(r'^(?P<gid>\d+)/news/add$', NewsCreateView.as_view()),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/edit$', NewsEditView.as_view()),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/delete$', 'ngw.core.views.news.contactgroup_news_delete'),
    url(r'^(?P<gid>\d+)/mailman$', MailmanSyncView.as_view()),
)


js_info_dict = {
    'packages': ('ngw.core',),
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

    url(r'^contacts/(?P<cid>\d+)/$', ContactDetailView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/edit$', ContactEditView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/pass$', PasswordView.as_view(), name='contact_pass'),
    url(r'^contacts/(?P<cid>\d+)/pass_letter$', PassLetterView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/delete$', 'ngw.core.views.contacts.contact_delete', {'gid': None}),
    url(r'^contacts/(?P<cid>\d+)/vcard$', ContactVcardView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/filters/$', FilterListView.as_view()),
    url(r'^contacts/(?P<cid>\d+)/filters/add$', 'ngw.core.views.contacts.contact_filters_add', name='filter_list'),
    url(r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/$', 'ngw.core.views.contacts.contact_filters_edit', name='filter_edit'),
    url(r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/delete$', 'ngw.core.views.contacts.contact_filters_delete', name='filter_delete'),
    url(r'^contacts/(?P<cid>\d+)/default_group$', 'ngw.core.views.contacts.contact_default_group'),

    url(r'^contactgroups/$', ContactGroupListView.as_view(), name='group_list'),
    url(r'^contactgroups/', include(groups_urlpatterns)),
    url(r'^events/$', EventListView.as_view(), name='event_list'),
    url(r'^events/', include(groups_urlpatterns)),

    url(r'^contactfields/$', FieldListView.as_view(), name='field_list'),
    url(r'^contactfields/add$', FieldCreateView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^contactfields/(?P<id>\d+)/edit$', FieldEditView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/moveup$', FieldMoveUpView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/movedown$', FieldMoveDownView.as_view()),
    url(r'^contactfields/(?P<id>\d+)/delete$', 'ngw.core.views.fields.field_delete'),

    url(r'^choicegroups/$', ChoiceListView.as_view(), name='choice_list'),
    url(r'^choicegroups/add$', ChoiceCreateView.as_view(), name='choice_add'),
    url(r'^choicegroups/(?P<id>\d+)/$', RedirectView.as_view(url='edit'), ),
    url(r'^choicegroups/(?P<id>\d+)/edit$', ChoiceEditView.as_view(), name='choice_edit'),
    url(r'^choicegroups/(?P<id>\d+)/delete$', 'ngw.core.views.choices.choicegroup_delete', name='choice_delete'),

    url(r'^media/g/(?P<gid>\d+)/(?P<filename>.+)$', GroupMediaFileView.as_view()),

    url(r'^pks/lookup$', 'ngw.core.gpg.lookup'),

    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
