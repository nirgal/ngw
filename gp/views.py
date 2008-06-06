# -*- encoding: utf8 -*-

import copy, traceback
from pprint import pprint
from itertools import chain
from django.http import *
from django.utils.html import escape
from django.core.urlresolvers import reverse
from django import newforms as forms
from django.newforms.util import smart_unicode
from django.shortcuts import render_to_response
from ngw.gp.alchemy_models import *

ROOTGROUP_CONTACT=1
GROUP_PREFIX = '_group_'
DEFAULT_INITIAL_FIELDS=['name', 'email', 'phone_1', 'postal_code', 'city', 'birthdate', 'sex', 'GL', '_group_5']
NB_LINES_PER_PAGE=5


def name_internal2nice(txt):
    """
    Capitalize first letter and replace _ by spaces
    """
    txt = txt.replace('_', ' ')
    if len(txt)>0:
        txt = txt[0].upper() + txt[1:]
    return txt

def MultiValueDict_unicode(d):
    "Create a copy of the dict, converting to unicode when necessary"
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

def index(request):
    return render_to_response('index.html', {
        'title':'Action DB',
        'ncontacts': Query(Contact).count(),
    })

def generic_delete(request, o, next_url):
    objtypename = o.__class__.__name__.lower()
    title = "Please confirm deletetion"

    if not o:
        raise Http404()

    confirm = request.GET.get("confirm", "")
    if confirm:
        Session.delete(o)
        Session.commit()
        return HttpResponseRedirect(next_url)
    else:
        return render_to_response('delete.html', {'title':title, 'id':id, 'objtypename':objtypename, 'o': o})
        

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


def query_print_tables(request, q, title):
    
    # get sort column name
    sort_column_index = request.REQUEST.get("_sc", 0)
    try:
        sort_column_index=int(sort_column_index)
    except ValueError:
        sort_column_index = 0
    #print "sort_column_index =", sort_column_index
    count = 0
    for col in q.columns:
        sort_col = col
        if count == sort_column_index:
            break
        count += 1
    #print "sort_col=", sort_col

    sort_reverse = request.REQUEST.get("_sr", False)
    if sort_reverse:
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col)

    totalcount = Session.execute(q.alias().count()).fetchone()[0]

    page = request.REQUEST.get("_page", 1)
    try:
        page=int(page)
    except ValueError:
        page = 1
    
    q = q.limit(NB_LINES_PER_PAGE)
    q = q.offset(NB_LINES_PER_PAGE*(page-1))

    return render_to_response('test_query_tables.html', {'title': title, 'query': Session.execute(q), 'sc': sort_column_index, 'sr': sort_reverse, 'count': totalcount, 'page': page, 'npages': (totalcount+NB_LINES_PER_PAGE-1)/NB_LINES_PER_PAGE })



def testquery_tables(request):
    #q=select(columns=[contact_table.c.name, contact_field_value_table.c.value], from_obj=outerjoin(contact_table, contact_field_value_table, and_(contact_table.c.id==contact_field_value_table.c.contact_id, contact_field_value_table.c.contact_field_id==6))).offset(3)

    from_obj = contact_table
    columns = [ contact_table.c.name ]

    for fid in (6, 29, 33):
        a = contact_field_value_table.alias()
        columns.append(a.c.value.label("Field "+str(fid)))
        from_obj = outerjoin(from_obj, a, and_(contact_table.c.id==a.c.contact_id, a.c.contact_field_id==fid))

    q=select(columns=columns, from_obj=from_obj)

    return query_print_tables(request, q, "test query")



def query_print_entities(request, template_name, args):
    q = args['query']
    cols = args['cols']

    # get sort column name
    sort_column_index = request.REQUEST.get("_sc", 0)
    try:
        sort_column_index=int(sort_column_index)
    except ValueError:
        sort_column_index = 0
    print "sort_column_index =", sort_column_index
    sort_col = cols[sort_column_index][3]

    sort_reverse = request.REQUEST.get("_sr", 0)
    if sort_reverse=="1":
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col)

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
    args['sc'] = sort_column_index
    args['sr'] = sort_reverse
    args['count'] = totalcount
    args['page'] = page
    args['npages'] = (totalcount+NB_LINES_PER_PAGE-1)/NB_LINES_PER_PAGE

    if not args.has_key("baseurl"):
        args["baseurl"]="?"
    return render_to_response(template_name, args)



