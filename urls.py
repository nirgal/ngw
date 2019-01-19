from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView

from ngw.core.gpg import GpgLookupView
from ngw.core.views.choices import Choice2EditView, ChoiceEditView
from ngw.core.views.contacts import (ContactCreateView, ContactDeleteView,
                                     ContactDetailView, ContactEditView,
                                     ContactListView, ContactVcardView,
                                     DefaultGroupView, FilterAddView,
                                     FilterDeleteView, FilterEditView,
                                     FilterListView, GroupAddManyView,
                                     HookPasswordView, PassLetterView,
                                     PasswordView)
from ngw.core.views.contactsearch import (ContactSearchAutocompleteView,
                                          ContactSearchColumnFiltersView,
                                          ContactSearchColumnsView,
                                          ContactSearchFilterParamsView,
                                          ContactSearchSavedFilterParamsView,
                                          ContactSearchSavedFiltersView)
from ngw.core.views.fields import (FieldCreateView, FieldDeleteView,
                                   FieldEditView, FieldListView,
                                   FieldMoveDownView, FieldMoveUpView)
from ngw.core.views.files import (FileContactFieldThumbView,
                                  FileContactFieldView, FileListView,
                                  GroupMediaFileView)
from ngw.core.views.groups import (CalendarQueryView, CalendarView,
                                   ContactGroupListView, ContactGroupView,
                                   ContactInGroupDelete,
                                   ContactInGroupInlineView,
                                   ContactInGroupView, EventListView,
                                   GroupCreateView, GroupDeleteView,
                                   GroupEditView, GroupMemberListView)
from ngw.core.views.logs import LogListView
from ngw.core.views.mailman import MailmanSyncView
from ngw.core.views.messages import (MessageDetailView, MessageListView,
                                     SendMessageView)
from ngw.core.views.misc import HomeView, LogoutView, TestView
from ngw.core.views.news import (NewsCreateView, NewsDeleteView, NewsEditView,
                                 NewsListView)

# from ngw.core.admin import ContactGroupAdmin


# These patterns are valid with both /contactgroups and /events prefixes
groups_urlpatterns = [
    url('^add$', GroupCreateView.as_view()),
    url('^(?P<gid>\d+)/$', ContactGroupView.as_view()),
    url('^(?P<gid>\d+)/edit$', GroupEditView.as_view()),
    url('^(?P<gid>\d+)/delete$', GroupDeleteView.as_view()),
    url('^(?P<gid>\d+)/members/$',
        GroupMemberListView.as_view(), name='group_members'),
    url('^(?P<gid>\d+)/members/send_message$', SendMessageView.as_view()),
    url('^(?P<gid>\d+)/members/add$', ContactCreateView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/$', ContactDetailView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/vcard$',
        ContactVcardView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/edit$',
        ContactEditView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/pass$', PasswordView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/pass_letter$',
        PassLetterView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/delete$',
        ContactDeleteView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/membership$',
        ContactInGroupView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/membershipinline$',
        ContactInGroupInlineView.as_view()),
    url('^(?P<gid>\d+)/members/(?P<cid>\d+)/remove$',
        ContactInGroupDelete.as_view()),
    url('^(?P<gid>\d+)/files(?P<path>/.*)$', FileListView.as_view()),
    url('^(?P<gid>\d+)/messages/$',
        MessageListView.as_view(), name='message_list'),
    url('^(?P<gid>\d+)/messages/(?P<mid>\d+)$',
        MessageDetailView.as_view(), name='message_detail'),
    url('^(?P<gid>\d+)/news/$', NewsListView.as_view(), name='news_list'),
    url('^(?P<gid>\d+)/news/add$', NewsCreateView.as_view()),
    url('^(?P<gid>\d+)/news/(?P<nid>\d+)/$',
        RedirectView.as_view(url='edit', permanent=True)),
    url('^(?P<gid>\d+)/news/(?P<nid>\d+)/edit$', NewsEditView.as_view()),
    url('^(?P<gid>\d+)/news/(?P<nid>\d+)/delete$', NewsDeleteView.as_view()),
    url('^(?P<gid>\d+)/mailman$', MailmanSyncView.as_view()),

    url('^(?P<gid>\d+)/fields/$', FieldListView.as_view()),
    url('^(?P<gid>\d+)/fields/add$', FieldCreateView.as_view()),
    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/$',
        RedirectView.as_view(url='edit', permanent=True)),
    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/edit$', FieldEditView.as_view()),
    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/moveup$',
        FieldMoveUpView.as_view()),
    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/movedown$',
        FieldMoveDownView.as_view()),
    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/delete$',
        FieldDeleteView.as_view()),

    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/choices$',
        ChoiceEditView.as_view()),
    url('^(?P<gid>\d+)/fields/(?P<id>\d+)/choices2$',
        Choice2EditView.as_view()),
]


