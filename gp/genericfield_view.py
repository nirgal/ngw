# -*- encoding: utf8 -*-

import copy
from pprint import pprint
from django.http import *
from django.core.urlresolvers import reverse
from django import newforms as forms
from django.shortcuts import render_to_response
from dj2.gp.models import *

ROOTGROUP_CONTACT=9
GROUP_PREFIX = '_group_'

def index(request):
    return render_to_response('index.html', {
        'title':'Action DB',
        'ncontacts': Contact.objects.count(),
    })

def contact_list(request):
    if request.GET.has_key('select'):
        select = request['select']
        fields = [ 'name' ] + select.split(',')
    else:
        fields = ['name', 'email', 'city', 'birthdate', 'sex', 'GL', '_group_1', '_group_12']

    return show_contactist(fields)


def show_contactist(fields):
    objs = Contact.objects.order_by('name')
    keys = []
    subgroups = {} 
    for prop in fields:
        if prop.startswith(GROUP_PREFIX):
            groupid = int(prop[len(GROUP_PREFIX):])
            cg = ContactGroup.objects.get(pk=groupid)
            keys.append(cg.name)
            subgroups[groupid] = [ g.id for g in cg.self_and_subgroups() ]
        else:
            keys.append(prop)
        
    values = []
    for o in objs:
        newline = [  o.id ]
        for prop in fields:
            if prop == 'name':
                newline.append(o.name)
            elif prop.startswith(GROUP_PREFIX):
                groupid = int(prop[len(GROUP_PREFIX):])
                if o.groups.filter(id=groupid).count()>=1:
                    newline.append("True")
                elif o.groups.filter(id__in=subgroups[groupid]).count()>=1:
                    newline.append("True ⁂")
                else:
                    newline.append("False")
            else:
                xf = XField.objects.get(name=prop)
                if xf.contact_group and xf.contact_group not in get_contacttypes(o):
                    newline.append( "N/A" )
                else:
                    try:
                        rawvalue = XFValue.objects.get(contact__id=o.id, xfield__name=prop).value
                    except XFValue.DoesNotExist:
                        rawvalue = ""
                    if xf.type == 'M':
                        Choice.objects.get(choice_group=xf.choicegroup, key=rawvalue)
                        newline.append( Choice.objects.get(choice_group=xf.choicegroup, key=rawvalue).value )

                    else:
                        newline.append( rawvalue  )
                
        values.append( newline )

    return render_to_response('list_contact.html', {'title': "Select a contact", 'objtypename':'contact', 'keys':keys, "values": values})



class ContactSearchLine:
    def __init__(self, name, label, checked=False):
        self.name = name
        self.label = label
        self.checked = checked
    
    def as_html(self):
        id = "id_" + self.name
        if self.checked:
            checked_str = "checked "
        else:
            checked_str = ""
        output = ""
        output += '<td><input type="checkbox" name="'+self.name+'" id="'+id+'" value="on" '+checked_str+'/>'
        output += '<th><label for="'+id+'">'+self.label+'</label>'
        output += '<td><select disabled><option value="EQ">=</option><option value="NEQ">!=</option></select>\n'
        output += '<td><input type=text disabled>\n'
        return output
        
    def javascript_checkme(self):
        return 'document.forms[0]["'+self.name+'"].checked = 1;'
        
        
class ContactSearchForm:
    def __init__(self):
        self.lines = []

        # Add name field, default to true
        self.lines.append(ContactSearchLine('name', 'name', True))
        # Add all extra fields
        for xf in XField.objects.order_by('sort_weigth'):
            self.lines.append(ContactSearchLine(xf.name, xf.name))
        # Add all groups
        for g in ContactGroup.objects.exclude(name__startswith='_'):
            self.lines.append(ContactSearchLine(GROUP_PREFIX + str(g.id), g.name + " group"))
    
    