def testquery_entities(request):
    #q = Query(Contact).add_entity(ContactFieldValue).select_from(outerjoin(contact_table, contact_field_value_table, and_(contact_table.c.id==contact_field_value_table.c.contact_id, contact_field_value_table.c.contact_field_id==field_id)))

    q = Query(Contact)
    j = contact_table
    cols=[ ("name", 0, "name", contact_table.c.name), ]

    for field_id in (6, 29, 33, 32):
        a = contact_field_value_table.alias()
        q = q.add_entity(ContactFieldValue, alias=a)
        j = outerjoin(j, a, and_(contact_table.c.id==a.c.contact_id, a.c.contact_field_id==field_id ))
        cols.append(("field "+str(field_id), len(cols), "__unicode__", a.c.value))

    q = q.select_from(j)

    args={}
    args['title'] = "test query"
    args['query'] = q
    args['cols'] = cols
    return query_print_entities(request, 'test_query_entities.html', args)


#######################################################################
#
# Contacts
#
#######################################################################

def contact_make_query_with_fields(fields):
    q = Query(Contact)
    n_entities = 1
    j = contact_table
    cols=[]
    
    subgroups = {} 
    for prop in fields:
        if prop.startswith(GROUP_PREFIX):
            groupid = int(prop[len(GROUP_PREFIX):])
            cg = Query(ContactGroup).get(groupid)
            subgroups[groupid] = [ g.id for g in cg.self_and_subgroups ]
            print "subgroups[",groupid,"]=", subgroups[groupid]
            cols.append( (cg.name, 0, lambda c: c.str_member_of(subgroups[groupid]), None) )
        elif prop=="name":
            cols.append( ("name", 0, "name", contact_table.c.name) )
        else:
            cf = Query(ContactField).filter_by(name=prop).one()
            a = contact_field_value_table.alias()
            q = q.add_entity(ContactFieldValue, alias=a)
            j = outerjoin(j, a, and_(contact_table.c.id==a.c.contact_id, a.c.contact_field_id==cf.id ))
            cols.append( (cf.name, n_entities, "__unicode__", a.c.value) )
            n_entities += 1

    q = q.select_from(j)
    return q, cols


def contact_list(request):
    if request.GET.has_key('select'):
        select = request['select']
        fields = [ 'name' ] + select.split(',')
    else:
        fields = DEFAULT_INITIAL_FIELDS
    
    print "contact_list:", fields

    q, cols = contact_make_query_with_fields(fields)
    args={}
    args['title'] = "Contact list"
    args['objtypename'] = "contact"
    args['query'] = q
    args['cols'] = cols
    return query_print_entities(request, 'list_contact.html', args)



def format_contact_table(contacts, fields):
    keys = []
    subgroups = {} 
    for prop in fields:
        if prop.startswith(GROUP_PREFIX):
            groupid = int(prop[len(GROUP_PREFIX):])
            cg = Query(ContactGroup).get(groupid)
            keys.append(cg.name)
            subgroups[groupid] = [ g.id for g in cg.self_and_subgroups ]
            #print "subgroups[",groupid,"]=", subgroups[groupid]
        else:
            keys.append(name_internal2nice(prop))
        
    values = []
    for contact in contacts:
        newline = [  contact.id ]
        cgroups = None
        for prop in fields:
            if prop == 'name':
                newline.append(contact.name)
            elif prop.startswith(GROUP_PREFIX):
                groupid = int(prop[len(GROUP_PREFIX):])
                if cgroups == None: # Cache list
                    cgroups =  [ g.id for g in contact.direct_groups ]
                if groupid in cgroups:
                    newline.append("True")
                else:
                    member=False
                    for g in cgroups:
                        if g in subgroups[groupid]:
                            newline.append("True "+AUTOMATIC_MEMBER_INDICATOR)
                            member=True
                            break
                    if not member:
                        newline.append("False")
            else:
                cf = Query(ContactField).filter_by(name=prop).one()
                if cf.contact_group and cf.contact_group not in get_contacttypes(contact):
                    newline.append( "N/A" )
                else:
                    value = Query(ContactFieldValue).filter_by(contact_id=contact.id, contact_field_id=cf.id).first()
                    if value == None:
                        newline.append( "" )
                    else:
                        newline.append( unicode(value) )
                
        values.append( newline )
    return keys, values, Query(Contact).count()


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
        return output
        
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
        return result

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
        return self._make_filter(query, 'contact.name LIKE %(value_name1)s OR contact.name LIKE %(value_name2)s', value_name1=value+"%", value_name2="% "+value+"%")


