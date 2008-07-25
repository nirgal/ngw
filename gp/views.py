# -*- encoding: utf8 -*-

import copy, traceback, time, subprocess
from pprint import pprint
from itertools import chain
from md5 import md5
from sha import sha
from random import random
from django.http import *
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django import forms
from django.forms.util import smart_unicode
from django.shortcuts import render_to_response
from django.template import RequestContext
from ngw import settings
from ngw.gp.alchemy_models import *
from ngw.gp.basicauth import *

GROUP_PREFIX = '_group_'
DEFAULT_INITIAL_FIELDS=['name', 'email', 'tel_mobile', 'tel_prive', 'tel_professionel', 'region']
NB_LINES_PER_PAGE=100


def ngw_auth(username, passwd):
    username = unicode(username, 'utf-8', 'replace')
    passwd = unicode(passwd, 'utf-8', 'replace')
    if not username or not passwd:
        return None
    c = Query(Contact).filter(Contact.c.login==username).first()
    if c==None:
        return None
    dbpasswd=c.passwd
    algo, salt, digest = dbpasswd.split('$')
    if algo=="crypt":
        targetdigest=subprocess.Popen(["openssl", "passwd", "-crypt", "-salt", salt, passwd], stdout=subprocess.PIPE).communicate()[0]
        targetdigest=targetdigest[:-1] # remove extra "\n"
        if salt+digest==targetdigest:
            return c
    elif algo=="md5":
        if md5(salt+passwd).hexdigest()==digest:
            return c
    elif algo=="sha1":
        if sha(salt+passwd).hexdigest()==digest:
            return c
    else:
        print "Unsupported password algorithm", algo.encode('utf-8')
        return None
    return None # authentification failed


def get_default_display_fields():
    # check the field still exists
    result = []
    for fname in DEFAULT_INITIAL_FIELDS:
        if fname=='name':
            pass
        elif fname.startswith(GROUP_PREFIX):
            try:
                groupid = int(fname[len(GROUP_PREFIX):])
            except ValueError:
                print "Error in default fields: %s has invalid syntax." % fname
                continue
            if not Query(ContactGroup).get(groupid):
                print "Error in default fields: There is no group #%d." % groupid
                continue
        else:
            if not Query(ContactField).filter(ContactField.c.name==fname).first():
                print "Error in default fields: %s doesn't exists." % fname
                continue
        result.append(fname)
    return result


def name_internal2nice(txt):
    """
    Capitalize first letter and replace _ by spaces
    """
    txt = txt.replace('_', ' ')
    if len(txt)>0:
        txt = txt[0].upper() + txt[1:]
    return txt

def MultiValueDict_unicode(d):
    "Create a copy of the dict, converting values to unicode when necessary"
    def u(x):
        if isinstance(x, str):
            return unicode(x, "utf-8")
        else:
            return x
    result = MultiValueDict()
    for k,v in d.iteritems():
        #print "kv=",k,v
        result.setlist(k, [ u(vi) for vi in v ])
    return result

@http_authenticate(ngw_auth, 'ngw')
def index(request):
    return render_to_response('index.html', {
        'title':'Action DB',
        'ncontacts': Query(Contact).count(),
    }, RequestContext(request))

@http_authenticate(ngw_auth, 'ngw')
def generic_delete(request, o, next_url):
    objtypename = o.__class__.__name__.lower()
    title = "Please confirm deletetion"

    if not o:
        raise Http404()

    confirm = request.GET.get("confirm", "")
    if confirm:
        Session.delete(o)
        request.user.push_message("Object has been deleted sucessfully!")
        return HttpResponseRedirect(next_url)
    else:
        return render_to_response('delete.html', {'title':title, 'id':id, 'objtypename':objtypename, 'o': o}, RequestContext(request))
        

# That class is a clone of forms.CheckboxSelectMultiple
# It only adds an extra class=multiplechoice to the <ul>
class NgwCheckboxSelectMultiple(forms.SelectMultiple):
    def render(self, name, value, attrs=None, choices=()):
        if value is None: value = []
        has_id = attrs and attrs.has_key('id')
        final_attrs = self.build_attrs(attrs, name=name)
        output = [u'<ul class=multiplechoice>']
        str_values = set([smart_unicode(v) for v in value]) # Normalize to strings.
        for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
            # If an ID attribute was given, add a numeric index as a suffix,
            # so that the checkboxes don't all have the same ID attribute.
            if has_id:
                final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
            cb = forms.CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
            option_value = smart_unicode(option_value)
            rendered_cb = cb.render(name, option_value)
            output.append(u'<li><label>%s %s</label></li>' % (rendered_cb, escape(smart_unicode(option_label))))
        output.append(u'</ul>')
        return u'\n'.join(output)

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_0'
        return id_
    id_for_label = classmethod(id_for_label)


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
            (name, self.verbose_name, int(self.is_stacked), settings.MEDIA_URL+settings.ADMIN_MEDIA_PREFIX))
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
        "MEDIA_URL": settings.MEDIA_URL,
    }
    ContactSysMsg(123456, 'Boum')
    return render_to_response("test.html", args, RequestContext(request))

#######################################################################
#
# Contacts
#
#######################################################################

def str_member_of_factory(contact_group):
    gids = [ g.id for g in contact_group.self_and_subgroups ]
    return lambda c: c.str_member_of(gids)

