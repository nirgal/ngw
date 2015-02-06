'''
Custom widgets for use in forms.
'''

from django.core.exceptions import ValidationError
from django import forms
from django.utils.safestring import mark_safe
from django.utils import html
from django.utils.html import format_html
from django.utils.translation import ugettext as _
from ngw.core import perms

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


#######################################################################
#
# forms.field for flags (membership)
#
#######################################################################

class FlagsWidget(forms.widgets.MultiWidget):
    def __init__(self, attrs=None):
        #print('attrs:', attrs)
        widgets = []
        if attrs is None:
            attrs = {}
        for flag, longname in perms.FLAGTOTEXT.items():
            widgets.append(forms.widgets.CheckboxInput)
        super().__init__(widgets, attrs)

    def decompress(self, value):
        return [
            value and bool(value & intval) or False
            for intval in perms.FLAGTOINT.values()]


    def render(self, name, value, attrs=None):
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        # value is a list of values, each corresponding to a widget
        # in self.widgets.
        if not isinstance(value, list):
            value = self.decompress(value)
        output = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)

        enumerated_flags = list(perms.FLAGTOINT.keys())

        def id_of(i):
            if id_:
                return '%s_%s' % (id_, i)
            else:
                return 'anonflag_%s' % i

        def name_of_flag(flag):
            'Returns the internal name of the input, 0-based'
            for i, aflag in enumerate(perms.FLAGTOINT.keys()):
                if flag == aflag:
                    return name + '_%s' % i

        for i, widget in enumerate(self.widgets):
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None
            if id_:
                final_attrs = dict(final_attrs, id=id_of(i))

            flag = enumerated_flags[i]
            field_name = name + '_%s' % i

            oncheck_js = ''.join([
                'this.form.%s.checked=true;' % name_of_flag(code)
                for code in perms.FLAGDEPENDS[flag]])
            oncheck_js += ''.join([
                'this.form.%s.checked=false;' % name_of_flag(code)
                for code in perms.FLAGCONFLICTS[flag]])

            onuncheck_js = ''
            for flag1, depflag1 in perms.FLAGDEPENDS.items():
                if flag in depflag1:
                    onuncheck_js += 'this.form.%s.checked=false;' % name_of_flag(flag1)

            final_attrs['onchange'] = 'if (this.checked) {%s} else {%s}' % (oncheck_js, onuncheck_js)

            output.append('<label for="%(id)s">%(widget)s %(label)s</label> ' % {
                'widget': widget.render(field_name, widget_value, final_attrs),
                'label': html.escape(str(perms.FLAGTOTEXT[flag])),
                'id': '%s_%s' % (id_, i)
                })
            if flag == 'd':
                output.append('<br style="clear:both;">')
        return mark_safe(self.format_output(output))


class FlagsField(forms.MultiValueField):
    widget = FlagsWidget
    def __init__(self, *args, **kwargs):
        localize = kwargs.get('localize', False)
        fields = []
        for intval, longname in perms.INTTOTEXT.items():
            fields.append(forms.BooleanField(label=longname, localize=localize, required=False))
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        #print("compressing", data_list)
        result = 0
        i = 0
        for flag, intval in perms.FLAGTOINT.items():
            if data_list[i]:
                result |= intval
            i += 1
        #print("compressed", result)
        return result

#######################################################################
#
# Double choices field & widget
#
#######################################################################

MAX_DOUBLECHOICE_LENGTH = 20

class DoubleChoicesWidget(forms.widgets.MultiWidget):
    def __init__(self, sub_count, sub_choice1, sub_choice2, attrs=None):
        #print('attrs:', attrs)
        widgets = []
        if attrs is None:
            attrs = {}
        for i in range(sub_count):
            widgets.append(forms.widgets.Select(choices=sub_choice1, attrs={'class': 'doublechoicefirst'}))
            widgets.append(forms.widgets.Select(choices=sub_choice2, attrs={'class': 'doublechoicesecond'}))
        super().__init__(widgets, attrs)

    def decompress(self, value):
        #print('decompress', value)
        if not value:
            return ()
        result = []
        for pair in value.split(','):
            result += pair.split('-')
        return result

    def render(self, name, value, attrs=None):
        result = super().render(name, value, attrs)
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        js="""
        <script>
        doublechoice_show('%(id)s', 1);
        </script>
        """
        result += mark_safe(js % { 'id': id_ })
        return result

class DoubleChoicesField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        localize = kwargs.get('localize', False)
        choicegroup1 = kwargs.pop('choicegroup1')
        choicegroup2 = kwargs.pop('choicegroup2')
        choices1 = [('', '---')] + choicegroup1.ordered_choices
        choices2 = [('', '---')] + choicegroup2.ordered_choices
        fields = []
        for i in range(MAX_DOUBLECHOICE_LENGTH):
            fields.append(forms.ChoiceField(choices=choices1))
            fields.append(forms.ChoiceField(choices=choices2))
        super().__init__(fields,
            widget = DoubleChoicesWidget(
                sub_count = MAX_DOUBLECHOICE_LENGTH,
                sub_choice1 = choices1,
                sub_choice2 = choices2),
            *args, **kwargs)
        self.choicegroup1 = choicegroup1
        self.choicegroup2 = choicegroup2

    def compress(self, data_list):
        #print("compressing", data_list)
        result = ''
        for i in range(0, len(data_list), 2):
            col1 = data_list[i]
            col2 = data_list[i+1]
            if not col1 and col2:
                raise ValidationError(_('You must choose column %(missingcol)s for each column %(presentcol)s') %
                    { 'missingcol': self.choicegroup1.name, 'presentcol': self.choicegroup2.name })
            if col1 and not col2:
                raise ValidationError(_('You must choose column %(missingcol)s for each column %(presentcol)s') %
                    { 'missingcol': self.choicegroup2.name, 'presentcol': self.choicegroup1.name })
            if col1 and col2:
                if result:
                    result += ','
                result += col1 + '-' + col2
        #print("compressed", result)
        return result
