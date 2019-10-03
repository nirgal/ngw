'''
Custom widgets for use in forms.
'''

from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from ngw.core import perms

#######################################################################
#
# forms.field for flags (membership)
#
#######################################################################

# class FlagsWidgetOld(forms.widgets.MultiWidget):
#
#     def __init__(self, attrs=None):
#         # print('attrs:', attrs)
#         widgets = []
#         if attrs is None:
#             attrs = {}
#         for flag, longname in perms.FLAGTOTEXT.items():
#             widgets.append(forms.widgets.CheckboxInput(attrs={
#                 'title': 'toto', # works ok
#                 }))
#         super().__init__(widgets, attrs)
#
#     def decompress(self, value):
#         return [
#             value and bool(value & intval) or False
#             for intval in perms.FLAGTOINT.values()]
#
#     def render(self, name, value, attrs=None):
#         if self.is_localized:
#             for widget in self.widgets:
#                 widget.is_localized = self.is_localized
#         # value is a list of values, each corresponding to a widget
#         # in self.widgets.
#         if not isinstance(value, list):
#             value = self.decompress(value)
#         output = []
#         final_attrs = self.build_attrs(attrs)
#         id_ = final_attrs.get('id', None)
#
#         enumerated_flags = list(perms.FLAGTOINT.keys())
#
#         def id_of(i):
#             if id_:
#                 return '{}_{}'.format(id_, i)
#             else:
#                 return 'anonflag_{}'.format(i)
#
#         def name_of_flag(flag):
#             'Returns the internal name of the input, 0-based'
#             for i, aflag in enumerate(perms.FLAGTOINT.keys()):
#                 if flag == aflag:
#                     return name + '_{}'.format(i)
#
#         for i, widget in enumerate(self.widgets):
#             try:
#                 widget_value = value[i]
#             except IndexError:
#                 widget_value = None
#             if id_:
#                 final_attrs = dict(final_attrs, id=id_of(i), required=False)
#
#             flag = enumerated_flags[i]
#             field_name = name + '_{}'.format(i)
#
#             oncheck_js = ''.join([
#                 'this.form.{}.checked=true;'.format(name_of_flag(code))
#                 for code in perms.FLAGDEPENDS[flag]])
#             oncheck_js += ''.join([
#                 'this.form.{}.checked=false;'.format(name_of_flag(code))
#                 for code in perms.FLAGCONFLICTS[flag]])
#
#             onuncheck_js = ''
#             for flag1, depflag1 in perms.FLAGDEPENDS.items():
#                 if flag in depflag1:
#                     onuncheck_js += ('this.form.{}.checked=false;'
#                                      .format(name_of_flag(flag1)))
#
#             final_attrs['onchange'] = (
#                 'if (this.checked) {{{oncheck_js}}} else {{{onuncheck_js}}}'
#                 .format(
#                     oncheck_js=oncheck_js,
#                     onuncheck_js=onuncheck_js))
#
#             output.append(
#                 '<label for="{id}">{widget} {label}</label> '.format(
#                     widget=widget.render(
#                         field_name, widget_value, final_attrs),
#                     label=html.escape(str(perms.FLAGTOTEXT[flag])),
#                     id='{}_{}'.format(id_, i)
#                     ))
#             if flag == 'D':
#                 output.append('<br style="clear:both;">')
#         return mark_safe(self.format_output(output))
#
#
# class FlagsFieldOld(forms.MultiValueField):
#     widget = FlagsWidgetOld
#
#     def __init__(self, **kwargs):
#         localize = kwargs.get('localize', False)
#         if 'fields' not in kwargs:
#             kwargs['fields'] = []
#             for intval, longname in perms.INTTOTEXT.items():
#                 kwargs['fields'].append(forms.BooleanField(
#                     label=longname, localize=localize))
#         super().__init__(**kwargs)
#
#     def compress(self, data_list):
#         # print("compressing", data_list)
#         result = 0
#         i = 0
#         for flag, intval in perms.FLAGTOINT.items():
#             if data_list[i]:
#                 result |= intval
#             i += 1
#         # print("compressed", result)
#         return result