def contact_make_query_with_fields(fields=None):
    if fields == None:
        fields = get_default_display_fields()

    q = Query(Contact)
    n_entities = 1
    j = contact_table
    cols=[]
    
    for prop in fields:
        if prop.startswith(GROUP_PREFIX):
            groupid = int(prop[len(GROUP_PREFIX):])
            cg = Query(ContactGroup).get(groupid)
            cols.append( (cg.name, 0, str_member_of_factory(cg), None) )
        elif prop=="name":
            cols.append( ("name", 0, "name", contact_table.c.name) )
        else:
            cf = Query(ContactField).filter_by(name=prop).one()
            a = contact_field_value_table.alias()
            q = q.add_entity(ContactFieldValue, alias=a)
            j = outerjoin(j, a, and_(contact_table.c.id==a.c.contact_id, a.c.contact_field_id==cf.id ))
            cols.append( (cf.name, n_entities, "str_print", a.c.value) )
            n_entities += 1

    q = q.select_from(j)
    return q, cols


@http_authenticate(ngw_auth, 'ngw')
def contact_list(request):
    if request.GET.has_key('select'):
        select = request['select']
        fields = [ 'name' ] + select.split(',')
    else:
        fields = None # default
   
    #print "contact_list:", fields
    q, cols = contact_make_query_with_fields(fields)
    args={}
    args['title'] = "Contact list"
    args['objtypename'] = "contact"
    args['query'] = q
    args['cols'] = cols
    return query_print_entities(request, 'list_contact.html', args)



@http_authenticate(ngw_auth, 'ngw')
def contact_detail(request, id):
    c = Query(Contact).get(id)
    rows = []
    for cf in c.get_allfields():
        cfv = Query(ContactFieldValue).get((id, cf.id))
        #if cfv:
        #    nice_value = unicode(cfv)
        #else:
        #    nice_value = u""
        #rows.append((cf.name, nice_value))
        if cfv:
            rows.append((cf.name, unicode(cfv)))
    
    args={}
    args['title'] = "Contact detail"
    args['objtypename'] = "contact"
    args['contact'] = c
    args['rows'] = rows
    return render_to_response('contact_detail.html', args, RequestContext(request))



@http_authenticate(ngw_auth, 'ngw')
def contact_vcard(request, id):
    c = Query(Contact).get(id)
    return HttpResponse(c.vcard().encode("utf-8"), mimetype="text/x-vcard")


class RibField(forms.Field):
    # TODO handle international IBAN numbers http://fr.wikipedia.org/wiki/ISO_13616
    def clean(self, value):
        """
        Validate the RIB key
        """
        super(RibField, self).clean(value)
        if value in (None, ""):
            return None
        iso_value = ""
        for c in value:
            if c==" ":
                continue # ignore spaces
            if c>="0" and c<="9":
                iso_value += c
                continue
            c = c.upper()
            if c>="A" and c<="I":
                iso_value += str(ord(c)-64)
            elif c>="J" and c<="R":
                iso_value += str(ord(c)-73)
            elif c>="S" and c<="Z":
                iso_value+= str(ord(c)-81)
            else:
                raise forms.ValidationError("Illegal character "+c)
            
        if len(iso_value) != 23:
            raise forms.ValidationError("There must be 23 non blank characters.")
            
        print iso_value
        if int(iso_value) % 97:
            raise forms.ValidationError("CRC error")
            
        return value


class ContactSearchLine:
    def __init__(self, form, name, label, checked=False):
        self.form = form
        self.name = name
        self.label = label
        self.checked = checked
        self.operators=[
            # form_value eg: "LT"
            # form_display: "&lt;"
            # need_parameter: True/False
            # filter_function(self, Query, value) -> Query
            ("", "", False, lambda x,y,z: x),
            ]
    
    def add_fields(self, fields):
        fields[self.name] = forms.BooleanField(required=False, initial=self.checked)
        
        fields["_op_"+self.name] = forms.ChoiceField(required=False, choices=[ (op[0], op[1]) for op in self.operators], widget=forms.Select(attrs={"onchange": "toggle_value_"+self.name+"()"}))
        fields["_val_"+self.name] = forms.CharField(required=False)
    
    def as_html(self):
        output = ""
        output += '<td>'+unicode(self.form[self.name])+'\n'
        output += '<th><label for="id_'+self.name+'">'+self.label+'</label>\n'
        output += '<td>'+unicode(self.form["_op_"+self.name])+'\n'
        output += '<td><span id="data_'+self.name+'">'+unicode(self.form["_val_"+self.name])+'</span>\n'
        return mark_safe(output)
        
    def javascript_toggle_value(self):
        result = """function toggle_value_%(name)s() {
            switch(document.forms[0]["_op_%(name)s"].value) {
            """ % { 'name': self.name }
        for op in self.operators:
            result += 'case "'+op[0]+'":'
            if op[2]:
                result += ' document.getElementById("data_'+self.name+'").style.display = "block";\n'
            else:
                result += ' document.getElementById("data_'+self.name+'").style.display = "none";\n'
            result += 'break;\n'
        result += " }\n"
        result += "}\n"
        return mark_safe(result)

    def _make_filter(self, query, where, **kargs):
        #print "kargs=", kargs
        assert query
            
        params_where = { }
        params_sql = { }
        for k,v in kargs.iteritems():
            #print k,"=",v
            if isinstance(v, unicode):
                params_where[ k ] = u':'+k
                params_sql[ k ] = v
            elif isinstance(v, int):
                params_where[ k ] = v
            else:
                raise Exception("Unsupported type "+str(type(v)))
        where = where % params_where
        return query.filter(where).params(params_sql)

    def get_filter(self, filter_name):
        for op in self.operators:
            if op[0]==filter_name:
                return op[3]
        raise Exception("Bad filter "+filter_name)


class ContactSearchLineName(ContactSearchLine):
    def __init__(self, form):
        ContactSearchLine.__init__(self, form, "name", "Name", checked=True)
        self.operators.append(("NAME", "Word starts with", True, self.filter_NAME))
    
    def filter_NAME(self, query, value):
        return self._make_filter(query, 'contact.name ILIKE %(value_name1)s OR contact.name ILIKE %(value_name2)s', value_name1=value+"%", value_name2="% "+value+"%")


