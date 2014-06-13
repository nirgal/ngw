# -*- encofing: utf8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
import inspect
from django import template
from django.utils import html
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def nav_is_active(navbar, tabname):
    if len(navbar.components) < 2:
        activetab = ''
    else:
        activetab = navbar.components[1][0]
    if activetab == tabname:
        return 'id=active'
    return ''

@register.filter
def escape_amp_query(txt):
    return txt.replace('&', '%26')

@register.filter
def pagenumber_iterator(page, npages):
    _VISIBLE_PAGES_AROUND = 5
    return range(max(1, page-_VISIBLE_PAGES_AROUND), min(npages, page+_VISIBLE_PAGES_AROUND)+1)

@register.filter
def order_absmatch(order, column_index):
    if order == '':
        return False
    if order[0] != '-':
        return int(order) == column_index
    else:
        return int(order[1:]) == column_index

@register.filter
def order_isreverted(order):
    return order and order[0] == '-'

@register.filter
def get(object, index):
    return object[index]

@register.filter
def get_notnull(object, index):
    # That fixes query_entities.html template use of {% if col|get:3 %} crash
    # because field is not bound on table(mapper) columns
    return object[index] is not None


@register.filter
def ngw_display(obj, coldesc):
    #return 'ngwtags.py disabled'

    # If coldesc[2] is a function
    if inspect.isfunction(coldesc[2]):
        result = coldesc[2](obj)
    else:
        # Else it's a string: get the matching attribute
        attribute_name = coldesc[2]
        result = obj.__getattribute__(attribute_name)
        if inspect.ismethod(result):
            result = result()
        if result == None:
            return ''
        #result = html.escape(result)

    if inspect.isfunction(coldesc[1]):
        #print("isfunction")
        return coldesc[1](result)
    if inspect.ismethod(coldesc[1]):
        #print("ismethod")
        result =  coldesc[1](result)
        #print(result)
        return result

    try:
        flink = obj.__getattribute__("get_link_"+coldesc[2].encode('utf-8'))
        link = flink()
        if link:
            result = '<a href="'+link+'">'+result+'</a>'
    except AttributeError, e:
        pass 
    return result

@register.filter
def group_visible_by(contact_groups_query, user_id):
    return contact_groups_query.extra(where=['perm_c_can_see_cg(%s, contact_group.id)' % user_id ])

@register.filter
def group_with_link(contact_group):
    return mark_safe('<a href="'+contact_group.get_absolute_url()+'">'+html.escape(contact_group.unicode_with_date())+'</a>')
