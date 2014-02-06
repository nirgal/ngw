# -*- encoding: utf-8 -*-

from __future__ import division, print_function, unicode_literals
from datetime import datetime
from django import forms
from django.utils import http
from django.utils import html
from django.conf import settings
from ngw.core.models import ( ContactField, ChoiceGroup, Choice,
    register_contact_field_type )
from ngw.core.models import (NameFilterStartsWith, FieldFilterStartsWith,
    FieldFilterEQ, FieldFilterNEQ, FieldFilterLE, FieldFilterGE,
    FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,
    FieldFilterIEQ, FieldFilterINE, FieldFilterILT, FieldFilterIGT,
    FieldFilterILE, FieldFilterIGE, FieldFilterAGE_GE, FieldFilterVALID_GT,
    FieldFilterFUTURE, FieldFilterChoiceEQ, FieldFilterChoiceNEQ,
    FieldFilterMultiChoiceHAS, FieldFilterMultiChoiceHASNOT,
    AllEventsNotReactedSince, AllEventsReactionYearRatioLess,
    AllEventsReactionYearRatioMore)
    #, GroupFilterIsMember, GroupFilterIsNotMember, GroupFilterIsInvited, GroupFilterIsNotInvited, GroupFilterDeclinedInvitation, GroupFilterNotDeclinedInvitation
from ngw.core import gpg
from ngw.core.widgets import NgwCalendarWidget, NgwCheckboxSelectMultiple
from ngw.core.templatetags.ngwtags import ngw_date_format, ngw_datetime_format #FIXME



class RibField(forms.Field):
    # TODO handle international IBAN numbers http://fr.wikipedia.org/wiki/ISO_13616
    def clean(self, value):
        """
        Validate the RIB key
        """
        super(RibField, self).clean(value)
        if value in (None, ""):
            return None
        iso_value = ""
        for c in value:
            if c == " ":
                continue # ignore spaces
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
            raise forms.ValidationError("There must be 23 non blank characters.")

        #print(iso_value)
        if int(iso_value) % 97:
            raise forms.ValidationError("CRC error")

        return value




