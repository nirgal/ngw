# -*- encoding: utf-8 -*-

from __future__ import division, print_function, unicode_literals
from django.utils import six
from django.utils.six import next
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _, string_concat
from django.utils.safestring import mark_safe
from django.utils import html
from django.utils.encoding import force_text
from django.http import HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from ngw.core.models import ( 
    ContactField, ContactGroup, ChoiceGroup,
    EmptyBoundFilter, AndBoundFilter, OrBoundFilter,
    FIELD_FILTERS )
from ngw.core.contactfield import ContactNameMetaField, AllEventsMetaField
from ngw.core import perms



def no_br(txt):
    " Replaces all spaces by non-breaking spaces"
    return txt.replace(' ', '\u00a0')

def format_link_list(l):
    # list is a 3-tupple ( url, display name, dom_id )
    return '\u00a0| '.join(
        [ '<a href="%(url)s" id="%(dom_id)s">%(name)s</a>\n' % {'url':url, 'name':name, 'dom_id':dom_id }
          for url, name, dom_id in l])


class LexicalError(Exception if six.PY3 else StandardError):
    pass
class FilterSyntaxError(Exception if six.PY3 else StandardError):
    pass

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
            types = { 0: 'WORD', 1: 'STRING', 2: 'INT', 3: 'LPARENTHESIS', 4: 'RPARENTHESIS', 5: 'COMMA' }
            return force_str('Lexem<' + types[self.type] + ',' + self.str + '>')
            
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
            if c == '(':
                yield self.Lexem(self.Lexem.Type.LPARENTHESIS, c)
            elif c == ')':
                yield self.Lexem(self.Lexem.Type.RPARENTHESIS, c)
            elif c == ',':
                yield self.Lexem(self.Lexem.Type.COMMA, c)
            elif c == "'":
                slexem = ''
                while True:
                    c = self.getchar()
                    if c == None:
                        raise LexicalError('Unexpected EOS while parsing string')
                    if c == '\\':
                        c = self.getchar()
                        if c == None:
                            raise LexicalError('Unexpected EOS while parsing string after "\\"')
                    if c == "'":
                        yield self.Lexem(self.Lexem.Type.STRING, slexem)
                        break
                    slexem += c

            elif c.isdigit():
                slexem = ''
                while c.isdigit():
                    slexem += c
                    c = self.getchar()
                    if c == None:
                        break
                if c != None:
                    self.goback()
                yield self.Lexem(self.Lexem.Type.INT, slexem)
            elif c.isalpha():
                slexem = ''
                while c.isalpha():
                    slexem += c
                    c = self.getchar()
                    if c == None:
                        break
                if c != None:
                    self.goback()
                yield self.Lexem(self.Lexem.Type.WORD, slexem)
            else:
                raise LexicalError('Unexpected character')


def _filter_parse_expression(lexer, user_id):
    '''
    Filter parser.
    Returns a BoundFilter, that is a filter reader to apply, that includes parameters.
    user_id is there only to check security priviledges.
    '''
    try:
        lexem = next(lexer)
    except StopIteration:
        return EmptyBoundFilter()

    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'and':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        subfilter1 = _filter_parse_expression(lexer, user_id)

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))
        
        subfilter2 = _filter_parse_expression(lexer, user_id)

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.RPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected ')'." % force_text(repr(lexem)))
        
        return AndBoundFilter(subfilter1, subfilter2)


    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'or':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        subfilter1 = _filter_parse_expression(lexer, user_id)

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))
        
        subfilter2 = _filter_parse_expression(lexer, user_id)

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.RPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected ')'." % force_text(repr(lexem)))
        
        return OrBoundFilter(subfilter1, subfilter2)


    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'ffilter':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.INT:
            raise FilterSyntaxError("Unexpected %s. Expected INT." % force_text(repr(lexem)))
        field_id = int(lexem.str)

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))
        
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError("Unexpected %s. Expected word." % force_text(repr(lexem)))
        field_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))

            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        field = ContactField.objects.get(pk=field_id)

        # Security check: user must have read access that field
        if not perms.c_can_view_fields_cg(user_id, field.contact_group_id):
            raise PermissionDenied

        filter = field.get_filter_by_name(field_filter_name)
        return filter.bind(*params)

    elif lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'gfilter':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.INT:
            raise FilterSyntaxError("Unexpected %s. Expected INT." % force_text(repr(lexem)))
        group_id = int(lexem.str)

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.COMMA:
            raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))
        
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError("Unexpected %s. Expected word." % force_text(repr(lexem)))
        group_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))

            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))

        # Security check: user must have access to members list of that group
        if not perms.c_can_see_members_cg(user_id, group_id):
            raise PermissionDenied

        filter = ContactGroup.objects.get(pk=group_id).get_filter_by_name(group_filter_name)
        return filter.bind(*params)

    elif lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'nfilter':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError("Unexpected %s. Expected word." % force_text(repr(lexem)))
        name_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))

            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        filter = ContactNameMetaField.get_filter_by_name(name_filter_name)
        return filter.bind(*params)

    elif lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'allevents':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.WORD:
            raise FilterSyntaxError("Unexpected %s. Expected word." % force_text(repr(lexem)))
        allevents_filter_name = lexem.str

        params = [ ]

        while True:
            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break
            if lexem.type != FilterLexer.Lexem.Type.COMMA:
                raise FilterSyntaxError("Unexpected %s. Expected ','." % force_text(repr(lexem)))

            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.STRING:
                params.append(lexem.str)
            elif lexem.type == FilterLexer.Lexem.Type.INT:
                params.append(int(lexem.str))
                
        filter = AllEventsMetaField.get_filter_by_name(allevents_filter_name)
        return filter.bind(*params)

    else:
        raise FilterSyntaxError("Unexpected %s." % force_text(repr(lexem)))
    

