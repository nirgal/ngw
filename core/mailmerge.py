#!/usr/bin/env python3

import os
import random
import subprocess
import sys

import uno

from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException

# from com.sun.star.uno import Exception as UnoException


TMPDIR = '/tmp'


def get_outputprefix():
    """ generate a random filename so that there is no file in TMPDIR that starts
    with that name"""
    for x in range(20):
        basename = str(random.randint(11111111, 99999999))
        for fn in os.listdir(TMPDIR):
            if fn.startswith(basename):
                break  # found a match! Try another name
        return basename
    raise ValueError("Can't generate a random prefix")


def ngw_mailmerge(filename_in, fields, target_dir):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    try:
        context = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;"
            "StarOffice.ComponentContext")
    except NoConnectException:
        print("Can't reach libreoffice on localhost on UDP port 2002")
        raise

    desktop = context.ServiceManager.createInstance(
        'com.sun.star.frame.Desktop')
    document = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(filename_in), '_blank', 0, ())

    find_replace = document.createSearchDescriptor()

    p1 = PropertyValue()
    p1.Name = 'SearchRegularExpression'
    p1.Value = True
    find_replace.setPropertyValue('SearchRegularExpression', True)
    find_replace.setSearchString('[{][{]([^}]*)[}][}]')

    found = document.findFirst(find_replace)
    while found:
        field_name = found.getString()[2:-2]
        found.setString(fields.get(field_name, 'FIELD NOT FOUND'))
        found = document.findNext(found.getEnd(), find_replace)

    oldumask = os.umask(0o007)

    filename_out = TMPDIR + '/' + get_outputprefix() + '.pdf'

    p1 = PropertyValue()
    p1.Name = 'Overwrite'
    p1.Value = True
    p2 = PropertyValue()
    p2.Name = 'FilterName'
    p2.Value = 'writer_pdf_Export'
    document.storeToURL(uno.systemPathToFileUrl(filename_out), (p1, p2))

    document.dispose()

    os.umask(oldumask)

    basefilename_out = os.path.basename(filename_out)
    # move to final directory, overriding any permissions
    if subprocess.call([
            "sudo", "/usr/bin/mvoomail", basefilename_out, target_dir]):
        print('File move failed')
        return None

    return basefilename_out


if __name__ == "__main__":
    # xcontext = oo_bootstrap()
    for name in sys.argv[1:]:
        name = unicode(name, 'utf8')
        filename = ngw_mailmerge(
            "/usr/lib/ngw/mailing/templates/resetpassword.odt",
            {'name': name}, '.')
        print(filename)
