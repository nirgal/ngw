# -*- encoding: utf8 -*-

import os, copy, traceback, time, subprocess
from md5 import md5
from sha import sha
from random import random
from base64 import b64encode
from django.http import *
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django import forms
from django.shortcuts import render_to_response
from django.template import loader, RequestContext
from ngw import settings
from ngw.core.alchemy_models import *
from ngw.core.basicauth import *

DISP_NAME = u'name'
DISP_FIELD_PREFIX = u'field_'
DISP_GROUP_PREFIX = u'group_'
NB_LINES_PER_PAGE=200

FTYPE_TEXT='TEXT'
FTYPE_LONGTEXT='LONGTEXT'
FTYPE_NUMBER='NUMBER'
FTYPE_DATE='DATE'
FTYPE_EMAIL='EMAIL'
FTYPE_PHONE='PHONE'
FTYPE_RIB='RIB'
FTYPE_CHOICE='CHOICE'
FTYPE_MULTIPLECHOICE='MULTIPLECHOICE'
FTYPE_PASSWORD='PASSWORD'


def ngw_auth(username, passwd):
    username = unicode(username, 'utf-8', 'replace')
    passwd = unicode(passwd, 'utf-8', 'replace')
    if not username or not passwd:
        return None
    login_value = Query(ContactFieldValue).filter(ContactFieldValue.c.contact_field_id==1).filter(ContactFieldValue.c.value==username).first()
    if not login_value:
        return None
    c = login_value.contact
    dbpasswd=Query(ContactFieldValue).get((c.id, 2)).value
    if not dbpasswd:
        return None
    if dbpasswd.startswith(u"{SHA}"):
        digest = dbpasswd[5:]
        if b64encode(sha(passwd).digest())==digest:
            c.update_lastconnection()
            return c
    else: # assume crypt algorithm
        salt,digest = dbpasswd[0:2],dbpasswd[2:]
        targetdigest=subprocess.Popen(["openssl", "passwd", "-crypt", "-salt", salt, passwd], stdout=subprocess.PIPE).communicate()[0]
        targetdigest=targetdigest[:-1] # remove extra "\n"
        if salt+digest==targetdigest:
            c.update_lastconnection()
            return c
    #algo, salt, digest = dbpasswd.split('$')
    #if algo=="crypt":
    #elif algo=="md5":
    #    if md5(salt+passwd).hexdigest()==digest:
    #        return c
    #elif algo=="sha1":
    #    if sha(salt+passwd).hexdigest()==digest:
    #        return c
    #else:
    #    print "Unsupported password algorithm", algo.encode('utf-8')
    #    return None
    return None # authentification failed


class navbar(object):
    def __init__(self, *args):
        self.components = [ (u"", u"Home") ]
        for arg in args:
            self.add_component(arg)

    def add_component(self, arg):
        if isinstance(arg, tuple):
            self.components.append(arg)
        else:
            assert isinstance(arg, unicode)
            self.components.append((arg,arg))
        
    def geturl(self, idx):
        return u"".join(self.components[i][0]+u"/" for i in range(idx+1))

    def getfragment(self, idx):
        result = u""
        if idx!=len(self.components)-1:
            result += u"<a href=\""+self.geturl(idx)+"\">"
        result += html.escape(self.components[idx][1])
        if idx!=len(self.components)-1:
            result += u"</a>"
        return result

    def __unicode__(self):
        return u" › ".join([self.getfragment(i) for i in range(len(self.components)) ])


def get_display_fields(user):
    # check the field still exists
    result = []
    default_fields = user.get_fieldvalue_by_id(FIELD_COLUMNS)
    if not default_fields:
        default_fields = Query(Config).get('columns')
        if default_fields:
            default_fields = default_fields.text
    if not default_fields:
        default_fields = u""
    for fname in default_fields.split(u','):
        if fname==u'name':
            pass
        elif fname.startswith(DISP_GROUP_PREFIX):
            try:
                groupid = int(fname[len(DISP_GROUP_PREFIX):])
            except ValueError:
                print "Error in default fields: %s has invalid syntax." % fname.encode('utf8')
                continue
            if not Query(ContactGroup).get(groupid):
                print "Error in default fields: There is no group #%d." % groupid
                continue
        elif fname.startswith(DISP_FIELD_PREFIX):
            try:
                fieldid = int(fname[len(DISP_FIELD_PREFIX):])
            except ValueError:
                print "Error in default fields: %s has invalid syntax." % fname.encode('utf8')
                continue
            if not Query(ContactField).get(fieldid):
                print "Error in default fields: There is no field #%d." % fieldid
                continue
        else:
            print "Error in default fields: Invalid syntax in \"%s\"." % fname.encode('utf8')
            continue
        result.append(fname)
    if not result:
        result = [ DISP_NAME ]
    return result


def unauthorized(request):
    return HttpResponseForbidden(
        loader.render_to_string('message.html',{
            'message': "Sorry. You are not authorized to browse that page."},
            RequestContext(request)))


@http_authenticate(ngw_auth, 'ngw')
def index(request):
    # Birthdates: select contact_id, substring(value from 6) as md from contact_field_value where contact_field_id=6 order by md;
    operator_groups_ids = [ cig.group_id for cig in Query(ContactInGroup).filter(ContactInGroup.contact_id==request.user.id).filter(ContactInGroup.operator==True) ]
    operator_groups = Query(ContactGroup).filter(ContactGroup.id.in_(operator_groups_ids)).order_by(ContactGroup.name)
    return render_to_response('index.html', {
        'nav': navbar(),
        'title':'Action DB',
        'ncontacts': Query(Contact).count(),
        'operator_groups': operator_groups,
        'news': Query(ContactGroupNews).filter(ContactGroupNews.contact_group_id==GROUP_ADMIN).order_by(desc(ContactGroupNews.date)).limit(5)
    }, RequestContext(request))

# Helper function that is never call directly, hence the lack of authentification check
def generic_delete(request, o, next_url, base_nav=None, ondelete_function=None):
    if not request.user.is_admin():
        return unauthorized(request)

    title = u"Please confirm deletetion"

    if not o:
        raise Http404()

    confirm = request.GET.get("confirm", u"")
    if confirm:
        if ondelete_function:
            ondelete_function(o)
        name = unicode(o)
        Session.delete(o)
        request.user.push_message("%s has been deleted sucessfully!"%name)
        log = Log(request.user.id)
        log.action = LOG_ACTION_DEL
        pk = o._instance_key[1] # this is a tuple
        log.target = unicode(o.__class__.__name__)+u" "+u" ".join([unicode(x) for x in pk])
        log.target_repr = o.get_class_verbose_name()+u" "+name
        return HttpResponseRedirect(next_url)
    else:
        nav = base_nav or navbar(o.get_class_navcomponent())
        nav.add_component(o.get_navcomponent())
        nav.add_component(u"delete")
        return render_to_response('delete.html', {'title':title, 'o': o, 'nav': nav}, RequestContext(request))
        

class FilterMultipleSelectWidget(forms.SelectMultiple):
    class Media:
        js = ('ngw.js',)

    def __init__(self, verbose_name, is_stacked, attrs=None, choices=()):
        self.verbose_name = verbose_name
        self.is_stacked = is_stacked
        super(FilterMultipleSelectWidget, self).__init__(attrs, choices)

    def render(self, name, value, attrs=None, choices=()):
        output = [super(FilterMultipleSelectWidget, self).render(name, value, attrs, choices)]
        output.append(u'<script type="text/javascript">addEvent(window, "load", function(e) {')
        # TODO: "id_" is hard-coded here. This should instead use the correct
        # API to determine the ID dynamically.
        output.append(u'SelectFilter.init("id_%s", "%s", %s, "%s"); });</script>\n' % \
            (name, self.verbose_name.replace(u'"', u'\\"'), int(self.is_stacked), settings.MEDIA_URL+settings.ADMIN_MEDIA_PREFIX))
        return mark_safe(u''.join(output))



