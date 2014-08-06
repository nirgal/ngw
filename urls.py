# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
from django.conf import settings
from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView
from django.conf.urls.static import static


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

#from ngw.core.views import ContactGroupList

groups_urlpatterns = patterns('',
    url(r'^add$', 'ngw.core.views.contactgroup_edit', {'id': None}),
    url(r'^(?P<gid>\d+)/$', 'ngw.core.views.contactgroup_details'),
    url(r'^(?P<id>\d+)/edit$', 'ngw.core.views.contactgroup_edit'),
    url(r'^(?P<id>\d+)/delete$', 'ngw.core.views.contactgroup_delete'),
    url(r'^(?P<gid>\d+)/members/$', 'ngw.core.views.contactgroup_members'),
    url(r'^(?P<gid>\d+)/members/vcards$', 'ngw.core.views.contactgroup_members', {'output_format': 'vcards'}),
    url(r'^(?P<gid>\d+)/members/emails$',  'ngw.core.views.contactgroup_emails'),
    #url(r'^(?P<gid>\d+)/members/emails$',  'ngw.core.views.contactgroup_members', {'output_format': 'emails'}),
    url(r'^(?P<gid>\d+)/members/csv$', 'ngw.core.views.contactgroup_members', {'output_format': 'csv'}),
    url(r'^(?P<gid>\d+)/members/add$', 'ngw.core.views.contact_edit', {'cid':None}),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/$', 'ngw.core.views.contact_detail'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/vcard$', 'ngw.core.views.contact_vcard'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/edit$', 'ngw.core.views.contact_edit'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/pass$', 'ngw.core.views.contact_pass'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/pass_letter$', 'ngw.core.views.contact_pass_letter'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/delete$', 'ngw.core.views.contact_delete'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/membership$', 'ngw.core.views.contactingroup_edit'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/membershipinline$', 'ngw.core.views.contactingroup_edit_inline'),
    url(r'^(?P<gid>\d+)/members/(?P<cid>\d+)/remove$', 'ngw.core.views.contactingroup_delete'),
    url(r'^add_contacts_to$', 'ngw.core.views.contactgroup_add_contacts_to'),
    url(r'^(?P<gid>\d+)/news/$', 'ngw.core.views.contactgroup_news'),
    url(r'^(?P<gid>\d+)/files(?P<path>.+)$', 'ngw.core.views.contactgroup_files'),
    url(r'^(?P<gid>\d+)/messages$', 'ngw.core.views.contactgroup_messages'),
    url(r'^(?P<gid>\d+)/news/add$', 'ngw.core.views.contactgroup_news_edit', {'nid':None}),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/edit$', 'ngw.core.views.contactgroup_news_edit'),
    url(r'^(?P<gid>\d+)/news/(?P<nid>\d+)/delete$', 'ngw.core.views.contactgroup_news_delete'),
    url(r'^(?P<id>\d+)/mailman$', 'ngw.core.views.contactgroup_mailman'),
)


js_info_dict = {
    'packages': ('ngw.core',),
    }

urlpatterns = patterns('',
    url(r'^$', 'ngw.core.views.home'),
    
    #url(r'^test$', 'ngw.core.views.test'),

    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog', js_info_dict),
    url(r'^jsi18n/(?P<packages>\S+?)/$', 'django.views.i18n.javascript_catalog'),

    url(r'session_security/', include('session_security.urls')),

    url(r'^hook_change_password$', 'ngw.core.views.hook_change_password'),

    url(r'^login$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^logout$', 'ngw.core.views.logout'),

    url(r'^logs$', 'ngw.core.views.logs'),

    url(r'^contacts/$', 'ngw.core.views.contact_list'),
    url(r'^contacts/add$', 'ngw.core.views.contact_edit', {'gid':None, 'cid':None}),
    url(r'^contacts/filter$', 'ngw.core.contactsearch.editfilter'),
    url(r'^contacts/search/fields/(?P<kind>\w+)$', 'ngw.core.contactsearch.contactsearch_get_fields'),
    url(r'^contacts/search/filters/(?P<field>\w+)$', 'ngw.core.contactsearch.contactsearch_get_filters'),
    url(r'^contacts/search/params/(?P<field>\w+)/(?P<filtername>\w+)$', 'ngw.core.contactsearch.contactsearch_get_params'),
    url(r'^contacts/search/filter_to_html$', 'ngw.core.contactsearch.contactsearch_filter_to_html'),
#    url(r'^contacts/make_login_mailing$', 'ngw.core.views.contact_make_login_mailing'),

    url(r'^contacts/(?P<cid>\d+)/$', 'ngw.core.views.contact_detail'),
    url(r'^contacts/(?P<cid>\d+)/edit$', 'ngw.core.views.contact_edit'),
    url(r'^contacts/(?P<cid>\d+)/pass$', 'ngw.core.views.contact_pass', { 'gid': None }),
    url(r'^contacts/(?P<cid>\d+)/pass_letter$', 'ngw.core.views.contact_pass_letter', { 'gid': None }),
    url(r'^contacts/(?P<cid>\d+)/delete$', 'ngw.core.views.contact_delete', { 'gid': None }),
    url(r'^contacts/(?P<cid>\d+)/vcard$', 'ngw.core.views.contact_vcard'),
    url(r'^contacts/(?P<cid>\d+)/filters/$', 'ngw.core.views.contact_filters_list'),
    url(r'^contacts/(?P<cid>\d+)/filters/add$', 'ngw.core.views.contact_filters_add'),
    url(r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/$', 'ngw.core.views.contact_filters_edit'),
    url(r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)/delete$', 'ngw.core.views.contact_filters_delete'),
    url(r'^contacts/(?P<cid>\d+)/default_group$', 'ngw.core.views.contact_default_group'),

    #url(r'^contactgroups2/$', ContactGroupList.as_view()),
    url(r'^contactgroups/$', 'ngw.core.views.contactgroup_list'),
    url(r'^contactgroups/', include(groups_urlpatterns)),
    url(r'^events/$', 'ngw.core.views.event_list'),
    url(r'^events/', include(groups_urlpatterns)),

    url(r'^contactfields/$', 'ngw.core.views.field_list'),
    url(r'^contactfields/add$', 'ngw.core.views.field_edit', {'id': None}),
    url(r'^contactfields/(?P<id>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^contactfields/(?P<id>\d+)/edit$', 'ngw.core.views.field_edit'),
    url(r'^contactfields/(?P<id>\d+)/moveup$', 'ngw.core.views.field_move_up'),
    url(r'^contactfields/(?P<id>\d+)/movedown$', 'ngw.core.views.field_move_down'),
    url(r'^contactfields/(?P<id>\d+)/delete$', 'ngw.core.views.field_delete'),

    url(r'^choicegroups/$', 'ngw.core.views.choicegroup_list'),
    url(r'^choicegroups/add$', 'ngw.core.views.choicegroup_edit', {'id': None}),
    url(r'^choicegroups/(?P<id>\d+)/$', RedirectView.as_view(url='edit')),
    url(r'^choicegroups/(?P<id>\d+)/edit$', 'ngw.core.views.choicegroup_edit'),
    url(r'^choicegroups/(?P<id>\d+)/delete$', 'ngw.core.views.choicegroup_delete'),

    url(r'^media/g/(?P<gid>\d+)/(?P<filename>.+)$', 'ngw.core.views.media_group_file'),

    url(r'^pks/lookup$', 'ngw.core.gpg.lookup'),

    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
