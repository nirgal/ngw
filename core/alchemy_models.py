#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
from datetime import *
from sqlalchemy import *
from sqlalchemy.orm import *
import sqlalchemy.engine.url
from django.utils import html
from django import forms
from django.forms.util import smart_unicode
from itertools import chain
from ngw.settings import DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT
import decorated_letters

GROUP_USER = 2
GROUP_ADMIN = 8

FIELD_LOGIN = 1
FIELD_PASSWORD = 2
FIELD_LASTCONNECTION = 3
FIELD_COLUMNS = 4
FIELD_FILTERS = 5

FIELD_STREET = 9
FIELD_POSTCODE = 11
FIELD_CITY = 14
FIELD_COUNTRY = 48

AUTOMATIC_MEMBER_INDICATOR = u"⁂"

# Ends with a /
GROUP_STATIC_DIR="/usr/lib/ngw/static/static/g/"

dburl = sqlalchemy.engine.url.URL("postgres", DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT or None, DATABASE_NAME)
engine = create_engine(dburl, convert_unicode=True) #, echo=True)

Session = scoped_session(sessionmaker(bind=engine, autoflush=True, transactional=True))
meta = MetaData(engine)

########################################################################
# create the table objects, using the existing database
########################################################################
choice_table = Table('choice', meta, autoload=True)
choice_group_table = Table('choice_group', meta, autoload=True)
contact_table = Table('contact', meta, autoload=True)
contact_field_table = Table('contact_field', meta, autoload=True)
contact_field_value_table = Table('contact_field_value', meta, autoload=True)
contact_group_table = Table('contact_group', meta, autoload=True)
contact_in_group_table = Table('contact_in_group', meta, autoload=True)
group_in_group_table = Table('group_in_group', meta, autoload=True)
contact_sysmsg_table = Table('contact_sysmsg', meta, autoload=True)
config_table = Table('config', meta, autoload=True)
log_table = Table('log', meta, autoload=True)
contact_group_news_table = Table('contact_group_news', meta, autoload=True)

#print "meta analysis:"
#for t in meta.table_iterator(reverse=True):
#    print "TABLE", t.name
#    for c in t.columns:
#        print "column", c
#        print "primary key:", c.primary_key
#        print "index:", c.index
#        print "nullable:", c.nullable
#        print "onupdate:", c.onupdate
#        print "unique:", c.unique
#        print "type:", c.type
#        print "default:", c.default
#        #print "cascade:", c.cascade
#        #print dir(c)


class NgwModel(object):
    @classmethod
    def get_class_verbose_name(cls):
        try:
            return cls.Meta.verbose_name
        except AttributeError:
            return cls.__name__.lower()
    
    @classmethod
    def get_class_verbose_name_plural(cls):
        try:
            return cls.Meta.verbose_name_plural
        except AttributeError:
            return cls.get_class_verbose_name()+u"s"
    
    @classmethod
    def get_class_absolute_url(cls):
        return u"/"+unicode(cls.__name__.lower(), "utf-8-")+u"s/"

    def get_absolute_url(self):
        return self.get_class_absolute_url()+unicode(self.id)+u"/"

########################################################################
# Define classes to be mapped to the above tables.
# Most properties are fetched from the database, and autodeclared
########################################################################
# Types of change
LOG_ACTION_ADD      = 1
LOG_ACTION_CHANGE   = 2
LOG_ACTION_DEL      = 3

class Log(NgwModel):
    class Meta:
        pass
    def __init__(self, contact_id):
        NgwModel.__init__(self)
        self.dt = datetime.utcnow()
        self.contact_id = contact_id
    
    def __unicode__(self):
        return u"%(date)s: %(contactname)s %(type_and_data)s"% {
                u'date': self.dt.isoformat(),
                u'contactname': self.contact.name,
                u'action_and_data': self.action_and_data(),
                }
            
    def action_and_data(self):
        if self.action==LOG_ACTION_CHANGE:
            return u"%(property)s %(target)s: %(change)s"% {
                u'target': self.target_repr,
                u'property': self.property_repr,
                u'change': self.change,
                }

    def small_date(self):
        return self.dt.strftime('%Y-%m-%d %H:%M:%S')

    def action_txt(self):
        return { LOG_ACTION_ADD: u"Add",
                 LOG_ACTION_CHANGE: u"Update",
                 LOG_ACTION_DEL: u"Delete"}[self.action]

class Config(NgwModel):
    class Meta:
        pass
    pass

class Choice(NgwModel):
    class Meta:
        pass
    def __init__(self, key, value):
        NgwModel.__init__(self)
        self.key = key
        self.value = value

class ChoiceGroup(NgwModel):
    class Meta:
        verbose_name="choices list"

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return "ChoiceGroup<"+self.name.encode('utf-8')+">"

    @property
    def ordered_choices(self):
        "Utility property to get choices tuples in correct order"
        q = Query(Choice)
        q = q.filter(choice_table.c.choice_group_id==self.id)
        if self.sort_by_key:
            q = q.order_by([choice_table.c.key])
        else:
            q = q.order_by([choice_table.c.value])
        return [(c.key, c.value) for c in q]

    def get_link(self):
        return u"/choicegroups/"+str(self.id)+"/edit"
    get_link_name=get_link # templatetags


