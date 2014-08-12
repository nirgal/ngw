# -*- encoding: utf-8 -*-
#
# Also note: You'll have to insert the output of 'manage.py sqlall core'
# into your database.

from __future__ import division, absolute_import, print_function, unicode_literals
import os
from functools import wraps
from datetime import datetime, timedelta
import subprocess
import logging
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils.encoding import force_text, smart_text, force_str, python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _, string_concat
from django.db import models, connection
from django import forms
from django.http import Http404
from django.utils import html
from django.utils import formats
from django.utils import six
from django.contrib.auth.hashers import check_password, make_password
from django.contrib import messages
import decoratedstr # Nirgal external package
from ngw.core.nav import Navbar
from ngw.core import perms
#from ngw.core.filters import (NameFilterStartsWith, FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLE, FieldFilterGE, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull, FieldFilterIEQ, FieldFilterINE, FieldFilterILT, FieldFilterIGT, FieldFilterILE, FieldFilterIGE, FieldFilterAGE_GE, FieldFilterVALID_GT, FieldFilterFUTURE, FieldFilterChoiceEQ, FieldFilterChoiceNEQ, FieldFilterMultiChoiceHAS, FieldFilterMultiChoiceHASNOT, GroupFilterIsMember, GroupFilterIsNotMember, GroupFilterIsInvited, GroupFilterIsNotInvited, GroupFilterDeclinedInvitation, GroupFilterNotDeclinedInvitation, AllEventsNotReactedSince, AllEventsReactionYearRatioLess, AllEventsReactionYearRatioMore)
from ngw.extensions import hooks
from django.utils.crypto import get_random_string

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
CIGFLAG_VIEW_MSGS      = 32768 # 'x'ternal messages
CIGFLAG_WRITE_MSGS     = 65536 # 'X'

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
    (CIGFLAG_OPERATOR, 'o', 'operator', 'veEcCfFnNuUxX', ''),
    (CIGFLAG_VIEWER, 'v', 'viewer', 'ecfnux', ''),
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
    (CIGFLAG_VIEW_MSGS, 'x', 'view_msgs', 'e', ''),
    (CIGFLAG_WRITE_MSGS, 'X', 'write_msgs', 'ex', ''),
)

ADMIN_CIGFLAGS =  (CIGFLAG_OPERATOR | CIGFLAG_VIEWER
                 | CIGFLAG_SEE_CG | CIGFLAG_CHANGE_CG
                 | CIGFLAG_SEE_MEMBERS | CIGFLAG_CHANGE_MEMBERS
                 | CIGFLAG_VIEW_FIELDS | CIGFLAG_WRITE_FIELDS
                 | CIGFLAG_VIEW_NEWS | CIGFLAG_WRITE_NEWS
                 | CIGFLAG_VIEW_FILES | CIGFLAG_WRITE_FILES
                 | CIGFLAG_VIEW_MSGS | CIGFLAG_WRITE_MSGS)

OBSERVER_CIGFLAGS = (CIGFLAG_VIEWER
                | CIGFLAG_SEE_CG
                | CIGFLAG_SEE_MEMBERS
                | CIGFLAG_VIEW_FIELDS
                | CIGFLAG_VIEW_NEWS
                | CIGFLAG_VIEW_FILES
                | CIGFLAG_VIEW_MSGS)
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

    for cflag, depends in six.iteritems(CIGFLAGS_CODEDEPENDS):
        for depend in depends:
            if cflag not in CIGFLAGS_CODEONDELETE[depend]:
                CIGFLAGS_CODEONDELETE[depend] += cflag

    #for intval, code, txt, requires, conflicts in __cig_flag_info__:
    #    print(code,
    #        str(TRANS_CIGFLAG_CODE2INT[code]),
    #        '+', CIGFLAGS_CODEDEPENDS[code],
    #        '|'.join([str(TRANS_CIGFLAG_CODE2INT[flag]) for flag in CIGFLAGS_CODEDEPENDS[code]]),
    #        '-', CIGFLAGS_CODEONDELETE[code],
    #        '|'.join([str(TRANS_CIGFLAG_CODE2INT[flag]) for flag in CIGFLAGS_CODEONDELETE[code]]),
    #    )

# This is run on module loading:
_initialise_cigflags_constants()

# Ends with a /
GROUP_STATIC_DIR = settings.MEDIA_ROOT+'g/'


def _truncate_text(txt, maxlen=200):
    'Utility function to truncate text longer that maxlen'
    if len(txt) < maxlen:
        return txt
    return txt[:maxlen] + '…'


class NgwModel(models.Model):
    '''
    This is the base class for all models in that project.
    '''
    # prevent django from trying to instanciate objtype:
    do_not_call_in_templates = True

    class Meta:
        abstract = True

    @classmethod
    def get_class_verbose_name(cls):
        return cls._meta.verbose_name

    @classmethod
    def get_class_verbose_name_plural(cls):
        return cls._meta.verbose_name_plural

    @classmethod
    def get_class_urlfragment(cls):
        return force_text(cls.__name__.lower()) + 's'

    def get_urlfragment(self):
        return force_text(self.id)

    def get_absolute_url(self):
        return self.get_class_absolute_url() + force_text(self.id) + '/'

    @classmethod
    def get_class_navcomponent(cls):
        return cls.get_class_urlfragment(), cls.get_class_verbose_name_plural()

    def get_navcomponent(self):
        return self.get_urlfragment(), smart_text(self)

    @classmethod
    def get_class_absolute_url(cls):
        return '/' + cls.get_class_urlfragment() + '/'


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
        verbose_name = _('log')
        verbose_name_plural = _('logs')

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

