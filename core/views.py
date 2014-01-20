# -*- encoding: utf8 -*-

from __future__ import print_function, unicode_literals
from datetime import *
from decoratedstr import remove_decoration
from copy import copy
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils import html
from django.shortcuts import render_to_response, get_object_or_404
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
from ngw.core.mailmerge import ngw_mailmerge
from ngw.core import contactsearch
from ngw.core import perms

from django.db.models.query import RawQuerySet, sql

DISP_NAME = 'name'
DISP_FIELD_PREFIX = 'field_'
DISP_GROUP_PREFIX = 'group_'

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

DEBUG_MEMBERSHIPS = False

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
    return scheme+'://'+request.META['HTTP_HOST']+'/'


def logout(request):
    #need to call auth_logout(request) when using auth contrib module
    return render_to_response('message.html', {
        'message': mark_safe('Have a nice day!<br><a href="%(url)s">Login again</a>' % { 'url': ngw_base_url(request) })
        }, RequestContext(request))


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
                raise PermissionDenied
            if not user.is_member_of(self.required_group):
                raise PermissionDenied
            return func(*args, **kwargs)
        return wrapped


def get_display_fields(user):
    # check the field still exists
    result = []
    default_fields = user.get_fieldvalue_by_id(FIELD_COLUMNS)
    if not default_fields:
        try:
            default_fields = Config.objects.get(pk='columns').text
        except Config.DoesNotExist:
            pass
    if not default_fields:
        default_fields = ''
    for fname in default_fields.split(','):
        if fname == 'name':
            pass
        elif fname.startswith(DISP_GROUP_PREFIX):
            try:
                groupid = int(fname[len(DISP_GROUP_PREFIX):])
            except ValueError:
                print('Error in default fields: %s has invalid syntax.' % fname.encode('utf8'))
                continue
            try:
                ContactGroup.objects.get(pk=groupid)
            except ContactGroup.DoesNotExist:
                print('Error in default fields: There is no group #%d.' % groupid)
                continue
        elif fname.startswith(DISP_FIELD_PREFIX):
            try:
                fieldid = int(fname[len(DISP_FIELD_PREFIX):])
            except ValueError:
                print('Error in default fields: %s has invalid syntax.' % fname.encode('utf8'))
                continue
            try:
                ContactField.objects.get(pk=fieldid)
            except ContactField.DoesNotExist:
                print('Error in default fields: There is no field #%d.' % fieldid)
                continue
        else:
            print('Error in default fields: Invalid syntax in "%s".' % fname.encode('utf8'))
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
    operator_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.group_id = contact_group.id AND contact_in_group.contact_id=%s AND contact_in_group.flags & %s <> 0)' % (request.user.id, CIGFLAG_OPERATOR)])
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
    #raise Exception('Boum')
    return render_to_response('test.html', args, RequestContext(request))


########################################################################
#
# Generic views
#
########################################################################

def query_print_entities(request, template_name, args, extrasort=None):
    try:
        object_query_page_length = Config.objects.get(pk='query_page_length')
        NB_LINES_PER_PAGE = int(object_query_page_length.text)
    except (Config.DoesNotExist, ValueError):
        NB_LINES_PER_PAGE = 200

    q = args['query']
    cols = args['cols']

    # get sort column name
    nosort = False
    order = request.REQUEST.get('_order', '')

    if order or not extrasort:
        # disable default sort on column 0 if there's an extrasort parameter
        try:
            intorder = int(order)
        except ValueError:
            if extrasort:
                order = ''
                nosort = True
            else:
                order = '0'
                intorder = 0
        if not nosort:
            sort_col = cols[abs(intorder)][3]
            if not order or order[0] != '-':
                q = q.order_by(sort_col)
            else:
                q = q.order_by('-'+sort_col)
    else: # no order and extrasort
        order = ''
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
    title = 'Please confirm deletetion'

    confirm = request.GET.get('confirm', '')
    if confirm:
        if ondelete_function:
            ondelete_function(o)
        name = unicode(o)
        log = Log()
        log.contact_id = request.user.id
        log.action = LOG_ACTION_DEL
        pk_names = (o._meta.pk.attname,) # default django pk name
        log.target = unicode(o.__class__.__name__)+' '+' '.join([unicode(o.__getattribute__(fieldname)) for fieldname in pk_names])
        log.target_repr = o.get_class_verbose_name()+' '+name
        o.delete()
        log.save()
        messages.add_message(request, messages.SUCCESS, '%s has been deleted sucessfully!' % name)
        return HttpResponseRedirect(next_url)
    else:
        nav = base_nav or Navbar(o.get_class_navcomponent())
        nav.add_component(o.get_navcomponent())
        nav.add_component('delete')
        return render_to_response('delete.html', {'title':title, 'o': o, 'nav': nav}, RequestContext(request))



#######################################################################
#
# Logs
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def logs(request):
    if not request.user.is_admin():
        raise PermissionDenied

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
    memberships = []
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % group_id)
    if flags is None:
        flags = 0
    flags_inherited = getattr(contact_with_extra_fields, 'group_%s_inherited_flags' % group_id)
    if flags_inherited is None:
        flags_inherited = 0
    if DEBUG_MEMBERSHIPS:
        if flags & CIGFLAG_MEMBER:
            memberships.append("Member")
        if flags_inherited & CIGFLAG_MEMBER:
            memberships.append("Member" + " " + AUTOMATIC_MEMBER_INDICATOR)
        if flags & CIGFLAG_INVITED:
            memberships.append("Invited")
        if flags_inherited & CIGFLAG_INVITED:
            memberships.append("Invited" + " " + AUTOMATIC_MEMBER_INDICATOR)
        if flags & CIGFLAG_DECLINED:
            memberships.append("Declined")

        if flags & CIGFLAG_OPERATOR:
            memberships.append("Operator")
        if flags & CIGFLAG_VIEWER:
            memberships.append("Viewer")
    else:
        if flags & CIGFLAG_MEMBER:
            memberships.append("Member")
        elif flags_inherited & CIGFLAG_MEMBER:
            memberships.append("Member" + " " + AUTOMATIC_MEMBER_INDICATOR)
        elif flags & CIGFLAG_INVITED:
            memberships.append("Invited")
        elif flags_inherited & CIGFLAG_INVITED:
            memberships.append("Invited" + " " + AUTOMATIC_MEMBER_INDICATOR)
        elif flags & CIGFLAG_DECLINED:
            memberships.append("Declined")

        if flags & CIGFLAG_OPERATOR:
            memberships.append("Operator")
        if flags & CIGFLAG_VIEWER:
            memberships.append("Viewer")

    if memberships:
        return ', '.join(memberships)
    else:
        return 'No'

def membership_to_text_factory(group_id):
    return lambda contact_with_extra_fields: \
        membership_to_text(contact_with_extra_fields, group_id)