class Contact(NgwModel):
    class Meta:
        verbose_name="contact"

    def __init__(self, name):
        NgwModel.__init__(self)
        self.name = name

    def __repr__(self):
        return self.name.encode('utf-8')

    def __unicode__(self):
        return self.name

    def str_member_of(self, gids):
        #gids = [ g.id for g in cg.self_and_subgroups ]
        gid = gids[0]
        cig = Query(ContactInGroup).get((self.id, gid))
        if cig:
            if cig.operator:
                return u"Operator"
            elif cig.member:
                return u"Member"
            elif cig.invited:
                return u"Invited"
            elif cig.declined_invitation:
                return u"Declined"
            else:
                return u"ERROR: invalid contact_in_group flag combinaision"

        elif select([contact_in_group_table], whereclause=and_(contact_in_group_table.c.contact_id==self.id, contact_in_group_table.c.group_id.in_(gids))).execute().fetchone(): 
            return u"Member"+u" "+AUTOMATIC_MEMBER_INDICATOR
        else:
            return u""

    def get_link(self):
        return u"/contacts/"+str(self.id)+"/"
    get_link_name=get_link # templatetags

    def get_directgroups_member(self):
        "returns the list of groups that contact is direct member of."
        q = Query(ContactInGroup).filter(ContactInGroup.c.contact_id == self.id ).filter(ContactInGroup.c.member==True)
        groupids = [cig.group_id for cig in q]
        return Query(ContactGroup).filter(ContactGroup.c.id.in_(groupids))

    def get_allgroups_member(self):
        "returns the list of groups that contact is member of."
        q = Query(ContactInGroup).filter(ContactInGroup.c.contact_id == self.id ).filter(ContactInGroup.c.member==True)
        groups = []
        for cig in q:
            g = Query(ContactGroup).get(cig.group_id)
            if g not in groups:
                groups.append(g)
            g._append_supergroups(groups)
        return groups

    def get_allgroups_invited(self):
        "returns the list of groups that contact is in invited list."
        q = Query(ContactInGroup).filter(ContactInGroup.c.contact_id == self.id ).filter(ContactInGroup.c.invited==True)
        groups = []
        for cig in q:
            g = Query(ContactGroup).get(cig.group_id)
            if g not in groups:
                groups.append(g)
            g._append_supergroups(groups)
        return groups

    def get_allgroups_withfields(self):
        "returns the list of groups with field_group ON that contact is member of."
        return [ g for g in self.get_allgroups_member() if g.field_group ]

    def get_allfields(self):
        contactgroupids = [ g.id for g in self.get_allgroups_withfields()] 
        #print "contactgroupids=", contactgroupids
        return Query(ContactField).filter(or_(ContactField.c.contact_group_id.in_(contactgroupids),ContactField.c.contact_group_id == None)).order_by(ContactField.c.sort_weight)

    def get_fieldvalues_by_type(self, type_):
        if issubclass(type_, ContactField):
            type_ = type_.db_type_id
        assert type_.__class__ == unicode
        fields = Query(ContactField).filter(ContactField.c.type==type_).order_by(ContactField.c.sort_weight)
        # TODO: check authority
        result = []
        for field in fields:
            v = self.get_fieldvalue_by_id(field.id)
            if v:
                result.append(v)
        return result

    def get_fieldvalue_by_id(self, field_id):
        cfv = Query(ContactFieldValue).get((self.id, field_id))
        if cfv == None:
            return u""
        return unicode(cfv)

    def set_fieldvalue(self, user, field, newvalue):
        """
        Sets a field value and registers the change in the log table.
        Field can be either a field id or a ContactField object.
        New value must be text.
        """
        if type(field)==int:
            field_id = field
            field = Query(ContactField).get(field)
        else:
            assert isinstance(field, ContactField)
            field_id = field.id
        cfv = Query(ContactFieldValue).get((self.id, field_id))
        if cfv == None:
            if newvalue:
                log = Log(user.id)
                log.action = LOG_ACTION_CHANGE
                log.target = u"Contact "+unicode(self.id)
                log.target_repr = u"Contact "+self.name
                log.property = unicode(field_id)
                log.property_repr = field.name
                cfv = ContactFieldValue()
                cfv.contact = self
                cfv.field = field
                cfv.value = newvalue
                log.change = u"new value is "+unicode(cfv)
        else: # There was a value
            if newvalue:
                if cfv.value!=newvalue:
                    log = Log(user.id)
                    log.action = LOG_ACTION_CHANGE
                    log.target = u"Contact "+unicode(self.id)
                    log.target_repr = u"Contact "+self.name
                    log.property = unicode(field_id)
                    log.property_repr = field.name
                    log.change = u"change from "+unicode(cfv)
                    cfv.value = newvalue
                    log.change += u" to "+unicode(cfv)
            else:
                log = Log(user.id)
                log.action = LOG_ACTION_DEL
                log.target = u"Contact "+unicode(self.id)
                log.target_repr = u"Contact "+self.name
                log.property = unicode(field_id)
                log.property_repr = field.name
                log.change = u"old value was "+unicode(cfv)
                Session.delete(cfv)

    def get_login(self):
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

        for phone in self.get_fieldvalues_by_type(PhoneContactField):
            vcf += line(u"TEL", phone)

        for email in self.get_fieldvalues_by_type(EmailContactField):
            vcf += line(u"EMAIL", email)

        vcf += line(u"END", u"VCARD")
        return vcf

    def get_addr_semicol(self):
        return self.get_fieldvalue_by_id(FIELD_STREET)+u";"+self.get_fieldvalue_by_id(FIELD_CITY)+u";"+self.get_fieldvalue_by_id(FIELD_COUNTRY)

    def push_message(self, message):
        ContactSysMsg(self.id, message)
        #N# Session.commit()

    def get_and_delete_messages(self):
        """
        That function is called by django ContextProcessor auth.
        See django.core.context_processors
        """
        messages = []
        for sm in self.sysmsg:
            messages.append(sm.message)
            Session.delete(sm)
        return messages

    def generate_login(self):
        words=self.name.split(" ")
        login=[w[0].lower() for w in words[:-1] ] + [ words[-1].lower() ]
        login = "".join(login)
        login = decorated_letters.remove_decoration(login)
        def get_logincfv_by_login(ref_uid, login):
            " return first login cfv where loginname=login and not uid!=ref_uid "
            return Query(ContactFieldValue).filter(ContactFieldValue.c.contact_field_id==FIELD_LOGIN) \
                                   .filter(ContactFieldValue.c.value==login) \
                                   .filter(ContactFieldValue.c.contact_id!=ref_uid) \
                                   .first()
        if not get_logincfv_by_login(self.id, login):
            return login
        i=1;
        while (True):
            altlogin = login+unicode(i)
            if not get_logincfv_by_login(self.id, altlogin):
                return altlogin
            i+=1

    @staticmethod
    def check_login_created(logged_contact):
        # Create login for people member of GROUP_USER
        for (uid,) in Session.execute("SELECT users.contact_id FROM (SELECT DISTINCT contact_in_group.contact_id FROM contact_in_group WHERE group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d))) AS users LEFT JOIN contact_field_value ON (contact_field_value.contact_id=users.contact_id AND contact_field_value.contact_field_id=%(FIELD_LOGIN)d) WHERE contact_field_value.value IS NULL"%{"GROUP_USER":GROUP_USER,"FIELD_LOGIN":FIELD_LOGIN}):
            contact = Query(Contact).get(uid)
            new_login = contact.generate_login()
            cfv = ContactFieldValue()
            cfv.contact_id = uid
            cfv.contact_field_id = FIELD_LOGIN
            cfv.value = new_login
            logged_contact.push_message("Login information generated for User %s."%(contact.name))
        
        for cfv in Query(ContactFieldValue).filter("contact_field_value.contact_field_id=1 AND NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact_field_value.contact_id AND contact_in_group.group_id IN (SELECT self_and_subgroups(%(GROUP_USER)d)) AND contact_in_group.member='t')"%{"GROUP_USER":GROUP_USER}):
            logged_contact.push_message("Delete login information for User %s."%(cfv.contact.name))
            Session.delete(cfv)

    def is_admin(self):
        adminsubgroups = Query(ContactGroup).get(GROUP_ADMIN).self_and_subgroups
        cig = Query(ContactInGroup).filter(ContactInGroup.c.contact_id==self.id).filter(ContactInGroup.c.group_id.in_([g.id for g in adminsubgroups])).first()
        return cig!=None

    def update_lastconnection(self):
        cfv = Query(ContactFieldValue).get((self.id, FIELD_LASTCONNECTION))
        if not cfv:
            cfv = ContactFieldValue()
            cfv.contact_id = self.id
            cfv.contact_field_id = FIELD_LASTCONNECTION
        cfv.value = datetime.utcnow().date().isoformat()


