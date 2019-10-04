'''
Password validator based on libcrack
'''

import crack
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


class CrackPasswordValidator(object):
    """
    Validate a password according to cracklib
    """

    def validate(self, password, user=None):
        try:
            crack.FascistCheck(password)
        except ValueError as err:
            # raise forms.ValidationError("{}".format(err))
            raise ValidationError(
                    # TODO: cracklibs already translate!
                    # See LANG ?
                    _("Cracklib rejected that password: {}").format(err),
                    code='cracklib',
            )

    def get_help_text(self):
        return _("Your password needs to be accepted by cracklib.")
