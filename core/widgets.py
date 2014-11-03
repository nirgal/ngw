# -*- encoding: utf-8 -*-
'''
Custom widgets for use in forms.
'''

from django import forms
from django.utils.safestring import mark_safe
from django.utils.html import format_html

class OnelineCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    '''
    That class is a clone of forms.CheckboxSelectMultiple
    It only adds an extra class=onelinechoices to the <ul>
    '''
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
                output.append(format_html('<li>{0}</li>', str(widget)))
            output.append('</ul>')
            return mark_safe('\n'.join(output))
    renderer = NgwCheckboxFieldRenderer