class ContactGroup(NgwModel):
    class Meta:
        verbose_name = u"contacts group"

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name.encode('utf-8')

    def _append_subgroups(self, result):
        for g in self.direct_subgroups:
            if g not in result:
                result.append(g)
                g._append_subgroups(result)
        
    def _get_subgroups(self):
        result = []
        self._append_subgroups(result)
        return result
    subgroups = property(_get_subgroups)

    def _get_self_and_subgroups(self):
        result = [self ]
        self._append_subgroups(result)
        return result
    self_and_subgroups = property(_get_self_and_subgroups)

    def _append_supergroups(self, result):
        for g in self.direct_supergroups:
            if g not in result:
                result.append(g)
                g._append_supergroups(result)
        
    def _get_supergroups(self):
        result = []
        self._append_supergroups(result)
        return result
    supergroups = property(_get_supergroups)

    def _get_self_and_supergroups(self):
        result = [self ]
        self._append_supergroups(result)
        return result
    self_and_supergroups = property(_get_self_and_supergroups)

    def get_direct_members(self):
        cigs = Query(ContactInGroup).filter(and_(ContactInGroup.c.group_id==self.id, ContactInGroup.c.member==True))
        cids = [ cig.contact_id for cig in cigs ]
        return Query(Contact).filter(Contact.c.id.in_(cids))

    def get_direct_invited(self):
        cigs = Query(ContactInGroup).filter(and_(ContactInGroup.c.group_id==self.id, ContactInGroup.c.invited==True))
        cids = [ cig.contact_id for cig in cigs ]
        return Query(Contact).filter(Contact.c.id.in_(cids))

    def _get_members(self):
        gids = [ ]
        for g in self.self_and_subgroups:
            gids.append(g.id)
        #print "gids=", gids
        #s = select([contact_in_group_table], contact_in_group_table.c.group_id.in_(gids))
        #print "members=", s, ":"
        #for c in Session.execute(s):
        #    print c
        s = select([contact_in_group_table.c.contact_id], and_(contact_in_group_table.c.group_id.in_(gids), contact_in_group_table.c.member==True)).distinct()
        #print "members=", s, ":"
        result =  []
        #TODO optimize me
        for cid in Session.execute(s):
            result.append(Query(Contact).get(cid[0]))
            #print cid[0]
        return result

    members = property(_get_members)

    def get_link(self):
        return u"/contactgroups/"+str(self.id)+"/"
    get_link_name=get_link # templatetags

    def supergroups_includinghtml(self):
        sgs = self.supergroups
        if not sgs:
            return u""
        return u" (implies "+u", ".join(['<a href="'+g.get_link()+'">'+html.escape(g.name)+'</a>' for g in sgs])+u")"

    def subgroups_includinghtml(self):
        sgs = self.subgroups
        if not sgs:
            return u""
        return u" (including "+u", ".join(['<a href="'+g.get_link()+'">'+html.escape(g.name)+'</a>' for g in sgs])+u")"

    def unicode_with_date(self):
        """ Returns the name of the group, and the date if there's one"""
        result = self.name
        if self.date:
            result += u" "+str(self.date)
        return result

    def static_folder(self):
        """ Returns the name of the folder for static files for that group """
        return GROUP_STATIC_DIR+str(self.id)


    def check_static_folder_created(self):
        """ Create the folder for static files and setup permissions """
        if not self.id:
            Session.commit()
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

