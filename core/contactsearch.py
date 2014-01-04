# -*- encoding: utf-8 -*-

import urllib2
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.utils import html
from django.template import RequestContext
from django.shortcuts import render_to_response
from ngw.core.basicauth import login_required
from ngw.core.models import ( EmptyBoundFilter, AndBoundFilter, OrBoundFilter,
    ContactField, ContactGroup, ChoiceGroup,
    ContactNameMetaField, AllEventsMetaField, FIELD_FILTERS )
#from ngw.core.views import unauthorized



def no_br(txt):
    " Replaces all spaces by non-breaking spaces"
    return txt.replace(u" ", u"\u00a0")

def format_link_list(l):
    # list is a 3-tupple ( url, display name, dom_id )
    return u"\u00a0| ".join(
        [ u'<a href="%(url)s" id="%(dom_id)s">%(name)s</a>\n' % {'url':url, 'name':name, 'dom_id':dom_id }
          for url, name, dom_id in l])


class LexicalError(StandardError):
    def __init__(self, *args, **kargs):
        StandardError.__init__(self, *args, **kargs)
class FilterSyntaxError(StandardError):
    def __init__(self, *args, **kargs):
        StandardError.__init__(self, *args, **kargs)

class FilterLexer(object):
    """ Trivial parser that recognise a few types, see Type class bellow """
    class Lexem(object):
        class Type(object):
            WORD = 0           # isalpha
            STRING = 1         # 'vbn hjk \' sdds \\ klmjk'
            INT = 2            # isdigit
            LPARENTHESIS = 3   # (
            RPARENTHESIS = 4   # )
            COMMA = 5          # ,

        def __init__(self, type, str):
            self.type = type
            self.str = str

        def __repr__(self):
            types = { 0:"WORD", 1:"STRING", 2:"INT", 3: "LPARENTHESIS", 4: "RPARENTHESIS", 5: "COMMA" }
            return "Lexem<"+types[self.type]+","+self.str.encode('utf8')+">"
            
    def __init__(self, str):
        self.buffer = str
        self.nextpos = 0

    def getchar(self):
        if self.nextpos >= len(self.buffer):
            return None
        c = self.buffer[self.nextpos]
        self.nextpos += 1
        return c

    def goback(self):
        self.nextpos -= 1

    def parse(self):
        while(True):
            c = self.getchar()
            if c == None:
                return
            if c == u"(":
                yield self.Lexem(self.Lexem.Type.LPARENTHESIS, c)
            elif c == u")":
                yield self.Lexem(self.Lexem.Type.RPARENTHESIS, c)
            elif c == u",":
                yield self.Lexem(self.Lexem.Type.COMMA, c)
            elif c == u"'":
                slexem = u""
                while True:
                    c = self.getchar()
                    if c == None:
                        raise LexicalError(u"Unexpected EOS while parsing string")
                    if c == u'\\':
                        c = self.getchar()
                        if c == None:
                            raise LexicalError(u"Unexpected EOS while parsing string after \"\\\"")
                    if c == u"'":
                        yield self.Lexem(self.Lexem.Type.STRING, slexem)
                        break
                    slexem += c

            elif c.isdigit():
                slexem = u""
                while c.isdigit():
                    slexem += c
                    c = self.getchar()
                    if c == None:
                        break
                if c != None:
                    self.goback()
                yield self.Lexem(self.Lexem.Type.INT, slexem)
            elif c.isalpha():
                slexem = u""
                while c.isalpha():
                    slexem += c
                    c = self.getchar()
                    if c == None:
                        break
                if c != None:
                    self.goback()
                yield self.Lexem(self.Lexem.Type.WORD, slexem)
            else:
                raise LexicalError(u"Unexpected character")