def _filter_parse_expression_root(lexer, user_id):
    '''
    Calls _filter_parse_expression() and check nothing is left after the end
    '''
    exp = _filter_parse_expression(lexer, user_id)
    try:
        lexem = next(lexer)
    except StopIteration:
        return exp
    else:
        raise FilterSyntaxError("Unexpected %s after end of string." % force_text(repr(lexem)))


def parse_filterstring(sfilter, user_id):
    '''
    Parse sfilter string, checking user_id priviledges.
    Returns a bound filter.
    '''
    #print("Parsing", sfilter)
    return _filter_parse_expression_root(FilterLexer(sfilter).parse(), user_id)

    




@login_required()
def editfilter(request):
    '''
    This is the basic widget to build and combine filters during a search
    '''
    # Security is handled by the parser
    filter = parse_filterstring('', request.user.id)
    return render_to_response('filter.html', {'filter_html':mark_safe(filter.to_html())}, RequestContext(request))


@login_required()
def contactsearch_get_fields(request, kind):
    '''
    This is the second step in the building of a contact search filter:
    Select field or group or event ...
    '''
    body = ""
    if kind == 'field':
        body = string_concat(body, _('Add a field'), ': ')
        fields = ContactField.objects.extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % request.user.id]).order_by('sort_weight')
        body = string_concat(body,
            format_link_list([("javascript:select_field('name')", _("Name"), "field_name")]+[ ("javascript:select_field('field_"+force_text(cf.id)+"')", no_br(html.escape(cf.name)), "field_field_"+force_text(cf.id)) for cf in fields]))
    elif kind == 'group':
        body = string_concat(body, _('Add a group'), ': ')
        groups = ContactGroup.objects.filter(date=None).extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % request.user.id]).order_by('name')
        body = string_concat(body,
            format_link_list([ ("javascript:select_field('group_"+force_text(cg.id)+"')", no_br(cg.unicode_with_date()), "field_group_"+force_text(cg.id)) for cg in groups]))
    elif kind == 'event':
        body = string_concat(body, _('Add an event'), ': ')
        groups = ContactGroup.objects.exclude(date=None).extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % request.user.id]).order_by('-date', 'name')
        body = string_concat(body, format_link_list(
            [ ("javascript:select_field('allevents')", no_br('All events'), "field_allevents") ] +
            [ ("javascript:select_field('group_"+force_text(cg.id)+"')", no_br(cg.unicode_with_date()), "field_group_"+force_text(cg.id)) for cg in groups]))
    elif kind == 'custom':
        body = string_concat(body, _('Add a custom filter'), ': ')
        body = string_concat(body, format_link_list([ ("javascript:select_field('custom_user')", _("Custom filters for %s") % request.user.name, 'field_custom_user')]))
    else:
        body += "ERROR in get_fields: kind=="+kind
    return HttpResponse(body)