########################################
# Contact Fields

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
            output.append(u'<li><label>%s %s</label></li>' % (rendered_cb, html.escape(smart_unicode(option_label))))
        output.append(u'</ul>')
        return u'\n'.join(output)

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_0'
        return id_
    id_for_label = classmethod(id_for_label)



CONTACT_FIELD_TYPES_CLASSES=[]
def register_contact_field_type(cls, db_type_id, human_type_id, has_choice):
    CONTACT_FIELD_TYPES_CLASSES.append(cls)
    cls.db_type_id = db_type_id
    cls.human_type_id = human_type_id
    cls.has_choice = has_choice
    return cls
def get_contact_field_type_by_dbid(db_type_id):
    for cls in CONTACT_FIELD_TYPES_CLASSES:
        if cls.db_type_id == db_type_id:
            return cls
    raise KeyError(u"No ContactField class using id "+db_type_id)



class ContactField(NgwModel):
    class Meta:
        verbose_name = u"optional field"
    
    # Overide url for all derived classes
    @classmethod
    def get_class_absolute_url(cls):
        return u"/contactfields/"

    def __repr__(self):
        return "ContactField<"+str(self.id)+","+self.name.encode('utf8')+','+self.type.encode('utf8')+">"

    def __unicode__(self):
        return self.name

    def str_type_base(self):
        return self.__class__.human_type_id

    def type_as_html(self):
        return self.str_type_base()

    def format_value_unicode(self, value):
        return value
    def format_value_html(self, value):
        return self.format_value_unicode(value)

    def get_link(self):
        return u"/contactfields/"+unicode(self.id)+u"/edit"
    get_link_name=get_link # templatetags

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