def membership_extended_widget(contact_with_extra_fields, contact_group, base_url):
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % contact_group.id)
    if flags is None:
        flags = 0
    member = flags & CIGFLAG_MEMBER
    invited = flags & CIGFLAG_INVITED
    declined = flags & CIGFLAG_DECLINED
    #operator = flags & CIGFLAG_OPERATOR
    #viewer = flags & CIGFLAG_VIEWER
    note = getattr(contact_with_extra_fields, 'group_%s_note' % contact_group.id)

    params = {}
    params['cid'] = contact_with_extra_fields.id
    params['gid'] = contact_group.id
    params['membership_str'] = membership_to_text(contact_with_extra_fields, contact_group.id)
    if note:
        params['note'] = '<br>'+html.escape(note)
    else:
        params['note'] = ''
    params['membership_url'] = contact_group.get_absolute_url()+'members/'+unicode(contact_with_extra_fields.id)+'/membership'
    params['title'] = contact_with_extra_fields.name+' in group '+contact_group.unicode_with_date()
    params['base_url'] = base_url

    if member:
        params['is_member_checked'] = ' checked'
    else:
        params['is_member_checked'] = ''
    if invited:
        params['is_invited_checked'] = ' checked'
    else:
        params['is_invited_checked'] = ''
    if declined:
        params['has_declined_invitation_checked'] = ' checked'
    else:
        params['has_declined_invitation_checked'] = ''

    return  '''
<a href="javascript:show_membership_extrainfo(%(cid)d)">%(membership_str)s</a>%(note)s
<div class=membershipextra id="membership_%(cid)d">
    <a href="javascript:show_membership_extrainfo(null)"><img src="/close.png" alt=close width=10 height=10 style="position:absolute; top:0px; right:0px;"></a>
    %(title)s<br>
    <form action="%(cid)d/membershipinline" method=post>
        <input type=hidden name="next_url" value="../../members/%(base_url)s">
        <input type=radio name=membership value=invited id="contact_%(cid)d_invited" %(is_invited_checked)s onclick="this.form.submit()"><label for="contact_%(cid)d_invited">Invited</label>
        <input type=radio name=membership value=member id="contact_%(cid)d_member" %(is_member_checked)s onclick="this.form.submit()"><label for="contact_%(cid)d_member">Member</label>
        <input type=radio name=membership value=declined_invitation id="contact_%(cid)d_declined_invitation" %(has_declined_invitation_checked)s onclick="this.form.submit()"><label for="contact_%(cid)d_declined_invitation"> Declined invitation</label>
        <br>
        <a href="%(membership_url)s">More...</a> | <a href="javascript:show_membership_extrainfo(null)">Close</a>
    </form>
</div>''' % params


def membership_extended_widget_factory(contact_group, base_url):
    return lambda contact_with_extra_fields: \
        membership_extended_widget(contact_with_extra_fields, contact_group, base_url)


class ContactQuerySet(RawQuerySet):
    def __init__(self, *args, **kargs):
        super(ContactQuerySet, self).__init__('', *args, **kargs)
        self.qry_fields = {'id':'contact.id', 'name':'name'}
        self.qry_from = ['contact']
        self.qry_where = []
        self.qry_orderby = []

    def add_field(self, fieldid):
        '''
        Add a field to query.
        The caller is reponsible for checking requesting user is authorized to query that field.
        '''
        fieldid = str(fieldid)
        self.qry_from.append('LEFT JOIN contact_field_value AS cfv%(fid)s ON (contact.id = cfv%(fid)s.contact_id AND cfv%(fid)s.contact_field_id = %(fid)s)' % {'fid':fieldid})
        self.qry_fields[DISP_FIELD_PREFIX+fieldid] = 'cfv%(fid)s.value' % {'fid':fieldid}

    def add_group(self, group_id):
        '''
        Add a group to query.
        The caller is reponsible for checking requesting user is authorized to view that group's members.
        '''
        group_flags_key = 'group_%s_flags' % group_id
        if group_flags_key in self.qry_fields:
            # We already have these fields
            return

        # Add fields for direct membership
        self.qry_fields[group_flags_key] = 'cig_%s.flags' % group_id
        self.qry_from.append('LEFT JOIN contact_in_group AS cig_%(gid)s ON (contact.id = cig_%(gid)s.contact_id AND cig_%(gid)s.group_id=%(gid)s)' % {'gid': group_id})

        # Add fields for indirect membership
        # Use postgresql 'bit_or' aggregate function to get all inherited flags at once in a single column
        self.qry_fields['group_%s_inherited_flags' % group_id] = 'cig_inherited_%s.flags' % group_id
        self.qry_from.append('LEFT JOIN (SELECT contact_id, bit_or(flags) AS flags FROM contact_in_group WHERE contact_in_group.group_id IN (SELECT self_and_subgroups(%(gid)s)) AND contact_in_group.group_id<>%(gid)s GROUP BY contact_id) AS cig_inherited_%(gid)s ON (contact.id = cig_inherited_%(gid)s.contact_id)' % {'gid': group_id})

    def add_group_withnote(self, group_id):
        '''
        Like add_group, but also adds the note in the list of columns to be returned.
        The caller is reponsible for checking requesting user is authorized to view that group's members.
        '''
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
        #print(repr(self.raw_query), repr(self.params))
        for x in RawQuerySet.__iter__(self):
            yield x


def contact_make_query_with_fields(user_id, fields, current_cg=None, base_url=None, format='html'):
    '''
    Creates an iterable objects with all the required fields (including groups).
    returns a tupple (query, columns)
    Permissions are checked for the fields. Forbidden field/groups are skiped.
    '''
    q = ContactQuerySet(Contact._default_manager.model, using=Contact._default_manager._db)
    cols = []

    for prop in fields:
        if prop == 'name':
            if format == 'html':
                cols.append( ('Name', None, 'name_with_relative_link', 'name') )
            else:
                cols.append( ('Name', None, '__unicode__', 'name') )
        elif prop.startswith(DISP_GROUP_PREFIX):
            groupid = int(prop[len(DISP_GROUP_PREFIX):])

            if not perms.c_can_see_members_cg(user_id, groupid):
                continue # just ignore groups that aren't allowed to be seen

            q.add_group(groupid)

            cg = ContactGroup.objects.get(pk=groupid)

            cols.append( (cg.name, None, membership_to_text_factory(groupid), None) )
            #cols.append( (cg.name, None, lambda c: membership_extended_widget(c, cg, base_url), None) )
            #cols.append( ('group_%s_flags' % groupid, None, 'group_%s_flags' % groupid, None))

        elif prop.startswith(DISP_FIELD_PREFIX):
            fieldid = prop[len(DISP_FIELD_PREFIX):]
            cf = ContactField.objects.get(pk=fieldid)

            if not perms.c_can_view_fields_cg(user_id, cf.contact_group_id):
                continue # Just ignore fields that can't be seen

            q.add_field(fieldid)

            if format == 'html':
                cols.append( (cf.name, cf.format_value_html, prop, prop) )
            else:
                cols.append( (cf.name, cf.format_value_unicode, prop, prop) )
        else:
            raise ValueError('Invalid field '+prop)

    if current_cg is not None:
        assert base_url
        q.add_group_withnote(current_cg.id)
        if format == 'html':
            cols.append( ('Status', None, lambda c: membership_extended_widget(c, current_cg, base_url), None) )
            #cols.append( ('group_%s_flags' % current_cg.id, None, 'group_%s_flags' % current_cg.id, None))
        else:
            cols.append( ('Status', None, lambda c: membership_to_text(c, current_cg.id), None) )
            cols.append( ('Note', None, 'group_%s_note' % current_cg.id, None) )
    return q, cols


def get_available_fields(user_id):
    result = [ (DISP_NAME, 'Name') ]
    for cf in ContactField.objects.extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % user_id]).order_by('sort_weight'):
        result.append((DISP_FIELD_PREFIX+unicode(cf.id), cf.name))
    for cg in ContactGroup.objects.extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % user_id]).order_by('-date', 'name'):
        result.append((DISP_GROUP_PREFIX+unicode(cg.id), cg.unicode_with_date()))
    return result


