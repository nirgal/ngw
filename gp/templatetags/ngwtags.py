# -*- encofing: utf8 -*-

from django import template
import inspect

register = template.Library()

@register.filter
def row_get_value_by_key(alchemy_entity, column_name):
    return alchemy_entity.__getattribute__(column_name)
    
@register.filter
def name_internal2nice(txt):
    """
    Capitalize first letter and replace _ by spaces
    """
    txt = txt.replace('_', ' ')
    if len(txt)>0:
        txt = txt[0].upper() + txt[1:]
    return txt

@register.filter
def iter_alchemy_tuple(row):
    """ That filter iterate entities when row is a tuple.
    When it's now, it iterates once yielding the one value"""
    if isinstance(row, tuple):
        for entity in row:
            yield entity
    else:
        yield row

@register.filter
def ngw_unicode(o):
    if o:
        return unicode(o)
    return u""


@register.filter
def pagenumber_iterator(page, npages):
    _VISIBLE_PAGES_AROUND=5
    return range(max(1,page-_VISIBLE_PAGES_AROUND), min(npages, page+_VISIBLE_PAGES_AROUND)+1)


@register.filter
def get(object, index):
    return object[index]

@register.filter
def ngw_display(row, col):
    entity_id = col[1]
    entity = row[entity_id]
    if not entity:
        return u""

    if inspect.isfunction(col[2]):
        return col[2](entity)
        
    attribute_name = col[2]
    result = entity.__getattribute__(attribute_name)
    if inspect.ismethod(result):
        return result()
    #TODO: handle more types & errors, like method need another parameter
    return result