def contact_search(request):
    if request.method == 'POST':
        print request.raw_post_data
        fields = []
        print request.raw_post_data
        for kv in request.raw_post_data.split("&"):
            k,v = kv.split('=',1)
            print k,v
            fields.append(k)
        return show_contactist(fields)

    objtypename = "contact";
    title = "Searching "+objtypename+"s"
    form = ContactSearchForm()
    return render_to_response('search.html', { 'title':title, 'objtypename':objtypename, 'form':form})



def get_contacttypes(contact):
    """
    Returns all the groups of that contact.
    That's usefull to know which fields are in use.
    """

    root_contacttype = ContactGroup.objects.get(pk=ROOTGROUP_CONTACT)
    contacttypeallids = [g.id for g in root_contacttype.self_and_subgroups() ]
    
    #print "allids=", contacttypeallids
    contacttype_direct = contact.groups.filter(id__in=contacttypeallids)
    result = []
    for g in contacttype_direct:
        for sg in g.self_and_supergroups():
            if sg not in result:
                #print g, "=>", sg
                result.append(sg)
    return result

class ContactEditForm(forms.Form):
    name = forms.CharField()

    def __init__(self, contactid=None, data=None, auto_id='id_%s', prefix=None, initial=None, default_group=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)

        if contactid:
            contact = Contact.objects.get(pk=contactid)
            contactgroupids = [ g.id for g in get_contacttypes(contact)] 
        elif default_group:
            contactgroupids = [ g.id for g in ContactGroup.objects.get(pk=default_group).self_and_supergroups()] 
            self.fields['default_group'] = forms.CharField(widget=forms.HiddenInput())
        else:
            contactgroupids = [ ]


        # Add all extra fields
        for xf in XField.objects.order_by('sort_weigth'):
            if xf.contact_group_id:
                if xf.contact_group_id not in contactgroupids:
                    continue # some fields are excluded
            if xf.type=='C':
                self.fields[xf.name] = forms.CharField(max_length=255, required=False, help_text=xf.hint)
            elif xf.type=='T':
                self.fields[xf.name] = forms.CharField(widget=forms.Textarea, required=False, help_text=xf.hint)
            elif xf.type=='B':
                self.fields[xf.name] = forms.NullBooleanField(help_text=xf.hint)
            elif xf.type=='I':
                self.fields[xf.name] = forms.IntegerField(required=False, help_text=xf.hint)
            elif xf.type=='M':
                choices = [ (c.key, c.value) for c in Choice.objects.filter(choice_group=xf.choicegroup) ]

                self.fields[xf.name] = forms.CharField(max_length=255, required=False, help_text=xf.hint, widget=forms.Select(choices=choices))
        
        def contactgroupchoices():
            return [ (g.id, g.name) for g in ContactGroup.objects.exclude(name__startswith='_')]

        self.fields['groups'] = forms.MultipleChoiceField(required=False, choices=contactgroupchoices())
        