class FieldSelectForm(forms.Form):
    '''
    Forms to select fields & groups to display. Only displays:
    - readable field
    - groups whose members can be viewed
    '''
    def __init__(self, user_id, *args, **kargs):
        #TODO: param user -> fine tuned fields selection
        forms.Form.__init__(self, *args, **kargs)
        self.fields['selected_fields'] = forms.MultipleChoiceField(required=False, widget=FilterMultipleSelectWidget('Fields', False), choices=get_available_fields(user_id))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_list(request):
    '''
    That view list all the contacts. See also contactgroup_members()
    '''
    if not perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
        raise PermissionDenied

    strfilter = request.REQUEST.get('filter', '')
    filter = contactsearch.parse_filterstring(strfilter, request.user.id)
    baseurl = '?filter='+strfilter

    strfields = request.REQUEST.get('fields', None)
    if strfields:
        fields = strfields.split(',')
        baseurl += '&fields='+strfields
    else:
        fields = get_display_fields(request.user)
        strfields = ','.join(fields)

    if (request.REQUEST.get('savecolumns')):
        request.user.set_fieldvalue(request.user, FIELD_COLUMNS, strfields)

    #print('contact_list:', fields)
    q, cols = contact_make_query_with_fields(request.user.id, fields, format='html')
    q = filter.apply_filter_to_query(q)

    # TODO:
    # We need to select only members who are in a group whose members the
    # request.user can see:
    #q.qry_where.append('')

    args = {}
    args['title'] = 'Contact list'
    args['baseurl'] = baseurl
    args['objtype'] = Contact
    args['nav'] = Navbar(args['objtype'].get_class_absolute_url().split('/')[1])
    args['query'] = q
    args['cols'] = cols
    args['filter'] = strfilter
    args['fields'] = strfields
    args['fields_form'] = FieldSelectForm(request.user.id, initial={'selected_fields': fields})

    return query_print_entities(request, 'list_contact.html', args)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_detail(request, gid=None, cid=None):
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        if not perms.c_can_see_members_cg(request.user.id, gid):
            raise PermissionDenied
    else:
        # gid is undefined: access through global contact list
        if cid != request.user.id and not perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
            raise PermissionDenied

    c = get_object_or_404(Contact, pk=cid)

    rows = []
    for cf in c.get_all_visible_fields(request.user.id):
        try:
            cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            rows.append((cf.name, mark_safe(cfv.as_html())))
        except ContactFieldValue.DoesNotExist:
            pass # ignore blank values

    args = {}
    args['title'] = 'Details for '+unicode(c)
    if gid:
        #args['title'] += ' in group '+cg.unicode_with_date()
        args['contact_group'] = cg
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component('members')
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
    if cid == request.user.id:
        # The user can see himself
        pass
    elif gid != None and perms.c_can_see_members_cg(request.user.id, gid):
        pass
    elif gid != None and perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
        pass
    else:
        raise PermissionDenied

    # TODO: We should also check the specific fields (email, address, phone,
    # ...) are readable by user

    contact = get_object_or_404(Contact, pk=cid)
    return HttpResponse(contact.vcard().encode('utf-8'), mimetype='text/x-vcard')



class ContactEditForm(forms.Form):
    def __init__(self, user_id, cid=None, contactgroup=None, *args, **kargs):
        # Note that user_id is the id of the contact making the query, not the
        # one beeing edited
        forms.Form.__init__(self, *args, **kargs)

        if perms.c_can_write_fields_cg(user_id, GROUP_EVERYBODY):
            self.fields['name'] = forms.CharField()
        if cid:
            contact = get_object_or_404(Contact, pk=cid)
            cfields = contact.get_all_writable_fields(user_id)
            # Here we have all the writable fields, including the one from
            # other groups that the user can see
        elif contactgroup:
            contactgroupids = [ g.id for g in contactgroup.get_self_and_supergroups() ]
            cfields = ContactField.objects.filter(contact_group_id__in = contactgroupids).extra(where=['perm_c_can_write_fields_cg(%s, contact_field.contact_group_id)' % user_id]).order_by('sort_weight')
            # Here we have the fields from contact_group and all its super
            # groups, IF user can write to them
        else: # FIXME
            cfields = []

        # store dbfields
        self.cfields = cfields

        # Add all extra forms.fields from ContactFields
        for cf in cfields:
            f = cf.get_form_fields()
            if f:
                self.fields[unicode(cf.id)] = f


