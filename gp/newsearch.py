# -*- encoding: utf-8 -*-

import pprint
from django.http import *
from django.utils.safestring import mark_safe
from ngw.gp.views import *
from ngw.gp.alchemy_models import *

def no_br(txt):
    " Replaces all spaces by non-breaking spaces"
    return txt.replace(u" ", u"\u00a0")

def format_link_list(l):
    # list is a 3-tupple ( url, display name, dom_id )
    return u"\u00a0| ".join(
        [ u'<a href="%(url)s" id="%(dom_id)s">%(name)s</a>\n' % {'url':url, 'name':name, 'dom_id':dom_id }
          for url,name,dom_id in l])


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
            WORD=0           # isalpha
            STRING=1         # 'vbn hjk \' sdds \\ klmjk'
            INT=2            # isdigit
            LPARENTHESIS=3   # (
            RPARENTHESIS=4   # )
            COMMA=5          # ,

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
            if c==None:
                return
            if c==u"(":
                yield self.Lexem(self.Lexem.Type.LPARENTHESIS, c)
            elif c==u")":
                yield self.Lexem(self.Lexem.Type.RPARENTHESIS, c)
            elif c==u",":
                yield self.Lexem(self.Lexem.Type.COMMA, c)
            elif c==u"'":
                slexem = u""
                while True:
                    c = self.getchar()
                    if c==None:
                        raise LexicalError(u"Unexpected EOS while parsing string")
                    if c==u'\\':
                        c = self.getchar()
                        if c==None:
                            raise LexicalError(u"Unexpected EOS while parsing string after \"\\\"")
                    if c==u"'":
                        yield self.Lexem(self.Lexem.Type.STRING, slexem)
                        break
                    slexem += c

            elif c.isdigit():
                slexem = u""
                while c.isdigit():
                    slexem += c
                    c = self.getchar()
                    if c==None:
                        break
                if c!=None:
                    self.goback()
                yield self.Lexem(self.Lexem.Type.INT, slexem)
            elif c.isalpha():
                slexem = u""
                while c.isalpha():
                    slexem += c
                    c = self.getchar()
                    if c==None:
                        break
                if c!=None:
                    self.goback()
                yield self.Lexem(self.Lexem.Type.WORD, slexem)
            else:
                raise LexicalError(u"Unexpected character")


