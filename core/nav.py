# -*- encoding: utf8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals
from django.utils import html

# TODO: We should realy make all the calls to Navbar from url.py

class Navbar(object):
    '''
    This is a breadcrumb builder, to build a navigation bar.
    '''
    def __init__(self, *args):
        self.components = [ ('', 'Home') ]
        for arg in args:
            self.add_component(arg)

    def add_component(self, arg):
        if isinstance(arg, tuple):
            self.components.append(arg)
        else:
            assert isinstance(arg, unicode)
            self.components.append((arg, arg))
        
    def geturl(self, idx):
        return ''.join(self.components[i][0] + '/' for i in range(idx+1))

    def getfragment(self, idx):
        result = ''
        if idx != len(self.components)-1:
            result += '<a href="'+self.geturl(idx)+'\">'
        result += html.escape(self.components[idx][1])
        if idx != len(self.components)-1:
            result += '</a>'
        return result

    def __unicode__(self):
        return ' › '.join([self.getfragment(i) for i in range(len(self.components)) ])

