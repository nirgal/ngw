# -*- encoding: utf8 -*-

from django.utils import html

# TODO: We should realy make all the calls to Navbar from url.py

class Navbar(object):
    '''
    This is a breadcrumb builder, to build a navigation bar.
    '''
    def __init__(self, *args):
        self.components = [ (u'', u'Home') ]
        for arg in args:
            self.add_component(arg)

    def add_component(self, arg):
        if isinstance(arg, tuple):
            self.components.append(arg)
        else:
            assert isinstance(arg, unicode)
            self.components.append((arg, arg))
        
    def geturl(self, idx):
        return u''.join(self.components[i][0]+u'/' for i in range(idx+1))

    def getfragment(self, idx):
        result = u''
        if idx != len(self.components)-1:
            result += u'<a href="'+self.geturl(idx)+'\">'
        result += html.escape(self.components[idx][1])
        if idx != len(self.components)-1:
            result += u'</a>'
        return result

    def __unicode__(self):
        return u' › '.join([self.getfragment(i) for i in range(len(self.components)) ])

