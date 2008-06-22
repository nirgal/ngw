#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from sqlalchemy import *
from sqlalchemy.orm import *
import sqlalchemy.engine.url
from django.utils import html
from settings import DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT

FTYPE_TEXT='TEXT'
FTYPE_LONGTEXT='LONGTEXT'
FTYPE_NUMBER='NUMBER'
FTYPE_DATE='DATE'
FTYPE_EMAIL='EMAIL'
FTYPE_PHONE='PHONE'
FTYPE_RIB='RIB'
FTYPE_CHOICE='CHOICE'
FTYPE_MULTIPLECHOICE='MULTIPLECHOICE'

FIELD_TYPES={
    FTYPE_TEXT: 'Text',
    FTYPE_LONGTEXT: 'Long text',
    FTYPE_NUMBER: 'Number',
    FTYPE_DATE: 'Date',
    FTYPE_EMAIL: 'E.Mail',
    FTYPE_PHONE: 'Phone',
    FTYPE_RIB: 'Bank account',
    FTYPE_CHOICE: 'Choice',
    FTYPE_MULTIPLECHOICE: 'Multiple choice',
}
FIELD_TYPE_CHOICES = FIELD_TYPES.items() # TODO: sort
AUTOMATIC_MEMBER_INDICATOR = u"⁂"

dburl = sqlalchemy.engine.url.URL("postgres", DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT or None, DATABASE_NAME)
engine = create_engine(dburl, convert_unicode=True) #, echo=True)

Session = scoped_session(sessionmaker(bind=engine, autoflush=True, transactional=True))
meta = MetaData(engine)
mapper = Session.mapper

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

########################################################################
# Define classes to be mapped to the above tables.
# Most properties are fetched from the database, and autodeclared
########################################################################
class Choice(object):
    def __init__(self, key, value):
        self.key = key
        self.value = value

class ChoiceGroup(object):
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

    @property
    def ordered_choices_with_unknown(self):
        """"
        Utility property to get choices tuples in correct order, with extra Unknown key
        """
        return [('', u"Unknown")] + self.ordered_choices

    def get_link(self):
        return u"/choicegroups/"+str(self.id)+"/edit"
    get_link_name = get_link


class Contact(object):
    def __init__(self, name):
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
            if cig.member:
                return "Member"
            elif cig.invited:
                return "Invited"
            else:
                return "ERROR: not member and not invited"

        elif select([contact_in_group_table], whereclause=and_(contact_in_group_table.c.contact_id==self.id, contact_in_group_table.c.group_id.in_(gids))).execute().fetchone(): 
            return "Member"+" "+AUTOMATIC_MEMBER_INDICATOR
        else:
            return ""

    def get_link(self):
        return u"/contacts/"+str(self.id)+"/"
    get_link_name = get_link

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

    def get_cfv_by_keyname(self, keyname):
        cf = Query(ContactField).filter(ContactField.c.name == keyname).one()
        if not cf:
            return None
        cfv = Query(ContactFieldValue).get((self.id, cf.id))
        return cfv

    def get_value_by_keyname(self, keyname):
        cf = Query(ContactField).filter(ContactField.c.name == keyname).one()
        if not cf:
            return u"ERROR: no field named "+keyname
        cfv = Query(ContactFieldValue).get((self.id, cf.id))
        if cfv == None:
            return u"" # FIXME need default for choices
        return unicode(cfv)

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

        street = self.get_value_by_keyname("street")
        postal_code = self.get_value_by_keyname("postal_code")
        city = self.get_value_by_keyname("city")
        country = self.get_value_by_keyname("country")
        vcf += line(u"ADR", u";;"+street+u";"+city+u";;"+postal_code+u";"+country)

        for pfield in ('tel_mobile', 'tel_prive', 'tel_professionel'):
            phone = self.get_value_by_keyname(pfield)
            vcf += line(u"TEL", phone)

        email = self.get_value_by_keyname("email")
        if email:
            vcf += line(u"EMAIL", email)

        vcf += line(u"END", u"VCARD")
        return vcf
    

    def get_addr_semicol(self):
        return self.get_value_by_keyname("street")+u";"+self.get_value_by_keyname("city")+u";"+self.get_value_by_keyname("country")

    def get_and_delete_messages(self):
        """
        That function is called by django ContextProcessor auth.
        """
        return u""

