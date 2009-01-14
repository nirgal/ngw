#!/usr/bin/env python
import os, random, sys, uno
from sys import platform
from time import sleep
from com.sun.star.connection import NoConnectException
from com.sun.star.uno import Exception as UnoException
from com.sun.star.beans import PropertyValue

TMPDIR="/tmp"

def get_outputprefix():
    """ generate a random filename so that there is no file in TMPDIR that starts
    with that name"""
    for x in range(20):
        basename = str(random.randint(11111111,99999999))
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
    mailmerge.DataSourceName="ngw"
    mailmerge.CommandType=uno.getConstantByName("com.sun.star.sdb.CommandType.TABLE") # see com.sun.star.sdb.CommandType
    mailmerge.Command="public.mailinginfo"
    if ids:
        mailmerge.Filter='"id" IN ('+','.join(ids)+')'
    #mailmerge.Filter='"id"=1'
    mailmerge.DocumentURL=uno.systemPathToFileUrl(filename_in)
    mailmerge.OutputType = uno.getConstantByName("com.sun.star.text.MailMergeType.FILE") # see com.sun.star.text.MailMergeType
    mailmerge.OutputURL=uno.systemPathToFileUrl(TMPDIR)
    mailmerge.FileNamePrefix=outputprefix
    mailmerge.SaveAsSingleFile=True
    mailmerge.execute(())
    mailmerge.dispose()

    for fn in os.listdir(TMPDIR):
        if fn.startswith(outputprefix):
            return os.path.join(TMPDIR, fn)

if __name__ == "__main__":
    ids = [ sys.argv[x] for x in range(1,len(sys.argv)) ]
    #xcontext = oo_bootstrap()
    result = ngw_mailmerge("/usr/lib/ngw/mailing/forms/welcome.odt", ids)
    print result
    