def query_print_entities(request, template_name, args):
    q = args['query']
    cols = args['cols']

    # get sort column name
    order = request.REQUEST.get("_order", 0)
    try:
        intorder=int(order)
    except ValueError:
        intorder = 0

    sort_col = cols[abs(intorder)][3]
    if not order or order[0]!="-":
        q = q.order_by(sort_col)
    else:
        q = q.order_by(sort_col.desc())

    totalcount = q.count()

    page = request.REQUEST.get("_page", 1)
    try:
        page=int(page)
    except ValueError:
        page = 1
    q = q.limit(NB_LINES_PER_PAGE)
    q = q.offset(NB_LINES_PER_PAGE*(page-1))

    args['query'] = q
    args['cols'] = cols
    args['order'] = order
    args['count'] = totalcount
    args['page'] = page
    args['npages'] = (totalcount+NB_LINES_PER_PAGE-1)/NB_LINES_PER_PAGE

    if not args.has_key("baseurl"):
        args["baseurl"]="?"
    return render_to_response(template_name, args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def test(request):
    args={
        "title": "Test",
        "env": os.environ,
        "MEDIA_URL": settings.MEDIA_URL,
        "objtype": Contact,
    }
    #raise Exception(u"Boum")
    return render_to_response("test.html", args, RequestContext(request))

def logout(request):
    if os.environ.has_key('HTTPS'):
        scheme = "https"
    else:
        scheme = "http"
    return render_to_response("message.html", {"message": mark_safe("Have a nice day!<br><a href=\""+scheme+"://"+request.META["HTTP_HOST"]+"/\">Login again</a>") }, RequestContext(request))

#######################################################################
#
# Logs
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def logs(request):
    if not request.user.is_admin():
        return unauthorized(request)

    args={}
    args['title'] = "Global log"
    args['nav'] = navbar(Log.get_class_navcomponent())
    args['objtype'] = Log
    args['query'] = Query(Log)
    args['cols'] = [
        ( "Date GMT", None, "small_date", Log.c.dt),
        ( "User", None, "contact", Log.c.contact_id),
        ( "Action", None, "action_txt", Log.c.action),
        ( "Target", None, "target_repr", Log.c.target_repr),
        ( "Property", None, "property_repr", Log.c.property_repr),
        ( "Change", None, "change", Log.c.change),
    ]
    return query_print_entities(request, 'list_log.html', args)

#######################################################################
#
# Contacts
#
#######################################################################

def str_member_of_factory(contact_group):
    gids = [ g.id for g in contact_group.self_and_subgroups ]
    return lambda c: c.str_member_of(gids)
def str_action_of_factory(contact_group):
    gids = [ g.id for g in contact_group.self_and_subgroups ]
    return lambda c: u"<a href=\""+contact_group.get_absolute_url()+u"members/"+unicode(c.id)+u"/membership\">"+c.str_member_of(gids)+u"</a>"

def contact_make_query_with_fields(fields, current_cg=None):
    q = Query(Contact)
    n_entities = 1
    j = contact_table
    cols=[]
    
    for prop in fields:
        if prop==u"name":
            cols.append( (u"Name", 0, "name_with_relative_link", contact_table.c.name) )
        elif prop.startswith(DISP_GROUP_PREFIX):
            groupid = int(prop[len(DISP_GROUP_PREFIX):])
            cg = Query(ContactGroup).get(groupid)
            cols.append( (cg.name, 0, str_member_of_factory(cg), None) )
        elif prop.startswith(DISP_FIELD_PREFIX):
            fieldid = int(prop[len(DISP_FIELD_PREFIX):])
            cf = Query(ContactField).get(fieldid)
            a = contact_field_value_table.alias()
            q = q.add_entity(ContactFieldValue, alias=a)
            j = outerjoin(j, a, and_(contact_table.c.id==a.c.contact_id, a.c.contact_field_id==cf.id ))
            cols.append( (cf.name, n_entities, "as_html", a.c.value) )
            n_entities += 1
        else:
            raise ValueError(u"Invalid field "+prop)

    if current_cg is not None:
        cols.append( ("Status", 0, str_action_of_factory(current_cg), None) )
        
    q = q.select_from(j)
    return q, cols


def get_available_fields():
    result = [ (DISP_NAME, u'Name') ]
    for cf in Query(ContactField).order_by(ContactField.c.sort_weight):
        result.append((DISP_FIELD_PREFIX+unicode(cf.id), cf.name))
    for cg in Query(ContactGroup):
        result.append((DISP_GROUP_PREFIX+unicode(cg.id), cg.unicode_with_date()))
    return result


class FieldSelectForm(forms.Form):
    def __init__(self, *args, **kargs):
        #TODO: param user -> fine tuned fields selection
        forms.Form.__init__(self, *args, **kargs)
        self.fields[u'selected_fields']=forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("Fields", False), choices=get_available_fields())


@http_authenticate(ngw_auth, 'ngw')
def contact_list(request):
    import contactsearch # FIXME
    if not request.user.is_admin():
        return unauthorized(request)

    strfilter = request.REQUEST.get(u'filter', u'')
    filter = contactsearch.parse_filterstring(strfilter)
    baseurl=u'?filter='+strfilter

    strfields = request.REQUEST.get(u'fields', None)
    if strfields:
        fields = strfields.split(u',')
        baseurl+='&fields='+strfields
    else:
        fields = get_display_fields(request.user)
        strfields = u",".join(fields)
   
    if (request.REQUEST.get(u'savecolumns')):
        request.user.set_fieldvalue(request.user, FIELD_COLUMNS, strfields)

    #print "contact_list:", fields
    q, cols = contact_make_query_with_fields(fields)
    q = filter.apply_filter_to_query(q)

    args={}
    args['title'] = u"Contact list"
    args['baseurl'] = baseurl
    args['objtype'] = Contact
    args['nav'] = navbar(args['objtype'].get_class_absolute_url().split(u'/')[1])
    args['query'] = q
    args['cols'] = cols
    args['filter'] = strfilter
    args['fields'] = strfields
    args['fields_form'] = FieldSelectForm(initial={u'selected_fields': fields})

    return query_print_entities(request, 'list_contact.html', args)




@http_authenticate(ngw_auth, 'ngw')
def contact_detail(request, gid=None, cid=None):
    cid = int(cid)
    if cid!=request.user.id and not request.user.is_admin():
        return unauthorized(request)
    c = Query(Contact).get(cid)
    rows = []
    for cf in c.get_allfields():
        cfv = Query(ContactFieldValue).get((cid, cf.id))
        if cfv:
            rows.append((cf.name, mark_safe(cfv.as_html())))
    
    is_admin = c.is_admin()
    args={}
    args['title'] = u"Details for "+unicode(c)
    if gid:
        cg = Query(ContactGroup).get(gid)
        args['nav'] = navbar(ContactGroup.get_class_navcomponent(), cg.get_navcomponent(), u"members")
    else:
        args['nav'] = navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(c.get_navcomponent())
    args['objtype'] = Contact
    args['contact'] = c
    args['rows'] = rows
    return render_to_response('contact_detail.html', args, RequestContext(request))