@python_2_unicode_compatible
class Config(NgwModel):
    id = models.CharField(max_length=32, primary_key=True)
    text = models.TextField(blank=True)
    class Meta:
        db_table = 'config'
        verbose_name = _('config')
        verbose_name_plural = _('configs')

    def __str__(self):
        return self.id

    @staticmethod
    def get_object_query_page_length():
        try:
            object_query_page_length = Config.objects.get(pk='query_page_length')
            return int(object_query_page_length.text)
        except (Config.DoesNotExist, ValueError):
            return 200


@python_2_unicode_compatible
class Choice(NgwModel):
    oid = models.AutoField(primary_key=True)
    choice_group = models.ForeignKey('ChoiceGroup', related_name='choices')
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    def __str__(self):
        return self.value
    class Meta:
        db_table = 'choice'
        verbose_name = _('choice')
        verbose_name_plural = _('choices')


@python_2_unicode_compatible
class ChoiceGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=True)
    sort_by_key = models.BooleanField(default=False)
    class Meta:
        db_table = 'choice_group'
        verbose_name = _('choices list')
        verbose_name_plural = _('choices lists')

    def __str__(self):
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


class MyContactManager(models.Manager):
    # TODO: Maybe BaseUserManager is a better base class
    def get_by_natural_key(self, username):
        try:
            login_value = ContactFieldValue.objects.get(contact_field_id=FIELD_LOGIN, value=username)
        except ContactFieldValue.DoesNotExist:
            raise Contact.DoesNotExist
        except ContactFieldValue.MultipleObjectsReturned:
            raise Contact.MultipleObjectsReturned
        return login_value.contact

    def create_superuser(self, name, password):
        contact = Contact(name=name)
        contact.save()

        cfv = ContactFieldValue(contact_id=contact.id,
                                contact_field_id = FIELD_LOGIN,
                                value = name)
        cfv.save()

        cfv = ContactFieldValue(contact_id=contact.id,
                                contact_field_id = FIELD_PASSWORD,
                                value = make_password(password))
        cfv.save()

        cig = ContactInGroup(contact_id=contact.id,
                             group_id=GROUP_ADMIN,
                             flags=CIGFLAG_MEMBER|CIGFLAG_OPERATOR)
        cig.save()


