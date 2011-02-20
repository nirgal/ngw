# -*- encofing: utf8 -*-

import inspect, traceback
from django import template
from django.utils import html

register = template.Library()

@register.filter
def nav_is_active(navbar, tabname):
    if len(navbar.components)<2:
        activetab = u''
    else:
        activetab = navbar.components[1][0]
    if activetab == tabname:
        return u"id=active"
    return u""


@register.filter
def escape_amp_query(txt):
    return txt.replace(u'&', u'%26')

#@register.filter
#def row_get_value_by_key(alchemy_entity, column_name):
#    return alchemy_entity.__getattribute__(column_name)
    
#@register.filter
#def iter_alchemy_tuple(row):
#    """ That filter iterate entities when row is a tuple.
#    When it's now, it iterates once yielding the one value"""
#    if isinstance(row, tuple):
#        for entity in row:
#            yield entity
#    else:
#        yield row

@register.filter
def ngw_date_format(dt):
    #TODO i18n process(LANG=fr_FR.UTF-8 date -d '2009-01-02' +'%a %d %b %Y')
    return dt.strftime('%a %d %b %Y')

@register.filter
def ngw_datetime_format(dt):
    return dt.strftime('%a %d %b %Y %H:%M:%S')

@register.filter
def pagenumber_iterator(page, npages):
    _VISIBLE_PAGES_AROUND=5
    return range(max(1,page-_VISIBLE_PAGES_AROUND), min(npages, page+_VISIBLE_PAGES_AROUND)+1)


@register.filter
def order_absmatch(order, column_index):
    if order==u"":
        return False
    if order[0]!="-":
        return int(order)==column_index
    else:
        return int(order[1:])==column_index

@register.filter
def order_isreverted(order):
    return order and order[0]=="-"


@register.filter
def get(object, index):
    return object[index]

@register.filter
def get_notnull(object, index):
    # That fixes query_entities.html template use of {% if col|get:3 %} crash
    # because field is not bound on table(mapper) columns
    return object[index] is not None


@register.filter
def ngw_display(row, col):
    #return u"ngwtags.py disabled"
    if isinstance(row, tuple):
        entity_id = col[1]
        entity = row[entity_id]
    else:
        entity = row

    if not entity:
        return u""

    if inspect.isfunction(col[2]):
        return col[2](entity)
        
    attribute_name = col[2]
    result = entity.__getattribute__(attribute_name)
    if inspect.ismethod(result):
        return result()
    #TODO: handle more types & errors, like method need another parameter
    if result==None:
        return u""
    result = html.escape(result)
    try:
        flink = entity.__getattribute__("get_link_"+attribute_name.encode('utf-8'))
        link = flink()
        if link:
            result = '<a href="'+link+'">'+result+'</a>'
    except AttributeError, e:
        pass 
    return result

