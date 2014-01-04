# -*- encoding: utf8 -*-

from datetime import *
from decoratedstr import remove_decoration
from copy import copy
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect, Http404
from django.utils.safestring import mark_safe
from django.utils import html
from django.shortcuts import render_to_response
from django.template import loader, RequestContext
from django.core.urlresolvers import reverse
from django import forms
#from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ngw.core.basicauth import login_required
from ngw.core.models import *
from ngw.core.widgets import NgwCalendarWidget, FilterMultipleSelectWidget
from ngw.core.nav import Navbar
from ngw.core.templatetags.ngwtags import ngw_display #FIXME: not nice to import tempate tags here
from ngw.core.mailmerge import ngw_mailmerge, ngw_mailmerge2
from ngw.core import contactsearch

from django.db.models.query import RawQuerySet, sql

DISP_NAME = u'name'
DISP_FIELD_PREFIX = u'field_'
DISP_GROUP_PREFIX = u'group_'

FTYPE_TEXT = 'TEXT'
FTYPE_LONGTEXT = 'LONGTEXT'
FTYPE_NUMBER = 'NUMBER'
FTYPE_DATE = 'DATE'
FTYPE_EMAIL = 'EMAIL'
FTYPE_PHONE = 'PHONE'
FTYPE_RIB = 'RIB'
FTYPE_CHOICE = 'CHOICE'
FTYPE_MULTIPLECHOICE = 'MULTIPLECHOICE'
FTYPE_PASSWORD = 'PASSWORD'

#######################################################################
#
# Login / Logout
#
#######################################################################

def ngw_base_url(request):
    if os.environ.has_key('HTTPS'):
        scheme = 'https'
    else:
        scheme = 'http'
    #FIXME empty scheme is enough, remove that
    return scheme+'://'+request.META['HTTP_HOST']+'/'


def logout(request):
    #need to call auth_logout(request) when using auth contrib module
    return render_to_response('message.html', {'message': mark_safe('Have a nice day!<br><a href="' + ngw_base_url(request) + '">Login again</a>') }, RequestContext(request))


# decorator for requests
class require_group:
    def __init__(self, required_group):
        self.required_group = required_group
    def __call__(self, func):
        def wrapped(*args, **kwargs):
            request = args[0]
            try:
                user = request.user
            except AttributeError:
                return unauthorized(request)
            if not user.is_member_of(self.required_group):
                return unauthorized(request)
            return func(*args, **kwargs)
        return wrapped


def get_display_fields(user):
    # check the field still exists
    result = []
    default_fields = user.get_fieldvalue_by_id(FIELD_COLUMNS)
    if not default_fields:
        default_fields = Config.objects.get(pk='columns')
        if default_fields:
            default_fields = default_fields.text
    if not default_fields:
        default_fields = u''
    for fname in default_fields.split(u','):
        if fname == u'name':
            pass
        elif fname.startswith(DISP_GROUP_PREFIX):
            try:
                groupid = int(fname[len(DISP_GROUP_PREFIX):])
            except ValueError:
                print 'Error in default fields: %s has invalid syntax.' % fname.encode('utf8')
                continue
            try:
                ContactGroup.objects.get(pk=groupid)
            except ContactGroup.DoesNotExist:
                print 'Error in default fields: There is no group #%d.' % groupid
                continue
        elif fname.startswith(DISP_FIELD_PREFIX):
            try:
                fieldid = int(fname[len(DISP_FIELD_PREFIX):])
            except ValueError:
                print 'Error in default fields: %s has invalid syntax.' % fname.encode('utf8')
                continue
            try:
                ContactField.objects.get(pk=fieldid)
            except ContactField.DoesNotExist:
                print 'Error in default fields: There is no field #%d.' % fieldid
                continue
        else:
            print 'Error in default fields: Invalid syntax in "%s".' % fname.encode('utf8')
            continue
        result.append(fname)
    if not result:
        result = [ DISP_NAME ]
    return result


def unauthorized(request):
    return HttpResponseForbidden(
        loader.render_to_string('message.html',{
            'message': 'Sorry. You are not authorized to browse that page.'},
            RequestContext(request)))