class FlagsWidget(forms.CheckboxSelectMultiple):

    def create_option(
            self, name, value, label, selected, index,
            subindex=None, attrs=None):
        '''
        Default version with extra "onchange" javascript hack
        '''
        parameters = super().create_option(
                name, value, label, selected, index, subindex, attrs)

        input_id = attrs['id'] if attrs else None  # id of the FlagsWidget
        value = parameters['value']

        oncheck_js = ''.join([
            "getElementById('{}').checked=true;".format(
                self.id_for_flag(input_id, code))
            for code in perms.FLAGDEPENDS[value]])
        oncheck_js += ''.join([
            "getElementById('{}').checked=false;".format(
                self.id_for_flag(input_id, code))
            for code in perms.FLAGCONFLICTS[value]])

        onuncheck_js = ''
        for flag1, depflag1 in perms.FLAGDEPENDS.items():
            if value in depflag1:
                onuncheck_js += ("getElementById('{}').checked=false;"
                                 .format(self.id_for_flag(input_id, flag1)))

        parameters['attrs']['onchange'] = (
            'if (this.checked) {{{oncheck_js}}} else {{{onuncheck_js}}};'
            .format(
                oncheck_js=oncheck_js,
                onuncheck_js=onuncheck_js))

        return parameters

    def django_composite_id_to_index(self, flag):
        igroup, iflag = flag.split('_')
        igroup = int(igroup)
        iflag = int(iflag)
        index = iflag
        if igroup > 0:
            index += 4
        return index

    def id_for_flag(self, id_, flag):
        return super().id_for_label(id_, flag)

    def id_for_label(self, id_, index='0'):
        # We use the perm letter as a input id suffix
        # This makes the javascript easier

        try:
            index = self.django_composite_id_to_index(index)
        except ValueError:
            return super().id_for_label(id_, index)
        flag = list(perms.FLAGTOINT.keys())[index]
        return self.id_for_flag(id_, flag)

    def get_context(self, name, value, attrs):
        # Here value is an integer (bit aray of permissions)
        value = perms.int_to_flags(value)  # Change into a string
        value = [char for char in value]  # Then into an array of letters
        context = super().get_context(name, value, attrs)
        return context


class FlagsField(forms.MultipleChoiceField):
    widget = FlagsWidget(
            attrs={'class': 'onelinechoices'})

    def __init__(self, choices=[], **kargs):

        choices_memb = []
        choices_perm = []
        for letter, longname in perms.FLAGTOTEXT.items():
            if letter in 'imdD':
                choices_memb.append([letter, longname])
            else:
                choices_perm.append([letter, longname])
        choices = [
                [_('Membership'), choices_memb],
                [_('Access'), choices_perm],
            ]
        # choices = perms.FLAGTOTEXT.items()
        super().__init__(choices, **kargs)

    def to_python(self, value):
        value = super().to_python(value)  # change into an array of letters
        value = ''.join(value)  # change into a string
        value = perms.flags_to_int(value)  # change into a bits
        return value

    def validate(self, value):
        pass


#######################################################################
#
# Double choices field & widget
#
#######################################################################

MAX_DOUBLECHOICE_LENGTH = 20


class DoubleChoicesWidget(forms.widgets.MultiWidget):
    def __init__(self, sub_count, sub_choice1, sub_choice2, attrs=None):
        # print('attrs:', attrs)
        widgets = []
        if attrs is None:
            attrs = {}
        for i in range(sub_count):
            widgets.append(forms.widgets.Select(
                choices=sub_choice1, attrs={'class': 'doublechoicefirst'}))
            widgets.append(forms.widgets.Select(
                choices=sub_choice2, attrs={'class': 'doublechoicesecond'}))
        super().__init__(widgets, attrs)

    def decompress(self, value):
        # print('decompress', value)
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
        js = """
        <script>
        doublechoice_show('{id}', 1);
        </script>
        """
        result += mark_safe(js.format(id=id_))
        return result


class DoubleChoicesField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        # localize = kwargs.get('localize', False)
        choicegroup1 = kwargs.pop('choicegroup1')
        choicegroup2 = kwargs.pop('choicegroup2')
        choices1 = [('', '---')] + choicegroup1.ordered_choices
        choices2 = [('', '---')] + choicegroup2.ordered_choices
        fields = []
        for i in range(MAX_DOUBLECHOICE_LENGTH):
            fields.append(forms.ChoiceField(choices=choices1))
            fields.append(forms.ChoiceField(choices=choices2))
        super().__init__(
            fields,
            widget=DoubleChoicesWidget(
                sub_count=MAX_DOUBLECHOICE_LENGTH,
                sub_choice1=choices1,
                sub_choice2=choices2),
            *args, **kwargs)
        self.choicegroup1 = choicegroup1
        self.choicegroup2 = choicegroup2

    def compress(self, data_list):
        # print("compressing", data_list)
        result = ''
        for i in range(0, len(data_list), 2):
            col1 = data_list[i]
            col2 = data_list[i+1]
            if not col1 and col2:
                raise ValidationError(
                    _('You must choose a column #1 for each column #2.'))
            if col1 and not col2:
                raise ValidationError(
                    _('You must choose a column #2 for each column #1.'))
            if col1 and col2:
                if result:
                    result += ','
                result += col1 + '-' + col2
        # print("compressed", result)
        return result
