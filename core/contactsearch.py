# -*- encoding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

from django.core.exceptions import PermissionDenied
from django.utils.encoding import force_text, force_str
from ngw.core.models import (
    ContactField, ContactGroup,
    EmptyBoundFilter, AndBoundFilter, OrBoundFilter)
from ngw.core.contactfield import ContactNameMetaField, AllEventsMetaField
from ngw.core import perms


class LexicalError(Exception):
    pass
class FilterSyntaxError(Exception):
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
            return force_str('<Lexem %s %s>' % (types[self.type], self.str))

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
        while True:
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

        subfilters = []

        while True:
            subfilters.append(_filter_parse_expression(lexer, user_id))

            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break

            if lexem.type == FilterLexer.Lexem.Type.COMMA:
                continue

            raise FilterSyntaxError("Unexpected %s. Expected ',' or ')'." % force_text(repr(lexem)))

        return AndBoundFilter(*subfilters)

    if lexem.type == FilterLexer.Lexem.Type.WORD and lexem.str == 'or':
        lexem = next(lexer)
        if lexem.type != FilterLexer.Lexem.Type.LPARENTHESIS:
            raise FilterSyntaxError("Unexpected %s. Expected '('." % force_text(repr(lexem)))

        subfilters = []

        while True:
            subfilters.append(_filter_parse_expression(lexer, user_id))

            lexem = next(lexer)
            if lexem.type == FilterLexer.Lexem.Type.RPARENTHESIS:
                break

            if lexem.type == FilterLexer.Lexem.Type.COMMA:
                continue

            raise FilterSyntaxError("Unexpected %s. Expected ',' or ')'." % force_text(repr(lexem)))

        return OrBoundFilter(*subfilters)

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
