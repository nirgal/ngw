# -*- encoding: utf-8 -*-
#
# Also note: You'll have to insert the output of 'manage.py sqlall core'
# into your database.

from __future__ import print_function, unicode_literals
import os
from functools import wraps
from datetime import datetime, timedelta
import subprocess
from django.db import models, connection
from django import forms
from django.contrib.auth.hashers import make_password
from django.http import Http404
from django.utils import html
import decoratedstr # Nirgal external package
from ngw.core.nav import Navbar
from ngw.core.templatetags.ngwtags import ngw_date_format, ngw_datetime_format #FIXME
#from ngw.core.filters import (NameFilterStartsWith, FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLE, FieldFilterGE, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull, FieldFilterIEQ, FieldFilterINE, FieldFilterILT, FieldFilterIGT, FieldFilterILE, FieldFilterIGE, FieldFilterAGE_GE, FieldFilterVALID_GT, FieldFilterFUTURE, FieldFilterChoiceEQ, FieldFilterChoiceNEQ, FieldFilterMultiChoiceHAS, FieldFilterMultiChoiceHASNOT, GroupFilterIsMember, GroupFilterIsNotMember, GroupFilterIsInvited, GroupFilterIsNotInvited, GroupFilterDeclinedInvitation, GroupFilterNotDeclinedInvitation, AllEventsNotReactedSince, AllEventsReactionYearRatioLess, AllEventsReactionYearRatioMore)
from ngw.extensions import hooks

GROUP_EVERYBODY = 1 # Group "Contact"
GROUP_USER = 2      # With login & password (does NOT mean it can access NGW, see bellow)
GROUP_ADMIN = 8
GROUP_OBSERVERS = 9
GROUP_USER_NGW = 52
GROUP_USER_PHPBB = 53

FIELD_LOGIN = 1             # GROUP_USER
FIELD_PASSWORD = 2          # GROUP_USER
FIELD_LASTCONNECTION = 3    # GROUP_USER
FIELD_COLUMNS = 4           # GROUP_USER_NGW
FIELD_FILTERS = 5           # GROUP_USER_NGW

FIELD_BIRTHDAY = 6
FIELD_EMAIL = 7
FIELD_STREET = 9
FIELD_POSTCODE = 11
FIELD_CITY = 14
FIELD_COUNTRY = 48
FIELD_PHPBB_USERID = 73
FIELD_PASSWORD_PLAIN = 74
FIELD_PASSWORD_STATUS = 75
FIELD_DEFAULT_GROUP = 83    # GROUP_USER_NGW

CIGFLAG_MEMBER         =     1 # 'm'ember
CIGFLAG_INVITED        =     2 # 'i'nvited
CIGFLAG_DECLINED       =     4 # 'd'eclined invitation
CIGFLAG_OPERATOR       =     8 # 'o'pertor
CIGFLAG_VIEWER         =    16 # 'v'iewer
CIGFLAG_SEE_CG         =    32 # 'e'xistance
CIGFLAG_CHANGE_CG      =    64 # 'E'
CIGFLAG_SEE_MEMBERS    =   128 # 'c'ontent
CIGFLAG_CHANGE_MEMBERS =   256 # 'C'
CIGFLAG_VIEW_FIELDS    =   512 # 'f'ields
CIGFLAG_WRITE_FIELDS   =  1024 # 'F'
CIGFLAG_VIEW_NEWS      =  2048 # 'n'ews
CIGFLAG_WRITE_NEWS     =  4096 # 'N'
CIGFLAG_VIEW_FILES     =  8192 # 'u'ploaded
CIGFLAG_WRITE_FILES    = 16384 # 'U'

# That information contains:
# int value (see above)
# character letter value, kinda human friendly
# human friendly text, sometimes used in forms field names
# dependency: 'u':'e' means viewing files implies viewing group existence
# conflicts: 'F':'f' means can't write to fields unless can read them too
__cig_flag_info__ = (
    (CIGFLAG_MEMBER, 'm', 'member', '', 'id'),
    (CIGFLAG_INVITED, 'i', 'invited', '', 'md'),
    (CIGFLAG_DECLINED, 'd', 'declined', '', 'mi'),
    (CIGFLAG_OPERATOR, 'o', 'operator', 'veEcCfFnNuU', ''),
    (CIGFLAG_VIEWER, 'v', 'viewer', 'ecfnu', ''),
    (CIGFLAG_SEE_CG, 'e', 'see_group', '', ''),
    (CIGFLAG_CHANGE_CG, 'E', 'change_group', 'e', ''),
    (CIGFLAG_SEE_MEMBERS, 'c', 'see_members', 'e', ''),
    (CIGFLAG_CHANGE_MEMBERS, 'C', 'change_members', 'ec', ''),
    (CIGFLAG_VIEW_FIELDS, 'f', 'view_fields', 'e', ''),
    (CIGFLAG_WRITE_FIELDS, 'F', 'write_fields', 'ef', ''),
    (CIGFLAG_VIEW_NEWS, 'n', 'view_news', 'e', ''),
    (CIGFLAG_WRITE_NEWS, 'N', 'write_news', 'en', ''),
    (CIGFLAG_VIEW_FILES, 'u', 'view_files', 'e', ''),
    (CIGFLAG_WRITE_FILES, 'U', 'write_files', 'eu', ''),
)

ADMIN_CIGFLAGS =  (CIGFLAG_OPERATOR | CIGFLAG_VIEWER
                 | CIGFLAG_SEE_CG | CIGFLAG_CHANGE_CG
                 | CIGFLAG_SEE_MEMBERS | CIGFLAG_CHANGE_MEMBERS
                 | CIGFLAG_VIEW_FIELDS | CIGFLAG_WRITE_FIELDS
                 | CIGFLAG_VIEW_NEWS | CIGFLAG_WRITE_NEWS
                 | CIGFLAG_VIEW_FILES | CIGFLAG_WRITE_FILES)

# dicts for quick translation 1 letter txt -> int, and 1 letter txt -> txt
TRANS_CIGFLAG_CODE2INT = {}
TRANS_CIGFLAG_CODE2TXT = {}

# dict for dependencies
# TODO: This is new, all was hardcoded and should use this:
CIGFLAGS_CODEDEPENDS = {}

# dict for cascade deletion of flags
# TODO: This is new, all was hardcoded and should use this:
CIGFLAGS_CODEONDELETE = {}