class ContactSearchLineBaseField(ContactSearchLine):
    def __init__(self, form, xf, initial_check=False):
        ContactSearchLine.__init__(self, form, xf.name, name_internal2nice(xf.name), initial_check)
        self.xf = xf

    def _make_filter(self, query, where, **kargs):
        kargs['field_id'] = self.xf.id
        return ContactSearchLine._make_filter(self, query, where, **kargs)

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
        null_name = "NULL ("+Query(Choice).get((xf.choice_group.id, "")).value+")"
        self.operators.append(("NULL", null_name, False, self.filter_NULL))

    def add_fields(self, fields):
        ContactSearchLine.add_fields(self, fields)
        self.form.fields["_val_"+self.name] = forms.ChoiceField(required=False, choices=self.xf.choice_group.ordered_choices_no_default,  widget=forms.Select() )

        
class ContactSearchLineMultiChoice(ContactSearchLineBaseField):
    def __init__(self, *args, **kargs):
        ContactSearchLineBaseField.__init__(self, *args, **kargs)
        self.operators.append(("MULTIHAS", "Has", True, self.filter_MULTIHAS))

    def add_fields(self, fields):
        ContactSearchLine.add_fields(self, fields)
        self.form.fields["_val_"+self.name] = forms.ChoiceField(required=False, choices=self.xf.choice_group.ordered_choices_no_default,  widget=forms.Select() )
    
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

    def filter_AGE_GE(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND NOW() - value::DATE > \'%(value)i years\'::INTERVAL )', value=int(value))
        
    def filter_VALID_GT(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', value=int(value))
        
    def filter_FUTURE(self, query, value):
        return self._make_filter(query, 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )')
        

class ContactSearchLineGroup(ContactSearchLine):
    def __init__(self, form, group, initial_check=False):
        ContactSearchLine.__init__(self, form, GROUP_PREFIX + str(group.id), group.name, initial_check)
        self.group = group
        self.operators.append(("MEMBER", "Member", False, self.filter_MEMBER))
        self.operators.append(("NOTMEMBER", "Not member", False, self.filter_NOTMEMBER))
        self.operators.append(("DIRECTMEMBER", "Direct member", False, self.filter_DIRECTMEMBER))
    
    def filter_MEMBER(self, query, value):
        return query.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s))' % ",".join([str(g.id) for g in self.group.self_and_subgroups]))
    
    def filter_NOTMEMBER(self, query, value):
        return query.filter('NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s))' % ",".join([str(g.id) for g in self.group.self_and_subgroups]))
    
    def filter_DIRECTMEMBER(self, query, value):
        return query.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%d)' % self.group.id)

        
class ContactSearchForm(forms.Form):
    def __init__(self, data=None, auto_id='id_%s', prefix=None, initial=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)
        self.lines = []

        def addLine(self, line):
            self.lines.append(line)
            line.add_fields(self.fields)

        # Add name field, default to true
        #addLine(self, ContactSearchLine(self, 'name', 'Name', True))
        addLine(self, ContactSearchLineName(self))

        # Add all contact fields
        for cf in Query(ContactField).order_by('sort_weight'):
            initial_check = cf.name in DEFAULT_INITIAL_FIELDS
            if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_EMAIL, FTYPE_RIB):
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
        for g in Query(ContactGroup).filter(not_(ContactGroup.c.name.startswith("\\_"))):
            initial_check = GROUP_PREFIX+str(g.id) in DEFAULT_INITIAL_FIELDS
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
    
def contact_search(request):
    if request.method == 'POST':
        params = request.raw_post_data
    else:
        params = request.environ['QUERY_STRING']

    print "params=", params
    if params:
        form = ContactSearchForm(request.REQUEST)
        if form.is_valid():
            fields = []
            for kv in params.split("&"):
                k,v = kv.split('=',1)
                if k.startswith('_'):
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
    return render_to_response('search.html', { 'title':title, 'objtypename':objtypename, 'form':form})