def filter_parse_expression(lexer):
    try:
        lexem = lexer.next()
    except StopIteration:
        return EmptyBoundFilter()

    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == u"and":
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        subfilter1 = filter_parse_expression(lexer)

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")
        
        subfilter2 = filter_parse_expression(lexer)

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.RPARENTHESIS:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ')'.")
        
        return AndBoundFilter(subfilter1, subfilter2)


    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == u"or":
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        subfilter1 = filter_parse_expression(lexer)

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")
        
        subfilter2 = filter_parse_expression(lexer)

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.RPARENTHESIS:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ')'.")
        
        return OrBoundFilter(subfilter1, subfilter2)


    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == u"ffilter":
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.INT:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected INT.")
        field_id = int(lexem.str)

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")
        
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected word.")
        field_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")

            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        field = ContactField.objects.get(pk=field_id)
        filter = field.get_filter_by_name(field_filter_name)
        return filter.bind(*params)

    elif lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == u"gfilter":
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.INT:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected INT.")
        group_id = int(lexem.str)

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")
        
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected word.")
        group_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")

            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        filter = ContactGroup.objects.get(pk=group_id).get_filter_by_name(group_filter_name)
        return filter.bind(*params)

    elif lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == u"nfilter":
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected word.")
        name_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")

            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        filter = ContactNameMetaField.get_filter_by_name(name_filter_name)
        return filter.bind(*params)

    elif lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == u"allevents":
        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        lexem = lexer.next()
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected word.")
        allevents_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")

            lexem = lexer.next()
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        filter = AllEventsMetaField.get_filter_by_name(allevents_filter_name)
        return filter.bind(*params)

    else:
        raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8'))
    

def filter_parse_expression_root(lexer):
    exp = filter_parse_expression(lexer)
    try:
        lexem = lexer.next()
    except StopIteration:
        return exp
    else:
        raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u" after end of string.")



def parse_filterstring(sfilter):
    #print "Parsing", sfilter
    return filter_parse_expression_root(FilterLexer(sfilter).parse())

    




@login_required()
def editfilter(request):
    if not request.user.is_admin():
        return unauthorized(request)
    filter = parse_filterstring(u'')
    return render_to_response('filter.html', {'filter_html':mark_safe(filter.to_html())}, RequestContext(request))


@login_required()
def contactsearch_get_fields(request, kind):
    if not request.user.is_admin():
        return unauthorized(request)
    
    body = u""
    if kind == u"field":
        body += u"Add a field: "
        body += format_link_list([(u"javascript:select_field('name')", u"Name", u"field_name")]+[ (u"javascript:select_field('field_"+unicode(cf.id)+"')", no_br(html.escape(cf.name)), u"field_field_"+unicode(cf.id)) for cf in ContactField.objects.order_by('sort_weight')])
    elif kind == u"group":
        body += u"Add a group: "
        body += format_link_list([ (u"javascript:select_field('group_"+unicode(cg.id)+"')", no_br(cg.unicode_with_date()), u"field_group_"+unicode(cg.id)) for cg in ContactGroup.objects.filter(date=None)])
    elif kind == u"event":
        body += u"Add an event: "
        body += format_link_list(
            [ (u"javascript:select_field('allevents')", no_br('All events'), u"field_allevents") ] +
            [ (u"javascript:select_field('group_"+unicode(cg.id)+"')", no_br(cg.unicode_with_date()), u"field_group_"+unicode(cg.id)) for cg in ContactGroup.objects.exclude(date=None)])
    elif kind == u"custom":
        body += u"Add a custom filter: "
        body += format_link_list([ (u"javascript:select_field('custom_user')", u"Custom filters for "+request.user.name, u'field_custom_user')])
    else:
        body += u"ERROR in get_fields: kind=="+kind
    return HttpResponse(body)

def parse_filter_list_str(txt):
    list = txt.split(u',')
    for idx in xrange(len(list)-1, 0, -1):
        if list[idx-1][-1] != u'"' or list[idx][0] != u'"':
            #print "merging elements ", idx-1, "and", idx, "of", repr(list)
            list[idx-1] += u"," + list[idx]
            del list[idx]
    for idx in xrange(len(list)):
        assert(list[idx][0] == u'"')
        assert(list[idx][-1] == u'"')
        list[idx] = list[idx][1:-1]
    assert(len(list)%2 == 0)
    return [ (list[2*i], list[2*i+1]) for i in range(len(list)/2) ]
    

