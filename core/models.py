# -*- encoding: utf-8 -*-
#
# Also note: You'll have to insert the output of 'manage.py sqlall core'
# into your database.

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
GROUP_USER = 2      # With login & password
GROUP_ADMIN = 8
GROUP_USER_NGW = 52
GROUP_USER_PHPBB = 53

FIELD_LOGIN = 1
FIELD_PASSWORD = 2
FIELD_LASTCONNECTION = 3
FIELD_COLUMNS = 4
FIELD_FILTERS = 5

FIELD_BIRTHDAY = 6
FIELD_EMAIL = 7
FIELD_STREET = 9
FIELD_POSTCODE = 11
FIELD_CITY = 14
FIELD_COUNTRY = 48
FIELD_PHPBB_USERID = 73
FIELD_PASSWORD_PLAIN = 74
FIELD_PASSWORD_STATUS = 75

AUTOMATIC_MEMBER_INDICATOR = u"⁂"


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
        return unicode(cls.__name__.lower(), "utf8")+u"s"

    def get_urlfragment(self):
        return unicode(self.id)

    @classmethod
    def get_class_navcomponent(cls):
        return cls.get_class_urlfragment(), cls.get_class_verbose_name_plural()

    def get_navcomponent(self):
        return self.get_urlfragment(), unicode(self)

    @classmethod
    def get_class_absolute_url(cls):
        return u"/"+cls.get_class_urlfragment()+u"/"

    def get_absolute_url(self):
        return self.get_class_absolute_url()+unicode(self.id)+u"/"

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
        db_table = u'log'

    #def __unicode__(self):
    #    return u"%(date)s: %(contactname)s %(type_and_data)s"% {
    #            u'date': self.dt.isoformat(),
    #            u'contactname': self.contact.name,
    #            u'action_and_data': self.action_and_data(),
    #            }
    #
    #def action_and_data(self):
    #    if self.action==LOG_ACTION_CHANGE:
    #        return u"%(property)s %(target)s: %(change)s"% {
    #            u'target': self.target_repr,
    #            u'property': self.property_repr,
    #            u'change': self.change,
    #            }

    def small_date(self):
        return self.dt.strftime('%Y-%m-%d %H:%M:%S')

    def action_txt(self):
        return { LOG_ACTION_ADD: u"Add",
                 LOG_ACTION_CHANGE: u"Update",
                 LOG_ACTION_DEL: u"Delete"}[self.action]


class Config(NgwModel):
    id = models.CharField(max_length=32, primary_key=True)
    text = models.TextField(blank=True)
    def __unicode__(self):
        return self.id
    class Meta:
        db_table = u'config'


class Choice(NgwModel):
    oid = models.AutoField(primary_key=True)
    choice_group = models.ForeignKey('ChoiceGroup', related_name='choices')
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    def __unicode__(self):
        return self.value
    class Meta:
        db_table = u'choice'

