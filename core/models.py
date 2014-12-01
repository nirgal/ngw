# Note: You'll have to insert the output of 'manage.py sqlall core'
# into your database.

import os
from datetime import datetime, timedelta
import logging
from collections import OrderedDict
import json
from importlib import import_module
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy, pgettext_lazy
from django.db import models, connection
from django.http import Http404
from django.utils import html
from django.utils import formats
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.hashers import check_password, make_password
from django.contrib import messages
import decoratedstr # Nirgal external package
from ngw.core.nav import Navbar
from ngw.core import perms
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
FIELD_PASSWORD_STATUS = 75
FIELD_DEFAULT_GROUP = 83    # GROUP_USER_NGW

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
        return cls.__name__.lower() + 's'

    def get_urlfragment(self):
        return str(self.id)

    def get_absolute_url(self):
        return self.get_class_absolute_url() + str(self.id) + '/'

    @classmethod
    def get_class_navcomponent(cls):
        return cls.get_class_urlfragment(), cls.get_class_verbose_name_plural()

    def get_navcomponent(self):
        return self.get_urlfragment(), str(self)

    @classmethod
    def get_class_absolute_url(cls):
        return '/' + cls.get_class_urlfragment() + '/'


# Types of change
LOG_ACTION_ADD    = 1
LOG_ACTION_CHANGE = 2
LOG_ACTION_DEL    = 3

class Log(NgwModel):
    id = models.AutoField(primary_key=True)
    dt = models.DateTimeField(ugettext_lazy('Date UTC'), auto_now=True)
    contact = models.ForeignKey('Contact')
    action = models.IntegerField(ugettext_lazy('Action'))
    target = models.TextField()
    target_repr = models.TextField(ugettext_lazy('Target'))
    property = models.TextField(blank=True, null=True)
    property_repr = models.TextField(ugettext_lazy('Property'), blank=True, null=True)
    change = models.TextField(pgettext_lazy('noun', 'Change'), blank=True, null=True)
    class Meta:
        db_table = 'log'
        verbose_name = ugettext_lazy('log')
        verbose_name_plural = ugettext_lazy('logs')
        ordering = '-dt',

    #def __str__(self):
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

    def action_txt(self):
        return {LOG_ACTION_ADD: _('Add'),
                LOG_ACTION_CHANGE: _('Update'),
                LOG_ACTION_DEL: _('Deletion')}[self.action]

class Config(NgwModel):
    id = models.CharField(max_length=32, primary_key=True)
    text = models.TextField(blank=True)
    class Meta:
        db_table = 'config'
        verbose_name = ugettext_lazy('config')
        verbose_name_plural = ugettext_lazy('configs')

    def __str__(self):
        return self.id

    @staticmethod
    def get_object_query_page_length():
        try:
            object_query_page_length = Config.objects.get(pk='query_page_length')
            return int(object_query_page_length.text)
        except (Config.DoesNotExist, ValueError):
            return 200


class Choice(NgwModel):
    oid = models.AutoField(primary_key=True)
    choice_group = models.ForeignKey('ChoiceGroup', related_name='choices')
    key = models.CharField(ugettext_lazy('Key'), max_length=255)
    value = models.CharField(ugettext_lazy('Value'), max_length=255)
    def __str__(self):
        return self.value
    class Meta:
        db_table = 'choice'
        verbose_name = ugettext_lazy('choice')
        verbose_name_plural = ugettext_lazy('choices')
        unique_together = 'choice_group', 'key'


class ChoiceGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(ugettext_lazy('Name'), max_length=255)
    sort_by_key = models.BooleanField(ugettext_lazy('Sort by key'), default=False)
    class Meta:
        db_table = 'choice_group'
        verbose_name = ugettext_lazy('choices list')
        verbose_name_plural = ugettext_lazy('choices lists')
        ordering = 'name',

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


class MyContactManager(BaseUserManager):
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
                                contact_field_id=FIELD_LOGIN,
                                value=name)
        cfv.save()

        cfv = ContactFieldValue(contact_id=contact.id,
                                contact_field_id=FIELD_PASSWORD,
                                value=make_password(password))
        cfv.save()

        cig = ContactInGroup(contact_id=contact.id,
                             group_id=GROUP_ADMIN,
                             flags=perms.MEMBER|perms.OPERATOR)
        cig.save()

    @staticmethod
    def check_login_created(request):
        # Create login for all members of GROUP_USER
        cursor = connection.cursor()
        cursor.execute("SELECT users.contact_id FROM (SELECT DISTINCT contact_in_group.contact_id FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.flags & %(member_flag)s <> 0) AS users LEFT JOIN contact_field_value ON (contact_field_value.contact_id=users.contact_id AND contact_field_value.contact_field_id=%(FIELD_LOGIN)d) WHERE contact_field_value.value IS NULL" % {'member_flag': perms.MEMBER, 'GROUP_USER': GROUP_USER, 'FIELD_LOGIN': FIELD_LOGIN})
        for uid, in cursor:
            contact = Contact.objects.get(pk=uid)
            new_login = contact.generate_login()
            contact.set_fieldvalue(request, FIELD_LOGIN, new_login)
            contact.set_password(Contacts.objects.make_random_password(), request=request)
            messages.add_message(request, messages.SUCCESS, _("Login information generated for User %s.") % contact.name)

        for cfv in ContactFieldValue.objects.extra(where=["contact_field_value.contact_field_id=%(FIELD_LOGIN)d AND NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact_field_value.contact_id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.flags & %(member_flag)s <> 0)" % {'member_flag': perms.MEMBER, 'GROUP_USER': GROUP_USER, 'FIELD_LOGIN': FIELD_LOGIN}]):
            cfv.delete()
            messages.add_message(request, messages.SUCCESS, _("Login information deleted for User %s.") % cfv.contact.name)