@python_2_unicode_compatible
class Contact(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=255, unique=True)

    objects = MyContactManager()
    USERNAME_FIELD = 'name' # Needed by contrib.auth
    REQUIRED_FIELDS = [] # Needed by contrib.auth

    is_active = True # FIXME
    is_staff = True # FIXME XXX XXX 
    def has_module_perms(self, package_name):
        return True
    def has_perm(self, perm, obj=None):
        return True

    class Meta:
        db_table = 'contact'
        verbose_name = _('contact')
        verbose_name_plural = _('contacts')

    def __repr__(self):
        return force_str('Contact <%s>' % self.name)

    def __str__(self):
        return self.name

    def  is_anonymous():
        '''
        Always returns False. Not like AnonymousUser.
        See https://docs.djangoproject.com/en/1.5/ref/contrib/auth/#methods
        '''
        return False

    def is_authenticated(self):
        '''
        Always returns True. Not like AnonymousUser.
        See https://docs.djangoproject.com/en/1.5/ref/contrib/auth/#methods
        '''
        return True

    def check_password(self, raw_password):
        """
        Returns a boolean of whether the raw_password was correct. Handles
        hashing formats behind the scenes.
        """

        try:
            cfv = ContactFieldValue.objects.get(contact_id=self.id, contact_field_id=FIELD_PASSWORD)
        except ContactFieldValue.DoesNotExist:
            return None

        def setter(raw_password):
            cfv.value = make_password(raw_password)
            cfv.save()

        dbpassword = cfv.value
        if not dbpassword:
            return None
        return check_password(raw_password, dbpassword, setter)

    #get_link_name=NgwModel.get_absolute_url
    def name_with_relative_link(self):
        return '<a href="%(id)d/">%(name)s</a>' % { 'id': self.id, 'name': html.escape(self.name) }


    def get_directgroups_member(self):
        "returns the list of groups that contact is a direct member of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=contact_group.id AND flags & %s <> 0)' % (self.id, CIGFLAG_MEMBER)]).order_by('-date', 'name')

    def get_allgroups_member(self):
        "returns the list of groups that contact is a member of."
        return ContactGroup.objects.extra(where=['id IN (SELECT self_and_supergroups(group_id) FROM contact_in_group WHERE contact_id=%s AND flags & %s <> 0)' % (self.id, CIGFLAG_MEMBER)])

    def get_directgroups_invited(self):
        "returns the list of groups that contact has been invited to, directly without group inheritance"
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=contact_group.id AND flags & %s <> 0)' % (self.id, CIGFLAG_INVITED)]).order_by('-date', 'name')

    def get_directgroups_declinedinvitation(self):
        "returns the list of groups that contact has been invited to and he declined the invitation."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=contact_group.id AND flags & %s <> 0)' % (self.id, CIGFLAG_DECLINED)]).order_by('-date', 'name')

    def get_directgroups_operator(self):
        "returns the list of groups that contact is an operator of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=contact_group.id AND flags & %s <> 0)' % (self.id, CIGFLAG_OPERATOR)]).order_by('-date', 'name')

    def get_directgroups_viewer(self):
        "returns the list of groups that contact is a viewer of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=contact_group.id AND flags & %s <> 0)' % (self.id, CIGFLAG_VIEWER)]).order_by('-date', 'name')

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
        assert isinstance(type_, six.text_type)
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
        return smart_text(cfv)

    def set_fieldvalue(self, request, field, newvalue):
        """
        Sets a field value and registers the change in the log table.
        Field can be either a field id or a ContactField object.
        New value must be text.
        """
        user = request.user
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
                    log.target = 'Contact ' + force_text(self.id)
                    log.target_repr = 'Contact ' + self.name
                    log.property = force_text(field_id)
                    log.property_repr = field.name
                    log.change = 'change from ' + smart_text(cfv)
                    cfv.value = newvalue
                    log.change += ' to ' + smart_text(cfv)
                    cfv.save()
                    log.save()
                    hooks.contact_field_changed(request, field_id, self)
            else:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_DEL
                log.target = 'Contact ' + force_text(self.id)
                log.target_repr = 'Contact ' + self.name
                log.property = smart_text(field_id)
                log.property_repr = field.name
                log.change = 'old value was ' + smart_text(cfv)
                cfv.delete()
                log.save()
                hooks.contact_field_changed(request, field_id, self)
        except ContactFieldValue.DoesNotExist:
            if newvalue:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'Contact ' + force_text(self.id)
                log.target_repr = 'Contact ' + self.name
                log.property = smart_text(field_id)
                log.property_repr = field.name
                cfv = ContactFieldValue()
                cfv.contact = self
                cfv.contact_field = field
                cfv.value = newvalue
                cfv.save()
                log.change = 'new value is ' + smart_text(cfv)
                log.save()
                hooks.contact_field_changed(request, field_id, self)


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
            vcf += line('BDAY', force_text(bday))

        vcf += line('END', 'VCARD')
        return vcf

    def get_addr_semicol(self):
        "Returns address in a form compatible with googlemap query"
        return self.get_fieldvalue_by_id(FIELD_STREET) + ';' + self.get_fieldvalue_by_id(FIELD_POSTCODE) + ';' + self.get_fieldvalue_by_id(FIELD_CITY) + ';' + self.get_fieldvalue_by_id(FIELD_COUNTRY)

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
            altlogin = login + force_text(i)
            if not get_logincfv_by_login(self.id, altlogin):
                return altlogin
            i += 1

    @staticmethod
    def generate_password():
        random_password = get_random_string( 8, 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ0123456789!@#$%&*(-_=+)')
        return random_password


    def set_password(self, newpassword_plain, new_password_status=None, request=None):
        assert request, 'ngw version of set_password needs a request parameter'
        # TODO check password strength
        hash = make_password(newpassword_plain)
        self.set_fieldvalue(request, FIELD_PASSWORD, hash)
        if new_password_status is None:
            if self.id == request.user.id:
                self.set_fieldvalue(request, FIELD_PASSWORD_STATUS, '3') # User defined
            else:
                self.set_fieldvalue(request, FIELD_PASSWORD_STATUS, '1') # Generated
        else:
            self.set_fieldvalue(request, FIELD_PASSWORD_STATUS, new_password_status)


    @staticmethod
    def check_login_created(request):
        # Create login for all members of GROUP_USER
        cursor = connection.cursor()
        cursor.execute("SELECT users.contact_id FROM (SELECT DISTINCT contact_in_group.contact_id FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.flags & %(member_flag)s <> 0) AS users LEFT JOIN contact_field_value ON (contact_field_value.contact_id=users.contact_id AND contact_field_value.contact_field_id=%(FIELD_LOGIN)d) WHERE contact_field_value.value IS NULL" % {'member_flag': CIGFLAG_MEMBER, 'GROUP_USER': GROUP_USER, 'FIELD_LOGIN': FIELD_LOGIN})
        for uid, in cursor:
            contact = Contact.objects.get(pk=uid)
            new_login = contact.generate_login()
            contact.set_fieldvalue(request, FIELD_LOGIN, new_login)
            contact.set_password(contact.generate_password(), request=request)
            messages.add_message(request, messages.SUCCESS, _("Login information generated for User %s.") % contact.name)

        for cfv in ContactFieldValue.objects.extra(where=["contact_field_value.contact_field_id=%(FIELD_LOGIN)d AND NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact_field_value.contact_id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.flags & %(member_flag)s <> 0)" % {'member_flag': CIGFLAG_MEMBER, 'GROUP_USER': GROUP_USER, 'FIELD_LOGIN': FIELD_LOGIN}]):
            cfv.delete()
            messages.add_message(request, messages.SUCCESS, _("Login information deleted for User %s.") % cfv.contact.name)


    def is_member_of(self, group_id):
        '''
        Return True if self is a member of group group_id, either directly or
        through inheritence.
        '''
        cin = ContactInGroup.objects.filter(contact_id=self.id).extra(where=['flags & %s <> 0' % CIGFLAG_MEMBER, 'group_id IN (SELECT self_and_subgroups(%s))' % group_id])
        return len(cin) > 0


    def is_directmember_of(self, group_id):
        '''
        Return True if self is a dirrect member of group group_id. Inheritence
        is ignored here.
        '''
        cin = ContactInGroup.objects.filter(contact_id=self.id).extra(where=['flags & %s <> 0' % CIGFLAG_MEMBER]).filter(group_id=group_id)
        return len(cin) > 0


    def is_admin(self):
        return self.is_member_of(GROUP_ADMIN)

    def can_see_all_contacts(self):
        return perms.c_can_see_members_cg(self.id, GROUP_EVERYBODY)

    def update_lastconnection(self):
        # see NgwAuthBackend.authenticate
        cfv, created = ContactFieldValue.objects.get_or_create(contact_id=self.id, contact_field_id=FIELD_LASTCONNECTION)
        cfv.value = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cfv.save()


@python_2_unicode_compatible
class ContactGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    field_group = models.BooleanField(default=False)
    date = models.DateField(null=True, blank=True)
    budget_code = models.CharField(max_length=10)
    system = models.BooleanField(default=False)
    mailman_address = models.CharField(max_length=255, blank=True)
    sticky = models.BooleanField(default=False)
    #direct_supergroups = models.ManyToManyField("self", through='GroupInGroup', symmetrical=False, related_name='none1+')
    #direct_subgroups = models.ManyToManyField("self", through='GroupInGroup', symmetrical=False, related_name='none2+')
    class Meta:
        db_table = 'contact_group'
        verbose_name = _('contact group')
        verbose_name_plural = _('contact groups')

    def __str__(self):
        return self.name

    def __repr__(self):
        return force_str('ContactGroup <%s %s>', (self.id, self.name))

    def get_smart_navbar(self):
        nav = Navbar()
        if self.date:
            nav.add_component(('events', _('events')))
        else:
            nav.add_component(('contactgroups', _('contact groups')))
        nav.add_component((str(self.id), self.name))
        return nav

    def get_absolute_url(self):
        if self.date:
            return '/events/' + force_text(self.id) + '/'
        else:
            return '/contactgroups/' + force_text(self.id) + '/'


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

    def get_members_count(self):
        return self.get_all_members().count()

    def get_contact_perms(self, contact_id):
        '''
        Returns a dictionary will all that group permissions for a given user
        '''
        # This is the optimized version of
        # return {
        #    'o': perms.c_operatorof_cg(contact_id, self.id),
        #    #'v'
        #    'e': perms.c_can_see_cg(contact_id, self.id),
        #    'E': perms.c_can_change_cg(contact_id, self.id),
        #    'c': perms.c_can_see_members_cg(contact_id, self.id),
        #    'C': perms.c_can_change_members_cg(contact_id, self.id),
        #    'f': perms.c_can_view_fields_cg(contact_id, self.id),
        #    'F': perms.c_can_write_fields_cg(contact_id, self.id),
        #    'n': perms.c_can_see_news_cg(contact_id, self.id),
        #    'N': perms.c_can_change_news_cg(contact_id, self.id),
        #    'u': perms.c_can_see_files_cg(contact_id, self.id),
        #    'U': perms.c_can_change_files_cg(contact_id, self.id),
        #    'x': perms.c_can_see_msgs_cg(contact_id, self.id),
        #    'X': perms.c_can_change_msgs_cg(contact_id, self.id),
        # } that returns data in a single query
        sql = '''
            SELECT bit_or(admin_flags) FROM
            (
                SELECT bit_or(gmg_perms.flags) AS admin_flags
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
                    AND contact_id = %(cid)s
                UNION
                    (
                    SELECT contact_in_group.flags AS admin_flags
                    FROM contact_in_group
                    WHERE contact_in_group.group_id=%(gid)s
                    AND contact_in_group.contact_id=%(cid)s
                    )
                UNION
                    (
                    SELECT %(ADMIN_CIGFLAGS)s AS admin_flags
                    WHERE c_ismemberof_cg(%(cid)s, %(GROUP_ADMIN)s)
                    )
                UNION
                    (
                    SELECT %(OBSERVER_CIGFLAGS)s AS admin_flags
                    WHERE c_ismemberof_cg(%(cid)s, %(GROUP_OBSERVERS)s)
                    )
            ) AS compiled
            ''' % {
            'cid': contact_id,
            'gid': self.id,
            'ADMIN_CIGFLAGS': ADMIN_CIGFLAGS,
            'OBSERVER_CIGFLAGS': OBSERVER_CIGFLAGS,
            'GROUP_ADMIN': GROUP_ADMIN,
            'GROUP_OBSERVERS': GROUP_OBSERVERS,
            }
        cursor = connection.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()
        if row:
            perms = row[0]
        else:
            perms = 0
        return {
            'o': perms & CIGFLAG_OPERATOR,
            'v': perms & CIGFLAG_VIEWER,
            'e': perms & CIGFLAG_SEE_CG,
            'E': perms & CIGFLAG_CHANGE_CG,
            'c': perms & CIGFLAG_SEE_MEMBERS,
            'C': perms & CIGFLAG_CHANGE_MEMBERS,
            'f': perms & CIGFLAG_VIEW_FIELDS,
            'F': perms & CIGFLAG_WRITE_FIELDS,
            'n': perms & CIGFLAG_VIEW_NEWS,
            'N': perms & CIGFLAG_WRITE_NEWS,
            'u': perms & CIGFLAG_VIEW_FILES,
            'U': perms & CIGFLAG_WRITE_FILES,
            'x': perms & CIGFLAG_VIEW_MSGS,
            'X': perms & CIGFLAG_WRITE_MSGS,
        }


    def get_link_name(self):
        "Name will then be clickable in the list"
        return self.get_absolute_url()

    # See group_add_contacts_to.html
    def is_event(self):
        '''
        Is this group an event or a permanent group?
        '''
        return self.date is not None

    def html_date(self):
        if self.date:
            return formats.date_format(self.date, "DATE_FORMAT")
        else:
            return ''

    def unicode_with_date(self):
        """ Returns the name of the group, and the date if there's one"""
        result = self.name
        if self.date:
            result += ' ‧ ' + formats.date_format(self.date, "DATE_FORMAT")
        return result

    def description_not_too_long(self):
        '''
        Same as description, but truncated if too long.
        '''
        return _truncate_text(self.description)

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
            os.makedirs(dirname)

    def get_fullfilename(self, path='/'):
        '''
        path is the relative file name within group media folder.
        Returns the full name
        path already be unquoted, but that's all: That function has the
        responsability to check that the path is valid and within the group
        media directory.
        THAT FUNCTION IS ONLY SAFE ON LINUX
        '''
        directory = self.static_folder() # /usr/lib/ngw/media/g/556
        fullfilename = os.path.normpath(directory + os.path.sep + path)
        if not fullfilename.startswith(os.path.normpath(directory)+os.path.sep) \
        and not fullfilename == directory:
            raise PermissionDenied
        return fullfilename


    def get_filenames(self, path='/'):
        '''
        Returns the list of static files of that contacts group
        '''
        folder = self.get_fullfilename(path)
        try:
            files = os.listdir(force_str(folder))
        except OSError as err:
            logging.error(_('Error while reading shared files list in %(folder)s: %(err)s') % {
                'folder': folder,
                'err': err})
            return []

        # listdir() returns some data in utf-8, we want everything in unicode:
        files = [ force_text(file, errors='replace')
            for file in files ]

        # hide files starting with a dot:
        iles = [ file for file in files if file[0]!='.' ]

        files.sort()
        return files


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


    def set_member_1(self, request, contact, group_member_mode):
        """
        group_member_mode is a combinaison of letters 'mido'
        if it starts with '+', the mode will be added (dropping incompatible ones).
        Example '+d' actually means '-mi+d'
        if it starst with '-', the mode will be deleted
        m/i/d are mutually exclusive
        returns:
        LOG_ACTION_ADD if added
        LOG_ACTION_CHANGE if changed
        LOG_ACTION_DEL if deleted
        0 other wise
        If the contact was not in the group, it will be added.
        If new mode is empty, the contact will be removed from the group.
        """

        user = request.user
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
            elif letter in 'oveEcCfFnNuUxX':
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
            log = Log(contact_id=user.id)
            log.action = LOG_ACTION_ADD
            log.target = 'ContactInGroup ' + force_text(contact.id) + ' ' + force_text(self.id)
            log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
            log.save()
            result = LOG_ACTION_ADD

        for flag in 'midoveEcCfFnNuUxX':
            intflag = TRANS_CIGFLAG_CODE2INT[flag]
            if add_mode & intflag:
                if not cig.flags & intflag:
                    if intflag & ADMIN_CIGFLAGS:
                        if not perms.c_operatorof_cg(user.id, self.id):
                            # You need to be operator to be able to change permissions
                            raise PermissionDenied
                    else: # m/i/d
                        # user needs to be able to add contacts
                        # in all subgroups it's not a member yet, including
                        # hidden ones
                        for sg in self.get_supergroups():
                            if not contact.is_directmember_of(sg.id) and not perms.c_can_change_members_cg(user.id, sg.id):
                                raise PermissionDenied
                    cig.flags |= intflag
                    log = Log(contact_id=user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = 'ContactInGroup ' + force_text(contact.id) + ' ' + force_text(self.id)
                    log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
                    log.property = TRANS_CIGFLAG_CODE2TXT[flag]
                    log.property_repr = log.property.replace('_', ' ').capitalize()
                    log.change = 'new value is true'
                    log.save()
                    result = result or LOG_ACTION_CHANGE
            if del_mode & intflag:
                if cig.flags & intflag:
                    if intflag & ADMIN_CIGFLAGS:
                        if not perms.c_operatorof_cg(user.id, self.id):
                            # You need to be operator to be able to change permissions
                            raise PermissionDenied
                    else: # m/i/d
                        # See comment above
                        for sg in self.get_supergroups():
                            if not contact.is_directmember_of(sg.id) and not perms.c_can_change_members_cg(user.id, sg.id):
                                raise PermissionDenied
                    cig.flags &= ~intflag
                    log = Log(contact_id=user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = 'ContactInGroup ' + force_text(contact.id) + ' ' + force_text(self.id)
                    log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
                    log.property = TRANS_CIGFLAG_CODE2TXT[flag]
                    log.property_repr = log.property.replace('_', ' ').capitalize()
                    log.change = 'new value is false'
                    log.save()
                    result = result or LOG_ACTION_CHANGE

        if not cig.flags:
            cig.delete()
            log = Log(contact_id=user.id)
            log.action = LOG_ACTION_DEL
            log.target = 'ContactInGroup ' + force_text(contact.id) + ' ' + force_text(self.id)
            log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.unicode_with_date()
            result = LOG_ACTION_CHANGE
        else:
            cig.save()

        if result:
            hooks.membership_changed(request, contact, self)
        return result


    def set_member_n(self, request, contacts, group_member_mode):
        """
        Like set_member_1 but for several contacts
        """
        added_contacts = []
        changed_contacts = []
        for contact in contacts:
            res = self.set_member_1(request, contact, group_member_mode)
            if res == LOG_ACTION_ADD:
                added_contacts.append(contact)
            elif res == LOG_ACTION_CHANGE:
                changed_contacts.append(contact)

        if added_contacts:
            msgpart_contacts = ', '.join([c.name for c in added_contacts])
            if len(added_contacts)==1:
                msg = _('Contact %(contacts)s has been added in %(group)s with status %(status)s.')
            else:
                msg = _('Contact %(contacts)s have been added in %(group)s with status %(status)s.')
            messages.add_message(request, messages.SUCCESS, msg % {
                'contacts': msgpart_contacts,
                'group': self.unicode_with_date(),
                'status': group_member_mode})
        if changed_contacts:
            msgpart_contacts = ', '.join([c.name for c in changed_contacts])
            if len(changed_contacts)==1:
                msg = _('Contact %(contacts)s already was in %(group)s. Status has been changed to %(status)s.')
            else:
                msg = _('Contacts %(contact)s already were in %(group)s. Status has been changed to %(status)s.')
            messages.add_message(request, messages.SUCCESS, msg % {
                'contacts': msgpart_contacts,
                'group': self.unicode_with_date(),
                'status': group_member_mode})



########################################
# Contact Fields

def register_contact_field_type(cls, db_type_id, human_type_id, has_choice):
    ContactField.types_classes[db_type_id] = cls
    cls.db_type_id = db_type_id
    cls.human_type_id = human_type_id
    cls.has_choice = has_choice
    return cls


@python_2_unicode_compatible
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
    system = models.BooleanField(default=False)
    default = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_field'
        verbose_name = _('contact field')
        verbose_name_plural = _('contact fields')
        ordering = 'sort_weight',

    @classmethod
    def get_class_urlfragment(cls):
        return 'contactfields'

    def __repr__(self):
        return force_str('ContactField <%s,%s,%s>' % (force_text(self.id), self.name, self.type))

    def __str__(self):
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
        return smart_text(value)

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
        for k, v in six.iteritems(kargs):
            #print(k, "=", v)
            auto_param_name = 'autoparam_' + force_text(len(query.params)) + '_' # resolve conflicts in sucessive calls to apply_where_to_query
            if isinstance(v, six.text_type):
                params_where[ k ] = '%(' + auto_param_name + k + ')s'
                params_sql[ auto_param_name+k ] = v
            elif isinstance(v, int):
                params_where[ k ] = v
            else:
                raise Exception('Unsupported type ' + force_text(type(v)))
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
        return string_concat('<b>Name</b> ', self.__class__.human_name, ' "', value, '"')

    def get_param_types(self):
        return (six.text_type,)
NameFilterStartsWith.internal_name = 'startswith'
NameFilterStartsWith.human_name = _('has a word starting with')

class FieldFilter(Filter):
    """ Helper abstract class for field filters """
    def __init__(self, field_id):
        self.field_id = field_id

class FieldFilterOp0(FieldFilter):
    """ Helper abstract class for field filters that takes no parameter """
    def to_html(self):
        field = ContactField.objects.get(pk=self.field_id)
        return string_concat('<b>', html.escape(field.name), '</b> ', self.__class__.human_name)

class FieldFilterOp1(FieldFilter):
    """ Helper abstract class for field filters that takes 1 parameter """
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        result = string_concat('<b>', html.escape(field.name), '</b> ', self.__class__.human_name, ' ')
        if isinstance(value, six.text_type):
            value = string_concat('"', value, '"')
        else:
            value = force_text(value)
        return string_concat(result, value)


class FieldFilterStartsWith(FieldFilterOp1):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value1)s OR (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value2)s', { 'field_id':self.field_id, 'value1': '^'+value, 'value2': ' '+value}
    def get_param_types(self):
        return (six.text_type,)
FieldFilterStartsWith.internal_name = 'startswith'
FieldFilterStartsWith.human_name = _('has a word starting with')


class FieldFilterEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (six.text_type,)
FieldFilterEQ.internal_name = 'eq'
FieldFilterEQ.human_name = '='


class FieldFilterNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (six.text_type,)
FieldFilterNEQ.internal_name = 'neq'
FieldFilterNEQ.human_name = '≠'


class FieldFilterLE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) <= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (six.text_type,)
FieldFilterLE.internal_name = 'le'
FieldFilterLE.human_name = '≤'


class FieldFilterGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) >= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (six.text_type,)
FieldFilterGE.internal_name = 'ge'
FieldFilterGE.human_name = '≥'


class FieldFilterLIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) LIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (six.text_type,)
FieldFilterLIKE.internal_name = 'like'
FieldFilterLIKE.human_name = 'SQL LIKE'


class FieldFilterILIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (six.text_type,)
FieldFilterILIKE.internal_name = 'ilike'
FieldFilterILIKE.human_name = 'SQL ILIKE'


class FieldFilterNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNull.internal_name = 'null'
FieldFilterNull.human_name = _('is undefined')


class FieldFilterNotNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNotNull.internal_name = 'notnull'
FieldFilterNotNull.human_name = _('is defined')


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
FieldFilterAGE_GE.human_name = _('Age (years) ≥')


class FieldFilterVALID_GT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterVALID_GT.internal_name = 'validitygt'
FieldFilterVALID_GT.human_name = _('date until event ≥')


class FieldFilterFUTURE(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )', { 'field_id': self.field_id }
    def get_param_types(self):
        return ()
FieldFilterFUTURE.internal_name = 'future'
FieldFilterFUTURE.human_name = _('In the future')


class FieldFilterChoiceEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return string_concat('<b>', html.escape(field.name), '</b> ', self.__class__.human_name, ' "', html.escape(cfv.value), '"')
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterChoiceEQ.internal_name = 'ceq'
FieldFilterChoiceEQ.human_name = '='


class FieldFilterChoiceNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return string_concat('<b>', html.escape(field.name), '</b> ', self.__class__.human_name, ' "', html.escape(cfv.value), '"')
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterChoiceNEQ.internal_name = 'cneq'
FieldFilterChoiceNEQ.human_name = '≠'


class FieldFilterMultiChoiceHAS(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return string_concat('<b>', html.escape(field.name), '</b> ', self.__class__.human_name, ' "', html.escape(cfv.value), '"')
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHAS.internal_name = 'mchas'
FieldFilterMultiChoiceHAS.human_name = _('contains')


class FieldFilterMultiChoiceHASNOT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return string_concat('<b>', html.escape(field.name), '</b> ', self.__class__.human_name, ' "', html.escape(cfv.value), '"')
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHASNOT.internal_name = 'mchasnot'
FieldFilterMultiChoiceHASNOT.human_name = _("doesn't contain")



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
        return string_concat(self.__class__.human_name, ' <b>', group.unicode_with_date(), '</b>')
    def get_param_types(self):
        return ()
GroupFilterIsMember.internal_name = 'memberof'
GroupFilterIsMember.human_name = _('is member of group')


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
        return string_concat(self.__class__.human_name, ' <b>', group.unicode_with_date(), '</b>')
    def get_param_types(self):
        return ()
GroupFilterIsNotMember.internal_name = 'notmemberof'
GroupFilterIsNotMember.human_name = _('is not member of group')


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
        return string_concat(self.__class__.human_name, ' <b>', group.unicode_with_date(), '</b>')
    def get_param_types(self):
        return ()
GroupFilterIsInvited.internal_name = 'ginvited'
GroupFilterIsInvited.human_name = _('has been invited in group')


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
        return string_concat(self.__class__.human_name, ' <b>', group.unicode_with_date(), '</b>')
    def get_param_types(self):
        return ()
GroupFilterIsNotInvited.internal_name = 'gnotinvited'
GroupFilterIsNotInvited.human_name = _('has not been invited in group')


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
        return string_concat(self.__class__.human_name, ' <b>', group.unicode_with_date(), '</b>')
    def get_param_types(self):
        return ()
GroupFilterDeclinedInvitation.internal_name = "gdeclined"
GroupFilterDeclinedInvitation.human_name = _('has declined invitation in group')


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
        return string_concat(self.__class__.human_name, ' <b>', group.unicode_with_date(), '</b>')
    def get_param_types(self):
        return ()
GroupFilterNotDeclinedInvitation.internal_name = 'gnotdeclined'
GroupFilterNotDeclinedInvitation.human_name = _('has not declined invitation in group')


class AllEventsNotReactedSince(Filter):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return 'NOT EXISTS (SELECT * from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %%(date)s AND flags & %s <> 0)' % (CIGFLAG_MEMBER | CIGFLAG_DECLINED), { 'date':value }
    def to_html(self, value):
        return string_concat(self.__class__.human_name, ' "', value, '"')
    def get_param_types(self):
        return (six.text_type,) # TODO: Accept date parameters
AllEventsNotReactedSince.internal_name = 'notreactedsince'
AllEventsNotReactedSince.human_name = _('has not reacted to any invitation since')

class AllEventsReactionYearRatioLess(Filter):
    def get_sql_where_params(self, value):
        return '(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_DECLINED) + ' <> 0) < ' + str(value/100) + ' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_INVITED | CIGFLAG_DECLINED) + ' <> 0)', { 'refdate': force_text((datetime.today() - timedelta(365)).strftime('%Y-%m-%d')) }
    def to_html(self, value):
        return string_concat(self.__class__.human_name, ' "', value, '"')
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioLess.internal_name = 'yearreactionratioless'
AllEventsReactionYearRatioLess.human_name = _('1 year invitation reaction percentage less than')

