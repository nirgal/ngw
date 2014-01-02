# -*- encoding: utf-8 -*-

from itertools import chain
from django.conf import settings
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode
from django.utils import html

class NgwCalendarWidget(forms.TextInput):
    class Media:
        #css = {
        #    'all': ('pretty.css',)
        #}
        js = ('ngw.js', 'calendar.js', 'DateTimeShortcuts.js')


class FilterMultipleSelectWidget(forms.SelectMultiple):
    class Media:
        js = ('ngw.js',)

    def __init__(self, verbose_name, is_stacked, attrs=None, choices=()):
        self.verbose_name = verbose_name
        self.is_stacked = is_stacked
        super(FilterMultipleSelectWidget, self).__init__(attrs, choices)

    def render(self, name, value, attrs=None, choices=()):
        output = [super(FilterMultipleSelectWidget, self).render(name, value, attrs, choices)]
        output.append(u'<script type="text/javascript">addEvent(window, "load", function(e) {')
        # TODO: 'id_' is hard-coded here. This should instead use the correct
        # API to determine the ID dynamically.
        output.append(u'SelectFilter.init("id_%s", "%s", %s, "%s"); });</script>\n' % \
            (name, self.verbose_name.replace(u'"', u'\\"'), int(self.is_stacked), settings.STATIC_URL+'admin/'))
        return mark_safe(u''.join(output))


# That class is a clone of forms.CheckboxSelectMultiple
# It only adds an extra class=multiplechoice to the <ul>
class NgwCheckboxSelectMultiple(forms.SelectMultiple):
    def render(self, name, value, attrs=None, choices=()):
        if value is None: value = []
        has_id = attrs and attrs.has_key('id')
        final_attrs = self.build_attrs(attrs, name=name)
        output = [u'<ul class=multiplechoice>']
        str_values = set([smart_unicode(v) for v in value]) # Normalize to strings.
        for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
            # If an ID attribute was given, add a numeric index as a suffix,
            # so that the checkboxes don't all have the same ID attribute.
            if has_id:
                final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
            cb = forms.CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
            option_value = smart_unicode(option_value)
            rendered_cb = cb.render(name, option_value)
            output.append(u'<li><label>%s %s</label></li>' % (rendered_cb, html.escape(smart_unicode(option_label))))
        output.append(u'</ul>')
        return u'\n'.join(output)

    def id_for_label(self, id_):
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_0'
        return id_
    id_for_label = classmethod(id_for_label)