#######################################################################
#
# Home
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def home(request):
    operator_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.group_id = contact_group.id AND contact_in_group.contact_id=%s AND operator)' % request.user.id])
    return render_to_response('home.html', {
        'title': 'Home page',
        'nav': Navbar(),
        'operator_groups': operator_groups,
        'news': ContactGroupNews.objects.filter(contact_group_id=GROUP_ADMIN)[:5],
        'GroupAdmin': ContactGroup.objects.get(id=GROUP_ADMIN),
    }, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def test(request):
    args = {
        'title': 'Test',
        'env': os.environ,
        'objtype': Contact,
    }
    #raise Exception(u'Boum')
    return render_to_response('test.html', args, RequestContext(request))


########################################################################
#
# Generic views
#
########################################################################

def query_print_entities(request, template_name, args, extrasort=None):
    try:
        object_query_page_length = Config.objects.get(pk=u'query_page_length')
        NB_LINES_PER_PAGE = int(object_query_page_length.text)
    except (Config.DoesNotExist, ValueError):
        NB_LINES_PER_PAGE = 200

    q = args['query']
    cols = args['cols']

    # get sort column name
    nosort = False
    order = request.REQUEST.get('_order', u'')

    if order or not extrasort:
        # disable default sort on column 0 if there's an extrasort parameter
        try:
            intorder = int(order)
        except ValueError:
            if extrasort:
                order = u''
                nosort = True
            else:
                order = u'0'
                intorder = 0
        if not nosort:
            sort_col = cols[abs(intorder)][3]
            if not order or order[0] != '-':
                q = q.order_by(sort_col)
            else:
                q = q.order_by('-'+sort_col)
    else: # no order and extrasort
        order = u''
    if extrasort:
        q = extrasort(q)

    totalcount = q.count()

    page = request.REQUEST.get('_page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1
    q = q[NB_LINES_PER_PAGE*(page-1):NB_LINES_PER_PAGE*page]

    args['query'] = q
    args['cols'] = cols
    args['order'] = order
    args['count'] = totalcount
    args['page'] = page
    args['npages'] = (totalcount+NB_LINES_PER_PAGE-1)/NB_LINES_PER_PAGE

    if not args.has_key('baseurl'):
        args['baseurl'] = '?'
    return render_to_response(template_name, args, RequestContext(request))


# Helper function that is never call directly, hence the lack of authentification check
def generic_delete(request, o, next_url, base_nav=None, ondelete_function=None):
    if not request.user.is_admin():
        return unauthorized(request)

    title = u'Please confirm deletetion'

    if not o:
        raise Http404()

    confirm = request.GET.get('confirm', u'')
    if confirm:
        if ondelete_function:
            ondelete_function(o)
        name = unicode(o)
        log = Log()
        log.contact_id = request.user.id
        log.action = LOG_ACTION_DEL
        pk_names = (o._meta.pk.attname,) # default django pk name
        log.target = unicode(o.__class__.__name__)+u' '+u' '.join([unicode(o.__getattribute__(fieldname)) for fieldname in pk_names])
        log.target_repr = o.get_class_verbose_name()+u' '+name
        o.delete()
        log.save()
        messages.add_message(request, messages.SUCCESS, u'%s has been deleted sucessfully!' % name)
        return HttpResponseRedirect(next_url)
    else:
        nav = base_nav or Navbar(o.get_class_navcomponent())
        nav.add_component(o.get_navcomponent())
        nav.add_component(u'delete')
        return render_to_response('delete.html', {'title':title, 'o': o, 'nav': nav}, RequestContext(request))



#######################################################################
#
# Logs
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
@require_group(GROUP_ADMIN)
def logs(request):
    if not request.user.is_admin():
        return unauthorized(request)

    args = {}
    args['title'] = 'Global log'
    args['nav'] = Navbar(Log.get_class_navcomponent())
    args['objtype'] = Log
    args['query'] = Log.objects.all()
    args['cols'] = [
        ( 'Date GMT', None, 'small_date', 'dt'),
        ( 'User', None, 'contact', 'contact__name'),
        ( 'Action', None, 'action_txt', 'action'),
        ( 'Target', None, 'target_repr', 'target_repr'),
        ( 'Property', None, 'property_repr', 'property_repr'),
        ( 'Change', None, 'change', 'change'),
    ]
    return query_print_entities(request, 'list_log.html', args)

#######################################################################
#
# Contacts
#
#######################################################################

def membership_to_text(contact_with_extra_fields, group_id):
    # memberships = []
    # if getattr(contact_with_extra_fields, 'group_%s_m' % group_id):
    #     memberships.append(u"Member")
    # if getattr(contact_with_extra_fields, 'group_%s_i' % group_id):
    #     memberships.append(u"Invited")
    # if getattr(contact_with_extra_fields, 'group_%s_d' % group_id):
    #     memberships.append(u"Declined")
    # if getattr(contact_with_extra_fields, 'group_%s_M' % group_id):
    #     memberships.append(u"Member" + u" " + AUTOMATIC_MEMBER_INDICATOR)
    # if getattr(contact_with_extra_fields, 'group_%s_I' % group_id):
    #     memberships.append(u"Invited" + u" " + AUTOMATIC_MEMBER_INDICATOR)
    # if getattr(contact_with_extra_fields, 'group_%s_D' % group_id):
    #     memberships.append(u"Declined" + u" " + AUTOMATIC_MEMBER_INDICATOR)
    # return u", ".join(memberships)
    if getattr(contact_with_extra_fields, 'group_%s_m' % group_id):
        return u"Member"
    if getattr(contact_with_extra_fields, 'group_%s_i' % group_id):
        return u"Invited"
    if getattr(contact_with_extra_fields, 'group_%s_d' % group_id):
        return u"Declined"
    if getattr(contact_with_extra_fields, 'group_%s_M' % group_id):
        return u"Member" + u" " + AUTOMATIC_MEMBER_INDICATOR
    if getattr(contact_with_extra_fields, 'group_%s_I' % group_id):
        return u"Invited" + u" " + AUTOMATIC_MEMBER_INDICATOR
    return u''



def membership_extended_widget(contact_with_extra_fields, contact_group, base_url):
    attrib_prefix = 'group_%s_' % contact_group.id
    member = getattr(contact_with_extra_fields, attrib_prefix+'m')
    invited = getattr(contact_with_extra_fields, attrib_prefix+'i')
    declined = getattr(contact_with_extra_fields, attrib_prefix+'d')
    note = getattr(contact_with_extra_fields, attrib_prefix+'note')

    params = {}
    params['cid'] = contact_with_extra_fields.id
    params['membership_str'] = membership_to_text(contact_with_extra_fields, contact_group.id)
    if note:
        params['note'] = u'<br>'+html.escape(note)
    else:
        params['note'] = u''
    params['membership_url'] = contact_group.get_absolute_url()+u'members/'+unicode(contact_with_extra_fields.id)+u'/membership'
    params['title'] = contact_with_extra_fields.name+u' in group '+contact_group.unicode_with_date()
    params['base_url'] = base_url

    if member:
        params['is_member_checked'] = u' checked'
    else:
        params['is_member_checked'] = u''
    if invited:
        params['is_invited_checked'] = u' checked'
    else:
        params['is_invited_checked'] = u''
    if declined:
        params['has_declined_invitation_checked'] = u' checked'
    else:
        params['has_declined_invitation_checked'] = u''

    return  u'<a href="javascript:show_membership_extrainfo(%(cid)d)">%(membership_str)s</a>%(note)s<div class=membershipextra id="membership_%(cid)d"><a href="javascript:show_membership_extrainfo(null)"><img src="/close.png" alt=close width=10 height=10 style="position:absolute; top:0px; right:0px;"></a>%(title)s<br><form action="%(cid)d/membershipinline" method=post><input type=hidden name="next_url" value="../../members/%(base_url)s"><input type=radio name=membership value=invited id="contact_%(cid)d_invited" %(is_invited_checked)s onclick="this.form.submit()"><label for="contact_%(cid)d_invited">Invited</label><input type=radio name=membership value=member id="contact_%(cid)d_member" %(is_member_checked)s onclick="this.form.submit()"><label for="contact_%(cid)d_member">Member</label><input type=radio name=membership value=declined_invitation id="contact_%(cid)d_declined_invitation" %(has_declined_invitation_checked)s onclick="this.form.submit()"><label for="contact_%(cid)d_declined_invitation"> Declined invitation</label><br><a href="%(membership_url)s">More...</a> | <a href="javascript:show_membership_extrainfo(null)">Close</a></form></div>' % params



class ContactQuerySet(RawQuerySet):
    def __init__(self, *args, **kargs):
        super(ContactQuerySet, self).__init__('', *args, **kargs)
        self.qry_fields = {'id':'contact.id', 'name':'name'}
        self.qry_from = ['contact']
        self.qry_where = []
        self.qry_orderby = []

    def add_field(self, fieldid):
        fieldid = str(fieldid)
        self.qry_from.append('LEFT JOIN contact_field_value AS cfv%(fid)s ON (contact.id = cfv%(fid)s.contact_id AND cfv%(fid)s.contact_field_id = %(fid)s)' % {'fid':fieldid})
        self.qry_fields[DISP_FIELD_PREFIX+fieldid] = 'cfv%(fid)s.value' % {'fid':fieldid}

    def add_group(self, group_id):
        # TODO: crashes if group is there more than one (viewed from a group with that group selected as a field)
        # Add fields for direct membership
        self.qry_fields['group_%s_m' % group_id] = 'cig_%s.member' % group_id
        self.qry_fields['group_%s_i' % group_id] = 'cig_%s.invited' % group_id
        self.qry_fields['group_%s_d' % group_id] = 'cig_%s.declined_invitation' % group_id
        self.qry_from.append('LEFT JOIN contact_in_group AS cig_%(gid)s ON (contact.id = cig_%(gid)s.contact_id AND cig_%(gid)s.group_id=%(gid)s)' % {'gid': group_id})

        # Add fields for indirect membership
        self.qry_fields['group_%s_M' % group_id] = "EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(gid)s)) AND contact_in_group.group_id <> %(gid)s AND member)" % { 'gid': group_id }
        self.qry_fields['group_%s_I' % group_id] = "EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(gid)s)) AND contact_in_group.group_id <> %(gid)s AND invited)" % { 'gid': group_id }
        self.qry_fields['group_%s_D' % group_id] = "EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(gid)s)) AND contact_in_group.group_id <> %(gid)s AND declined_invitation)" % { 'gid': group_id }

    def add_group_withnote(self, group_id):
        self.add_group(group_id)
        self.qry_fields['group_%s_note' % group_id] = 'cig_%s.note' % group_id

    def filter(self, extrawhere):
        self.qry_where.append(extrawhere)
        return self

    def add_params(self, params):
        if self.params:
            self.params.update(params)
        else:
            self.params = params
        return self

    def order_by(self, name):
        self.qry_orderby.append(name)
        return self

    def compile(self):
        qry = 'SELECT '
        qry += ', '.join(['%s AS "%s"' % (v, k) for k, v in self.qry_fields.iteritems()])
        qry += ' FROM ' + ' '.join(self.qry_from)
        if self.qry_where:
            qry += ' WHERE ( ' + ') AND ('.join(self.qry_where) + ' )'
        if self.qry_orderby:
            order = []
            for by in self.qry_orderby:
                if by[0] == '-':
                    order.append(by[1:]+' DESC')
                else:
                    order.append(by)
            qry += ' ORDER BY ' + ', '.join(order)

        self.raw_query = qry
        self.query = sql.RawQuery(sql=qry, using=self.db, params=self.params)

    def count(self):
        qry = 'SELECT '
        qry += ', '.join(['%s AS %s' % (v, k) for k, v in self.qry_fields.iteritems()])
        qry += ' FROM ' + ' '.join(self.qry_from)
        if self.qry_where:
            qry += ' WHERE (' + ') AND ('.join(self.qry_where) + ')'

        countqry = 'SELECT COUNT(*) FROM ('+qry+') AS qry_count'
        for count, in sql.RawQuery(sql=countqry, using=self.db, params=self.params):
            return count

    def __iter__(self):
        self.compile()
        #print repr(self.raw_query), repr(self.params)
        for x in RawQuerySet.__iter__(self):
            yield x


def contact_make_query_with_fields(fields, current_cg=None, base_url=None, format=u'html'):
    q = ContactQuerySet(Contact._default_manager.model, using=Contact._default_manager._db)
    cols = []

    for prop in fields:
        if prop == u'name':
            if format == u'html':
                cols.append( (u'Name', None, 'name_with_relative_link', 'name') )
            else:
                cols.append( (u'Name', None, '__unicode__', 'name') )
        elif prop.startswith(DISP_GROUP_PREFIX):
            groupid = int(prop[len(DISP_GROUP_PREFIX):])
            cg = ContactGroup.objects.get(pk=groupid)
            q.add_group(groupid)
            #cols.append( ('group_%s_m' % groupid, None, 'group_%s_m' % groupid, None))
            #cols.append( ('group_%s_i' % groupid, None, 'group_%s_i' % groupid, None))
            #cols.append( ('group_%s_d' % groupid, None, 'group_%s_d' % groupid, None))
            #cols.append( ('group_%s_M' % groupid, None, 'group_%s_M' % groupid, None))
            #cols.append( ('group_%s_I' % groupid, None, 'group_%s_I' % groupid, None))
            #cols.append( ('group_%s_D' % groupid, None, 'group_%s_D' % groupid, None))
            cols.append( (cg.name, None, lambda c: membership_to_text(c, groupid), None) )

        elif prop.startswith(DISP_FIELD_PREFIX):
            fieldid = prop[len(DISP_FIELD_PREFIX):]

            q.add_field(fieldid)

            cf = ContactField.objects.get(pk=fieldid)
            if format == u'html':
                cols.append( (cf.name, cf.format_value_html, prop, prop) )
            else:
                cols.append( (cf.name, cf.format_value_unicode, prop, prop) )
        else:
            raise ValueError(u'Invalid field '+prop)

    if current_cg is not None:
        assert base_url
        q.add_group_withnote(current_cg.id)
        if format == u'html':
            cols.append( ('Status', None, lambda c: membership_extended_widget(c, current_cg, base_url), None) )
        else:
            cols.append( ('Status', None, lambda c: membership_to_text(c, current_cg.id), None) )
            cols.append( ('Note', None, 'group_%s_note' % current_cg.id, None) )
    return q, cols


def get_available_fields():
    result = [ (DISP_NAME, u'Name') ]
    for cf in ContactField.objects.order_by('sort_weight'):
        result.append((DISP_FIELD_PREFIX+unicode(cf.id), cf.name))
    for cg in ContactGroup.objects.order_by('-date', 'name'):
        result.append((DISP_GROUP_PREFIX+unicode(cg.id), cg.unicode_with_date()))
    return result


class FieldSelectForm(forms.Form):
    def __init__(self, *args, **kargs):
        #TODO: param user -> fine tuned fields selection
        forms.Form.__init__(self, *args, **kargs)
        self.fields[u'selected_fields'] = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget('Fields', False), choices=get_available_fields())


@login_required()
@require_group(GROUP_USER_NGW)
def contact_list(request):
    if not request.user.is_admin():
        return unauthorized(request)

    strfilter = request.REQUEST.get(u'filter', u'')
    filter = contactsearch.parse_filterstring(strfilter)
    baseurl = u'?filter='+strfilter

    strfields = request.REQUEST.get(u'fields', None)
    if strfields:
        fields = strfields.split(u',')
        baseurl += '&fields='+strfields
    else:
        fields = get_display_fields(request.user)
        strfields = u','.join(fields)

    if (request.REQUEST.get(u'savecolumns')):
        request.user.set_fieldvalue(request.user, FIELD_COLUMNS, strfields)

    #print 'contact_list:', fields
    q, cols = contact_make_query_with_fields(fields, format=u'html')
    q = filter.apply_filter_to_query(q)

    args = {}
    args['title'] = u'Contact list'
    args['baseurl'] = baseurl
    args['objtype'] = Contact
    args['nav'] = Navbar(args['objtype'].get_class_absolute_url().split(u'/')[1])
    args['query'] = q
    args['cols'] = cols
    args['filter'] = strfilter
    args['fields'] = strfields
    args['fields_form'] = FieldSelectForm(initial={u'selected_fields': fields})

    return query_print_entities(request, 'list_contact.html', args)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_detail(request, gid=None, cid=None):
    cid = int(cid)
    if cid != request.user.id and not request.user.is_admin():
        return unauthorized(request)
    try:
        c = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()

    rows = []
    for cf in c.get_allfields():
        try:
            cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            rows.append((cf.name, mark_safe(cfv.as_html())))
        except ContactFieldValue.DoesNotExist:
            pass

    args = {}
    args['title'] = u'Details for '+unicode(c)
    if gid:
        cg = ContactGroup.objects.get(pk=gid)
        #args['title'] += u' in group '+cg.unicode_with_date()
        args['contact_group'] = cg
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component(u'members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(c.get_navcomponent())
    args['objtype'] = Contact
    args['contact'] = c
    args['rows'] = rows
    return render_to_response('contact_detail.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_vcard(request, gid=None, cid=None):
    cid = int(cid)
    if cid != request.user.id and not request.user.is_admin():
        return unauthorized(request)
    try:
        c = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    return HttpResponse(c.vcard().encode('utf-8'), mimetype='text/x-vcard')



class ContactEditForm(forms.Form):
    name = forms.CharField()

    def __init__(self, request_user, id=None, contactgroup=None, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        contactid = id # FIXME

        if contactid:
            try:
                contact = Contact.objects.get(pk=contactid)
            except Contact.DoesNotExist:
                raise Http404()
            fields = contact.get_allfields()
        elif contactgroup:
            contactgroupids = [ g.id for g in contactgroup.get_self_and_supergroups() ]
            fields = ContactField.objects.filter(contact_group_id__in = contactgroupids).order_by('sort_weight')
        else:
            field = [ ]

        # Add all extra fields
        for cf in fields:
            f = cf.get_form_fields()
            if f:
                self.fields[unicode(cf.id)] = f

        #if request_user.is_admin():
        #    # sql '_' means 'any character' and must be escaped: g in Query(ContactGroup).filter(not_(ContactGroup.name.startswith('\\_'))).order_by ...
        #    contactgroupchoices = [ (g.id, g.unicode_with_date()) for g in Query(ContactGroup).order_by(ContactGroup.date.desc(), ContactGroup.name) ]
        #    self.fields['groups'] = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget('Group', False), choices=contactgroupchoices)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_edit(request, gid=None, cid=None):
    if cid: # edit existing contact
        cid = int(cid)
        if cid != request.user.id and not request.user.is_admin():
            return unauthorized(request)
    else: # add
        if not request.user.is_admin():
            return unauthorized(request)
        assert gid, 'Missing required parameter groupid'

    if gid: # edit/add in a group
        try:
            cg = ContactGroup.objects.get(pk=gid)
        except ContactGroup.DoesNotExist:
            raise Http404()
    else: # edit out of a group
        cg = None

    objtype = Contact
    if cid:
        try:
            contact = Contact.objects.get(pk=cid)
        except Contact.DoesNotExist:
            raise Http404()
        title = u'Editing '+unicode(contact)
    else:
        title = u'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactEditForm(id=cid, data=request.POST, contactgroup=cg, request_user=request.user) # FIXME
        if form.is_valid():
            data = form.clean()
            #print 'saving', repr(form.data)

            # record the values

            # 1/ In contact
            if cid:
                if contact.name != data['name']:
                    log = Log(contact_id=request.user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = u'Contact '+unicode(contact.id)
                    log.target_repr = u'Contact '+contact.name
                    log.property = u'Name'
                    log.property_repr = u'Name'
                    log.change = u'change from '+contact.name+u' to '+data['name']
                    log.save()

                contact.name = data['name']
                contact.save()

                fields = contact.get_allfields() # Need to keep a record of initial groups

            else:
                contact = Contact(name=data['name'])
                contact.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_ADD
                log.target = u'Contact '+unicode(contact.id)
                log.target_repr = u'Contact '+contact.name
                log.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'Contact '+unicode(contact.id)
                log.target_repr = u'Contact '+contact.name
                log.property = u'Name'
                log.property_repr = u'Name'
                log.change = u'new value is '+contact.name
                log = Log(request.user.id)

                cig = ContactInGroup(contact_id=contact.id, group_id=gid)
                cig.member = True
                cig.save()
                # TODO: Log

                contactgroupids = [ g.id for g in cg.get_self_and_supergroups() ]
                fields = ContactField.objects.filter(contact_group_id__in = contactgroupids).order_by('sort_weight')

            # 2/ In ContactFields
            for cf in fields:
                if cf.type == FTYPE_PASSWORD:
                    continue
                #cfname = cf.name
                cfid = cf.id
                newvalue = data[unicode(cfid)]
                if newvalue != None:
                    newvalue = cf.formfield_value_to_db_value(newvalue)
                contact.set_fieldvalue(request.user, cf, newvalue)
            messages.add_message(request, messages.SUCCESS, u'Contact %s has been saved sucessfully!' % contact.name)

            if cg:
                base_url = cg.get_absolute_url()+u'members/'+unicode(contact.id)+u'/'
            else:
                base_url = contact.get_class_absolute_url()+unicode(contact.id)+u'/'

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(base_url+u'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(base_url+u'../add')
            elif request.user.is_admin(): # FIXME can read user list is better
                return HttpResponseRedirect(base_url)
            else:
                return HttpResponseRedirect(u'/')

        # else add/update failed validation
    else: # GET /  HEAD
        initialdata = {}
        if cid: # modify existing
            initialdata['name'] = contact.name

            for cfv in contact.values.all():
                cf = cfv.contact_field
                if cf.type != FTYPE_PASSWORD:
                    initialdata[unicode(cf.id)] = cf.db_value_to_formfield_value(cfv.value)
            form = ContactEditForm(id=cid, initial=initialdata, request_user=request.user, contactgroup=cg)

        else:
            for cf in ContactField.objects.all():
                if cf.default:
                    if cf.type == FTYPE_DATE and cf.default == u'today':
                        initialdata[unicode(cf.id)] = date.today()
                    else:
                        initialdata[unicode(cf.id)] = cf.db_value_to_formfield_value(cf.default)

            if cg:
                initialdata['groups'] = [ cg.id ]
                form = ContactEditForm(id=cid, initial=initialdata, contactgroup=cg, request_user=request.user)
            else:
                form = ContactEditForm(id=cid, request_user=request.user)

    args = {}
    args['form'] = form
    args['title'] = title
    args['id'] = cid
    args['objtype'] = objtype
    if gid:
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component(u'members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    if cid:
        args['nav'].add_component(contact.get_navcomponent())
        args['nav'].add_component(u'edit')
    else:
        args['nav'].add_component(u'add')
    if cid:
        args['o'] = contact

    return render_to_response('edit.html', args, RequestContext(request))


class ContactPasswordForm(forms.Form):
    new_password = forms.CharField(max_length=50, widget=forms.PasswordInput())
    confirm_password = forms.CharField(max_length=50, widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', u'') != self.cleaned_data.get('confirm_password', u''):
            raise forms.ValidationError('The passwords must match!')
        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass(request, gid=None, cid=None):
    if gid is not None:
        gid = int(gid)
    cid = int(cid)
    if cid != request.user.id and not request.user.is_admin():
        return unauthorized(request)
    try:
        contact = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    args = {}
    args['title'] = 'Change password'
    args['contact'] = contact
    if request.method == 'POST':
        form = ContactPasswordForm(request.POST)
        if form.is_valid():
            # record the value
            password = form.clean()['new_password']
            contact.set_password(request.user, password)
            messages.add_message(request, messages.SUCCESS, u'Password has been changed sucessfully!')
            if gid:
                cg = ContactGroup.objects.get(pk=gid)
                return HttpResponseRedirect(cg.get_absolute_url()+u'members/'+unicode(cid)+u'/')
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else: # GET
        form = ContactPasswordForm()
    args['form'] = form
    if gid:
        cg = ContactGroup.objects.get(pk=gid)
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component(u'members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component(u'password')
    try:
        args['PASSWORD_LETTER'] = settings.PASSWORD_LETTER
    except AttributeError:
        pass # it's ok not to have a letter
    return render_to_response('password.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER) # not GROUP_USER_NGW
def hook_change_password(request):
    newpassword_plain = request.POST.get(u'password')
    if not newpassword_plain:
        return HttpResponse(u'Missing password POST parameter')
    #TODO: check strength
    request.user.set_password(request.user, newpassword_plain)
    return HttpResponse('OK')


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass_letter(request, gid=None, cid=None):
    if gid is not None:
        gid = int(gid)
    cid = int(cid)
    if cid != request.user.id and not request.user.is_admin():
        return unauthorized(request)
    try:
        contact = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    args = {}
    args['title'] = 'Generate a new password and print a letter'
    args['contact'] = contact
    if gid:
        try:
            cg = ContactGroup.objects.get(pk=gid)
        except ContactGroup.DoesNotExist:
            raise Http404()
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component(u'members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component(u'password letter')

    if request.method == 'POST':
        new_password = Contact.generate_password()

        # record the value
        contact.set_password(request.user, new_password, u'2') # Generated and mailed
        messages.add_message(request, messages.SUCCESS, u'Password has been changed sucessfully!')

        fields = {}
        for cf in contact.get_allfields():
            try:
                cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            except ContactFieldValue.DoesNotExist:
                continue
            fields[cf.name] = unicode(cfv).replace(u'\r', u'')
            #if cfv:
            #    rows.append((cf.name, mark_safe(cfv.as_html())))
        fields['name'] = contact.name
        fields['password'] = new_password

        result = ngw_mailmerge2('/usr/lib/ngw/mailing/forms/welcome2.odt', fields)
        if not result:
            return HttpResponse('File generation failed')

        filename = os.path.basename(result)
        if subprocess.call(['sudo', '/usr/bin/mvoomail', filename, '/usr/lib/ngw/mailing/generated/']):
            return HttpResponse('File move failed')

        #if gid:
        #    cg = Query(ContactGroup).get(gid)
        #    return HttpResponseRedirect(cg.get_absolute_url()+u'members/'+unicode(cid)+u'/')
        #else:
        #    return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))

        url = ngw_base_url(request) + 'mailing-generated/' + filename
        html_message = 'File generated in <a href="%(url)s">%(url)s</a>.' % { 'url': url}
        args['message'] = mark_safe(html_message)
        return render_to_response('message.html', args, RequestContext(request))
    return render_to_response('password_letter.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_delete(request, gid=None, cid=None):
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        o = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    if gid:
        try:
            next_url = ContactGroup.objects.get(pk=gid).get_absolute_url()+u'members/'
        except ContactGroup.DoesNotExist:
            raise Http404()
    else:
        next_url = reverse('ngw.core.views.contact_list')
    if gid:
        cg = ContactGroup.objects.get(pk=gid)
        base_nav = cg.get_smart_navbar()
        base_nav.add_component(u'members')
    else:
        base_nav = None
    return generic_delete(request, o, next_url, base_nav=base_nav)

@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_add(request, cid=None):
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        contact = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    filter_str = request.GET['filterstr']
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if filter_list_str:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    else:
        filter_list = []
    filter_list.append((u'No name', filter_str))
    filter_list_str = u','.join([u'"'+name+u'","'+filterstr+u'"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request.user, FIELD_FILTERS, filter_list_str)
    messages.add_message(request, messages.SUCCESS, u'Filter has been added sucessfully!')
    return HttpResponseRedirect(reverse('ngw.core.views.contact_filters_edit', args=(cid, len(filter_list)-1)))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_list(request, cid=None):
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        contact = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    filters = []
    if filter_list_str:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
        filters = [ (filtername, contactsearch.parse_filterstring(filter_str).to_html())
                    for filtername, filter_str in filter_list ]
    args = {}
    args['title'] = u'User custom filters'
    args['contact'] = contact
    args['filters'] = filters
    args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component((u'filters', u'custom filters'))
    return render_to_response('customfilters_user.html', args, RequestContext(request))


class FilterEditForm(forms.Form):
    name = forms.CharField(max_length=50)

@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_edit(request, cid=None, fid=None):
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        contact = Contact.objects.get(pk=cid)
    except Contact.DoesNotExist:
        raise Http404()
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if not filter_list_str:
        return HttpResponse(u'ERROR: no custom filter for that user')
    else:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    try:
        filtername, filterstr = filter_list[int(fid)]
    except (IndexError, ValueError):
        return HttpResponse(u"ERROR: Can't find filter #"+fid)

    if request.method == 'POST':
        form = FilterEditForm(request.POST)
        if form.is_valid():
            #print repr(filter_list)
            #print repr(filter_list_str)
            filter_list[int(fid)]=(form.clean()['name'], filterstr)
            #print repr(filter_list)
            filter_list_str = u','.join([u'"'+name+u'","'+filterstr+u'"' for name, filterstr in filter_list])
            #print repr(filter_list_str)
            contact.set_fieldvalue(request.user, FIELD_FILTERS, filter_list_str)
            messages.add_message(request, messages.SUCCESS, u'Filter has been renamed sucessfully!')
            return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else:
        form = FilterEditForm(initial={ 'name': filtername })
    args = {}
    args['title'] = u'User custom filter renaming'
    args['contact'] = contact
    args['form'] = form
    args['filtername'] = filtername
    args['filter_html'] = contactsearch.parse_filterstring(filterstr).to_html()
    args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component((u'filters', u'custom filters'))
    args['nav'].add_component((unicode(fid), filtername))

    return render_to_response('customfilter_user.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_ADMIN)
def contact_make_login_mailing(request):
    # select contacts whose password is in state 'Registered', with both 'Adress' and 'City' not null
    q = Contact.objects.all()
    q = q.extra(where=["EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value='%(value)s')" % { 'field_id': FIELD_PASSWORD_STATUS, 'value': '1' }])
    q = q.extra(where=['EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i)' % { 'field_id': FIELD_STREET}])
    q.extra(where=['EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i)' % { 'field_id': FIELD_CITY}])
    ids = [ row.id for row in q ]
    #print ids
    if not ids:
        return HttpResponse('No waiting mail')

    result = ngw_mailmerge('/usr/lib/ngw/mailing/forms/welcome.odt', [str(id) for id in ids])
    if not result:
        return HttpResponse('File generation failed')
    #print result
    filename = os.path.basename(result)
    if subprocess.call(['sudo', '/usr/bin/mvoomail', os.path.splitext(filename)[0], '/usr/lib/ngw/mailing/generated/']):
        return HttpResponse('File move failed')
    for row in q:
        contact = row[0]
        contact.set_fieldvalue(request.user, FIELD_PASSWORD_STATUS, u'2')

    return HttpResponse('File generated in /usr/lib/ngw/mailing/generated/')


#######################################################################
#
# Contact groups
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_list(request):
    LIST_PREVIEW_LEN = 5
    def _trucate_list(l):
        if len(l)>LIST_PREVIEW_LEN:
            return l[:LIST_PREVIEW_LEN]+[u'…']
        return l
    def _trucate_description(cg):
        DESCRIPTION_MAXLEN = 200
        if len(cg.description) < DESCRIPTION_MAXLEN:
            return cg.description
        else:
            return cg.description[:DESCRIPTION_MAXLEN]+u'…'

	
    if not request.user.is_admin():
        return unauthorized(request)
    def print_fields(cg):
        if cg.field_group:
            fields = cg.contact_fields
            if fields:
                return u', '.join(['<a href="'+f.get_absolute_url()+'">'+html.escape(f.name)+'</a>' for f in fields])
            else:
                return u'Yes (but none yet)'
        else:
            return u'No'

    q = ContactGroup.objects.filter(date=None)
    cols = [
        #( u'Date', None, 'html_date', ContactGroup.date ),
        ( u'Name', None, 'name', 'name' ),
        ( u'Description', None, lambda cg: _trucate_description(cg), None ),
        #( u'Description', None, 'description', lambda cg: len(cg.description)<100 and cg.description+u'!!' or cg.description[:100]+u"…", None ),
        #( u'Contact fields', None, print_fields, 'field_group' ),
        ( u'Super\u00a0groups', None, lambda cg: u', '.join(_trucate_list([sg.unicode_with_date() for sg in cg.get_direct_supergroups()[:LIST_PREVIEW_LEN+1]])), None ),
        ( u'Sub\u00a0groups', None, lambda cg: u', '.join(_trucate_list([html.escape(sg.unicode_with_date()) for sg in cg.get_direct_subgroups()][:LIST_PREVIEW_LEN+1])), None ),
        #( u'Budget\u00a0code', None, 'budget_code', 'budget_code' ),
        #( 'Members', None, lambda cg: str(len(cg.get_members())), None ),
        #( u'System\u00a0locked', None, 'system', 'system' ),
    ]
    args = {}
    args['title'] = 'Select a contact group'
    args['query'] = q
    args['cols'] = cols
    args['objtype'] = ContactGroup
    args['nav'] = Navbar(ContactGroup.get_class_navcomponent())
    #return query_print_entities(request, 'list_groups.html', args)
    return query_print_entities(request, 'list.html', args)


MONTHES = u'January,February,March,April,May,June,July,August,Septembre,October,November,December'.split(',')

class WeekDate:
    def __init__(self, date, events):
        self.date = date
        self.events = events

    def days(self):
        for i in range(7):
            dt = self.date + timedelta(days=i)
            events = self.events.get(dt, [])
            yield dt, events

class YearMonthCal:
    def __init__(self, year, month, events):
        self.year = year
        self.month = month
        self.events = events

    def title(self):
        return u'%s %s' % (MONTHES[self.month-1], self.year)

    def prev(self):
        year, month = self.year, self.month
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        return u'%s-%s' % (year, month)

    def next(self):
        year, month = self.year, self.month
        month += 1
        if month > 12:
            month = 1
            year += 1
        return u'%s-%s' % (year, month)

    def weeks(self):
        first_day_of_month = date(self.year, self.month, 1)
        first_day_of_month_isocal = first_day_of_month.isocalendar()
        firstweeknumber = first_day_of_month_isocal[1]

        first_day_of_month_isoweekday = first_day_of_month_isocal[2] # 1=monday, 7=sunday
        first_week_date = first_day_of_month - timedelta(days=first_day_of_month_isoweekday-1)

        nextyear, nextmonth = self.year, self.month
        nextmonth += 1
        if nextmonth > 12:
            nextmonth = 1
            nextyear += 1
        next_month_start = date(nextyear, nextmonth, 1)

        dt = first_week_date
        while dt < next_month_start:
            yield WeekDate(dt, self.events)
            dt += timedelta(days=7)


@login_required()
@require_group(GROUP_USER_NGW)
def event_list(request):
    if not request.user.is_admin():
        return unauthorized(request)

    dt = request.REQUEST.get('dt', None)
    year = month = None
    if dt is not None:
        try:
            year, month = dt.split(u'-')
            year = int(year)
            month = int(month)
        except ValueError:
            year = month = None
        else:
            if year < 2000 or year > 2100 \
             or month < 1 or month > 12:
                year = month = None

    if year is None or month is None:
        now = datetime.utcnow()
        month = now.month
        year = now.year

    min_date = datetime(year, month, 1) - timedelta(days=6)
    min_date = min_date.strftime('%Y-%m-%d')
    max_date = datetime(year, month, 1) + timedelta(days=31+6)
    max_date = max_date.strftime('%Y-%m-%d')

    q = ContactGroup.objects.filter(date__gte=min_date, date__lte=max_date)

    cols = [
        ( u'Date', None, 'html_date', 'date' ),
        ( u'Name', None, 'name', 'name' ),
        ( u'Description', None, 'description', 'description' ),
    ]

    month_events = {}
    for cg in q:
        if not month_events.has_key(cg.date):
            month_events[cg.date] = []
        month_events[cg.date].append(cg)

    args = {}
    args['title'] = u'Events'
    args['query'] = q
    args['cols'] = cols
    args['objtype'] = ContactGroup
    args['nav'] = Navbar()
    args['nav'].add_component(('events', u'Events'))
    args['year_month'] = YearMonthCal(year, month, month_events)
    args['today'] = date.today()
    return query_print_entities(request, 'list_events.html', args)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_detail(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    return HttpResponseRedirect(u'./members/')

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_members(request, gid, output_format=''):
    if not request.user.is_admin():
        return unauthorized(request)

    strfilter = request.REQUEST.get(u'filter', u'')
    filter = contactsearch.parse_filterstring(strfilter)
    baseurl = u'?filter='+strfilter

    strfields = request.REQUEST.get(u'fields', None)
    if strfields:
        fields = strfields.split(u',')
        baseurl += '&fields='+strfields
    else:
        fields = get_display_fields(request.user)
        strfields = u','.join(fields)
        #baseurl doesn't need to have default fields

    if request.REQUEST.get(u'savecolumns'):
        request.user.set_fieldvalue(request.user, FIELD_COLUMNS, strfields)

    try:
        cg = ContactGroup.objects.get(pk=gid)
    except ContactGroup.DoesNotExist:
        raise Http404()

    display = request.REQUEST.get(u'display', None)
    if display is None:
        display = cg.get_default_display()
    baseurl += u'&display='+display

    args = {}
    args['fields_form'] = FieldSelectForm(initial={u'selected_fields': fields})
    if output_format == u'csv':
        query_format = u'text'
    else:
        query_format = u'html'
    q, cols = contact_make_query_with_fields(fields, current_cg=cg, base_url=baseurl, format=query_format)

    cig_conditions_flags = []
    if u'm' in display:
        cig_conditions_flags.append(u'member=True')
        args['display_member'] = 1
    if u'i' in display:
        cig_conditions_flags.append(u'invited=True')
        args['display_invited'] = 1
    if u'd' in display:
        cig_conditions_flags.append(u'declined_invitation=True')
        args['display_declined'] = 1

    if cig_conditions_flags:
        cig_conditions_flags = u' AND (%s)' % u' OR '.join(cig_conditions_flags)
    else:
        cig_conditions_flags = u' AND False' # display nothing

    if u'g' in display:
        cig_conditions_group = u'group_id IN (SELECT self_and_subgroups(%s))' % cg.id
        args['display_subgroups'] = 1
    else:
        cig_conditions_group = u'group_id=%d' % cg.id

    q = q.filter(u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND '+cig_conditions_group+cig_conditions_flags+u')')
    q = filter.apply_filter_to_query(q)

    if output_format == u'vcards':
        #FIXME: This works but is really inefficient (try it on a large group!)
        result = u''
        for contact in q:
            result += contact.vcard()
        return HttpResponse(result.encode('utf-8'), mimetype='text/x-vcard')
    elif output_format == u'emails':
        emails = []
        noemails = []
        for contact in q:
            c_emails = contact.get_fieldvalues_by_type('EMAIL')
            if c_emails:
                emails.append((contact, c_emails[0])) # only the first email
            else:
                noemails.append(contact)
        def email_sort(a, b):
            return cmp(remove_decoration(a[0].name.lower()), remove_decoration(b[0].name.lower()))
        emails.sort(email_sort)

        args['title'] = u'Emails for '+cg.name
        args['strfilter'] = strfilter
        args['filter'] = filter
        args['cg'] = cg
        args['emails'] = emails
        args['noemails'] = noemails
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component(u'members')
        args['nav'].add_component(u'emails')
        return render_to_response('emails.html', args, RequestContext(request))
    elif output_format == u'csv':
        result = u''
        def _quote_csv(u):
            return u'"'+u.replace(u'"', u'\\"')+u'"'
        for i, col in enumerate(cols):
            if i: # not first column
                result += u','
            result += _quote_csv(col[0])
        result += '\n'
        for row in q:
            for i, col in enumerate(cols):
                if i: # not first column
                    result += u','
                v = ngw_display(row, col)
                if v == None:
                    continue
                result += _quote_csv(v)
            result += '\n'
        return HttpResponse(result, mimetype='text/csv; charset=utf-8')

    folder = cg.static_folder()
    try:
        files = os.listdir(folder)
    except OSError as (errno, errmsg):
        messages.add_message(request, messages.ERROR, u'Error while reading shared files list in %s: %s' % (folder, errmsg))
        files = []
    if '.htaccess' in files:
        files.remove('.htaccess')
    files.sort()

    args['title'] = u'Contacts of group '+cg.unicode_with_date()
    args['baseurl'] = baseurl # contains filter, display, fields. NO output, no order
    args['display'] = display
    args['query'] = q
    args['cols'] = cols
    args['cg'] = cg
    args['files'] = files
    ####
    args['objtype'] = ContactGroup
    args['filter'] = strfilter
    args['fields'] = strfields
    ####
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component(u'members')

    response = query_print_entities(request, 'group_detail.html', args)
    #from django.db import connection
    #import pprint
    #pprint.PrettyPrinter(indent=4).pprint(connection.queries)
    return response


class ContactGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(required=False, widget=forms.Textarea)
    date = forms.DateField(required=False, help_text=u'Use YYYY-MM-DD format. Leave empty for permanent groups.', widget=NgwCalendarWidget(attrs={'class':'vDateField'}))
    budget_code = forms.CharField(required=False, max_length=10)
    sticky = forms.BooleanField(required=False, help_text=u'If set, automatic membership because of subgroups becomes permanent. Use with caution.')
    field_group = forms.BooleanField(required=False, help_text=u'Does that group yield specific fields to its members?')
    mailman_address = forms.CharField(required=False, max_length=255, help_text=u'Mailing list address, if the group is linked to a mailing list.')
    has_news = forms.BooleanField(required=False, help_text=u'Does that group supports internal news system?')
    direct_supergroups = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget('groups', False))

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        self.fields['direct_supergroups'].choices = [ (g.id, g.unicode_with_date()) for g in ContactGroup.objects.order_by('date', 'name') ]


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_edit(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype = ContactGroup
    if id:
        try:
            cg = ContactGroup.objects.get(pk=id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        title = u'Editing '+unicode(cg)
    else:
        title = u'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactGroupForm(request.POST)
        if form.is_valid():
            # record the values

            data = form.clean()
            if not id:
                cg = ContactGroup()
            cg.name = data['name']
            cg.description = data['description']
            cg.field_group = data['field_group']
            cg.sticky = data['sticky']
            cg.date = data['date']
            cg.budget_code = data['budget_code']
            cg.mailman_address = data['mailman_address']
            cg.has_news = data['has_news']

            cg.save()
            old_direct_supergroups_ids = cg.get_direct_supergroups_ids()
            new_direct_supergroups_id = data['direct_supergroups']
            if cg.id != GROUP_EVERYBODY and not new_direct_supergroups_id:
                new_direct_supergroups_id = [ GROUP_EVERYBODY ]

            # supergroups have no properties (yet!): just recreate the array with brute force
            cg.set_direct_supergroups_ids(new_direct_supergroups_id)

            messages.add_message(request, messages.SUCCESS, u'Group %s has been changed sucessfully!' % cg.unicode_with_date())

            cg.check_static_folder_created()
            Contact.check_login_created(request.user) # subgroups change

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cg.get_absolute_url()+u'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cg.get_class_absolute_url()+u'add')
            else:
                return HttpResponseRedirect(cg.get_absolute_url())

    else: # GET
        if id:
            try:
                cg = ContactGroup.objects.get(pk=id)
            except ContactGroup.DoesNotExist:
                raise Http404()
            initialdata = {
                'name': cg.name,
                'description': cg.description,
                'field_group': cg.field_group,
                'sticky': cg.sticky,
                'date': cg.date,
                'budget_code': cg.budget_code,
                'mailman_address': cg.mailman_address,
                'has_news': cg.has_news,
                'direct_supergroups': cg.get_direct_supergroups_ids()
            }
            form = ContactGroupForm(initialdata)
        else: # add new one
            form = ContactGroupForm()
    args = {}
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    args['form'] = form
    if id:
        args['o'] = cg
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component(u'edit')
    else:
        args['nav'] = Navbar(ContactGroup.get_class_navcomponent())
        args['nav'].add_component(u'add')

    return render_to_response('edit.html', args, RequestContext(request))


def on_contactgroup_delete(cg):
    """
    All subgroups will now have their fathers' fathers as direct fathers
    """
    supergroups_ids = set(cg.get_direct_supergroups_ids())
    for subcg in cg.get_direct_subgroups():
        sub_super = set(subcg.get_direct_supergroups_ids())
        #print repr(subcg), "had these fathers:", sub_super
        sub_super = sub_super | supergroups_ids - { cg.id }
        if not sub_super:
            sub_super = { GROUP_EVERYBODY }
        #print repr(subcg), "new fathers:", sub_super
        subcg.set_direct_supergroups_ids(sub_super)
        #print repr(subcg), "new fathers double check:", subcg.get_direct_supergroups_ids()
    # TODO: delete static folder


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = ContactGroup.objects.get(pk=id)
    next_url = reverse('ngw.core.views.contactgroup_list')
    if o.system:
        messages.add_message(request, messages.ERROR, u'Group %s is locked and CANNOT be deleted.' % o.name)
        return HttpResponseRedirect(next_url)
    return generic_delete(request, o, next_url, ondelete_function=on_contactgroup_delete)# args=(p.id,)))


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_add_contacts_to(request):
    if not request.user.is_admin():
        return unauthorized(request)

    if request.method == 'POST':
        target_gid = request.POST[u'group']
        if target_gid:
            target_group = ContactGroup.objects.get(pk=target_gid)
            assert target_group
            t = request.REQUEST.get('type', u'')
            if t == u'Invite':
                mode = u'i'
            elif t == u'Member':
                mode = u'm'
            elif t == u'Declined invitation':
                mode = u'd'
            else:
                raise Exception('Unsupported membership type '+t.encode('utf8'))

            contacts = []
            for param in request.POST:
                if not param.startswith(u'contact_'):
                    continue
                contact_id = param[len(u'contact_'):]
                contact = Contact.objects.get(pk=contact_id)
                contacts.append(contact)
            target_group.set_member_n(request.user, contacts, mode)

            return HttpResponseRedirect(target_group.get_absolute_url())
        else:
            messages.add_message(request, messages.ERROR, u'You must select a target group')

    gid = request.REQUEST.get(u'gid', u'')
    assert gid
    try:
        cg = ContactGroup.objects.get(pk=gid)
    except ContactGroup.DoesNotExist:
        raise Http404()

    strfilter = request.REQUEST.get(u'filter', u'')
    filter = contactsearch.parse_filterstring(strfilter)

    q, cols = contact_make_query_with_fields([], format=u'html') #, current_cg=cg)

    q = q.order_by('name')

    display = request.REQUEST.get(u'display', None)
    if display is None:
        display = cg.get_default_display()
    cig_conditions_flags = []
    if u'm' in display:
        cig_conditions_flags.append(u'member=True')
    if u'i' in display:
        cig_conditions_flags.append(u'invited=True')
    if u'd' in display:
        cig_conditions_flags.append(u'declined_invitation=True')

    if cig_conditions_flags:
        cig_conditions_flags = u' AND (%s)' % u' OR '.join(cig_conditions_flags)
    else:
        cig_conditions_flags = u' AND False' # display nothing

    if u'g' in display:
        cig_conditions_group = u'group_id IN (SELECT self_and_subgroups(%s))' % cg.id
    else:
        cig_conditions_group = u'group_id=%d' % cg.id

    q = q.filter(u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND '+cig_conditions_group+cig_conditions_flags+u')')
    q = filter.apply_filter_to_query(q)

    args = {}
    args['title'] = 'Add contacts to a group'
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component((u'add_contacts_to', u'add contacts to'))
    args['groups'] = ContactGroup.objects.order_by('-date', 'name')
    args['query'] = q
    return render_to_response('group_add_contacts_to.html', args, RequestContext(request))




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
    note = forms.CharField(required=False)

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        self.fields['invited'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.declined_invitation.checked=false; this.form.member.checked=false; this.form.operator.checked=false;}'}
        self.fields['declined_invitation'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.invited.checked=false; this.form.member.checked=false; this.form.operator.checked=false;}'}
        self.fields['member'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.invited.checked=false; this.form.declined_invitation.checked=false; } else { this.form.operator.checked=false;}'}
        self.fields['operator'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.invited.checked=false; this.form.declined_invitation.checked=false; this.form.member.checked=true; }'}

    def clean(self):
        data = self.cleaned_data
        if  (data['invited'] and data['declined_invitation']) \
         or (data['declined_invitation'] and data['member']) \
         or (data['invited'] and data['member']) \
         or (data['operator'] and not data['member']):
            raise forms.ValidationError('Invalid flags combinaison')
        return data

@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit(request, gid, cid):
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        cig = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        raise Http404()
    cg = ContactGroup.objects.get(pk=gid)
    contact = Contact.objects.get(pk=cid)
    args = {}
    args['title'] = u'Contact '+unicode(contact)+u' in group '+cg.unicode_with_date()
    args['cg'] = cg
    args['contact'] = contact
    args['objtype'] = ContactInGroup
    initial = {}
    if cig:
        initial['invited'] = cig.invited
        initial['declined_invitation'] = cig.declined_invitation
        initial['member'] = cig.member
        initial['operator'] = cig.operator
        initial['note'] = cig.note

    if request.method == 'POST':
        form = ContactInGroupForm(request.POST, initial=initial)
        if form.is_valid():
            data = form.cleaned_data
            if not data['invited'] and not data['declined_invitation'] and not data['member'] and not data['operator']:
                return HttpResponseRedirect(reverse('ngw.core.views.contactingroup_delete', args=(unicode(cg.id), cid))) # TODO update logins deletion, call membership hooks
            if not cig:
                cig = ContactInGroup(contact_id=contact.id, croup_id=cg.id)
            cig.invited = data['invited']
            cig.declined_invitation = data['declined_invitation']
            cig.member = data['member']
            cig.operator = data['operator']
            cig.note = data['note']
            messages.add_message(request, messages.SUCCESS, u'Member %s of group %s has been changed sucessfully!' % (contact.name, cg.name))
            Contact.check_login_created(request.user)
            cig.save()
            hooks.membership_changed(request.user, contact, cg)
            return HttpResponseRedirect(cg.get_absolute_url())
    else:
        form = ContactInGroupForm(initial=initial)

    args['form'] = form

    inherited_info = u''

    automember_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND member AND group_id=contact_group.id)' % (gid, cid)]).exclude(id=gid).order_by('-date', 'name')
    #print automember_groups.query
    if automember_groups:
        inherited_info += u'Automatically member because member of subgroup(s):<br>'
        for sub_cg in automember_groups:
            inherited_info += u'<li><a href=\"%(url)s\">%(name)s</a>' % { 'name': sub_cg.unicode_with_date(), 'url': sub_cg.get_absolute_url() }
        inherited_info += u'<br>'

    autoinvited_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND invited AND group_id=contact_group.id)' % (gid, cid)]).exclude(id=gid).order_by('-date', 'name')
    if autoinvited_groups:
        inherited_info += u'Automatically invited because invited in subgroup(s):<br>'
        for sub_cg in autoinvited_groups:
            inherited_info += u'<li><a href=\"%(url)s\">%(name)s</a>' % { 'name': sub_cg.unicode_with_date(), 'url': sub_cg.get_absolute_url() }
    args['inherited_info'] = mark_safe(inherited_info)

    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component(u'members')
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component(u'membership')
    return render_to_response('contact_in_group.html', args, RequestContext(request))

@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit_inline(request, gid, cid):
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        cig = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        cig = ContactInGroup(contact_id=cid, group_id=gid)
    cg = ContactGroup.objects.get(pk=gid)
    contact = Contact.objects.get(pk=cid)
    newmembership = request.POST['membership']
    if newmembership == u'invited':
        cig.invited = True
        cig.declined_invitation = False
        cig.member = False
        cig.operator = False
    elif newmembership == u'member':
        cig.invited = False
        cig.declined_invitation = False
        cig.member = True
        # cig.operator can be any value
    elif newmembership == u'declined_invitation':
        cig.invited = False
        cig.declined_invitation = True
        cig.member = False
        cig.operator = False
    else:
        raise Exception(u'invalid membership '+request.POST['membership'])
    cig.save()
    messages.add_message(request, messages.SUCCESS, u'Member %s of group %s has been changed sucessfully!' % (contact.name, cg.name))
    hooks.membership_changed(request.user, contact, cg)
    return HttpResponseRedirect(request.POST['next_url'])

@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_delete(request, gid, cid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = ContactGroup.objects.get(pk=gid)
    try:
        o = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        return HttpResponse('Error, that contact is not a direct member. Please check subgroups')
    #messages.add_message(request, messages.SUCCESS, u'%s has been removed for group %s.' % (cig.contact.name, cig.group.name))
    base_nav = cg.get_smart_navbar()
    base_nav.add_component(u'members')
    return generic_delete(request, o, next_url=cg.get_absolute_url()+u'members/', base_nav=base_nav)
    # TODO: realnav bar is 'remove', not 'delete'


#######################################################################
#
# ContactGroup News
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news(request, gid):
    cg = ContactGroup.objects.get(pk=gid)
    args = {}
    args['title'] = u'News for group '+cg.name
    args['news'] = ContactGroupNews.objects.filter(contact_group=gid)
    args['cg'] = cg
    args['objtype'] = ContactGroupNews
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component(u'news')
    return render_to_response('news.html', args, RequestContext(request))


class NewsEditForm(forms.Form):
    title = forms.CharField(max_length=50)
    text = forms.CharField(widget=forms.Textarea)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_edit(request, gid, nid):
    cg = ContactGroup.objects.get(pk=gid)
    if nid:
        news = ContactGroupNews.objects.get(pk=nid)
        if str(news.contact_group_id) != gid:
            return HttpResponse(u'ERROR: Group mismatch')

    if request.method == 'POST':
        form = NewsEditForm(request.POST)
        if form.is_valid():
            data = form.clean()
            if not nid:
                news = ContactGroupNews()
                news.author_id = request.user.id
                news.contact_group = cg
                news.date = datetime.now()
            news.title = data['title']
            news.text = data['text']
            news.save()
            messages.add_message(request, messages.SUCCESS, u'News %s has been changed sucessfully!' % news)

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(news.get_absolute_url())
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_news_edit', args=(cg.id,))) # 2nd parameter is None
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contactgroup_news', args=(cg.id,)))
    else:
        initial = {}
        if nid:
            initial['title'] = news.title
            initial['text'] = news.text
        form = NewsEditForm(initial=initial)
    args = {}
    args['title'] = u'News edition'
    args['cg'] = cg
    args['form'] = form
    if nid:
        args['o'] = news
        args['id'] = nid
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component(u'news')
    if nid:
        args['nav'].add_component(news.get_navcomponent())
        args['nav'].add_component(u'edit')
    else:
        args['nav'].add_component(u'add')

    return render_to_response('edit.html', args, RequestContext(request))

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_delete(request, gid, nid):
    if not request.user.is_admin():
        return unauthorized(request)
    cg = ContactGroup.objects.get(pk=gid)
    o = ContactGroupNews.objects.get(pk=nid)
    return generic_delete(request, o, cg.get_absolute_url()+u'news/')

class MailmanSyncForm(forms.Form):
    mail = forms.CharField(widget=forms.Textarea)

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_mailman(request, id):
    initial_value = '''
Les résultats de vos commandes courriels sont fournies ci-dessous.
Ci-joint votre message original.

- Résultats :
    Abonnés en mode non-groupé (normaux) :
        user1@example.com (John DOE)
        user2@example.com

- Fait.
    '''
    from ngw.extensions.mailman import synchronise_group
    if not request.user.is_admin():
        return unauthorized(request)
    try:
        cg = ContactGroup.objects.get(pk=id)
    except ContactGroup.DoesNotExist:
        raise Http404()

    args = {}
    args['title'] = u'Mailman synchronisation'
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component(u'mailman')
    args['cg'] = cg

    if request.method == 'POST':
        form = MailmanSyncForm(request.POST)
        if form.is_valid():
            data = form.clean()
            args['sync_res'] = synchronise_group(cg, data['mail'])
            return render_to_response('group_mailman_result.html', args, RequestContext(request))
    else:
        form = MailmanSyncForm(initial={'mail': initial_value})

    args['form'] = form
    return render_to_response('group_mailman.html', args, RequestContext(request))


#######################################################################
#
# Contact Fields
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def field_list(request):
    if not request.user.is_admin():
        return unauthorized(request)
    args = {}
    args['query'] = ContactField.objects.order_by('sort_weight')
    args['cols'] = [
        ( 'Name', None, 'name', 'name'),
        ( 'Type', None, 'type_as_html', 'type'),
        ( 'Only for', None, 'contact_group', 'contact_group_id'),
        ( 'System locked', None, 'system', 'system'),
        ( 'Move', None, lambda cf: '<a href='+str(cf.id)+'/moveup>Up</a> <a href='+str(cf.id)+'/movedown>Down</a>', None),
    ]
    args['title'] = 'Select an optionnal field'
    args['objtype'] = ContactField
    args['nav'] = Navbar(ContactField.get_class_navcomponent())
    def extrasort(query):
        return query.order_by('sort_weight')
    return query_print_entities(request, 'list.html', args, extrasort=extrasort)


@login_required()
@require_group(GROUP_USER_NGW)
def field_move_up(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    cf = ContactField.objects.get(pk=id)
    cf.sort_weight -= 15
    cf.save()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))

@login_required()
@require_group(GROUP_USER_NGW)
def field_move_down(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    cf = ContactField.objects.get(pk=id)
    cf.sort_weight += 15
    cf.save()
    field_renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))


def field_renumber():
    """
    Update all fields sort_weight so that each weight is previous + 10
    """
    new_weigth = 0
    for cf in ContactField.objects.order_by('sort_weight'):
        new_weigth += 10
        cf.sort_weight = new_weigth
        cf.save()


class FieldEditForm(forms.Form):
    name = forms.CharField()
    hint = forms.CharField(required=False, widget=forms.Textarea)
    contact_group = forms.CharField(label=u'Only for', required=False, widget=forms.Select)
    type = forms.CharField(widget=forms.Select)
    choicegroup = forms.CharField(required=False, widget=forms.Select)
    default_value = forms.CharField(required=False)
    move_after = forms.IntegerField(widget=forms.Select())

    def __init__(self, cf, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)

        contacttypes = ContactGroup.objects.filter(field_group=True)
        self.fields['contact_group'].widget.choices = [ (g.id, g.name) for g in contacttypes ]

        self.fields['type'].widget.choices = [ (cls.db_type_id, cls.human_type_id)
            for cls in ContactField.types_classes.itervalues() ] # TODO: Sort
        js_test_type_has_choice = u' || '.join([ u"this.value=='"+cls.db_type_id+"'"
            for cls in ContactField.types_classes.values()
            if cls.has_choice ])
        self.fields['type'].widget.attrs = { 'onchange': mark_safe('if (0 || '+js_test_type_has_choice+") { document.forms['objchange']['choicegroup'].disabled = 0; } else { document.forms['objchange']['choicegroup'].value = ''; document.forms['objchange']['choicegroup'].disabled = 1; }") }

        self.fields['choicegroup'].widget.choices = [('', '---')] + [(c.id, c.name) for c in ChoiceGroup.objects.order_by('name')]

        t = self.data.get('type', '') or self.initial.get('type', '')
        if t:
            cls_contact_field = ContactField.get_contact_field_type_by_dbid(t)
        else:
            cls_contact_field = ContactField.get_contact_field_type_by_dbid('TEXT')
        if cls_contact_field.has_choice:
            if self.fields['choicegroup'].widget.attrs.has_key('disabled'):
                del self.fields['choicegroup'].widget.attrs['disabled']
            self.fields['choicegroup'].required = True
        else:
            self.fields['choicegroup'].widget.attrs['disabled'] = 1
            self.fields['choicegroup'].required = False

        self.fields['default_value'].widget.attrs['disabled'] = 1

        self.fields['move_after'].widget.choices = [ (5, 'Name') ] + [ (field.sort_weight + 5, field.name) for field in ContactField.objects.order_by('sort_weight') ]

        if cf and cf.system:
            self.fields['contact_group'].widget.attrs['disabled'] = 1
            self.fields['type'].widget.attrs['disabled'] = 1
            self.fields['type'].required = False
            self.fields['choicegroup'].widget.attrs['disabled'] = 1

    def clean(self):
        t = self.cleaned_data.get('type', None)
        if t:
            # system fields have type disabled, this is ok
            cls_contact_field = ContactField.get_contact_field_type_by_dbid(t)
            if cls_contact_field.has_choice and not self.cleaned_data['choicegroup']:
                raise forms.ValidationError('You must select a choice group for that type.')
        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def field_edit(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype = ContactField
    initial = {}
    if id:
        cf = ContactField.objects.get(pk=id)
        title = u'Editing '+unicode(cf)
        initial['name'] = cf.name
        initial['hint'] = cf.hint
        initial['contact_group'] = cf.contact_group_id
        initial['type'] = cf.type
        initial['choicegroup'] = cf.choice_group_id
        initial['default_value'] = cf.default
        initial['move_after'] = cf.sort_weight-5
    else:
        cf = None
        title = u'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = FieldEditForm(cf, request.POST, initial=initial)
        #print request.POST
        if form.is_valid():
            data = form.clean()
            if not id:
                cf = ContactField(name = data['name'],
                                  hint = data['hint'],
                                  contact_group_id = int(data['contact_group']),
                                  type = data['type'],
                                  choice_group_id = data['choicegroup'] and int(data['choicegroup']) or None,
                                  sort_weight = int(data['move_after']))
                cf.save()
            else:
                if not cf.system and (cf.type != data['type'] or unicode(cf.choice_group_id) != data['choicegroup']):
                    deletion_details = []
                    newcls = ContactField.get_contact_field_type_by_dbid(data['type'])
                    choice_group_id = None
                    if data['choicegroup']:
                        choice_group_id = int(data['choicegroup'])
                    for cfv in cf.values.all():
                        if not newcls.validate_unicode_value(cfv.value, choice_group_id):
                            deletion_details.append((cfv.contact, cfv))

                    if deletion_details:
                        if request.POST.get('confirm', None):
                            for cfv in [ dd[1] for dd in deletion_details ]:
                                cfv.delete()
                        else:
                            args = {}
                            args['title'] = 'Type incompatible with existing data'
                            args['id'] = id
                            args['cf'] = cf
                            args['deletion_details'] = deletion_details
                            for k in ( 'name', 'hint', 'contact_group', 'type', 'choicegroup', 'move_after'):
                                args[k] = data[k]
                            args['nav'] = Navbar(cf.get_class_navcomponent(), cf.get_navcomponent(), (u'edit', u'delete imcompatible data'))
                            return render_to_response('type_change.html', args, RequestContext(request))

                    cf.type = data['type']
                    cf.polymorphic_upgrade() # This is needed after changing type
                    cf.save()
                cf.name = data['name']
                cf.hint = data['hint']
                if not cf.system:
                    # system fields have some properties disabled
                    cf.contact_group_id = int(data['contact_group'])
                    cf.type = data['type']
                    if data['choicegroup']:
                        cf.choice_group_id = int(data['choicegroup'])
                    else:
                        cf.choice_group_id = None
                cf.sort_weight = int(data['move_after'])
                cf.save()

            field_renumber()
            messages.add_message(request, messages.SUCCESS, u'Field %s has been changed sucessfully.' % cf.name)
            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cf.get_absolute_url()+u'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cf.get_class_absolute_url()+u'add')
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.field_list'))
        # else validation error
    else:
        if id: # modify
            form = FieldEditForm(cf, initial=initial)
        else: # add
            form = FieldEditForm(None, initial=initial)


    args = {}
    args['form'] = form
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    if id:
        args['o'] = cf
    args['nav'] = Navbar(ContactField.get_class_navcomponent())
    if id:
        args['nav'].add_component(cf.get_navcomponent())
        args['nav'].add_component(u'edit')
    else:
        args['nav'].add_component(u'add')
    return render_to_response('edit.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def field_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = ContactField.objects.get(pk=id)
    next_url = reverse('ngw.core.views.field_list')
    if o.system:
        messages.add_message(request, messages.ERROR, u'Field %s is locked and CANNOT be deleted.' % o.name)
        return HttpResponseRedirect(next_url)
    return generic_delete(request, o, next_url)

#######################################################################
#
# Choice groups
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_list(request):
    if not request.user.is_admin():
        return unauthorized(request)
    args = {}
    args['query'] = ChoiceGroup.objects
    args['cols'] = [
        ( 'Name', None, 'name', 'name'),
        ( 'Choices', None, lambda cg: ', '.join([html.escape(c[1]) for c in cg.ordered_choices]), None),
    ]
    args['title'] = 'Select a choice group'
    args['objtype'] = ChoiceGroup
    args['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())
    return query_print_entities(request, 'list.html', args)


class ChoicesWidget(forms.MultiWidget):
    def __init__(self, ndisplay, attrs=None):
        widgets = []
        attrs_value = attrs or {}
        attrs_key = attrs or {}
        attrs_value['style'] = u'width:90%'
        attrs_key['style'] = u'width:9%; margin-left:1ex;'

        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs_value))
            widgets.append(forms.TextInput(attrs=attrs_key))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay
    def decompress(self, value):
        if value:
            return value.split(u',')
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
            return u','.join(data_list)
        return None
    def clean(self, value):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = forms.MultiValueField.clean(self, value).split(u',')
        #print 'possibles_values=', repr(possibles_values)
        keys = []
        for i in range(len(possibles_values)/2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines without values
            if not k:
                continue # empty keys are ok
            if k in keys:
                raise forms.ValidationError('You cannot have two keys with the same value. Leave empty for automatic generation.')
            keys.append(k)
        return possibles_values



class ChoiceGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    sort_by_key = forms.BooleanField(required=False)

    def __init__(self, cg=None, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)

        ndisplay = 0
        self.initial['possible_values'] = []

        if cg:
            self.initial['name'] = cg.name
            self.initial['sort_by_key'] = cg.sort_by_key
            choices = cg.ordered_choices
            for c in choices:
                self.initial['possible_values'].append(c[1])
                self.initial['possible_values'].append(c[0])
                ndisplay += 1

        for i in range(3): # add 3 blank lines to add data
            self.initial['possible_values'].append(u'')
            self.initial['possible_values'].append(u'')
            ndisplay += 1
        self.fields['possible_values'] = ChoicesField(required=False, widget=ChoicesWidget(ndisplay=ndisplay), ndisplay=ndisplay)


    def save(self, cg, request):
        if cg:
            oldid = cg.id
        else:
            cg = ChoiceGroup()
            oldid = None
        cg.name = self.clean()['name']
        cg.sort_by_key = self.clean()['sort_by_key']
        cg.save()

        possibles_values = self['possible_values']._data()
        choices = {}

        # first ignore lines with empty keys, and update auto_key
        auto_key = 0
        for i in range(len(possibles_values)/2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines whose value is empty
            if k: # key is not left empty for automatic generation
                if k.isdigit():
                    intk = int(k)
                    if intk > auto_key:
                        auto_key = intk
                choices[k] = v

        auto_key += 1

        # now generate key for empty ones
        for i in range(len(possibles_values)/2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines whose value is empty
            if not k: # key is left empty for automatic generation
                k = str(auto_key)
                auto_key += 1
                choices[k] = v

        #print 'choices=', choices

        for c in cg.choices.all():
            k = c.key
            if k in choices.keys():
                #print 'UPDATING', k
                c.value = choices[k]
                c.save()
                del choices[k]
            else: # that key has be deleted
                #print 'DELETING', k
                c.delete()
        for k, v in choices.iteritems():
            #print 'ADDING', k
            cg.choices.create(key=k, value=v)

        messages.add_message(request, messages.SUCCESS, u'Choice %s has been saved sucessfully.' % cg.name)
        return cg


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_edit(request, id=None):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype = ChoiceGroup
    if id:
        cg = ChoiceGroup.objects.get(pk=id)
        title = u'Editing '+unicode(cg)
    else:
        cg = None
        title = u'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, request.POST)
        if form.is_valid():
            cg = form.save(cg, request)
            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cg.get_absolute_url()+u'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cg.get_class_absolute_url()+u'add')
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.choicegroup_list'))
    else:
        form = ChoiceGroupForm(cg)

    args = {}
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    args['form'] = form
    if id:
        args['o'] = cg
    args['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())
    if id:
        args['nav'].add_component(cg.get_navcomponent())
        args['nav'].add_component(u'edit')
    else:
        args['nav'].add_component(u'add')
    return render_to_response('edit.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = ChoiceGroup.objects.get(pk=id)
    return generic_delete(request, o, reverse('ngw.core.views.choicegroup_list'))