class ContactSearchLineBaseField(ContactSearchLine):
    def __init__(self, form, xf, initial_check=False):
        ContactSearchLine.__init__(self, form, xf.name, name_internal2nice(xf.name), initial_check)
        self.xf = xf

    def _make_filter(self, query, where, **kargs):
        kargs['field_id'] = self.xf.id
        return ContactSearchLine._make_filter(self, query, where, **kargs)

    def filter_STARTSWITH(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value1)s OR (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value2)s', value1=value+"%", value2="% "+value+"%")

    def filter_EQ(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', value=value)

    def filter_NEQ(self, query, value):
        return self._make_filter(query, 'NOT EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', value=value)
    
    def filter_LE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) <= %(value)s', value=value)

    def filter_GE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) > %(value)s', value=value)

    def filter_LIKE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) LIKE %(value)s', value=value)

    def filter_ILIKE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value)s', value=value)

    def filter_NULL(self, query, value):
        return self._make_filter(query, 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )')

    def filter_NOTNULL(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )')


class ContactSearchLineInteger(ContactSearchLineBaseField):
    def __init__(self, *args, **kargs):
        ContactSearchLineBaseField.__init__(self, *args, **kargs)
        self.operators.append(("EQ", "=", True, self.filter_IEQ))
        self.operators.append(("NE", "≠", True, self.filter_INE))
        self.operators.append(("LT", "<", True, self.filter_ILT))
        self.operators.append(("GT", ">", True, self.filter_IGT))
        self.operators.append(("LE", "≤", True, self.filter_ILE))
        self.operators.append(("GE", "≥", True, self.filter_IGE))
        self.operators.append(("NULL", "NULL", False, self.filter_NULL))
        self.operators.append(("NOTNULL", "NOT NULL", False, self.filter_NOTNULL))
    
    def filter_IEQ(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int = %(value)i', value=int(value))

    def filter_INE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <> %(value)i', value=int(value))

    def filter_ILT(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int < %(value)i', value=int(value))

    def filter_IGT(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int > %(value)i', value=int(value))

    def filter_ILE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <= %(value)i', value=int(value))

    def filter_IGE(self, query, value):
        return self._make_filter(query, '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int >= %(value)i', value=int(value))

        
class ContactSearchLineText(ContactSearchLineBaseField):
    def __init__(self, *args, **kargs):
        ContactSearchLineBaseField.__init__(self, *args, **kargs)
        self.operators.append(("STARTSWITH", "Word starts with", True, self.filter_STARTSWITH))
        self.operators.append(("EQUALS", "=", True, self.filter_EQ))
        self.operators.append(("NE", "≠", True, self.filter_NEQ))
        self.operators.append(("LIKE", "LIKE", True, self.filter_LIKE))
        self.operators.append(("ILIKE", "ILIKE", True, self.filter_ILIKE))
        self.operators.append(("NULL", "NULL", False, self.filter_NULL))
        self.operators.append(("NOTNULL", "NOT NULL", False, self.filter_NOTNULL))
    
        
class ContactSearchLineChoice(ContactSearchLineBaseField):
    def __init__(self, form, xf, *args, **kargs):
        ContactSearchLineBaseField.__init__(self, form, xf, *args, **kargs)
        self.operators.append(("EQUALS", "=", True, self.filter_EQ))
        self.operators.append(("NE", "≠", True, self.filter_NEQ))
        null_name = "NULL (Unknown)"
        self.operators.append(("NULL", null_name, False, self.filter_NULL))

    def add_fields(self, fields):
        ContactSearchLine.add_fields(self, fields)
        self.form.fields["_val_"+self.name] = forms.ChoiceField(required=False, choices=self.xf.choice_group.ordered_choices,  widget=forms.Select() )

        
class ContactSearchLineMultiChoice(ContactSearchLineBaseField):
    def __init__(self, *args, **kargs):
        ContactSearchLineBaseField.__init__(self, *args, **kargs)
        self.operators.append(("MULTIHAS", "Has", True, self.filter_MULTIHAS))

    def add_fields(self, fields):
        ContactSearchLine.add_fields(self, fields)
        self.form.fields["_val_"+self.name] = forms.ChoiceField(required=False, choices=self.xf.choice_group.ordered_choices,  widget=forms.Select() )
    
    def filter_MULTIHAS(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', value=value, valuestart=value+",%", valuemiddle="%,"+value+",%", valueend="%,"+value)


        
class ContactSearchLineDate(ContactSearchLineBaseField):
    def __init__(self, *args, **kargs):
        ContactSearchLineBaseField.__init__(self, *args, **kargs)
        self.operators.append(("EQUALS", "=", True, self.filter_EQ))
        self.operators.append(("LE", "≤", True, self.filter_LE))
        self.operators.append(("GE", "≥", True, self.filter_GE))
        self.operators.append(("AGE_GE", "Age ≥", True, self.filter_AGE_GE))
        #self.operators.append(("VALID_GT", "Validity ≥", True, self.filter_VALID_GT))
        self.operators.append(("FUTURE", "In the future", False, self.filter_FUTURE))
        self.operators.append(("NULL", "NULL", False, self.filter_NULL))
        self.operators.append(("NOTNULL", "NOT NULL", False, self.filter_NOTNULL))

    def filter_AGE_GE(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND NOW() - value::DATE > \'%(value)i years\'::INTERVAL )', value=int(value))
        
    def filter_VALID_GT(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', value=int(value))
        
    def filter_FUTURE(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )')
        

class ContactSearchLineGroup(ContactSearchLine):
    def __init__(self, form, group, initial_check=False):
        nicename = group.name
        if group.date:
            nicename+=u" "+unicode(group.date)
        ContactSearchLine.__init__(self, form, GROUP_PREFIX + str(group.id), nicename, initial_check)
        self.group = group
        self.operators.append(("MEMBER", "Member", False, self.filter_MEMBER))
        self.operators.append(("INVITED", "Invited", False, self.filter_INVITED))
        self.operators.append(("NOTMEMBER", "Not member", False, self.filter_NOTMEMBER))
        self.operators.append(("DIRECTMEMBER", "Direct member", False, self.filter_DIRECTMEMBER))
    
    def filter_MEMBER(self, query, value):
        return query.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND member=\'t\')' % ",".join([str(g.id) for g in self.group.self_and_subgroups]))
    
    def filter_NOTMEMBER(self, query, value):
        return query.filter('NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND member=\'t\')' % ",".join([str(g.id) for g in self.group.self_and_subgroups]))
    
    def filter_INVITED(self, query, value):
        return query.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND invited=\'t\')' % ",".join([str(g.id) for g in self.group.self_and_subgroups]))
    
    def filter_DIRECTMEMBER(self, query, value):
        return query.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%d  AND member=\'t\')' % self.group.id)

        
class ContactSearchForm(forms.Form):
    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        self.lines = []
        default_display_fields = get_default_display_fields()

        def addLine(self, line):
            self.lines.append(line)
            line.add_fields(self.fields)

        # Add name field, default to true
        #addLine(self, ContactSearchLine(self, 'name', 'Name', True))
        addLine(self, ContactSearchLineName(self))

        # Add all contact fields
        for cf in Query(ContactField).order_by('sort_weight'):
            initial_check = cf.name in default_display_fields
            if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_EMAIL, FTYPE_PHONE, FTYPE_RIB):
                addLine(self, ContactSearchLineText(self, cf, initial_check))
            elif cf.type == FTYPE_NUMBER:
                addLine(self, ContactSearchLineInteger(self, cf, initial_check))
            elif cf.type == FTYPE_DATE:
                addLine(self, ContactSearchLineDate(self, cf, initial_check))
            elif cf.type == FTYPE_CHOICE:
                addLine(self, ContactSearchLineChoice(self, cf, initial_check))
            elif cf.type == FTYPE_MULTIPLECHOICE:
                addLine(self, ContactSearchLineMultiChoice(self, cf, initial_check))
            else:
                addLine(self, ContactSearchLineBaseField(self, cf, initial_check))

        # Add all groups
        for g in Query(ContactGroup).order_by([ContactGroup.c.date.desc(), ContactGroup.c.name]):
            initial_check = GROUP_PREFIX+str(g.id) in default_display_fields
            addLine(self, ContactSearchLineGroup(self, g, initial_check))
    
    def do_filter(self, q):
        clean_data = self.clean()
        for line in self.lines:
            op = clean_data["_op_"+line.name]
            if op:
                filter=line.get_filter(op)
                value = clean_data["_val_"+line.name]
                #print filter
                q = filter(q, value)
        return q
    

@http_authenticate(ngw_auth, 'ngw')
def contact_search(request):
    if request.method == 'POST':
        params = request.raw_post_data
    else:
        params = request.META['QUERY_STRING'] or ''

    #print "params=", params
    if params:
        form = ContactSearchForm(request.REQUEST)
        if form.is_valid():
            fields = []
            for kv in params.split("&"):
                k,v = kv.split('=',1)
                if k.startswith('_') and not k.startswith(GROUP_PREFIX):
                    continue
                #print k,v
                fields.append(k)
    
            q, cols = contact_make_query_with_fields(fields)
            q = form.do_filter(q)
            args={}
            args['title'] = "Contacts search results"
            args['objtypename'] = "contact"
            args['query'] = q
            args['cols'] = cols
            args['baseurl'] = "?"+params
            return query_print_entities(request, 'searchresult_contact.html', args)
    else:
        form = ContactSearchForm()

    objtypename = "contact";
    title = "Searching "+objtypename+"s"
    return render_to_response('search.html', { 'title':title, 'objtypename':objtypename, 'form':form}, RequestContext(request))



class ContactEditForm(forms.Form):
    name = forms.CharField()

    def __init__(self, contactid=None, default_group=None, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)

        if contactid:
            contact = Query(Contact).get(contactid)
            contactgroupids = [ g.id for g in contact.get_allgroups_withfields()] 
        elif default_group:
            contactgroupids = [ g.id for g in Query(ContactGroup).get(default_group).self_and_supergroups ] 
            self.fields['default_group'] = forms.CharField(widget=forms.HiddenInput())
        else:
            contactgroupids = [ ]


        # Add all extra fields
        for cf in Query(ContactField).order_by(ContactField.c.sort_weight):
            if cf.contact_group_id:
                if cf.contact_group_id not in contactgroupids:
                    continue # some fields are excluded
            if cf.type==FTYPE_TEXT or cf.type==FTYPE_PHONE:
                self.fields[cf.name] = forms.CharField(max_length=255, required=False, help_text=cf.hint)
            elif cf.type==FTYPE_LONGTEXT:
                self.fields[cf.name] = forms.CharField(widget=forms.Textarea, required=False, help_text=cf.hint)
            elif cf.type==FTYPE_NUMBER:
                self.fields[cf.name] = forms.IntegerField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_DATE:
                self.fields[cf.name] = forms.DateField(required=False, help_text=u"Use YYYY-MM-DD format."+u" "+cf.hint)
            elif cf.type==FTYPE_EMAIL:
                self.fields[cf.name] = forms.EmailField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_RIB:
                self.fields[cf.name] = RibField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_CHOICE:
                self.fields[cf.name] = forms.CharField(max_length=255, required=False, help_text=cf.hint, widget=forms.Select(choices=cf.choice_group.ordered_choices_with_unknown))
            elif cf.type==FTYPE_MULTIPLECHOICE:
                self.fields[cf.name] = forms.MultipleChoiceField(required=False, help_text=cf.hint, choices=cf.choice_group.ordered_choices, widget=NgwCheckboxSelectMultiple())
        
        def contactgroupchoices():
            result = []
            # sql "_" means "any character" and must be escaped
            for g in Query(ContactGroup).filter(not_(ContactGroup.c.name.startswith("\\_"))).order_by([ContactGroup.c.date.desc(), ContactGroup.c.name]):
                nice_name = g.name
                if g.date:
                    nice_name+=u" "+unicode(g.date)
                result.append( (g.id, nice_name) )
            return result

        self.fields['groups'] = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("Group", False), choices=contactgroupchoices())
        