class TextContactField(ContactField):
    class Meta:
        proxy = True
    def get_form_fields(self):
        return forms.CharField(label=self.name, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(TextContactField, 'TEXT', 'Text', has_choice=False)

class LongTextContactField(ContactField):
    class Meta:
        proxy = True
    def get_form_fields(self):
        return forms.CharField(label=self.name, widget=forms.Textarea, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(LongTextContactField, 'LONGTEXT', 'Long Text', has_choice=False)

class NumberContactField(ContactField):
    class Meta:
        proxy = True
    def get_form_fields(self):
        return forms.IntegerField(label=self.name, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterIEQ, FieldFilterINE, FieldFilterILE, FieldFilterIGE, FieldFilterILT, FieldFilterIGT, FieldFilterNull, FieldFilterNotNull,)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            int(value)
        except ValueError:
            return False
        return True
register_contact_field_type(NumberContactField, 'NUMBER', 'Number', has_choice=False)

class DateContactField(ContactField):
    class Meta:
        proxy = True

    def get_form_fields(self):
        return forms.DateField(label=self.name, required=False, help_text='Use YYYY-MM-DD format.' + ' ' + self.hint, widget=NgwCalendarWidget(attrs={'class':'vDateField'}))

    def format_value_html(self, value):
        value = datetime.strptime(value, '%Y-%m-%d')
        return ngw_date_format(value)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterLE, FieldFilterGE, FieldFilterAGE_GE, FieldFilterVALID_GT, FieldFilterFUTURE,  FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(DateContactField, 'DATE', 'Date', has_choice=False)

class DateTimeContactField(ContactField):
    class Meta:
        proxy = True
    def get_form_fields(self):
        return forms.DateTimeField(label=self.name, required=False, help_text='Use YYYY-MM-DD HH:MM:SS format.' + ' ' + self.hint)
    def format_value_html(self, value):
        value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return ngw_datetime_format(value)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterEQ, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(DateTimeContactField, 'DATETIME', 'DateTime', has_choice=False)

class EmailContactField(ContactField):
    class Meta:
        proxy = True
    def format_value_html(self, value):
        if gpg.is_email_secure(value):
            gpg_indicator = ' <a href="/pks/lookup?op=get&options=mr&extact=on&search=' + http.urlquote_plus(value) + '"><img src="' + settings.STATIC_URL + 'static/key.jpeg" alt=key title="GPG key available" border=0></a>'
        else:
            gpg_indicator = ''
        return '<a href="mailto:%(value)s">%(value)s</a>%(gpg_indicator)s' % {'value':value, 'gpg_indicator':gpg_indicator}
    def get_form_fields(self):
        return forms.EmailField(label=self.name, required=False, help_text=self.hint)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            forms.EmailField().clean(value)
        except forms.ValidationError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(EmailContactField, 'EMAIL', 'E.Mail', has_choice=False)

class PhoneContactField(ContactField):
    class Meta:
        proxy = True
    def format_value_html(self, value):
        return '<a href="tel:%(value)s">%(value)s</a>' % {'value':value} # rfc3966
    def get_form_fields(self):
        return forms.CharField(label=self.name, max_length=255, required=False, help_text=self.hint)
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(PhoneContactField, 'PHONE', 'Phone', has_choice=False)

class RibContactField(ContactField):
    class Meta:
        proxy = True
    def get_form_fields(self):
        return RibField(label=self.name, required=False, help_text=self.hint)
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        try:
            RibField().clean(value)
        except forms.ValidationError:
            return False
        return True
    def get_filters_classes(self):
        return (FieldFilterStartsWith, FieldFilterEQ, FieldFilterNEQ, FieldFilterLIKE, FieldFilterILIKE, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(RibContactField, 'RIB', 'French bank account', has_choice=False)

class ChoiceContactField(ContactField):
    class Meta:
        proxy = True
    def type_as_html(self):
        return self.str_type_base() + " (<a href='" + self.choice_group.get_absolute_url() + "'>" + html.escape(self.choice_group.name) + "</a>)"
    def format_value_unicode(self, value):
        chg = self.choice_group
        if chg == None:
            return 'Error'
        try:
            c = Choice.objects.get(choice_group_id=chg.id, key=value)
        except Choice.DoesNotExist:
            return 'Error'
        else:
            return c.value
    def get_form_fields(self):
        return forms.CharField(max_length=255, label=self.name, required=False, help_text=self.hint, widget=forms.Select(choices=[('', 'Unknown')]+self.choice_group.ordered_choices))
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        return Choice.objects.filter(choice_group_id=choice_group_id).filter(key=value).count() == 1
    def get_filters_classes(self):
        return (FieldFilterChoiceEQ, FieldFilterChoiceNEQ, FieldFilterNull, FieldFilterNotNull,)

register_contact_field_type(ChoiceContactField, 'CHOICE', 'Choice', has_choice=True)

class MultipleChoiceContactField(ContactField):
    class Meta:
        proxy = True
    def type_as_html(self):
        return self.str_type_base() + " (<a href='" + self.choice_group.get_absolute_url() + "'>" + html.escape(self.choice_group.name) + "</a>)"
    def format_value_unicode(self, value):
        try:
            chg = ChoiceGroup.objects.get(pk=self.choice_group_id)
        except ChoiceGroup.DoesNotExist:
            print("ChoiceGroup %s was lost!" % self.choice_group_id)
            return 'Error'
        txt_choice_list = []
        for cid in value.split(','):
            if cid == '':
                txt_choice_list.append( "default" ) # this should never occur
                continue
            try:
                c = Choice.objects.get(choice_group_id=chg.id, key=cid)
            except Choice.DoesNotExist:
                print('Choice', cid, 'in', chg, 'was lost.')
                txt_choice_list.append( "error" )
            else:
                txt_choice_list.append( c.value )
        return ', '.join(txt_choice_list)
    def get_form_fields(self):
        return forms.MultipleChoiceField(label=self.name, required=False, help_text=self.hint, choices=self.choice_group.ordered_choices, widget=NgwCheckboxSelectMultiple())
    def formfield_value_to_db_value(self, value):
        return ','.join(value)
    def db_value_to_formfield_value(self, value):
        return value.split(',')
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        for v in value.split(','):
            if Choice.objects.filter(choice_group_id=choice_group_id).filter(key=v).count() != 1:
                return False
        return True
    def get_filters_classes(self):
        return (FieldFilterMultiChoiceHAS, FieldFilterMultiChoiceHASNOT, FieldFilterNull, FieldFilterNotNull,)
register_contact_field_type(MultipleChoiceContactField, 'MULTIPLECHOICE', 'Multiple choice', has_choice=True)


class PasswordContactField(ContactField):
    class Meta:
        proxy = True
    def format_value_unicode(self, value):
        return '********'
    def get_form_fields(self):
        return None
    def formfield_value_to_db_value(self, value):
        raise NotImplementedError()
    def db_value_to_formfield_value(self, value):
        raise NotImplementedError('Cannot reverse hash of a password')
    @classmethod
    def validate_unicode_value(cls, value, choice_group_id=None):
        return len(value)==13 # We are locked with crypt algorithm, right now
register_contact_field_type(PasswordContactField, 'PASSWORD', 'Password', has_choice=False)


class ContactNameMetaField(object):
    @classmethod
    def get_filters_classes(cls):
        return (NameFilterStartsWith, )

    @classmethod
    def get_filters(cls):
        return [ filter() for filter in cls.get_filters_classes() ]

    @classmethod
    def get_filter_by_name(cls, name):
        return [ f for f in cls.get_filters() if f.__class__.internal_name==name][0]


class AllEventsMetaField(object):
    @classmethod
    def get_filters_classes(cls):
        return (AllEventsNotReactedSince, AllEventsReactionYearRatioLess, AllEventsReactionYearRatioMore, )

    @classmethod
    def get_filters(cls):
        return [ filter() for filter in cls.get_filters_classes() ]

    @classmethod
    def get_filter_by_name(cls, name):
        return [ f for f in cls.get_filters() if f.__class__.internal_name==name][0]