def get_contacttypes(contact):
    """
    Returns all the CONTACT_TYPE subgroups of that contact.
    That's usefull to know which fields are in use.
    """

    root_contacttype = Query(ContactGroup).get(ROOTGROUP_CONTACT)
    contacttypeallids = [g.id for g in root_contacttype.self_and_subgroups ]
    #print "allids=", contacttypeallids

    contacttype_direct = []
    for g in contact.direct_groups:
        if g.id in contacttypeallids:
            contacttype_direct.append(g)
    #print "contacttype_direct=", contacttype_direct

    result = []
    for g in contacttype_direct:
        for sg in g.self_and_supergroups:
            if sg not in result:
                #print g, "=>", sg
                result.append(sg)
    return result


class ContactEditForm(forms.Form):
    name = forms.CharField()

    def __init__(self, contactid=None, data=None, auto_id='id_%s', prefix=None, initial=None, default_group=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)

        if contactid:
            contact = Query(Contact).get(contactid)
            contactgroupids = [ g.id for g in get_contacttypes(contact)] 
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
            if cf.type==FTYPE_TEXT:
                self.fields[cf.name] = forms.CharField(max_length=255, required=False, help_text=cf.hint)
            elif cf.type==FTYPE_LONGTEXT:
                self.fields[cf.name] = forms.CharField(widget=forms.Textarea, required=False, help_text=cf.hint)
            elif cf.type==FTYPE_NUMBER:
                self.fields[cf.name] = forms.IntegerField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_DATE:
                self.fields[cf.name] = forms.DateField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_EMAIL:
                self.fields[cf.name] = forms.EmailField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_RIB:
                self.fields[cf.name] = RibField(required=False, help_text=cf.hint)
            elif cf.type==FTYPE_CHOICE:
                self.fields[cf.name] = forms.CharField(max_length=255, required=False, help_text=cf.hint, widget=forms.Select(choices=cf.choice_group.ordered_choices))
            elif cf.type==FTYPE_MULTIPLECHOICE:
                self.fields[cf.name] = forms.MultipleChoiceField(required=False, help_text=cf.hint, choices=cf.choice_group.ordered_choices_no_default, widget=NgwCheckboxSelectMultiple())
        
        def contactgroupchoices():
            # sql "_" means "any character" and must be escaped
            return [ (g.id, g.name) for g in Query(ContactGroup).filter(not_(ContactGroup.c.name.startswith("\\_"))) ]

        self.fields['groups'] = forms.MultipleChoiceField(required=False, choices=contactgroupchoices())
        

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
        form = ContactEditForm(id, request.POST, default_group=default_group)
        if form.is_valid():
            # print "saving", repr(form.data)

            # record the values

            # 1/ In contact
            if id:
                contact = Query(Contact).get(id)
                contactgroupids = [ g.id for g in get_contacttypes(contact)]  # Need to keep a record of initial groups
                contact.name = form.clean()['name']
            else:
                contact = Contact(form.clean()['name'])
                default_group = form.clean().get('default_group', "") # Direct requested group
                if default_group:
                    default_group = int(default_group)
                    contactgroupids = [ g.id for g in Query(ContactGroup).get(default_group).self_and_supergroups ]
                else:
                    contactgroupids = [ ]

            newgroups = form.clean().get('groups', [])
            newgroups = Query(ContactGroup).filter(ContactGroup.c.id.in_(newgroups)).all()
            print "newgroups =", newgroups
            contact.direct_groups = newgroups
            
            # 2/ In ContactFields
            for cf in Query(ContactField):
                if cf.contact_group_id not in contactgroupids:
                    continue
                cfname = cf.name
                cfid = cf.id
                newvalue = form.clean()[cfname]
                if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_DATE, FTYPE_EMAIL, FTYPE_RIB, FTYPE_CHOICE):
                    newvalue = newvalue
                elif cf.type == FTYPE_MULTIPLECHOICE:
                    newvalue = ",".join(newvalue)
                    print "storing", repr(newvalue), "in", cfname
                elif cf.type==FTYPE_NUMBER:
                    newvalue = newvalue # store as a string for now
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
            Session.commit()
            if not request.POST.get("_continue", None):
                return HttpResponseRedirect(reverse('ngw.gp.views.contact_list')) # args=(p.id,)))
        # else /new/ or /change/ failed validation
    else: # GET /  HEAD
        initialdata = {}
        if id: # modify existing
            contact = Query(Contact).get(id)
            initialdata['groups'] = [ group.id for group in contact.direct_groups ]
            initialdata['name'] = contact.name
            form = ContactEditForm(id, initialdata)

            for cfv in contact.values:
                cf = cfv.field
                if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_DATE, FTYPE_EMAIL, FTYPE_RIB, FTYPE_CHOICE):
                    form.data[cf.name] = cfv.value
                elif cf.type==FTYPE_NUMBER:
                    form.data[cf.name] = cfv.value
                elif cf.type==FTYPE_MULTIPLECHOICE:
                    form.data[cf.name] = cfv.value.split(",")

        else:
            if 'default_group' in request.GET:
                default_group = request.GET['default_group']
                initialdata['default_group'] = default_group
                initialdata['groups'] = [ int(default_group) ]
                form = ContactEditForm(id, initial=initialdata, default_group=default_group )
            else:
                form = ContactEditForm(id)

    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})
    