@http_authenticate(ngw_auth, 'ngw')
def contact_edit(request, id):
    objtypename = "contact";
    if id:
        title = "Changing a "+objtypename
    else:
        title = "Adding a new "+objtypename
    if request.method == 'POST':
        if 'default_group' in request.POST:
            default_group = request.POST['default_group']
        else:
            default_group = None
        form = ContactEditForm(id, data=request.POST, default_group=default_group)
        if form.is_valid():
            data = form.clean()
            # print "saving", repr(form.data)

            # record the values

            # 1/ In contact
            if id:
                contact = Query(Contact).get(id)
                contactgroupids = [ g.id for g in contact.get_allgroups_withfields()]  # Need to keep a record of initial groups
                contact.name = data['name']
            else:
                contact = Contact(data['name'])
                default_group = data.get('default_group', "") # Direct requested group
                if default_group:
                    default_group = int(default_group)
                    contactgroupids = [ g.id for g in Query(ContactGroup).get(default_group).self_and_supergroups ]
                else:
                    contactgroupids = [ ]

            newgroups = data.get('groups', [])
            registeredgroups = []
            for gid in newgroups:
                cig = Query(ContactInGroup).get((contact.id, gid))
                if cig==None: # Was not a member
                    cig = ContactInGroup(contact.id, gid)
                    cig.member = True
                registeredgroups.append(gid)
            for cig in Query(ContactInGroup).filter(and_(ContactInGroup.c.contact_id==id, not_(ContactInGroup.c.group_id.in_(registeredgroups)))):
                # TODO optimize me
                print "Deleting", cig
                Session.delete(cig)
            #print "newgroups =", newgroups
            #contact.direct_groups = newgroups
            
            # 2/ In ContactFields
            for cf in Query(ContactField):
                if cf.contact_group_id and cf.contact_group_id not in contactgroupids:
                    continue
                cfname = cf.name
                cfid = cf.id
                newvalue = data[cfname]
                if newvalue!=None:
                    if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_DATE, FTYPE_EMAIL, FTYPE_PHONE, FTYPE_RIB, FTYPE_CHOICE):
                        newvalue = unicode(newvalue)
                    elif cf.type == FTYPE_MULTIPLECHOICE:
                        newvalue = ",".join(newvalue)
                        #print "storing", repr(newvalue), "in", cfname
                    elif cf.type==FTYPE_NUMBER:
                        newvalue = unicode(newvalue) # store as a string for now
                cfv = Query(ContactFieldValue).get((id, cfid))
                if cfv == None:
                    if newvalue:
                        cfv = ContactFieldValue()
                        cfv.contact = contact
                        cfv.field = cf
                        cfv.value = newvalue
                else:
                    if newvalue:
                        cfv.value = newvalue
                    else:
                        Session.delete(cfv)
            request.user.push_message("Contact has been saved sucessfully!")
            if request.POST.get("_continue", None):
                return HttpResponseRedirect("/contacts/"+str(contact.id)+"/edit")
            elif request.POST.get("_addanother", None):
                url = "/contacts/add"
                if default_group:
                    url+="?default_group="+str(default_group)
                return HttpResponseRedirect(url)
            else:
                return HttpResponseRedirect(reverse('ngw.gp.views.contact_list')) # args=(p.id,)))
        # else /new/ or /change/ failed validation
    else: # GET /  HEAD
        initialdata = {}
        if id: # modify existing
            contact = Query(Contact).get(id)
            initialdata['groups'] = [ group.id for group in contact.get_directgroups_member() ]
            initialdata['name'] = contact.name

            for cfv in contact.values:
                cf = cfv.field
                if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_DATE, FTYPE_EMAIL, FTYPE_PHONE, FTYPE_RIB, FTYPE_CHOICE):
                    initialdata[cf.name] = cfv.value
                elif cf.type==FTYPE_NUMBER:
                    initialdata[cf.name] = cfv.value
                elif cf.type==FTYPE_MULTIPLECHOICE:
                    initialdata[cf.name] = cfv.value.split(",")

            form = ContactEditForm(id, initial=initialdata)

        else:
            if 'default_group' in request.GET:
                default_group = request.GET['default_group']
                initialdata['default_group'] = default_group
                initialdata['groups'] = [ int(default_group) ]
                form = ContactEditForm(id, initial=initialdata, default_group=default_group )
            else:
                form = ContactEditForm(id)

    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,}, RequestContext(request))
    

