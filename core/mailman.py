from ngw.core.models import FIELD_EMAIL


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
        email_base = c.get_fieldvalue_by_id(FIELD_EMAIL) # FIXME
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
