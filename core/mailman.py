#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
import sys
import os
import logging

def normalize_name(name):
    '''
    looks for upper case words, put them at the end
    '''
    words = name.split(' ')
    lastname = []
    while True:
        if len(words) == 0:
            break
        word = words[0]
        if word == word.upper():
            lastname.append(word)
            del words[0]
        else:
            break
    return ' '.join(words + lastname)
    

def parse_who_result(mailcontent):
    mailman_members = []
    for line in mailcontent.split('\n'):
        if not '@' in line:
            continue
        line = line.strip()
        if ' ' in line:
            email, name = line.split(' ', 1)
            assert name[0] == '(' and name[-1] == ')', 'Invalid name, () not found on line '+line
            name = name[1:-1]
        else:
            email = line
            name = ''
        mailman_members.append((name, email))
    return mailman_members


def format_mailadd(name, email):
    if name:
        result = name + ' '
    else:
        result = ''
    result += '<%s>' % email
    return result

def synchronise_group(cg, mailcontent):
    '''
    takes a contact group
    returns a list of tupples: ('msg', unsubscribe_addr, subscribe_addr)
    '''
    result = []
    mailman_members = parse_who_result(mailcontent)
    unsubscribe_list = []
    subscribe_list = []
    for c in cg.get_all_members():
        email_base = c.get_fieldvalue_by_id(7) # FIXME
        name_base = c.name
        if name_base == email_base:
            name_base = ''
        mailman_names = [name for name, email in mailman_members if email == email_base]
        if not mailman_names:
            result.append((format_mailadd(c.name, email_base) + ' from database is not registered in mailman!',
                           None,
                           format_mailadd(c.name, email_base)))
        else:
            mailman_name = mailman_names[0]
            if mailman_name != name_base:
                result.append(('<%s> is called "%s" in mailman but it should be "%s"' % \
                                  (email_base, mailman_name, name_base),
                               format_mailadd(mailman_name, email_base),
                               format_mailadd(name_base, email_base)))
            mailman_members.remove((mailman_name, email_base))

    for name, email in mailman_members:
        result.append((format_mailadd(name, email) + ' should not be registered in mailman.',
                       format_mailadd(name, email),
                       None))
    return result


if __name__ == '__main__':
    sys.path += ['/usr/lib/']
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ngw.settings'

    from ngw.core.models import ContactGroup
    from optparse import OptionParser
    from django.utils.encoding import force_text
    parser = OptionParser(usage='%prog [options] filename dump|normalize|check')
    parser.add_option('-g', '--group', action='store', dest='groupid', type='int', help='specify groupid')

    options, args = parser.parse_args()

    if len(args) != 2:
        print('Need exactly 2 arguments\n', file=sys.stderr)
        parser.print_help(file=sys.stderr)
        sys.exit(1)
    
    action = args[1]

    filecontent = open(args[0]).read()
    filecontent = force_text(filecontent)

    if action == 'dump':
        mailman_members = parse_who_result(filecontent)
        for name, email in mailman_members:
            if name:
                print(name, '->', normalize_name(name), end=' ')
            print('<%s>' % email)
    elif action == 'normalize':
        mailman_members = parse_who_result(filecontent)
        print('*')
        print('unscrubsribe:')
        for name, email in mailman_members:
            if name != normalize_name(name):
                print(name, end=' ')
                print('<%s>' % email)
        print('*')
        print('scrubsribe:')
        for name, email in mailman_members:
            if name != normalize_name(name):
                print(normalize_name(name), end=' ')
                print('<%s>' % email)

    elif action == 'check':
        assert options.groupid is not None, 'You must use -g option'
        cg = ContactGroup.objects.get(pk=options.groupid)
        print('Synching', cg.name)
        
        msg, unsubscribe_list, subscribe_list = synchronise_group(cg, filecontent)

        print(msg)

        print('*'*80)
        print('unscubscribe')
        for cmd in unsubscribe_list:
            print(cmd)
        print()
        print()
        print('*'*80)
        print('subscribe')
        for cmd in subscribe_list:
            print(cmd)
        print()
        print()


    else:
        print('unknow action', action, file=sys.stderr)