class ContactPasswordForm(forms.Form):
    new_password = forms.CharField(max_length=50, widget=forms.PasswordInput())
    confirm_password = forms.CharField(max_length=50, widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', u'') != self.cleaned_data.get('confirm_password', u''):
            raise forms.ValidationError("The passwords must match!")
        return self.cleaned_data


@http_authenticate(ngw_auth, 'ngw')
def contact_pass(request, id):
    contact = Query(Contact).get(id)
    args={}
    args['title'] = "Change password"
    args['objtypename'] = "contact"
    args['contact'] = contact
    if contact.passwd:
        args['currentaccess'] = u"This contact has a password and can modify his own information."
    else:
        args['currentaccess'] = u"This contact has no password and cannot connect to modify his own information."
    if request.method == 'POST':
        form = ContactPasswordForm(request.POST)
        if form.is_valid():
            # record the value
            password = form.clean()['new_password']
            salt = sha(str(random())).hexdigest()[:5]
            hash = sha(salt+password).hexdigest()
            contact.passwd = "sha1$"+salt+"$"+hash
            request.user.push_message("Password has been changed sucessfully!")
            return HttpResponseRedirect(reverse('ngw.gp.views.contact_detail', args=(id,)))
    else: # GET
        form = ContactPasswordForm()
    args['form'] = form
    return render_to_response('password.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def contact_delete(request, id):
    o = Query(Contact).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.contact_list'))



#######################################################################
#
# Contact groups
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def contactgroup_list(request):
    def print_fields(cg):
        if cg.field_group:
            fields = cg.contact_fields
            if fields:
                return u", ".join(['<a href="'+f.get_link()+'">'+html.escape(f.name)+"</a>" for f in fields])
            else:
                return u"Yes (but none yet)"
        else:
            return u"No"

    q = Query(ContactGroup)
    cols = [
        ( "Date", None, "date", contact_group_table.c.date ),
        ( "Name", None, "name", contact_group_table.c.name ),
        ( "Description", None, "description", contact_group_table.c.description ),
        ( "Fields", None, print_fields, contact_group_table.c.field_group ),
        ( "Super groups", None, lambda cg: u", ".join([sg.name for sg in cg.direct_supergroups]), None ),
        ( "Sub groups", None, lambda cg: u", ".join([html.escape(sg.name) for sg in cg.direct_subgroups]), None ),
        ( "Budget code", None, "budget_code", contact_group_table.c.budget_code ),
        ( "Members", None, lambda cg: str(len(cg.members)), None ),
    ]
    args={}
    args['title'] = "Select a contact group"
    args['query'] = q
    args['cols'] = cols
    args['objtypename'] = "contactgroup"
    return query_print_entities(request, 'list.html', args)


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_detail(request, id):
    fields = get_default_display_fields()
    cg = Query(ContactGroup).get(id)
    #print cg.direct_subgroups
    args={}

    display=request.REQUEST.get("display", "")
    if display=="mi":
        args['title'] = "Members and invited contacts of group "+cg.unicode_with_date()
        fields.append(GROUP_PREFIX+str(id))
        q, cols = contact_make_query_with_fields(fields)
        q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND (member=\'t\' OR invited=\'t\'))' % ",".join([str(g.id) for g in cg.self_and_subgroups]))
    elif display=="i":
        args['title'] = "Contact invited in group "+cg.unicode_with_date()
        q, cols = contact_make_query_with_fields(fields)
        q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND invited=\'t\')' % ",".join([str(g.id) for g in cg.self_and_subgroups]))
    else:
        display='m'
        args['title'] = "Members of group "+cg.unicode_with_date()
        q, cols = contact_make_query_with_fields(fields)
        q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND member=\'t\')' % ",".join([str(g.id) for g in cg.self_and_subgroups]))
    if request.REQUEST.get("output", "")=="vcard":
        result=u""
        for row in q:
            contact = row[0]
            result += contact.vcard()
        return HttpResponse(result.encode("utf-8"), mimetype="text/x-vcard")

    cols.append(("Action", 0, lambda c:'<a href="remove/'+str(c.id)+'">remove from group</a>', None))
    args['baseurl'] = "?display="+display
    args['display'] = display
    args['objtypename'] = "contactgroup"
    args['query'] = q
    args['cols'] = cols
    args['cg'] = cg
    return query_print_entities(request, 'group_detail.html', args)


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_emails(request, id):
    cg = Query(ContactGroup).get(id)
    members = cg.members
    emails = []
    noemails = []
    for c in members:
        email = c.get_value_by_keyname("email")
        if email:
            emails.append((c, email))
        else:
            noemails.append(c)

    args = {}
    args['title'] = u"Emails for "+cg.name
    args['objtypename'] = "contactgroup"
    args['cg'] = cg
    args['emails'] = emails
    args['noemails'] = noemails
    return render_to_response('emails.html', args, RequestContext(request))


class ContactGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(required=False, widget=forms.Textarea)
    field_group = forms.BooleanField(required=False, help_text=u"Does that group yield specific fields to its members?")
    date = forms.DateField(required=False)
    budget_code = forms.CharField(required=False, max_length=10)
    direct_members = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("contacts", False))
    direct_subgroups = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget("groups", False))

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        
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
    objtypename = "contactgroup"
    if id:
        title = "Changing a "+objtypename
    else:
        title = "Adding a new "+objtypename
    
    if request.method == 'POST':
        form = ContactGroupForm(request.POST)
        if form.is_valid():
            # record the values

            if id:
                cg = Query(ContactGroup).get(id)
            else:
                cg = ContactGroup()
            data = form.clean()
            cg.name = data['name']
            cg.description = data['description']
            cg.field_group = data['field_group']
            cg.date = data['date']
            cg.budget_code = data['budget_code']
            
            # we need to add/remove people without destroying their admin flags
            new_member_ids = [ int(id) for id in data['direct_members']]
            print "WANTED MEMBERS=", new_member_ids
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

            # subgroups have no properties: just recreate the array with brute force
            cg.direct_subgroups = [ Query(ContactGroup).get(id) for id in form.clean()['direct_subgroups']]
            request.user.push_message(u"Group %s has been changed sucessfully!" % cg.name)
            
            if request.POST.get("_continue", None):
                return HttpResponseRedirect("/contactgroups/"+str(cg.id)+"/edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect("/contactgroups/add")
            else:
                return HttpResponseRedirect(reverse('ngw.gp.views.contactgroup_detail', args=(cg.id,)))

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
    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,}, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_remove(request, gid, cid):
    cig = Query(ContactInGroup).get((cid, gid))
    if not cig:
        return HttpResponse("Error, that contact is not a direct member. Please check subgroups")
    Session.delete(cig)
    request.user.push_message(u"%s has been removed for group %s." % (cig.contact.name, cig.group.name))
    return HttpResponseRedirect(reverse('ngw.gp.views.contactgroup_detail', args=(gid,)))


