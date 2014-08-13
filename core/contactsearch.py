# -*- encoding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

from collections import OrderedDict
import json
from django.utils import six
from django.utils.six import next
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _, ugettext, string_concat
from django.utils.encoding import force_text, force_str
from django.http import HttpResponse, Http404
from django.template import RequestContext
from ngw.core.models import (
    GROUP_USER_NGW,
    ContactField, ContactGroup, ChoiceGroup,
    EmptyBoundFilter, AndBoundFilter, OrBoundFilter,
    FIELD_FILTERS)
from ngw.core.contactfield import ContactNameMetaField, AllEventsMetaField
from ngw.core import perms
from ngw.core.viewdecorators import *


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
            types = {0: 'WORD', 1: 'STRING', 2: 'INT', 3: 'LPARENTHESIS', 4: 'RPARENTHESIS', 5: 'COMMA'}
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
                    elif c == "'": # else is needed because it could be escaped
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

        params = []

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

        params = []

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

        params = []

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

        params = []

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

    



class JsonHttpResponse(HttpResponse):
    '''
    HttpResponse subclass that json encode content, with default content_type
    '''
    def __init__(self, content, content_type='application/json', *args, **kwargs):
        super(JsonHttpResponse, self).__init__(json.dumps(content), content_type, *args, **kwargs)


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_columns(request, column_type):
    if column_type == 'fields':
        fields = ContactField.objects.order_by('sort_weight').extra(where=['perm_c_can_view_fields_cg(%s, contact_field.contact_group_id)' % request.user.id])
        choices = [{'id': 'name', 'text': force_text(_('Name'))}]
        for field in fields:
            choices.append({'id': force_text(field.id), 'text': field.name})

    elif column_type == 'groups':
        groups = ContactGroup.objects.filter(date=None).extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % request.user.id]).order_by('name')
        choices = []
        for group in groups:
            choices.append({'id': force_text(group.id), 'text': group.name})

    elif column_type == 'events':
        groups = ContactGroup.objects.exclude(date=None).extra(where=['perm_c_can_see_members_cg(%s, contact_group.id)' % request.user.id]).order_by('-date', 'name')
        choices = []
        choices.append({'id': 'allevents', 'text': force_text(_('All events'))})
        for group in groups:
            choices.append({'id': force_text(group.id), 'text': group.unicode_with_date()})

    elif column_type == 'custom':
        choices = [{'id': 'user', 'text': request.user.name}]

    else:
        raise Http404

    return JsonHttpResponse({'params' : [choices]})


def get_column(column_type, column_id):
    '''
    returns a 2-tuple:
    - First component has a get_filter event
    - second component is the prefix to build the text version of the filter
    '''
    if column_type == 'fields':
        if column_id == 'name':
            return ContactNameMetaField, 'nfilter('
        else:
            return ContactField.objects.get(pk=column_id), 'ffilter('+column_id

    if column_type == 'groups':
        return ContactGroup.objects.get(pk=column_id), 'gfilter('+column_id

    if column_type == 'events':
        if column_id == 'allevents':
            return AllEventsMetaField, 'allevents('
        else:
            return ContactGroup.objects.get(pk=column_id), 'gfilter('+column_id

    if column_type == 'custom':
        raise NotImplementedError # We might make a MetaField

    raise Http404


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_filters(request, column_type, column_id):
    if column_type == 'custom':
        # right now, custom only support 'user'
        # in the future, we might have global and/or group specific stored filters
        if column_id != 'user':
            raise Http404

        filter_list_str = request.user.get_fieldvalue_by_id(FIELD_FILTERS)
        choices = []
        if filter_list_str:
            filter_list = parse_filter_list_str(filter_list_str)
            for i, filterpair in enumerate(filter_list):
                filtername, filterstr = filterpair
                choices.append({'id': force_text(i), 'text': filtername})

    else:
        column, submit_prefix = get_column(column_type, column_id)

        filters = column.get_filters()

        choices = []
        for filter in filters:
            choices.append({'id': filter.internal_name, 'text': force_text(filter.human_name)})
    return JsonHttpResponse({'params' : [choices]})


@login_required()
@require_group(GROUP_USER_NGW)
def ajax_get_filters_params(request, column_type, column_id, filter_id):
    if column_type == 'custom':
        # right now, custom only support 'user'
        # in the future, we might have global and/or group specific stored filters
        if column_id != 'user':
            raise Http404

        filter_list_str = request.user.get_fieldvalue_by_id(FIELD_FILTERS)
        if not filter_list_str:
            raise Http404
        filter_list = parse_filter_list_str(filter_list_str)
        filter_id = int(filter_id)
        customname, filter = filter_list[filter_id]
        assert filter[-1] == ')', "Custom filter %s should end with a ')'" % customname
        return JsonHttpResponse({'submit_prefix': filter[:-1], 'params' : []})

    column, submit_prefix = get_column(column_type, column_id)
    filter = column.get_filter_by_name(filter_id)
    parameter_types = filter.get_param_types()
    jsparams = []
    for param_type in parameter_types:
        if param_type == six.text_type:
            jsparams.append('string')
        elif param_type == int:
            jsparams.append('number')
        elif isinstance(param_type, ChoiceGroup):
            choices = []
            for key, value in param_type.ordered_choices:
                choices.append({'id': key, 'text': value})
            jsparams.append(choices)
        else:
            assert False, "Unsupported filter parameter of type " + force_text(param_type)
    if submit_prefix[-1] != '(':
        submit_prefix += ','
    submit_prefix += filter_id
    return JsonHttpResponse({'submit_prefix': submit_prefix, 'params' : jsparams})


#TODO: Move into models.py
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
    return [(list[2*i], list[2*i+1]) for i in range(len(list)//2)]


@login_required()
@require_group(GROUP_USER_NGW)
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
