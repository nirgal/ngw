from django import template
from django.utils import html
from django.utils.safestring import mark_safe

from ngw.core import perms

register = template.Library()


@register.filter
def nav_is_active(navbar, tabname):
    if navbar == '':  # Undefined
        return ''
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
    return range(max(1, page-_VISIBLE_PAGES_AROUND),
                 min(npages, page+_VISIBLE_PAGES_AROUND)+1)


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
def group_is_permanent(contact_groups_query):
    return contact_groups_query.filter(date__isnull=True)


@register.filter
def group_is_event(contact_groups_query):
    return contact_groups_query.filter(date__isnull=False, perso_unavail=False)


@register.filter
def group_is_perso_unavail(contact_groups_query):
    return contact_groups_query.filter(date__isnull=False, perso_unavail=True)


@register.filter
def group_visible_by(contact_groups_query, user_id):
    # TODO This is supposed to be better, but is actually much slower :(
    return contact_groups_query.with_user_perms(
        user_id, perms.SEE_CG, add_column=False)
    # return contact_groups_query.extra(where=[
    #   'perm_c_can_see_cg({}, contact_group.id)'.format(user_id)])


@register.filter
def group_with_link(contact_group):
    return mark_safe('<a href="'
                     + contact_group.get_absolute_url()
                     + '">'
                     + html.escape(str(contact_group))
                     + '</a>')


@register.filter
def perms_int_to_flags(intperms):
    return perms.int_to_flags(intperms)
