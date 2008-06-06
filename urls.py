from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^ngw/', include('ngw.apps.foo.urls.foo')),
    (r'^$', 'ngw.gp.views.index'),
    (r'^testquery_tables$', 'ngw.gp.views.testquery_tables'),
    (r'^testquery_entities$', 'ngw.gp.views.testquery_entities'),
    (r'^contacts/$', 'ngw.gp.views.contact_list'),
    (r'^contacts/add$', 'ngw.gp.views.contact_edit', {'id': None}),
    (r'^contacts/search$', 'ngw.gp.views.contact_search'),
    (r'^contacts/(?P<id>\d+)/edit$', 'ngw.gp.views.contact_edit'),
    (r'^contacts/(?P<id>\d+)/delete$', 'ngw.gp.views.contact_delete'),
    (r'^contactfields/$', 'ngw.gp.views.field_list'),
    (r'^contactfields/add$', 'ngw.gp.views.field_edit', {'id': None}),
    (r'^contactfields/(?P<id>\d+)/$', 'ngw.gp.views.field_edit'),
    (r'^contactfields/(?P<id>\d+)/edit$', 'ngw.gp.views.field_edit'),
    (r'^contactfields/(?P<id>\d+)/moveup$', 'ngw.gp.views.field_move_up'),
    (r'^contactfields/(?P<id>\d+)/movedown$', 'ngw.gp.views.field_move_down'),
    (r'^contactfields/(?P<id>\d+)/delete$', 'ngw.gp.views.field_delete'),
    (r'^contactgroups/$', 'ngw.gp.views.contactgroup_list'),
    (r'^contactgroups/add$', 'ngw.gp.views.contactgroup_edit', {'id': None}),
    (r'^contactgroups/(?P<id>\d+)/$', 'ngw.gp.views.contactgroup_detail'),
    (r'^contactgroups/(?P<id>\d+)/edit$', 'ngw.gp.views.contactgroup_edit'),
    (r'^contactgroups/(?P<id>\d+)/delete$', 'ngw.gp.views.contactgroup_delete'),
    (r'^choicegroups/$', 'ngw.gp.views.choicegroup_list'),
    (r'^choicegroups/add$', 'ngw.gp.views.choicegroup_edit', {'id': None}),
    (r'^choicegroups/(?P<id>\d+)/edit$', 'ngw.gp.views.choicegroup_edit'),
    (r'^choicegroups/(?P<id>\d+)/delete$', 'ngw.gp.views.choicegroup_delete'),

    # Uncomment this for admin:
    #(r'^admin/', include('django.contrib.admin.urls')),
)