def contact_edit(request, id):
    objtypename = "contact";
    if id:
        title = "Changing a "+objtypename
    else:
        title = "Adding a new "+objtypename
    if request.method == 'POST':
        if 'default_group' in request.POST:
            default_group = request.POST['default_group']
        else:
            default_group = None
        form = ContactEditForm(id, request.POST, default_group=default_group)
        if form.is_valid():
            # print "saving", repr(form.data)

            # record the values

            # 1/ In contact

            if id:
                contact = Contact.objects.get(pk=id)
                contactgroupids = [ g.id for g in get_contacttypes(contact)]  # Need to keep a record of initial groups
            else:
                contact = Contact()
                contactgroupids = form.clean().get('default_group', [])

            contact.name = form.data['name']

            newgroups = form.clean().get('groups', [])
            if id:
                contact.save()
                contact.groups = newgroups
            else:
                contact.save() # need to create the contact before setting groups
                contact.groups = newgroups
                contact.save()
            
            # 2/ In XFields
            for xf in XField.objects.all():
                if xf.contact_group_id and xf.contact_group_id not in contactgroupids:
                    continue
                else:
                    pass #TODO delete obsolete fields?
                xfname = xf.name
                xfid = xf.id
                try:
                    xfv = XFValue.objects.get(contact=id, xfield=xf)
                except XFValue.DoesNotExist:
                    xfv = XFValue(contact=contact, xfield=xf, value="")
                newvalue = form.data[xfname]
                if xf.type=='C' or xf.type=='T' or xf.type=='M':
                    newvalue = newvalue
                elif xf.type=='B':
                    newvalue = newvalue # db keep the system 1:Unknown 2:True, 3:False
                elif xf.type=='I':
                    newvalue = newvalue # store as a string for now
                xfv.value = newvalue
                xfv.save()
            return HttpResponseRedirect(reverse('dj2.gp.views.contact_list')) # args=(p.id,)))
        # else /new/ or /change/ failed validation
    else: # GET /  HEAD
        initialdata = {}
        if id: # modify existing
            contact = Contact.objects.select_related().get(pk=id)
            initialdata['groups'] = [ group.id for group in contact.groups.all() ]
            initialdata['name'] = contact.name
            form = ContactEditForm(id, initialdata)

            for xfv in XFValue.objects.filter(contact=contact):
                xf = xfv.xfield
                if xf.type=='C' or xf.type=='T' or xf.type=='M':
                    form.data[xf.name] = xfv.value
                elif xf.type=='B':
                    form.data[xf.name] = xfv.value
                elif xf.type=='I':
                    form.data[xf.name] = xfv.value
        else:
            if 'default_group' in request.GET:
                default_group = request.GET['default_group']
                initialdata['default_group'] = default_group
                initialdata['groups'] = [ int(default_group) ]
                form = ContactEditForm(id, initial=initialdata, default_group=default_group )
            else:
                form = ContactEditForm(id)

    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})
    
def contact_delete(request, id):
    contact = Contact.objects.get(pk=id)
    contact.delete()
    return HttpResponseRedirect(reverse('dj2.gp.views.contact_list')) # args=(p.id,)))



#######################################################################
#
# Fields
#
#######################################################################

def field_list(request):
    keys = [
        'name',
        'type',
        'only_for',
        'sort_weigth',
    ]
    values = []
    for xf in XField.objects.order_by('sort_weigth'):
        values += [(
            xf.id,
            xf.name,
            FIELD_TYPES[xf.type],
            xf.contact_group and xf.contact_group.name or "Everyone",
            xf.sort_weigth,
        )]
    return render_to_response('list.html', {'title': "Select an optionnal field", 'objtypename':'field', 'keys': keys, 'values':values })



def field_edit(request, id):
    objtypename = "field"
    if id:
        title = "Changing a "+objtypename
    else:
        title = "Adding a new "+objtypename
    
    def patchForm(form):
        form.fields['type'].widget = forms.Select(choices=FIELD_TYPE_CHOICES)
        form.fields['type'].widget.attrs = { "onchange": "if (this.value=='M') { document.forms[0]['choicegroup'].disabled = 0; } else { document.forms[0]['choicegroup'].value = ''; document.forms[0]['choicegroup'].disabled = 1; }" }

        contacttypes = ContactGroup.objects.get(pk=ROOTGROUP_CONTACT).subgroups()[1:] # skip root   
        form.fields['contact_group'].widget.choices = [('', 'Everyone')] + [ (g.id, g.name) for g in contacttypes ]
        
        t = form.data.get("type", "") or form.fields['type'].initial
        if t != 'M':
            form.fields['choicegroup'].widget.attrs['disabled'] = 1
        form.fields['choicegroup'].required = False

        # TODO choicegroup is required is t=='M'
        #def ccustomclean(self):
        #    return self.clean_data

        #form.clean = ccustomclean


    if id:
        xf = XField.objects.get(pk=id)
        XFieldForm = forms.form_for_instance(xf)
    else: # add new one
        XFieldForm = forms.form_for_model(XField)

    if request.method == 'POST':
        form = XFieldForm(request.POST)
        patchForm(form)
        if form.is_valid():
            # TODO check new values are compatible with actual XFValues
            form.save()
            return HttpResponseRedirect(reverse('dj2.gp.views.field_list')) # args=(p.id,)))
    else:
        form = XFieldForm()
        patchForm(form)
        if not id:
            form.initial['sort_weigth'] = 300


    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})