class ContactGroup(object):
    def __repr__(self):
        return self.name

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
    get_link_name = get_link

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


class ContactField(object):
    def __repr__(self):
        return "ContactField<"+self.name.encode('utf-8')+">"

    def __unicode__(self):
        return self.name

    def type_as_html(self):
        type = FIELD_TYPES[self.type]
        if self.type in (FTYPE_CHOICE, FTYPE_MULTIPLECHOICE):
            type += " (<a href='"+self.choice_group.get_link()+"'>"+html.escape(self.choice_group.name)+"</a>)"
        return type

    def get_link(self):
        return u"/contactfields/"+str(self.id)+"/edit"
    get_link_name = get_link


class ContactFieldValue(object):
    def __repr__(self):
        return 'ContactFieldValue<"'+unicode(self.contact).encode("utf-8")+'", "'+unicode(self.field).encode('utf-8')+'", "'+unicode(self).encode('utf-8')+'">'

    def __unicode__(self):
        cf = self.field
        if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_NUMBER, FTYPE_DATE, FTYPE_EMAIL, FTYPE_PHONE, FTYPE_RIB):
            return self.value
        elif cf.type == FTYPE_CHOICE:
            chg = cf.choice_group
            if chg == None:
                return u"Error"
            c = Query(Choice).get((chg.id, self.value))
            if c == None:
                return u"Error"
            else:
                return c.value
        elif cf.type == FTYPE_MULTIPLECHOICE:
            chg = cf.choice_group
            if chg == None:
                return u"Error"
            txt_choice_list = []
            for cid in self.value.split(u","):
                if cid==u"":
                    txt_choice_list.append( "default" ) # this should never occur
                    continue
                c = Query(Choice).get((chg.id, cid))
                if c == None:
                    txt_choice_list.append( "error" )
                else:
                    txt_choice_list.append( c.value )
            return u", ".join(txt_choice_list)
        else:
            raise Exception("Unsuported field type "+cf.type)
 
    def get_link_value(self):
        t = self.field.type
        if t==FTYPE_EMAIL:
            return u"mailto:"+self.value
        elif t==FTYPE_PHONE: # rfc3966
            return u"tel:"+self.value
        return u""

    def str_print(self):
        result = unicode(self)
        link = self.get_link_value()
        if link:
            result =  u'<a href="'+link+'">'+result+'</a>'
        return result

class ContactInGroup(object):
    def __init__(self, contact_id, group_id):
        self.contact_id = contact_id
        self.group_id = group_id

    def __repr__(self):
        return "ContactInGroup<%s,%s>"%(self.contact_id, self.group_id)
#mapper(ContactInGroup,
#    contact_in_group_table, properties={ \
##    'choices': relation(Choice, primaryjoin=choice_table.c.choice_group_id==choice_group_table.c.id, cascade="save, update, merge, expunge, refresh, delete, expire"),
#})

########################################################################
# Map the class to the tables
########################################################################
choice_mapper=mapper(Choice, choice_table)
choice_group_mapper = mapper(ChoiceGroup, choice_group_table)
contact_mapper = mapper(Contact, contact_table)
contact_group_mapper = mapper(ContactGroup, contact_group_table)
contact_in_group_mapper = mapper(ContactInGroup, contact_in_group_table)
contact_field_mapper = mapper(ContactField, contact_field_table)
contact_field_value_mapper = mapper(ContactFieldValue, contact_field_value_table)

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