def filter_parse_expression(lexer):
    lexem = lexer.next()
    if lexem.type==FilterLexer.Lexem.Type.WORD and lexem.str==u"ffilter":
        lexem = lexer.next()
        if lexem.type!=FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        lexem = lexer.next()
        if lexem.type!=FilterLexer.Lexem.Type.INT:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected INT.")
        field_id = int(lexem.str)

        lexem = lexer.next()
        if lexem.type!=FilterLexer.Lexem.Type.COMMA:
            raise (u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")
        
        lexem = lexer.next()
        if lexem.type!=FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected word.")
        field_filter_name = lexem.str

        params = [ ]

        while 1:
            lexem = lexer.next()
            if lexem.type==FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type!=FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")

            lexem = lexer.next()
            if lexem.type==FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type==FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        return FieldFilterCondition(field_id, field_filter_name, *params)

    elif lexem.type==FilterLexer.Lexem.Type.WORD and lexem.str==u"nfilter":
        lexem = lexer.next()
        if lexem.type!=FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected '('.")

        lexem = lexer.next()
        if lexem.type!=FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected word.")
        name_filter_name = lexem.str

        params = [ ]

        while 1:
            lexem = lexer.next()
            if lexem.type==FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type!=FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError(u"Unexpected "+unicode(repr(lexem), 'utf8')+u". Expected ','.")

            lexem = lexer.next()
            if lexem.type==FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type==FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        return NameFilterCondition(name_filter_name, *params)

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
    print "Parsing", sfilter
    return filter_parse_expression_root(FilterLexer(sfilter).parse())

    

@http_authenticate(ngw_auth, 'ngw')
def testsearch(request):
    if not request.user.is_admin():
        return unauthorized(request)
    
    strfilter = request.REQUEST.get('filter') or u""
    filter = parse_filterstring(strfilter)
    
    if request.GET.has_key('runfilter'):
        q, cols = contact_make_query_with_fields()
        q = filter.apply_filter_to_query(q)
        args={}
        args['title'] = "Contacts search results"
        args['objtype'] = Contact
        args['query'] = q
        args['cols'] = cols
        params = request.META['QUERY_STRING'] or u""
        args['baseurl'] = "?"+params
        return query_print_entities(request, 'searchresult_contact.html', args)
        

    args={}
    args["title"] = "Contact search"
    args["objtype"] = Contact
    args["filter_from_py"] = filter.to_html()
    args["strfilter"] = mark_safe(html.escape(strfilter))
    return render_to_response('search_contact_new.html', args, RequestContext(request))


@http_authenticate(ngw_auth, 'ngw')
def testsearch_get_fields(request, kind):
    if not request.user.is_admin():
        return unauthorized(request)
    
    body = u""
    if kind==u"field":
        body += u"Add a field: "
        body += format_link_list([(u"javascript:select_field('name')", u"Name", u"field_name")]+[ (u"javascript:select_field('field_"+unicode(cf.id)+"')", no_br(name_internal2nice(cf.name)), u"field_field_"+unicode(cf.id)) for cf in Query(ContactField).order_by(ContactField.c.sort_weight)])
    elif kind==u"group":
        body += u"Add a group: "
        body += format_link_list([ (u"javascript:select_field('group_"+unicode(cg.id)+"')", no_br(cg.unicode_with_date()), u"field_group_"+unicode(cg.id)) for cg in Query(ContactGroup).filter(ContactGroup.c.date==None)])

    elif kind==u"event":
        body += u"Add an event: "
        body += format_link_list([ (u"javascript:select_field('group_"+unicode(cg.id)+"')", no_br(cg.unicode_with_date()), u"field_group_"+unicode(cg.id)) for cg in Query(ContactGroup).filter(ContactGroup.c.date!=None)])
    else:
        body += u"ERROR in get_fields: kind=="+kind
    return HttpResponse(body)

@http_authenticate(ngw_auth, 'ngw')
def testsearch_get_filters(request, field):
    if not request.user.is_admin():
        return unauthorized(request)
    
    body = u""
    if field == u"name":
        body+=u"testsearch_get_filters NOT IMPLEMENTED for field=name"

    elif field.startswith(u"field_"):
        field_id = int(field[len(u"field_"):])
        field = Query(ContactField).get(field_id)
        body += u"Add a filter for field of type "+field.human_type_id+u" : "
            
        body += format_link_list([ (u"javascript:select_filtername('"+internal_name+u"')", no_br(internal_name), u"filter_"+internal_name) for (internal_name, filter_function, filter_as_html_function, return_type, parameter_types) in field.filters_info ])

    elif field.startswith(u"group_"):
        group_id = int(field[len(u"group_"):])
        group = Query(ContactGroup).get(group_id)
        body+=u"testsearch_get_filters NOT IMPLEMENTED for field="+field

    else:
        body+=u"ERROR in get_filters: field=="+field
    
    return HttpResponse(body)


@http_authenticate(ngw_auth, 'ngw')
def testsearch_get_params(request, field, filtername):
    if not request.user.is_admin():
        return unauthorized(request)
    
    if not field.startswith(u"field_"):
        return HttpResponse(u"ERROR: field "+field+" not supported")
    field_id = int(field[len(u"field_"):])

    field = Query(ContactField).get(field_id)
    filter_info = [ filter_info for filter_info in field.filters_info if filter_info[0]==filtername][0]
    internal_name, filter_function, filter_as_html_function, return_type, parameter_types = filter_info

    body = u""
    #body += u"Parameter for field "+ field.human_type_id + " and filter "+filtername+u": "+html.escape(pprint.pformat(parameter_types))+u"<br>"
    for i, param_type in enumerate(parameter_types):
        body += u"<input type=text id=\"filter_param_"+unicode(i)+u"\"><br>\n"

    js = u"'ffilter("
    js+= unicode(field_id)
    js+= u","
    js+= filtername
    for i, param_type in enumerate(parameter_types):
        js+=u",'+"
        if param_type==unicode:
            js+=u"escape_quote("
        js+=u"document.getElementById('filter_param_"+unicode(i)+u"').value"
        if param_type==unicode:
            js+=u")"
        js+=u"+'"
    js+=u")'"
    body += u"<input type=submit onclick=\"newfilter="+js+u"; document.getElementById('filter').value=newfilter; ajax_load_innerhtml('curent_filter','/testsearch/filter_to_html?'+newfilter);\" value=\"Set filter\">\n"
    body += u"<br clear=all>\n"
    return HttpResponse(body)



@http_authenticate(ngw_auth, 'ngw')
def testsearch_filter_to_html(request):
    if not request.user.is_admin():
        return unauthorized(request)
 
    # that request expect a single string as parameters/values
    #FIXME: crashes when there's a '&' or a '='
    strfilter = request.GET.items()[0][0]
    return HttpResponse(parse_filterstring(strfilter).to_html())