def parse_filter_list_str(txt):
    '''
    This takes a filter list stored in the database and returns a list of tupples
    ( filtername, filter_string )
    '''
    list = txt.split(',')
    for idx in range(len(list)-1, 0, -1):
        if list[idx-1][-1] != '"' or list[idx][0] != '"':
            #print("merging elements ", idx-1, "and", idx, "of", repr(list))
            list[idx-1] += ',' + list[idx]
            del list[idx]
    for idx in range(len(list)):
        assert(list[idx][0] == '"')
        assert(list[idx][-1] == '"')
        list[idx] = list[idx][1:-1]
    assert(len(list)%2 == 0)
    return [ (list[2*i], list[2*i+1]) for i in range(len(list)//2) ]
    

@login_required()
def contactsearch_get_filters(request, field):
    '''
    This is the third step in building a contact search filter:
    Display operators such as "is lower than" to apply to the "field" selected.
    Acutally, field can an event, or other things...
    '''
    body = ""
    if field == 'name':
        body = string_concat(body, _('Add a filter for name'), ': ')
        body = string_concat(body, format_link_list([ ("javascript:select_filtername('"+filter.internal_name+"')", no_br(filter.human_name), "filter_"+filter.internal_name) for filter in ContactNameMetaField.get_filters() ]))

    elif field.startswith('field_'):
        field_id = int(field[len('field_'):])
        field = ContactField.objects.get(pk=field_id)
        body = string_concat(body, _('Add a filter for field of type %s') % field.human_type_id, ': ')
        body = string_concat(body, format_link_list([ ("javascript:select_filtername('"+filter.internal_name+"')", no_br(filter.human_name), "filter_"+filter.internal_name) for filter in field.get_filters() ]))

    elif field.startswith('group_'):
        group_id = int(field[len('group_'):])
        group = ContactGroup.objects.get(pk=group_id)
        body = string_concat(body, _('Add a filter for group/event'), ': ')
        body = string_concat(body, format_link_list([ ("javascript:select_filtername('"+filter.internal_name+"')", no_br(filter.human_name), "filter_"+filter.internal_name) for filter in group.get_filters() ]))

    elif field.startswith('allevents'):
        body = string_concat(body, _('Add a filter for all events'), ': ')
        body = string_concat(body, format_link_list([ ("javascript:select_filtername('"+filter.internal_name+"')", no_br(filter.human_name), "filter_"+filter.internal_name) for filter in AllEventsMetaField.get_filters() ]))

    elif field.startswith('custom'):
        filter_list_str = request.user.get_fieldvalue_by_id(FIELD_FILTERS)
        if not filter_list_str:
            body = string_concat(body, _('No custom filter available'))
        else:
            filter_list = parse_filter_list_str(filter_list_str)
            body = string_concat(body, _('Select a custom filter'), ': ')
            body = string_concat(body, format_link_list([ ("javascript:select_filtername('"+force_text(i)+"')", no_br(filter[0]), "usercustom_"+force_text(i)) for i, filter in enumerate(filter_list) ]))
    else:
        body = string_concat(body, _('ERROR in get_filters: field==%s') % field)
    
    return HttpResponse(body)


@login_required()
def contactsearch_get_params(request, field, filtername):
    '''
    This is the last step in building a contact search filter:
    After selecting a "field" and a filtername (operator), user enters a paramter.
    The parameter type depends of the filter. Can be a string, a date, ...
    '''

    previous_filter = request.GET.get('previous_filter', '')
    filter = None

    if field == 'name':
        filter = ContactNameMetaField.get_filter_by_name(filtername)
        filter_internal_beginin = "nfilter("

    elif field.startswith('field_'):
        field_id = int(field[len('field_'):])
        field = ContactField.objects.get(pk=field_id)
        if not perms.c_can_view_fields_cg(request.user.id, field.contact_group_id):
            raise PermissionDenied
        filter = field.get_filter_by_name(filtername)
        filter_internal_beginin = 'ffilter(' + force_text(field_id) + ','

    elif field.startswith('group_'):
        group_id = int(field[len('group_'):])
        if not perms.c_can_see_members_cg(request.user.id, group_id):
            raise PermissionDenied
        group = ContactGroup.objects.get(pk=group_id)
        filter = group.get_filter_by_name(filtername)
        filter_internal_beginin = 'gfilter(' + force_text(group_id) + ','

    elif field == 'allevents':
        filter = AllEventsMetaField.get_filter_by_name(filtername)
        filter_internal_beginin = 'allevents('

    elif field == 'custom_user':
        pass
    else:
        return HttpResponse('ERROR: field ' + field + ' not supported')


    body = ''

    if field == 'custom_user':
        filter_list_str = request.user.get_fieldvalue_by_id(FIELD_FILTERS)
        if not filter_list_str:
            return HttpResponse('ERROR: no custom filter for that user')
        else:
            filter_list = parse_filter_list_str(filter_list_str)
        try:
            filterstr = filter_list[int(filtername)][1]
        except (IndexError, ValueError):
            return HttpResponse("ERROR: Can't find filter #" + filtername)
        js = "'" + filterstr.replace("\\", "\\\\").replace("'", "\\'") + "'"
        parameter_types = []
    else:
        parameter_types = filter.get_param_types()

        js = "'" + filter_internal_beginin
        js += filtername
        for i, param_type in enumerate(parameter_types):
            js += ",'+"
            if param_type == six.text_type:
                js += "escape_quote(document.getElementById('filter_param_" + force_text(i) + "').value)"
            elif param_type == int:
                js += "document.getElementById('filter_param_" + force_text(i) + "').value"
            elif isinstance(param_type, ChoiceGroup):
                js += "escape_quote(document.getElementById('filter_param_" + force_text(i) + "').options[document.getElementById('filter_param_" + force_text(i) + "').selectedIndex].value)"
            else:
                raise Exception("Unsupported filter parameter of type " + force_text(param_type))
            js += "+'"
        js += ")'"

    if previous_filter: # CLEAN ME
        body = string_concat(body, "<form id='filter_param_form' onsubmit=\"newfilter=", js, "; combine='and'; for (i=0; i<document.forms['filter_param_form']['filter_combine'].length; ++i) if (document.forms['filter_param_form']['filter_combine'][i].checked) combine=document.forms['filter_param_form']['filter_combine'][i].value; newfilter=combine+'('+document.getElementById('filter').value+','+newfilter+')'; document.getElementById('filter').value=newfilter; if (!add_another_filter) document.forms['mainform'].submit(); else { select_field(null); ajax_load_innerhtml('curent_filter', '/contacts/search/filter_to_html?'+newfilter); } return false;\">\n")
        for i, param_type in enumerate(parameter_types):
            if param_type in (six.text_type, int):
                body = string_concat(body, "<input type=text id=\"filter_param_" + force_text(i) + "\"><br>\n")
            elif isinstance(param_type, ChoiceGroup):
                body = string_concat(body, "<select id=\"filter_param_", force_text(i), "\">\n")
                for choice_key, choice_value in param_type.ordered_choices:
                    body = string_concat(body, "<option value=\"%(choice_key)s\">%(choice_value)s</option>\n" % { 'choice_key': html.escape(choice_key), 'choice_value': html.escape(choice_value)})
                body = string_concat(body, "</select>\n")
            else:
                raise Exception("Unsupported filter parameter of type "+force_text(param_type))
        body = string_concat(body, _('Filter combinaison type'), ": <input type=radio name='filter_combine' value=and checked>", _('AND'), " <input type=radio name='filter_combine' value=or>", _('OR'), "\n")
        body = string_concat(body, "<input type=submit value=\"", _('Add and apply filter'), "\" onclick=\"add_another_filter=false;\">\n")
        body = string_concat(body, "<input type=submit value=\"", _('Continue adding conditions'), "\" onclick=\"add_another_filter=true;\">\n")
        body = string_concat(body, "</form>\n")
        body = string_concat(body, "<br clear=all>\n")
    else:
        body = string_concat(body, "<form id='filter_param_form' onsubmit=\"newfilter=", js, "; document.getElementById('filter').value=newfilter; if (!add_another_filter) document.forms['mainform'].submit(); else { select_field(null); ajax_load_innerhtml('curent_filter', '/contacts/search/filter_to_html?'+newfilter); } return false;\">\n")
        for i, param_type in enumerate(parameter_types):
            if param_type in (six.text_type, int):
                body = string_concat(body, "<input type=text id=\"filter_param_", force_text(i), "\"><br>\n")
            elif isinstance(param_type, ChoiceGroup):
                body = string_concat(body, "<select id=\"filter_param_" + force_text(i) + "\">\n")
                for choice_key, choice_value in param_type.ordered_choices:
                    body = string_concat(body, "<option value=\"%(choice_key)s\">%(choice_value)s</option>\n" % { 'choice_key': html.escape(choice_key), 'choice_value': html.escape(choice_value)})
                body = string_concat(body, "</select><br>\n")
            else:
                raise Exception("Unsupported filter parameter of type " + force_text(param_type))
        body = string_concat(body, "<input type=submit value=\"", _('Apply filter'), "\" onclick=\"add_another_filter=false;\">\n")
        body = string_concat(body, "<input type=submit value=\"", _('Set filter and add another condition'), "\" onclick=\"add_another_filter=true;\">\n")
        body = string_concat(body, "</form>\n")
        body = string_concat(body, "<br clear=all>\n")
    return HttpResponse(body)



@login_required()
def contactsearch_filter_to_html(request):
    '''
    Convert a filter string into a nice indented html block
    with fieldid replaced by field names and so on.
    Security is checked by filter parser.
    '''
    strfilter = request.META['QUERY_STRING']
    if strfilter:
        strfilter = six.moves.urllib.parse.unquote(strfilter)
        strfilter = force_text(strfilter)
    else:
        strfilter = ''
    filter = parse_filterstring(strfilter, request.user.id)
    return HttpResponse(filter.to_html())