@http_authenticate(ngw_auth, 'ngw')
def contactgroup_delete(request, id):
    o = Query(ContactGroup).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.contactgroup_list'))# args=(p.id,)))


@http_authenticate(ngw_auth, 'ngw')
def contactingroup_edit(request, gid, cid):
    return HttpResponse("Not implemented")

#######################################################################
#
# Contact Fields
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def field_list(request):
    args = {}
    args['query'] = Query(ContactField).order_by([ContactField.c.sort_weight])
    args['cols'] = [
        ( "Name", None, "name", contact_field_table.c.name),
        ( "Type", None, "type_as_html", contact_field_table.c.type),
        ( "Only for", None, "contact_group", contact_field_table.c.contact_group_id),
        ( "Display group", None, "display_group", contact_field_table.c.display_group),
        #( "Move", None, lambda cf: "<a href="+str(cf.id)+"/moveup>Up</a> <a href="+str(cf.id)+"/movedown>Down</a>", None),
    ]
    args['title'] = "Select an optionnal field"
    args['objtypename'] = "contactfield"
    return query_print_entities(request, 'list.html', args)


@http_authenticate(ngw_auth, 'ngw')
def field_move_up(request, id):
    cf = Query(ContactField).get(id)
    cf.sort_weight -= 15
    Session.commit()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.gp.views.field_list'))

@http_authenticate(ngw_auth, 'ngw')
def field_move_down(request, id):
    cf = Query(ContactField).get(id)
    cf.sort_weight += 15
    Session.commit()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.gp.views.field_list'))

def field_renumber():
    new_weigth = 0
    for cf in Query(ContactField).order_by('sort_weight'):
        new_weigth += 10
        cf.sort_weight = new_weigth
    Session.commit()


class FieldEditForm(forms.Form):
    name = forms.CharField()
    hint = forms.CharField(required=False, widget=forms.Textarea)
    contact_group = forms.CharField(required=False, widget=forms.Select)
    type = forms.CharField(widget=forms.Select(choices=FIELD_TYPE_CHOICES), initial="")
    choicegroup = forms.CharField(required=False, widget=forms.Select)
    move_after = forms.IntegerField(widget=forms.Select())

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
    
        contacttypes = Query(ContactGroup).filter(ContactGroup.c.field_group==True)
        self.fields['contact_group'].widget.choices = [('', 'Everyone')] + [ (g.id, g.name) for g in contacttypes ]

        self.fields['type'].widget.attrs = { "onchange": "if (this.value=='"+FTYPE_CHOICE+"' || this.value=='"+FTYPE_MULTIPLECHOICE+"') { document.forms[0]['choicegroup'].disabled = 0; } else { document.forms[0]['choicegroup'].value = ''; document.forms[0]['choicegroup'].disabled = 1; }" }
    
        self.fields['choicegroup'].widget.choices = [('', '---')] + [(c.id, c.name) for c in Query(ChoiceGroup).order_by(ChoiceGroup.c.name)]
        #pprint (self.data)
        #pprint (self.initial)
       
        t = self.data.get("type", "") or self.initial.get('type', "")
        if t != FTYPE_CHOICE and t!=FTYPE_MULTIPLECHOICE:
            self.fields['choicegroup'].widget.attrs['disabled'] = 1
        else:
            if self.fields['choicegroup'].widget.attrs.has_key('disabled'):
                del self.fields['choicegroup'].widget.attrs['disabled']
        
        self.fields['choicegroup'].required = False
        
        self.fields['move_after'].widget.choices = [ (5, "Name") ] + [ (cf.sort_weight + 5, cf.name) for cf in Query(ContactField).order_by('sort_weight') ]


    def clean(self):
        if self.cleaned_data['type'] in (FTYPE_CHOICE, FTYPE_MULTIPLECHOICE) and self.cleaned_data['choicegroup'] == "":
            raise forms.ValidationError("You must select a choicegroup when for types choice")
        return self.cleaned_data

    def clean_name(self):
        name = self.cleaned_data['name']
        result = u""
        for c in name:
            if c==u"_" or c>=u"0" and c<=u"9" or c>=u"A" and c<=u"Z" or c>=u"a" and c<=u"z":
                result+=c
            else:
                result+="_"
        return result
        