@login_required()
@require_group(GROUP_USER_NGW)
def contact_edit(request, gid=None, cid=None):
    if gid: # edit/add in a group
        if not perms.c_can_see_members_cg(request.user.id, gid):
            raise PermissionDenied
        cg = get_object_or_404(ContactGroup, pk=gid)
    else: # edit out of a group
        if request.user.id == cid:
            # Everybody can edit his own data
            pass
        elif not perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
            raise PermissionDenied
        cg = None

    if cid: # edit existing contact
        cid = int(cid)
    else: # record a new contact
        assert gid, 'Missing required parameter gid' # FIXME: remove from urls.py

    objtype = Contact
    if cid:
        contact = get_object_or_404(Contact, pk=cid)
        title = 'Editing '+unicode(contact)
    else:
        title = 'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactEditForm(request.user.id, cid=cid, data=request.POST, contactgroup=cg)
        # TODO: New forms system, when bound to a models, should provide a save() method
        if form.is_valid():
            data = form.clean()
            #print('saving', repr(form.data))

            # record the values

            # 1/ The contact name
            if cid:
                if perms.c_can_write_fields_cg(request.user.id, GROUP_EVERYBODY):
                    if contact.name != data['name']:
                        log = Log(contact_id=request.user.id)
                        log.action = LOG_ACTION_CHANGE
                        log.target = 'Contact ' + unicode(contact.id)
                        log.target_repr = 'Contact ' + contact.name
                        log.property = 'Name'
                        log.property_repr = 'Name'
                        log.change = 'change from ' + contact.name + ' to ' + data['name']
                        log.save()

                    contact.name = data['name']
                    contact.save()

            else:
                if not perms.c_can_write_fields_cg(request.user.id, GROUP_EVERYBODY):
                    # If user can't write name, we have a problem creating a new contact
                    raise PermissionDenied
                contact = Contact(name=data['name'])
                contact.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_ADD
                log.target = 'Contact ' + unicode(contact.id)
                log.target_repr = 'Contact ' + contact.name
                log.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'Contact ' + unicode(contact.id)
                log.target_repr = 'Contact ' + contact.name
                log.property = 'Name'
                log.property_repr = 'Name'
                log.change = 'new value is ' + contact.name
                log = Log(request.user.id)

                cig = ContactInGroup(contact_id=contact.id, group_id=gid)
                cig.member = True
                cig.save()
                # TODO: Log new cig


            # 2/ In ContactFields
            for cf in form.cfields:
                if cf.type == FTYPE_PASSWORD:
                    continue
                #cfname = cf.name
                cfid = cf.id
                newvalue = data[unicode(cfid)]
                if newvalue != None:
                    newvalue = cf.formfield_value_to_db_value(newvalue)
                contact.set_fieldvalue(request.user, cf, newvalue)

            messages.add_message(request, messages.SUCCESS, 'Contact %s has been saved sucessfully!' % contact.name)

            if cg:
                base_url = cg.get_absolute_url() + 'members/' + unicode(contact.id) + '/'
            else:
                base_url = contact.get_class_absolute_url() + unicode(contact.id) + '/'

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(base_url + 'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(base_url + '../add')
            elif perms.c_can_see_members_cg(request.user.id, GROUP_EVERYBODY):
                return HttpResponseRedirect(base_url)
            else:
                return HttpResponseRedirect('/')

        # else add/update failed validation
    else: # GET /  HEAD
        initialdata = {}
        if cid: # modify existing
            initialdata['name'] = contact.name

            for cfv in contact.values.all():
                cf = cfv.contact_field
                if cf.type != FTYPE_PASSWORD:
                    initialdata[unicode(cf.id)] = cf.db_value_to_formfield_value(cfv.value)
            form = ContactEditForm(request.user.id, cid=cid, initial=initialdata, contactgroup=cg)

        else:
            for cf in ContactField.objects.all():
                if cf.default:
                    if cf.type == FTYPE_DATE and cf.default == 'today':
                        initialdata[unicode(cf.id)] = date.today()
                    else:
                        initialdata[unicode(cf.id)] = cf.db_value_to_formfield_value(cf.default)

            if cg:
                initialdata['groups'] = [ cg.id ]
                form = ContactEditForm(request.user.id, cid=cid, initial=initialdata, contactgroup=cg)
            else:
                form = ContactEditForm(request.user.id, cid=cid)

    args = {}
    args['form'] = form
    args['title'] = title
    args['id'] = cid
    args['objtype'] = objtype
    if gid:
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component('members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    if cid:
        args['nav'].add_component(contact.get_navcomponent())
        args['nav'].add_component('edit')
    else:
        args['nav'].add_component('add')
    if cid:
        args['o'] = contact

    return render_to_response('edit.html', args, RequestContext(request))


class ContactPasswordForm(forms.Form):
    new_password = forms.CharField(max_length=50, widget=forms.PasswordInput())
    confirm_password = forms.CharField(max_length=50, widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', '') != self.cleaned_data.get('confirm_password', ''):
            raise forms.ValidationError('The passwords must match!')
        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass(request, gid=None, cid=None):
    if gid is not None:
        gid = int(gid)
    cid = int(cid)
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    args = {}
    args['title'] = 'Change password'
    args['contact'] = contact
    if request.method == 'POST':
        form = ContactPasswordForm(request.POST)
        if form.is_valid():
            # record the value
            password = form.clean()['new_password']
            contact.set_password(request.user, password)
            messages.add_message(request, messages.SUCCESS, 'Password has been changed sucessfully!')
            if gid:
                cg = get_object_or_404(ContactGroup, pk=gid)
                return HttpResponseRedirect(cg.get_absolute_url() + 'members/' + unicode(cid) + '/')
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else: # GET
        form = ContactPasswordForm()
    args['form'] = form
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component('members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component('password')
    try:
        args['PASSWORD_LETTER'] = settings.PASSWORD_LETTER
        # So here the 'reset by letter' button will be enabled
    except AttributeError:
        pass # it's ok not to have a letter
    return render_to_response('password.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER) # not GROUP_USER_NGW
def hook_change_password(request):
    newpassword_plain = request.POST.get('password')
    if not newpassword_plain:
        return HttpResponse('Missing password POST parameter')
    #TODO: check strength
    request.user.set_password(request.user, newpassword_plain)
    return HttpResponse('OK')


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass_letter(request, gid=None, cid=None):
    if gid is not None:
        gid = int(gid)
    cid = int(cid)
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    args = {}
    args['title'] = 'Generate a new password and print a letter'
    args['contact'] = contact
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component('members')
    else:
        args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component('password letter')

    if request.method == 'POST':
        new_password = Contact.generate_password()

        # record the value
        contact.set_password(request.user, new_password, '2') # Generated and mailed
        messages.add_message(request, messages.SUCCESS, 'Password has been changed sucessfully!')

        fields = {}
        for cf in contact.get_all_visible_fields(request.user.id):
            try:
                cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            except ContactFieldValue.DoesNotExist:
                continue
            fields[cf.name] = unicode(cfv).replace('\r', '')
            #if cfv:
            #    rows.append((cf.name, mark_safe(cfv.as_html())))
        fields['name'] = contact.name
        fields['password'] = new_password

        filename = ngw_mailmerge(settings.PASSWORD_LETTER, fields, '/usr/lib/ngw/mailing/generated/')
        if not filename:
            return HttpResponse('File generation failed')

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
    o = get_object_or_404(Contact, pk=cid)
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        base_nav = cg.get_smart_navbar()
        base_nav.add_component('members')
        next_url = cg.get_absolute_url() + 'members/'
    else:
        next_url = reverse('ngw.core.views.contact_list')
        base_nav = None
    return generic_delete(request, o, next_url, base_nav=base_nav)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_add(request, cid=None):
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_str = request.GET['filterstr']
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if filter_list_str:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    else:
        filter_list = []
    filter_list.append(('No name', filter_str))
    filter_list_str = ','.join(['"' + name + '","' + filterstr + '"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request.user, FIELD_FILTERS, filter_list_str)
    messages.add_message(request, messages.SUCCESS, 'Filter has been added sucessfully!')
    return HttpResponseRedirect(reverse('ngw.core.views.contact_filters_edit', args=(cid, len(filter_list)-1)))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_list(request, cid=None):
    if cid != request.user.id and not perms.c_can_view_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    filters = []
    if filter_list_str:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
        filters = [ filtername for filtername, filter_str in filter_list ]
    args = {}
    args['title'] = 'User custom filters'
    args['contact'] = contact
    args['filters'] = filters
    args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component(('filters', 'custom filters'))
    return render_to_response('customfilters_user.html', args, RequestContext(request))


class FilterEditForm(forms.Form):
    name = forms.CharField(max_length=50)

@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_edit(request, cid=None, fid=None):
    # Warning, here fid is the index in the filter list of a given user
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if not filter_list_str:
        return HttpResponse('ERROR: no custom filter for that user')
    else:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    try:
        filtername, filterstr = filter_list[int(fid)]
    except (IndexError, ValueError):
        return HttpResponse("ERROR: Can't find filter #"+fid)

    if request.method == 'POST':
        form = FilterEditForm(request.POST)
        if form.is_valid():
            #print(repr(filter_list))
            #print(repr(filter_list_str))
            filter_list[int(fid)]=(form.clean()['name'], filterstr)
            #print(repr(filter_list))
            filter_list_str = ','.join(['"' + name + '","' + filterstr + '"' for name, filterstr in filter_list])
            #print(repr(filter_list_str))
            contact.set_fieldvalue(request.user, FIELD_FILTERS, filter_list_str)
            messages.add_message(request, messages.SUCCESS, 'Filter has been renamed sucessfully!')
            return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else:
        form = FilterEditForm(initial={ 'name': filtername })
    args = {}
    args['title'] = 'User custom filter renaming'
    args['contact'] = contact
    args['form'] = form
    args['filtername'] = filtername
    try:
        filter_html = contactsearch.parse_filterstring(filterstr, request.user.id).to_html()
    except PermissionDenied:
        filter_html = "[Permission was denied to explain that filter. You probably don't have access to the fields / group names it is using.]<br>Raw filter=%s" % filterstr
    args['filter_html'] = filter_html
    args['nav'] = Navbar(Contact.get_class_navcomponent())
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component(('filters', 'custom filters'))
    args['nav'].add_component((unicode(fid), filtername))

    return render_to_response('customfilter_user.html', args, RequestContext(request))


#@login_required()
#@require_group(GROUP_ADMIN)
#def contact_make_login_mailing(request):
#    # select contacts whose password is in state 'Registered', with both 'Adress' and 'City' not null
#    q = Contact.objects
#    q = q.extra(where=["EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value='%(value)s')" % { 'field_id': FIELD_PASSWORD_STATUS, 'value': '1' }])
#    q = q.extra(where=['EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i)' % { 'field_id': FIELD_STREET}])
#    q.extra(where=['EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i)' % { 'field_id': FIELD_CITY}])
#    ids = [ row.id for row in q ]
#    #print(ids)
#    if not ids:
#        return HttpResponse('No waiting mail')
#
#    result = ngw_mailmerge('/usr/lib/ngw/mailing/forms/welcome.odt', [str(id) for id in ids])
#    if not result:
#        return HttpResponse('File generation failed')
#    #print(result)
#    filename = os.path.basename(result)
#    if subprocess.call(['sudo', '/usr/bin/mvoomail', os.path.splitext(filename)[0], '/usr/lib/ngw/mailing/generated/']):
#        return HttpResponse('File move failed')
#    for row in q:
#        contact = row[0]
#        contact.set_fieldvalue(request.user, FIELD_PASSWORD_STATUS, '2')
#
#    return HttpResponse('File generated in /usr/lib/ngw/mailing/generated/')


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
            return l[:LIST_PREVIEW_LEN] + ['…']
        return l
    def _trucate_description(cg):
        DESCRIPTION_MAXLEN = 200
        if len(cg.description) < DESCRIPTION_MAXLEN:
            return cg.description
        else:
            return cg.description[:DESCRIPTION_MAXLEN] + '…'

	
    def print_fields(cg):
        if cg.field_group:
            fields = cg.contact_fields
            if fields:
                return ', '.join(['<a href="' + f.get_absolute_url() + '">'+html.escape(f.name) + '</a>' for f in fields])
            else:
                return 'Yes (but none yet)'
        else:
            return 'No'

    q = ContactGroup.objects.filter(date=None).extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    cols = [
        #( 'Date', None, 'html_date', ContactGroup.date ),
        ( 'Name', None, 'name', 'name' ),
        ( 'Description', None, lambda cg: _trucate_description(cg), None ),
        #( 'Description', None, 'description', lambda cg: len(cg.description)<100 and cg.description + '!!' or cg.description[:100] + '…', None ),
        #( 'Contact fields', None, print_fields, 'field_group' ),
        ( 'Super\u00a0groups', None, lambda cg: ', '.join(_trucate_list([sg.unicode_with_date() for sg in cg.get_direct_supergroups().extra(where=['perm_c_can_see_cg(%s, id)' % request.user.id])[:LIST_PREVIEW_LEN+1]])), None ),
        ( 'Sub\u00a0groups', None, lambda cg: ', '.join(_trucate_list([html.escape(sg.unicode_with_date()) for sg in cg.get_direct_subgroups().extra(where=['perm_c_can_see_cg(%s, id)' % request.user.id])][:LIST_PREVIEW_LEN+1])), None ),
        #( 'Budget\u00a0code', None, 'budget_code', 'budget_code' ),
        #( 'Members', None, lambda cg: str(len(cg.get_members())), None ),
        #( 'System\u00a0locked', None, 'system', 'system' ),
    ]
    args = {}
    args['title'] = 'Select a contact group'
    args['query'] = q
    args['cols'] = cols
    args['objtype'] = ContactGroup
    args['nav'] = Navbar(ContactGroup.get_class_navcomponent())
    return query_print_entities(request, 'list.html', args)


MONTHES = 'January,February,March,April,May,June,July,August,Septembre,October,November,December'.split(',')

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
        return '%s %s' % (MONTHES[self.month-1], self.year)

    def prev_month(self):
        year, month = self.year, self.month
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        return '%s-%s' % (year, month)

    def next_month(self):
        year, month = self.year, self.month
        month += 1
        if month > 12:
            month = 1
            year += 1
        return '%s-%s' % (year, month)

    def prev_year(self):
        return '%s-%s' % (self.year-1, self.month)

    def next_year(self):
        return '%s-%s' % (self.year+1, self.month)

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
    dt = request.REQUEST.get('dt', None)
    year = month = None
    if dt is not None:
        try:
            year, month = dt.split('-')
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

    q = ContactGroup.objects.filter(date__gte=min_date, date__lte=max_date).extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])

    cols = [
        ( 'Date', None, 'html_date', 'date' ),
        ( 'Name', None, 'name', 'name' ),
        ( 'Description', None, 'description', 'description' ),
    ]

    month_events = {}
    for cg in q:
        if not month_events.has_key(cg.date):
            month_events[cg.date] = []
        month_events[cg.date].append(cg)

    args = {}
    args['title'] = 'Events'
    args['query'] = q
    args['cols'] = cols
    args['objtype'] = ContactGroup
    args['nav'] = Navbar()
    args['nav'].add_component(('events', 'Events'))
    args['year_month'] = YearMonthCal(year, month, month_events)
    args['today'] = date.today()
    return query_print_entities(request, 'list_events.html', args)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_members(request, gid, output_format=''):
    if not perms.c_can_see_members_cg(request.user.id, gid):
        raise PermissionDenied

    strfilter = request.REQUEST.get('filter', '')
    filter = contactsearch.parse_filterstring(strfilter, request.user.id)
    baseurl = '?filter='+strfilter

    strfields = request.REQUEST.get('fields', None)
    if strfields:
        fields = strfields.split(',')
        baseurl += '&fields='+strfields
    else:
        fields = get_display_fields(request.user)
        strfields = ','.join(fields)
        # baseurl doesn't need to have default fields
        # They'll still be default next time

    if request.REQUEST.get('savecolumns'):
        request.user.set_fieldvalue(request.user, FIELD_COLUMNS, strfields)

    cg = get_object_or_404(ContactGroup, pk=gid)

    display = request.REQUEST.get('display', None)
    if display is None:
        display = cg.get_default_display()
    baseurl += '&display='+display

    args = {}
    args['fields_form'] = FieldSelectForm(request.user.id, initial={'selected_fields': fields})
    if output_format == 'csv':
        query_format = 'text'
    else:
        query_format = 'html'
    q, cols = contact_make_query_with_fields(request.user.id, fields, current_cg=cg, base_url=baseurl, format=query_format)

    cig_conditions_flags = []
    if 'm' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_MEMBER)
        args['display_member'] = 1
    if 'i' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_INVITED)
        args['display_invited'] = 1
    if 'd' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_DECLINED)
        args['display_declined'] = 1
    if 'o' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_OPERATOR)
        args['display_operator'] = 1
    if 'v' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_VIEWER)
        args['display_viewer'] = 1

    if cig_conditions_flags:
        cig_conditions_flags = ' AND (%s)' % ' OR '.join(cig_conditions_flags)
    else:
        cig_conditions_flags = ' AND False' # display nothing

    if 'g' in display and ('o' in display or 'v' in display):
        raise ValueError("Can't display both inherited memberships and operators/viewers")
    if 'g' in display:
        cig_conditions_group = 'group_id IN (SELECT self_and_subgroups(%s))' % cg.id
        args['display_subgroups'] = 1
    else:
        cig_conditions_group = 'group_id=%d' % cg.id

    q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND ' + cig_conditions_group + cig_conditions_flags + ')')
    q = filter.apply_filter_to_query(q)

    if output_format == 'vcards':
        #FIXME: This works but is really inefficient (try it on a large group!)
        result = ''
        for contact in q:
            result += contact.vcard()
        return HttpResponse(result.encode('utf-8'), mimetype='text/x-vcard')
    elif output_format == 'emails':
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

        args['title'] = 'Emails for ' + cg.name
        args['strfilter'] = strfilter
        args['filter'] = filter
        args['cg'] = cg
        args['emails'] = emails
        args['noemails'] = noemails
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component('members')
        args['nav'].add_component('emails')
        return render_to_response('emails.html', args, RequestContext(request))
    elif output_format == 'csv':
        result = ''
        def _quote_csv(u):
            return '"' + u.replace('"', '\\"') + '"'
        for i, col in enumerate(cols):
            if i: # not first column
                result += ','
            result += _quote_csv(col[0])
        result += '\n'
        for row in q:
            for i, col in enumerate(cols):
                if i: # not first column
                    result += ','
                v = ngw_display(row, col)
                if v == None:
                    continue
                result += _quote_csv(v)
            result += '\n'
        return HttpResponse(result, mimetype='text/csv; charset=utf-8')

    if perms.c_can_see_files_cg(request.user.id, gid):
        folder = cg.static_folder()
        try:
            files = os.listdir(folder)
        except OSError as (errno, errmsg):
            messages.add_message(request, messages.ERROR, 'Error while reading shared files list in %s: %s' % (folder, errmsg))
            files = []

        # listdir() returns some data in utf-8, we want everything in unicode:
        unicode_files = []
        for file in files:
            if isinstance(file, unicode):
                unicode_files.append(file)
            else:
                unicode_files.append(unicode(file, 'utf8', 'replace'))
        files = unicode_files

        if '.htaccess' in files:
            files.remove('.htaccess')
        files.sort()
    else:
        files = None

    args['title'] = 'Contacts of group ' + cg.unicode_with_date()
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
    args['nav'].add_component('members')

    response = query_print_entities(request, 'group_detail.html', args)
    #from django.db import connection
    #import pprint
    #pprint.PrettyPrinter(indent=4).pprint(connection.queries)
    return response


class ContactGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(required=False, widget=forms.Textarea)
    date = forms.DateField(required=False, help_text='Use YYYY-MM-DD format. Leave empty for permanent groups.', widget=NgwCalendarWidget(attrs={'class':'vDateField'}))
    budget_code = forms.CharField(required=False, max_length=10)
    sticky = forms.BooleanField(required=False, help_text='If set, automatic membership because of subgroups becomes permanent. Use with caution.')
    field_group = forms.BooleanField(required=False, help_text='Does that group yield specific fields to its members?')
    mailman_address = forms.CharField(required=False, max_length=255, help_text='Mailing list address, if the group is linked to a mailing list.')
    has_news = forms.BooleanField(required=False, help_text='Does that group supports internal news system?')
    direct_supergroups = forms.MultipleChoiceField(required=False, help_text='Members will automatically be granted membership in these groups.', widget=FilterMultipleSelectWidget('groups', False))
    operator_groups = forms.MultipleChoiceField(required=False, help_text='Members of these groups will automatically be granted administrative priviledges.', widget=FilterMultipleSelectWidget('groups', False))
    viewer_groups = forms.MultipleChoiceField(required=False, help_text='Members of these groups will automatically be granted viewer priviledges.', widget=FilterMultipleSelectWidget('groups', False))

    def __init__(self, for_user, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        self.fields['direct_supergroups'].choices = [ (g.id, g.unicode_with_date()) for g in ContactGroup.objects.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % for_user]).order_by('-date', 'name') ]
        self.fields['operator_groups'].choices = [ (g.id, g.unicode_with_date()) for g in ContactGroup.objects.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % for_user]).order_by('-date', 'name') ]
        self.fields['viewer_groups'].choices = [ (g.id, g.unicode_with_date()) for g in ContactGroup.objects.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % for_user]).order_by('-date', 'name') ]


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_edit(request, id):
    objtype = ContactGroup
    if id:
        cg = get_object_or_404(ContactGroup, pk=id)
        if not perms.c_can_change_cg(request.user.id, id):
            raise PermissionDenied
        title = 'Editing ' + cg.unicode_with_date()
    else:
        title = 'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ContactGroupForm(request.user.id, request.POST)
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

            # Update the super groups
            old_direct_supergroups_ids = set(cg.get_visible_direct_supergroups_ids(request.user.id))
            new_direct_supergroups_id = set([int(i) for i in data['direct_supergroups']])
            if cg.id != GROUP_EVERYBODY and not new_direct_supergroups_id:
                new_direct_supergroups_id = { GROUP_EVERYBODY }

            supergroup_added = new_direct_supergroups_id - old_direct_supergroups_ids
            supergroup_removed = old_direct_supergroups_ids - new_direct_supergroups_id

            print('supergroup_added=', supergroup_added)
            print('supergroup_removed=', supergroup_removed)
            for sgid in supergroup_added:
                GroupInGroup(father_id=sgid, subgroup_id=cg.id).save()
            for sgid in supergroup_removed:
                GroupInGroup.objects.get(father_id=sgid, subgroup_id=cg.id).delete()

            # Update the operator groups
            old_operator_groups_ids = set(cg.get_visible_operator_mananger_groups_ids(request.user.id))
            new_operator_groups_ids = set([int(ogid) for ogid in data['operator_groups']])
            operatorgroup_added = new_operator_groups_ids - old_operator_groups_ids
            operatorgroup_removed = old_operator_groups_ids - new_operator_groups_ids
            print('operatorgroup_added=', operatorgroup_added)
            print('operatorgroup_removed=', operatorgroup_removed)
            for ogid in operatorgroup_added:
                try:
                    gmg = GroupManageGroup.objects.get(father_id=ogid, subgroup_id=cg.id)
                except GroupManageGroup.DoesNotExist:
                    gmg = GroupManageGroup(father_id=ogid, subgroup_id=cg.id, flags=0)
                gmg.flags |= CIGFLAG_OPERATOR
                gmg.save()
            for ogid in operatorgroup_removed:
                gmg = GroupManageGroup.objects.get(father_id=ogid, subgroup_id=cg.id)
                gmg.flags &= ~ CIGFLAG_OPERATOR
                if gmg.flags:
                    gmg.save()
                else:
                    gmg.delete()

            # Update the viewer groups
            old_viewer_groups_ids = set(cg.get_visible_viewer_mananger_groups_ids(request.user.id))
            new_viewer_groups_ids = set([int(ogid) for ogid in data['viewer_groups']])
            viewergroup_added = new_viewer_groups_ids - old_viewer_groups_ids
            viewergroup_removed = old_viewer_groups_ids - new_viewer_groups_ids
            print('viewergroup_added=', viewergroup_added)
            print('viewergroup_removed=', viewergroup_removed)
            for vgid in viewergroup_added:
                try:
                    gmg = GroupManageGroup.objects.get(father_id=vgid, subgroup_id=cg.id)
                except GroupManageGroup.DoesNotExist:
                    gmg = GroupManageGroup(father_id=vgid, subgroup_id=cg.id, flags=0)
                gmg.flags |= CIGFLAG_VIEWER
                gmg.save()
            for vgid in viewergroup_removed:
                gmg = GroupManageGroup.objects.get(father_id=vgid, subgroup_id=cg.id)
                gmg.flags &= ~ CIGFLAG_VIEWER
                if gmg.flags:
                    gmg.save()
                else:
                    gmg.delete()

            messages.add_message(request, messages.SUCCESS, 'Group %s has been changed sucessfully!' % cg.unicode_with_date())

            cg.check_static_folder_created()
            Contact.check_login_created(request.user) # subgroups change

            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cg.get_absolute_url() + 'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cg.get_class_absolute_url() + 'add')
            else:
                return HttpResponseRedirect(cg.get_absolute_url())

    else: # GET
        if id:
            initialdata = {
                'name': cg.name,
                'description': cg.description,
                'field_group': cg.field_group,
                'sticky': cg.sticky,
                'date': cg.date,
                'budget_code': cg.budget_code,
                'mailman_address': cg.mailman_address,
                'has_news': cg.has_news,
                'direct_supergroups': cg.get_visible_direct_supergroups_ids(request.user.id),
                'operator_groups': cg.get_visible_operator_mananger_groups_ids(request.user.id),
                'viewer_groups': cg.get_visible_viewer_mananger_groups_ids(request.user.id),
            }
            form = ContactGroupForm(request.user.id, initialdata)
        else: # add new one
            form = ContactGroupForm(request.user.id)
    args = {}
    args['title'] = title
    args['id'] = id
    args['objtype'] = objtype
    args['form'] = form
    if id:
        args['o'] = cg
        args['nav'] = cg.get_smart_navbar()
        args['nav'].add_component('edit')
    else:
        args['nav'] = Navbar(ContactGroup.get_class_navcomponent())
        args['nav'].add_component('add')

    return render_to_response('edit.html', args, RequestContext(request))


