import json
import os
from datetime import datetime

import crack
import magic
from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template, loader
from django.utils import formats, html, http
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from ngw.core import gpg
from ngw.core.models import (AllEventsNotReactedSince,
                             AllEventsReactionYearRatioLess,
                             AllEventsReactionYearRatioMore, Choice,
                             ContactField, FieldFilterAGE_GE,
                             FieldFilterChoiceEQ, FieldFilterChoiceNEQ,
                             FieldFilterDoubleChoiceHAS,
                             FieldFilterDoubleChoiceHASNOT, FieldFilterEQ,
                             FieldFilterFUTURE, FieldFilterGE, FieldFilterIEQ,
                             FieldFilterIGE, FieldFilterIGT, FieldFilterILE,
                             FieldFilterILIKE, FieldFilterILT, FieldFilterINE,
                             FieldFilterLE, FieldFilterLIKE,
                             FieldFilterMultiChoiceHAS,
                             FieldFilterMultiChoiceHASNOT, FieldFilterNEQ,
                             FieldFilterNotNull, FieldFilterNull,
                             FieldFilterStartsWith, FieldFilterVALID_GT,
                             NameFilterStartsWith, register_contact_field_type)
from ngw.core.widgets import DoubleChoicesField, OnelineCheckboxSelectMultiple


#                            GroupFilterIsMember, GroupFilterIsNotMember,
#                            GroupFilterIsInvited, GroupFilterIsNotInvited,
#                            GroupFilterDeclinedInvitation,
#                            GroupFilterNotDeclinedInvitation


class RibField(forms.Field):
    # TODO handle international IBAN numbers
    # http://fr.wikipedia.org/wiki/ISO_13616
    def clean(self, value):
        """
        Validate the RIB key
        """
        super().clean(value)
        if value in (None, ""):
            return None
        iso_value = ""
        for c in value:
            if c == " ":
                continue  # ignore spaces
            if c >= "0" and c <= "9":
                iso_value += c
                continue
            c = c.upper()
            if c >= "A" and c <= "I":
                iso_value += str(ord(c)-64)
            elif c >= "J" and c <= "R":
                iso_value += str(ord(c)-73)
            elif c >= "S" and c <= "Z":
                iso_value += str(ord(c)-81)
            else:
                raise forms.ValidationError("Illegal character "+c)

        if len(iso_value) != 23:
            raise forms.ValidationError(
                _("There must be 23 non blank characters."))

        # print(iso_value)
        if int(iso_value) % 97:
            raise forms.ValidationError(_("CRC error"))

        return value


class TextContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return forms.CharField(label=self.name, required=False,
                               help_text=self.hint)

    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ,
                FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull,
                FieldFilterNotNull,)
register_contact_field_type(TextContactField, 'TEXT',
                            ugettext_lazy('Text'), has_choice=0)


class LongTextContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return forms.CharField(label=self.name, widget=forms.Textarea,
                               required=False, help_text=self.hint)

    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ,
                FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull,
                FieldFilterNotNull,)
register_contact_field_type(LongTextContactField, 'LONGTEXT',
                            ugettext_lazy('Long Text'), has_choice=0)


class NumberContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return forms.IntegerField(label=self.name, required=False,
                                  help_text=self.hint)

    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterIEQ, FieldFilterINE, FieldFilterILE,
                FieldFilterIGE, FieldFilterILT, FieldFilterIGT,
                FieldFilterNull, FieldFilterNotNull,)

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            int(value)
        except ValueError:
            return False
        return True
register_contact_field_type(NumberContactField, 'NUMBER',
                            ugettext_lazy('Number'), has_choice=0)


class DateContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return forms.DateField(label=self.name, required=False,
                               help_text=self.hint, widget=AdminDateWidget)

    def format_value_html(self, value):
        value = datetime.strptime(value, '%Y-%m-%d')
        return formats.date_format(value, "DATE_FORMAT")

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return False
        return True

    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterLE, FieldFilterGE, FieldFilterAGE_GE,
                FieldFilterVALID_GT, FieldFilterFUTURE, FieldFilterNull,
                FieldFilterNotNull,)
register_contact_field_type(DateContactField, 'DATE',
                            ugettext_lazy('Date'), has_choice=0)


class DateTimeContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return forms.DateTimeField(label=self.name, required=False,
                                   help_text=self.hint)

    def format_value_html(self, value):
        value = self.db_value_to_formfield_value(value)
        return formats.date_format(value, "DATETIME_FORMAT")

    def formfield_value_to_db_value(self, value):
        return datetime.strftime(value, '%Y-%m-%d %H:%M:%S')

    def db_value_to_formfield_value(self, value):
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return False
        return True

    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(DateTimeContactField, 'DATETIME',
                            ugettext_lazy('Date time'), has_choice=0)


class EmailContactField(ContactField):
    class Meta:
        proxy = True

    def format_value_html(self, value):
        if gpg.is_email_secure(value):
            gpg_indicator = (
                ' <a href="{link}">'
                '<img src="{static_dir}ngw/key.jpeg"'
                ' alt=key title="{alt}" border=0>'
                '</a>'
                ).format(
                    link='/pks/lookup?op=get&options=mr&extact=on&search='
                         + http.urlquote_plus(value),
                    static_dir=settings.STATIC_URL,
                    alt=_('GPG key available'),
                )
        else:
            gpg_indicator = ''
        return '<a href="mailto:{value}">{value}</a>{gpg_indicator}'.format(
            value=value,
            gpg_indicator=gpg_indicator)

    def get_form_fields(self):
        return forms.EmailField(label=self.name, required=False,
                                help_text=self.hint)

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            forms.EmailField().clean(value)
        except forms.ValidationError:
            return False
        return True

    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ,
                FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull,
                FieldFilterNotNull,)
register_contact_field_type(EmailContactField, 'EMAIL',
                            ugettext_lazy('E.Mail'), has_choice=0)


class PhoneContactField(ContactField):
    class Meta:
        proxy = True

    def format_value_html(self, value):
        # rfc3966
        return '<a href="tel:{value}">{value}</a>'.format(value=value)

    def get_form_fields(self):
        return forms.CharField(label=self.name, max_length=255,
                               required=False, help_text=self.hint)

    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ,
                FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull,
                FieldFilterNotNull,)
register_contact_field_type(PhoneContactField, 'PHONE',
                            ugettext_lazy('Phone'), has_choice=0)


class RibContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return RibField(label=self.name, required=False, help_text=self.hint)

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            RibField().clean(value)
        except forms.ValidationError:
            return False
        return True

    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ,
                FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull,
                FieldFilterNotNull,)
register_contact_field_type(RibContactField, 'RIB',
                            ugettext_lazy('French bank account'), has_choice=0)


