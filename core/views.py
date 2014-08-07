# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
from datetime import *
from decoratedstr import remove_decoration
from copy import copy
import json
from functools import wraps
import crack
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import (CompatibleStreamingHttpResponse, HttpResponse,
    HttpResponseForbidden, HttpResponseRedirect)
from django.utils.safestring import mark_safe
from django.utils import html
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text, smart_text
from django.utils.six import iteritems, itervalues
from django.utils import formats
from django.utils.decorators import available_attrs # python2 compat
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, RequestContext
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django import forms
from django.views import static
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
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


#######################################################################
#
# Login / Logout
#
#######################################################################

def logout(request):
    auth_logout(request)
    return render_to_response('message.html', {
        'message': mark_safe(_('Have a nice day!<br><br><a href="%s">Login again</a>.') % settings.LOGIN_URL)
        }, RequestContext(request))


def require_group(required_group):
    '''
    Decorator to make a view only accept users from a given group. Usage:
    '''
    def decorator(func):
        @wraps(func, assigned=available_attrs(func))
        def inner(request, *args, **kwargs):
            try:
                user = request.user
            except AttributeError:
                raise PermissionDenied
            if not user.is_member_of(required_group):
                raise PermissionDenied
            return func(request, *args, **kwargs)
        return inner
    return decorator

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
                print('Error in default fields: %s has invalid syntax.' % fname)
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
                print('Error in default fields: %s has invalid syntax.' % fname)
                continue
            try:
                ContactField.objects.get(pk=fieldid)
            except ContactField.DoesNotExist:
                print('Error in default fields: There is no field #%d.' % fieldid)
                continue
        else:
            print('Error in default fields: Invalid syntax in "%s".' % fname)
            continue
        result.append(fname)
    if not result:
        result = [ DISP_NAME ]
    return result


#######################################################################
#
# Home
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def home(request):
    operator_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.group_id = contact_group.id AND contact_in_group.contact_id=%s AND contact_in_group.flags & %s <> 0)' % (request.user.id, CIGFLAG_OPERATOR)])

    qry_news = ContactGroupNews.objects.extra(where=['perm_c_can_see_news_cg(%s, contact_group_news.contact_group_id)' % request.user.id])
    paginator = Paginator(qry_news, 7)

    page = request.GET.get('page')
    try:
        news = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        news = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        news = paginator.page(paginator.num_pages)

    return render_to_response('home.html', {
        'title': _('Lastest news'),
        'nav': Navbar(),
        'operator_groups': operator_groups,
        'news': news,
    }, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def test(request):
    context = {
        'title': 'Test',
        'env': os.environ,
        'objtype': Contact,
        'nav': Navbar('test'),
    }
    messages.add_message(request, messages.INFO, 'This is a test')
    return render_to_response('test.html', context, RequestContext(request))


########################################################################
#
# Generic views
#
########################################################################

def query_print(request, template_name, context, forcesort=None):
    '''
    This function renders the query, paginated
    '''
    try:
        object_query_page_length = Config.objects.get(pk='query_page_length')
        NB_LINES_PER_PAGE = int(object_query_page_length.text)
    except (Config.DoesNotExist, ValueError):
        NB_LINES_PER_PAGE = 200

    q = context['query']
    cols = context['cols']

    # get sort column name
    nosort = False
    order = request.REQUEST.get('_order', '')

    if order and not forcesort:
        # disable default sort on column 0 if there's an forcesort parameter
        try:
            intorder = int(order)
        except ValueError:
            if forcesort:
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
    else: # no order and forcesort
        order = ''
    if forcesort:
        q = q.order_by(forcesort)


    paginator = Paginator(q, NB_LINES_PER_PAGE)
    page = request.REQUEST.get('_page', 1)
    try:
        q = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        q = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        q = paginator.page(paginator.num_pages)

    context['query'] = q
    context['cols'] = cols
    context['order'] = order

    context['paginator'] = paginator
    context['page_obj'] = q

    if 'baseurl' not in context:
        context['baseurl'] = '?'
    return render_to_response(template_name, context, RequestContext(request))


# Helper function that is never call directly, hence the lack of authentification check
def generic_delete(request, o, next_url, base_nav=None, ondelete_function=None):
    title = _('Please confirm deletetion')

    confirm = request.GET.get('confirm', '')
    if confirm:
        if ondelete_function:
            ondelete_function(o)
        name = force_text(o)
        log = Log()
        log.contact_id = request.user.id
        log.action = LOG_ACTION_DEL
        pk_names = (o._meta.pk.attname,) # default django pk name
        log.target = force_text(o.__class__.__name__)+' '+' '.join([force_text(o.__getattribute__(fieldname)) for fieldname in pk_names])
        log.target_repr = o.get_class_verbose_name()+' '+name
        o.delete()
        log.save()
        messages.add_message(request, messages.SUCCESS, _('%s has been deleted sucessfully!') % name)
        return HttpResponseRedirect(next_url)
    else:
        nav = base_nav or Navbar(o.get_class_navcomponent())
        nav.add_component(o.get_navcomponent()) \
           .add_component(('delete', _('delete')))
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

    context = {}
    context['title'] = _('Global log')
    context['nav'] = Navbar(Log.get_class_navcomponent())
    context['objtype'] = Log
    context['query'] = Log.objects.all()
    context['cols'] = [
        ( _('Date UTC'), None, 'small_date', 'dt'),
        ( _('User'), None, 'contact', 'contact__name'),
        ( _('Action'), None, 'action_txt', 'action'),
        ( _('Target'), None, 'target_repr', 'target_repr'),
        ( _('Property'), None, 'property_repr', 'property_repr'),
        ( _('Change'), None, 'change', 'change'),
    ]
    return query_print(request, 'list_log.html', context)

#######################################################################
#
# Contacts
#
#######################################################################


def membership_to_text(contact_with_extra_fields, group_id):
    debug_memberships = False
    automatic_member_indicator = '⁂'
    automatic_admin_indicator = '⁑'

    memberships = []
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % group_id)
    if flags is None:
        flags = 0
    flags_inherited = getattr(contact_with_extra_fields, 'group_%s_inherited_flags' % group_id)
    if flags_inherited is None:
        flags_inherited = 0
    flags_ainherited = getattr(contact_with_extra_fields, 'group_%s_inherited_aflags' % group_id)
    if flags_ainherited is None:
        flags_ainherited = 0

    if debug_memberships:
        # That version show everything, even when obvious like
        # Inherited member + member
        for code in 'midoveEcCfFnNuUxX':
            if flags & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm)
        for code in 'mid':
            if flags_inherited & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm + ' ' + automatic_member_indicator)
        for code in 'oveEcCfFnNuUxX':
            if flags_ainherited & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm + ' ' + automatic_admin_indicator)
    else:
        if flags & CIGFLAG_MEMBER:
            memberships.append(_("Member"))
        elif flags_inherited & CIGFLAG_MEMBER:
            memberships.append(_("Member") + " " + automatic_member_indicator)
        elif flags & CIGFLAG_INVITED:
            memberships.append(_("Invited"))
        elif flags_inherited & CIGFLAG_INVITED:
            memberships.append(_("Invited") + " " + automatic_member_indicator)
        elif flags & CIGFLAG_DECLINED:
            memberships.append(_("Declined"))

        for code in 'ovEcCfFnNuUexX':
            if flags & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm)
                if code == 'o':
                    break # Don't show more details then
            elif flags_ainherited & TRANS_CIGFLAG_CODE2INT[code]:
                nice_perm = TRANS_CIGFLAG_CODE2TXT[code]
                nice_perm = nice_perm.replace('_', ' ').capitalize()
                memberships.append(nice_perm + ' ' + automatic_admin_indicator)
                if code == 'o':
                    break # Don't show more details then

    if memberships:
        result = ''
        for membership in memberships:
            if result:
                result = translation.string_concat(result, ', ')
            result = translation.string_concat(result, membership)
        return result
    else:
        return _('No')

def membership_to_text_factory(group_id):
    return lambda contact_with_extra_fields: \
        membership_to_text(contact_with_extra_fields, group_id)


def membership_extended_widget(request, contact_with_extra_fields, contact_group):
    flags = getattr(contact_with_extra_fields, 'group_%s_flags' % contact_group.id)
    if flags is None:
        flags = 0

    return loader.render_to_string('membership_widget.html', {
        'cid': contact_with_extra_fields.id,
        'gid': contact_group.id,
        'membership_str': membership_to_text(contact_with_extra_fields, contact_group.id),
        'note': getattr(contact_with_extra_fields, 'group_%s_note' % contact_group.id),
        'member': flags & CIGFLAG_MEMBER,
        'invited': flags & CIGFLAG_INVITED,
        'declined': flags & CIGFLAG_DECLINED,
        'cig_url': contact_group.get_absolute_url()+'members/'+force_text(contact_with_extra_fields.id),
        'title': contact_with_extra_fields.name+' in group '+contact_group.unicode_with_date(),
        'next_url': request.get_full_path(),
        }, RequestContext(request))