class TextContactField(ContactField):
    def get_form_fields(self):
        return forms.CharField(label=self.name, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(TextContactField, u"TEXT", u"Text", has_choice=False)

class LongTextContactField(ContactField):
    def get_form_fields(self):
        return forms.CharField(label=self.name, widget=forms.Textarea, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(LongTextContactField, u"LONGTEXT", u"Long Text", has_choice=False)

class NumberContactField(ContactField):
    def get_form_fields(self):
        return forms.IntegerField(label=self.name, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterIEQ, FieldFilterINE, FieldFilterILE, FieldFilterIGE, FieldFilterILT, FieldFilterIGT, FieldFilterNull, FieldFilterNotNull,)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            int(value)
        except ValueError:
            return False
        return True
register_contact_field_type(NumberContactField, u"NUMBER", u"Number", has_choice=False)

class DateContactField(ContactField):
    def get_form_fields(self):
        return forms.DateField(label=self.name, required=False, help_text=u"Use YYYY-MM-DD format."+u" "+self.hint)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterLE, FieldFilterGE, FieldFilterAGE_GE, FieldFilterVALID_GT, FieldFilterFUTURE,  FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(DateContactField, u"DATE", u"Date", has_choice=False)

class EmailContactField(ContactField):
    def format_value_html(self, value):
        return u'<a href="mailto:%(value)s">%(value)s</a>' % {'value':value}
    def get_form_fields(self):
        return forms.EmailField(label=self.name, required=False, help_text=self.hint)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            forms.EmailField().clean(value)
        except forms.ValidationError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(EmailContactField, u"EMAIL", u"E.Mail", has_choice=False)

class PhoneContactField(ContactField):
    def format_value_html(self, value):
        return u'<a href="tel:%(value)s">%(value)s</a>' % {'value':value} # rfc3966
    def get_form_fields(self):
        return forms.CharField(label=self.name, max_length=255, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(PhoneContactField, u"PHONE", u"Phone", has_choice=False)

class RibContactField(ContactField):
    def get_form_fields(self):
        return RibField(label=self.name, required=False, help_text=self.hint)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            RibField().clean(value)
        except forms.ValidationError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(RibContactField, u"RIB", u"French bank account", has_choice=False)

class ChoiceContactField(ContactField):
    def type_as_html(self):
        return self.str_type_base() + u" (<a href='"+self.choice_group.get_link()+u"'>"+html.escape(self.choice_group.name)+u"</a>)"
    def format_value_unicode(self, value):
        chg = self.choice_group
        if chg == None:
            return u"Error"
        c = Query(Choice).get((chg.id, value))
        if c == None:
            return u"Error"
        else:
            return c.value
    def get_form_fields(self):
        return forms.CharField(max_length=255, label=self.name, required=False, help_text=self.hint, widget=forms.Select(choices=[(u'', u"Unknown")]+self.choice_group.ordered_choices))
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        return Query(Choice).filter(Choice.c.choice_group_id==choice_group_id).filter(Choice.c.key==value).count() == 1
    def get_filters_classes(self):
        return (FieldFilterChoiceEQ, FieldFilterChoiceNEQ, FieldFilterNull, FieldFilterNotNull,)

register_contact_field_type(ChoiceContactField, u"CHOICE", u"Choice", has_choice=True)

class MultipleChoiceContactField(ContactField):
    def type_as_html(self):
        return self.str_type_base() + u" (<a href='"+self.choice_group.get_link()+u"'>"+html.escape(self.choice_group.name)+u"</a>)"
    def format_value_unicode(self, value):
        chg = self.choice_group
        if chg == None:
            return u"Error"
        txt_choice_list = []
        for cid in value.split(u","):
            if cid==u"":
                txt_choice_list.append( "default" ) # this should never occur
                continue
            c = Query(Choice).get((chg.id, cid))
            if c == None:
                txt_choice_list.append( "error" )
            else:
                txt_choice_list.append( c.value )
        return u", ".join(txt_choice_list)
    def get_form_fields(self):
        return forms.MultipleChoiceField(label=self.name, required=False, help_text=self.hint, choices=self.choice_group.ordered_choices, widget=NgwCheckboxSelectMultiple())
    def formfield_value_to_db_value(self, value):
        return u",".join(value)
    def db_value_to_formfield_value(self, value):
        return value.split(u",")
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        for v in value.split(','):
            if Query(Choice).filter(Choice.c.choice_group_id==choice_group_id).filter(Choice.c.key==v).count() != 1:
                return False
        return True
    def get_filters_classes(self):
        return (FieldFilterMultiChoiceHAS, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(MultipleChoiceContactField, u"MULTIPLECHOICE", u"Multiple choice", has_choice=True)

class PasswordContactField(ContactField):
    def format_value_unicode(self, value):
        return u"********"
    def get_form_fields(self):
        return None
    def formfield_value_to_db_value(self, value):
        raise NotImplemented()
    def db_value_to_formfield_value(self, value):
        raise NotImplemented(u"Cannot reverse hash of a password")
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        return len(value)==13 #TODO
register_contact_field_type(PasswordContactField, u"PASSWORD", u"Password", has_choice=False)


class ContactNameMetaField(object):
    @classmethod
    def get_filters_classes(cls):
        return (NameFilterStartsWith, )

    @classmethod
    def get_filters(cls):
        return [ filter() for filter in cls.get_filters_classes() ]

    @classmethod
    def get_filter_by_name(cls, name):
        return [ f for f in cls.get_filters() if f.__class__.internal_name==name][0]

    

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
        for k,v in kargs.iteritems():
            #print k,"=",v
            auto_param_name=u"autoparam_"+unicode(len(query._params))+u"_" # resolve conflicts in sucessive calls to apply_where_to_query
            if isinstance(v, unicode):
                params_where[ k ] = u':'+auto_param_name+k
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
        query = query.params(params)
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
        value = decorated_letters.str_match_withdecoration(value.lower())
        return u'contact.name ~* %(value_name1)s OR contact.name ~* %(value_name2)s', { 'value_name1':u"^"+value, 'value_name2':u" "+value }
    def to_html(self, value):
        return u"<b>Name</b> "+self.__class__.human_name+u" \""+unicode(value)+u"\""

    def get_param_types(self):
        return (unicode,)
NameFilterStartsWith.internal_name="startswith"
NameFilterStartsWith.human_name=u"has a word starting with"


class FieldFilter(Filter):
    """ Helper abstract class for field filters """
    def __init__(self, field_id):
        self.field_id = field_id

class FieldFilterOp0(FieldFilter):
    """ Helper abstract class for field filters that takes not parameter """
    def to_html(self):
        field = Query(ContactField).get(self.field_id)
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name

class FieldFilterOp1(FieldFilter):
    """ Helper abstract class for field filters that takes 1 parameter """
    def to_html(self, value):
        field = Query(ContactField).get(self.field_id)
        result = u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" "
        if isinstance(value, unicode):
            value = u'"'+value+u'"'
        else:
            value = unicode(value)
        return result+value


class FieldFilterStartsWith(FieldFilterOp1):
    def get_sql_where_params(self, value):
        value = decorated_letters.str_match_withdecoration(value.lower())
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value1)s OR (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ~* %(value2)s', { 'field_id':self.field_id, 'value1':u"^"+value, 'value2':u" "+value}
    def get_param_types(self):
        return (unicode,)
FieldFilterStartsWith.internal_name="startswith"
FieldFilterStartsWith.human_name=u"has a word starting with"


class FieldFilterEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value}
    def get_param_types(self):
        return (unicode,)
FieldFilterEQ.internal_name="eq"
FieldFilterEQ.human_name=u"="

    
class FieldFilterNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterNEQ.internal_name="neq"
FieldFilterNEQ.human_name=u"≠"

    
class FieldFilterLE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) <= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterLE.internal_name="le"
FieldFilterLE.human_name=u"≤"

    
class FieldFilterGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) >= %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterGE.internal_name="ge"
FieldFilterGE.human_name=u"≥"

    
class FieldFilterLIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) LIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterLIKE.internal_name="like"
FieldFilterLIKE.human_name=u"SQL LIKE"

    
class FieldFilterILIKE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) ILIKE %(value)s', { 'field_id':self.field_id, 'value':value }
    def get_param_types(self):
        return (unicode,)