class ChoiceGroup(NgwModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=True)
    sort_by_key = models.BooleanField()
    class Meta:
        db_table = u'choice_group'
        verbose_name = u"choices list"

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
        db_table = u'contact'

    def __repr__(self):
        return 'Contact <'+self.name.encode('utf-8')+'>'

    def __unicode__(self):
        return self.name

    def is_authenticated(self):
        return True

    #get_link_name=NgwModel.get_absolute_url
    def name_with_relative_link(self):
        return u"<a href=\"%(id)d/\">%(name)s</a>" % { 'id': self.id, 'name': html.escape(self.name) }


    def get_directgroups_member(self):
        "returns the list of groups that contact is a direct member of."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND member)' % self.id])

    def get_allgroups_member(self):
        "returns the list of groups that contact is a member of."
        return ContactGroup.objects.extra(where=['id IN (SELECT self_and_supergroups(group_id) FROM contact_in_group WHERE contact_id=%s AND member)' % self.id])

    def get_directgroups_invited(self):
        "returns the list of groups that contact has been invited to."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND invited)' % self.id])

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
        "returns the list of groups that contact has been invited to."
        return ContactGroup.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=%s AND group_id=id AND declined_invitation)' % self.id])

    def get_allgroups_withfields(self):
        "returns the list of groups with field_group ON that contact is member of."
        return self.get_allgroups_member().filter(field_group=True)

    def get_allfields(self):
        contactgroupids = [ g.id for g in self.get_allgroups_withfields() ]
        #print "contactgroupids=", contactgroupids
        return ContactField.objects.filter(contact_group_id__in = contactgroupids).order_by('sort_weight')

    def get_fieldvalues_by_type(self, type_):
        if issubclass(type_, ContactField):
            type_ = type_.db_type_id
        assert type_.__class__ == unicode
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
            return u""
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
                    log.target = u"Contact "+unicode(self.id)
                    log.target_repr = u"Contact "+self.name
                    log.property = unicode(field_id)
                    log.property_repr = field.name
                    log.change = u"change from "+unicode(cfv)
                    cfv.value = newvalue
                    log.change += u" to "+unicode(cfv)
                    cfv.save()
                    log.save()
                    hooks.contact_field_changed(user, field_id, self)
            else:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_DEL
                log.target = u"Contact "+unicode(self.id)
                log.target_repr = u"Contact "+self.name
                log.property = unicode(field_id)
                log.property_repr = field.name
                log.change = u"old value was "+unicode(cfv)
                cfv.delete()
                log.save()
                hooks.contact_field_changed(user, field_id, self)
        except ContactFieldValue.DoesNotExist:
            if newvalue:
                log = Log(contact_id=user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u"Contact "+unicode(self.id)
                log.target_repr = u"Contact "+self.name
                log.property = unicode(field_id)
                log.property_repr = field.name
                cfv = ContactFieldValue()
                cfv.contact = self
                cfv.contact_field = field
                cfv.value = newvalue
                cfv.save()
                log.change = u"new value is "+unicode(cfv)
                log.save()
                hooks.contact_field_changed(user, field_id, self)


    def get_login(self):
        # See templates/contact_detail.htm
        return self.get_fieldvalue_by_id(FIELD_LOGIN)

    def vcard(self):
        # http://www.ietf.org/rfc/rfc2426.txt
        vcf = u""
        def line(key, value):
            value = value.replace("\\", "\\\\")
            value = value.replace("\r", "")
            value = value.replace("\n", "\\n")
            return key+":"+value+"\r\n"
        vcf += line(u"BEGIN", u"VCARD")
        vcf += line(u"VERSION", u"3.0")
        vcf += line(u"FN", self.name)
        vcf += line(u"N", self.name)


        street = self.get_fieldvalue_by_id(FIELD_STREET)
        postal_code = self.get_fieldvalue_by_id(FIELD_POSTCODE)
        city = self.get_fieldvalue_by_id(FIELD_CITY)
        country = self.get_fieldvalue_by_id(FIELD_COUNTRY)
        vcf += line(u"ADR", u";;"+street+u";"+city+u";;"+postal_code+u";"+country)

        for phone in self.get_fieldvalues_by_type('PHONE'):
            vcf += line(u"TEL", phone)

        for email in self.get_fieldvalues_by_type('EMAIL'):
            vcf += line(u"EMAIL", email)

        bday = self.get_fieldvalue_by_id(FIELD_BIRTHDAY)
        if bday:
            vcf += line(u"BDAY", unicode(bday))

        vcf += line(u"END", u"VCARD")
        return vcf

    def get_addr_semicol(self):
        "Returns address in a form compatible with googlemap query"
        return self.get_fieldvalue_by_id(FIELD_STREET)+u";"+self.get_fieldvalue_by_id(FIELD_POSTCODE)+u";"+self.get_fieldvalue_by_id(FIELD_CITY)+u";"+self.get_fieldvalue_by_id(FIELD_COUNTRY)

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
                self.set_fieldvalue(user, FIELD_PASSWORD_STATUS, u'3') # User defined
            else:
                self.set_fieldvalue(user, FIELD_PASSWORD_STATUS, u'1') # Generated
        else:
            self.set_fieldvalue(user, FIELD_PASSWORD_STATUS, new_password_status)


    @staticmethod
    def check_login_created(logged_contact):
        # Create login for all members of GROUP_USER
        cursor = connection.cursor()
        cursor.execute("SELECT users.contact_id FROM (SELECT DISTINCT contact_in_group.contact_id FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.member) AS users LEFT JOIN contact_field_value ON (contact_field_value.contact_id=users.contact_id AND contact_field_value.contact_field_id=%(FIELD_LOGIN)d) WHERE contact_field_value.value IS NULL" % {"GROUP_USER":GROUP_USER, "FIELD_LOGIN":FIELD_LOGIN})
        for uid, in cursor:
            contact = Contact.objects.get(pk=uid)
            new_login = contact.generate_login()
            contact.set_fieldvalue(logged_contact, FIELD_LOGIN, new_login)
            contact.set_password(logged_contact, contact.generate_password())
            logged_contact.push_message("Login information generated for User %s."%(contact.name))

        for cfv in ContactFieldValue.objects.extra(where=["contact_field_value.contact_field_id=%(FIELD_LOGIN)d AND NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact_field_value.contact_id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.member)"%{"GROUP_USER":GROUP_USER, "FIELD_LOGIN":FIELD_LOGIN}]):
            cfv.delete()
            logged_contact.push_message("Delete login information for User %s."%(cfv.contact.name))

    def is_member_of(self, group_id):
        cin = ContactInGroup.objects.filter(contact_id=self.id, member=True).extra(where=['group_id IN (SELECT self_and_subgroups(%s))' % group_id])
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
        db_table = u'contact_group'

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return 'ContactGroup<'+str(self.id)+self.name.encode('utf-8')+'>'

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
            return '/events/'+unicode(self.id)+u"/"
        else:
            return self.get_class_absolute_url()+unicode(self.id)+u"/"


    def get_direct_supergroups_ids(self):
        return [gig.father_id for gig in GroupInGroup.objects.filter(subgroup_id=self.id)]

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


#    def get_direct_members(self):
#        cigs = Query(ContactInGroup).filter(and_(ContactInGroup.group_id==self.id, ContactInGroup.member==True))
#        cids = [ cig.contact_id for cig in cigs ]
#        return Query(Contact).filter(Contact.id.in_(cids))
#
#    def get_direct_invited(self):
#        cigs = Query(ContactInGroup).filter(and_(ContactInGroup.group_id==self.id, ContactInGroup.invited==True))
#        cids = [ cig.contact_id for cig in cigs ]
#        return Query(Contact).filter(Contact.id.in_(cids))
#
#    #    s = select([contact_in_group_table.c.contact_id], and_(contact_in_group_table.c.group_id.in_(gids), contact_in_group_table.c.member==True)).distinct()
#    #    #print "members=", s, ":"
#    #    result =  []
#    #    for cid in Session.execute(s):
#    #        result.append(Query(Contact).get(cid[0]))
#    #        #print cid[0]
#    #    return result

#    def get_members_query(self):
#        #TODO optimize me
#        gids = [ g.id for g in self.self_and_subgroups ]
#        return Query(Contact).filter(ContactInGroup.contact_id==Contact.id).filter(ContactInGroup.group_id.in_(gids)).filter(ContactInGroup.member==True)

    def get_all_members(self):
        return Contact.objects.extra(where=['EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND member)' % self.id])
#    members = property(get_members)


    def get_link_name(self):
        "Name will then be clickable in the list"
        return self.get_absolute_url()

    def supergroups_includinghtml(self):
        sgs = self.get_supergroups()
        if not sgs:
            return u""
        return u" (implies "+u", ".join(['<a href="'+g.get_absolute_url()+'">'+html.escape(g.name)+'</a>' for g in sgs])+u")"

    def subgroups_includinghtml(self):
        sgs = self.get_subgroups()
        if not sgs:
            return u""
        return u" (including "+u", ".join(['<a href="'+g.get_absolute_url()+'">'+html.escape(g.name)+'</a>' for g in sgs])+u")"

    # See group_add_contacts_to.html
    def is_event(self):
        return self.date is not None

    def html_date(self):
        if self.date:
            return ngw_date_format(self.date)
        else:
            return u''

    def unicode_with_date(self):
        """ Returns the name of the group, and the date if there's one"""
        result = self.name
        if self.date:
            result += u' ‧ '+ngw_date_format(self.date)
        return result

    def mailman_request_address(self):
        ''' Adds -request before the @ of the address '''
        if self.mailman_address:
            return self.mailman_address.replace(u'@', u'-request@')


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
            print "Creating missing directory for group %i" % self.id
            os.mkdir(dirname)
        htaccess_path = os.path.join(dirname, ".htaccess")
        if not os.path.isfile(htaccess_path):
            print "Creating missing .htaccess file for group %i" % self.id
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
        #print q.query
        return q

    def get_default_display(self):
        if not self.date:
            return u'mg'
        if self.date > datetime.utcnow().date():
            return u'mig'
        else:
            return u'mg'


    def set_member_1(self, logged_contact, contact, group_member_mode):
        """
        group_member_mode is a combinaison of letters 'mido'
        if it starts with '+', the mode will be added (dropping incompatible ones).
        Example '+o' actually means '+m-id+o'
                '+d' actually means '-mi+d-o'
        if it starst with '-', the mode will be deleted
        TODO enforce that:
        m/i/d are mutually exclusive
        o require m
        returns
        LOG_ACTION_ADD if added
        LOG_ACTION_CHANGE if changed
        LOG_ACTION_DEL if deleted
        0 other wise
        If the contact was not in the group, it will be added.
        """

        result = 0

        add_mode = set()
        del_mode = set()

        if group_member_mode and group_member_mode[0] in u'+-':
            for letter in group_member_mode:
                if letter in u'+-':
                    operation = letter
                elif letter == u'm':
                    if operation == u'+':
                        add_mode.add(u'm')
                        del_mode.discard(u'm')
                        add_mode.discard(u'i')
                        del_mode.add(u'i')
                        add_mode.discard(u'd')
                        del_mode.add(u'd')
                    else: # operation == u'-'
                        add_mode.discard(u'm')
                        del_mode.add(u'm')
                        add_mode.discard(u'o')
                        del_mode.add(u'o')
                elif letter == u'i':
                    if operation == u'+':
                        add_mode.discard(u'm')
                        del_mode.add(u'm')
                        add_mode.add(u'i')
                        del_mode.discard(u'i')
                        add_mode.discard(u'd')
                        del_mode.add(u'd')
                        add_mode.discard(u'o')
                        del_mode.add(u'o')
                    else: # operation == u'-'
                        add_mode.discard(u'i')
                        del_mode.add(u'i')
                elif letter == u'd':
                    if operation == u'+':
                        add_mode.discard(u'm')
                        del_mode.add(u'm')
                        add_mode.discard(u'i')
                        del_mode.add(u'i')
                        add_mode.add(u'd')
                        del_mode.discard(u'd')
                        add_mode.discard(u'o')
                        del_mode.add(u'o')
                    else: # operation == u'-'
                        add_mode.discard(u'd')
                        del_mode.add(u'd')
                elif letter == u'o':
                    if operation == u'+':
                        add_mode.add(u'm')
                        del_mode.discard(u'm')
                        add_mode.discard(u'i')
                        del_mode.add(u'i')
                        add_mode.discard(u'd')
                        del_mode.add(u'd')
                        add_mode.add(u'o')
                        del_mode.discard(u'o')
                    else: # operation == u'-'
                        add_mode.discard(u'o')
                        del_mode.add(u'o')

        else:
            # set mode, no + nor -
            if u'+' in group_member_mode or u'-' in group_member_mode:
                raise ValueError("Can't set mode %s" % group_member_mode)
            if u'm' in group_member_mode:
                if u'i' in group_member_mode or u'd' in group_member_mode:
                    raise ValueError("Can't set mode %s" % group_member_mode)
                add_mode.add(u'm')
                del_mode.add(u'i')
                del_mode.add(u'd')
            if u'i' in group_member_mode:
                if u'm' in group_member_mode or u'd' in group_member_mode or u'o' in group_member_mode:
                    raise ValueError("Can't set mode %s" % group_member_mode)
                del_mode.add(u'm')
                add_mode.add(u'i')
                del_mode.add(u'd')
                del_mode.add(u'o')
            if u'd' in group_member_mode:
                if u'm' in group_member_mode or u'i' in group_member_mode or u'o' in group_member_mode:
                    raise ValueError("Can't set mode %s" % group_member_mode)
                del_mode.add(u'm')
                del_mode.add(u'i')
                add_mode.add(u'd')
                del_mode.add(u'o')
            if u'o' in group_member_mode:
                if u'i' in group_member_mode or u'd' in group_member_mode:
                    raise ValueError("Can't set mode %s" % group_member_mode)
                add_mode.add(u'm')
                del_mode.add(u'i')
                del_mode.add(u'd')
                add_mode.add(u'o')

        try:
            cig = ContactInGroup.objects.get(contact_id=contact.id, group_id=self.id)
        except ContactInGroup.DoesNotExist:
            if not add_mode:
                return result # 0 = no change

            cig = ContactInGroup(contact_id=contact.id, group_id=self.id)
            log = Log(contact_id=logged_contact.id)
            log.action = LOG_ACTION_ADD
            log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
            log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
            log.save()
            result = LOG_ACTION_ADD

        #print "ok +", add_mode, "-", del_mode
        if u'm' in add_mode:
            if not cig.member:
                cig.member = True
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'member'
                log.property_repr = u'Member'
                log.change = u'new value is true'
                log.save()
                result = result or LOG_ACTION_CHANGE
        if u'm' in del_mode:
            if cig.member:
                cig.member = False
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'member'
                log.property_repr = u'Member'
                log.change = u'new value is false'
                log.save()
                result = result or LOG_ACTION_CHANGE

        if u'i' in add_mode:
            if not cig.invited:
                cig.invited = True
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'invited'
                log.property_repr = u'Invited'
                log.change = u'new value is true'
                log.save()
                result = result or LOG_ACTION_CHANGE
        if u'i' in del_mode:
            if cig.invited:
                cig.invited = False
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'invited'
                log.property_repr = u'Invited'
                log.change = u'new value is false'
                log.save()
                result = result or LOG_ACTION_CHANGE

        if u'd' in add_mode:
            if not cig.declined_invitation:
                cig.declined_invitation = True
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'declined_invitation'
                log.property_repr = u'Declined invitation'
                log.change = u'new value is true'
                log.save()
                result = result or LOG_ACTION_CHANGE
        if u'd' in del_mode:
            if cig.declined_invitation:
                cig.declined_invitation = False
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'declined_invitation'
                log.property_repr = u'Declined invitation'
                log.change = u'new value is false'
                log.save()
                result = result or LOG_ACTION_CHANGE

        if u'o' in add_mode:
            if not cig.operator:
                cig.operator = True
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'operator'
                log.property_repr = u'Operator'
                log.change = u'new value is true'
                log.save()
                result = result or LOG_ACTION_CHANGE
        if u'o' in del_mode:
            if cig.operator:
                cig.operator = False
                log = Log(contact_id=logged_contact.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
                log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
                log.property = u'operator'
                log.property_repr = u'Operator'
                log.change = u'new value is false'
                log.save()
                result = result or LOG_ACTION_CHANGE

        if not cig.member and not cig.invited and not cig.declined_invitation:
            cig.delete()
            log = Log(contact_id=logged_contact.id)
            log.action = LOG_ACTION_DEL
            log.target = u'ContactInGroup '+unicode(contact.id)+u' '+unicode(self.id)
            log.target_repr = u'Membership contact '+contact.name+u' in group '+self.unicode_with_date()
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
            msgpart_contacts = u', '.join([c.name for c in added_contacts])
            if len(added_contacts)==1:
                msg = u'Contact %s has been added in %s with status %s.'
            else:
                msg = u'Contacts %s have been added in %s with status %s.'
            logged_contact.push_message(msg % (msgpart_contacts, self.unicode_with_date(), group_member_mode))
        if changed_contacts:
            msgpart_contacts = u', '.join([c.name for c in changed_contacts])
            if len(changed_contacts)==1:
                msg = u'Contact %s allready was in %s. Status has been changed to %s.'
            else:
                msg = u'Contacts %s allready were in %s. Status have been changed to %s.'
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
        db_table = u'contact_field'
        ordering = 'sort_weight',

    @classmethod
    def get_class_absolute_url(cls):
        return u"/contactfields/"

    def __repr__(self):
        return "ContactField<"+str(self.id)+","+self.name.encode('utf8')+','+self.type.encode('utf8')+">"

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
    assert field.type is not None, u"Polymorphic abstract class must be created with type defined"
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
            #print k,"=",v
            auto_param_name = u"autoparam_"+unicode(len(query.params))+u"_" # resolve conflicts in sucessive calls to apply_where_to_query
            if isinstance(v, unicode):
                params_where[ k ] = u'%('+auto_param_name+k+u')s'
                params_sql[ auto_param_name+k ] = v
            elif isinstance(v, int):
                params_where[ k ] = v
            else:
                raise Exception(u"Unsupported type "+unicode(type(v)))
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
        return u'(contact.name ~* %(value_name1)s OR contact.name ~* %(value_name2)s)', { 'value_name1':u"^"+value, 'value_name2':u" "+value }
    def to_html(self, value):
        return u"<b>Name</b> "+self.__class__.human_name+u" \""+unicode(value)+u"\""

    def get_param_types(self):
        return (unicode,)
NameFilterStartsWith.internal_name = "startswith"
NameFilterStartsWith.human_name = u"has a word starting with"

class FieldFilter(Filter):
    """ Helper abstract class for field filters """
    def __init__(self, field_id):
        self.field_id = field_id

class FieldFilterOp0(FieldFilter):
    """ Helper abstract class for field filters that takes no parameter """
    def to_html(self):
        field = ContactField.objects.get(pk=self.field_id)
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name

class FieldFilterOp1(FieldFilter):
    """ Helper abstract class for field filters that takes 1 parameter """
    def to_html(self, value):
        field = ContactField.objects.get(pk=self.field_id)
        result = u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" "
        if isinstance(value, unicode):
            value = u'"'+value+u'"'
        else:
            value = unicode(value)
        return result+value


class FieldFilterStartsWith(FieldFilterOp1):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value1)s OR (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value2)s', { 'field_id':self.field_id, 'value1':u"^"+value, 'value2':u" "+value}
    def get_param_types(self):
        return (unicode,)
FieldFilterStartsWith.internal_name = "startswith"
FieldFilterStartsWith.human_name = u"has a word starting with"


class FieldFilterEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (unicode,)
FieldFilterEQ.internal_name = "eq"
FieldFilterEQ.human_name = u"="


class FieldFilterNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterNEQ.internal_name = "neq"
FieldFilterNEQ.human_name = u"≠"


class FieldFilterLE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) <= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterLE.internal_name = "le"
FieldFilterLE.human_name = u"≤"


class FieldFilterGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) >= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterGE.internal_name = "ge"
FieldFilterGE.human_name = u"≥"


class FieldFilterLIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) LIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterLIKE.internal_name = "like"
FieldFilterLIKE.human_name = u"SQL LIKE"


class FieldFilterILIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterILIKE.internal_name = "ilike"
FieldFilterILIKE.human_name = u"SQL ILIKE"


class FieldFilterNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNull.internal_name = "null"
FieldFilterNull.human_name = u"is undefined"


class FieldFilterNotNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return u'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNotNull.internal_name = "notnull"
FieldFilterNotNull.human_name = u"is defined"


class FieldFilterIEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int = %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIEQ.internal_name = "ieq"
FieldFilterIEQ.human_name = u"="


class FieldFilterINE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <> %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterINE.internal_name = "ineq"
FieldFilterINE.human_name = u"≠"


class FieldFilterILT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int < %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterILT.internal_name = "ilt"
FieldFilterILT.human_name = u"<"


class FieldFilterIGT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int > %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIGT.internal_name = "igt"
FieldFilterIGT.human_name = u">"


class FieldFilterILE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <= %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterILE.internal_name = "ile"
FieldFilterILE.human_name = u"≤"


class FieldFilterIGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int >= %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIGE.internal_name = "ige"
FieldFilterIGE.human_name = u"≥"