def membership_extended_widget_factory(request, contact_group):
    return lambda contact_with_extra_fields: \
        membership_extended_widget(request, contact_with_extra_fields, contact_group)


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

        # Add column for direct membership / admin
        self.qry_fields[group_flags_key] = 'cig_%s.flags' % group_id
        self.qry_from.append('LEFT JOIN contact_in_group AS cig_%(gid)s ON (contact.id = cig_%(gid)s.contact_id AND cig_%(gid)s.group_id=%(gid)s)' % {'gid': group_id})

        # Add column for indirect membership
        self.qry_fields['group_%s_inherited_flags' % group_id] = 'cig_inherited_%s.flags' % group_id
        self.qry_from.append('''
            LEFT JOIN (
                SELECT contact_id, bit_or(flags) AS flags
                FROM contact_in_group
                WHERE contact_in_group.group_id IN (SELECT self_and_subgroups(%(gid)s))
                    AND contact_in_group.group_id<>%(gid)s
                GROUP BY contact_id) AS cig_inherited_%(gid)s
            ON (contact.id = cig_inherited_%(gid)s.contact_id)''' % {'gid': group_id})

        # Add column for inherited admin
        self.qry_fields['group_%s_inherited_aflags' % group_id] = 'gmg_inherited_%s.flags' % group_id
        self.qry_from.append('''
            LEFT JOIN (
                SELECT contact_id, bit_or(gmg_perms.flags) AS flags
                FROM contact_in_group
                JOIN (
                    SELECT self_and_subgroups(father_id) AS group_id,
                        bit_or(flags) AS flags
                    FROM group_manage_group
                    WHERE subgroup_id=%(gid)s
                    GROUP BY group_id
                ) AS gmg_perms
                ON contact_in_group.group_id=gmg_perms.group_id
                    AND contact_in_group.flags & 1 <> 0
                GROUP BY contact_id
            ) AS gmg_inherited_%(gid)s
            ON contact.id=gmg_inherited_%(gid)s.contact_id''' % {'gid': group_id})

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
        qry += ', '.join(['%s AS "%s"' % (v, k) for k, v in iteritems(self.qry_fields)])
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
        qry += ', '.join(['%s AS %s' % (v, k) for k, v in iteritems(self.qry_fields)])
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


def contact_make_query_with_fields(request, fields, current_cg=None, base_url=None, format='html'):
    '''
    Creates an iterable objects with all the required fields (including groups).
    returns a tupple (query, columns)
    Permissions are checked for the fields. Forbidden field/groups are skiped.

    base_url is almost the "calling" url, but with only these parameters:
     . filter
     . fields
     . display
    It does *not* contain pagination parameters nor format.
    '''

    q = ContactQuerySet(Contact._default_manager.model, using=Contact._default_manager._db)
    cols = []

    user_id = request.user.id
    for prop in fields:
        if prop == 'name':
            if format == 'html':
                cols.append( (_('Name'), None, 'name_with_relative_link', 'name') )
            else:
                cols.append( (_('Name'), None, '__unicode__', 'name') )
        elif prop.startswith(DISP_GROUP_PREFIX):
            groupid = int(prop[len(DISP_GROUP_PREFIX):])

            if not perms.c_can_see_members_cg(user_id, groupid):
                continue # just ignore groups that aren't allowed to be seen

            q.add_group_withnote(groupid)

            cg = ContactGroup.objects.get(pk=groupid)

            #cols.append( (cg.name, None, membership_to_text_factory(groupid), None) )
            cols.append( (cg.name, None, membership_extended_widget_factory(request, cg), None) )
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
            cols.append( (_('Status'), None, membership_extended_widget_factory(request, current_cg), None) )
            #cols.append( ('group_%s_flags' % current_cg.id, None, 'group_%s_flags' % current_cg.id, None))
            #cols.append( ('group_%s_inherited_flags' % current_cg.id, None, 'group_%s_inherited_flags' % current_cg.id, None))
            #cols.append( ('group_%s_inherited_aflags' % current_cg.id, None, 'group_%s_inherited_aflags' % current_cg.id, None))
        else:
            cols.append( (_('Status'), None, lambda c: membership_to_text(c, current_cg.id), None) )
            cols.append( (_('Note'), None, 'group_%s_note' % current_cg.id, None) )
    return q, cols