class AllEventsReactionYearRatioMore(Filter):
    def get_sql_where_params(self, value):
        return '(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_DECLINED) + ' <> 0) > ' + str(value/100) + ' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(CIGFLAG_MEMBER | CIGFLAG_INVITED | CIGFLAG_DECLINED) + ' <> 0)', { 'refdate': force_text((datetime.today() - timedelta(365)).strftime('%Y-%m-%d')) }
    def to_html(self, value):
        return string_concat(self.__class__.human_name, ' "', value, '"')
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioMore.internal_name = 'yearreactionratiomore'
AllEventsReactionYearRatioMore.human_name = _('1 year invitation reaction percentage more than')



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
        return force_str(
            'BoundFilter <' + \
            ','.join([force_str(repr(self.filter))] + [force_str(repr(arg)) for arg in self.args]) \
            + '>')

    def get_sql_where_params(self):
        return self.filter.get_sql_where_params(*self.args)

    def to_html(self, indent_level=0):
        return string_concat(self.indent(indent_level), self.filter.to_html(*self.args))


class EmptyBoundFilter(BaseBoundFilter):
    def apply_filter_to_query(self, query):
        return query
    def to_html(self, indent_level=0):
        return string_concat(self.indent(indent_level), _('All contacts'))


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
        return string_concat(self.f1.to_html(indent_level+1), '<br>', self.indent(indent_level), _('AND'), '<br>', self.f2.to_html(indent_level+1))


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
        return string_concat(self.f1.to_html(indent_level+1), '<br>', self.indent(indent_level), _('OR'), '<br>', self.f2.to_html(indent_level+1))