def _initialise_cigflags_constants():
    if TRANS_CIGFLAG_CODE2INT:
        return # already initialized
    for intval, code, txt, requires, conflicts in __cig_flag_info__:
        TRANS_CIGFLAG_CODE2INT[code] = intval
        TRANS_CIGFLAG_CODE2TXT[code] = txt

    for intval, code, txt, requires, conflicts in __cig_flag_info__:
        CIGFLAGS_CODEDEPENDS[code] = requires
        CIGFLAGS_CODEONDELETE[code] = conflicts

    for cflag, depends in CIGFLAGS_CODEDEPENDS.items():
        for depend in depends:
            if cflag not in CIGFLAGS_CODEONDELETE[depend]:
                CIGFLAGS_CODEONDELETE[depend] += cflag

    #for intval, code, txt, requires, conflicts in __cig_flag_info__:
    #    print(code, '+', CIGFLAGS_CODEDEPENDS[code],
    #                '-', CIGFLAGS_CODEONDELETE[code])

# This is run on module loading:
_initialise_cigflags_constants()

# Ends with a /
GROUP_STATIC_DIR = "/usr/lib/ngw/static/static/g/"

class NgwModel(models.Model):
    do_not_call_in_templates = True # prevent django from trying to instanciate objtype

    @classmethod
    def get_class_verbose_name(cls):
        return unicode(cls._meta.verbose_name)

    @classmethod
    def get_class_verbose_name_plural(cls):
        return unicode(cls._meta.verbose_name_plural)

    @classmethod
    def get_class_urlfragment(cls):
        return unicode(cls.__name__.lower(), 'utf8') + 's'

    def get_urlfragment(self):
        return unicode(self.id)

    @classmethod
    def get_class_navcomponent(cls):
        return cls.get_class_urlfragment(), cls.get_class_verbose_name_plural()

    def get_navcomponent(self):
        return self.get_urlfragment(), unicode(self)

    @classmethod
    def get_class_absolute_url(cls):
        return '/' + cls.get_class_urlfragment() + '/'

    def get_absolute_url(self):
        return self.get_class_absolute_url() + unicode(self.id) + '/'

    class Meta:
        abstract = True


# Types of change
LOG_ACTION_ADD      = 1
LOG_ACTION_CHANGE   = 2
LOG_ACTION_DEL      = 3

class Log(NgwModel):
    id = models.AutoField(primary_key=True)
    dt = models.DateTimeField(auto_now=True)
    contact = models.ForeignKey('Contact')
    action = models.IntegerField()
    target = models.TextField()
    target_repr = models.TextField()
    property = models.TextField(blank=True, null=True)
    property_repr = models.TextField(blank=True, null=True)
    change = models.TextField(blank=True, null=True)
    class Meta:
        db_table = 'log'

    #def __unicode__(self):
    #    return '%(date)s: %(contactname)s %(type_and_data)s' % {
    #            'date': self.dt.isoformat(),
    #            'contactname': self.contact.name,
    #            'action_and_data': self.action_and_data(),
    #            }
    #
    #def action_and_data(self):
    #    if self.action==LOG_ACTION_CHANGE:
    #        return '%(property)s %(target)s: %(change)s' % {
    #            'target': self.target_repr,
    #            'property': self.property_repr,
    #            'change': self.change,
    #            }

    def small_date(self):
        return self.dt.strftime('%Y-%m-%d %H:%M:%S')

    def action_txt(self):
        return { LOG_ACTION_ADD: 'Add',
                 LOG_ACTION_CHANGE: 'Update',
                 LOG_ACTION_DEL: 'Delete'}[self.action]


class Config(NgwModel):
    id = models.CharField(max_length=32, primary_key=True)
    text = models.TextField(blank=True)
    def __unicode__(self):
        return self.id
    class Meta:
        db_table = 'config'


class Choice(NgwModel):
    oid = models.AutoField(primary_key=True)
    choice_group = models.ForeignKey('ChoiceGroup', related_name='choices')
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    def __unicode__(self):
        return self.value
    class Meta:
        db_table = 'choice'

class ChoiceGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=True)
    sort_by_key = models.BooleanField()
    class Meta:
        db_table = 'choice_group'
        verbose_name = 'choices list'

    def __unicode__(self):
        return self.name

    @property
    def ordered_choices(self):
        "Utility property to get choices tuples in correct order"
        q = Choice.objects
        q = q.filter(choice_group_id=self.id)
        if self.sort_by_key:
            q = q.order_by('key')
        else:
            q = q.order_by('value')
        return [(c.key, c.value) for c in q]

    get_link_name = NgwModel.get_absolute_url


class Contact(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    class Meta:
        db_table = 'contact'

    def __repr__(self):
        return b'Contact <' + self.name.encode('utf-8') + b'>'

    def __unicode__(self):
        return self.name

    def is_authenticated(self):
        return True

    #get_link_name=NgwModel.get_absolute_url
    def name_with_relative_link(self):
        return '<a href="%(id)d/">%(name)s</a>' % { 'id': self.id, 'name': html.escape(self.name) }


    def get_directgroups_member(self):
        "returns the list of groups that contact is a direct member of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND flags & %s <> 0)' % (self.id, CIGFLAG_MEMBER)]).order_by('-date', 'name')

    def get_allgroups_member(self):
        "returns the list of groups that contact is a member of."
        return ContactGroup.objects.extra(where=['id IN (SELECT self_and_supergroups(group_id) FROM contact_in_group WHERE contact_id=%s AND flags & %s <> 0)' % (self.id, CIGFLAG_MEMBER)])

    def get_directgroups_invited(self):
        "returns the list of groups that contact has been invited to, directly without group inheritance"
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND flags & %s <> 0)' % (self.id, CIGFLAG_INVITED)]).order_by('-date', 'name')

