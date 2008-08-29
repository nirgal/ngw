# -*- encoding: utf-8 -*-

#TODO: æĳœ

# for range \u00c0 \u0179
letter_to_alternatives_lower={
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

letter_to_alternatives={}
for letter,alternatives in letter_to_alternatives_lower.iteritems():
    letter_to_alternatives[letter] = alternatives
    letter_to_alternatives[letter.upper()] = alternatives.upper()


alternative_to_letter = {}
for letter,alternatives in letter_to_alternatives_lower.iteritems():
    for alternative in alternatives:
        alternative_to_letter[alternative] = letter
        alternative_to_letter[alternative.upper()] = letter.upper()

def remove_decoration(utxt):
    result = u""
    for l in utxt:
        if l in alternative_to_letter:
            l = alternative_to_letter[l]
        ord(l) < 128
        result += l
    return result

def str_match_withdecoration(txt):
    result=u""
    for c in txt:
        c = c.lower()
        if c in alternative_to_letter.keys():
            c = alternative_to_letter[c]
        if c in letter_to_alternatives.keys():
            result += u"["+c+letter_to_alternatives[c]+c.upper()+letter_to_alternatives[c.upper()]+u"]"
        else:
            result += c
    return result