@login_required()
def contactsearch_get_filters(request, field):
    if not request.user.is_admin():
        return unauthorized(request)
    
    body = u""
    if field == u"name":
        body += u"Add a filter for name : "
        body += format_link_list([ (u"javascript:select_filtername('"+filter.internal_name+u"')", no_br(filter.human_name), u"filter_"+filter.internal_name) for filter in ContactNameMetaField.get_filters() ])

    elif field.startswith(u"field_"):
        field_id = int(field[len(u"field_"):])
        field = ContactField.objects.get(pk=field_id)
        body += u"Add a filter for field of type "+field.human_type_id+u" : "
        body += format_link_list([ (u"javascript:select_filtername('"+filter.internal_name+u"')", no_br(filter.human_name), u"filter_"+filter.internal_name) for filter in field.get_filters() ])

    elif field.startswith(u"group_"):
        group_id = int(field[len(u"group_"):])
        group = ContactGroup.objects.get(pk=group_id)
        body += u"Add a filter for group/event : "
        body += format_link_list([ (u"javascript:select_filtername('"+filter.internal_name+u"')", no_br(filter.human_name), u"filter_"+filter.internal_name) for filter in group.get_filters() ])

    elif field.startswith(u"allevents"):
        body += u"Add a filter for all events : "
        body += format_link_list([ (u"javascript:select_filtername('"+filter.internal_name+u"')", no_br(filter.human_name), u"filter_"+filter.internal_name) for filter in AllEventsMetaField.get_filters() ])

    elif field.startswith(u"custom"):
        filter_list_str = request.user.get_fieldvalue_by_id(FIELD_FILTERS)
        if not filter_list_str:
            body += u"No custom filter available"
        else:
            filter_list = parse_filter_list_str(filter_list_str)
            #body += u"Not implemented"
            body += u"Select a custom filter : "
            body += format_link_list([ (u"javascript:select_filtername('"+unicode(i)+u"')", no_br(filter[0]), u"usercustom_"+unicode(i)) for i, filter in enumerate(filter_list) ])
    else:
        body += u"ERROR in get_filters: field=="+field
    
    return HttpResponse(body)