def field_delete(request, id):
    xf = XField.objects.get(pk=id)
    xf.delete()
    return HttpResponseRedirect(reverse('dj2.gp.views.field_list')) # args=(p.id,)))
    

#######################################################################
#
# Contact groups
#
#######################################################################

def contactgroup_list(request):
    keys = [
        'name',
        'members',
        'description',
    ]
    values = []
    def addgroup(cg, values, level=0):
        print cg
        values += [(
            cg.id,
            unichr(160)*level*3+cg.name,
            str(len(cg.members_all()))+"&nbsp;("+str(cg.contact_set.count())+"&nbsp;direct)",
            cg.description,
        )]
        for cg_sub in ContactGroup.objects.filter(parent=cg):
            addgroup(cg_sub, values, level+1)
    for cg in ContactGroup.objects.filter(parent__isnull=True):
        addgroup(cg, values)

    return render_to_response('list.html', {'title': "Select a contact group", 'objtypename':'contactgroup','keys':keys, 'values': values})


class ContactGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
    description = forms.CharField(required=False, widget=forms.Textarea)
    parent_group = forms.IntegerField(required=False, widget=forms.Select(), help_text="Members will automatically be granted membership of that group.")
    direct_members = forms.MultipleChoiceField(required=False,) # help_text="⁂ = Indirect member")

    def __init__(self, data=None, auto_id='id_%s', prefix=None, initial=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)
        
        def memberchoices():
            return 

        self.fields['parent_group'].widget.choices = [('','Internal')] + [ (g.id, g.name) for g in ContactGroup.objects.all() ]
        self.fields['direct_members'].choices = [ (g.id, g.name) for g in Contact.objects.order_by('name')]

    def flag_inherited_members(self, g):
        choices = []
        subgroups = g.subgroups()
        for c in Contact.objects.order_by('name'):
            automember = False
            for sg in subgroups:
                if Contact.objects.filter(id=c.id, groups__id=sg.id):
                    automember = True
                    break
            flagname = c.name
            if automember:
                flagname += " ⁂"
            choices.append( (c.id, flagname) )

        self.fields['direct_members'].choices = choices
        self.fields['direct_members'].help_text = u"⁂ = Automatic members from " + ", ".join([ sg.name+" ("+str(len(sg.members_all()))+")" for sg in g.subgroups() ]),

def contactgroup_edit(request, id):
    objtypename = "contactgroup"
    if id:
        title = "Changing a "+objtypename
    else:
        title = "Adding a new "+objtypename
    
    if request.method == 'POST':
        form = ContactGroupForm(request.POST)
        if form.is_valid():
            # record the values

            if id:
                cg = ContactGroup.objects.get(pk=id)
            else:
                cg = ContactGroup()
            cg.name = form.data['name']
            cg.description = form.data['description']
            cg.parent_id = form.clean()['parent_group']
            cg.contact_set = form.clean()['direct_members']
            cg.save()
            
            return HttpResponseRedirect(reverse('dj2.gp.views.contactgroup_list')) # args=(p.id,)))

    else: # GET
        if id:
            cg = ContactGroup.objects.get(pk=id)
            initialdata = {
                'name': cg.name,
                'description': cg.description,
                'parent_group': cg.parent_id,
                'direct_members': [ c.id for c in cg.members_direct() ],
            }
            
            form = ContactGroupForm(initialdata)
            form.flag_inherited_members(cg)
        else: # add new one
            form = ContactGroupForm()
    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})


