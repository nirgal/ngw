from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'ngw.gp.views.index'),

    (r'^test$', 'ngw.gp.views.test'),

    (r'^logout$', 'ngw.gp.views.logout'),

    (r'^logs$', 'ngw.gp.views.logs'),

    (r'^contacts/$', 'ngw.gp.views.contact_list'),
    (r'^contacts/add$', 'ngw.gp.views.contact_edit', {'id': None}),
    (r'^contacts/filter$', 'ngw.gp.contactsearch.editfilter'),
    (r'^contacts/search/fields/(?P<kind>\w+)$', 'ngw.gp.contactsearch.contactsearch_get_fields'),
    (r'^contacts/search/filters/(?P<field>\w+)$', 'ngw.gp.contactsearch.contactsearch_get_filters'),
    (r'^contacts/search/params/(?P<field>\w+)/(?P<filtername>\w+)$', 'ngw.gp.contactsearch.contactsearch_get_params'),
    (r'^contacts/search/filter_to_html$', 'ngw.gp.contactsearch.contactsearch_filter_to_html'),
    (r'^contacts/(?P<id>\d+)/$', 'ngw.gp.views.contact_detail'),
    (r'^contacts/(?P<id>\d+)/edit$', 'ngw.gp.views.contact_edit'),
    (r'^contacts/(?P<id>\d+)/pass$', 'ngw.gp.views.contact_pass'),
    (r'^contacts/(?P<id>\d+)/delete$', 'ngw.gp.views.contact_delete'),
    (r'^contacts/(?P<id>\d+)/vcard$', 'ngw.gp.views.contact_vcard'),

    (r'^contactgroups/$', 'ngw.gp.views.contactgroup_list'),
    (r'^contactgroups/add$', 'ngw.gp.views.contactgroup_edit', {'id': None}),
    (r'^contactgroups/(?P<id>\d+)/emails$', 'ngw.gp.views.contactgroup_emails'),
    (r'^contactgroups/(?P<id>\d+)/$', 'ngw.gp.views.contactgroup_detail'),
    (r'^contactgroups/(?P<id>\d+)/edit$', 'ngw.gp.views.contactgroup_edit'),
    (r'^contactgroups/(?P<id>\d+)/delete$', 'ngw.gp.views.contactgroup_delete'),
    (r'^contactgroups/(?P<gid>\d+)/remove/(?P<cid>\d+)$', 'ngw.gp.views.contactgroup_remove'),
    (r'^contactgroups/(?P<gid>\d+)/(?P<cid>\d+)$', 'ngw.gp.views.contactingroup_edit'),

    (r'^contactfields/$', 'ngw.gp.views.field_list'),
    (r'^contactfields/add$', 'ngw.gp.views.field_edit', {'id': None}),
    (r'^contactfields/(?P<id>\d+)/$', 'django.views.generic.simple.redirect_to', {'url': '/contactfields/%(id)s/edit'}),
    (r'^contactfields/(?P<id>\d+)/edit$', 'ngw.gp.views.field_edit'),
    (r'^contactfields/(?P<id>\d+)/moveup$', 'ngw.gp.views.field_move_up'),
    (r'^contactfields/(?P<id>\d+)/movedown$', 'ngw.gp.views.field_move_down'),
    (r'^contactfields/(?P<id>\d+)/delete$', 'ngw.gp.views.field_delete'),

    (r'^choicegroups/$', 'ngw.gp.views.choicegroup_list'),
    (r'^choicegroups/add$', 'ngw.gp.views.choicegroup_edit', {'id': None}),
    (r'^choicegroups/(?P<id>\d+)/$', 'django.views.generic.simple.redirect_to', {'url': '/choicegroups/%(id)s/edit'}),
    (r'^choicegroups/(?P<id>\d+)/edit$', 'ngw.gp.views.choicegroup_edit'),
    (r'^choicegroups/(?P<id>\d+)/delete$', 'ngw.gp.views.choicegroup_delete'),
)