#    def get_allgroups_invited(self):
#        "returns the list of groups that contact has been invited to."
#        q = Query(ContactInGroup).filter(ContactInGroup.contact_id == self.id ).filter(ContactInGroup.invited==True)
#        groups = []
#        for cig in q:
#            g = Query(ContactGroup).get(cig.group_id)
#            if g not in groups:
#                groups.append(g)
#            g._append_supergroups(groups)
#        return groups

    def get_directgroups_declinedinvitation(self):
        "returns the list of groups that contact has been invited to and he declined the invitation."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND flags & %s <> 0)' % (self.id, CIGFLAG_DECLINED)]).order_by('-date', 'name')

    def get_directgroups_operator(self):
        "returns the list of groups that contact is an operator of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND flags & %s <> 0)' % (self.id, CIGFLAG_OPERATOR)]).order_by('-date', 'name')

    def get_directgroups_viewer(self):
        "returns the list of groups that contact is a viewer of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND flags & %s <> 0)' % (self.id, CIGFLAG_VIEWER)]).order_by('-date', 'name')

    def get_allgroups_withfields(self):
        "returns the list of groups with field_group ON that contact is member of."
        return self.get_allgroups_member().filter(field_group=True)

    def _get_allfields(self):
        '''
        Returns a query with all the fields that self has gained, that is you
        will not get fields that belong to a group is not a member of.
        You should probaly use get_all_visible_fields or get_all_writable_fields
        '''
        contactgroupids = [ g.id for g in self.get_allgroups_withfields() ]
        #print("contactgroupids=", contactgroupids)
        return ContactField.objects.filter(contact_group_id__in = contactgroupids).order_by('sort_weight')

    def get_all_visible_fields(self, user_id):
        '''
        Like _get_allfields() but check user_id has read permission
        '''
        fields = self._get_allfields()
        if user_id == self.id:
            return fields
        else:
            return fields.extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % user_id])

    def get_all_writable_fields(self, user_id):
        '''
        Like _get_allfields() but check user_id has write permission
        '''
        fields = self._get_allfields()
        if user_id == self.id:
            return fields
        else:
            return fields.extra(where=['perm_c_can_write_fields_cg(%s, contact_field.contact_group_id)' % user_id])

    def get_fieldvalues_by_type(self, type_):
        if isinstance(type_, ContactField):
            type_ = type_.db_type_id
        assert isinstance(type_, unicode)
        fields = ContactField.objects.filter(type=type_).order_by('sort_weight')
        # TODO: check authority
        result = []
        for field in fields:
            v = self.get_fieldvalue_by_id(field.id)
            if v:
                result.append(v)
        return result

    def get_fieldvalue_by_id(self, field_id):
        try:
            cfv = ContactFieldValue.objects.get(contact_id=self.id, contact_field_id=field_id)
        except ContactFieldValue.DoesNotExist:
            return ''
        return unicode(cfv)

    def set_fieldvalue(self, user, field, newvalue):
        """
        Sets a field value and registers the change in the log table.
        Field can be either a field id or a ContactField object.
        New value must be text.
        """
        if type(field) == int:
            field_id = field
            field = ContactField.objects.get(pk=field)
        else:
            assert isinstance(field, ContactField)
            field_id = field.id
        try:
            cfv = ContactFieldValue.objects.get(contact_id=self.id, contact_field_id=field_id)
            if newvalue:
                if cfv.value != newvalue:
                    log = Log(contact_id=user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = 'Contact ' + unicode(self.id)
                    log.target_repr = 'Contact ' + self.name
                    log.property = unicode(field_id)
                    log.property_repr = field.name
                    log.change = 'change from ' + unicode(cfv)
                    cfv.value = newvalue
                    log.change += ' to ' + unicode(cfv)
                    cfv.save()
                    log.save()
                    hooks.contact_field_changed(user, field_id, self)
            else:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_DEL
                log.target = 'Contact ' + unicode(self.id)
                log.target_repr = 'Contact ' + self.name
                log.property = unicode(field_id)
                log.property_repr = field.name
                log.change = 'old value was ' + unicode(cfv)
                cfv.delete()
                log.save()
                hooks.contact_field_changed(user, field_id, self)
        except ContactFieldValue.DoesNotExist:
            if newvalue:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'Contact ' + unicode(self.id)
                log.target_repr = 'Contact ' + self.name
                log.property = unicode(field_id)
                log.property_repr = field.name
                cfv = ContactFieldValue()
                cfv.contact = self
                cfv.contact_field = field
                cfv.value = newvalue
                cfv.save()
                log.change = 'new value is ' + unicode(cfv)
                log.save()
                hooks.contact_field_changed(user, field_id, self)


    def get_login(self):
        # See templates/contact_detail.htm
        return self.get_fieldvalue_by_id(FIELD_LOGIN)

    def vcard(self):
        # http://www.ietf.org/rfc/rfc2426.txt
        vcf = ''
        def line(key, value):
            value = value.replace('\\', '\\\\')
            value = value.replace('\r', '')
            value = value.replace('\n', '\\n')
            return key + ':' + value + '\r\n'
        vcf += line('BEGIN', 'VCARD')
        vcf += line('VERSION', '3.0')
        vcf += line('FN', self.name)
        vcf += line('N', self.name)


        street = self.get_fieldvalue_by_id(FIELD_STREET)
        postal_code = self.get_fieldvalue_by_id(FIELD_POSTCODE)
        city = self.get_fieldvalue_by_id(FIELD_CITY)
        country = self.get_fieldvalue_by_id(FIELD_COUNTRY)
        vcf += line('ADR', ';;' + street + ';' + city + ';;' + postal_code + ';' + country)

        for phone in self.get_fieldvalues_by_type('PHONE'):
            vcf += line('TEL', phone)

        for email in self.get_fieldvalues_by_type('EMAIL'):
            vcf += line('EMAIL', email)

        bday = self.get_fieldvalue_by_id(FIELD_BIRTHDAY)
        if bday:
            vcf += line('BDAY', unicode(bday))

        vcf += line('END', 'VCARD')
        return vcf

    def get_addr_semicol(self):
        "Returns address in a form compatible with googlemap query"
        return self.get_fieldvalue_by_id(FIELD_STREET) + ';' + self.get_fieldvalue_by_id(FIELD_POSTCODE) + ';' + self.get_fieldvalue_by_id(FIELD_CITY) + ';' + self.get_fieldvalue_by_id(FIELD_COUNTRY)

    # TODO: migrate to new django.contrib.messages framework
    def push_message(self, message):
        ContactSysMsg(contact_id=self.id, message=message).save()

    def generate_login(self):
        words = self.name.split(" ")
        login = [w[0].lower() for w in words[:-1] ] + [ words[-1].lower() ]
        login = "".join(login)
        login = decoratedstr.remove_decoration(login)
        def get_logincfv_by_login(ref_uid, login):
            """
            Returns login cfv where loginname=login and not uid!=ref_uid
            This can be evaluated as true is login is already in use by another user
            """
            return ContactFieldValue.objects.filter(contact_field_id=FIELD_LOGIN) \
                                   .filter(value=login) \
                                   .exclude(contact_id=ref_uid)
        if not get_logincfv_by_login(self.id, login):
            return login
        i = 1
        while True:
            altlogin = login + unicode(i)
            if not get_logincfv_by_login(self.id, altlogin):
                return altlogin
            i += 1

    @staticmethod
    def generate_password():
        random_password = subprocess.Popen(['pwgen', '-N', '1'], stdout=subprocess.PIPE).communicate()[0]
        random_password = random_password[:-1] # remove extra "\n"
        return random_password


    def set_password(self, user, newpassword_plain, new_password_status=None):
        # TODO check password strength
        hash = make_password(newpassword_plain)
        assert hash.startswith('crypt$$'), 'Hash algorithm is imcompatible with apache authentication'
        hash = hash[len('crypt$$'):]
        self.set_fieldvalue(user, FIELD_PASSWORD, hash)
        self.set_fieldvalue(user, FIELD_PASSWORD_PLAIN, newpassword_plain)
        if new_password_status is None:
            if self.id == user.id:
                self.set_fieldvalue(user, FIELD_PASSWORD_STATUS, '3') # User defined
            else:
                self.set_fieldvalue(user, FIELD_PASSWORD_STATUS, '1') # Generated
        else:
            self.set_fieldvalue(user, FIELD_PASSWORD_STATUS, new_password_status)


    @staticmethod
    def check_login_created(logged_contact):
        # Create login for all members of GROUP_USER
        cursor = connection.cursor()
        cursor.execute("SELECT users.contact_id FROM (SELECT DISTINCT contact_in_group.contact_id FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.flags & %(member_flag)s <> 0) AS users LEFT JOIN contact_field_value ON (contact_field_value.contact_id=users.contact_id AND contact_field_value.contact_field_id=%(FIELD_LOGIN)d) WHERE contact_field_value.value IS NULL" % {'member_flag': CIGFLAG_MEMBER, 'GROUP_USER': GROUP_USER, 'FIELD_LOGIN': FIELD_LOGIN})
        for uid, in cursor:
            contact = Contact.objects.get(pk=uid)
            new_login = contact.generate_login()
            contact.set_fieldvalue(logged_contact, FIELD_LOGIN, new_login)
            contact.set_password(logged_contact, contact.generate_password())
            logged_contact.push_message("Login information generated for User %s."%(contact.name))

        for cfv in ContactFieldValue.objects.extra(where=["contact_field_value.contact_field_id=%(FIELD_LOGIN)d AND NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact_field_value.contact_id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.flags & %(member_flag)s <> 0)" % {'member_flag': CIGFLAG_MEMBER, 'GROUP_USER': GROUP_USER, 'FIELD_LOGIN': FIELD_LOGIN}]):
            cfv.delete()
            logged_contact.push_message("Delete login information for User %s."%(cfv.contact.name))

    def is_member_of(self, group_id):
        cin = ContactInGroup.objects.filter(contact_id=self.id).extra(where=['flags & %s <> 0' % CIGFLAG_MEMBER, 'group_id IN (SELECT self_and_subgroups(%s))' % group_id])
        return len(cin) > 0

    def is_admin(self):
        return self.is_member_of(GROUP_ADMIN)

    def update_lastconnection(self):
        # see NgwAuthBackend.enable_lastconnection_updates
        cfv, created = ContactFieldValue.objects.get_or_create(contact_id=self.id, contact_field_id=FIELD_LASTCONNECTION)
        cfv.value = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cfv.save()



class ContactGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    field_group = models.BooleanField()
    date = models.DateField(null=True, blank=True)
    budget_code = models.CharField(max_length=10)
    system = models.BooleanField()
    mailman_address = models.CharField(max_length=255, blank=True)
    has_news = models.BooleanField()
    sticky = models.BooleanField()
    #direct_supergroups = models.ManyToManyField("self", through='GroupInGroup', symmetrical=False, related_name='none1+')
    #direct_subgroups = models.ManyToManyField("self", through='GroupInGroup', symmetrical=False, related_name='none2+')
    class Meta:
        db_table = 'contact_group'

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return b'ContactGroup <' + str(self.id) + self.name.encode('utf-8') + b'>'

    def get_smart_navbar(self):
        nav = Navbar()
        if self.date:
            nav.add_component(("events", "Events"))
        else:
            nav.add_component(("contactgroups", "Contact Groups"))
        nav.add_component((str(self.id), self.name))
        return nav

    def get_absolute_url(self):
        if self.date:
            return '/events/' + unicode(self.id) + '/'
        else:
            return self.get_class_absolute_url() + unicode(self.id) + '/'


    def get_direct_supergroups_ids(self):
        """
        Returns all the direct supergroup ids
        """
        return [gig.father_id \
            for gig in GroupInGroup.objects.filter(subgroup_id=self.id)]

    def get_visible_direct_supergroups_ids(self, cid):
        """
        Returns the direct supergroup ids that are visible by contact cid
        """
        return [gig.father_id \
            for gig in GroupInGroup.objects.filter(subgroup_id=self.id).extra(where=[
                'perm_c_can_see_cg(%s, group_in_group.father_id)' % cid ])]

    def get_direct_supergroups(self):
        return ContactGroup.objects.filter(direct_gig_subgroups__subgroup_id=self.id)

    def set_direct_supergroups_ids(self, ids):
        # supergroups have no properties (yet!): just recreate the array with brute force
        for gig in GroupInGroup.objects.filter(subgroup_id=self.id):
            gig.delete()

        for id in ids:
            GroupInGroup(father_id=id, subgroup_id=self.id).save()

    def get_self_and_supergroups(self):
        return ContactGroup.objects.extra(where=['id IN (SELECT self_and_supergroups(%s))' % self.id])

    def get_supergroups(self):
        return self.get_self_and_supergroups().exclude(id=self.id)



    def get_direct_subgroups(self):
        return ContactGroup.objects.filter(direct_gig_supergroups__father_id=self.id)

    def get_self_and_subgroups(self):
        return ContactGroup.objects.extra(where=['id IN (SELECT self_and_subgroups(%s))' % self.id])

    def get_subgroups(self):
        return self.get_self_and_subgroups().exclude(id=self.id)


    def get_visible_mananger_groups_ids(self, cid, flag):
        '''
        Returns a list of groups ids whose members automatically gets "flag"
        priviledges on self, and are visbile contact cid.
        '''
        return [gig.father_id \
            for gig in GroupManageGroup.objects.filter(subgroup_id=self.id).extra(where=[
                'flags & %s <> 0' % flag,
                'perm_c_can_see_cg(%s, group_manage_group.father_id)' % cid ])]

    def get_manager_groups(self):
        return ContactGroup.objects \
            .filter(direct_gmg_subgroups__subgroup_id=self.id)

    def get_all_members(self):
        return Contact.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.id, CIGFLAG_MEMBER)])


    def get_link_name(self):
        "Name will then be clickable in the list"
        return self.get_absolute_url()

    # Don't use that, we need to check permissions
    #def supergroups_includinghtml(self):
    #    sgs = self.get_supergroups()
    #    if not sgs:
    #        return ''
    #    return ' (implies ' + ', '.join(['<a href="'+g.get_absolute_url()+'">'+html.escape(g.name)+'</a>' for g in sgs]) + ')'

    # Don't use that, we need to check permissions
    #def subgroups_includinghtml(self):
    #    sgs = self.get_subgroups()
    #    if not sgs:
    #        return ''
    #    return ' (including ' + ', '.join(['<a href="'+g.get_absolute_url()+'">'+html.escape(g.name)+'</a>' for g in sgs]) + ')'

    # See group_add_contacts_to.html
    def is_event(self):
        return self.date is not None

    def html_date(self):
        if self.date:
            return ngw_date_format(self.date)
        else:
            return ''

    def unicode_with_date(self):
        """ Returns the name of the group, and the date if there's one"""
        result = self.name
        if self.date:
            result += ' ‧ '+ngw_date_format(self.date)
        return result

    def mailman_request_address(self):
        ''' Adds -request before the @ of the address '''
        if self.mailman_address:
            return self.mailman_address.replace('@', '-request@')


    def static_folder(self):
        """ Returns the name of the folder for static files for that group """
        return GROUP_STATIC_DIR+str(self.id)


    def check_static_folder_created(self):
        """ Create the folder for static files and setup permissions """