def contactgroup_delete(request, id):
    contact = ContactGroup.objects.get(pk=id)
    contact.delete()
    return HttpResponseRedirect(reverse('dj2.gp.views.contactgroup_list')) # args=(p.id,)))



#######################################################################
#
# Choice groups
#
#######################################################################
def choicegroup_list(request):
    keys = [
        'name',
        'choices',
    ]
    values = []
    for cg in ChoiceGroup.objects.all():
        values += [(
            cg.id,
            cg.name,
            ", ".join([c.value for c in cg.choice_set.all()]),
        )]
    return render_to_response('list.html', {'title': "Select a choice group", 'objtypename':'choicegroup', 'keys': keys, 'values':values })


class ChoicesField(forms.MultiValueField):
    def __init__(self, ndisplay, *args, **kwargs):
        fields = []
        for i in range(ndisplay):
            fields.append(forms.CharField())
        super(ChoicesField, self).__init__(fields, *args, **kwargs)
        self.ndisplay = ndisplay
    def compress(self, data_list):
        if data_list:
            return ",".join(data_list)
        return None

class ChoicesWidget(forms.MultiWidget):
    def __init__(self, ndisplay, attrs=None):
        widgets = []
        for i in range(ndisplay):
            widgets.append(forms.TextInput(attrs=attrs))
        super(ChoicesWidget, self).__init__(widgets, attrs)
        self.ndisplay = ndisplay
    def decompress(self, value):
        if value:
            return value.split(",")
        nonelist = []
        for i in range(self.ndisplay):
            nonelist.append(None)
        return nonelist

class ChoiceGroupForm(forms.Form):
    name = forms.CharField(max_length=255)
#    default_value = forms.CharField(max_length=255)
    sort_by_key = forms.BooleanField()

    def __init__(self, cg=None, data=None, auto_id='id_%s', prefix=None, initial=None):
        forms.Form.__init__(self, data, auto_id, prefix, initial)
        nextra_display=3
        
        if cg:
            self.initial['name'] = cg.name
#            self.initial['default_value'] = cg.default_value
            self.initial['sort_by_key'] = cg.sort_by_key
            self.initial['possible_values']=[]
            ndisplay=0
            for c in cg.choice_set.order_by('value'):
                self.initial['possible_values'].append(c.value)
                ndisplay+=1
            for i in range(nextra_display):
                self.initial['possible_values'].append("")
                ndisplay+=1
        else:
            ndisplay=nextra_display
        self.fields['possible_values'] = ChoicesField(required=False, widget=ChoicesWidget(ndisplay=ndisplay), ndisplay=ndisplay)

    def save(self, cg):
        if cg:
            oldid = cg.id
        else:
            cg = ChoiceGroup()
            oldid = None
        cg.name = self.clean()['name']
#        cg.default_value = self.clean()['default_value']
        cg.sort_by_key = self.clean()['sort_by_key']
        cg.save()
        #newvalue = self.clean().get('newvalue_1', None)
        #if newvalue:
        #    Choice(choice_group=cg, value=newvalue).save()
           
        
def choicegroup_edit(request, id=None):
    objtypename = "choicegroup"
    if id:
        title = "Changing a "+objtypename
        cg = ChoiceGroup.objects.get(pk=id)
    else:
        title = "Adding a new "+objtypename
        cg = None

    if request.method == 'POST':
        form = ChoiceGroupForm(cg, request.POST)
        if form.is_valid():
            form.save(cg)
            return HttpResponseRedirect(reverse('dj2.gp.views.choicegroup_list')) # args=(p.id,)))
    else:
        form = ChoiceGroupForm(cg)

    return render_to_response('edit.html', {'form': form, 'title':title, 'id':id, 'objtypename':objtypename,})


def choicegroup_delete(request, id):
    cg = ChoiceGroup.objects.get(pk=id)
    cg.delete()
    return HttpResponseRedirect(reverse('dj2.gp.views.choicegroup_list')) # args=(p.id,)))
    
