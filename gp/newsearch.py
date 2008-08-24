# -*- encoding: utf-8 -*-

from django.http import *
from django.utils.safestring import mark_safe
from ngw.gp.views import *
from ngw.gp.alchemy_models import *

def no_br(txt):
    return txt.replace(u" ", unichr(160))

def format_link_list(l):
    # list is a 3-tupple ( url, display name, dom_id )
    return (unichr(160)+u"| ").join(
        [ u'<a href="%(url)s" id="%(dom_id)s">%(name)s</a>\n' % {'url':url, 'name':name, 'dom_id':dom_id }
          for url,name,dom_id in l])

@http_authenticate(ngw_auth, 'ngw')
def testsearch(request):
    if not request.user.is_admin():
        return unauthorized(request)
    
    params = request.META['QUERY_STRING'] or ''
    params = u"field1_gt=2&name_startswith=lai"

    body = u""
    body += params

    args={}
    args["title"] = "Contact search"
    args["objtype"] = Contact
    args["message"] = mark_safe(body)
    return render_to_response('search_contact_new.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def testsearch_get_fields(request, kind):
    if not request.user.is_admin():
        return unauthorized(request)
    
    body = u""
    if kind==u"field":
        body += u"Add a field: "
        body += format_link_list([(u"javascript:select_field('name')", u"Name", u"field_name")]+[ (u"javascript:select_field('field_"+unicode(cf.id)+"')", no_br(name_internal2nice(cf.name)), u"field_field_"+unicode(cf.id)) for cf in Query(ContactField).order_by(ContactField.c.sort_weight)])
    elif kind==u"group":
        body += u"Add a group: "
        body += format_link_list([ (u"javascript:select_field('group_"+unicode(cg.id)+"')", no_br(cg.unicode_with_date()), u"field_group_"+unicode(cg.id)) for cg in Query(ContactGroup).filter(ContactGroup.c.date==None)])

    elif kind==u"event":
        body += u"Add an event: "
        body += format_link_list([ (u"javascript:select_field('group_"+unicode(cg.id)+"')", no_br(cg.unicode_with_date()), u"field_group_"+unicode(cg.id)) for cg in Query(ContactGroup).filter(ContactGroup.c.date!=None)])
    else:
        body += u"ERROR in get_fields: kind=="+kind
    return HttpResponse(body)

@http_authenticate(ngw_auth, 'ngw')
def testsearch_get_filters(request, field):
    if not request.user.is_admin():
        return unauthorized(request)
    
    body = u""
    if field == u"name":
        body+=u"testsearch_get_filters NOT IMPLEMENTED for field=name"

    elif field.startswith(u"field_"):
        field_id = int(field[len(u"field_"):])
        field = Query(ContactField).get(field_id)
        body+=u"Not implemented: Fetching filters from type "+field.human_type_id

    elif field.startswith(u"group_"):
        group_id = int(field[len(u"group_"):])
        group = Query(ContactGroup).get(group_id)
        body+=u"testsearch_get_filters NOT IMPLEMENTED for field="+field

    else:
        body+=u"ERROR in get_filters: field=="+field
    
    body+=u"<br>"
    body+=u"<a href=#>Add this filter</a>"
    return HttpResponse(body)