@http_authenticate(ngw_auth, 'ngw')
def field_edit(request, id):
    objtypename = "contactfield"
    if id:
        title = "Changing a "+objtypename
    else:
        title = "Adding a new "+objtypename
    
    if id:
        cf = Query(ContactField).get(id)

    if request.method == 'POST':
        form = FieldEditForm(request.POST)
        if form.is_valid():
            data = form.clean()
            if not id:
                cf = ContactField()
            elif cf.type != data['type'] or unicode(cf.choice_group_id) != data['choicegroup']:
                deletion_details=[]
                if data['type'] in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_PHONE):
                    pass
                if data['type']==FTYPE_NUMBER:
                    for cfv in cf.values:
                        try:
                            int(cfv.value)
                        except ValueError:
                            deletion_details.append((cfv.contact, cfv))
                elif data['type']==FTYPE_DATE:
                    for cfv in cf.values:
                        try:
                            time.strptime(cfv.value, '%Y-%m-%d')
                        except ValueError:
                            deletion_details.append((cfv.contact, cfv))
                elif data['type']==FTYPE_EMAIL:
                    for cfv in cf.values:
                        try:
                            forms.EmailField().clean(cfv.value)
                        except forms.ValidationError:
                            deletion_details.append((cfv.contact, cfv))
                elif data['type']==FTYPE_RIB:
                    for cfv in cf.values:
                        try:
                            RibField().clean(cfv.value)
                        except forms.ValidationError:
                            deletion_details.append((cfv.contact, cfv))
                elif data['type']==FTYPE_CHOICE:
                    for cfv in cf.values:
                        choice_group_id = int(data['choicegroup'])
                        if not Query(Choice).filter(Choice.c.choice_group_id==choice_group_id).filter(Choice.c.key==cfv.value).count():
                            deletion_details.append((cfv.contact, cfv))
                elif data['type']==FTYPE_MULTIPLECHOICE:
                    for cfv in cf.values:
                        choice_group_id = int(data['choicegroup'])
                        for v in cfv.value.split(','):
                            if not Query(Choice).filter(Choice.c.choice_group_id==choice_group_id).filter(Choice.c.key==v).count():
                                deletion_details.append((cfv.contact, cfv))
                                break # stop parsing the other values, this is allready bad
                
                if deletion_details:
                    if request.POST.get('confirm', None):
                        for cfv in [ dd[1] for dd in deletion_details ]:
                            Session.delete(cfv)
                    else:
                        args={}
                        args['title'] = "Type incompatible with existing data"
                        args['objtypename'] = "contactfield"
                        args['id'] = id
                        args['cf'] = cf
                        args['deletion_details'] = deletion_details
                        for k in ( 'name', 'hint', 'contact_group', 'type', 'choicegroup', 'move_after'):
                            args[k] = data[k]
                        return render_to_response('type_change.html', args, RequestContext(request))
            cf.name = data['name']
            cf.hint = data['hint']
            if data['contact_group']:
                cf.contact_group_id = int(data['contact_group'])
            else:
                cf.contact_group_id = None
            cf.type = data['type']
            if data['choicegroup']:
                cf.choice_group_id = int(data['choicegroup'])
            else:
                cf.choice_group_id = None
            cf.sort_weight = int(data['move_after'])

            Session.commit()
            field_renumber()
            request.user.push_message(u"Field %s has been changed sucessfully." % cf.name)
            if request.POST.get("_continue", None):
                return HttpResponseRedirect("/contactfields/"+str(cf.id)+"/edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect("/contactfields/add")
            else:
                return HttpResponseRedirect(reverse('ngw.gp.views.field_list')) # args=(p.id,)))
        # else validation error
    else:
        if id: # modify
            initial = {}
            initial['name'] = cf.name
            initial['hint'] = cf.hint
            initial['contact_group'] = cf.contact_group_id
            initial['type'] = cf.type
            initial['choicegroup'] = cf.choice_group_id
            initial['move_after'] = cf.sort_weight-5
            form = FieldEditForm(initial=initial)
        else: # add
            form = FieldEditForm()


    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,}, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def field_delete(request, id):
    o = Query(ContactField).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.field_list'))


#######################################################################
#
# Choice groups
#
#######################################################################

@http_authenticate(ngw_auth, 'ngw')
def choicegroup_list(request):
    args = {}
    args['query'] = Query(ChoiceGroup)
    args['cols'] = [
        ( "Name", None, "name", ChoiceGroup.c.name),
        ( "Choices", None, lambda cg: ", ".join([html.escape(c[1]) for c in cg.ordered_choices]), None),
    ]
    args['title'] = "Select a choice group"
    args['objtypename'] = "choicegroup"
    return query_print_entities(request, 'list.html', args)


class ChoicesWidget(forms.MultiWidget):
    def __init__(self, ndisplay, attrs=None):
        widgets = []
        attrs_value = attrs or {}
        attrs_key = attrs or {}
        attrs_value['style'] = "width:90%"
        attrs_key['style'] = "width:9%; margin-left:1ex;"

        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs_value))
            widgets.append(forms.TextInput(attrs=attrs_key))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay
    def decompress(self, value):
        if value:
            return value.split(",")
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
            return ",".join(data_list)
        return None


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
            self.initial['possible_values'].append("")
            self.initial['possible_values'].append("")
            ndisplay+=1
        self.fields['possible_values'] = ChoicesField(required=False, widget=ChoicesWidget(ndisplay=ndisplay), ndisplay=ndisplay)

    def clean(self):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = self['possible_values']._data()
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
        #print "clean() OK"
        return self.cleaned_data


    def save(self, cg, request):
        if cg:
            oldid = cg.id
        else:
            cg = ChoiceGroup()
            oldid = None
        cg.name = self.clean()['name']
        cg.sort_by_key = self.clean()['sort_by_key']
        
        possibles_values = self['possible_values']._data()
        #print "possibles_values=", self.clean_possible_values()
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
    objtypename = "choicegroup"
    if id:
        title = "Changing a "+objtypename
        cg = Session.get(ChoiceGroup, id)
        #print cg
    else:
        title = "Adding a new "+objtypename
        cg = None

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, MultiValueDict_unicode(request.POST))
        if form.is_valid():
            cg = form.save(cg, request)
            if request.POST.get("_continue", None):
                return HttpResponseRedirect("/choicegroups/"+str(cg.id)+"/edit")
            elif request.POST.get("_addanother", None):
                return HttpResponseRedirect("/choicegroups/add")
            else:
                return HttpResponseRedirect(reverse('ngw.gp.views.choicegroup_list'))
    else:
        form = ChoiceGroupForm(cg)

    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,}, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def choicegroup_delete(request, id):
    o = Query(ChoiceGroup).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.choicegroup_list'))# args=(p.id,)))