#        if not self.id:
#            self.save()
        assert(self.id)
        dirname = self.static_folder()
        if not os.path.isdir(dirname):
            print("Creating missing directory for group %i" % self.id)
            os.mkdir(dirname)
        htaccess_path = os.path.join(dirname, ".htaccess")
        if not os.path.isfile(htaccess_path):
            print("Creating missing .htaccess file for group %i" % self.id)
            f = open(htaccess_path, 'w')
            f.write("Require group %i\n" % self.id)
            f.close()

    def get_filters_classes(self):
        return (GroupFilterIsMember, GroupFilterIsNotMember, GroupFilterIsInvited, GroupFilterIsNotInvited, GroupFilterDeclinedInvitation, GroupFilterNotDeclinedInvitation, )

    def get_filters(self):
        return [ cls(self.id) for cls in self.get_filters_classes() ]

    def get_filter_by_name(self, name):
        return [ f for f in self.get_filters() if f.__class__.internal_name==name][0]

    def get_birthday_members(self):
        #select * from contact_field_value where contact_field_id=6 and value like '%-11-%';
        q = self.get_all_members()
        w2 = "EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id=contact.id AND contact_field_value.contact_field_id=%s AND contact_field_value.value LIKE '%s')" % \
                    (FIELD_BIRTHDAY, datetime.today().strftime('%%%%-%m-%d'))
        q = q.extra(where=[w2])
        #print(q.query)
        return q

    def get_default_display(self):
        if not self.date:
            return 'mg'
        if self.date > datetime.utcnow().date():
            return 'mig'
        else:
            return 'mg'


    def set_member_1(self, logged_contact, contact, group_member_mode):
        """
        group_member_mode is a combinaison of letters 'mido'
        if it starts with '+', the mode will be added (dropping incompatible ones).
        Example '+d' actually means '-mi+d'
        if it starst with '-', the mode will be deleted
        TODO enforce that:
        m/i/d are mutually exclusive
        returns
        LOG_ACTION_ADD if added
        LOG_ACTION_CHANGE if changed
        LOG_ACTION_DEL if deleted
        0 other wise
        If the contact was not in the group, it will be added.
        If new mode is empty, the contact will be removed from the group.
        """

        result = 0

        add_mode = 0
        del_mode = 0

        assert group_member_mode and group_member_mode[0] in '+-', 'Invalid membership mode'
        for letter in group_member_mode:
            if letter in '+-':
                operation = letter
            elif letter == 'm':
                if operation == '+':
                    add_mode = (add_mode | CIGFLAG_MEMBER) & ~(CIGFLAG_INVITED | CIGFLAG_DECLINED)
                    del_mode = del_mode & ~CIGFLAG_MEMBER | CIGFLAG_INVITED | CIGFLAG_DECLINED
                else: # operation == '-'
                    del_mode |= CIGFLAG_MEMBER
                    add_mode &= ~CIGFLAG_MEMBER
            elif letter == 'i':
                if operation == '+':
                    add_mode = (add_mode | CIGFLAG_INVITED) & ~(CIGFLAG_MEMBER | CIGFLAG_DECLINED)
                    del_mode = del_mode & ~CIGFLAG_INVITED | CIGFLAG_MEMBER | CIGFLAG_DECLINED
                else: # operation == '-'
                    del_mode |= CIGFLAG_INVITED
                    add_mode &= ~CIGFLAG_INVITED
            elif letter == 'd':
                if operation == '+':
                    add_mode = (add_mode | CIGFLAG_DECLINED) & ~ (CIGFLAG_MEMBER | CIGFLAG_INVITED)
                    del_mode = del_mode & ~CIGFLAG_DECLINED | CIGFLAG_MEMBER | CIGFLAG_INVITED
                else: # operation == '-'
                    del_mode |= CIGFLAG_DECLINED
                    add_mode &= ~CIGFLAG_DECLINED
            elif letter in 'iveEcCfFnNuU':
                intmode = TRANS_CIGFLAG_CODE2INT[letter]
                if operation == '+':
                    add_mode |= intmode
                    del_mode &= ~intmode
                else: # operation == '-'
                    del_mode |= intmode
                    add_mode &= ~intmode
            else:
                raise ValueError('Unknown mode "%s"' % letter)

        try:
            cig = ContactInGroup.objects.get(contact_id=contact.id, group_id=self.id)
        except ContactInGroup.DoesNotExist:
            if not add_mode:
                return result # 0 = no change

            cig = ContactInGroup(contact_id=contact.id, group_id=self.id, flags=0)
            log = Log(contact_id=logged_contact.id)
            log.action = LOG_ACTION_ADD
            log.target = 'ContactInGroup ' + unicode(contact.id) + ' ' + unicode(self.id)
            log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
            log.save()
            result = LOG_ACTION_ADD

        for flag in 'midoveEcCfFnNuU':
            intflag = TRANS_CIGFLAG_CODE2INT[flag]
            if add_mode & intflag:
                if not cig.flags & intflag:
                    cig.flags |= intflag
                    log = Log(contact_id=logged_contact.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = 'ContactInGroup ' + unicode(contact.id) + ' ' + unicode(self.id)
                    log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
                    log.property = TRANS_CIGFLAG_CODE2TXT[flag]
                    log.property_repr = log.property.replace('_', ' ').capitalize()
                    log.change = 'new value is true'
                    log.save()
                    result = result or LOG_ACTION_CHANGE
            if del_mode & intflag:
                if cig.flags & intflag:
                    cig.flags &= ~intflag
                    log = Log(contact_id=logged_contact.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = 'ContactInGroup ' + unicode(contact.id) + ' ' + unicode(self.id)
                    log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
                    log.property = TRANS_CIGFLAG_CODE2TXT[flag]
                    log.property_repr = log.property.replace('_', ' ').capitalize()
                    log.change = 'new value is false'
                    log.save()
                    result = result or LOG_ACTION_CHANGE

        if not cig.flags:
            cig.delete()
            log = Log(contact_id=logged_contact.id)
            log.action = LOG_ACTION_DEL
            log.target = 'ContactInGroup ' + unicode(contact.id) + ' ' + unicode(self.id)
            log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
            result = LOG_ACTION_CHANGE
        else:
            cig.save()

        if result:
            hooks.membership_changed(logged_contact, contact, self)
        return result


    def set_member_n(self, logged_contact, contacts, group_member_mode):
        """
        Like set_member_1 but for several contacts
        """
        added_contacts = []
        changed_contacts = []
        for contact in contacts:
            res = self.set_member_1(logged_contact, contact, group_member_mode)
            if res == LOG_ACTION_ADD:
                added_contacts.append(contact)
            elif res == LOG_ACTION_CHANGE:
                changed_contacts.append(contact)

        if added_contacts:
            msgpart_contacts = ', '.join([c.name for c in added_contacts])
            if len(added_contacts)==1:
                msg = 'Contact %s has been added in %s with status %s.'
            else:
                msg = 'Contacts %s have been added in %s with status %s.'
            logged_contact.push_message(msg % (msgpart_contacts, self.unicode_with_date(), group_member_mode))
        if changed_contacts:
            msgpart_contacts = ', '.join([c.name for c in changed_contacts])
            if len(changed_contacts)==1:
                msg = 'Contact %s allready was in %s. Status has been changed to %s.'
            else:
                msg = 'Contacts %s allready were in %s. Status have been changed to %s.'
            logged_contact.push_message(msg % (msgpart_contacts, self.unicode_with_date(), group_member_mode))



########################################
# Contact Fields

def register_contact_field_type(cls, db_type_id, human_type_id, has_choice):
    ContactField.types_classes[db_type_id] = cls
    cls.db_type_id = db_type_id
    cls.human_type_id = human_type_id
    cls.has_choice = has_choice
    return cls



class ContactField(NgwModel):
    # This is a polymorphic class:
    # When it's ready, it's "upgraded" into one of its subclass
    # See polymorphic_upgrade()
    types_classes = {}

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    hint = models.TextField(blank=True)
    type = models.CharField(max_length=15)
    contact_group = models.ForeignKey(ContactGroup)
    sort_weight = models.IntegerField()
    choice_group = models.ForeignKey(ChoiceGroup, null=True, blank=True)
    system = models.BooleanField()
    default = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_field'
        ordering = 'sort_weight',

    @classmethod
    def get_class_absolute_url(cls):
        return '/contactfields/'

    def __repr__(self):
        return b'ContactField <' + str(self.id) + b',' + self.name.encode('utf8') + b',' + self.type.encode('utf8') + b'>'

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_contact_field_type_by_dbid(db_type_id):
        return ContactField.types_classes[db_type_id]

    def polymorphic_upgrade(self):
        """
        That special method is called to "upgrade" a base abstract ContactType
        into one of its subtypes.
        """
        self.__class__ = self.types_classes[self.type]

    get_link_name = NgwModel.get_absolute_url

    def str_type_base(self):
        return self.human_type_id

    def type_as_html(self):
        return self.str_type_base()

    def format_value_unicode(self, value):
        return value

    def format_value_html(self, value):
        return self.format_value_unicode(value)

    def get_form_fields(self):
        raise NotImplementedError()

    def formfield_value_to_db_value(self, value):
        return unicode(value)

    def db_value_to_formfield_value(self, value):
        return value

    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        return True

    def get_filters_classes(self):
        return (FieldFilterNull, FieldFilterNotNull,)

    def get_filters(self):
        return [ cls(self.id) for cls in self.get_filters_classes() ]

    def get_filter_by_name(self, name):
        return [ f for f in self.get_filters() if f.__class__.internal_name==name][0]

    @staticmethod
    def renumber():
        """
        Update all fields sort_weight so that each weight is previous + 10
        """
        new_weigth = 0
        for cf in ContactField.objects.order_by('sort_weight'):
            new_weigth += 10
            cf.sort_weight = new_weigth
            cf.save()


def contact_field_initialized_my_manager(sender, **kwargs):
    field = kwargs['instance']
    assert field.type is not None, 'Polymorphic abstract class must be created with type defined'
    field.polymorphic_upgrade()
models.signals.post_init.connect(contact_field_initialized_my_manager, ContactField)



class FilterHelper(object):
    @staticmethod
    def sqlescape_where_params(query, where, **kargs):
        """
        That function renames the arguements in such a way that it can be called successive times using the same parameters.
        It modifies the where string and return a new one, *without* actually applying the filters, so it can be used in a or clause.
        On the other hand, the parameters are automatically added to the query ones.
        The return value is a 2-tupple with the modified where clause and the modified parameters.
        """
        # kargs is a dictionnary of parameters to apply to where
        # unicode parameters are escaped
        # integers are expanded inline
        params_where = { }
        params_sql = { }
        for k, v in kargs.iteritems():
            #print(k, "=", v)
            auto_param_name = 'autoparam_' + unicode(len(query.params)) + '_' # resolve conflicts in sucessive calls to apply_where_to_query
            if isinstance(v, unicode):
                params_where[ k ] = '%(' + auto_param_name + k + ')s'
                params_sql[ auto_param_name+k ] = v
            elif isinstance(v, int):
                params_where[ k ] = v
            else:
                raise Exception('Unsupported type ' + unicode(type(v)))
        where = where % params_where
        return where, params_sql

    def get_sql_query_where(self, query, *args, **kargs):
        """
        Helper function thaa:
        - calls self.get_sql_where_params
        - renames the parameters in a way there can't be name collisions
        - add the literal parameters to the query
        - return (query, where string)
        """
        where, params = self.get_sql_where_params(*args, **kargs)
        where, params = self.sqlescape_where_params(query, where, **params)
        query = query.add_params(params)
        return query, where


class Filter(FilterHelper):
    """
    This is a generic filter that must be given arguments before being applied.
    Exemple: "profession startswith"
    Filters should define 3 methods:
        get_sql_where_params(query, ...)
        to_html(...)
        get_param_types()
    """
    def bind(self, *args):
        return BoundFilter(self, *args)

class NameFilterStartsWith(Filter):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return '(contact.name ~* %(value_name1)s OR contact.name ~* %(value_name2)s)', { 'value_name1': '^' + value, 'value_name2': ' '+value }
    def to_html(self, value):
        return '<b>Name</b> ' + self.__class__.human_name + ' "' + unicode(value) + '"'

    def get_param_types(self):
        return (unicode,)
NameFilterStartsWith.internal_name = 'startswith'
NameFilterStartsWith.human_name = 'has a word starting with'

class FieldFilter(Filter):
    """ Helper abstract class for field filters """
    def __init__(self, field_id):
        self.field_id = field_id

class FieldFilterOp0(FieldFilter):
    """ Helper abstract class for field filters that takes no parameter """
    def to_html(self):
        field = ContactField.objects.get(pk=self.field_id)
        return '<b>' + html.escape(field.name) + '</b> ' + self.__class__.human_name

class FieldFilterOp1(FieldFilter):
    """ Helper abstract class for field filters that takes 1 parameter """
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        result = '<b>' + html.escape(field.name) + '</b> ' + self.__class__.human_name + ' '
        if isinstance(value, unicode):
            value = '"' + value + '"'
        else:
            value = unicode(value)
        return result+value


class FieldFilterStartsWith(FieldFilterOp1):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value1)s OR (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value2)s', { 'field_id':self.field_id, 'value1': '^'+value, 'value2': ' '+value}
    def get_param_types(self):
        return (unicode,)
FieldFilterStartsWith.internal_name = 'startswith'
FieldFilterStartsWith.human_name = 'has a word starting with'


class FieldFilterEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (unicode,)
FieldFilterEQ.internal_name = 'eq'
FieldFilterEQ.human_name = '='


class FieldFilterNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterNEQ.internal_name = 'neq'
FieldFilterNEQ.human_name = '≠'


class FieldFilterLE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) <= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterLE.internal_name = 'le'
FieldFilterLE.human_name = '≤'


class FieldFilterGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) >= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterGE.internal_name = 'ge'
FieldFilterGE.human_name = '≥'


class FieldFilterLIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) LIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterLIKE.internal_name = 'like'
FieldFilterLIKE.human_name = 'SQL LIKE'


class FieldFilterILIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterILIKE.internal_name = 'ilike'
FieldFilterILIKE.human_name = 'SQL ILIKE'


class FieldFilterNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNull.internal_name = 'null'
FieldFilterNull.human_name = 'is undefined'


class FieldFilterNotNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNotNull.internal_name = 'notnull'
FieldFilterNotNull.human_name = 'is defined'


class FieldFilterIEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int = %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIEQ.internal_name = 'ieq'
FieldFilterIEQ.human_name = '='


class FieldFilterINE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <> %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterINE.internal_name = 'ineq'
FieldFilterINE.human_name = '≠'


class FieldFilterILT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int < %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterILT.internal_name = 'ilt'
FieldFilterILT.human_name = '<'


class FieldFilterIGT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int > %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIGT.internal_name = 'igt'
FieldFilterIGT.human_name = '>'


class FieldFilterILE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <= %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterILE.internal_name = 'ile'
FieldFilterILE.human_name = '≤'


class FieldFilterIGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int >= %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIGE.internal_name = 'ige'
FieldFilterIGE.human_name = '≥'