js_info_dict = {
    'packages': ('ngw.core', 'django.contrib.admin',),
    }


urlpatterns = [
    url('^$', HomeView.as_view()),

    url('^test$', TestView.as_view()),

    url('^jsi18n/$', 'django.views.i18n.javascript_catalog', js_info_dict),
    url('^jsi18n/(?P<packages>\S+?)/$',
        'django.views.i18n.javascript_catalog'),

    url('session_security/', include('session_security.urls')),

    url('^hook_change_password$', HookPasswordView.as_view()),

    url('^login$',
        'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url('^logout$', LogoutView.as_view(), name='logout'),

    url('^logs$', LogListView.as_view(), name='log_list'),

    url('^contacts/$', ContactListView.as_view(), name='contact_list'),
    url('^contacts/ajaxsearch/autocomplete$',
        ContactSearchAutocompleteView.as_view()),
    url('^contacts/ajaxsearch/(?P<column_type>\w+)$',
        ContactSearchColumnsView.as_view()),
    url('^contacts/ajaxsearch/saved/(?P<cid>\d+)$',
        ContactSearchSavedFiltersView.as_view()),
    url('^contacts/ajaxsearch/(?P<column_type>\w+)/(?P<column_id>\w+)$',
        ContactSearchColumnFiltersView.as_view()),
    url('^contacts/ajaxsearch/saved/(?P<cid>\d+)/(?P<filter_id>[^/]+)$',
        ContactSearchSavedFilterParamsView.as_view()),
    url('^contacts/ajaxsearch/(?P<column_type>\w+)/(?P<column_id>\w+)'
        r'/(?P<filter_id>[^/]+)$',
        ContactSearchFilterParamsView.as_view()),
    # url('^contacts/make_login_mailing$',
    #     'ngw.core.views.contacts.contact_make_login_mailing'),

    url('^contacts/(?P<cid>\d+)/$',
        ContactDetailView.as_view(), name='contact_detail'),
    url('^contacts/add_to_group$', GroupAddManyView.as_view()),
    url('^contacts/(?P<cid>\d+)/edit$', ContactEditView.as_view()),
    url('^contacts/(?P<cid>\d+)/pass$',
        PasswordView.as_view(), name='contact_pass'),
    url('^contacts/(?P<cid>\d+)/pass_letter$', PassLetterView.as_view()),
    url('^contacts/(?P<cid>\d+)/delete$', ContactDeleteView.as_view()),
    url('^contacts/(?P<cid>\d+)/vcard$', ContactVcardView.as_view()),
    url('^contacts/(?P<cid>\d+)/filters/$', FilterListView.as_view()),
    url('^contacts/(?P<cid>\d+)/filters/add$', FilterAddView.as_view()),
    url('^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/$',
        FilterEditView.as_view(), name='filter_edit'),
    url('^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/delete$',
        FilterDeleteView.as_view(), name='filter_delete'),
    url('^contacts/(?P<cid>\d+)/default_group$', DefaultGroupView.as_view()),

    url('^contactgroups/$',
        ContactGroupListView.as_view(), name='group_list'),
    url('^contactgroups/', include(groups_urlpatterns)),
    # url('^contactgroups2/$',
    #     admin.site.admin_view(
    #         admin.site._registry[ContactGroup].changelist_view)),
    url('^events/$', EventListView.as_view(), name='event_list'),
    url('^events/calendar/$', CalendarView.as_view()),
    url('^events/calendar/query$', CalendarQueryView.as_view()),
    url('^events/', include(groups_urlpatterns)),

    url('^media/g/(?P<gid>\d+)/(?P<filename>.+)$',
        GroupMediaFileView.as_view()),
    url('^media/fields/(?P<fid>\d+)/(?P<cid>\d+)$',
        FileContactFieldView.as_view()),
    url('^media/fields/(?P<fid>\d+)/'
        + '(?P<cid>\d+)\.(?P<width>\d+)x(?P<height>\d+)$',
        FileContactFieldThumbView.as_view()),

    url('^pks/lookup$', GpgLookupView.as_view()),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url('^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url('^admin/', include(admin.site.urls)),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