def get_available_fields(user_id):
    result = [ (DISP_NAME, 'Name') ]
    for cf in ContactField.objects.extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % user_id]).order_by('sort_weight'):
        result.append((DISP_FIELD_PREFIX+force_text(cf.id), cf.name))
    for cg in ContactGroup.objects.extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % user_id]).order_by('-date', 'name'):
        result.append((DISP_GROUP_PREFIX+force_text(cg.id), cg.unicode_with_date()))
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
        request.user.set_fieldvalue(request, FIELD_COLUMNS, strfields)

    #print('contact_list:', fields)
    q, cols = contact_make_query_with_fields(request, fields, format='html')
    q = filter.apply_filter_to_query(q)

    # TODO:
    # We need to select only members who are in a group whose members the
    # request.user can see:
    #q.qry_where.append('')

    context = {}
    context['title'] = _('Contact list')
    context['baseurl'] = baseurl
    context['objtype'] = Contact
    context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['query'] = q
    context['cols'] = cols
    context['filter'] = strfilter
    context['fields'] = strfields
    context['fields_form'] = FieldSelectForm(request.user.id, initial={'selected_fields': fields})
    context['no_confirm_form_discard'] = True

    return query_print(request, 'list_contact.html', context)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_detail(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
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

    context = {}
    context['title'] = _('Details for %s') % force_text(c)
    if gid:
        #context['title'] += ' in group '+cg.unicode_with_date()
        context['contact_group'] = cg
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
        context['cg_perms'] = cg.get_contact_perms(request.user.id)
        context['active_submenu'] = 'members'
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['nav'].add_component(c.get_navcomponent())
    context['objtype'] = Contact
    context['contact'] = c
    context['rows'] = rows
    context['group_user_perms'] = ContactGroup.objects.get(pk=GROUP_USER).get_contact_perms(request.user.id)
    context['group_user_ngw_perms'] = ContactGroup.objects.get(pk=GROUP_USER_NGW).get_contact_perms(request.user.id)
    return render_to_response('contact_detail.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_vcard(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
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
    return HttpResponse(contact.vcard(), mimetype='text/x-vcard')



class ContactEditForm(forms.Form):
    def __init__(self, user_id, cid=None, contactgroup=None, *args, **kargs):
        # Note that user_id is the id of the contact making the query, not the
        # one beeing edited
        forms.Form.__init__(self, *args, **kargs)

        if perms.c_can_write_fields_cg(user_id, GROUP_EVERYBODY):
            self.fields['name'] = forms.CharField(label=_('Name'))
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
                self.fields[force_text(cf.id)] = f


@login_required()
@require_group(GROUP_USER_NGW)
def contact_edit(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
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
        title = _('Editing %s') % force_text(contact)
    else:
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

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
                        log.target = 'Contact ' + force_text(contact.id)
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
                log.target = 'Contact ' + force_text(contact.id)
                log.target_repr = 'Contact ' + contact.name
                log.save()

                log = Log(contact_id=request.user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'Contact ' + force_text(contact.id)
                log.target_repr = 'Contact ' + contact.name
                log.property = 'Name'
                log.property_repr = 'Name'
                log.change = 'new value is ' + contact.name
                log = Log(request.user.id)

                cig = ContactInGroup(contact_id=contact.id, group_id=gid)
                cig.flags = CIGFLAG_MEMBER
                cig.save()
                # TODO: Log new cig
                # TODO: Check can add members in super groups


            # 2/ In ContactFields
            for cf in form.cfields:
                if cf.type == FTYPE_PASSWORD:
                    continue
                #cfname = cf.name
                cfid = cf.id
                newvalue = data[force_text(cfid)]
                if newvalue != None:
                    newvalue = cf.formfield_value_to_db_value(newvalue)
                contact.set_fieldvalue(request, cf, newvalue)

            messages.add_message(request, messages.SUCCESS, _('Contact %s has been saved sucessfully!') % contact.name)

            if cg:
                base_url = cg.get_absolute_url() + 'members/' + force_text(contact.id) + '/'
            else:
                base_url = contact.get_class_absolute_url() + force_text(contact.id) + '/'

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
                    initialdata[force_text(cf.id)] = cf.db_value_to_formfield_value(cfv.value)
            form = ContactEditForm(request.user.id, cid=cid, initial=initialdata, contactgroup=cg)

        else:
            for cf in ContactField.objects.all():
                if cf.default:
                    if cf.type == FTYPE_DATE and cf.default == 'today':
                        initialdata[force_text(cf.id)] = date.today()
                    else:
                        initialdata[force_text(cf.id)] = cf.db_value_to_formfield_value(cf.default)

            if cg:
                initialdata['groups'] = [ cg.id ]
                form = ContactEditForm(request.user.id, cid=cid, initial=initialdata, contactgroup=cg)
            else:
                form = ContactEditForm(request.user.id, cid=cid)

    context = {}
    context['form'] = form
    context['title'] = title
    context['id'] = cid
    context['objtype'] = objtype
    if gid:
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    if cid:
        context['nav'].add_component(contact.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))
    if cid:
        context['o'] = contact

    return render_to_response('edit.html', context, RequestContext(request))


class ContactPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        if self.cleaned_data.get('new_password', '') != self.cleaned_data.get('confirm_password', ''):
            raise forms.ValidationError('The passwords must match!')
            
        try:
            crack.FascistCheck(self.cleaned_data.get('new_password', ''))
        except ValueError as err:
            raise forms.ValidationError(err.message)
            
        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    context = {}
    context['title'] = _('Change password')
    context['contact'] = contact
    if request.method == 'POST':
        form = ContactPasswordForm(request.POST)
        if form.is_valid():
            # record the value
            password = form.clean()['new_password']
            contact.set_password(password, request=request)
            messages.add_message(request, messages.SUCCESS, 'Password has been changed sucessfully!')
            if gid:
                cg = get_object_or_404(ContactGroup, pk=gid)
                return HttpResponseRedirect(cg.get_absolute_url() + 'members/' + force_text(cid) + '/')
            else:
                return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else: # GET
        form = ContactPasswordForm()
    context['form'] = form
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['nav'].add_component(contact.get_navcomponent()) \
                  .add_component(('password', _('password')))
    try:
        context['PASSWORD_LETTER'] = settings.PASSWORD_LETTER
        # So here the 'reset by letter' button will be enabled
    except AttributeError:
        pass # it's ok not to have a letter
    return render_to_response('password.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER) # not GROUP_USER_NGW
def hook_change_password(request):
    newpassword_plain = request.POST.get('password')
    if not newpassword_plain:
        return HttpResponse('Missing password POST parameter')
    #TODO: check strength
    request.user.set_password(newpassword_plain, request=request)
    return HttpResponse('OK')


@login_required()
@require_group(GROUP_USER_NGW)
def contact_pass_letter(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    context = {}
    context['title'] = _('Generate a new password and print a letter')
    context['contact'] = contact
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members')))
    else:
        context['nav'] = Navbar(Contact.get_class_navcomponent())
    context['nav'].add_component(contact.get_navcomponent()) \
                  .add_component(('password letter', _('password letter')))

    if request.method == 'POST':
        new_password = Contact.generate_password()

        # record the value
        contact.set_password(new_password, '2', request=request) # Generated and mailed
        messages.add_message(request, messages.SUCCESS, _('Password has been changed sucessfully!'))

        fields = {}
        for cf in contact.get_all_visible_fields(request.user.id):
            try:
                cfv = ContactFieldValue.objects.get(contact_id=cid, contact_field_id=cf.id)
            except ContactFieldValue.DoesNotExist:
                continue
            fields[cf.name] = force_text(cfv).replace('\r', '')
            #if cfv:
            #    rows.append((cf.name, mark_safe(cfv.as_html())))
        fields['name'] = contact.name
        fields['password'] = new_password

        filename = ngw_mailmerge(settings.PASSWORD_LETTER, fields, '/usr/lib/ngw/mailing/generated/')
        if not filename:
            return HttpResponse(_('File generation failed'))

        fullpath = os.path.join('/usr/lib/ngw/mailing/generated/', filename)
        response = CompatibleStreamingHttpResponse(open(fullpath, 'rb'), content_type='application/pdf')
        os.unlink(fullpath)
        return response
    return render_to_response('password_letter.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_delete(request, gid=None, cid=None):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not request.user.is_admin():
        raise PermissionDenied
    o = get_object_or_404(Contact, pk=cid)
    if gid:
        cg = get_object_or_404(ContactGroup, pk=gid)
        base_nav = cg.get_smart_navbar() \
                     .add_component(('members', _('members')))
        next_url = cg.get_absolute_url() + 'members/'
    else:
        next_url = reverse('ngw.core.views.contact_list')
        base_nav = None
    return generic_delete(request, o, next_url, base_nav=base_nav)


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_add(request, cid=None):
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_str = request.GET['filterstr']
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if filter_list_str:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    else:
        filter_list = []
    filter_list.append((_('No name'), filter_str))
    filter_list_str = ','.join(['"' + force_text(name) + '","' + force_text(filterstr) + '"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)
    messages.add_message(request, messages.SUCCESS, _('Filter has been added sucessfully!'))
    return HttpResponseRedirect(reverse('ngw.core.views.contact_filters_edit', args=(cid, len(filter_list)-1)))


@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_list(request, cid=None):
    cid = cid and int(cid) or None
    if cid != request.user.id and not perms.c_can_view_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    filters = []
    if filter_list_str:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
        filters = [ filtername for filtername, filter_str in filter_list ]
    context = {}
    context['title'] = _('User custom filters')
    context['contact'] = contact
    context['filters'] = filters
    context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('filters', _('custom filters')))
    return render_to_response('customfilters_user.html', context, RequestContext(request))


class FilterEditForm(forms.Form):
    name = forms.CharField(max_length=50)

@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_edit(request, cid=None, fid=None):
    cid = cid and int(cid) or None
    fid = int(fid)
    # Warning, here fid is the index in the filter list of a given user
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if not filter_list_str:
        return HttpResponse(_('ERROR: no custom filter for that user'))
    else:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    try:
        filtername, filterstr = filter_list[int(fid)]
    except (IndexError, ValueError):
        return HttpResponse(_("ERROR: Can't find filter #%s") % fid)

    if request.method == 'POST':
        form = FilterEditForm(request.POST)
        if form.is_valid():
            #print(repr(filter_list))
            #print(repr(filter_list_str))
            filter_list[int(fid)]=(form.clean()['name'], filterstr)
            #print(repr(filter_list))
            filter_list_str = ','.join(['"' + name + '","' + filterstr + '"' for name, filterstr in filter_list])
            #print(repr(filter_list_str))
            contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)
            messages.add_message(request, messages.SUCCESS, _('Filter has been renamed.'))
            return HttpResponseRedirect(reverse('ngw.core.views.contact_detail', args=(cid,)))
    else:
        form = FilterEditForm(initial={ 'name': filtername })
    context = {}
    context['title'] = _('User custom filter renaming')
    context['contact'] = contact
    context['form'] = form
    context['filtername'] = filtername
    try:
        filter_html = contactsearch.parse_filterstring(filterstr, request.user.id).to_html()
    except PermissionDenied:
        filter_html = _("[Permission was denied to explain that filter. You probably don't have access to the fields / group names it is using.]<br>Raw filter=%s") % filterstr
    except ContactField.DoesNotExist:
        filter_html = _("Unparsable filter: Field does not exist.")
    context['filter_html'] = filter_html
    context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('filters', _('custom filters'))) \
                     .add_component((force_text(fid), filtername))

    return render_to_response('customfilter_user.html', context, RequestContext(request))

@login_required()
@require_group(GROUP_USER_NGW)
def contact_filters_delete(request, cid=None, fid=None):
    cid = cid and int(cid) or None
    fid = int(fid)
    # Warning, here fid is the index in the filter list of a given user
    if cid != request.user.id and not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW):
        raise PermissionDenied
    contact = get_object_or_404(Contact, pk=cid)
    filter_list_str = contact.get_fieldvalue_by_id(FIELD_FILTERS)
    if not filter_list_str:
        return HttpResponse(_('ERROR: no custom filter for that user'))
    else:
        filter_list = contactsearch.parse_filter_list_str(filter_list_str)
    del filter_list[fid]
    filter_list_str = ','.join(['"' + name + '","' + filterstr + '"' for name, filterstr in filter_list])
    contact.set_fieldvalue(request, FIELD_FILTERS, filter_list_str)
    messages.add_message(request, messages.SUCCESS, _('Filter has been deleted.'))
    return HttpResponseRedirect(contact.get_absolute_url())



class DefaultGroupForm(forms.Form):
    def __init__(self, contact, *args, **kargs):
        super(DefaultGroupForm, self).__init__(*args, **kargs)
        available_groups = contact.get_allgroups_member().filter(date__isnull=True)
        choices = [ ('', _('Create new personnal group'))] + [ (cg.id, cg.name) for cg in available_groups
            if not cg.date and perms.c_can_see_cg(contact.id, cg.id) ]
        self.fields['default_group'] = forms.ChoiceField(
            label=_('Default group'), choices=choices, required=False)

@login_required()
@require_group(GROUP_USER_NGW)
def contact_default_group(request, cid=None):
    cid = cid and int(cid) or None
    contact = get_object_or_404(Contact, pk=cid)
    if not perms.c_can_write_fields_cg(request.user.id, GROUP_USER_NGW) and cid != request.user.id:
        raise PermissionDenied

    if request.method == 'POST':
        form = DefaultGroupForm(contact, request.POST)
        if form.is_valid():
            default_group = form.cleaned_data['default_group']
            if not default_group:
                cg = ContactGroup(
                    name = _('Group of %s') % contact.name,
                    description = _('This is the default group of %s') % contact.name,
                    )
                cg.save()
                cg.check_static_folder_created()

                cig = ContactInGroup(
                    contact_id=cid,
                    group_id=cg.id,
                    flags = CIGFLAG_MEMBER|ADMIN_CIGFLAGS,
                    )
                cig.save()
                messages.add_message(request, messages.SUCCESS, _('Personnal group created.') )
                default_group = str(cg.id)

            contact.set_fieldvalue(request, FIELD_DEFAULT_GROUP, default_group)
            messages.add_message(request, messages.SUCCESS, _('Default group has been changed sucessfully.') )
            return HttpResponseRedirect(contact.get_absolute_url())
    else:
        default_group = contact.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
        form = DefaultGroupForm(contact, initial={'default_group': default_group})
    context = {}
    context['title'] = _('User default group')
    context['contact'] = contact
    context['form'] = form
    context['nav'] = Navbar(Contact.get_class_navcomponent()) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('default_group', _('default group')))
    return render_to_response('contact_default_group.html', context, RequestContext(request))


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
#        contact.set_fieldvalue(request, FIELD_PASSWORD_STATUS, '2')
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
        #( _('Date'), None, 'html_date', 'date' ),
        ( _('Name'), None, 'name', 'name' ),
        ( _('Description'), None, 'description100', 'description' ),
        #( _('Contact fields'), None, print_fields, 'field_group' ),
        ( _('Super groups'), None, lambda cg: ', '.join(_trucate_list([sg.unicode_with_date() for sg in cg.get_direct_supergroups().extra(where=['perm_c_can_see_cg(%s, id)' % request.user.id])[:LIST_PREVIEW_LEN+1]])), None ),
        #( _('Super groups'), None, 'visible_direct_supergroups_5', None ),
        ( _('Sub groups'), None, lambda cg: ', '.join(_trucate_list([html.escape(sg.unicode_with_date()) for sg in cg.get_direct_subgroups().extra(where=['perm_c_can_see_cg(%s, id)' % request.user.id])][:LIST_PREVIEW_LEN+1])), None ),
        #( _('Budget\u00a0code'), None, 'budget_code', 'budget_code' ),
        #( _('Members'), None, lambda cg: str(len(cg.get_all_members())), None ),
        #( _('System\u00a0locked'), None, 'system', 'system' ),
    ]
    context = {}
    context['title'] = _('Select a contact group')
    context['query'] = q
    context['cols'] = cols
    context['objtype'] = ContactGroup
    context['nav'] = Navbar(ContactGroup.get_class_navcomponent())
    return query_print(request, 'list.html', context)


#from django.views.generic import ListView
#from django.utils.decorators import method_decorator
#class ContactGroupList(ListView):
#
#    @method_decorator(login_required)
#    @method_decorator(require_group(GROUP_USER_NGW))
#    def dispatch(self, *args, **kwargs):
#        return super(ContactGroupList, self).dispatch(*args, **kwargs)
#
#    template_name = 'list.html'
#    context_object_name = 'query'
#    page_kwarg = '_page'
#
#    def get_queryset(self):
#        return ContactGroup.objects.filter(date=None).extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % self.request.user.id])
#
#    def get_paginate_by(self, queryset):
#        try:
#            object_query_page_length = Config.objects.get(pk='query_page_length')
#            return int(object_query_page_length.text)
#        except (Config.DoesNotExist, ValueError):
#            return 200
#
#    def get_context_data(self, *args, **kwargs):
#        context = super(ContactGroupList, self).get_context_data(*args, **kwargs)
#        context['title'] = _('Select a contact group')
#        context['cols'] = [
#            ( _('Name'), None, 'name', 'name' ),
#        ]
#        context['objtype'] = ContactGroup
#        context['nav'] = Navbar(ContactGroup.get_class_navcomponent())
#        context['order'] = '' # FIXME
#        return context


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
        first_day_of_week = formats.get_format('FIRST_DAY_OF_WEEK')

        first_day_of_month = date(self.year, self.month, 1)
        first_day_of_month_isocal = first_day_of_month.isocalendar()
        #firstweeknumber = first_day_of_month_isocal[1]

        first_day_of_month_isoweekday = first_day_of_month_isocal[2] # 1=monday, 7=sunday
        first_week_date = first_day_of_month - timedelta(days=(first_day_of_month_isoweekday-first_day_of_week)%7)

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

    def first_day(self):
        return datetime(self.year, self.month, 1)


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
        ( _('Date'), None, 'html_date', 'date' ),
        ( _('Name'), None, 'name', 'name' ),
        ( _('Description'), None, 'description', 'description' ),
    ]

    month_events = {}
    for cg in q:
        if cg.date not in month_events:
            month_events[cg.date] = []
        month_events[cg.date].append(cg)

    context = {}
    context['title'] = _('Events')
    context['query'] = q
    context['cols'] = cols
    context['objtype'] = ContactGroup
    context['nav'] = Navbar().add_component(('events', _('events')))
    context['year_month'] = YearMonthCal(year, month, month_events)
    context['today'] = date.today()

    return query_print(request, 'list_events.html', context)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_details(request, gid):
    '''
    Redirect to members list, if allowed.
    Otherwise, try to find some authorized page.
    '''
    gid = gid and int(gid) or None
    cg = get_object_or_404(ContactGroup, pk=gid)
    if perms.c_can_see_members_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'members/')
    if perms.c_can_see_news_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'news/')
    if perms.c_can_see_files_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'files/')
    if perms.c_can_view_msgs_cg(request.user.id, gid):
        return HttpResponseRedirect(cg.get_absolute_url() + 'messages')
    raise PermissionDenied

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_members(request, gid, output_format=''):
    gid = gid and int(gid) or None
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
        request.user.set_fieldvalue(request, FIELD_COLUMNS, strfields)

    cg = get_object_or_404(ContactGroup, pk=gid)

    display = request.REQUEST.get('display', None)
    if display is None:
        display = cg.get_default_display()
    baseurl += '&display='+display

    context = {}
    context['fields_form'] = FieldSelectForm(request.user.id, initial={'selected_fields': fields})
    if output_format == 'csv':
        query_format = 'text'
    else:
        query_format = 'html'
    q, cols = contact_make_query_with_fields(request, fields, current_cg=cg, base_url=baseurl, format=query_format)

    wanted_flags = 0
    if 'm' in display:
        wanted_flags |= CIGFLAG_MEMBER
    if 'i' in display:
        wanted_flags |= CIGFLAG_INVITED
    if 'd' in display:
        wanted_flags |= CIGFLAG_DECLINED
    if 'a' in display:
        wanted_flags |= ADMIN_CIGFLAGS

    if not wanted_flags:
        # Show nothing
        q = q.filter('FALSE')
    elif not 'g' in display:
        # Not interested in inheritance:
        q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%s AND flags & %s <> 0)'
            % (cg.id, wanted_flags))
    else:
        # We want inherited people
        or_conditions = []
        # The local flags
        or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%s AND flags & %s <> 0)'
            % (cg.id, wanted_flags))
        # The inherited memberships/invited/declined
        or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)'
            % (cg.id, wanted_flags & (CIGFLAG_MEMBER|CIGFLAG_INVITED|CIGFLAG_DECLINED)))
        # The inherited admins
        or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(father_id) FROM group_manage_group WHERE subgroup_id=%s AND group_manage_group.flags & %s <> 0) AND contact_in_group.flags & 1 <> 0)'
            % (cg.id, wanted_flags & ADMIN_CIGFLAGS))

        q = q.filter('(' + ') OR ('.join(or_conditions) + ')')

    q = filter.apply_filter_to_query(q)

    if output_format == 'vcards':
        #FIXME: This works but is really inefficient (try it on a large group!)
        result = ''
        for contact in q:
            result += contact.vcard()
        return HttpResponse(result, mimetype='text/x-vcard')
    elif output_format == 'emails':
        emails = []
        noemails = []
        for contact in q:
            c_emails = contact.get_fieldvalues_by_type('EMAIL')
            if c_emails:
                emails.append((contact.id, contact, c_emails[0])) # only the first email
            else:
                noemails.append(contact)
        emails.sort(key=lambda x:remove_decoration(x[1].name.lower()))

        context['title'] = _('Emails for %s') % cg.name
        context['strfilter'] = strfilter
        context['filter'] = filter
        context['cg'] = cg
        context['cg_perms'] = cg.get_contact_perms(request.user.id)
        context['emails'] = emails
        context['noemails'] = noemails
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('members', _('members'))) \
                         .add_component(('emails', _('emails')))
        context['display_member'] = 'm' in display
        context['display_invited'] = 'i' in display
        context['display_declined'] = 'd' in display
        context['display_subgroups'] = 'g' in display
        context['display_admins'] = 'a' in display
        context['active_submenu'] = 'members'
        return render_to_response('emails.html', context, RequestContext(request))
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

    context['title'] = _('Contacts of group %s') % cg.unicode_with_date()
    context['baseurl'] = baseurl # contains filter, display, fields. NO output, no order
    context['display'] = display
    context['query'] = q
    context['cols'] = cols
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    ####
    context['objtype'] = ContactGroup
    context['filter'] = strfilter
    context['fields'] = strfields
    ####
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('members', _('members')))
    context['display_member'] = 'm' in display
    context['display_invited'] = 'i' in display
    context['display_declined'] = 'd' in display
    context['display_subgroups'] = 'g' in display
    context['display_admins'] = 'a' in display
    context['active_submenu'] = 'members'
    context['no_confirm_form_discard'] = True

    response = query_print(request, 'group_detail.html', context)
    #from django.db import connection
    #import pprint
    #pprint.PrettyPrinter(indent=4).pprint(connection.queries)
    return response


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_emails(request, gid):
    gid = gid and int(gid) or None
    if request.method == 'POST':
        if not perms.c_can_see_members_cg(request.user.id, gid):
            raise PermissionDenied
        message = request.POST.get('message', '')
        language = translation.get_language()
        for param in request.POST:
            if not param.startswith('contact_'):
                continue
            contact_id = param[len('contact_'):]
            contact = get_object_or_404(Contact, pk=contact_id)
            cig = ContactInGroup.objects.get(contact_id=contact_id, group_id=gid)
            contact_msg = ContactMsg(cig=cig)
            contact_msg.send_date = datetime.utcnow()
            contact_msg.text = message
            contact_msg.sync_info = json.dumps({'language': language})
            contact_msg.save()
            messages.add_message(request, messages.INFO, _('Messages stored.'))

    return contactgroup_members(request, gid, output_format='emails')


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_messages(request, gid):
    gid = gid and int(gid) or None
    if not perms.c_can_view_msgs_cg(request.user.id, gid):
        raise PermissionDenied

    cg = get_object_or_404(ContactGroup, pk=gid)
    messages = ContactMsg.objects.filter(cig__group_id=gid).order_by('-send_date')
    context = {}
    context['title'] = _('Messages for %s') % cg.unicode_with_date()
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('messages', _('messages')))
    context['contact_messages'] = messages
    context['active_submenu'] = 'messages'

    return render_to_response('group_messages.html', context, RequestContext(request))


