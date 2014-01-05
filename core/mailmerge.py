#!/usr/bin/env python

from __future__ import print_function, unicode_literals
import os
import random
import sys
import uno
import subprocess
from time import sleep
from com.sun.star.connection import NoConnectException
from com.sun.star.uno import Exception as UnoException
from com.sun.star.beans import PropertyValue

TMPDIR = '/tmp'

def get_outputprefix():
    """ generate a random filename so that there is no file in TMPDIR that starts
    with that name"""
    for x in range(20):
        basename = str(random.randint(11111111, 99999999))
        for fn in os.listdir(TMPDIR):
            if fn.startswith(basename):
                break # found a match! Try another name
        return basename
    raise ValueError("Can't generate a random prefix")

    
def ngw_mailmerge(filename_in, ids):
    outputprefix = get_outputprefix()

    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    mailmerge = context.ServiceManager.createInstanceWithContext("com.sun.star.text.MailMerge", context)
    #mailmerge = xcontext.getServiceManager().createInstanceWithContext("com.sun.star.text.MailMerge", xcontext)
    mailmerge.DataSourceName = "ngw"
    mailmerge.CommandType = uno.getConstantByName("com.sun.star.sdb.CommandType.TABLE") # see com.sun.star.sdb.CommandType
    mailmerge.Command = "public.mailinginfo"
    if ids:
        mailmerge.Filter = '"id" IN ('+','.join(ids)+')'
    #mailmerge.Filter='"id"=1'
    mailmerge.DocumentURL = uno.systemPathToFileUrl(filename_in)
    mailmerge.OutputType = uno.getConstantByName("com.sun.star.text.MailMergeType.FILE") # see com.sun.star.text.MailMergeType
    mailmerge.OutputURL = uno.systemPathToFileUrl(TMPDIR)
    mailmerge.FileNamePrefix = outputprefix
    mailmerge.SaveAsSingleFile = True
    mailmerge.execute(())  # BOUM
    mailmerge.dispose()

    for fn in os.listdir(TMPDIR):
        if fn.startswith(outputprefix):
            return os.path.join(TMPDIR, fn)



def ngw_mailmerge2(filename_in, fields):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")

    desktop = context.ServiceManager.createInstance('com.sun.star.frame.Desktop')
    document = desktop.loadComponentFromURL(uno.systemPathToFileUrl(filename_in), '_blank', 0, ())

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

    oldumask = os.umask(0077)
    os.umask(0007)

    filename_out = TMPDIR + '/' + get_outputprefix() + '.pdf'

    p1 = PropertyValue()
    p1.Name = 'Overwrite'
    p1.Value = True
    p2 = PropertyValue()
    p2.Name = 'FilterName'
    p2.Value = 'writer_pdf_Export'
    document.storeToURL(uno.systemPathToFileUrl(filename_out), (p1, p2))

    # move to final directory, overriding and permissions
    #subprocess.call(["sudo", "/usr/bin/mvoomail", 'guideogm.pdf', '/usr/lib/guideogm/www/'])

    document.dispose()
    os.umask(oldumask)

    return filename_out



if __name__ == "__main__":
    #xcontext = oo_bootstrap()
    for name in sys.argv[1:]:
        name = unicode(name, 'utf8')
        result = ngw_mailmerge2("/usr/lib/ngw/mailing/forms/welcome.odt", {'name': name})
        result = result.split('/')[-1]
        subprocess.call(["sudo", "/usr/bin/mvoomail", result, '/usr/lib/ngw/mailing/generated'])
        print('/usr/lib/ngw/mailing/generated/'+result)
    