def on_contactgroup_delete(cg):
    """
    All subgroups will now have their fathers' fathers as direct fathers
    """
    supergroups_ids = set(cg.get_direct_supergroups_ids())
    for subcg in cg.get_direct_subgroups():
        sub_super = set(subcg.get_direct_supergroups_ids())
        #print(repr(subcg), "had these fathers:", sub_super)
        sub_super = sub_super | supergroups_ids - { cg.id }
        if not sub_super:
            sub_super = { GROUP_EVERYBODY }
        #print(repr(subcg), "new fathers:", sub_super)
        subcg.set_direct_supergroups_ids(sub_super)
        #print(repr(subcg), "new fathers double check:", subcg.get_direct_supergroups_ids())
    # TODO: delete static folder


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_delete(request, id):
    if not perms.c_can_change_cg(request.user.id, id):
        raise PermissionDenied
    o = get_object_or_404(ContactGroup, pk=id)
    next_url = reverse('ngw.core.views.contactgroup_list')
    if o.system:
        messages.add_message(request, messages.ERROR, 'Group %s is locked and CANNOT be deleted.' % o.name)
        return HttpResponseRedirect(next_url)
    return generic_delete(request, o, next_url, ondelete_function=on_contactgroup_delete)# args=(p.id,)))


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_add_contacts_to(request):
    if request.method == 'POST':
        target_gid = request.POST['group']
        if target_gid:
            if not perms.c_can_change_members_cg(request.user.id, target_gid):
                raise PermissionDenied
            target_group = get_object_or_404(ContactGroup, pk=target_gid)
            modes=''
            if request.REQUEST.get('membership_member', False):
                modes += '+m'
            if request.REQUEST.get('membership_invited', False):
                modes += '+i'
            if request.REQUEST.get('membership_declined', False):
                modes += '+d'
            if request.REQUEST.get('membership_operator', False):
                modes += '+o'
            if request.REQUEST.get('membership_viewer', False):
                modes += '+v'
            if not modes:
                raise ValueError('You must select at least one mode')

            contacts = []
            for param in request.POST:
                if not param.startswith('contact_'):
                    continue
                contact_id = param[len('contact_'):]
                contact = get_object_or_404(Contact, pk=contact_id)
                contacts.append(contact)
            target_group.set_member_n(request.user, contacts, modes)

            return HttpResponseRedirect(target_group.get_absolute_url())
        else:
            messages.add_message(request, messages.ERROR, 'You must select a target group')

    gid = request.REQUEST.get('gid', '')
    assert gid
    if not perms.c_can_see_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)

    strfilter = request.REQUEST.get('filter', '')
    filter = contactsearch.parse_filterstring(strfilter, request.user.id)

    q, cols = contact_make_query_with_fields(request.user.id, [], format='html') #, current_cg=cg)

    q = q.order_by('name')

    display = request.REQUEST.get('display', None)
    if display is None:
        display = cg.get_default_display()
    cig_conditions_flags = []
    if 'm' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_MEMBER)
    if 'i' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_INVITED)
    if 'd' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_DECLINED)
    if 'o' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_OPERATOR)
    if 'v' in display:
        cig_conditions_flags.append('flags & %s <> 0' % CIGFLAG_VIEWER)

    if cig_conditions_flags:
        cig_conditions_flags = ' AND (%s)' % ' OR '.join(cig_conditions_flags)
    else:
        cig_conditions_flags = ' AND False' # display nothing

    if 'g' in display and ('o' in display or 'v' in display):
        raise ValueError("Can't display both inherited memberships and operators")
    if 'g' in display:
        cig_conditions_group = 'group_id IN (SELECT self_and_subgroups(%s))' % cg.id
    else:
        cig_conditions_group = 'group_id=%d' % cg.id

    q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND ' + cig_conditions_group+cig_conditions_flags + ')')
    q = filter.apply_filter_to_query(q)

    args = {}
    args['title'] = 'Add contacts to a group'
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component(('add_contacts_to', 'add contacts to'))
    args['groups'] = ContactGroup.objects.extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % request.user.id]).order_by('-date', 'name')
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
    viewer = forms.BooleanField(required=False)
    note = forms.CharField(required=False)

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        self.fields['invited'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.declined_invitation.checked=false; this.form.member.checked=false;}'}
        self.fields['declined_invitation'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.invited.checked=false; this.form.member.checked=false;}'}
        self.fields['member'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.invited.checked=false; this.form.declined_invitation.checked=false; }'}
        self.fields['operator'].widget.attrs = { 'onchange': 'if (this.checked) { this.form.viewer.checked=true; }'}

    def clean(self):
        data = self.cleaned_data
        if   (data['invited'] and data['declined_invitation']) \
          or (data['declined_invitation'] and data['member']) \
          or (data['invited'] and data['member']) :
            raise forms.ValidationError('Invalid flags combinaison')
        return data


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit(request, gid, cid):
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    try:
        cig = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        cig = ContactInGroup(contact_id=cid, group_id=gid, flags=0)
    cg = ContactGroup.objects.get(pk=gid)
    contact = Contact.objects.get(pk=cid)
    args = {}
    args['title'] = 'Contact ' + unicode(contact) + ' in group ' + cg.unicode_with_date()
    args['cg'] = cg
    args['contact'] = contact
    args['objtype'] = ContactInGroup

    initial = {}
    initial['invited'] = (cig.flags & CIGFLAG_INVITED) != 0
    initial['declined_invitation'] = (cig.flags & CIGFLAG_DECLINED) != 0
    initial['member'] = (cig.flags & CIGFLAG_MEMBER) != 0
    initial['operator'] = (cig.flags & CIGFLAG_OPERATOR) != 0
    initial['viewer'] = (cig.flags & CIGFLAG_VIEWER) != 0
    initial['note'] = cig.note

    if request.method == 'POST':
        form = ContactInGroupForm(request.POST, initial=initial)
        if form.is_valid():
            data = form.cleaned_data
            if not data['invited'] and not data['declined_invitation'] and not data['member'] and not data['operator'] and not data['viewer']:
                return HttpResponseRedirect(reverse('ngw.core.views.contactingroup_delete', args=(unicode(cg.id), cid))) # TODO update logins deletion, call membership hooks
            cig.flags = 0
            if data['member']:
                cig.flags |= CIGFLAG_MEMBER
            if data['invited']:
                cig.flags |= CIGFLAG_INVITED
            if data['declined_invitation']:
                cig.flags |= CIGFLAG_DECLINED
            if data['operator']:
                cig.flags |= CIGFLAG_OPERATOR
            if data['viewer']:
                cig.flags |= CIGFLAG_VIEWER
            cig.note = data['note']
            messages.add_message(request, messages.SUCCESS, 'Member %s of group %s has been changed sucessfully!' % (contact.name, cg.name))
            Contact.check_login_created(request.user)
            cig.save()
            hooks.membership_changed(request.user, contact, cg)
            return HttpResponseRedirect(cg.get_absolute_url())
    else:
        form = ContactInGroupForm(initial=initial)

    args['form'] = form

    inherited_info = ''

    automember_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, CIGFLAG_MEMBER)]).exclude(id=gid).order_by('-date', 'name')
    visible_automember_groups = automember_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    invisible_automember_groups = automember_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    #print(automember_groups.query)
    if automember_groups:
        inherited_info += 'Automatically member because member of subgroup(s):<br>'
        for sub_cg in visible_automember_groups:
            inherited_info += '<li><a href=\"%(url)s\">%(name)s</a>' % { 'name': sub_cg.unicode_with_date(), 'url': sub_cg.get_absolute_url() }
        if invisible_automember_groups:
            inherited_info += '<li>Hidden group(s)...'
        inherited_info += '<br>'

    autoinvited_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, CIGFLAG_INVITED)]).exclude(id=gid).order_by('-date', 'name')
    visible_autoinvited_groups = autoinvited_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    invisible_autoinvited_groups = autoinvited_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    if autoinvited_groups:
        inherited_info += 'Automatically invited because invited in subgroup(s):<br>'
        for sub_cg in visible_autoinvited_groups:
            inherited_info += '<li><a href=\"%(url)s\">%(name)s</a>' % { 'name': sub_cg.unicode_with_date(), 'url': sub_cg.get_absolute_url() }
        if invisible_autoinvited_groups:
            inherited_info += '<li>Hidden group(s)...'

    args['inherited_info'] = mark_safe(inherited_info)

    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component('members')
    args['nav'].add_component(contact.get_navcomponent())
    args['nav'].add_component('membership')
    return render_to_response('contact_in_group.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit_inline(request, gid, cid):
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    contact = get_object_or_404(Contact, pk=cid)
    newmembership = request.POST['membership']
    if newmembership == 'invited':
        flags = '+i'
    elif newmembership == 'member':
        flags = '+m'
    elif newmembership == 'declined_invitation':
        flags = '+d'
    else:
        raise Exception('invalid membership '+request.POST['membership'])
    cg.set_member_1(request.user, contact, flags)
    hooks.membership_changed(request.user, contact, cg)
    return HttpResponseRedirect(request.POST['next_url'])


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_delete(request, gid, cid):
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    try:
        o = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        return HttpResponse('Error, that contact is not a direct member. Please check subgroups')
    #messages.add_message(request, messages.SUCCESS, '%s has been removed for group %s.' % (cig.contact.name, cig.group.name))
    base_nav = cg.get_smart_navbar()
    base_nav.add_component('members')
    return generic_delete(request, o, next_url=cg.get_absolute_url()+'members/', base_nav=base_nav)
    # TODO: realnav bar is 'remove', not 'delete'


#######################################################################
#
# ContactGroup News
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news(request, gid):
    if not perms.c_can_see_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    args = {}
    args['title'] = 'News for group ' + cg.name
    args['news'] = ContactGroupNews.objects.filter(contact_group=gid)
    args['cg'] = cg
    args['objtype'] = ContactGroupNews
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component('news')
    return render_to_response('news.html', args, RequestContext(request))


class NewsEditForm(forms.Form):
    title = forms.CharField(max_length=50)
    text = forms.CharField(widget=forms.Textarea)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_edit(request, gid, nid):
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    if nid:
        news = get_object_or_404(ContactGroupNews, pk=nid)
        if str(news.contact_group_id) != gid:
            return HttpResponse('ERROR: Group mismatch')

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
            messages.add_message(request, messages.SUCCESS, 'News %s has been changed sucessfully!' % news)

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
    args['title'] = 'News edition'
    args['cg'] = cg
    args['form'] = form
    if nid:
        args['o'] = news
        args['id'] = nid
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component('news')
    if nid:
        args['nav'].add_component(news.get_navcomponent())
        args['nav'].add_component('edit')
    else:
        args['nav'].add_component('add')

    return render_to_response('edit.html', args, RequestContext(request))

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_delete(request, gid, nid):
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    o = get_object_or_404(ContactGroupNews, pk=nid)
    return generic_delete(request, o, cg.get_absolute_url() + 'news/')


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
    if not perms.c_can_see_members_cg(id):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=id)

    args = {}
    args['title'] = 'Mailman synchronisation'
    args['nav'] = cg.get_smart_navbar()
    args['nav'].add_component('mailman')
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
    fields = ContactField.objects.order_by('sort_weight').extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % request.user.id ])
    args = {}
    args['query'] = fields
    args['cols'] = [
        ( 'Name', None, 'name', 'name'),
        ( 'Type', None, 'type_as_html', 'type'),
        ( 'Only for', None, 'contact_group', 'contact_group_id'),
        ( 'System locked', None, 'system', 'system'),
        #( 'Move', None, lambda cf: '<a href='+str(cf.id)+'/moveup>Up</a> <a href='+str(cf.id)+'/movedown>Down</a>', None),
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
    cf = get_object_or_404(ContactField, pk=id)
    cf.sort_weight -= 15
    cf.save()
    ContactField.renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))