class FieldFilterAGE_GE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND NOW() - value::DATE > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterAGE_GE.internal_name = "agege"
FieldFilterAGE_GE.human_name = u"Age (years) ≥"


class FieldFilterVALID_GT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterVALID_GT.internal_name = "validitygt"
FieldFilterVALID_GT.human_name = u"date until event ≥"


class FieldFilterFUTURE(FieldFilterOp0):
    def get_sql_where_params(self):
        return u'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )', { 'field_id': self.field_id }
    def get_param_types(self):
        return ()
FieldFilterFUTURE.internal_name = "future"
FieldFilterFUTURE.human_name = u"In the future"


class FieldFilterChoiceEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterChoiceEQ.internal_name = "ceq"
FieldFilterChoiceEQ.human_name = u"="


class FieldFilterChoiceNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterChoiceNEQ.internal_name = "cneq"
FieldFilterChoiceNEQ.human_name = u"≠"


class FieldFilterMultiChoiceHAS(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHAS.internal_name = "mchas"
FieldFilterMultiChoiceHAS.human_name = u"contains"


class FieldFilterMultiChoiceHASNOT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = ContactField.objects.get(self.field_id)
        cfv = Choice.objects.get(choice_group_id=field.choice_group_id, key=value)
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = ContactField.objects.get(self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHASNOT.internal_name = "mchasnot"
FieldFilterMultiChoiceHASNOT.human_name = u"doesn't contain"



class GroupFilterIsMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND member)' % self.group_id, {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsMember.internal_name = "memberof"
GroupFilterIsMember.human_name = u"is member of group"


class GroupFilterIsNotMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return u'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND member)' % self.group_id, {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsNotMember.internal_name = "notmemberof"
GroupFilterIsNotMember.human_name = u"is not member of group"


class GroupFilterIsInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND invited)' % self.group_id, {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsInvited.internal_name = "ginvited"
GroupFilterIsInvited.human_name = u"has been invited in group"


class GroupFilterIsNotInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return u'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND invited)' % self.group_id, {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsNotInvited.internal_name = "gnotinvited"
GroupFilterIsNotInvited.human_name = u"has not been invited in group"


class GroupFilterDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND declined_invitation)' % self.group_id, {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterDeclinedInvitation.internal_name = "gdeclined"
GroupFilterDeclinedInvitation.human_name = u"has declined invitation in group"


class GroupFilterNotDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        return u'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND declined_invitation)' % self.group_id, {}
    def to_html(self):
        try:
            group = ContactGroup.objects.get(pk=self.group_id)
        except ContactGroup.DoesNotExist:
            raise Http404()
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterNotDeclinedInvitation.internal_name = "gnotdeclined"
GroupFilterNotDeclinedInvitation.human_name = u"has not declined invitation in group"


class AllEventsNotReactedSince(Filter):
    def get_sql_where_params(self, value):
        value = decoratedstr.decorated_match(value)
        return u'NOT EXISTS (SELECT * from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(date)s AND (operator OR member OR declined_invitation))', { 'date':value }
    def to_html(self, value):
        return self.__class__.human_name+u" \""+unicode(value)+u"\""
    def get_param_types(self):
        return (unicode,) # TODO
AllEventsNotReactedSince.internal_name = "notreactedsince"
AllEventsNotReactedSince.human_name = u"has not reacted to any invitation since"

class AllEventsReactionYearRatioLess(Filter):
    def get_sql_where_params(self, value):
        return u'(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND (operator OR member OR declined_invitation)) < '+str(value/100.)+' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s)', { 'refdate':unicode(((datetime.today() - timedelta(365)).strftime('%Y-%m-%d'))) }
    def to_html(self, value):
        return self.__class__.human_name+u" \""+unicode(value)+u"\""
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioLess.internal_name = "yearreactionratioless"
AllEventsReactionYearRatioLess.human_name = u"1 year invitation reaction % less than"

class AllEventsReactionYearRatioMore(Filter):
    def get_sql_where_params(self, value):
        return u'(SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s AND (operator OR member OR declined_invitation)) > '+str(value/100.)+' * (SELECT COUNT(*) from contact_in_group JOIN contact_group ON (contact_in_group.group_id = contact_group.id) WHERE contact_in_group.contact_id=contact.id AND contact_group.date >= %(refdate)s)', { 'refdate':unicode(((datetime.today() - timedelta(365)).strftime('%Y-%m-%d'))) }
    def to_html(self, value):
        return self.__class__.human_name+u" \""+unicode(value)+u"\""
    def get_param_types(self):
        return (int,)
AllEventsReactionYearRatioMore.internal_name = "yearreactionratiomore"
AllEventsReactionYearRatioMore.human_name = u"1 year invitation reaction % more than"



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
        return u"\u00a0"*4*indent_level


class BoundFilter(BaseBoundFilter):
    # TODO: Rename to FieldBoundFilter

    def __init__(self, filter, *args):
        super(BoundFilter, self).__init__()
        self.filter = filter
        self.args = args

    def __repr__(self):
        return "BoundFilter<" + \
            ",".join([repr(self.filter)]+[repr(arg) for arg in self.args]) \
            +">"
    def get_sql_where_params(self):
        return self.filter.get_sql_where_params(*self.args)

    def to_html(self, indent_level=0):
        return self.indent(indent_level)+self.filter.to_html(*self.args)


class EmptyBoundFilter(BaseBoundFilter):
    def apply_filter_to_query(self, query):
        return query
    def to_html(self, indent_level=0):
        return self.indent(indent_level)+u"All contacts"


class AndBoundFilter(BaseBoundFilter):
    def __init__(self, f1, f2):
        super(AndBoundFilter, self).__init__()
        self.f1 = f1
        self.f2 = f2
    def get_sql_query_where(self, query, *args, **kargs):
        query, where1 = self.f1.get_sql_query_where(query)
        query, where2 = self.f2.get_sql_query_where(query)
        return query, u"((" + where1 + u') AND (' + where2 + u'))'
    def to_html(self, indent_level=0):
        return self.f1.to_html(indent_level+1) + u"<br>"+self.indent(indent_level)+u"AND<br>"+ self.f2.to_html(indent_level+1)


class OrBoundFilter(BaseBoundFilter):
    def __init__(self, f1, f2):
        super(OrBoundFilter, self).__init__()
        self.f1 = f1
        self.f2 = f2
    def get_sql_query_where(self, query, *args, **kargs):
        query, where1 = self.f1.get_sql_query_where(query)
        query, where2 = self.f2.get_sql_query_where(query)
        return query, u"((" + where1 + u') OR (' + where2 + u'))'
    def to_html(self, indent_level=0):
        return self.f1.to_html(indent_level+1) + u"<br>"+self.indent(indent_level)+u"OR<br>"+ self.f2.to_html(indent_level+1)


class ContactFieldValue(NgwModel):
    oid = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact, related_name='values')
    contact_field = models.ForeignKey(ContactField, related_name='values')
    value = models.TextField(blank=True)
    class Meta:
        db_table = u'contact_field_value'

    def __repr__(self):
        cf = self.contact_field
        return 'ContactFieldValue<"'+unicode(self.contact).encode("utf-8")+'", "'+unicode(cf).encode('utf-8')+'", "'+unicode(self).encode('utf-8')+'">'

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
        db_table = u'group_in_group'

    def __repr__(self):
        return 'GroupInGroup <%s %s>' % (self.subgroup_id, self.father_id)