class FieldFilterAGE_GE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND NOW() - value::DATE > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterAGE_GE.internal_name = 'agege'
FieldFilterAGE_GE.human_name = 'Age (years) ≥'


class FieldFilterVALID_GT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterVALID_GT.internal_name = 'validitygt'
FieldFilterVALID_GT.human_name = 'date until event ≥'


class FieldFilterFUTURE(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )', { 'field_id': self.field_id }
    def get_param_types(self):
        return ()
FieldFilterFUTURE.internal_name = 'future'
FieldFilterFUTURE.human_name = 'In the future'


class FieldFilterChoiceEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return '<b>' + html.escape(field.name) + '</b> ' + self.__class__.human_name + ' "' + html.escape(cfv.value) + '"'
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterChoiceEQ.internal_name = 'ceq'
FieldFilterChoiceEQ.human_name = '='


class FieldFilterChoiceNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return '<b>' + html.escape(field.name) + '</b> ' + self.__class__.human_name + ' "' + html.escape(cfv.value) + '"'
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterChoiceNEQ.internal_name = 'cneq'
FieldFilterChoiceNEQ.human_name = '≠'


class FieldFilterMultiChoiceHAS(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return '<b>' + html.escape(field.name) + '</b> ' + self.__class__.human_name + ' "' + html.escape(cfv.value) + '"'
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHAS.internal_name = 'mchas'
FieldFilterMultiChoiceHAS.human_name = 'contains'


class FieldFilterMultiChoiceHASNOT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return '<b>' + html.escape(field.name) + '</b> ' + self.__class__.human_name + ' "' + html.escape(cfv.value) + '"'
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHASNOT.internal_name = 'mchasnot'
FieldFilterMultiChoiceHASNOT.human_name = "doesn't contain"



class GroupFilterIsMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, CIGFLAG_MEMBER), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name + ' <b>' + group.unicode_with_date() + '</b>'
    def get_param_types(self):
        return ()