def contact_delete(request, id):
    o = Query(Contact).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.contact_list'))



#######################################################################
#
# Contact Fields
#
#######################################################################

def field_list(request):
    keys = [
        'Name',
        'Type',
        'Only for',
        'Display group',
        'Move',
    ]
    values = []
    for cf in Query(ContactField).order_by([ContactField.c.sort_weight]):
        values += [(
            cf.id,
            cf.name,
            cf.repr_type(),
            cf.contact_group.id!=ROOTGROUP_CONTACT and cf.contact_group.name or "",
            cf.display_group,
            "<a href="+str(cf.id)+"/moveup>Up</a> <a href="+str(cf.id)+"/movedown>Down</a>",
        )]
    return render_to_response('list.html', {'title': "Select an optionnal field", 'objtypename':'contactfield', 'keys': keys, 'values':values })


def field_move_up(request, id):
    cf = Query(ContactField).get(id)
    cf.sort_weight -= 15
    Session.commit()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.gp.views.field_list'))

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
    type = forms.CharField(widget=forms.Select(choices=FIELD_TYPE_CHOICES), initial=ROOTGROUP_CONTACT,)
    choicegroup = forms.CharField(required=False, widget=forms.Select)
    move_after = forms.IntegerField(widget=forms.Select())

    def __init__(self, data=None, auto_id='id_%s', prefix=None, initial=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)
    
        contacttypes = Query(ContactGroup).get(ROOTGROUP_CONTACT).subgroups

        self.fields['contact_group'].widget.choices = [(ROOTGROUP_CONTACT, 'Everyone')] + [ (g.id, g.name) for g in contacttypes ]

        self.fields['type'].widget.attrs = { "onchange": "if (this.value=='"+FTYPE_CHOICE+"' || this.value=='"+FTYPE_MULTIPLECHOICE+"') { document.forms[0]['choicegroup'].disabled = 0; } else { document.forms[0]['choicegroup'].value = ''; document.forms[0]['choicegroup'].disabled = 1; }" }
    
        self.fields['choicegroup'].widget.choices = [('', '---')] + [(c.id, c.name) for c in Query(ChoiceGroup).select()]
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
        if self.clean_data['type'] in (FTYPE_CHOICE, FTYPE_MULTIPLECHOICE) and self.clean_data['choicegroup'] == "":
            raise forms.ValidationError("You must select a choicegroup when for types choice")
        return self.clean_data


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
            # TODO check new values are compatible with actual XFValues
            if not id:
                cf = ContactField()
            data = form.clean()
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
            Session.commit()
            if not request.POST.get("_continue", None):
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


    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})


def field_delete(request, id):
    o = Query(ContactField).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.field_list'))


#######################################################################
#
# Contact groups
#
#######################################################################