FieldFilterILIKE.internal_name="ilike"
FieldFilterILIKE.human_name=u"SQL ILIKE"

    
class FieldFilterNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNull.internal_name="null"
FieldFilterNull.human_name=u"is undefined"

    
class FieldFilterNotNull(FieldFilterOp0):
    def get_sql_where_params(self):
        return u'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )', { 'field_id':self.field_id }
    def get_param_types(self):
        return ()
FieldFilterNotNull.internal_name="notnull"
FieldFilterNotNull.human_name=u"is defined"

    
class FieldFilterIEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int = %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIEQ.internal_name="ieq"
FieldFilterIEQ.human_name=u"="

    
class FieldFilterINE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <> %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterINE.internal_name="ineq"
FieldFilterINE.human_name=u"≠"

    
class FieldFilterIEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int = %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIEQ.internal_name="ieq"
FieldFilterIEQ.human_name=u"="

    
class FieldFilterILT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int < %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterILT.internal_name="ilt"
FieldFilterILT.human_name=u"<"

    
class FieldFilterIGT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int > %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIGT.internal_name="igt"
FieldFilterIGT.human_name=u">"

    
class FieldFilterILE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int <= %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterILE.internal_name="ile"
FieldFilterILE.human_name=u"≤"

    
class FieldFilterIGE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i )::int >= %(value)i', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterIGE.internal_name="ige"
FieldFilterIGE.human_name=u"≥"

    
class FieldFilterAGE_GE(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND NOW() - value::DATE > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterAGE_GE.internal_name="agege"
FieldFilterAGE_GE.human_name=u"Age (years) ≥"

    
class FieldFilterVALID_GT(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE - NOW() > \'%(value)i years\'::INTERVAL )', { 'field_id':self.field_id, 'value':int(value) }
    def get_param_types(self):
        return (int,)
FieldFilterVALID_GT.internal_name="validitygt"
FieldFilterVALID_GT.human_name=u"date until event ≥"

    
class FieldFilterFUTURE(FieldFilterOp0):
    def get_sql_where_params(self):
        return u'EXISTS (SELECT * FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND value::DATE > NOW() )', { 'field_id': self.field_id }
    def get_param_types(self):
        return ()
FieldFilterFUTURE.internal_name="future"
FieldFilterFUTURE.human_name=u"In the future"

    
class FieldFilterChoiceEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'(SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i ) = %(value)s', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = Query(ContactField).get(self.field_id)
        cfv = Query(Choice).get((field.choice_group_id, value))
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = Query(ContactField).get(self.field_id)
        return (field.choice_group,)
FieldFilterChoiceEQ.internal_name="ceq"
FieldFilterChoiceEQ.human_name=u"="


class FieldFilterChoiceNEQ(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'NOT EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND contact_field_value.value = %(value)s)', { 'field_id':self.field_id, 'value':value }
    def to_html(self, value):
        field = Query(ContactField).get(self.field_id)
        cfv = Query(Choice).get((field.choice_group_id, value))
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = Query(ContactField).get(self.field_id)
        return (field.choice_group,)
FieldFilterChoiceNEQ.internal_name="cneq"
FieldFilterChoiceNEQ.human_name=u"≠"

    
class FieldFilterMultiChoiceHAS(FieldFilterOp1):
    def get_sql_where_params(self, value):
        return u'EXISTS (SELECT value FROM contact_field_value WHERE contact_field_value.contact_id = contact.id AND contact_field_value.contact_field_id = %(field_id)i AND ( value=%(value)s OR value LIKE %(valuestart)s OR value LIKE %(valuemiddle)s OR value LIKE %(valueend)s ) )', { 'field_id':self.field_id, 'value':value, 'valuestart':value+",%", 'valuemiddle':"%,"+value+",%", 'valueend':"%,"+value }
    def to_html(self, value):
        field = Query(ContactField).get(self.field_id)
        cfv = Query(Choice).get((field.choice_group_id, value))
        return u"<b>"+html.escape(field.name)+u"</b> "+self.__class__.human_name+u" \""+html.escape(cfv.value)+u"\""
    def get_param_types(self):
        field = Query(ContactField).get(self.field_id)
        return (field.choice_group,)
FieldFilterMultiChoiceHAS.internal_name="mchas"
FieldFilterMultiChoiceHAS.human_name=u"contains"



class GroupFilterIsMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        group = Query(ContactGroup).get(self.group_id)
        return u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND member=True)' % ",".join([str(g.id) for g in group.self_and_subgroups]), {}
    def to_html(self):
        group = Query(ContactGroup).get(self.group_id)
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsMember.internal_name="memberof"
GroupFilterIsMember.human_name=u"is member of group"

    
class GroupFilterIsNotMember(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        group = Query(ContactGroup).get(self.group_id)
        return u'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND member=True)' % ",".join([str(g.id) for g in group.self_and_subgroups]), {}
    def to_html(self):
        group = Query(ContactGroup).get(self.group_id)
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsNotMember.internal_name="notmemberof"
GroupFilterIsNotMember.human_name=u"is not member of group"

    
class GroupFilterIsInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        group = Query(ContactGroup).get(self.group_id)
        return u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND invited=True)' % ",".join([str(g.id) for g in group.self_and_subgroups]), {}
    def to_html(self):
        group = Query(ContactGroup).get(self.group_id)
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsInvited.internal_name="ginvited"
GroupFilterIsInvited.human_name=u"has been invited in group"

    
class GroupFilterIsNotInvited(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        group = Query(ContactGroup).get(self.group_id)
        return u'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND invited=True)' % ",".join([str(g.id) for g in group.self_and_subgroups]), {}
    def to_html(self):
        group = Query(ContactGroup).get(self.group_id)
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterIsNotInvited.internal_name="gnotinvited"
GroupFilterIsNotInvited.human_name=u"has not been invited in group"

    
class GroupFilterDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        group = Query(ContactGroup).get(self.group_id)
        return u'EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND declined_invitation=True)' % ",".join([str(g.id) for g in group.self_and_subgroups]), {}
    def to_html(self):
        group = Query(ContactGroup).get(self.group_id)
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterDeclinedInvitation.internal_name="gdeclined"
GroupFilterDeclinedInvitation.human_name=u"has declined invitation in group"

    
class GroupFilterNotDeclinedInvitation(Filter):
    def __init__(self, group_id):
        self.group_id = group_id
    def get_sql_where_params(self):
        group = Query(ContactGroup).get(self.group_id)
        return u'NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (%s) AND declined_invitation=True)' % ",".join([str(g.id) for g in group.self_and_subgroups]), {}
    def to_html(self):
        group = Query(ContactGroup).get(self.group_id)
        return self.__class__.human_name+u" <b>"+group.unicode_with_date()+"</b>"
    def get_param_types(self):
        return ()
GroupFilterNotDeclinedInvitation.internal_name="gnotdeclined"
GroupFilterNotDeclinedInvitation.human_name=u"has not declined invitation in group"

    
    
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
        self.f1 = f1
        self.f2 = f2
    def get_sql_query_where(self, query, *args, **kargs):
        query, where1 = self.f1.get_sql_query_where(query)
        query, where2 = self.f2.get_sql_query_where(query)
        return query, u"("+where1+u') AND ('+where2+u')'
    def to_html(self, indent_level=0):
        return self.f1.to_html(indent_level+1) + u"<br>"+self.indent(indent_level)+u"AND<br>"+ self.f2.to_html(indent_level+1)


class OrBoundFilter(BaseBoundFilter):
    def __init__(self, f1, f2):
        self.f1 = f1
        self.f2 = f2
    def get_sql_query_where(self, query, *args, **kargs):
        query, where1 = self.f1.get_sql_query_where(query)
        query, where2 = self.f2.get_sql_query_where(query)
        return query, u"("+where1+u') OR ('+where2+u')'
    def to_html(self, indent_level=0):
        return self.f1.to_html(indent_level+1) + u"<br>"+self.indent(indent_level)+u"OR<br>"+ self.f2.to_html(indent_level+1)



class ContactFieldValue(NgwModel):
    class Meta:
        verbose_name = u"contact field value"

    def __repr__(self):
        return 'ContactFieldValue<"'+unicode(self.contact).encode("utf-8")+'", "'+unicode(self.field).encode('utf-8')+'", "'+unicode(self).encode('utf-8')+'">'

    def __unicode__(self):
        return self.field.format_value_unicode(self.value)
 
    def as_html(self):
        return self.field.format_value_html(self.value)

class ContactInGroup(NgwModel):
    def __init__(self, contact_id, group_id):
        NgwModel.__init__(self)
        self.contact_id = contact_id
        self.group_id = group_id

    def __repr__(self):
        return "ContactInGroup<%s,%s>"%(self.contact_id, self.group_id)


class ContactSysMsg(NgwModel):
    def __init__(self, contact_id, message):
        NgwModel.__init__(self)
        self.contact_id = contact_id
        self.message = message
    def __repr__(self):
        return "ContactSysMsg<%s,%s>"%(self.contact_id, self.message)

class ContactGroupNews(NgwModel):
    class Meta:
        verbose_name = u"news"
        verbose_name_plural = u"news"
    #def __repr__(self):
    #    return "ContactGroupNews<%s,%s>"%(self.contact_id, self.message)
    def __unicode__(self):
        return self.title + u" - " + self.date.strftime("%Y %m %d")
    
    @staticmethod
    def get_class_absolute_url(cls):
        raise Error("Not implemented")

    #def get_link(self):
    def get_absolute_url(self):
        return self.contact_group.get_absolute_url()+u"news/"+str(self.id)+"/"

########################################################################
# Map the class to the tables
########################################################################
mapper = Session.mapper
choice_mapper=mapper(Choice, choice_table)
choice_group_mapper = mapper(ChoiceGroup, choice_group_table)
contact_mapper = mapper(Contact, contact_table)
contact_group_mapper = mapper(ContactGroup, contact_group_table)
contact_in_group_mapper = mapper(ContactInGroup, contact_in_group_table)
contact_field_mapper = mapper(ContactField, contact_field_table, polymorphic_on=contact_field_table.c.type)
for cls in CONTACT_FIELD_TYPES_CLASSES:
    mapper(cls, contact_field_table, inherits=ContactField, polymorphic_identity=cls.db_type_id)
contact_field_value_mapper = mapper(ContactFieldValue, contact_field_value_table)
contact_sysmsg_mapper = mapper(ContactSysMsg, contact_sysmsg_table)
config_mapper = mapper(Config, config_table)
log_mapper = mapper(Log, log_table)
contact_group_news_mapper = mapper(ContactGroupNews, contact_group_news_table)

#mapper(ContactInGroup,
#    contact_in_group_table, properties={ \
##    'choices': relation(Choice, primaryjoin=choice_table.c.choice_group_id==choice_group_table.c.id, cascade="save, update, merge, expunge, refresh, delete, expire"),
#})
########################################################################
# Define the relations between the tables
########################################################################

#TODO backref=backref('parent', uselist=False)

# ChoiceGroup <-> Choice
choice_group_mapper.add_property('choices', relation(
    Choice,
    primaryjoin=choice_table.c.choice_group_id==choice_group_table.c.id,
    cascade="delete",
    passive_deletes=True))

# ContactInGroup <-> Contact
contact_mapper.add_property('in_group', relation(
    ContactInGroup,
    primaryjoin=contact_table.c.id==contact_in_group_table.c.contact_id,
    cascade="delete",
    backref="contact",
    passive_deletes=True))

# ContactInGroup <-> Contact
contact_group_mapper.add_property('in_group', relation(
    ContactInGroup,
    primaryjoin=contact_group_table.c.id==contact_in_group_table.c.group_id,
    cascade="delete",
    backref="group",
    passive_deletes=True))
# ContactGroup <-> Contact
#contact_mapper.add_property('direct_groups', relation(
#    ContactGroup,
#    secondary=contact_in_group_table,
#    lazy=True,
#    cascade="none",
#    backref='direct_contacts',
#    passive_deletes=True))

# ContactGroup <-> ContactGroup
contact_group_mapper.add_property('direct_subgroups', relation(
    ContactGroup, 
    primaryjoin=contact_group_table.c.id==group_in_group_table.c.father_id,
    secondary=group_in_group_table,
    secondaryjoin=contact_group_table.c.id==group_in_group_table.c.subgroup_id,
    lazy=True,
    cascade="none", 
    backref='direct_supergroups',
    passive_deletes=True))

# ContactField <-> ContactGroup
contact_group_mapper.add_property('contact_fields', relation(
    ContactField,
    primaryjoin=contact_group_table.c.id==contact_field_table.c.contact_group_id,
    cascade="none",
    backref='contact_group',
    passive_deletes=True))

# ContactField <-> ChoiceGroup
choice_group_mapper.add_property('contact_field', relation(
    ContactField,
    primaryjoin=choice_group_table.c.id==contact_field_table.c.choice_group_id,
    cascade="delete", # TODO
    backref='choice_group',
    passive_deletes=True))

# ContactFieldValue <-> Contact
contact_mapper.add_property('values', relation(
    ContactFieldValue,
    cascade="delete",
    backref="contact",
    passive_deletes=True))

# ContactFieldValue <-> ContactField
contact_field_mapper.add_property('values', relation(
    ContactFieldValue,
    cascade="delete",
    backref="field",
    passive_deletes=True))

# Contact <-> ContactSysMsg
contact_mapper.add_property('sysmsg', relation(
    ContactSysMsg,
    primaryjoin=contact_sysmsg_table.c.contact_id==contact_table.c.id,
    cascade="delete",
    passive_deletes=True))

# Log <-> Contact
log_mapper.add_property('contact', relation(
    Contact,
    primaryjoin=log_table.c.contact_id==contact_table.c.id,
    cascade="delete",
    backref='logs',
    passive_deletes=True))

# Contact <-> ContactGroupNews
contact_mapper.add_property('news', relation(
    ContactGroupNews,
    primaryjoin=contact_group_news_table.c.author_id==contact_table.c.id,
    cascade="all,delete",
    backref='author',
    passive_deletes=True,
    order_by=desc(ContactGroupNews.date)))
# ContactGroup <-> ContactGroupNews 
contact_group_mapper.add_property('news', relation(
    ContactGroupNews,
    primaryjoin=contact_group_news_table.c.contact_group_id==contact_group_table.c.id,
    cascade="all,delete",
    backref='contact_group',
    passive_deletes=True,
    order_by=desc(ContactGroupNews.date)))

print "Alchemy initialized"