@login_required()
def contactsearch_get_params(request, field, filtername):
    if not request.user.is_admin():
        return unauthorized(request)
    
    previous_filter = request.GET.get("previous_filter", u"")
    filter = None

    if field == u"name":
        filter = ContactNameMetaField.get_filter_by_name(filtername)
        filter_internal_beginin = u"nfilter("

    elif field.startswith(u"field_"):
        field_id = int(field[len(u"field_"):])
        field = ContactField.objects.get(pk=field_id)
        filter = field.get_filter_by_name(filtername)
        filter_internal_beginin = u"ffilter("+unicode(field_id)+u","

    elif field.startswith(u"group_"):
        group_id = int(field[len(u"group_"):])
        group = ContactGroup.objects.get(pk=group_id)
        filter = group.get_filter_by_name(filtername)
        filter_internal_beginin = u"gfilter("+unicode(group_id)+u","

    elif field == u"allevents":
        filter = AllEventsMetaField.get_filter_by_name(filtername)
        filter_internal_beginin = u"allevents("

    elif field == u"custom_user":
        pass
    else:
        return HttpResponse(u"ERROR: field "+field+" not supported")


    body = u""

    if field == u"custom_user":
        filter_list_str = request.user.get_fieldvalue_by_id(FIELD_FILTERS)
        if not filter_list_str:
            return HttpResponse(u"ERROR: no custom filter for that user")
        else:
            filter_list = parse_filter_list_str(filter_list_str)
        try:
            filterstr = filter_list[int(filtername)][1]
        except (IndexError, ValueError):
            return HttpResponse(u"ERROR: Can't find filter #"+filtername)
        js = u"'" + filterstr.replace(u"\\", u"\\\\").replace(u"'", u"\\'") + u"'"
        parameter_types = []
    else:
        parameter_types = filter.get_param_types()

        js = u"'"+filter_internal_beginin
        js += filtername
        for i, param_type in enumerate(parameter_types):
            js += u",'+"
            if param_type == unicode:
                js += u"escape_quote(document.getElementById('filter_param_"+unicode(i)+u"').value)"
            elif param_type == int:
                js += u"document.getElementById('filter_param_"+unicode(i)+u"').value"
            elif isinstance(param_type, ChoiceGroup):
                js += u"escape_quote(document.getElementById('filter_param_"+unicode(i)+u"').options[document.getElementById('filter_param_"+unicode(i)+u"').selectedIndex].value)"
            else:
                raise Exception(u"Unsupported filter parameter of type "+unicode(param_type))
            js += u"+'"
        js += u")'"

    if previous_filter: # CLEAN ME
        body += u"<form id='filter_param_form' onsubmit=\"newfilter="+js+u"; combine='and'; for (i=0; i<document.forms['filter_param_form']['filter_combine'].length; ++i) if (document.forms['filter_param_form']['filter_combine'][i].checked) combine=document.forms['filter_param_form']['filter_combine'][i].value; newfilter=combine+'('+document.getElementById('filter').value+','+newfilter+')'; document.getElementById('filter').value=newfilter; if (!add_another_filter) document.forms['mainform'].submit(); else { select_field(null); ajax_load_innerhtml('curent_filter', '/contacts/search/filter_to_html?'+newfilter); } return false;\">\n"
        for i, param_type in enumerate(parameter_types):
            if param_type in (unicode, int):
                body += u"<input type=text id=\"filter_param_"+unicode(i)+u"\"><br>\n"
            elif isinstance(param_type, ChoiceGroup):
                body += u"<select id=\"filter_param_"+unicode(i)+u"\">\n"
                for choice_key, choice_value in param_type.ordered_choices:
                    body += "<option value=\"%(choice_key)s\">%(choice_value)s</option>\n" % { 'choice_key': html.escape(choice_key), 'choice_value': html.escape(choice_value)}
                body += u"</select>\n"
            else:
                raise Exception(u"Unsupported filter parameter of type "+unicode(param_type))
        body += u"Filter combinaison type: <input type=radio name='filter_combine' value=and checked>AND <input type=radio name='filter_combine' value=or>OR\n"
        body += u"<input type=submit value=\"Add and apply filter\" onclick=\"add_another_filter=false;\">\n"
        body += u"<input type=submit value=\"Continue adding conditions\" onclick=\"add_another_filter=true;\">\n"
        body += u"</form>\n"
        body += u"<br clear=all>\n"
    else:
        body += u"<form id='filter_param_form' onsubmit=\"newfilter="+js+u"; document.getElementById('filter').value=newfilter; if (!add_another_filter) document.forms['mainform'].submit(); else { select_field(null); ajax_load_innerhtml('curent_filter', '/contacts/search/filter_to_html?'+newfilter); } return false;\">\n"
        for i, param_type in enumerate(parameter_types):
            if param_type in (unicode, int):
                body += u"<input type=text id=\"filter_param_"+unicode(i)+u"\"><br>\n"
            elif isinstance(param_type, ChoiceGroup):
                body += u"<select id=\"filter_param_"+unicode(i)+u"\">\n"
                for choice_key, choice_value in param_type.ordered_choices:
                    body += "<option value=\"%(choice_key)s\">%(choice_value)s</option>\n" % { 'choice_key': html.escape(choice_key), 'choice_value': html.escape(choice_value)}
                body += u"</select><br>\n"
            else:
                raise Exception(u"Unsupported filter parameter of type "+unicode(param_type))
        body += u"<input type=submit value=\"Apply filter\" onclick=\"add_another_filter=false;\">\n"
        body += u"<input type=submit value=\"Set filter and add another condition\" onclick=\"add_another_filter=true;\">\n"
        body += u"</form>\n"
        body += u"<br clear=all>\n"
    return HttpResponse(body)



@login_required()
def contactsearch_filter_to_html(request):
    if not request.user.is_admin():
        return unauthorized(request)
 
    strfilter = request.META['QUERY_STRING'] or ""
    strfilter = urllib2.unquote(strfilter)
    strfilter = unicode(strfilter, 'utf8')
    filter = parse_filterstring(strfilter)
    return HttpResponse(filter.to_html())