@python_2_unicode_compatible
class ContactFieldValue(NgwModel):
    oid = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact, related_name='values')
    contact_field = models.ForeignKey(ContactField, related_name='values')
    value = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_field_value'
        verbose_name = _('contact field value')
        verbose_name_plural = _('contact field values')

    def __repr__(self):
        cf = self.contact_field
        return force_str('ContactFieldValue <%s,%s,%s>' % (force_text(self.contact), force_text(cf), force_text(self)))

    def __str__(self):
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
        verbose_name = _('group in group')
        verbose_name_plural = _('groups in group')

    def __repr__(self):
        return force_str('GroupInGroup <%s %s>' % (self.subgroup_id, self.father_id))


class GroupManageGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    father = models.ForeignKey(ContactGroup, related_name='direct_gmg_subgroups')
    subgroup = models.ForeignKey(ContactGroup, related_name='direct_gmg_supergroups')
    flags = models.IntegerField()
    class Meta:
        db_table = 'group_manage_group'
        verbose_name = _('group managing group')
        verbose_name_plural = _('groups managing group')

    def __repr__(self):
        return force_str('GroupManageGroup <%s %s>' % (self.subgroup_id, self.father_id))


@python_2_unicode_compatible
class ContactInGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact)
    group = models.ForeignKey(ContactGroup)
    flags = models.IntegerField()
    note = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_in_group'
        verbose_name = _('contact in group')
        verbose_name_plural = _('contacts in group')

    def __repr__(self):
        return force_str('ContactInGroup<%s,%s>' % (self.contact_id, self.group_id))

    def __str__(self):
        return _('contact %(contactname)s in group %(groupname)s') % { 'contactname': self.contact.name, 'groupname': self.group.unicode_with_date() }

    @classmethod
    def get_class_navcomponent(cls):
        raise NotImplementedError()

    def get_navcomponent(self):
        return self.contact.get_navcomponent()

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url() + 'members/' + str(self.contact_id) + '/membership'


@python_2_unicode_compatible
class ContactGroupNews(NgwModel):
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(Contact, null=True, blank=True)
    contact_group = models.ForeignKey(ContactGroup, null=True, blank=True)
    date = models.DateTimeField()
    title = models.TextField()
    text = models.TextField()

    class Meta:
        db_table = 'contact_group_news'
        verbose_name = _('news item')
        verbose_name_plural = _('news')
        ordering = '-date',

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url() + 'news/' + str(self.id) + '/'


class ContactMsg(NgwModel):
    id = models.AutoField(primary_key=True)
    cig = models.ForeignKey(ContactInGroup)
    send_date = models.DateTimeField()
    read_date = models.DateTimeField(null=True, blank=True)
    is_answer = models.BooleanField(default=False)
    #subject
    text = models.TextField()
    sync_info = models.TextField(blank=True) # json data for external storage

    class Meta:
        db_table = 'contact_message'
        verbose_name = _('message')
        verbose_name_plural = _('messages')