GroupFilterIsMember.internal_name = 'memberof'
GroupFilterIsMember.human_name = 'is member of group'


class GroupFilterIsNotMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, CIGFLAG_MEMBER), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name + ' <b>' + group.unicode_with_date() + '</b>'
    def get_param_types(self):
        return ()
GroupFilterIsNotMember.internal_name = 'notmemberof'
GroupFilterIsNotMember.human_name = 'is not member of group'


class GroupFilterIsInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, CIGFLAG_INVITED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name + ' <b>' + group.unicode_with_date() + '</b>'
    def get_param_types(self):
        return ()
GroupFilterIsInvited.internal_name = 'ginvited'
GroupFilterIsInvited.human_name = 'has been invited in group'


class GroupFilterIsNotInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, CIGFLAG_INVITED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name + ' <b>' + group.unicode_with_date() + '</b>'
    def get_param_types(self):
        return ()
GroupFilterIsNotInvited.internal_name = 'gnotinvited'
GroupFilterIsNotInvited.human_name = 'has not been invited in group'


class GroupFilterDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, CIGFLAG_DECLINED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name + ' <b>' + group.unicode_with_date() + '</b>'
    def get_param_types(self):
        return ()
GroupFilterDeclinedInvitation.internal_name = "gdeclined"
GroupFilterDeclinedInvitation.human_name = 'has declined invitation in group'


class GroupFilterNotDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, CIGFLAG_DECLINED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name + ' <b>' + group.unicode_with_date() + '</b>'
    def get_param_types(self):
        return ()
GroupFilterNotDeclinedInvitation.internal_name = 'gnotdeclined'
GroupFilterNotDeclinedInvitation.human_name = 'has not declined invitation in group'