class Contact(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(verbose_name=ugettext_lazy('Name'), max_length=255, unique=True)

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
        verbose_name = ugettext_lazy('contact')
        verbose_name_plural = ugettext_lazy('contacts')
        ordering = 'name',

    def __repr__(self):
        return '<Contact %s>' % self.name

    def __str__(self):
        return self.name

    def  is_anonymous():
        '''
        Always returns False. Unlike AnonymousUser.
        See https://docs.djangoproject.com/en/1.5/ref/contrib/auth/#methods
        '''
        return False

    def is_authenticated(self):
        '''
        Always returns True. Unlike AnonymousUser.
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

    def get_visible_directgroups(self, user, wanted_flag):
        """
        Returns the list of groups whose members are visible by user, and that
        contact is a *direct* member of, with the specified flags (invited...).
        """
        return ContactGroup.objects.with_user_perms(user.id, perms.SEE_MEMBERS).extra(
            where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=contact_group.id AND flags & %s <> 0)' % (self.id, wanted_flag)])

    def _get_directgroups_with_flag(self, wanted_flag):
        """
        Returns the list of groups that contact is a *direct* 'wanted_flag'
        of. Like "member of"
        """
        return ContactGroup.objects.extra(where=[
            'EXISTS ('
            ' SELECT * FROM contact_in_group'
            ' WHERE contact_id=%s AND group_id=contact_group.id'
            ' AND flags & %s <> 0)' % (self.id, wanted_flag)])

    def get_directgroups_member(self):
        """
        Returns the list of groups that contact is a direct member of.
        """
        return self._get_directgroups_with_flag(perms.MEMBER)

    def get_directgroups_invited(self):
        """
        Returns the list of groups that contact has been invited to, directly
        without group inheritance
        """
        return self._get_directgroups_with_flag(perms.INVITED)

    def get_directgroups_declined(self):
        """
        Returns the list of groups that contact has been invited to and he
        declined the invitation.
        """
        return self._get_directgroups_with_flag(perms.DECLINED)

    def get_directgroups_operator(self):
        """
        Returns the list of groups that contact is an operator of.
        """
        return self._get_directgroups_with_flag(perms.OPERATOR)

    def get_directgroups_viewer(self):
        """
        Returns the list of groups that contact is an viewer of.
        """
        return self._get_directgroups_with_flag(perms.VIEWER)

    def get_contactfields(self, user_id, writable=False):
        '''
        Returns a queryset with all the fields that self has gained, that is you
        will not get fields that belong to a group is not a member of.
        '''
        # Get all the groups whose fields are readble / writable by user_id
        if writable:
            wanted_perm = perms.WRITE_FIELDS
        else:
            wanted_perm = perms.VIEW_FIELDS
        groups = ContactGroup.objects.with_user_perms(user_id, wanted_perm)
        # Limit to groups with fields
        groups = groups.filter(field_group=True)
        # Also limit to group in wich self is member
        groups = groups.with_member(self.id)
        # The line below should work, but we get an sql compiler alias error:
        #return ContactField.objects.filter(contact_group__in=groups)
        group_ids = [g.id for g in groups]
        #print("group_ids=", group_ids)
        return ContactField.objects.filter(contact_group_id__in=group_ids)

    def get_fieldvalues_by_type(self, type_):
        if isinstance(type_, ContactField):
            type_ = type_.db_type_id
        assert isinstance(type_, str)
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
        return str(cfv)

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
                    log.target = 'Contact ' + str(self.id)
                    log.target_repr = 'Contact ' + self.name
                    log.property = str(field_id)
                    log.property_repr = field.name
                    log.change = 'change from ' + str(cfv)
                    cfv.value = newvalue
                    log.change += ' to ' + str(cfv)
                    cfv.save()
                    log.save()
                    hooks.contact_field_changed(request, field_id, self)
            else:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_DEL
                log.target = 'Contact ' + str(self.id)
                log.target_repr = 'Contact ' + self.name
                log.property = str(field_id)
                log.property_repr = field.name
                log.change = 'old value was ' + str(cfv)
                cfv.delete()
                log.save()
                hooks.contact_field_changed(request, field_id, self)
        except ContactFieldValue.DoesNotExist:
            if newvalue:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'Contact ' + str(self.id)
                log.target_repr = 'Contact ' + self.name
                log.property = str(field_id)
                log.property_repr = field.name
                cfv = ContactFieldValue()
                cfv.contact = self
                cfv.contact_field = field
                cfv.value = newvalue
                cfv.save()
                log.change = 'new value is ' + str(cfv)
                log.save()
                hooks.contact_field_changed(request, field_id, self)


    def get_username(self):
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
            vcf += line('BDAY', str(bday))

        vcf += line('END', 'VCARD')
        return vcf

    def get_addr_semicol(self):
        "Returns address in a form compatible with googlemap query"
        return self.get_fieldvalue_by_id(FIELD_STREET) + ';' + self.get_fieldvalue_by_id(FIELD_POSTCODE) + ';' + self.get_fieldvalue_by_id(FIELD_CITY) + ';' + self.get_fieldvalue_by_id(FIELD_COUNTRY)

    def generate_login(self):
        words = self.name.split(" ")
        login = [w[0].lower() for w in words[:-1]] + [words[-1].lower()]
        login = "".join(login)
        login = decoratedstr.remove_decoration(login)
        def get_logincfv_by_login(ref_uid, login):
            """
            Returns login cfv where loginname=login and not uid!=ref_uid
            This can be evaluated as true if login is already in use by another user
            """
            return ContactFieldValue.objects.filter(contact_field_id=FIELD_LOGIN) \
                                   .filter(value=login) \
                                   .exclude(contact_id=ref_uid)
        if not get_logincfv_by_login(self.id, login):
            return login
        i = 1
        while True:
            altlogin = login + str(i)
            if not get_logincfv_by_login(self.id, altlogin):
                return altlogin
            i += 1

    def set_password(self, newpassword_plain, new_password_status=None, request=None):
        assert request, 'ngw version of set_password needs a request parameter'
        hash = make_password(newpassword_plain)
        self.set_fieldvalue(request, FIELD_PASSWORD, hash)
        if new_password_status is None:
            if self.id == request.user.id:
                self.set_fieldvalue(request, FIELD_PASSWORD_STATUS, '3') # User defined
            else:
                self.set_fieldvalue(request, FIELD_PASSWORD_STATUS, '1') # Generated
        else:
            self.set_fieldvalue(request, FIELD_PASSWORD_STATUS, new_password_status)
        self.save()


    def is_member_of(self, group_id):
        '''
        Return True if self is a member of group group_id, either directly or
        through inheritence.
        '''
        cin = ContactInGroup.objects.filter(contact_id=self.id).extra(where=['flags & %s <> 0' % perms.MEMBER, 'group_id IN (SELECT self_and_subgroups(%s))' % group_id])
        return len(cin) > 0


    def is_directmember_of(self, group_id):
        '''
        Return True if self is a dirrect member of group group_id. Inheritence
        is ignored here.
        '''
        cin = ContactInGroup.objects.filter(contact_id=self.id).extra(where=['flags & %s <> 0' % perms.MEMBER]).filter(group_id=group_id)
        return len(cin) > 0


    def is_admin(self):
        return self.is_member_of(GROUP_ADMIN)

    def can_search_names(self):
        return True
        # TODO
        #return perms.c_can_view_fields_cg(self.id, GROUP_EVERYBODY)

    def can_search_logins(self):
        login_field = ContactField.objects.get(pk=FIELD_LOGIN)
        return perms.c_can_view_fields_cg(self.id, login_field.contact_group_id)

    def update_lastconnection(self):
        # see NgwAuthBackend.authenticate
        cfv, created = ContactFieldValue.objects.get_or_create(contact_id=self.id, contact_field_id=FIELD_LASTCONNECTION)
        cfv.value = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cfv.save()

    def get_customfilters(self):
        '''
        Returns a list of tuples ( filtername, filter_string )
        '''
        field_value = self.get_fieldvalue_by_id(FIELD_FILTERS)
        if not field_value:
            return []

        list = field_value.split(',')
        for idx in range(len(list)-1, 0, -1):
            if list[idx-1][-1] != '"' or list[idx][0] != '"':
                #print("merging elements ", idx-1, "and", idx, "of", repr(list))
                list[idx-1] += ',' + list[idx]
                del list[idx]
        for idx in range(len(list)):
            assert list[idx][0] == '"'
            assert list[idx][-1] == '"'
            list[idx] = list[idx][1:-1]
        assert len(list)%2 == 0
        return [(list[2*i], list[2*i+1]) for i in range(len(list)//2)]


#######################################################################
# ContactGroup
#######################################################################

class ContactGroupQuerySet(models.query.QuerySet):
    def with_user_perms(self, user_id, wanted_flags=None, add_column=True):
        '''
        Returns a ContactGroup QuerySet with a extra colum 'userperms'
        representing the user permissions over the groups as a integer
        '''
        qs = self.extra(
            tables=['v_cig_perm'],
            where=[
                'v_cig_perm.contact_id=%s'%user_id,
                'v_cig_perm.group_id=contact_group.id'],
            )
        if add_column:
            qs = qs.extra(
                select={'userperms': 'v_cig_perm.flags'})

        if wanted_flags is not None:
            qs = qs.extra(where=['v_cig_perm.flags & %s <> 0' % wanted_flags])
        return qs


    def with_member(self, contact_id):
        '''
        Filter the queryset to keep only those whose contact_id is member
        '''
        return self.extra(
            tables=['v_c_member_of'],
            where=[
                'v_c_member_of.contact_id=%s' % contact_id,
                'v_c_member_of.group_id=contact_group.id'],
            )

    def with_counts(self):
        '''
        That function adds columns:
        "message_count" is the total number of messages in that group
        "unread_message_count" is the number of incoming unread messages
        "news_count" is the number of news
        '''
        qs = self
        qs = self.annotate(message_count=models.Count('message_set'))
        qs = qs.extra(select={
            'unread_message_count': 'SELECT COUNT(*) FROM contact_message WHERE is_answer AND read_date IS NULL AND group_id=contact_group.id'})
        qs = qs.annotate(news_count=models.Count('news_set'))
        qs = qs.extra(select={
            'member_count': 'SELECT COUNT(*) FROM v_c_member_of WHERE group_id=contact_group.id'})
        return qs


class ContactGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(ugettext_lazy('Name'), max_length=255)
    description = models.TextField(ugettext_lazy('Description'), blank=True)
    field_group = models.BooleanField(
        ugettext_lazy('Field group'), default=False,
        help_text=ugettext_lazy('Does that group yield specific fields to its members?'))
    date = models.DateField(ugettext_lazy('Date'), null=True, blank=True)
    end_date = models.DateField(ugettext_lazy('End date'), null=True, blank=True,
        help_text=ugettext_lazy('Included. Last day.'))
    budget_code = models.CharField(ugettext_lazy('Budget code'), max_length=10, blank=True)
    system = models.BooleanField(ugettext_lazy('System locked'), default=False)
    mailman_address = models.CharField(
        ugettext_lazy('Mailman address'), max_length=255, blank=True,
        help_text=ugettext_lazy('Mailing list address, if the group is linked to a mailing list.'))
    sticky = models.BooleanField(
        ('Sticky'), default=False,
        help_text=ugettext_lazy('If set, automatic membership because of subgroups becomes permanent. Use with caution.'))
    #direct_supergroups = models.ManyToManyField("self", through='GroupInGroup', symmetrical=False, related_name='none1+')
    #direct_subgroups = models.ManyToManyField("self", through='GroupInGroup', symmetrical=False, related_name='none2+')

    class Meta:
        db_table = 'contact_group'
        verbose_name = ugettext_lazy('contact group')
        verbose_name_plural = ugettext_lazy('contact groups')
        ordering = '-date', 'name'
    objects = ContactGroupQuerySet.as_manager()

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<ContactGroup %s %s>' % (self.id, self.name)

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
            return '/events/' + str(self.id) + '/'
        else:
            return '/contactgroups/' + str(self.id) + '/'


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
            for gig in GroupInGroup.objects.filter(subgroup_id=self.id).extra(
                tables={'v_cig_perm': 'v_cig_perm'},
                where=[
                    'v_cig_perm.contact_id=%s'
                    ' AND v_cig_perm.group_id=group_in_group.father_id'
                    ' AND v_cig_perm.flags & %s <> 0'
                    % (cid, perms.SEE_CG)])]

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


    def get_visible_mananger_groups_ids(self, cid, intflag):
        '''
        Returns a list of groups ids whose members automatically gets "flag"
        priviledges on self, and are visbile contact cid.
        '''
        return [gig.father_id \
            for gig in GroupManageGroup.objects.filter(subgroup_id=self.id).extra(
                tables={'v_cig_perm': 'v_cig_perm'},
                where=[
                    'v_cig_perm.contact_id=%s'
                    ' AND v_cig_perm.group_id=group_manage_group.father_id'
                    ' AND v_cig_perm.flags & %s <> 0'
                    ' AND group_manage_group.flags & %s <> 0'
                    % (cid, intflag, perms.SEE_CG)])]


    def get_manager_groups(self):
        return ContactGroup.objects \
            .filter(direct_gmg_subgroups__subgroup_id=self.id)

    def get_all_members(self):
        return Contact.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.id, perms.MEMBER)])

    def get_members_count(self):
        return self.get_all_members().count()

    def get_contact_perms(self, contact_id):
        '''
        Returns a string will all that group permissions for a given user
        '''
        perm = perms.cig_flags_int(contact_id, self.id)
        return perms.int_to_flags(perm)


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

    def name_with_date(self):
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
    description_not_too_long.short_description = ugettext_lazy('Description')
    description_not_too_long.admin_order_field = 'description'

    def mailman_request_address(self):
        ''' Adds -request before the @ of the address '''
        if self.mailman_address:
            return self.mailman_address.replace('@', '-request@')


    def static_folder(self):
        """ Returns the name of the folder for static files for that group """
        return GROUP_STATIC_DIR + str(self.id)


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
            files = os.listdir(str(folder))
        except OSError as err:
            logging.error(_('Error while reading shared files list in %(folder)s: %(err)s') % {
                'folder': folder,
                'err': err})
            return []

        # probably fixed by python3
        # listdir() returns some data in utf-8, we want everything in unicode:
        #files = [str(file, errors='replace')
        #    for file in files]

        # hide files starting with a dot:
        files = [file for file in files if file[0] != '.']

        files.sort()
        return files


    def get_filters_classes(self):
        return (
            GroupFilterIsMember, GroupFilterIsNotMember,
            GroupFilterIsInvited, GroupFilterIsNotInvited,
            GroupFilterDeclinedInvitation, GroupFilterNotDeclinedInvitation)

    def get_filters(self):
        return [cls(self.id) for cls in self.get_filters_classes()]

    def get_filter_by_name(self, name):
        return [f for f in self.get_filters() if f.__class__.internal_name == name][0]

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

        try:
            cig = ContactInGroup.objects.get(contact_id=contact.id, group_id=self.id)
        except ContactInGroup.DoesNotExist:
            cig = ContactInGroup(contact_id=contact.id, group_id=self.id, flags=0)
            result = LOG_ACTION_ADD
        newflags = cig.flags

        assert group_member_mode and group_member_mode[0] in '+-', 'Invalid membership mode'
        for letter in group_member_mode:
            if letter in '+-':
                operation = letter
                continue

            if operation == '+':
                newflags |= perms.FLAGTOINT[letter]
                for dependency in perms.FLAGDEPENDS[letter]:
                    newflags |= perms.FLAGTOINT[dependency]
                for conflict in perms.FLAGCONFLICTS[letter]:
                    newflags &= ~perms.FLAGTOINT[conflict]
            else:  # operation == '-'
                newflags &= ~perms.FLAGTOINT[letter]
                for flag1, depflag1 in perms.FLAGDEPENDS.items():
                    if letter in depflag1:
                        newflags &= ~perms.FLAGTOINT[flag1]

        if cig.flags ^ newflags & perms.ADMIN_ALL:
            if not perms.c_operatorof_cg(user.id, self.id):
                # You need to be operator to be able to change permissions
                raise PermissionDenied
        if cig.flags ^ newflags & ~perms.ADMIN_ALL:  # m/i/d
            # user needs to be able to add contacts
            # in all subgroups it's not a member yet, including
            # hidden ones
            for sg in self.get_supergroups():
                if not contact.is_directmember_of(sg.id) and not perms.c_can_change_members_cg(user.id, sg.id):
                    raise PermissionDenied

        if newflags == 0:
            if result == LOG_ACTION_ADD:
                # We were about to add the contact in the group: nothing to do
                return 0

            cig.delete()

            log = Log(contact_id=user.id)
            log.action = LOG_ACTION_DEL
            log.target = 'ContactInGroup ' + str(contact.id) + ' ' + str(self.id)
            log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.name_with_date()

            hooks.membership_changed(request, contact, self)

            return LOG_ACTION_CHANGE # FIXME

        if result == LOG_ACTION_ADD:
            log = Log(contact_id=user.id)
            log.action = LOG_ACTION_ADD
            log.target = 'ContactInGroup ' + str(contact.id) + ' ' + str(self.id)
            log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.name_with_date()
        else:
            result = LOG_ACTION_CHANGE

        for flag, intflag in perms.FLAGTOINT.items():
            if cig.flags & intflag and not newflags & intflag:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'ContactInGroup ' + str(contact.id) + ' ' + str(self.id)
                log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.name_with_date()
                log.property = 'membership_' + flag
                log.property_repr = perms.FLAGTOTEXT[flag]
                log.change = 'new value is false'
                log.save()
            if not cig.flags & intflag and newflags & intflag:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = 'ContactInGroup ' + str(contact.id) + ' ' + str(self.id)
                log.target_repr = 'Membership contact ' + contact.name + ' in group ' + self.name_with_date()
                log.property = 'membership_' + flag
                log.property_repr = perms.FLAGTOTEXT[flag]
                log.change = 'new value is true'
                log.save()

        cig.flags = newflags
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
            if len(added_contacts) == 1:
                msg = _('Contact %(contacts)s has been added in %(group)s with status %(status)s.')
            else:
                msg = _('Contact %(contacts)s have been added in %(group)s with status %(status)s.')
            messages.add_message(request, messages.SUCCESS, msg % {
                'contacts': msgpart_contacts,
                'group': self.name_with_date(),
                'status': group_member_mode})
        if changed_contacts:
            msgpart_contacts = ', '.join([c.name for c in changed_contacts])
            if len(changed_contacts) == 1:
                msg = _('Contact %(contacts)s already was in %(group)s. Status has been changed to %(status)s.')
            else:
                msg = _('Contacts %(contacts)s already were in %(group)s. Status has been changed to %(status)s.')
            messages.add_message(request, messages.SUCCESS, msg % {
                'contacts': msgpart_contacts,
                'group': self.name_with_date(),
                'status': group_member_mode})


    def count_messages(self):
        return ContactMsg.objects.filter(group_id=self.id).count()

    def count_unread_messages(self):
        return ContactMsg.objects.filter(group_id=self.id, read_date__isnull=True, is_answer=True).count()


########################################
# Contact Fields

def register_contact_field_type(cls, db_type_id, human_type_id, has_choice):
    ContactField.types_classes[db_type_id] = cls
    cls.db_type_id = db_type_id
    cls.human_type_id = human_type_id
    cls.has_choice = has_choice
    models.signals.post_save.connect(contact_field_saved, cls)
    return cls


class ContactFieldQuerySet(models.query.QuerySet):
    def with_user_perms(self, user_id, writable=False):
        # Note that 1.7 will support *fields in select_related
        if writable:
            wanted_flag = perms.WRITE_FIELDS
        else:
            wanted_flag = perms.VIEW_FIELDS
        qs = self.extra(
            tables=('v_cig_perm',),
            where=[
                'v_cig_perm.contact_id = %s'
                ' AND v_cig_perm.group_id = contact_field.contact_group_id'
                ' AND v_cig_perm.flags & %s <> 0'
                % (user_id, wanted_flag)])
        return qs

    def renumber(self):
        """
        Update all fields sort_weight so that each weight is previous + 10
        """
        new_weigth = 0
        for cf in self.order_by('sort_weight'):
            new_weigth += 10
            cf.sort_weight = new_weigth
            cf.save()


class ContactField(NgwModel):
    # This is a polymorphic class:
    # When it's ready, it's "upgraded" into one of its subclass
    # See polymorphic_upgrade()
    types_classes = {}

    id = models.AutoField(primary_key=True)
    name = models.CharField(ugettext_lazy('Name'), max_length=255)
    hint = models.TextField(ugettext_lazy('Hint'), blank=True)
    type = models.CharField(ugettext_lazy('Type'), max_length=15, default='TEXT')
    contact_group = models.ForeignKey(ContactGroup, verbose_name=ugettext_lazy('Only for'))
    sort_weight = models.IntegerField()
    choice_group = models.ForeignKey(ChoiceGroup, verbose_name=ugettext_lazy('Choice group'), null=True, blank=True)
    system = models.BooleanField(ugettext_lazy('System locked'), default=False)
    default = models.TextField(ugettext_lazy('Default value'), blank=True)
    class Meta:
        db_table = 'contact_field'
        verbose_name = ugettext_lazy('contact field')
        verbose_name_plural = ugettext_lazy('contact fields')
        ordering = 'sort_weight',
    objects = ContactFieldQuerySet.as_manager()

    @classmethod
    def get_class_urlfragment(cls):
        return 'contactfields'

    def __repr__(self):
        return '<ContactField %s %s %s>' % (self.id, self.name, self.type)

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
    type_as_html.short_description = ugettext_lazy('Type')
    type_as_html.admin_order_field = 'type'

    def format_value_text(self, value):
        return value

    def format_value_html(self, value):
        return self.format_value_text(value)

    def get_form_fields(self):
        raise NotImplementedError()

    def formfield_value_to_db_value(self, value):
        return str(value)

    def db_value_to_formfield_value(self, value):
        return value

    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        return True

    def get_filters_classes(self):
        return (FieldFilterNull, FieldFilterNotNull,)

    def get_filters(self):
        return [cls(self.id) for cls in self.get_filters_classes()]

    def get_filter_by_name(self, name):
        return [f for f in self.get_filters() if f.__class__.internal_name == name][0]

    def cached_choices(self):
        try:
            return self._cached_choices
        except AttributeError:
            self._cached_choices = OrderedDict()
            choice_group = self.choice_group
            if not choice_group:
                print("Error: %s doesn't have choices")
            choices = self.choice_group.choices.all()
            for choice in choices:
                self._cached_choices[choice.key] = choice.value
            return self._cached_choices

def contact_field_initialized_by_manager(sender, **kwargs):
    field = kwargs['instance']
    assert field.type is not None, 'Polymorphic abstract class must be created with type defined'
    field.polymorphic_upgrade()
models.signals.post_init.connect(contact_field_initialized_by_manager, ContactField)

def contact_field_saved(**kwargs):
    field = kwargs['instance']
    if field.sort_weight % 10: # To avoid recursion
        ContactField.objects.renumber()
models.signals.post_save.connect(contact_field_saved, ContactField)


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
        params_where = {}
        params_sql = {}
        for k, v in kargs.items():
            #print(k, "=", v)
            auto_param_name = 'autoparam_' + str(len(query.params)) + '_' # resolve conflicts in sucessive calls to apply_where_to_query
            if isinstance(v, str):
                params_where[k] = '%(' + auto_param_name + k + ')s'
                params_sql[auto_param_name+k] = v
            elif isinstance(v, int):
                params_where[k] = v
            else:
                raise Exception('Unsupported type ' + str(type(v)))
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
        return '(contact.name ~* %(value_name1)s OR contact.name ~* %(value_name2)s)', {'value_name1': '^' + value, 'value_name2': ' '+value}
    def to_html(self, value):
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s "%(value)s"' % {
            'fieldname': _('Name'),
            'filtername': self.__class__.human_name,
            'value': value})

    def get_param_types(self):
        return (str,)
NameFilterStartsWith.internal_name = 'startswith'
NameFilterStartsWith.human_name = ugettext_lazy('has a word starting with')

class FieldFilter(Filter):
    """ Helper abstract class for field filters """
    def __init__(self, field_id):
        self.field_id = field_id

class FieldFilterOp0(FieldFilter):
    """ Helper abstract class for field filters that takes no parameter """
    def to_html(self):
        field = ContactField.objects.get(pk=self.field_id)
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s' % {
            'fieldname': html.escape(field.name),
            'filtername': html.escape(self.__class__.human_name)})

class FieldFilterOp1(FieldFilter):
    """ Helper abstract class for field filters that takes 1 parameter """
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        if isinstance(value, str):
            formt = '<b>%(fieldname)s</b> %(filtername)s "%(value)s"'
        else:
            formt = '<b>%(fieldname)s</b> %(filtername)s %(value)s'
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s "%(value)s"' % {
            'fieldname': html.escape(field.name),
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(str(value))})


class FieldFilterStartsWith(FieldFilterOp1):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value1)s OR (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value2)s', {'field_id':self.field_id, 'value1': '^'+value, 'value2': ' '+value}
    def get_param_types(self):
        return (str,)
FieldFilterStartsWith.internal_name = 'startswith'
FieldFilterStartsWith.human_name = ugettext_lazy('has a word starting with')


class FieldFilterEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', {'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (str,)
FieldFilterEQ.internal_name = 'eq'
FieldFilterEQ.human_name = '='


class FieldFilterNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', {'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (str,)
FieldFilterNEQ.internal_name = 'neq'
FieldFilterNEQ.human_name = '≠'


class FieldFilterLE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) <= %(value)s', {'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (str)
FieldFilterLE.internal_name = 'le'
FieldFilterLE.human_name = '≤'


class FieldFilterGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) >= %(value)s', {'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (str,)
FieldFilterGE.internal_name = 'ge'
FieldFilterGE.human_name = '≥'


class FieldFilterLIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) LIKE %(value)s', {'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (str,)
FieldFilterLIKE.internal_name = 'like'
FieldFilterLIKE.human_name = 'SQL LIKE'


class FieldFilterILIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value)s', {'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (str,)
FieldFilterILIKE.internal_name = 'ilike'
FieldFilterILIKE.human_name = 'SQL ILIKE'


class FieldFilterNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', {'field_id':self.field_id}
    def get_param_types(self):
        return ()
FieldFilterNull.internal_name = 'null'
FieldFilterNull.human_name = ugettext_lazy('is undefined')


class FieldFilterNotNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', {'field_id':self.field_id}
    def get_param_types(self):
        return ()
FieldFilterNotNull.internal_name = 'notnull'
FieldFilterNotNull.human_name = ugettext_lazy('is defined')


class FieldFilterIEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int = %(value)i', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterIEQ.internal_name = 'ieq'
FieldFilterIEQ.human_name = '='


class FieldFilterINE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <> %(value)i', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterINE.internal_name = 'ineq'
FieldFilterINE.human_name = '≠'


class FieldFilterILT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int < %(value)i', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterILT.internal_name = 'ilt'
FieldFilterILT.human_name = '<'


class FieldFilterIGT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int > %(value)i', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterIGT.internal_name = 'igt'
FieldFilterIGT.human_name = '>'


class FieldFilterILE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <= %(value)i', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterILE.internal_name = 'ile'
FieldFilterILE.human_name = '≤'


class FieldFilterIGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int >= %(value)i', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterIGE.internal_name = 'ige'
FieldFilterIGE.human_name = '≥'


class FieldFilterAGE_GE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND NOW() - value::DATE > \'%(value)i years\'::INTERVAL )', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterAGE_GE.internal_name = 'agege'
FieldFilterAGE_GE.human_name = ugettext_lazy('Age (years) ≥')


class FieldFilterVALID_GT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', {'field_id':self.field_id, 'value':int(value)}
    def get_param_types(self):
        return (int,)
FieldFilterVALID_GT.internal_name = 'validitygt'
FieldFilterVALID_GT.human_name = ugettext_lazy('date until event ≥')


class FieldFilterFUTURE(FieldFilterOp0):
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )', {'field_id': self.field_id}
    def get_param_types(self):
        return ()
FieldFilterFUTURE.internal_name = 'future'
FieldFilterFUTURE.human_name = ugettext_lazy('In the future')


class FieldFilterChoiceEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return '(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', {'field_id':self.field_id, 'value':value}
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s "%(value)s"' % {
            'fieldname': html.escape(field.name),
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(cfv.value)})
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterChoiceEQ.internal_name = 'ceq'
FieldFilterChoiceEQ.human_name = '='


class FieldFilterChoiceNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', {'field_id':self.field_id, 'value':value}
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s "%(value)s"' % {
            'fieldname': html.escape(field.name),
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(cfv.value)})
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterChoiceNEQ.internal_name = 'cneq'
FieldFilterChoiceNEQ.human_name = '≠'


class FieldFilterMultiChoiceHAS(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', {'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value}
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s "%(value)s"' % {
            'fieldname': html.escape(field.name),
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(cfv.value)})
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHAS.internal_name = 'mchas'
FieldFilterMultiChoiceHAS.human_name = ugettext_lazy('contains')


class FieldFilterMultiChoiceHASNOT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return 'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', {'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value}
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return mark_safe('<b>%(fieldname)s</b> %(filtername)s "%(value)s"' % {
            'fieldname': html.escape(field.name),
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(cfv.value)})
    def get_param_types(self):
        field = ContactField.objects.get(pk=self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHASNOT.internal_name = 'mchasnot'
FieldFilterMultiChoiceHASNOT.human_name = ugettext_lazy("doesn't contain")



class GroupFilterIsMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, perms.MEMBER), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return mark_safe('%(filtername)s <b>%(groupname)s</b>' % {
            'filtername': html.escape(self.__class__.human_name),
            'groupname': html.escape(group.name_with_date())})
    def get_param_types(self):
        return ()
GroupFilterIsMember.internal_name = 'memberof'
GroupFilterIsMember.human_name = ugettext_lazy('is member of group')


class GroupFilterIsNotMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, perms.MEMBER), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return mark_safe('%(filtername)s <b>%(groupname)s</b>' % {
            'filtername': html.escape(self.__class__.human_name),
            'groupname': html.escape(group.name_with_date())})
    def get_param_types(self):
        return ()
GroupFilterIsNotMember.internal_name = 'notmemberof'
GroupFilterIsNotMember.human_name = ugettext_lazy('is not member of group')


class GroupFilterIsInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, perms.INVITED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return mark_safe('%(filtername)s <b>%(groupname)s</b>' % {
            'filtername': html.escape(self.__class__.human_name),
            'groupname': html.escape(group.name_with_date())})
    def get_param_types(self):
        return ()
GroupFilterIsInvited.internal_name = 'ginvited'
GroupFilterIsInvited.human_name = ugettext_lazy('has been invited in group')


class GroupFilterIsNotInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, perms.INVITED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return mark_safe('%(filtername)s <b>%(groupname)s</b>' % {
            'filtername': html.escape(self.__class__.human_name),
            'groupname': html.escape(group.name_with_date())})
    def get_param_types(self):
        return ()
GroupFilterIsNotInvited.internal_name = 'gnotinvited'
GroupFilterIsNotInvited.human_name = ugettext_lazy('has not been invited in group')


class GroupFilterDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, perms.DECLINED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return mark_safe('%(filtername)s <b>%(groupname)s</b>' % {
            'filtername': html.escape(self.__class__.human_name),
            'groupname': html.escape(group.name_with_date())})
    def get_param_types(self):
        return ()
GroupFilterDeclinedInvitation.internal_name = "gdeclined"
GroupFilterDeclinedInvitation.human_name = ugettext_lazy('has declined invitation in group')


class GroupFilterNotDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return 'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (self.group_id, perms.DECLINED), {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return mark_safe('%(filtername)s <b>%(groupname)s</b>' % {
            'filtername': html.escape(self.__class__.human_name),
            'groupname': html.escape(group.name_with_date())})
    def get_param_types(self):
        return ()
GroupFilterNotDeclinedInvitation.internal_name = 'gnotdeclined'
GroupFilterNotDeclinedInvitation.human_name = ugettext_lazy('has not declined invitation in group')


class AllEventsNotReactedSince(Filter):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return 'NOT EXISTS (SELECT * from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %%(date)s AND flags & %s <> 0)' % (perms.MEMBER | perms.DECLINED), {'date':value}
    def to_html(self, value):
        return mark_safe('%(filtername)s "%(value)s"' % {
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(value)})
    def get_param_types(self):
        return (str,) # TODO: Accept date parameters
AllEventsNotReactedSince.internal_name = 'notreactedsince'
AllEventsNotReactedSince.human_name = ugettext_lazy('has not reacted to any invitation since')

class AllEventsReactionYearRatioLess(Filter):
    def get_sql_where_params(self, value):
        return '(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(perms.MEMBER | perms.DECLINED) + ' <> 0) < ' + str(value/100) + ' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(perms.MEMBER | perms.INVITED | perms.DECLINED) + ' <> 0)', {'refdate': (datetime.today() - timedelta(365)).strftime('%Y-%m-%d')}
    def to_html(self, value):
        return mark_safe('%(filtername)s "%(value)s"' % {
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(value)})
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioLess.internal_name = 'yearreactionratioless'
AllEventsReactionYearRatioLess.human_name = ugettext_lazy('1 year invitation reaction percentage less than')

class AllEventsReactionYearRatioMore(Filter):
    def get_sql_where_params(self, value):
        return '(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(perms.MEMBER | perms.DECLINED) + ' <> 0) > ' + str(value/100) + ' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND flags & ' + str(perms.MEMBER | perms.INVITED | perms.DECLINED) + ' <> 0)', {'refdate': (datetime.today() - timedelta(365)).strftime('%Y-%m-%d')}
    def to_html(self, value):
        return mark_safe('%(filtername)s "%(value)s"' % {
            'filtername': html.escape(self.__class__.human_name),
            'value': html.escape(value)})
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioMore.internal_name = 'yearreactionratiomore'
AllEventsReactionYearRatioMore.human_name = ugettext_lazy('1 year invitation reaction percentage more than')



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
        super().__init__()
        self.filter = filter
        self.args = args

    def __repr__(self):
        return '<BoundFilter ' + \
               ','.join([repr(self.filter)] + [repr(arg) for arg in self.args]) \
               + '>'

    def get_sql_where_params(self):
        return self.filter.get_sql_where_params(*self.args)

    def to_html(self, indent_level=0):
        return mark_safe(self.indent(indent_level) + self.filter.to_html(*self.args))


class EmptyBoundFilter(BaseBoundFilter):
    def apply_filter_to_query(self, query):
        return query
    def to_html(self, indent_level=0):
        return mark_safe(self.indent(indent_level) + _('All contacts'))


class AndBoundFilter(BaseBoundFilter):
    def __init__(self, *subfilters):
        super().__init__()
        self.subfilters = subfilters
    def get_sql_query_where(self, query, *args, **kargs):
        wheres = []
        for subfilter in self.subfilters:
            query, newwhere = subfilter.get_sql_query_where(query)
            wheres.append(newwhere)
        wherestr = '((' + ') AND ('.join(where for where in wheres) + '))'
        return query, wherestr
    def to_html(self, indent_level=0):
        html = ''
        for subfilter in self.subfilters:
            if html:
                html += '<br>'
                html += self.indent(indent_level)
                html += _('AND')
                html += '<br>'
            html += subfilter.to_html(indent_level+1)
        return mark_safe(html)


class OrBoundFilter(BaseBoundFilter):
    def __init__(self, *subfilters):
        super().__init__()
        self.subfilters = subfilters
    def get_sql_query_where(self, query, *args, **kargs):
        wheres = []
        for subfilter in self.subfilters:
            query, newwhere = subfilter.get_sql_query_where(query)
            wheres.append(newwhere)
        wherestr = '((' + ') OR ('.join(where for where in wheres) + '))'
        return query, wherestr
    def to_html(self, indent_level=0):
        html = ''
        for subfilter in self.subfilters:
            if html:
                html += '<br>'
                html += self.indent(indent_level)
                html += _('OR')
                html += '<br>'
            html += subfilter.to_html(indent_level+1)
        return mark_safe(html)


class ContactFieldValue(NgwModel):
    oid = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact, related_name='values')
    contact_field = models.ForeignKey(ContactField, related_name='values')
    value = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_field_value'
        verbose_name = ugettext_lazy('contact field value')
        verbose_name_plural = ugettext_lazy('contact field values')

    def __repr__(self):
        cf = self.contact_field
        return '<ContactFieldValue %s %s %s>' % (self.contact, cf, self)

    def __str__(self):
        cf = self.contact_field
        return cf.format_value_text(self.value)

    def as_html(self):
        cf = self.contact_field
        return cf.format_value_html(self.value)


class GroupInGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    father = models.ForeignKey(ContactGroup, related_name='direct_gig_subgroups')
    subgroup = models.ForeignKey(ContactGroup, related_name='direct_gig_supergroups')
    class Meta:
        db_table = 'group_in_group'
        verbose_name = ugettext_lazy('group in group')
        verbose_name_plural = ugettext_lazy('groups in group')

    def __repr__(self):
        return '<GroupInGroup %s %s>' % (self.subgroup_id, self.father_id)


class GroupManageGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    father = models.ForeignKey(ContactGroup, related_name='direct_gmg_subgroups')
    subgroup = models.ForeignKey(ContactGroup, related_name='direct_gmg_supergroups')
    flags = models.IntegerField()
    class Meta:
        db_table = 'group_manage_group'
        verbose_name = ugettext_lazy('group managing group')
        verbose_name_plural = ugettext_lazy('groups managing group')

    def __repr__(self):
        return '<GroupManageGroup %s %s>' % (self.subgroup_id, self.father_id)


class ContactInGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact)
    group = models.ForeignKey(ContactGroup)
    flags = models.IntegerField()
    note = models.TextField(blank=True)
    class Meta:
        db_table = 'contact_in_group'
        verbose_name = ugettext_lazy('contact in group')
        verbose_name_plural = ugettext_lazy('contacts in group')

    def __repr__(self):
        return '<ContactInGroup %s %s>' % (self.contact_id, self.group_id)

    def __str__(self):
        return _('contact %(contactname)s in group %(groupname)s') % {'contactname': self.contact.name, 'groupname': self.group.name_with_date()}

    @classmethod
    def get_class_navcomponent(cls):
        raise NotImplementedError()

    def get_navcomponent(self):
        return self.contact.get_navcomponent()

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url() + 'members/' + str(self.contact_id) + '/membership'


class ContactGroupNews(NgwModel):
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(Contact, null=True, blank=True)
    contact_group = models.ForeignKey(ContactGroup, null=True, blank=True, related_name='news_set')
    date = models.DateTimeField()
    title = models.CharField(ugettext_lazy('title'), max_length=64)
    text = models.TextField(ugettext_lazy('text'))

    class Meta:
        db_table = 'contact_group_news'
        verbose_name = ugettext_lazy('news item')
        verbose_name_plural = ugettext_lazy('news')
        ordering = '-date',

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url() + 'news/' + str(self.id) + '/'


class ContactMsgManager(models.Manager):
    known_backends = {}
    def get_backend_by_name(self, name):
        if name not in self.known_backends:
            backend = import_module(name)
            self.known_backends[name] = backend
        return self.known_backends[name]

class ContactMsg(NgwModel):
    id = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact, verbose_name=ugettext_lazy('Contact'))
    group = models.ForeignKey(ContactGroup, related_name='message_set')
    send_date = models.DateTimeField()
    read_date = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(Contact, null=True, related_name='msgreader')
    is_answer = models.BooleanField(default=False)
    subject = models.CharField(ugettext_lazy('Subject'), max_length=64)
    text = models.TextField()
    sync_info = models.TextField(blank=True) # json data for external storage

    class Meta:
        db_table = 'contact_message'
        verbose_name = ugettext_lazy('message')
        verbose_name_plural = ugettext_lazy('messages')
        ordering = '-send_date',
    objects = ContactMsgManager()

    def nice_date(self):
        return formats.date_format(self.send_date, 'DATETIME_FORMAT')
    nice_date.short_description = ugettext_lazy('Date UTC')
    nice_date.admin_order_field = 'send_date'

    def get_absolute_url(self):
        return self.group.get_absolute_url() + 'messages/' + str(self.id)

    get_link_subject = get_absolute_url

    def nice_flags(self):
        if self.sync_info:
            sync_info = json.loads(self.sync_info)
        else:
            sync_info = {}

        result = ''
        if self.is_answer:
            result += '<span title="%s">⬅</span>' % _('Received')
            if self.read_date:
                result += '<span style="color:green;" title="%s">✉</span>' % _('Read')
            else:
                result += '<span style="color:red;" title="%s">✉</span>' % _('Unread')
        else:
            result += '<span title="%s">➡</span>' % _('Sent')

            if 'otid' in sync_info:
                if 'deleted' not in sync_info:
                    result += '<span style="color:green;" title="%s">⛁</span>' % _('Stored externally')
                else:
                    result += '<span style="color:red;" title="%s">⛁</span>' % _('External storage expired')
            else:
                result += '<span style="color:red;" title="%s">⛁</span>' % _('Not stored externally')

            if 'email_sent' in sync_info:
                if self.read_date:
                    result += '<span style="color:green;" title="%s">✉</span>' % _('Notification sent and read')
                else:
                    result += '<span style="color:red;" title="%s">✉</span>' % _('Notification sent but unread')
        return mark_safe(result)
    nice_flags.short_description = ugettext_lazy('Flags')

    def get_backend(self):
        '''
        Returns the backend python module for that message
        '''
        sync_info = json.loads(self.sync_info)
        backend_name = sync_info['backend']
        return ContactMsg.objects.get_backend_by_name(backend_name)

    def get_related_messages(self):
        '''
        Find the list of related messages, delegating the question to the
        matching backend.
        '''
        backend = self.get_backend()
        func_name = 'get_related_messages'
        try:
            func = getattr(backend, func_name)
        except AttributeError:
            return ()
        return func(self)
