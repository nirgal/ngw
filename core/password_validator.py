'''
Password validator based on libcrack
'''

import os

import crack
from django.core.exceptions import ValidationError
from django.utils.translation import get_language
from django.utils.translation import ugettext as _

# Match django locale from
# /usr/lib/python3/dist-packages/django/contrib/sites/locale/
# into system locale from
# /usr/share/i18n/locales
#
# For following data was generated from
#
# cd /usr/share/i18n/locales
# for x in `ls /usr/lib/python3/dist-packages/django/contrib/sites/locale/`
# do
#  echo "'$x': '*searching...*',"
#  for choice in `find -iname $x'_*' | cut -c 3-`
#  do
#   echo "'$x': '"$choice"',"
#  done
# done
#
# and then by selecting a "main" variant.

DJANGO_LANGUAGE_TO_LOCALE = {  # UTF-8 version is a requirement
    'af': 'af_ZA.UTF-8',
    'ar': 'ar_SA.UTF-8',
    'ast': 'ast_ES.UTF-8',
    'az': 'az_AZ.UTF-8',
    'be': 'be_BY.UTF-8',
    'bg': 'bg_BG.UTF-8',
    'bn': 'bn_BD.UTF-8',
    'br': 'br_FR.UTF-8',
    'bs': 'bs_BA.UTF-8',
    'ca': 'ca_ES.UTF-8',
    'cs': 'cs_CZ.UTF-8',
    'cy': 'cy_GB.UTF-8',
    'da': 'da_DK.UTF-8',
    'de': 'de_DE.UTF-8',
    'dsb': 'dsb_DE.UTF-8',
    'el': 'el_GR.UTF-8',
    'en': 'en_US.UTF-8',
    'en_AU': 'en_AU.UTF-8',
    'en_GB': 'en_GB.UTF-8',
    'eo': 'eo.UTF-8',
    'es': 'es_ES.UTF-8',
    'es_AR': 'es_AR.UTF-8',
    'es_CO': 'es_CO.UTF-8',
    'es_MX': 'es_MX.UTF-8',
    'es_VE': 'es_VE.UTF-8',
    'et': 'et_EE.UTF-8',
    'eu': 'eu_ES.UTF-8',
    'fa': 'fa_IR.UTF-8',
    'fi': 'fi_FI.UTF-8',
    'fr': 'fr_FR.UTF-8',
    'fy': 'fy_DE.UTF-8',
    'ga': 'ga_IE.UTF-8',
    'gd': 'gd_GB.UTF-8',
    'gl': 'gl_ES.UTF-8',
    'he': 'he_IL.UTF-8',
    'hi': 'hi_IN.UTF-8',
    'hr': 'hr_HR.UTF-8',
    'hsb': 'hsb_DE.UTF-8',
    'hu': 'hu_HU.UTF-8',
    'hy': 'hy_AM.UTF-8',
    'ia': 'ia_FR.UTF-8',
    'id': 'id_ID.UTF-8',
    # 'io': '*unsupported by locales*',
    'is': 'is_IS.UTF-8',
    'it': 'it_IT.UTF-8',
    'ja': 'ja_JP.UTF-8',
    'ka': 'ka_GE.UTF-8',
    'kk': 'kk_KZ.UTF-8',
    'km': 'km_KH.UTF-8',
    'kn': 'kn_IN.UTF-8',
    'ko': 'ko_KR.UTF-8',
    'lb': 'lb_LU.UTF-8',
    'lt': 'lt_LT.UTF-8',
    'lv': 'lv_LV.UTF-8',
    'mk': 'mk_MK.UTF-8',
    'ml': 'ml_IN.UTF-8',
    'mn': 'mn_MN.UTF-8',
    'mr': 'mr_IN.UTF-8',
    'my': 'my_MM.UTF-8',
    'nb': 'nb_NO.UTF-8',
    'ne': 'ne_NP.UTF-8',
    'nl': 'nl_NL.UTF-8',
    'nn': 'nn_NO.UTF-8',
    'os': 'os_RU.UTF-8',
    'pa': 'pa_PK.UTF-8',
    'pl': 'pl_PL.UTF-8',
    'pt': 'pt_PT.UTF-8',
    'pt_BR': 'pt_BR.UTF-8',
    'ro': 'ro_RO.UTF-8',
    'ru': 'ru_RU.UTF-8',
    'sk': 'sk_SK.UTF-8',
    'sl': 'sl_SI.UTF-8',
    'sq': 'sq_AL.UTF-8',
    'sr': 'sr_RS.UTF-8',
    'sr_Latn': 'sr_RS.UTF-8@latin',
    'sv': 'sv_FI.UTF-8',
    'sw': 'sw_TZ.UTF-8',
    'ta': 'ta_IN.UTF-8',
    'te': 'te_IN.UTF-8',
    'th': 'th_TH.UTF-8',
    'tr': 'tr_TR.UTF-8',
    'tt': 'tt_RU.UTF-8',
    # 'udm': '*unsupported by locales*',
    'uk': 'uk_UA.UTF-8',
    'ur': 'ur_PK.UTF-8',
    'vi': 'vi_VN.UTF-8',
    'zh_Hans': 'zh_CH.UTF-8',
    'zh_Hant': 'zh_TW.UTF-8',
}


class CrackPasswordValidator(object):
    """
    Validate a password according to cracklib
    """

    def validate(self, password, user=None):
        django_lang = get_language()
        new_lang = DJANGO_LANGUAGE_TO_LOCALE.get(django_lang, 'C.UTF-8')
        # print("language for query is", django_lang, ":"
        #       "Locale set to", new_lang)
        oldlang = os.getenv('LANG')
        try:
            os.putenv('LANG', new_lang)
            crack.FascistCheck(password)
        except ValueError as err:
            raise ValidationError(
                    _("Cracklib rejected that password: {}").format(err),
                    code='cracklib',
            )
        finally:
            if oldlang is None:
                os.unsetenv('LANG')
            else:
                os.putenv('LANG', oldlang)

    def get_help_text(self):
        return _("Your password needs to be accepted by cracklib.")