def contactgroup_list(request):
    keys = [
        'Name',
        'Direct members',
        'Direct subgroups',
        'Subgroups',
        'Members',
        'Description',
    ]
    values = []
    for cg in Query(ContactGroup):
        #print cg, repr(cg.members)
        values += [(
            cg.id,
            cg.name,
            u", ".join([c.name for c in cg.direct_contacts]),
            u", ".join([g.name for g in cg.direct_subgroups]),
            u", ".join([g.name for g in cg.subgroups]),
            u", ".join([c.name for c in cg.members]),
#            str(len(cg.members_all()))+"&nbsp;("+str(cg.contact_set.count())+"&nbsp;direct)",
            cg.description,
        )]
        #print "values =", values

    return render_to_response('list.html', {'title': "Select a contact group", 'objtypename':'contactgroup','keys':keys, 'values': values, 'totalcount': Query(ContactGroup).count() })


def contactgroup_detail(request, id):
    fields = DEFAULT_INITIAL_FIELDS
    cg = Query(ContactGroup).get(id)
    q, cols = contact_make_query_with_fields(fields)
    q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s))' % ",".join([str(g.id) for g in cg.self_and_subgroups]))
    args={}
    args['title'] = "Group "+cg.name
    args['objtypename'] = "contactgroup"
    args['query'] = q
    args['cols'] = cols
    args['cg'] = cg
    return query_print_entities(request, 'group_detail.html', args)


class ContactGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(required=False, widget=forms.Textarea)
    direct_members = forms.MultipleChoiceField(required=False)
    direct_subgroups = forms.MultipleChoiceField(required=False)

    def __init__(self, data=None, auto_id='id_%s', prefix=None, initial=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)
        
        self.fields['direct_members'].choices = [ (c.id, c.name) for c in Query(Contact).order_by([Contact.c.name]) ]
        self.fields['direct_subgroups'].choices = [ (g.id, g.name) for g in Query(ContactGroup).order_by([ContactGroup.c.name]) ]

    def flag_inherited_members(self, g):
        has_automembers = False
        choices = []
        subgroups = g.subgroups
        for c in Query(Contact).order_by(Contact.c.name):
            automember = False
            for sg in subgroups:
                if c in sg.direct_contacts:
                    automember = True
                    break
            flagname = c.name
            if automember:
                flagname += " "+AUTOMATIC_MEMBER_INDICATOR
                has_automembers = True
            choices.append( (c.id, flagname) )

        self.fields['direct_members'].choices = choices
        if has_automembers:
            help_text = AUTOMATIC_MEMBER_INDICATOR + " = Automatic members from " + ", ".join([ sg.name+" ("+str(len(sg.direct_contacts))+")" for sg in subgroups ]),
            self.fields['direct_members'].help_text = help_text


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
            cg.name = form.data['name']
            cg.description = form.data['description']
            
            # we need to add/remove people without destroying their admin flags
            new_member_ids = [ int(id) for id in form.clean()['direct_members']]
            #print "BEFORE, members=", cg.direct_contacts
            #print "WANTED MEMBERS=", new_member_ids
            for cid in new_member_ids:
                c = Query(Contact).get(cid)
                if not c in cg.direct_contacts:
                    #print "ADDING", c.name, "(", c.id, ") to group"
                    cg.direct_contacts.append(c)
            # Search members to remove:
            members_to_remove = []
            for c in cg.direct_contacts:
                print "Considering", c.name
                if c.id not in new_member_ids:
                    #print "REMOVING", c.name, "(", c.id, ") from group:", c.id, "not in", new_member_ids
                    members_to_remove.append(c)
            # Actually remove them
            for c in members_to_remove:
                    cg.direct_contacts.remove(c)
            #print "AFTER, members=", cg.direct_contacts

            # subgroups have no properties: just recreate the array with brute force
            cg.direct_subgroups = [ Query(ContactGroup).get(id) for id in form.clean()['direct_subgroups']]
            Session.commit()
            
            if not request.POST.get("_continue", None):
                return HttpResponseRedirect(reverse('ngw.gp.views.contactgroup_list')) # args=(p.id,)))

    else: # GET
        if id:
            cg = Query(ContactGroup).get(id)
            initialdata = {
                'name': cg.name,
                'description': cg.description,
                'direct_members': [ c.id for c in cg.direct_contacts ],
                'direct_subgroups': [ g.id for g in cg.direct_subgroups ],
            }
            
            form = ContactGroupForm(initialdata)
            form.flag_inherited_members(cg)
        else: # add new one
            form = ContactGroupForm()
    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})