class AllEventsNotReactedSince(Filter):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return 'NOT EXISTS (SELECT * from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %%(date)s AND flags & %s <> 0)' % (CIGFLAG_MEMBER | CIGFLAG_DECLINED), { 'date':value }
    def to_html(self, value):
        return self.__class__.human_name + ' "' + unicode(value) + '"'
    def get_param_types(self):
        return (unicode,) # TODO: Accept date parameters
AllEventsNotReactedSince.internal_name = 'notreactedsince'
AllEventsNotReactedSince.human_name = 'has not reacted to any invitation since'

class AllEventsReactionYearRatioLess(Filter):
    def get_sql_where_params(self, value):
        return '(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_DECLINED) + ' <> 0) < ' + str(value/100.) + ' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_INVITED | CIGFLAG_DECLINED) + ' <> 0)', { 'refdate': unicode((datetime.today() - timedelta(365)).strftime('%Y-%m-%d')) }
    def to_html(self, value):
        return self.__class__.human_name + ' "' + unicode(value) + '"'
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioLess.internal_name = 'yearreactionratioless'
AllEventsReactionYearRatioLess.human_name = '1 year invitation reaction % less than'

class AllEventsReactionYearRatioMore(Filter):
    def get_sql_where_params(self, value):
        return '(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_DECLINED) + ' <> 0) > ' + str(value/100.) + ' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_INVITED | CIGFLAG_DECLINED) + ' <> 0)', { 'refdate': unicode((datetime.today() - timedelta(365)).strftime('%Y-%m-%d')) }
    def to_html(self, value):
        return self.__class__.human_name + ' "' + unicode(value) + '"'
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioMore.internal_name = 'yearreactionratiomore'
AllEventsReactionYearRatioMore.human_name = '1 year invitation reaction % more than'



#######################################################

class BaseBoundFilter(FilterHelper):
    """
    This is a full contact filter with both function and arguments
    """
    def apply_filter_to_query(self, query):
        query, where = self.get_sql_query_where(query)
        return query.filter(where)

    @staticmethod
    def indent(indent_level):
        return '\u00a0' * 4 * indent_level


class BoundFilter(BaseBoundFilter):
    # TODO: Rename to FieldBoundFilter

    def __init__(self, filter, *args):
        super(BoundFilter, self).__init__()
        self.filter = filter
        self.args = args

    def __repr__(self):
        return b'BoundFilter <' + \
            b','.join([repr(self.filter)] + [repr(arg) for arg in self.args]) \
            + b'>'

    def get_sql_where_params(self):
        return self.filter.get_sql_where_params(*self.args)

    def to_html(self, indent_level=0):
        return self.indent(indent_level)+self.filter.to_html(*self.args)


class EmptyBoundFilter(BaseBoundFilter):
    def apply_filter_to_query(self, query):
        return query
    def to_html(self, indent_level=0):
        return self.indent(indent_level) + 'All contacts'


class AndBoundFilter(BaseBoundFilter):
    def __init__(self, f1, f2):
        super(AndBoundFilter, self).__init__()
        self.f1 = f1
        self.f2 = f2
    def get_sql_query_where(self, query, *args, **kargs):
        query, where1 = self.f1.get_sql_query_where(query)
        query, where2 = self.f2.get_sql_query_where(query)
        return query, '((' + where1 + ') AND (' + where2 + '))'
    def to_html(self, indent_level=0):
        return self.f1.to_html(indent_level+1) + '<br>' + self.indent(indent_level) + 'AND<br>' + self.f2.to_html(indent_level+1)


class OrBoundFilter(BaseBoundFilter):
    def __init__(self, f1, f2):
        super(OrBoundFilter, self).__init__()
        self.f1 = f1
        self.f2 = f2
    def get_sql_query_where(self, query, *args, **kargs):
        query, where1 = self.f1.get_sql_query_where(query)
        query, where2 = self.f2.get_sql_query_where(query)
        return query, '((' + where1 + ') OR (' + where2 + '))'
    def to_html(self, indent_level=0):
        return self.f1.to_html(indent_level+1) + '<br>' + self.indent(indent_level) + 'OR<br>' + self.f2.to_html(indent_level+1)


class ContactFieldValue(NgwModel):
    oid = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact, related_name='values')
    contact_field = models.ForeignKey(ContactField, related_name='values')
    value = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_field_value'

    def __repr__(self):
        cf = self.contact_field
        return b'ContactFieldValue <"' + unicode(self.contact).encode('utf-8') + b'", "' + unicode(cf).encode('utf-8') + b'", "' + unicode(self).encode('utf-8') + b'">'

    def __unicode__(self):
        cf = self.contact_field
        return cf.format_value_unicode(self.value)

    def as_html(self):
        cf = self.contact_field
        return cf.format_value_html(self.value)


class GroupInGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    father = models.ForeignKey(ContactGroup, related_name='direct_gig_subgroups')
    subgroup = models.ForeignKey(ContactGroup, related_name='direct_gig_supergroups')
    class Meta:
        db_table = 'group_in_group'

    def __repr__(self):
        return b'GroupInGroup <%s %s>' % (self.subgroup_id, self.father_id)


class GroupManageGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    father = models.ForeignKey(ContactGroup, related_name='direct_gmg_subgroups')
    subgroup = models.ForeignKey(ContactGroup, related_name='direct_gmg_supergroups')
    flags = models.IntegerField()
    class Meta:
        db_table = 'group_manage_group'

    def __repr__(self):
        return b'GroupManageGroup <%s %s>' % (self.subgroup_id, self.father_id)



class ContactInGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact)
    group = models.ForeignKey(ContactGroup)
    flags = models.IntegerField()
    note = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_in_group'

    def __repr__(self):
        return b'ContactInGroup<%s,%s>' % (self.contact_id, self.group_id)

    def __unicode__(self):
        return 'contact %(contactname)s in group %(groupname)s' % { 'contactname': self.contact.name, 'groupname': self.group.unicode_with_date() }

    @classmethod
    def get_class_navcomponent(cls):
        raise NotImplementedError()

    def get_navcomponent(self):
        return self.contact.get_navcomponent()

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url() + 'members/' + str(self.contact_id) + '/membership'


class ContactSysMsg(NgwModel):
    id = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact)
    message = models.TextField()
    class Meta:
        db_table = 'contact_sysmsg'


class ContactGroupNews(NgwModel):
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(Contact, null=True, blank=True)
    contact_group = models.ForeignKey(ContactGroup, null=True, blank=True)
    date = models.DateTimeField()
    title = models.TextField()
    text = models.TextField()

    class Meta:
        db_table = 'contact_group_news'
        ordering = '-date',
        verbose_name = 'news'
        verbose_name_plural = 'news'

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url() + 'news/' + str(self.id) + '/'


