# -*- encoding: utf-8 -*-

from django import forms

class NgwCalendarWidget(forms.TextInput):
    class Media:
        #css = {
        #    'all': ('pretty.css',)
        #}
        js = ('ngw.js', 'calendar.js', 'DateTimeShortcuts.js')


