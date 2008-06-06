#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from sqlalchemy import *
from sqlalchemy.orm import *
import sqlalchemy.engine.url
from settings import DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT

FTYPE_TEXT='TEXT'
FTYPE_LONGTEXT='LONGTEXT'
FTYPE_NUMBER='NUMBER'
FTYPE_DATE='DATE'
FTYPE_EMAIL='EMAIL'
FTYPE_RIB='RIB'
FTYPE_CHOICE='CHOICE'
FTYPE_MULTIPLECHOICE='MULTIPLECHOICE'

FIELD_TYPES={
    FTYPE_TEXT: 'Text',
    FTYPE_LONGTEXT: 'Long text',
    FTYPE_NUMBER: 'Number',
    FTYPE_DATE: 'Date',
    FTYPE_EMAIL: 'E.Mail',
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
    #def __init__(self, ):
    def __repr__(self):
        return self.name

    @property
    def ordered_choices(self):
        "Utility property to get choices tuples in correct order"
            
        q = Query(Choice)
        q = q.filter(choice_table.c.choice_group_id==self.id)
        q = q.filter(choice_table.c.key=='')
        
        result = [('', 'Unknown')] # default
        for c in q[0:]:
            result = [('', c.value)] # overwrite default

        q = Query(Choice)
        q = q.filter(choice_table.c.choice_group_id==self.id)
        q = q.filter(choice_table.c.key!='')
        if self.sort_by_key:
            q = q.order_by([choice_table.c.key])
        else:
            q = q.order_by([choice_table.c.value])
        
        for c in q:
            result += [(c.key, c.value)]
        #print "result=", result
        return result

    @property
    def ordered_choices_no_default(self):
        "Utility property to get choices tuples in correct order"
            
        q = Query(Choice)
        q = q.filter(choice_table.c.choice_group_id==self.id)
        q = q.filter(choice_table.c.key!='')
        if self.sort_by_key:
            q = q.order_by([choice_table.c.key])
        else:
            q = q.order_by([choice_table.c.value])
        
        return [(c.key, c.value) for c in q]


class Contact(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    def str_member_of(self, gids):
        gid = gids[0]
        if select([contact_in_group_table], whereclause=and_(contact_in_group_table.c.contact_id==self.id, contact_in_group_table.c.group_id==gid)).execute().fetchone():
            return "Yes"
        elif select([contact_in_group_table], whereclause=and_(contact_in_group_table.c.contact_id==self.id, contact_in_group_table.c.group_id.in_(gids))).execute().fetchone(): 
            return "Yes"+" "+AUTOMATIC_MEMBER_INDICATOR
        else:
            return "No"

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

    def _get_members(self):
        gids = [ ]
        for g in self.self_and_subgroups:
            gids.append(g.id)
        #print "gids=", gids
        #s = select([contact_in_group_table], contact_in_group_table.c.group_id.in_(gids))
        #print "members=", s, ":"
        #for c in Session.execute(s):
        #    print c
        s = select([contact_in_group_table.c.contact_id], contact_in_group_table.c.group_id.in_(gids)).distinct()
        #print "members=", s, ":"
        result =  []
        for cid in Session.execute(s):
            result.append(Query(Contact).get(cid[0]))
            #print cid[0]
        return result

    members = property(_get_members)


class ContactField(object):
    def __repr__(self):
        return self.name

    def repr_type(self):
        type = FIELD_TYPES[self.type]
        if self.type in (FTYPE_CHOICE, FTYPE_MULTIPLECHOICE):
            type += " ("+self.choice_group.name+")"
        return type

class ContactFieldValue(object):
    def __unicode__(self):
        cf = self.field
        if cf.type in (FTYPE_TEXT, FTYPE_LONGTEXT, FTYPE_NUMBER, FTYPE_DATE, FTYPE_EMAIL, FTYPE_RIB):
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
 


#class ContactInGroup(object):
#    def __repr__(self):
#        return "ContactInGroup<%s,%s>"%(self.contact_id, self.group_id)
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

# ContactGroup <-> Contact
contact_mapper.add_property('direct_groups', relation(
    ContactGroup,
    secondary=contact_in_group_table,
    lazy=True,
    cascade="none",
    backref='direct_contacts',
    passive_deletes=True))

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

