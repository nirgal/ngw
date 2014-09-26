# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
from itertools import chain
from django.conf import settings
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils.html import format_html

class FilterMultipleSelectWidget(forms.SelectMultiple):
    class Media:
        js = ('ngw/ngw.js',)

    def __init__(self, verbose_name, is_stacked, attrs=None, choices=()):
        self.verbose_name = verbose_name
        self.is_stacked = is_stacked
        super(FilterMultipleSelectWidget, self).__init__(attrs, choices)

    def render(self, name, value, attrs=None, choices=()):
        output = [super(FilterMultipleSelectWidget, self).render(name, value, attrs, choices)]
        output.append('<script type="text/javascript">addEvent(window, "load", function(e) {')
        # TODO: 'id_' is hard-coded here. This should instead use the correct
        # API to determine the ID dynamically.
        output.append('SelectFilter.init("id_%s", "%s", %s, "%s"); });</script>\n' % \
            (name, self.verbose_name.replace('"', '\\"'), int(self.is_stacked), settings.STATIC_URL+'admin/'))
        return mark_safe(''.join(output))


# That class is a clone of forms.CheckboxSelectMultiple
# It only adds an extra class=onelinechoices to the <ul>
class OnelineCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    class NgwCheckboxFieldRenderer(forms.widgets.CheckboxFieldRenderer):
        def render(self):
            """
            Outputs a <ul> for this set of choice fields.
            If an id was given to the field, it is applied to the <ul> (each
            item in the list will get an id of `$id_$i`).
            """
            id_ = self.attrs.get('id', None)
            start_tag = format_html('<ul class=onelinechoices id="{0}">', id_) if id_ else '<ul class=onelinechoices>'
            output = [start_tag]
            for widget in self:
                output.append(format_html('<li>{0}</li>', force_text(widget)))
            output.append('</ul>')
            return mark_safe('\n'.join(output))
    renderer = NgwCheckboxFieldRenderer