class ChoiceContactField(ContactField):
    class Meta:
        proxy = True

    def type_as_html(self):
        return "{txtname} (<a href='{url}'>{txt}</a>)".format(
            txtname=self.str_type_base(),
            url=self.get_absolute_url() + "choices",
            txt=html.escape(_('Choices')),
            )

    def format_value_text(self, value):
        choices = self.cached_choices()
        try:
            return choices[value]
        except KeyError:
            return _('Error')

    def get_form_fields(self):
        choices = [('', 'Unknown')] + self.choice_group.ordered_choices
        return forms.CharField(max_length=255, label=self.name, required=False,
                               help_text=self.hint,
                               widget=forms.Select(choices=choices))

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        return (Choice.objects.filter(choice_group_id=choice_group_id)
                              .filter(key=value)
                              .count() == 1)

    def get_filters_classes(self):
        return (FieldFilterChoiceEQ, FieldFilterChoiceNEQ,
                FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(ChoiceContactField, 'CHOICE',
                            ugettext_lazy('Choice'), has_choice=1)


class MultipleChoiceContactField(ContactField):
    class Meta:
        proxy = True

    def type_as_html(self):
        return "{txtname} (<a href='{url}'>{txt}</a>)".format(
            txtname=self.str_type_base(),
            url=self.get_absolute_url() + "choices",
            txt=html.escape(_('Choices')),
            )

    def format_value_text(self, value):
        choices = self.cached_choices()
        txt_choice_list = []
        for key in value.split(','):
            if key == '':
                txt_choice_list.append("default")  # this should never occur
                continue
            try:
                value = choices[key]
            except KeyError:
                value = _('Error')
            txt_choice_list.append(value)
        return '<br>'.join(txt_choice_list)

    def get_form_fields(self):
        return forms.MultipleChoiceField(
            label=self.name, required=False,
            help_text=self.hint,
            choices=self.choice_group.ordered_choices,
            widget=OnelineCheckboxSelectMultiple())

    def formfield_value_to_db_value(self, value):
        return ','.join(value)

    def db_value_to_formfield_value(self, value):
        return value.split(',')

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        for v in value.split(','):
            if (Choice.objects.filter(choice_group_id=choice_group_id)
                              .filter(key=v)
                              .count() != 1):
                return False
        return True

    def get_filters_classes(self):
        return (FieldFilterMultiChoiceHAS, FieldFilterMultiChoiceHASNOT,
                FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(MultipleChoiceContactField, 'MULTIPLECHOICE',
                            ugettext_lazy('Multiple choice'), has_choice=1)


class MultipleDoubleChoiceContactField(ContactField):
    class Meta:
        proxy = True

    def type_as_html(self):
        return (
            "{txtname} ("
            "<a href='{url1}'>{txt1}</a>, "
            "<a href='{url2}'>{txt2}</a>)"
            ).format(
                txtname=self.str_type_base(),
                url1=self.get_absolute_url() + "choices",
                txt1=html.escape(_('Choices column 1')),
                url2=self.get_absolute_url() + "choices2",
                txt2=html.escape(_('Choices column 2')),
                )

    def format_value_text(self, value):
        choices = self.cached_choices()
        choices2 = self.cached_choices2()
        choices_list = []  # list of (val1, val2, key1_index_in_choices)
        for key in value.split(','):
            # if key == '':
            #     choices_list.append("default")  # this should never occur
            #     continue
            try:
                key1, key2 = key.split('-', 1)
                val1 = choices[key1]
                val2 = choices2[key2]
            except (ValueError, KeyError):
                choices_list.append(_('Error'), _('Error'), 0)
                continue
            for index, key1test in enumerate(choices):
                if key1 == key1test:
                    choices_list.append((val1, val2, index))
                    break
            else:
                print('Key {0} lost in {1}'.format(key1, choices))
        choices_list.sort(key=lambda x: x[2])
        t = Template("{% for value1, value2, indexkey1 in choices_list %}"
                     "{{ value1 }} ({{ value2 }})<br>"
                     "{% endfor %}")
        return t.render(Context({'choices_list': choices_list}))

    def get_form_fields(self):
        return DoubleChoicesField(label=self.name, required=False,
                                  help_text=self.hint,
                                  choicegroup1=self.choice_group,
                                  choicegroup2=self.choice_group2)

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        for v in value.split(','):
            try:
                k1, k2 = v.split('-', 1)
            except ValueError:
                return False
            if (Choice.objects.filter(choice_group_id=choice_group_id)
                              .filter(key=k1)
                              .count() != 1):
                return False
            if (Choice.objects.filter(choice_group_id=choice_group2_id)
                              .filter(key=k2)
                              .count() != 1):
                return False
        return True

    def get_filters_classes(self):
        return (FieldFilterDoubleChoiceHAS, FieldFilterDoubleChoiceHASNOT,
                FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(MultipleDoubleChoiceContactField, 'DOUBLECHOICE',
                            ugettext_lazy('Double choices'), has_choice=2)


class PasswordContactField(ContactField):
    class Meta:
        proxy = True

    def format_value_text(self, value):
        return '********'

    def get_form_fields(self):
        return forms.CharField(label=self.name, max_length=255,
                               required=False, help_text=self.hint,
                               widget=forms.PasswordInput)

    def formfield_value_to_db_value(self, value):
        return make_password(value)

    def db_value_to_formfield_value(self, value):
        return ''  # Do not show previous password hash

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            crack.FascistCheck(value)
        except ValueError:
            return False
        else:
            return True
register_contact_field_type(PasswordContactField, 'PASSWORD',
                            ugettext_lazy('Password'), has_choice=0)


class FileContactField(ContactField):
    class Meta:
        proxy = True

    def format_value_html(self, value):
        fileinfo = json.loads(value)
        return loader.render_to_string('file_info.html', fileinfo)

    def get_form_fields(self):
        return forms.FileField(label=self.name, required=False,
                               help_text=self.hint,
                               widget=forms.ClearableFileInput,
                               max_length=10*1024**3)

    def formfield_value_to_db_value(self, value):
        if not value:
            return None
        return json.dumps(value)

    def db_value_to_formfield_value(self, value):
        fileinfo = json.loads(value)
        if fileinfo is False:
            return None
        filename = os.path.join(settings.MEDIA_ROOT, fileinfo['mediafilename'])
        content = open(filename, 'rb').read()
        suf = SimpleUploadedFile.from_dict({
            'filename': fileinfo['filename'],
            'content': content,
            'content-type': fileinfo['content_type']
            })
        # Note that next line is needed, or "clear file" won't work:
        suf.url = os.path.join(settings.MEDIA_URL, fileinfo['mediafilename'])
        return suf

    def get_filters_classes(self):
        return (FieldFilterNull, FieldFilterNotNull,)

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            value = json.loads(value)
        except ValueError:
            return False
        for key in ('mediafilename', 'filename', 'content_type', 'charset',
                    'size'):
            if key not in value:
                print('Key', key, 'not found in', value)
                return False
        return True

    def save_file(self, contact_id, uploadedFile):
        """
        Save the file in /media/fields folder.
        Return json with the information
        """
        dirname = os.path.join(
            settings.MEDIA_ROOT,
            'fields',
            str(self.id))
        if not os.path.isdir(dirname):
            # create the missing directory for that field
            os.mkdir(dirname)
        filename = os.path.join(dirname, str(contact_id))
        f = open(filename, mode='wb')
        try:
            for chunk in uploadedFile.chunks():
                f.write(chunk)
        finally:
            f.close()
        # TODO: don't reload magic on each upload, use a global.
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        content_type_list = m.file(filename).split("; ", 1)
        if len(content_type_list) == 1:
            content_type = content_type_list[0]
            charset = ""
        else:
            content_type = content_type_list[0]
            charset = content_type_list[1]

        return {
            'mediafilename': os.path.join(
                'fields', str(self.id), str(contact_id)),
            'filename': uploadedFile.name,
            'content_type': content_type,
            'charset': charset,
            'size': uploadedFile.size}
register_contact_field_type(FileContactField, 'FILE',
                            ugettext_lazy('File'), has_choice=0)


class ImageContactField(FileContactField):
    class Meta:
        proxy = True

    def default_value_html(self):
        return loader.render_to_string('image_field_default.html', {})

    def format_value_html(self, value):
        fileinfo = json.loads(value)
        return loader.render_to_string('image_field.html', fileinfo)

    def get_form_fields(self):
        return forms.ImageField(label=self.name, required=False,
                                help_text=self.hint,
                                widget=forms.ClearableFileInput,
                                max_length=10*1024**3)

    def formfield_value_to_db_value(self, value):
        if not value:
            return None
        return json.dumps(value)

    def db_value_to_formfield_value(self, value):
        fileinfo = json.loads(value)
        if fileinfo is False:
            return None
        filename = os.path.join(settings.MEDIA_ROOT, fileinfo['mediafilename'])
        content = open(filename, 'rb').read()
        suf = SimpleUploadedFile.from_dict({
            'filename': fileinfo['filename'],
            'content': content,
            'content-type': fileinfo['content_type']
            })
        # Note that next line is needed, or "clear file" won't work:
        suf.url = os.path.join(settings.MEDIA_URL, fileinfo['mediafilename'])
        return suf

    def get_filters_classes(self):
        return (FieldFilterNull, FieldFilterNotNull,)

    @classmethod
    def validate_unicode_value(cls, value,
                               choice_group_id=None, choice_group2_id=None):
        try:
            value = json.loads(value)
        except ValueError:
            return False
        for key in ('mediafilename', 'filename', 'content_type', 'charset',
                    'size'):
            if key not in value:
                print('Key', key, 'not found in', value)
                return False
        return True
register_contact_field_type(ImageContactField, 'IMAGE',
                            ugettext_lazy('Image'), has_choice=0)


class ContactNameMetaField(object):
    @classmethod
    def get_filters_classes(cls):
        return (NameFilterStartsWith, )

    @classmethod
    def get_filters(cls):
        return [filter() for filter in cls.get_filters_classes()]

    @classmethod
    def get_filter_by_name(cls, name):
        return [f for f in cls.get_filters()
                if f.__class__.internal_name == name][0]


class AllEventsMetaField(object):
    @classmethod
    def get_filters_classes(cls):
        return (AllEventsNotReactedSince, AllEventsReactionYearRatioLess,
                AllEventsReactionYearRatioMore, )

    @classmethod
    def get_filters(cls):
        return [filter() for filter in cls.get_filters_classes()]

    @classmethod
    def get_filter_by_name(cls, name):
        return [f for f in cls.get_filters()
                if f.__class__.internal_name == name][0]