def contactgroup_delete(request, id):
    o = Query(ContactGroup).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.contactgroup_list'))# args=(p.id,)))


#######################################################################
#
# Choice groups
#
#######################################################################
def choicegroup_list(request):
    keys = [
        'Name',
        'Choices',
    ]
    values = []
    for cg in Query(ChoiceGroup).order_by('name'):
        values += [(
            cg.id,
            cg.name,
            ", ".join([c[1] for c in cg.ordered_choices]),
        )]
    return render_to_response('list.html', {'title': "Select a choice group", 'objtypename':'choicegroup', 'keys': keys, 'values':values, 'totalcount': Query(ChoiceGroup).count() })


class ChoicesWidget(forms.MultiWidget):
    def __init__(self, ndisplay, attrs=None):
        widgets = []
        attrs_value = attrs or {}
        attrs_key = attrs or {}
        attrs_value['style'] = "width:90%"
        attrs_key['style'] = "width:9%; margin-left:1ex;"

        # first line is special: key editing is disabled
        attrs_key0 = copy.copy(attrs_key)
        attrs_key0['disabled'] = ""
        widgets.append(forms.TextInput(attrs=attrs_value))
        widgets.append(forms.TextInput(attrs=attrs_key0))

        for i in range(1, ndisplay):
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

    def __init__(self, cg=None, data=None, auto_id='id_%s', prefix=None, initial=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)
        nextra_display=3
        
        ndisplay=0
        self.initial['possible_values']=[]

        if cg:
            self.initial['name'] = cg.name
            self.initial['sort_by_key'] = cg.sort_by_key
            choices = cg.ordered_choices
            self.initial['possible_values'].append(choices[0][1])
            self.initial['possible_values'].append("Default")
            ndisplay+=1

            for c in choices[1:]:
                self.initial['possible_values'].append(c[1])
                self.initial['possible_values'].append(c[0])
                ndisplay+=1

        for i in range(nextra_display):
            self.initial['possible_values'].append("")
            self.initial['possible_values'].append("")
            ndisplay+=1
        self.fields['possible_values'] = ChoicesField(required=False, widget=ChoicesWidget(ndisplay=ndisplay), ndisplay=ndisplay)

    def clean(self):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = self['possible_values']._data()
        keys = []
        for i in range(1, len(possibles_values)/2):
            v,k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines without values
            if not k:
                continue # empty keys are ok
            if k in keys:
                raise forms.ValidationError("You cannot have two keys with the same value. Leave empty for automatic generation.")
            keys.append(k)
        #print "clean() OK"
        return self.clean_data


    def save(self, cg):
        if cg:
            oldid = cg.id
        else:
            cg = ChoiceGroup()
            oldid = None
        cg.name = self.clean()['name']
        cg.sort_by_key = self.clean()['sort_by_key']
        
        #Session.flush() # we'll need cg.id just bellow

        possibles_values = self['possible_values']._data()
        #print "possibles_values=", self.clean_possible_values()
        choices={"": possibles_values[0]} # default value

        # first ignore lines with empty keys, and update auto_key
        auto_key = 0
        for i in range(1,len(possibles_values)/2):
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
        for i in range(1,len(possibles_values)/2):
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
    
        Session.commit()
            
        
def choicegroup_edit(request, id=None):
    objtypename = "choicegroup"
    if id:
        title = "Changing a "+objtypename
        cg = Session.get(ChoiceGroup, id)
        print cg
    else:
        title = "Adding a new "+objtypename
        cg = None

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, MultiValueDict_unicode(request.POST))
        if form.is_valid():
            form.save(cg)
            if not request.POST.get("_continue", None):
                return HttpResponseRedirect(reverse('ngw.gp.views.choicegroup_list')) # args=(p.id,)))
    else:
        form = ChoiceGroupForm(cg)

    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})


def choicegroup_delete(request, id):
    o = Query(ChoiceGroup).get(id)
    return generic_delete(request, o, reverse('ngw.gp.views.choicegroup_list'))# args=(p.id,)))