@http_authenticate(ngw_auth, 'ngw')
def contact_vcard(request, gid=None, cid=None):
    cid = int(cid)
    if cid!=request.user.id and not request.user.is_admin():
        return unauthorized(request)
    c = Query(Contact).get(cid)
    return HttpResponse(c.vcard().encode("utf-8"), mimetype="text/x-vcard")




class ContactEditForm(forms.Form):
    name = forms.CharField()

    def __init__(self, request_user, id=None, contactgroup=None, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        contactid = id # FIXME

        if contactid:
            contact = Query(Contact).get(contactid)
            contactgroupids = [ g.id for g in contact.get_allgroups_withfields()] 
        elif contactgroup:
            contactgroupids = [ g.id for g in contactgroup.self_and_supergroups ] 
        else:
            contactgroupids = [ ]

        # Add all extra fields
        for cf in Query(ContactField).order_by(ContactField.c.sort_weight):
            if cf.contact_group_id:
                if cf.contact_group_id not in contactgroupids:
                    continue # some fields are excluded
            fields = cf.get_form_fields()
            if fields:
                self.fields[unicode(cf.id)] = fields
        
        if request_user.is_admin():
            # sql "_" means "any character" and must be escaped: g in Query(ContactGroup).filter(not_(ContactGroup.c.name.startswith("\\_"))).order_by ...
            contactgroupchoices = [ (g.id, g.unicode_with_date()) for g in Query(ContactGroup).order_by([ContactGroup.c.date.desc(), ContactGroup.c.name]) ]
            self.fields['groups'] = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("Group", False), choices=contactgroupchoices)
        

