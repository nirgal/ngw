from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'ngw.core.views.index'),

    #(r'^test$', 'ngw.core.views.test'),

    (r'^logout$', 'ngw.core.views.logout'),

    (r'^logs$', 'ngw.core.views.logs'),

    (r'^contacts/$', 'ngw.core.views.contact_list'),
    (r'^contacts/add$', 'ngw.core.views.contact_edit', {'gid':None, 'cid':None}),
    (r'^contacts/filter$', 'ngw.core.contactsearch.editfilter'),
    (r'^contacts/search/fields/(?P<kind>\w+)$', 'ngw.core.contactsearch.contactsearch_get_fields'),
    (r'^contacts/search/filters/(?P<field>\w+)$', 'ngw.core.contactsearch.contactsearch_get_filters'),
    (r'^contacts/search/params/(?P<field>\w+)/(?P<filtername>\w+)$', 'ngw.core.contactsearch.contactsearch_get_params'),
    (r'^contacts/search/filter_to_html$', 'ngw.core.contactsearch.contactsearch_filter_to_html'),

    (r'^contacts/(?P<cid>\d+)/$', 'ngw.core.views.contact_detail'),
    (r'^contacts/(?P<cid>\d+)/edit$', 'ngw.core.views.contact_edit'),
    (r'^contacts/(?P<cid>\d+)/pass$', 'ngw.core.views.contact_pass', { 'gid': None }),
    (r'^contacts/(?P<cid>\d+)/delete$', 'ngw.core.views.contact_delete', { 'gid': None }),
    (r'^contacts/(?P<cid>\d+)/vcard$', 'ngw.core.views.contact_vcard'),
    (r'^contacts/(?P<cid>\d+)/filters/$', 'ngw.core.views.contact_filters_list'),
    (r'^contacts/(?P<cid>\d+)/filters/add$', 'ngw.core.views.contact_filters_add'),
    (r'^contacts/(?P<cid>\d+)/filters/(?P<fid>\d+)$', 'ngw.core.views.contact_filters_edit'),

    (r'^contactgroups/$', 'ngw.core.views.contactgroup_list'),
    (r'^contactgroups/add$', 'ngw.core.views.contactgroup_edit', {'id': None}),
    (r'^contactgroups/(?P<id>\d+)/$', 'ngw.core.views.contactgroup_detail'),
    (r'^contactgroups/(?P<id>\d+)/edit$', 'ngw.core.views.contactgroup_edit'),
    (r'^contactgroups/(?P<id>\d+)/delete$', 'ngw.core.views.contactgroup_delete'),
    (r'^contactgroups/(?P<gid>\d+)/members/$', 'ngw.core.views.contactgroup_members'),
    (r'^contactgroups/(?P<gid>\d+)/members/vcards$', 'ngw.core.views.contactgroup_members', {'output_format': 'vcards'}),
    (r'^contactgroups/(?P<gid>\d+)/members/emails$',  'ngw.core.views.contactgroup_members', {'output_format': 'emails'}),
    (r'^contactgroups/(?P<gid>\d+)/members/add$', 'ngw.core.views.contact_edit', {'cid':None}),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/$', 'ngw.core.views.contact_detail'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/vcard$', 'ngw.core.views.contact_vcard'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/edit$', 'ngw.core.views.contact_edit'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/pass$', 'ngw.core.views.contact_pass'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/delete$', 'ngw.core.views.contact_delete'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/membership$', 'ngw.core.views.contactingroup_edit'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/membershipinline$', 'ngw.core.views.contactingroup_edit_inline'),
    (r'^contactgroups/(?P<gid>\d+)/members/(?P<cid>\d+)/remove$', 'ngw.core.views.contactingroup_delete'),
    (r'^contactgroups/add_contacts_to$', 'ngw.core.views.contactgroup_add_contacts_to'),

    (r'^contactgroups/(?P<gid>\d+)/news/$', 'ngw.core.views.contactgroup_news'),
    (r'^contactgroups/(?P<gid>\d+)/news/add$', 'ngw.core.views.contactgroup_news_edit', {'nid':None}),
    (r'^contactgroups/(?P<gid>\d+)/news/(?P<nid>\d+)/$', 'django.views.generic.simple.redirect_to', {'url': '/contactgroups/%(gid)s/news/%(nid)s/edit'}),
    (r'^contactgroups/(?P<gid>\d+)/news/(?P<nid>\d+)/edit$', 'ngw.core.views.contactgroup_news_edit'),
    (r'^contactgroups/(?P<gid>\d+)/news/(?P<nid>\d+)/delete$', 'ngw.core.views.contactgroup_news_delete'),

    (r'^contactfields/$', 'ngw.core.views.field_list'),
    (r'^contactfields/add$', 'ngw.core.views.field_edit', {'id': None}),
    (r'^contactfields/(?P<id>\d+)/$', 'django.views.generic.simple.redirect_to', {'url': '/contactfields/%(id)s/edit'}),
    (r'^contactfields/(?P<id>\d+)/edit$', 'ngw.core.views.field_edit'),
    (r'^contactfields/(?P<id>\d+)/moveup$', 'ngw.core.views.field_move_up'),
    (r'^contactfields/(?P<id>\d+)/movedown$', 'ngw.core.views.field_move_down'),
    (r'^contactfields/(?P<id>\d+)/delete$', 'ngw.core.views.field_delete'),

    (r'^choicegroups/$', 'ngw.core.views.choicegroup_list'),
    (r'^choicegroups/add$', 'ngw.core.views.choicegroup_edit', {'id': None}),
    (r'^choicegroups/(?P<id>\d+)/$', 'django.views.generic.simple.redirect_to', {'url': '/choicegroups/%(id)s/edit'}),
    (r'^choicegroups/(?P<id>\d+)/edit$', 'ngw.core.views.choicegroup_edit'),
    (r'^choicegroups/(?P<id>\d+)/delete$', 'ngw.core.views.choicegroup_delete'),

    (r'^pks/lookup$', 'ngw.core.gpg.lookup'),
)
