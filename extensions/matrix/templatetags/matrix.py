from django import template
from django.utils import html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def matrixuser(username):
    return mark_safe(
            # f'<a href="/matrix/user/{username}?debug=1">'
            f'<a href="/matrix/user/{username}">'
            + html.escape(username)
            + '</a>')