@login_required()
@require_group(GROUP_USER_NGW)
def field_move_down(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    cf = get_object_or_404(ContactField, pk=id)
    cf.sort_weight += 15
    cf.save()
    ContactField.renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))


class FieldEditForm(forms.Form):
    name = forms.CharField()
    hint = forms.CharField(required=False, widget=forms.Textarea)
    contact_group = forms.CharField(label='Only for', required=False, widget=forms.Select)
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
        js_test_type_has_choice = ' || '.join([ "this.value=='" + cls.db_type_id + "'"
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
        cf = get_object_or_404(ContactField, pk=id)
        title = 'Editing '+unicode(cf)
        initial['name'] = cf.name
        initial['hint'] = cf.hint
        initial['contact_group'] = cf.contact_group_id
        initial['type'] = cf.type
        initial['choicegroup'] = cf.choice_group_id
        initial['default_value'] = cf.default
        initial['move_after'] = cf.sort_weight-5
    else:
        cf = None
        title = 'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = FieldEditForm(cf, request.POST, initial=initial)
        #print(request.POST)
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
                            args['nav'] = Navbar(cf.get_class_navcomponent(), cf.get_navcomponent(), ('edit', 'delete imcompatible data'))
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

            ContactField.renumber()
            messages.add_message(request, messages.SUCCESS, 'Field %s has been changed sucessfully.' % cf.name)
            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cf.get_absolute_url()+'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cf.get_class_absolute_url()+'add')
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
        args['nav'].add_component('edit')
    else:
        args['nav'].add_component('add')
    return render_to_response('edit.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def field_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = get_object_or_404(ContactField, pk=id)
    next_url = reverse('ngw.core.views.field_list')
    if o.system:
        messages.add_message(request, messages.ERROR, 'Field %s is locked and CANNOT be deleted.' % o.name)
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
        attrs_value['style'] = 'width:90%'
        attrs_key['style'] = 'width:9%; margin-left:1ex;'

        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs_value))
            widgets.append(forms.TextInput(attrs=attrs_key))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay
    def decompress(self, value):
        if value:
            return value.split(',')
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
            return ','.join(data_list)
        return None
    def clean(self, value):
        # check there is no duplicate keys
        # necessary since keys are the id used in <select>
        possibles_values = forms.MultiValueField.clean(self, value).split(',')
        #print('possibles_values=', repr(possibles_values))
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
            self.initial['possible_values'].append('')
            self.initial['possible_values'].append('')
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

        #print('choices=', choices)

        for c in cg.choices.all():
            k = c.key
            if k in choices.keys():
                #print('UPDATING', k)
                c.value = choices[k]
                c.save()
                del choices[k]
            else: # that key has be deleted
                #print('DELETING', k)
                c.delete()
        for k, v in choices.iteritems():
            #print('ADDING', k)
            cg.choices.create(key=k, value=v)

        messages.add_message(request, messages.SUCCESS, 'Choice %s has been saved sucessfully.' % cg.name)
        return cg


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_edit(request, id=None):
    if not request.user.is_admin():
        return unauthorized(request)
    objtype = ChoiceGroup
    if id:
        cg = get_object_or_404(ChoiceGroup, pk=id)
        title = 'Editing '+unicode(cg)
    else:
        cg = None
        title = 'Adding a new '+objtype.get_class_verbose_name()

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, request.POST)
        if form.is_valid():
            cg = form.save(cg, request)
            if request.POST.get('_continue', None):
                return HttpResponseRedirect(cg.get_absolute_url()+'edit')
            elif request.POST.get('_addanother', None):
                return HttpResponseRedirect(cg.get_class_absolute_url()+'add')
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
        args['nav'].add_component('edit')
    else:
        args['nav'].add_component('add')
    return render_to_response('edit.html', args, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_delete(request, id):
    if not request.user.is_admin():
        return unauthorized(request)
    o = get_object_or_404(ChoiceGroup, pk=id)
    return generic_delete(request, o, reverse('ngw.core.views.choicegroup_list'))
