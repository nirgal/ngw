# -*- encoding: utf8 -*-

from django.db import models

class Contact(models.Model):
    name = models.TextField()
    groups = models.ManyToManyField('ContactGroup')
    def __str__(self):
        return self.name

    def groups_all(self):
        """
        All groups that contact is a group of, including indirect groups
        return dict of ( group, is_aotomatic)
        """

        result = {}
        for g in self.groups.all():
            result[g] = False
        for g in self.groups.all():
            g2 = g.parent
            while g2:
                if g2 not in result.keys():
                    result[g2] = True
                g2 = g2.parent
        return result
    class Admin:
        list_display = ( 'name', )

class ContactGroup(models.Model):
    name = models.CharField(maxlength=255)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('ContactGroup', null=True)
    def __str__(self):
        return self.name

    def subgroups(self):
        """ returns a list of all possible subgroups. """
        result = []
        for subgroup in self.contactgroup_set.all():
            result += subgroup.self_and_subgroups()
        return result
    
    def self_and_subgroups(self):
        """ returns a list with self and all possible subgroups. """
        result = [ self ]
        for subgroup in self.contactgroup_set.all():
            result += subgroup.self_and_subgroups()
        return result

        return [ self ] + self.subgroups()
    
    def supergroups(self):
        """ returns a list with all implied super groups. """
        if self.parent:
            return [ self.parent ] + self.parent.supergroups()
        else:
            return []

    def self_and_supergroups(self):
        """ returns a list with self and all implied super groups. """
        result = [ self ]
        if self.parent:
            result += self.parent.self_and_supergroups()
        return result

    def root_ancestor(self):
        """ returns top most ancestor """
        if not self.parent:
            return self
        else:
            return self.parent.root_ancestor()

    def members_direct(self):
        return self.contact_set.all()

    def members_indirect(self):
        direct_members = self.members_direct()
        result = []
        for g in self.subgroups():
            for c in g.contact_set.all():
                if c in direct_members:
                    continue
                if c not in result:
                    result.append( c )
        return result

        return g.contact_set.all()

    def members_all(self):
        result = []
        for g in self.self_and_subgroups():
            for c in g.contact_set.all():
                if c not in result:
                    result.append( c )
        return result
        
    class Admin:
        pass

FIELD_TYPES={
    'C': 'Text',
    'B': 'Boolean',
    'T': 'Long text',
    'I': 'Number',
    'M': 'Choice',
}
FIELD_TYPE_CHOICES = FIELD_TYPES.items()

class XField(models.Model):
    name = models.CharField(maxlength=255)
    hint = models.TextField(blank=True)
    contact_group = models.ForeignKey(ContactGroup, null=True, blank=True)
    type = models.CharField(maxlength=1, choices=FIELD_TYPE_CHOICES)
    choicegroup = models.ForeignKey('ChoiceGroup', null=True, help_text="Only for type Choice")
    sort_weigth = models.IntegerField(default=100)
    def __str__(self):
        return self.name
    class Admin:
        pass


class XFValue(models.Model):
    #table_id (1 for contact...)
    contact = models.ForeignKey(Contact)
    xfield = models.ForeignKey(XField)
    value = models.TextField()
    class Admin:
        pass


class ChoiceGroup(models.Model):
    name = models.CharField(unique=True, maxlength=255)
    sort_by_key = models.BooleanField(default=False)
    def __str__(self):
        return self.name

    def _get_ordered_choices(self):
        "Utility property to get choices tuples in correct order"
        choices = []
        try:
            choices.append(('', self.choice_set.get(key="").value))
        except Choice.DoesNotExist:
            choices.append(('', 'Unknown'))
        set = self.choice_set.exclude(key="")
        if self.sort_by_key:
            set = set.order_by('key')
        else:
            set = set.order_by('value')
        choices += [ (c.key, c.value) for c in set ]
        return choices
    ordered_choices = property(_get_ordered_choices)

    class Admin:
        pass

class Choice(models.Model):
    choice_group = models.ForeignKey(ChoiceGroup, edit_inline=True)
    key = models.CharField(maxlength=255, blank=True)
    value = models.CharField(maxlength=255, core=True)
    def __str__(self):
        return self.value
    class Admin:
        pass
