# -*- encoding: utf-8 -*-

#TODO: æĳœ

# for range \u00c0 \u0179
letter_to_alternatives={
    u'a': u'àáâãäåāăą',
    u'c': u'çćĉċč',
    u'd': u'ďđ',
    u'e': u'èéêëēĕėęě',
    u'g': u'ĝğġģ',
    u'h': u'ĥħ',
    u'i': u'ìíîïĩīĭįı',
    u'j': u'ĵ',
    u'k': u'ķ',
    u'l': u'ĺļľŀł',
    u'n': u'ñńņňŉŋ',
    u'o': u'òóôöøōŏő',
    u'r': u'ŕŗř',
    u's': u'śŝşš',
    u't': u'ţťŧ',
    u'u': u'ùúûüũūŭůűų',
    u'w': u'ŵ',
    u'y': u'ýÿŷ',
    u'z': u'źżž',
}

# lower case version only, for now
alternative_to_letter = {}
for letter,alternatives in letter_to_alternatives.iteritems():
    for alternative in alternatives:
        alternative_to_letter[alternative] = letter

def remove_decoration(utxt):
    # TODO: support upper_cases
    result = u""
    for l in utxt:
        if l in alternative_to_letter:
            l = alternative_to_letter[l]
        ord(l) < 128
        result += l
    return result