@http_authenticate(ngw_auth, 'ngw')
def contact_edit(request, gid=None, cid=None):
    if cid: # edit existing contact
        cid = int(cid)
        if cid!=request.user.id and not request.user.is_admin():
            return unauthorized(request)
    else: # add
        if not request.user.is_admin():
            return unauthorized(request)
 
    if gid: # edit/add in a group
        gid = int(gid)
        cg = Query(ContactGroup).get(gid)
    else: # edit out of a group
        cg = None

    objtype = Contact;
    if cid:
        contact = Query(Contact).get(cid)
        title = u"Editing "+unicode(contact)
    else:
        title = u"Adding a new "+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactEditForm(id=cid, data=request.POST, contactgroup=cg, request_user=request.user) # FIXME
        if form.is_valid():
            data = form.clean()
            # print "saving", repr(form.data)

            # record the values

            # 1/ In contact
            if cid:
                contactgroupids = [ g.id for g in contact.get_allgroups_withfields()]  # Need to keep a record of initial groups
                if contact.name != data['name']:
                    log = Log(request.user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = u"Contact "+unicode(contact.id)
                    log.target_repr = u"Contact "+contact.name
                    log.property = u"Name"
                    log.property_repr = u"Name"
                    log.change = u"change from "+contact.name+u" to "+data['name']

                contact.name = data['name']
            else:
                contact = Contact(data['name'])
                Session.flush()
                log = Log(request.user.id)
                log.action = LOG_ACTION_ADD
                log.target = u"Contact "+unicode(contact.id)
                log.target_repr = u"Contact "+contact.name

                log = Log(request.user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u"Contact "+unicode(contact.id)
                log.target_repr = u"Contact "+contact.name
                log.property = u"Name"
                log.property_repr = u"Name"
                log.change = u"new value is "+contact.name

                if cg:
                    contactgroupids = [ g.id for g in cg.self_and_supergroups ]
                else:
                    contactgroupids = [ ]

            if request.user.is_admin():
                newgroups = data.get('groups', [])
                registeredgroups = []
                for new_gid in newgroups:
                    cig = Query(ContactInGroup).get((contact.id, new_gid))
                    if cig==None: # Was not a member
                        cig = ContactInGroup(contact.id, new_gid)
                        cig.member = True
                    registeredgroups.append(new_gid)
                for cig in Query(ContactInGroup).filter(and_(ContactInGroup.c.contact_id==cid, not_(ContactInGroup.c.group_id.in_(registeredgroups)))):
                    # TODO optimize me
                    print "Deleting", cig
                    Session.delete(cig)
                #print "newgroups =", newgroups
                #contact.direct_groups = newgroups
            
            # 2/ In ContactFields
            for cf in Query(ContactField):
                if cf.contact_group_id and cf.contact_group_id not in contactgroupids or cf.type==FTYPE_PASSWORD:
                    continue
                cfname = cf.name
                cfid = cf.id
                newvalue = data[unicode(cfid)]
                if newvalue!=None:
                    newvalue = cf.formfield_value_to_db_value(newvalue)
                contact.set_fieldvalue(request.user, cf, newvalue)
            request.user.push_message(u"Contact %s has been saved sucessfully!" % contact.name)
                
            if not cid:
                Session.commit() # We need the id rigth now!

            if cg:
                base_url=cg.get_absolute_url()+u"members/"+unicode(contact.id)+u"/"
            else:
                base_url=contact.get_class_absolute_url()

            if request.POST.get("_continue", None):
                return HttpResponseRedirect(base_url+u"edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect(base_url+u"../add")
            else:
                return HttpResponseRedirect(base_url)
        # else add/update failed validation
    else: # GET /  HEAD
        initialdata = {}
        if cid: # modify existing
            initialdata['groups'] = [ group.id for group in contact.get_directgroups_member() ]
            initialdata['name'] = contact.name

            for cfv in contact.values:
                cf = cfv.field
                if cf.type != FTYPE_PASSWORD:
                    initialdata[unicode(cf.id)] = cf.db_value_to_formfield_value(cfv.value)
            form = ContactEditForm(id=cid, initial=initialdata, request_user=request.user, contactgroup=cg)

        else:
            if cg:
                initialdata['groups'] = [ cg.id ]
                form = ContactEditForm(id=cid, initial=initialdata, contactgroup=cg, request_user=request.user)
            else:
                form = ContactEditForm(id=cid, request_user=request.user)

    args={}
    args['form'] = form
    args['title'] = title
    args['id'] = cid
    args['objtype'] = objtype
    if gid:
        args['nav'] = navbar(ContactGroup.get_class_navcomponent(), cg.get_navcomponent(), u"members")
    else:
        args['nav'] = navbar(Contact.get_class_navcomponent())
    if cid:
        args['nav'].add_component(contact.get_navcomponent())
        args['nav'].add_component(u"edit")
    else:
        args['nav'].add_component(u"add")
    if cid:
        args['o'] = contact

    return render_to_response('edit.html', args, RequestContext(request))
    

class ContactPasswordForm(forms.Form):
    new_password = forms.CharField(max_length=50, widget=forms.PasswordInput())
    confirm_password = forms.CharField(max_length=50, widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', u'') != self.cleaned_data.get('confirm_password', u''):
            raise forms.ValidationError("The passwords must match!")
        return self.cleaned_data


@http_authenticate(ngw_auth, 'ngw')
def contact_pass(request, gid=None, cid=None):
    if gid is not None:
        gid = int(gid)
    cid = int(cid)
    if cid!=request.user.id and not request.user.is_admin():
        return unauthorized(request)
    contact = Query(Contact).get(cid)
    args={}
    args['title'] = "Change password"
    args['contact'] = contact
    if request.method == 'POST':
        form = ContactPasswordForm(request.POST)
        if form.is_valid():
            # record the value
            password = form.clean()['new_password']
            hash=subprocess.Popen(["openssl", "passwd", "-crypt", password], stdout=subprocess.PIPE).communicate()[0]
            hash=hash[:-1] # remove extra "\n"
            cfv = Query(ContactFieldValue).get((contact.id, 2))
            if not cfv:
                cfv = ContactFieldValue()
                cfv.contact_id = contact.id
                cfv.contact_field_id = 2
            cfv.value = hash
            #hash = b64encode(sha(password).digest())
            #contact.passwd = "{SHA}"+hash
            request.user.push_message("Password has been changed sucessfully!")
            if gid:
                cg = Query(ContactGroup).get(gid)
                return HttpResponseRedirect(cg.get_absolute_url()+u"members/"+unicode(cid)+u"/")
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else: # GET
        form = ContactPasswordForm()
    args['form'] = form
    if gid:
        cg = Query(ContactGroup).get(gid)
        args['nav'] = navbar(ContactGroup.get_class_navcomponent(), cg.get_navcomponent(), u"members")
    else:
        args['nav'] = navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component(u"password")
    return render_to_response('password.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def contact_delete(request, gid=None, cid=None):
    if not request.user.is_admin():
        return unauthorized(request)
    o = Query(Contact).get(cid)
    if gid:
        next_url = Query(ContactGroup).get(gid).get_absolute_url()+u"members/"
    else:
        next_url = reverse('ngw.core.views.contact_list')
    if gid:
        cg = Query(ContactGroup).get(gid)
        base_nav = navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"members")
    else:
        base_nav = None
    return generic_delete(request, o, next_url, base_nav=base_nav)


@http_authenticate(ngw_auth, 'ngw')
def contact_filters_add(request, cid=None):
    from contactsearch import *
    if not request.user.is_admin():
        return unauthorized(request)
    contact = Query(Contact).get(cid)
    filter_str = request.GET['filterstr']
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if filter_list_str:
        filter_list = parse_filter_list_str(filter_list_str)
    else:
        filter_list = []
    filter_list.append((u'No name', filter_str))
    filter_list_str = u",".join([u'"'+name+u'","'+filterstr+u'"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request.user, FIELD_FILTERS, filter_list_str)
    request.user.push_message("Filter has been added sucessfully!")
    return HttpResponseRedirect(reverse('ngw.core.views.contact_filters_edit', args=(cid,len(filter_list)-1)))


@http_authenticate(ngw_auth, 'ngw')
def contact_filters_list(request, cid=None):
    from contactsearch import *
    if not request.user.is_admin():
        return unauthorized(request)
    contact = Query(Contact).get(cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    filters = []
    if filter_list_str:
        filter_list = parse_filter_list_str(filter_list_str)
        filters = [ (filtername,parse_filterstring(filter_str).to_html()) for (filtername,filter_str) in filter_list]
    args = {}
    args['title'] = u"User custom filters"
    args['contact'] = contact
    args['filters'] = filters
    args['nav'] = navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component((u"filters", u"custom filters"))
    return render_to_response('customfilters_user.html', args, RequestContext(request))


class FilterEditForm(forms.Form):
    name = forms.CharField(max_length=50)

@http_authenticate(ngw_auth, 'ngw')
def contact_filters_edit(request, cid=None, fid=None):
    from contactsearch import *
    if not request.user.is_admin():
        return unauthorized(request)
    contact = Query(Contact).get(cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if not filter_list_str:
        return HttpResponse(u"ERROR: no custom filter for that user")
    else:
        filter_list = parse_filter_list_str(filter_list_str)
    try:
        filtername,filterstr = filter_list[int(fid)]
    except IndexError, ValueError:
        return HttpResponse(u"ERROR: Can't find filter #"+fid)

    if request.method == 'POST':
        form = FilterEditForm(request.POST)
        if form.is_valid():
            #print repr(filter_list)
            #print repr(filter_list_str)
            filter_list[int(fid)]=(form.clean()['name'],filterstr)
            #print repr(filter_list)
            filter_list_str = u",".join([u'"'+name+u'","'+filterstr+u'"' for name, filterstr in filter_list])
            #print repr(filter_list_str)
            contact.set_fieldvalue(request.user, FIELD_FILTERS, filter_list_str)
            request.user.push_message("Filter has been renamed sucessfully!")
            return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else:
        form = FilterEditForm(initial={ 'name': filtername })
    args = {}
    args['title'] = u"User custom filter renaming"
    args['contact'] = contact
    args['form'] = form
    args['filtername'] = filtername
    args['filter_html'] = parse_filterstring(filterstr).to_html()
    args['nav'] = navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component((u"filters", u"custom filters"))
    args['nav'].add_component((unicode(fid), filtername))

    return render_to_response('customfilter_user.html', args, RequestContext(request))



#######################################################################
#
# Contact groups
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def contactgroup_list(request):
    if not request.user.is_admin():
        return unauthorized(request)
    def print_fields(cg):
        if cg.field_group:
            fields = cg.contact_fields
            if fields:
                return u", ".join(['<a href="'+f.get_absolute_url()+'">'+html.escape(f.name)+"</a>" for f in fields])
            else:
                return u"Yes (but none yet)"
        else:
            return u"No"

    q = Query(ContactGroup)
    cols = [
        ( u"Date", None, "date", contact_group_table.c.date ),
        ( u"Name", None, "name", contact_group_table.c.name ),
        ( u"Description", None, "description", contact_group_table.c.description ),
        ( u"Contact fields", None, print_fields, contact_group_table.c.field_group ),
        ( u"Super\u00a0groups", None, lambda cg: u", ".join([sg.name for sg in cg.direct_supergroups]), None ),
        ( u"Sub\u00a0groups", None, lambda cg: u", ".join([html.escape(sg.name) for sg in cg.direct_subgroups]), None ),
        ( u"Budget\u00a0code", None, "budget_code", contact_group_table.c.budget_code ),
        #( "Members", None, lambda cg: str(len(cg.members)), None ),
    ]
    args={}
    args['title'] = "Select a contact group"
    args['query'] = q
    args['cols'] = cols
    args['objtype'] = ContactGroup
    args['nav'] = navbar(ContactGroup.get_class_navcomponent())
    return query_print_entities(request, 'list.html', args)


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_detail(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_members', args=(id,)))


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_members(request, gid):
    import contactsearch # FIXME
    if not request.user.is_admin():
        return unauthorized(request)

    strfilter = request.REQUEST.get(u'filter', u'')
    filter = contactsearch.parse_filterstring(strfilter)
    baseurl=u'?filter='+strfilter

    strfields = request.REQUEST.get(u'fields', None)
    if strfields:
        fields = strfields.split(u',')
        baseurl+='&fields='+strfields
    else:
        fields = get_display_fields(request.user)
        strfields = u",".join(fields)
   
    if (request.REQUEST.get(u'savecolumns')):
        request.user.set_fieldvalue(request.user, FIELD_COLUMNS, strfields)

    cg = Query(ContactGroup).get(gid)
    if not cg:
        raise Http404

    #print cg.direct_subgroups
    args={}
    args['fields_form'] = FieldSelectForm(initial={u'selected_fields': fields})
    q, cols = contact_make_query_with_fields(fields, cg)

    display=request.REQUEST.get(u"display", u"mg")
    args['title'] = u"Contacts of group "+cg.unicode_with_date()
    cig_conditions_flags = []
    if u"m" in display:
        cig_conditions_flags.append(u"member=True")
        args['display_member'] = 1
    if u"i" in display:
        cig_conditions_flags.append(u"invited=True")
        args['display_invited'] = 1
    if u"d" in display:
        cig_conditions_flags.append(u"declined_invitation=True")
        args['display_declined'] = 1
    if u"o" in display:
        cig_conditions_flags.append(u"operator=True")
        args['display_operator'] = 1

    if cig_conditions_flags:
        cig_conditions_flags = u" AND (%s)" % u" OR ".join(cig_conditions_flags)
    else:
        cig_conditions_flags = u" AND False" # display nothing

    if u"g" in display:
        cig_conditions_group = u"group_id IN (%s)" % u",".join([unicode(g.id) for g in cg.self_and_subgroups])
        args['display_subgroups'] = 1
    else:
        cig_conditions_group = u"group_id=%d" % cg.id

    q = q.filter(u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND '+cig_conditions_group+cig_conditions_flags+u')')

    if request.REQUEST.get("output", u"")==u"vcard":
        result=u""
        for row in q:
            contact = row[0]
            result += contact.vcard()
        return HttpResponse(result.encode("utf-8"), mimetype="text/x-vcard")

    baseurl += u"&display="+display
    q = filter.apply_filter_to_query(q)

    args['baseurl'] = baseurl
    args['display'] = display
    args['query'] = q
    args['cols'] = cols
    args['cg'] = cg
    args['dir'] = cg.static_folder()
    args['files'] = os.listdir(args['dir'])
    args['files'].remove('.htaccess')
    ####
    args['objtype'] = ContactGroup
    args['filter'] = strfilter
    args['fields'] = strfields
    ####
    args['nav'] = navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"members")
    return query_print_entities(request, 'group_detail.html', args)


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_emails(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = Query(ContactGroup).get(id)
    members = cg.members
    emails = []
    noemails = []
    for c in members:
        c_emails = c.get_fieldvalues_by_type(EmailContactField)
        if c_emails:
            emails.append((c, c_emails[0])) # only the first
        else:
            noemails.append(c)

    args = {}
    args['title'] = u"Emails for "+cg.name
    args['cg'] = cg
    args['emails'] = emails
    args['noemails'] = noemails
    args['nav'] = navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"members", u"emails")
    return render_to_response('emails.html', args, RequestContext(request))


class ContactGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(required=False, widget=forms.Textarea)
    field_group = forms.BooleanField(required=False, help_text=u"Does that group yield specific fields to its members?")
    date = forms.DateField(required=False, help_text=u"Use YYYY-MM-DD format.")
    budget_code = forms.CharField(required=False, max_length=10)
    #invited_members = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("contacts", False))
    direct_members = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("contacts", False))
    direct_subgroups = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("groups", False))

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        
        #self.fields['invited_members'].choices = [ (c.id, c.name) for c in Query(Contact).order_by([Contact.c.name]) ]
        self.fields['direct_members'].choices = [ (c.id, c.name) for c in Query(Contact).order_by([Contact.c.name]) ]
        self.fields['direct_subgroups'].choices = [ (g.id, g.unicode_with_date()) for g in Query(ContactGroup).order_by([ContactGroup.c.date, ContactGroup.c.name]) ]

    def flag_inherited_members(self, g):
        has_automembers = False
        choices = []
        members = g.members
        direct_members = g.get_direct_members()
        for c in Query(Contact).order_by(Contact.c.name):
            cname = c.name
            if c in members and c not in direct_members:
                cname += " "+AUTOMATIC_MEMBER_INDICATOR
                has_automembers = True
            choices.append( (c.id, cname) )

        self.fields['direct_members'].choices = choices
        if has_automembers:
            help_text = AUTOMATIC_MEMBER_INDICATOR + " = Automatic members from " + ", ".join([ sg.name+" ("+str(sg.get_direct_members().count())+")" for sg in g.subgroups ])
            self.fields['direct_members'].help_text = help_text


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_edit(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype= ContactGroup
    if id:
        cg = Query(ContactGroup).get(id)
        if not cg:
            raise Http404
        title = u"Editing "+unicode(cg)
    else:
        title = u"Adding a new "+objtype.get_class_verbose_name()
    
    if request.method == 'POST':
        form = ContactGroupForm(request.POST)
        if form.is_valid():
            # record the values

            if not id:
                cg = ContactGroup()
            data = form.clean()
            cg.name = data['name']
            cg.description = data['description']
            cg.field_group = data['field_group']
            cg.date = data['date']
            cg.budget_code = data['budget_code']
            
            # we need to add/remove people without destroying their flags
            #new_invited_ids = [ int(id) for id in data['invited_members']]
            new_member_ids = [ int(id) for id in data['direct_members']]
            #print "WANTED INVITED=", new_invited_ids
            print "WANTED MEMBERS=", new_member_ids
            #TODO
            for cid in new_member_ids:
                c = Query(Contact).get(cid)
                if not Query(ContactInGroup).get((c.id, cg.id)):
                    #print "ADDING", c.name, "(", c.id, ") to group"
                    cig = ContactInGroup(c.id, cg.id)
                    cig.member = True

            # Search members to remove:
            for cig in Query(ContactInGroup).filter(ContactInGroup.c.group_id==cg.id):
                c = cig.contact
                print "Considering", c.name.encode('utf-8')
                if c.id not in new_member_ids:
                    print "REMOVING", c.name.encode('utf-8'), "(", c.id, ") from group:", c.id, "not in", new_member_ids
                    Session.delete(cig)

            old_direct_subgroups = cg.direct_subgroups
            old_direct_subgroups_ids = [ g.id for g in old_direct_subgroups ] # TODO: fine a better algo!
            new_direct_subgroups_id = data['direct_subgroups']

            # subgroups have no properties: just recreate the array with brute force
            cg.direct_subgroups = [ Query(ContactGroup).get(id) for id in new_direct_subgroups_id]
            request.user.push_message(u"Group %s has been changed sucessfully!" % cg.name)

            for subid in old_direct_subgroups_ids:
                if subid not in new_direct_subgroups_id:
                    # that subgroups no longer is a subgroups
                    subcg = Query(ContactGroup).get(subid)
                    if not subcg.direct_supergroups:
                        subcg.direct_supergroups = [ Query(ContactGroup).get(GROUP_EVERYBODY) ]

            if not cg.direct_supergroups:
                cg.direct_supergroups = [ Query(ContactGroup).get(GROUP_EVERYBODY) ]

            cg.check_static_folder_created()
            Session.commit()
            Contact.check_login_created(request.user)

            if request.POST.get("_continue", None):
                if not id:
                    Session.commit() # We need the id rigth now!
                return HttpResponseRedirect(cg.get_absolute_url()+u"edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect(cg.get_class_absolute_url()+u"add")
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_members', args=(cg.id,)))

    else: # GET
        if id:
            cg = Query(ContactGroup).get(id)
            initialdata = {
                'name': cg.name,
                'description': cg.description,
                'field_group': cg.field_group,
                'date': cg.date,
                'budget_code': cg.budget_code,
                'direct_members': [ c.id for c in cg.get_direct_members() ],
                'direct_subgroups': [ g.id for g in cg.direct_subgroups ],
            }
            
            form = ContactGroupForm(initialdata)
            form.flag_inherited_members(cg)
        else: # add new one
            form = ContactGroupForm()
    args={}
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    args['form'] = form
    if id:
        args['o'] = cg
    args['nav'] = navbar(ContactGroup.get_class_navcomponent())
    if id:
        args['nav'].add_component(cg.get_navcomponent())
        args['nav'].add_component(u"edit")
    else:
        args['nav'].add_component(u"add")

    return render_to_response('edit.html', args, RequestContext(request))


def on_contactgroup_delete(cg):
    for subcg in cg.direct_subgroups:
        if not subcg.direct_supergroups:
            subcg.direct_supergroups = [ Query(ContactGroup).get(GROUP_EVERYBODY) ]
    # TODO: delete static folder

@http_authenticate(ngw_auth, 'ngw')
def contactgroup_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = Query(ContactGroup).get(id)
    return generic_delete(request, o, reverse('ngw.core.views.contactgroup_list'), ondelete_function=on_contactgroup_delete)# args=(p.id,)))


#######################################################################
#
# Contact In Group
#
#######################################################################


class ContactInGroupForm(forms.Form):
    invited = forms.BooleanField(required=False)
    declined_invitation = forms.BooleanField(required=False)
    member = forms.BooleanField(required=False)
    operator = forms.BooleanField(required=False)

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        #self.fields['direct_members'].choices = [ (c.id, c.name) for c in Query(Contact).order_by([Contact.c.name]) ]
        self.fields['invited'].widget.attrs = { "onchange": "if (this.checked) { this.form.declined_invitation.checked=false; this.form.member.checked=false; this.form.operator.checked=false;}"}
        self.fields['declined_invitation'].widget.attrs = { "onchange": "if (this.checked) { this.form.invited.checked=false; this.form.member.checked=false; this.form.operator.checked=false;}"}
        self.fields['member'].widget.attrs = { "onchange": "if (this.checked) { this.form.invited.checked=false; this.form.declined_invitation.checked=false; } else { this.form.operator.checked=false;}"}
        self.fields['operator'].widget.attrs = { "onchange": "if (this.checked) { this.form.invited.checked=false; this.form.declined_invitation.checked=false; this.form.member.checked=true; }"}

    def clean(self):
        data = self.cleaned_data
        if  (data['invited'] and data['declined_invitation']) \
         or (data['declined_invitation'] and data['member']) \
         or (data['invited'] and data['member']) \
         or (data['operator'] and not data['member']):
            raise forms.ValidationError("Invalid flags combinaison")
        return data

@http_authenticate(ngw_auth, 'ngw')
def contactingroup_edit(request, gid, cid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = Query(ContactGroup).get(gid)
    contact = Query(Contact).get(cid)
    cig = Query(ContactInGroup).get((cid, gid))
    args = {}
    args['title'] = u"Contact "+unicode(contact)+u" in group "+cg.unicode_with_date()
    args['cg'] = cg
    args['contact'] = contact
    args['objtype'] = ContactInGroup
    initial={}
    if cig:
        initial['invited'] = cig.invited
        initial['declined_invitation'] = cig.declined_invitation
        initial['member'] = cig.member
        initial['operator'] = cig.operator

    if request.method == 'POST':
        form = ContactInGroupForm(request.POST, initial=initial)
        if form.is_valid():
            data = form.cleaned_data
            if not data['invited'] and not data['declined_invitation'] and not data['member'] and not data['operator']:
                return HttpResponseRedirect(reverse('ngw.core.views.contactingroup_delete', args=(unicode(cg.id),cid)))
            if not cig:
                cig = ContactInGroup(contact.id, cg.id)
            cig.invited = data['invited']
            cig.declined_invitation = data['declined_invitation']
            cig.member = data['member']
            cig.operator = data['operator']
            request.user.push_message(u"Member %s of group %s has been changed sucessfully!" % (contact.name, cg.name))
            return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_members', args=(cg.id,)))
    else:
        form = ContactInGroupForm(initial=initial)

    args['form'] = form

    subgroups = cg.subgroups
    subgroup_ids = [ subg.id for subg in subgroups ]
    auto_member = []
    auto_invited = []
    for sub_cig in Query(ContactInGroup).filter(ContactInGroup.contact_id==cid).filter(ContactInGroup.group_id.in_(subgroup_ids)).filter(ContactInGroup.member==True):
        sub_cg = Query(ContactGroup).get(sub_cig.group_id)
        auto_member.append(sub_cg)
    for sub_cig in Query(ContactInGroup).filter(ContactInGroup.contact_id==cid).filter(ContactInGroup.group_id.in_(subgroup_ids)).filter(ContactInGroup.invited==True):
        sub_cg = Query(ContactGroup).get(sub_cig.group_id)
        auto_invited.append(sub_cg)
    inherited_info = u""
    if auto_member:
        inherited_info += u"Automatically member because member of subgroup(s):<br>"
        for sub_cg in auto_member:
            inherited_info += u"<li><a href=\"%(url)s\">%(name)s</a>" % { 'name': sub_cg.unicode_with_date(), 'url': sub_cg.get_absolute_url() }
        inherited_info += u"<br>"
    if auto_invited:
        inherited_info += u"Automatically invited because invited in subgroup(s):<br>"
        for sub_cg in auto_invited:
            inherited_info += u"<li><a href=\"%(url)s\">%(name)s</a>" % { 'name': sub_cg.unicode_with_date(), 'url': sub_cg.get_absolute_url() }
    args['inherited_info'] = mark_safe(inherited_info)

    args['nav'] = navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"members", contact.get_navcomponent(), u"membership")
    return render_to_response('contact_in_group.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def contactingroup_delete(request, gid, cid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = Query(ContactGroup).get(gid)
    o = Query(ContactInGroup).get((cid, gid))
    if not o:
        return HttpResponse("Error, that contact is not a direct member. Please check subgroups")
    #request.user.push_message(u"%s has been removed for group %s." % (cig.contact.name, cig.group.name))
    return generic_delete(request, o, next_url=cg.get_absolute_url()+u"members/", base_nav=navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"members"))
    # TODO: realnav bar is "remove", not "delete"


#######################################################################
#
# ContactGroup News
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def contactgroup_news(request, gid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = Query(ContactGroup).get(gid)
    args = {}
    args['title'] = u"News for group "+cg.name
    #args['news'] = cg.news #order doesn't work?!
    args['news'] = Query(ContactGroupNews).filter(ContactGroupNews.contact_group==cg).order_by(desc(ContactGroupNews.date))
    args['cg'] = cg
    args['objtype'] = ContactGroupNews
    args['nav'] = navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"news")
    return render_to_response('news.html', args, RequestContext(request))


class NewsEditForm(forms.Form):
    title = forms.CharField(max_length=50)
    text = forms.CharField(widget=forms.Textarea)

@http_authenticate(ngw_auth, 'ngw')
def contactgroup_news_edit(request, gid, nid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = Query(ContactGroup).get(gid)
    if nid:
        news = Query(ContactGroupNews).get(nid)
        if news.contact_group!=cg:
            return HttpResponse(u"ERROR: Invalid group")

    if request.method == 'POST':
        form = NewsEditForm(request.POST)
        if form.is_valid():
            data = form.clean()
            if not nid:
                news = ContactGroupNews()
                news.author = request.user
                news.contact_group = cg
                news.date = datetime.now()
            news.title = data['title']
            news.text = data['text']
            request.user.push_message("News %s has been changed sucessfully!" % unicode(news))
            Session.commit()
            
            if request.POST.get("_continue", None):
                return HttpResponseRedirect(news.get_absolute_url())
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_news_edit', args=(cg.id,))) # 2nd parameter is None
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_news', args=(cg.id,)))
    else:
        initial={}
        if nid:
            initial['title'] = news.title
            initial['text'] = news.text
        form = NewsEditForm(initial=initial)
    args = {}
    args['title'] = u"News edition"
    args['cg'] = cg
    args['form'] = form
    if nid:
        args['o'] = news
        args['id'] = nid
    args['nav'] = navbar(cg.get_class_navcomponent(), cg.get_navcomponent(), u"news")
    if nid:
        args['nav'].add_component(news.get_navcomponent())
        args['nav'].add_component(u"edit")
    else:
        args['nav'].add_component(u"add")

    return render_to_response('edit.html', args, RequestContext(request))

@http_authenticate(ngw_auth, 'ngw')
def contactgroup_news_delete(request, gid, nid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = Query(ContactGroup).get(gid)
    o = Query(ContactGroupNews).get(nid)
    return generic_delete(request, o, cg.get_absolute_url()+u"news/")

#######################################################################
#
# Contact Fields
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def field_list(request):
    if not request.user.is_admin():
        return unauthorized(request)
    args = {}
    args['query'] = Query(ContactField).order_by([ContactField.c.sort_weight]) # FIXME
    args['cols'] = [
        ( "Name", None, "name", contact_field_table.c.name),
        ( "Type", None, "type_as_html", contact_field_table.c.type),
        ( "Only for", None, "contact_group", contact_field_table.c.contact_group_id),
        ( "System locked", None, "system", contact_field_table.c.system),
        #( "Move", None, lambda cf: "<a href="+str(cf.id)+"/moveup>Up</a> <a href="+str(cf.id)+"/movedown>Down</a>", None),
    ]
    args['title'] = "Select an optionnal field"
    args['objtype'] = ContactField
    args['nav'] = navbar(ContactField.get_class_navcomponent())
    return query_print_entities(request, 'list.html', args)


@http_authenticate(ngw_auth, 'ngw')
def field_move_up(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    cf = Query(ContactField).get(id)
    cf.sort_weight -= 15
    Session.commit()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))

@http_authenticate(ngw_auth, 'ngw')
def field_move_down(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    cf = Query(ContactField).get(id)
    cf.sort_weight += 15
    Session.commit()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))

def field_renumber():
    new_weigth = 0
    for cf in Query(ContactField).order_by('sort_weight'):
        new_weigth += 10
        cf.sort_weight = new_weigth
    Session.commit()


class FieldEditForm(forms.Form):
    name = forms.CharField()
    hint = forms.CharField(required=False, widget=forms.Textarea)
    contact_group = forms.CharField(label=u"Only for", required=False, widget=forms.Select)
    type = forms.CharField(widget=forms.Select)
    choicegroup = forms.CharField(required=False, widget=forms.Select)
    move_after = forms.IntegerField(widget=forms.Select())

    def __init__(self, cf, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
    
        contacttypes = Query(ContactGroup).filter(ContactGroup.c.field_group==True)
        self.fields['contact_group'].widget.choices = [('', u'Everyone')] + [ (g.id, g.name) for g in contacttypes ]

        self.fields['type'].widget.choices = [ (cls.db_type_id, cls.human_type_id) for cls in CONTACT_FIELD_TYPES_CLASSES ]
        js_test_type_has_choice = u" || ".join([ u"this.value=='"+cls.db_type_id+"'" for cls in CONTACT_FIELD_TYPES_CLASSES if cls.has_choice ])
        self.fields['type'].widget.attrs = { "onchange": "if (0 || "+js_test_type_has_choice+") { document.forms[0]['choicegroup'].disabled = 0; } else { document.forms[0]['choicegroup'].value = ''; document.forms[0]['choicegroup'].disabled = 1; }" }
    
        self.fields['choicegroup'].widget.choices = [('', '---')] + [(c.id, c.name) for c in Query(ChoiceGroup).order_by(ChoiceGroup.c.name)]
 
        t = self.data.get("type", "") or self.initial.get('type', "")
        if t:
            cls_contact_field = get_contact_field_type_by_dbid(t)
        else:
            cls_contact_field = CONTACT_FIELD_TYPES_CLASSES[0]
        if cls_contact_field.has_choice:
            if self.fields['choicegroup'].widget.attrs.has_key('disabled'):
                del self.fields['choicegroup'].widget.attrs['disabled']
            self.fields['choicegroup'].required = True
        else:
            self.fields['choicegroup'].widget.attrs['disabled'] = 1
            self.fields['choicegroup'].required = False
       
        self.fields['move_after'].widget.choices = [ (5, "Name") ] + [ (field.sort_weight + 5, field.name) for field in Query(ContactField).order_by('sort_weight') ]

        if cf and cf.system:
            self.fields['contact_group'].widget.attrs['disabled'] = 1
            self.fields['type'].widget.attrs['disabled'] = 1
            self.fields['type'].required = False
            self.fields['choicegroup'].widget.attrs['disabled'] = 1

    def clean(self):
        t = self.cleaned_data.get('type', None)
        if t:
            # system fields have type disabled, this is ok
            cls_contact_field = get_contact_field_type_by_dbid(t)
            if cls_contact_field.has_choice and not self.cleaned_data['choicegroup']:
                raise forms.ValidationError("You must select a choice group for that type.")
        return self.cleaned_data


@http_authenticate(ngw_auth, 'ngw')
def field_edit(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype=ContactField
    initial = {}
    if id:
        cf = Query(ContactField).get(id)
        title = u"Editing "+unicode(cf)
        initial['name'] = cf.name
        initial['hint'] = cf.hint
        initial['contact_group'] = cf.contact_group_id
        initial['type'] = cf.type
        initial['choicegroup'] = cf.choice_group_id
        initial['move_after'] = cf.sort_weight-5
    else:
        cf = None
        title = u"Adding a new "+objtype.get_class_verbose_name()
    
    if request.method == 'POST':
        form = FieldEditForm(cf, request.POST, initial=initial)
        print request.POST
        if form.is_valid():
            data = form.clean()
            if not id:
                cf = ContactField()
                
                cf.name = data['name']
                cf.hint = data['hint']
                if data['contact_group']:
                    cf.contact_group_id = int(data['contact_group'])
                else:
                    cf.contact_group_id = None
                cf.type = data['type'] # BUG can't change polymorphic type
                if data['choicegroup']:
                    cf.choice_group_id = int(data['choicegroup'])
                else:
                    cf.choice_group_id = None
                cf.sort_weight = int(data['move_after'])
                # reload polymorphic class:
                Session.commit()
                cfid = cf.id
                Session.execute("UPDATE contact_field SET type='%(type)s' WHERE id=%(id)i"%{'id':cfid, 'type': data['type']})
                Session.expunge(cf)
                cf = Query(ContactField).get(cfid)
            else:
                if not cf.system and (cf.type != data['type'] or unicode(cf.choice_group_id) != data['choicegroup']):
                    deletion_details=[]
                    cls = get_contact_field_type_by_dbid(data['type'])
                    choice_group_id = None
                    if data['choicegroup']:
                        choice_group_id = int(data['choicegroup'])
                    for cfv in cf.values:
                        if not cls.validate_unicode_value(cfv.value, choice_group_id):
                            deletion_details.append((cfv.contact, cfv))
                            
                    if deletion_details:
                        if request.POST.get('confirm', None):
                            for cfv in [ dd[1] for dd in deletion_details ]:
                                Session.delete(cfv)
                        else:
                            args={}
                            args['title'] = "Type incompatible with existing data"
                            args['id'] = id
                            args['cf'] = cf
                            args['deletion_details'] = deletion_details
                            for k in ( 'name', 'hint', 'contact_group', 'type', 'choicegroup', 'move_after'):
                                args[k] = data[k]
                            args['nav'] = navbar(cf.get_class_navcomponent(), cf.get_navcomponent(), (u"edit", u"delete imcompatible data"))
                            return render_to_response('type_change.html', args, RequestContext(request))
                    
                    # Needed work around sqlalchemy polymorphic feature
                    # Recreate the record
                    # Updating type of a sub class silently fails
                    id_int = int(id)
                    Session.execute("UPDATE contact_field SET type='%(type)s' WHERE id=%(id)i"%{'id':id_int, 'type': data['type']})
                    cf = Query(ContactField).get(id)
                cf.name = data['name']
                cf.hint = data['hint']
                if not cf.system:
                    # system fields have some properties disabled
                    if data['contact_group']:
                        cf.contact_group_id = int(data['contact_group'])
                    else:
                        cf.contact_group_id = None
                    cf.type = data['type'] # BUG can't change polymorphic type
                    if data['choicegroup']:
                        cf.choice_group_id = int(data['choicegroup'])
                    else:
                        cf.choice_group_id = None
                cf.sort_weight = int(data['move_after'])


            field_renumber()
            print cf
            request.user.push_message(u"Field %s has been changed sucessfully." % cf.name)
            if request.POST.get("_continue", None):
                if not id:
                    Session.commit() # We need the id rigth now!
                return HttpResponseRedirect(cf.get_absolute_url()+u"edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect(cf.get_class_absolute_url()+u"add")
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.field_list')) # args=(p.id,)))
        # else validation error
    else:
        if id: # modify
            form = FieldEditForm(cf, initial=initial)
        else: # add
            form = FieldEditForm(None, initial=initial)


    args={}
    args['form'] = form
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    if id:
        args['o'] = cf
    args['nav'] = navbar(ContactField.get_class_navcomponent())
    if id:
        args['nav'].add_component(cf.get_navcomponent())
        args['nav'].add_component(u"edit")
    else:
        args['nav'].add_component(u"add")
    return render_to_response('edit.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def field_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = Query(ContactField).get(id)
    next_url = reverse('ngw.core.views.field_list')
    if o.system:
        request.user.push_message(u"Field %s is locked and CANNOT be deleted." % o.name)
        return HttpResponseRedirect(next_url)
    return generic_delete(request, o, next_url)


#######################################################################
#
# Choice groups
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def choicegroup_list(request):
    if not request.user.is_admin():
        return unauthorized(request)
    args = {}
    args['query'] = Query(ChoiceGroup)
    args['cols'] = [
        ( "Name", None, "name", ChoiceGroup.c.name),
        ( "Choices", None, lambda cg: ", ".join([html.escape(c[1]) for c in cg.ordered_choices]), None),
    ]
    args['title'] = "Select a choice group"
    args['objtype'] = ChoiceGroup
    args['nav'] = navbar(ChoiceGroup.get_class_navcomponent())
    return query_print_entities(request, 'list.html', args)


class ChoicesWidget(forms.MultiWidget):
    def __init__(self, ndisplay, attrs=None):
        widgets = []
        attrs_value = attrs or {}
        attrs_key = attrs or {}
        attrs_value['style'] = u"width:90%"
        attrs_key['style'] = u"width:9%; margin-left:1ex;"

        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs_value))
            widgets.append(forms.TextInput(attrs=attrs_key))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay
    def decompress(self, value):
        if value:
            return value.split(u",")
        nonelist = []
        for i in range(self.ndisplay):
            nonelist.append(None)
        return nonelist


class ChoicesField(forms.MultiValueField):
    def __init__(self, ndisplay, *args, **kwargs):
        fields = []
        for i in range(ndisplay):
            fields.append(forms.CharField())
            fields.append(forms.CharField())
        super(ChoicesField, self).__init__(fields, *args, **kwargs)
        self.ndisplay = ndisplay
    def compress(self, data_list):
        if data_list:
            return u",".join(data_list)
        return None
    def clean(self, value):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = forms.MultiValueField.clean(self, value).split(u",")
        #print "possibles_values=", repr(possibles_values)
        keys = []
        for i in range(len(possibles_values)/2):
            v,k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines without values
            if not k:
                continue # empty keys are ok
            if k in keys:
                raise forms.ValidationError("You cannot have two keys with the same value. Leave empty for automatic generation.")
            keys.append(k)
        return possibles_values


class ChoiceGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    sort_by_key = forms.BooleanField(required=False)

    def __init__(self, cg=None, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        
        ndisplay=0
        self.initial['possible_values']=[]

        if cg:
            self.initial['name'] = cg.name
            self.initial['sort_by_key'] = cg.sort_by_key
            choices = cg.ordered_choices
            for c in choices:
                self.initial['possible_values'].append(c[1])
                self.initial['possible_values'].append(c[0])
                ndisplay+=1

        for i in range(3): # add 3 blank lines to add data
            self.initial['possible_values'].append(u"")
            self.initial['possible_values'].append(u"")
            ndisplay+=1
        self.fields['possible_values'] = ChoicesField(required=False, widget=ChoicesWidget(ndisplay=ndisplay), ndisplay=ndisplay)

    
    def save(self, cg, request):
        if cg:
            oldid = cg.id
        else:
            cg = ChoiceGroup()
            oldid = None
        cg.name = self.clean()['name']
        cg.sort_by_key = self.clean()['sort_by_key']
        
        possibles_values = self['possible_values']._data()
        choices={}

        # first ignore lines with empty keys, and update auto_key
        auto_key = 0
        for i in range(len(possibles_values)/2):
            v,k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines whose value is empty
            if k: # key is not left empty for automatic generation
                if k.isdigit():
                    intk = int(k)
                    if intk>auto_key:
                        auto_key = intk
                choices[k] = v

        auto_key += 1

        # now generate key for empty ones
        for i in range(len(possibles_values)/2):
            v,k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines whose value is empty
            if not k: # key is left empty for automatic generation
                k = str(auto_key)
                auto_key += 1
                choices[k] = v

        #print "choices=", choices
        
        for c in cg.choices:
            k = c.key
            if k in choices.keys():
                #print "UPDATING", k
                c.value=choices[k]
                del choices[k]
            else: # that key has be deleted
                #print "DELETING", k
                Session.delete(c)
        for k,v in choices.iteritems():
            #print "ADDING", k
            cg.choices.append(Choice(key=k, value=v))
    
        request.user.push_message(u"Choice %s has been saved sucessfully." % cg.name)
        return cg
            
        
@http_authenticate(ngw_auth, 'ngw')
def choicegroup_edit(request, id=None):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype = ChoiceGroup
    if id:
        cg = Session.get(ChoiceGroup, id)
        title = u"Editing "+unicode(cg)
    else:
        cg = None
        title = u"Adding a new "+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, request.POST)
        if form.is_valid():
            cg = form.save(cg, request)
            if request.POST.get("_continue", None):
                if not id:
                    Session.commit() # We need the id rigth now!
                return HttpResponseRedirect(cg.get_absolute_url()+u"edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect(cg.get_class_absolute_url()+u"add")
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.choicegroup_list'))
    else:
        form = ChoiceGroupForm(cg)

    args={}
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    args['form'] = form
    if id:
        args['o'] = cg
    args['nav'] = navbar(ChoiceGroup.get_class_navcomponent())
    if id:
        args['nav'].add_component(cg.get_navcomponent())
        args['nav'].add_component(u"edit")
    else:
        args['nav'].add_component(u"add")
    return render_to_response('edit.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def choicegroup_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = Query(ChoiceGroup).get(id)
    return generic_delete(request, o, reverse('ngw.core.views.choicegroup_list'))# args=(p.id,)))