class ContactInGroup(NgwModel):
    oid = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact)
    group = models.ForeignKey(ContactGroup)
    operator = models.BooleanField()
    member = models.BooleanField()
    invited = models.BooleanField()
    declined_invitation = models.BooleanField()
    note = models.TextField(blank=True)
    class Meta:
        db_table = u'contact_in_group'

    def __repr__(self):
        return "ContactInGroup<%s,%s>" % (self.contact_id, self.group_id)

    def __unicode__(self):
        return u"contact %(contactname)s in group %(groupname)s" % { 'contactname': self.contact.name, 'groupname': self.group.unicode_with_date() }

    @classmethod
    def get_class_navcomponent(cls):
        raise NotImplementedError()

    def get_navcomponent(self):
        return self.contact.get_navcomponent()

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url()+u"members/"+str(self.contact_id)+u"/membership"


class ContactSysMsg(NgwModel):
    id = models.AutoField(primary_key=True)
    contact = models.ForeignKey(Contact)
    message = models.TextField()
    class Meta:
        db_table = u'contact_sysmsg'


class ContactGroupNews(NgwModel):
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(Contact, null=True, blank=True)
    contact_group = models.ForeignKey(ContactGroup, null=True, blank=True)
    date = models.DateTimeField()
    title = models.TextField()
    text = models.TextField()

    class Meta:
        db_table = u'contact_group_news'
        ordering = '-date',
        verbose_name = u"news"
        verbose_name_plural = 'news'

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return self.contact_group.get_absolute_url()+u"news/"+str(self.id)+"/"