class ContactGroupForm(forms.Form):
    name = forms.CharField(label=_('Name'),
        max_length=255)
    description = forms.CharField(label=_('Description'),
        required=False, widget=forms.Textarea)
    date = forms.DateField(label=_('Date'),
        required=False,
        help_text=_('Leave empty for permanent groups.'), widget=NgwCalendarWidget(attrs={'class':'vDateField'}))
    budget_code = forms.CharField(label=_('Budget code'),
        required=False, max_length=10)
    sticky = forms.BooleanField(label=_('Sticky'),
        required=False,
        help_text=_('If set, automatic membership because of subgroups becomes permanent. Use with caution.'))
    field_group = forms.BooleanField(label=_('Field group'),
        required=False,
        help_text=_('Does that group yield specific fields to its members?'))
    mailman_address = forms.CharField(label=_('Mailman address'),
        required=False, max_length=255,
        help_text=_('Mailing list address, if the group is linked to a mailing list.'))
    direct_supergroups = forms.MultipleChoiceField(label=_('Direct supergroups'),
        required=False,
        help_text=_('Members will automatically be granted membership in these groups.'), widget=FilterMultipleSelectWidget('groups', False))
    operator_groups = forms.MultipleChoiceField(label=_('Operator groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted administrative priviledges.'),
        widget=FilterMultipleSelectWidget('groups', False))
    viewer_groups = forms.MultipleChoiceField(label=_('Viewer groups'),
        required=False,
        help_text=_("Members of these groups will automatically be granted viewer priviledges: They can see everything but can't change things."),
        widget=FilterMultipleSelectWidget('groups', False))
    see_group_groups = forms.MultipleChoiceField(label=_('Existence seer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to know that current group exists.'),
        widget=FilterMultipleSelectWidget('groups', False))
    change_group_groups = forms.MultipleChoiceField(label=_('Editor groups'),
        required=False, 
        help_text=_('Members of these groups will automatically be granted priviledge to change/delete the current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    see_members_groups = forms.MultipleChoiceField(label=_('Members seer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to see the list of members.'),
        widget=FilterMultipleSelectWidget('groups', False))
    change_members_groups = forms.MultipleChoiceField(label=_('Members changing groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to change members of current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_fields_groups = forms.MultipleChoiceField(label=_('Fields viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to read the fields associated to current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_fields_groups = forms.MultipleChoiceField(label=_('Fields writer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted priviledge to write to fields associated to current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_news_groups = forms.MultipleChoiceField(label=_('News viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permisson to read news of current group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_news_groups = forms.MultipleChoiceField(label=_('News writer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to write news in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_files_groups = forms.MultipleChoiceField(label=_('File viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to view uploaded files in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_files_groups = forms.MultipleChoiceField(label=_('File uploader groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to upload files.'),
        widget=FilterMultipleSelectWidget('groups', False))
    view_msgs_groups = forms.MultipleChoiceField(label=_('Message viewer groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to view messages in that group.'),
        widget=FilterMultipleSelectWidget('groups', False))
    write_msgs_groups = forms.MultipleChoiceField(label=_('Message sender groups'),
        required=False,
        help_text=_('Members of these groups will automatically be granted permission to send messages.'),
        widget=FilterMultipleSelectWidget('groups', False))

    def __init__(self, for_user, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        visible_groups_choices = [ (g.id, g.unicode_with_date()) for g in ContactGroup.objects.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % for_user]).order_by('-date', 'name') ]
        self.fields['direct_supergroups'].choices = visible_groups_choices
        for flag in 'oveEcCfFnNuUxX':
            field_name = TRANS_CIGFLAG_CODE2TXT[flag] + '_groups'
            self.fields[field_name].choices = visible_groups_choices



@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_edit(request, id):
    id = id and int(id) or None
    objtype = ContactGroup
    if id:
        cg = get_object_or_404(ContactGroup, pk=id)
        if not perms.c_can_change_cg(request.user.id, id):
            raise PermissionDenied
        title = _('Editing %s') % cg.unicode_with_date()
    else:
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

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

            # Update the administrative groups
            for flag in 'oveEcCfFnNuUxX':
                field_name = TRANS_CIGFLAG_CODE2TXT[flag] + '_groups'
                intflag = TRANS_CIGFLAG_CODE2INT[flag]
                old_groups_ids = set(cg.get_visible_mananger_groups_ids(request.user.id, intflag))
                new_groups_ids = set([int(ogid) for ogid in data[field_name]])
                groups_added = new_groups_ids - old_groups_ids
                groups_removed = old_groups_ids - new_groups_ids
                print('flag', flag, 'groups_added=', groups_added)
                print('flag', flag, 'groups_removed=', groups_removed)
                if id and (groups_added or groups_removed) and not perms.c_operatorof_cg(request.user.id, id):
                    # Only operators can change permissions
                    raise PermissionDenied
                for ogid in groups_added:
                    try:
                        gmg = GroupManageGroup.objects.get(father_id=ogid, subgroup_id=cg.id)
                    except GroupManageGroup.DoesNotExist:
                        gmg = GroupManageGroup(father_id=ogid, subgroup_id=cg.id, flags=0)
                    gmg.flags |= intflag
                    gmg.save()
                for ogid in groups_removed:
                    gmg = GroupManageGroup.objects.get(father_id=ogid, subgroup_id=cg.id)
                    gmg.flags &= ~ intflag
                    if gmg.flags:
                        gmg.save()
                    else:
                        gmg.delete()

            messages.add_message(request, messages.SUCCESS, _('Group %s has been changed sucessfully!') % cg.unicode_with_date())

            cg.check_static_folder_created()
            Contact.check_login_created(request) # subgroups change

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
                'direct_supergroups': cg.get_visible_direct_supergroups_ids(request.user.id),
            }
            for flag in 'ovveEcCfFnNuUxX':
                field_name = TRANS_CIGFLAG_CODE2TXT[flag] + '_groups'
                intflag = TRANS_CIGFLAG_CODE2INT[flag]
                initialdata[field_name] = cg.get_visible_mananger_groups_ids(request.user.id, intflag)
        else: # add new one
            default_group_id = request.user.get_fieldvalue_by_id(FIELD_DEFAULT_GROUP)
            if not default_group_id:
                messages.add_message(request, messages.WARNING,
                    _('You must define a default group before you can create a group.'))
                return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
            default_group_id = int(default_group_id)
            if not request.user.is_member_of(default_group_id):
                messages.add_message(request, messages.WARNING,
                    _('You no longer are member of your default group. Please define a new default group.'))
                return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
            if not perms.c_can_see_cg(request.user.id, default_group_id):
                messages.add_message(request, messages.WARNING,
                    _('You no longer are authorized to see your default group. Please define a new default group.'))
                return HttpResponseRedirect(request.user.get_absolute_url()+'default_group')
            initialdata = {
                TRANS_CIGFLAG_CODE2TXT['o'] + '_groups': (default_group_id,)}
        form = ContactGroupForm(request.user.id, initial=initialdata)
    context = {}
    context['title'] = title
    context['id'] = id
    context['objtype'] = objtype
    context['form'] = form
    if id:
        context['o'] = cg
        context['nav'] = cg.get_smart_navbar() \
                         .add_component(('edit', _('edit')))
    else:
        context['nav'] = Navbar(ContactGroup.get_class_navcomponent()) \
                         .add_component(('add', _('add')))

    return render_to_response('edit.html', context, RequestContext(request))


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
    id = id and int(id) or None
    if not perms.c_can_change_cg(request.user.id, id):
        raise PermissionDenied
    o = get_object_or_404(ContactGroup, pk=id)
    next_url = reverse('ngw.core.views.contactgroup_list')
    if o.system:
        messages.add_message(request, messages.ERROR, _('Group %s is locked and CANNOT be deleted.') % o.name)
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
            for flag, propname in TRANS_CIGFLAG_CODE2TXT.items():
                field_name = 'membership_' + propname
                if request.REQUEST.get(field_name, False):
                    modes += '+' + flag
                    intflag = TRANS_CIGFLAG_CODE2INT[flag]
                    if intflag & ADMIN_CIGFLAGS and not perms.c_operatorof_cg(request.user.id, target_gid):
                        # Only operator can grant permissions
                        raise PermissionDenied
            if not modes:
                raise ValueError(_('You must select at least one mode'))

            contacts = []
            for param in request.POST:
                if not param.startswith('contact_'):
                    continue
                contact_id = param[len('contact_'):]
                #TODO: Check contact_id can be seen by user
                contact = get_object_or_404(Contact, pk=contact_id)
                contacts.append(contact)
            target_group.set_member_n(request, contacts, modes)

            return HttpResponseRedirect(target_group.get_absolute_url())
        else:
            messages.add_message(request, messages.ERROR, _('You must select a target group'))

    gid = request.REQUEST.get('gid', '')
    assert gid
    if not perms.c_can_see_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)

    strfilter = request.REQUEST.get('filter', '')
    filter = contactsearch.parse_filterstring(strfilter, request.user.id)

    q, cols = contact_make_query_with_fields(request, [], format='html') #, current_cg=cg)

    q = q.order_by('name')

    display = request.REQUEST.get('display', None)
    if display is None:
        display = cg.get_default_display()

    wanted_flags = 0
    if 'm' in display:
        wanted_flags |= CIGFLAG_MEMBER
    if 'i' in display:
        wanted_flags |= CIGFLAG_INVITED
    if 'd' in display:
        wanted_flags |= CIGFLAG_DECLINED
    if 'a' in display:
        wanted_flags |= ADMIN_CIGFLAGS

    if not wanted_flags:
        # Show nothing
        q = q.filter('FALSE')
    elif not 'g' in display:
        # Not interested in inheritance:
        q = q.filter('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%s AND flags & %s <> 0)'
            % (cg.id, wanted_flags))
    else:
        # We want inherited people
        or_conditions = []
        # The local flags
        or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id=%s AND flags & %s <> 0)'
            % (cg.id, wanted_flags))
        # The inherited memberships/invited/declined
        or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)'
            % (cg.id, wanted_flags & (CIGFLAG_MEMBER|CIGFLAG_INVITED|CIGFLAG_DECLINED)))
        # The inherited admins
        or_conditions.append('EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(father_id) FROM group_manage_group WHERE subgroup_id=%s AND group_manage_group.flags & %s <> 0) AND contact_in_group.flags & 1 <> 0)'
            % (cg.id, wanted_flags & ADMIN_CIGFLAGS))

        q = q.filter('(' + ') OR ('.join(or_conditions) + ')')

    q = filter.apply_filter_to_query(q)

    context = {}
    context['title'] = _('Add contacts to a group')
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('add_contacts_to', _('add contacts to')))
    context['groups'] = ContactGroup.objects.extra(where=['perm_c_can_change_members_cg(%s, contact_group.id)' % request.user.id]).order_by('-date', 'name')
    context['query'] = q
    context['active_submenu'] = 'members'
    return render_to_response('group_add_contacts_to.html', context, RequestContext(request))



