# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
from itertools import chain
from django.conf import settings
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils import html

class NgwCalendarWidget(forms.TextInput):
    class Media:
        #css = {
        #    'all': ('pretty.css',)
        #}
        js = ('ngw/ngw.js', 'admin/js/calendar.js', 'admin/js/admin/DateTimeShortcuts.js')


class FilterMultipleSelectWidget(forms.SelectMultiple):
    class Media:
        js = ('ngw.js',)

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
# It only adds an extra class=multiplechoice to the <ul>
class NgwCheckboxSelectMultiple(forms.SelectMultiple):
    def render(self, name, value, attrs=None, choices=()):
        if value is None: value = []
        has_id = attrs and 'id' in attrs
        final_attrs = self.build_attrs(attrs, name=name)
        output = ['<ul class=multiplechoice>']
        # Normalize to strings
        str_values = set([force_text(v) for v in value])
        for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
            # If an ID attribute was given, add a numeric index as a suffix,
            # so that the checkboxes don't all have the same ID attribute.
            if has_id:
                final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
                label_for = ' for="%s"' % final_attrs['id']
            else:
                label_for = ''

            cb = forms.CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
            option_value = force_text(option_value)
            rendered_cb = cb.render(name, option_value)
            option_label = html.conditional_escape(force_text(option_label))
            output.append('<li><label%s>%s %s</label></li>' % (label_for, rendered_cb, option_label))
        output.append('</ul>')
        return mark_safe('\n'.join(output))