#######################################################################
#
# Contact In Group
#
#######################################################################


class ContactInGroupForm(forms.Form):
    invited = forms.BooleanField(label=_('Invited'), required=False)
    declined = forms.BooleanField(label=_('Declined'), required=False)
    member = forms.BooleanField(label=_('Member'), required=False)
    operator = forms.BooleanField(label=_('Operator'), required=False,
        help_text=_('Full administrator of that group.'))
    viewer = forms.BooleanField(label=_('Viewer'), required=False,
        help_text=_('Can see everything, but read only access.'))
    see_group = forms.BooleanField(label=_('Can see group exists'), required=False)
    change_group = forms.BooleanField(label=_('Can change group'), required=False,
        help_text=_('Can change the group itself, delete it.'))
    see_members = forms.BooleanField(label=_('Can see members'), required=False)
    change_members = forms.BooleanField(label=_('Can change members'), required=False)
    view_fields = forms.BooleanField(label=_('Can view fields'), required=False,
        help_text=_('Can view the fields (like "address" or "email") associated with that group. Few groups support that.'))
    write_fields = forms.BooleanField(label=_('Can write fields'), required=False)
    view_news = forms.BooleanField(label=_('Can view news'), required=False,
        help_text=_('View the news of that group.'))
    write_news = forms.BooleanField(label=_('Can write news'), required=False)
    view_files = forms.BooleanField(label=_('Can view uploaded files'), required=False,
        help_text=_('View the uploaded files. Few group supports that.'))
    write_files = forms.BooleanField(label=_('Can upload files'), required=False)
    view_msgs = forms.BooleanField(label=_('Can view messages'), required=False)
    write_msgs = forms.BooleanField(label=_('Can write messages'), required=False)
    note = forms.CharField(required=False)

    def __init__(self, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)
        self.fields['invited'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.declined.checked=false;
                this.form.member.checked=false;
            }'''}
        self.fields['declined'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.invited.checked=false;
                this.form.member.checked=false;
            }'''}
        self.fields['member'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.invited.checked=false;
                this.form.declined.checked=false;
            }'''}
        self.fields['operator'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.viewer.checked=true;
                this.form.see_group.checked=true;
                this.form.change_group.checked=true;
                this.form.see_members.checked=true;
                this.form.change_members.checked=true;
                this.form.view_fields.checked=true;
                this.form.write_fields.checked=true;
                this.form.view_news.checked=true;
                this.form.write_news.checked=true;
                this.form.view_files.checked=true;
                this.form.write_files.checked=true;
                this.form.view_msgs.checked=true;
                this.form.write_msgs.checked=true;
            }'''}
        self.fields['viewer'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.see_members.checked=true;
                this.form.view_fields.checked=true;
                this.form.view_news.checked=true;
                this.form.view_files.checked=true;
                this.form.view_msgs.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['see_group'].widget.attrs = { 'onchange': '''
            if (!this.checked) {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.change_group.checked=false;
                this.form.see_members.checked=false;
                this.form.change_members.checked=false;
                this.form.view_fields.checked=false;
                this.form.write_fields.checked=false;
                this.form.view_news.checked=false;
                this.form.write_news.checked=false;
                this.form.view_files.checked=false;
                this.form.write_files.checked=false;
                this.form.view_msgs.checked=false;
                this.form.write_msgs.checked=false;
            }'''}
        self.fields['change_group'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['see_members'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.change_members.checked=false;
            }'''}
        self.fields['change_members'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.see_members.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_fields'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_fields.checked=false;
            }'''}
        self.fields['write_fields'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_fields.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_news'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_news.checked=false;
            }'''}
        self.fields['write_news'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_news.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_files'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_files.checked=false;
            }'''}
        self.fields['write_files'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_files.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}
        self.fields['view_msgs'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
            } else {
                this.form.operator.checked=false;
                this.form.viewer.checked=false;
                this.form.write_msgs.checked=false;
            }'''}
        self.fields['write_msgs'].widget.attrs = { 'onchange': '''
            if (this.checked) {
                this.form.see_group.checked=true;
                this.form.view_msgs.checked=true;
            } else {
                this.form.operator.checked=false;
            }'''}

    def clean(self):
        data = self.cleaned_data
        if   (data['invited'] and data['declined']) \
          or (data['declined'] and data['member']) \
          or (data['invited'] and data['member']) :
            raise forms.ValidationError('Invalid flags combinaison')
        return data


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit(request, gid, cid):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    try:
        cig = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        cig = ContactInGroup(contact_id=cid, group_id=gid, flags=0)
    cg = ContactGroup.objects.get(pk=gid)
    contact = Contact.objects.get(pk=cid)
    context = {}
    context['title'] = _('Contact %(contact)s in group %(group)s') % {
        'contact': force_text(contact),
        'group': cg.unicode_with_date() }
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['contact'] = contact
    context['objtype'] = ContactInGroup

    initial = {}
    for code, intval in TRANS_CIGFLAG_CODE2INT.items():
        if cig.flags & intval:
            field_name = TRANS_CIGFLAG_CODE2TXT[code]
            initial[field_name] = True
    initial['note'] = cig.note

    if request.method == 'POST':
        form = ContactInGroupForm(request.POST, initial=initial)
        if form.is_valid():
            data = form.cleaned_data
            newflags = 0
            for code, field_name in TRANS_CIGFLAG_CODE2TXT.items():
                if data[field_name]:
                    newflags |= TRANS_CIGFLAG_CODE2INT[code]
            if not newflags:
                return HttpResponseRedirect(reverse('ngw.core.views.contactingroup_delete', args=(force_text(cg.id), cid)))
            if (cig.flags ^ newflags) & ADMIN_CIGFLAGS \
                and not perms.c_operatorof_cg(request.user.id, cg.id):
                # If you change any permission flags of that group, you must be a group operator
                raise PermissionDenied
            cig.flags = newflags
            cig.note = data['note']
            # TODO: use set_member_1 for logs
            messages.add_message(request, messages.SUCCESS, 'Member %s of group %s has been changed sucessfully!' % (contact.name, cg.name))
            Contact.check_login_created(request)
            cig.save()
            hooks.membership_changed(request, contact, cg)
            return HttpResponseRedirect(cg.get_absolute_url())
    else:
        form = ContactInGroupForm(initial=initial)

    context['form'] = form

    inherited_info = ''

    automember_groups = ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%s)) AND contact_id=%s AND flags & %s <> 0 AND group_id=contact_group.id)' % (gid, cid, CIGFLAG_MEMBER)]).exclude(id=gid).order_by('-date', 'name')
    visible_automember_groups = automember_groups.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    invisible_automember_groups = automember_groups.extra(where=['not perm_c_can_see_cg(%s, contact_group.id)' % request.user.id])
    #print(automember_groups.query)
    if automember_groups:
        inherited_info += 'Automatically member because member of subgroup(s):' + '<br>'
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

    context['inherited_info'] = mark_safe(inherited_info)

    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('members', _('members'))) \
                     .add_component(contact.get_navcomponent()) \
                     .add_component(('membership', _('membership')))
    return render_to_response('contact_in_group.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_edit_inline(request, gid, cid):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    contact = get_object_or_404(Contact, pk=cid)
    if request.method == 'GET':
        # This occurs when there is a timeout (logout)
        # Fall back to detailed membership:
        return HttpResponseRedirect(cg.get_absolute_url()+'members/'+cid+'/membership')
    newmembership = request.POST['membership']
    if newmembership == 'invited':
        flags = '+i'
    elif newmembership == 'member':
        flags = '+m'
    elif newmembership == 'declined_invitation':
        flags = '+d'
    else:
        raise Exception('invalid membership '+request.POST['membership'])
    cg.set_member_1(request, contact, flags)
    hooks.membership_changed(request, contact, cg)
    return HttpResponseRedirect(request.POST['next_url'])


@login_required()
@require_group(GROUP_USER_NGW)
def contactingroup_delete(request, gid, cid):
    gid = gid and int(gid) or None
    cid = cid and int(cid) or None
    if not perms.c_can_change_members_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    try:
        o = ContactInGroup.objects.get(contact_id=cid, group_id=gid)
    except ContactInGroup.DoesNotExist:
        return HttpResponse(_('Error, that contact is not a direct member. Please check subgroups'))
    #messages.add_message(request, messages.SUCCESS, '%s has been removed for group %s.' % (cig.contact.name, cig.group.name))
    base_nav = cg.get_smart_navbar() \
                  .add_component(('members', _('members')))
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
    gid = gid and int(gid) or None
    if not perms.c_can_see_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    context = {}
    context['title'] = _('News for group %s') % cg.name
    context['news'] = ContactGroupNews.objects.filter(contact_group=gid)
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['objtype'] = ContactGroupNews
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('news', _('news')))
    context['active_submenu'] = 'news'
    return render_to_response('news.html', context, RequestContext(request))


class NewsEditForm(forms.Form):
    title = forms.CharField(max_length=50)
    text = forms.CharField(widget=forms.Textarea)


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_edit(request, gid, nid):
    gid = gid and int(gid) or None
    nid = nid and int(nid) or None
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    if nid:
        news = get_object_or_404(ContactGroupNews, pk=nid)
        if str(news.contact_group_id) != gid:
            return HttpResponse(_('ERROR: Group mismatch'))

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
            messages.add_message(request, messages.SUCCESS, _('News %s has been changed sucessfully!') % news)

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
    context = {}
    context['title'] = _('News edition')
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['form'] = form
    if nid:
        context['o'] = news
        context['id'] = nid
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('news', ('news')))
    if nid:
        context['nav'].add_component(news.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))

    return render_to_response('edit.html', context, RequestContext(request))

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_news_delete(request, gid, nid):
    gid = gid and int(gid) or None
    nid = nid and int(nid) or None
    if not perms.c_can_change_news_cg(request.user.id, gid):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=gid)
    o = get_object_or_404(ContactGroupNews, pk=nid)
    return generic_delete(request, o, cg.get_absolute_url() + 'news/')


class UploadFileForm(forms.Form):
    file_to_upload = forms.FileField(label=_('File to upload'))


@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_files(request, gid, path):
    gid = gid and int(gid) or None
    if not perms.c_can_see_files_cg(request.user.id, gid):
        raise PermissionDenied

    cg = get_object_or_404(ContactGroup, pk=gid)

    #return render_to_response('message.html', {
    #    'message': 'real path = %s' % cg.get_fullfilename('')
    #    }, RequestContext(request))

    if request.method == 'POST':
        if not perms.c_can_change_files_cg(request.user.id, gid):
            raise PermissionDenied
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            upfile = request.FILES['file_to_upload']
            # name has already been sanitized by UploadedFile._set_name
            fullfilename = cg.get_fullfilename(path + os.path.sep + upfile.name)
            destination = None
            try:
                destination = open(force_str(fullfilename), 'wb')
                for chunk in upfile.chunks():
                    destination.write(chunk)
                messages.add_message(request, messages.SUCCESS,
                    _('File %s has been uploaded sucessfully.') % upfile.name)
            except IOError as err:
                messages.add_message(request, messages.ERROR,
                    _('Could not upload file %(filename)s: %(error)s') % {
                        'filename': upfile.name,
                        'error': str(err)})
            finally:
                if destination:
                    destination.close()
            form = UploadFileForm() # ready for another file
    else:
        form = UploadFileForm()

    context = {}
    context['title'] = _('Files for group %s') % cg.name
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)
    context['objtype'] = ContactGroupNews
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('files', _('files')))
    base_fullname = cg.get_fullfilename()
    path_fullname = cg.get_fullfilename(path)
    if not path_fullname.startswith(base_fullname):
        raise PermissionDenied
    for part in path_fullname[len(base_fullname):].split('/'):
        if part:
            context['nav'] = context['nav'].add_component(part)
    context['active_submenu'] = 'files'
    context['path'] = path
    context['files'] = cg.get_filenames(path)
    context['form'] = form
    return render_to_response('group_files.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def media_group_file(request, gid, filename):
    gid = int(gid)
    if not perms.c_can_see_files_cg(request.user.id, gid):
        raise PermissionDenied

    cg = get_object_or_404(ContactGroup, pk=gid)

    fullfilename = cg.get_fullfilename(filename)
    if os.path.isdir(force_str(fullfilename)):
        return HttpResponseRedirect('/contactgroups/'+force_text(cg.id)+'/files/'+filename)
    return static.serve(request, filename, cg.static_folder(), show_indexes=False)


class MailmanSyncForm(forms.Form):
    mail = forms.CharField(widget=forms.Textarea)

@login_required()
@require_group(GROUP_USER_NGW)
def contactgroup_mailman(request, id):
    id = id and int(id) or None
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
    if not perms.c_can_see_members_cg(request.user.id, id):
        raise PermissionDenied
    cg = get_object_or_404(ContactGroup, pk=id)

    context = {}
    context['title'] = _('Mailman synchronisation')
    context['nav'] = cg.get_smart_navbar() \
                     .add_component(('mailman', _('mailman')))
    context['cg'] = cg
    context['cg_perms'] = cg.get_contact_perms(request.user.id)

    if request.method == 'POST':
        form = MailmanSyncForm(request.POST)
        if form.is_valid():
            data = form.clean()
            context['sync_res'] = synchronise_group(cg, data['mail'])
            return render_to_response('group_mailman_result.html', context, RequestContext(request))
    else:
        form = MailmanSyncForm(initial={'mail': initial_value})

    context['form'] = form
    return render_to_response('group_mailman.html', context, RequestContext(request))


#######################################################################
#
# Contact Fields
#
#######################################################################

@login_required()
@require_group(GROUP_USER_NGW)
def field_list(request):
    fields = ContactField.objects.order_by('sort_weight').extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % request.user.id ])
    context = {}
    context['query'] = fields
    context['cols'] = [
        ( _('Name'), None, 'name', 'name'),
        ( _('Type'), None, 'type_as_html', 'type'),
        ( _('Only for'), None, 'contact_group', 'contact_group__name'),
        ( _('System locked'), None, 'system', 'system'),
        #( _('Move'), None, lambda cf: '<a href='+str(cf.id)+'/moveup>Up</a> <a href='+str(cf.id)+'/movedown>Down</a>', None),
    ]
    context['title'] = _('Select an optionnal field')
    context['objtype'] = ContactField
    context['nav'] = Navbar(ContactField.get_class_navcomponent())
    return query_print(request, 'list.html', context, forcesort='sort_weight')


@login_required()
@require_group(GROUP_USER_NGW)
def field_move_up(request, id):
    id = id and int(id) or None
    if not request.user.is_admin():
        raise PermissionDenied
    cf = get_object_or_404(ContactField, pk=id)
    cf.sort_weight -= 15
    cf.save()
    ContactField.renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))


@login_required()
@require_group(GROUP_USER_NGW)
def field_move_down(request, id):
    id = id and int(id) or None
    if not request.user.is_admin():
        raise PermissionDenied
    cf = get_object_or_404(ContactField, pk=id)
    cf.sort_weight += 15
    cf.save()
    ContactField.renumber()
    return HttpResponseRedirect(reverse('ngw.core.views.field_list'))


class FieldEditForm(forms.Form):
    name = forms.CharField(label=_('Name'))
    hint = forms.CharField(label=_('Hint'),
        required=False, widget=forms.Textarea)
    contact_group = forms.CharField(label=_('Only for'), required=False, widget=forms.Select)
    type = forms.CharField(label=_('Type'),
        widget=forms.Select)
    choicegroup = forms.CharField(label=_('Choice group'), required=False, widget=forms.Select)
    default_value = forms.CharField(label=_('Default value'), required=False)
    move_after = forms.IntegerField(label=_('Move after'), widget=forms.Select())

    def __init__(self, cf, *args, **kargs):
        forms.Form.__init__(self, *args, **kargs)

        contacttypes = ContactGroup.objects.filter(field_group=True)
        self.fields['contact_group'].widget.choices = [ (g.id, g.name) for g in contacttypes ]

        self.fields['type'].widget.choices = [ (cls.db_type_id, cls.human_type_id)
            for cls in itervalues(ContactField.types_classes) ] # TODO: Sort
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
            if 'disabled' in self.fields['choicegroup'].widget.attrs:
                del self.fields['choicegroup'].widget.attrs['disabled']
            self.fields['choicegroup'].required = True
        else:
            self.fields['choicegroup'].widget.attrs['disabled'] = 1
            self.fields['choicegroup'].required = False

        self.fields['default_value'].widget.attrs['disabled'] = 1

        self.fields['move_after'].widget.choices = [ (5, _('Name')) ] + [ (field.sort_weight + 5, field.name) for field in ContactField.objects.order_by('sort_weight') ]

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
            if cls_contact_field.has_choice and not self.cleaned_data.get('choicegroup'):
                raise forms.ValidationError('You must select a choice group for that type.')
        return self.cleaned_data


@login_required()
@require_group(GROUP_USER_NGW)
def field_edit(request, id):
    if not request.user.is_admin():
        raise PermissionDenied
    id = id and int(id) or None
    objtype = ContactField
    initial = {}
    if id:
        cf = get_object_or_404(ContactField, pk=id)
        title = _('Editing %s') % smart_text(cf)
        initial['name'] = cf.name
        initial['hint'] = cf.hint
        initial['contact_group'] = cf.contact_group_id
        initial['type'] = cf.type
        initial['choicegroup'] = cf.choice_group_id
        initial['default_value'] = cf.default
        initial['move_after'] = cf.sort_weight-5
    else:
        cf = None
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

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
                if not cf.system and (cf.type != data['type'] or force_text(cf.choice_group_id) != data['choicegroup']):
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
                            context = {}
                            context['title'] = _('Type incompatible with existing data')
                            context['id'] = id
                            context['cf'] = cf
                            context['deletion_details'] = deletion_details
                            for k in ( 'name', 'hint', 'contact_group', 'type', 'choicegroup', 'move_after'):
                                context[k] = data[k]
                            context['nav'] = Navbar(cf.get_class_navcomponent(), cf.get_navcomponent(), ('edit', _('delete imcompatible data')))
                            return render_to_response('type_change.html', context, RequestContext(request))

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
            messages.add_message(request, messages.SUCCESS, _('Field %s has been changed sucessfully.') % cf.name)
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


    context = {}
    context['form'] = form
    context['title'] = title
    context['id'] = id
    context['objtype'] = objtype
    if id:
        context['o'] = cf
    context['nav'] = Navbar(ContactField.get_class_navcomponent())
    if id:
        context['nav'].add_component(cf.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))
    return render_to_response('edit.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def field_delete(request, id):
    if not request.user.is_admin():
        raise PermissionDenied
    o = get_object_or_404(ContactField, pk=id)
    id = id and int(id) or None
    next_url = reverse('ngw.core.views.field_list')
    if o.system:
        messages.add_message(request, messages.ERROR, _('Field %s is locked and CANNOT be deleted.') % o.name)
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
        raise PermissionDenied
    context = {}
    context['query'] = ChoiceGroup.objects.all()
    context['cols'] = [
        ( _('Name'), None, 'name', 'name'),
        ( _('Choices'), None, lambda cg: ', '.join([html.escape(c[1]) for c in cg.ordered_choices]), None),
    ]
    context['title'] = _('Select a choice group')
    context['objtype'] = ChoiceGroup
    context['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())
    return query_print(request, 'list.html', context)


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
        for i in range(len(possibles_values)//2):
            v, k = possibles_values[2*i], possibles_values[2*i+1]
            if not v:
                continue # ignore lines without values
            if not k:
                continue # empty keys are ok
            if k in keys:
                raise forms.ValidationError(_('You cannot have two keys with the same value. Leave empty for automatic generation.'))
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

        possibles_values = self.cleaned_data['possible_values']
        choices = {}

        # first ignore lines with empty keys, and update auto_key
        auto_key = 0
        for i in range(len(possibles_values)//2):
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
        for i in range(len(possibles_values)//2):
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
        for k, v in iteritems(choices):
            #print('ADDING', k)
            cg.choices.create(key=k, value=v)

        messages.add_message(request, messages.SUCCESS, _('Choice %s has been saved sucessfully.') % cg.name)
        return cg


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_edit(request, id=None):
    if not request.user.is_admin():
        raise PermissionDenied
    objtype = ChoiceGroup
    id = id and int(id) or None
    if id:
        cg = get_object_or_404(ChoiceGroup, pk=id)
        title = _('Editing %s') % smart_text(cg)
    else:
        cg = None
        title = _('Adding a new %s') % objtype.get_class_verbose_name()

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

    context = {}
    context['title'] = title
    context['id'] = id
    context['objtype'] = objtype
    context['form'] = form
    if id:
        context['o'] = cg
    context['nav'] = Navbar(ChoiceGroup.get_class_navcomponent())
    if id:
        context['nav'].add_component(cg.get_navcomponent()) \
                      .add_component(('edit', _('edit')))
    else:
        context['nav'].add_component(('add', _('add')))
    return render_to_response('edit.html', context, RequestContext(request))


@login_required()
@require_group(GROUP_USER_NGW)
def choicegroup_delete(request, id):
    if not request.user.is_admin():
        raise PermissionDenied
    id = id and int(id) or None
    o = get_object_or_404(ChoiceGroup, pk=id)
    return generic_delete(request, o, reverse('ngw.core.views.choicegroup_list'))
