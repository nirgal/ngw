from django.utils.translation import ugettext as _


# TODO: We should realy make all the calls to Navbar from url.py

class Navbar(object):
    '''
    This is a breadcrumb builder, to build a navigation bar.
    '''
    def __init__(self, *args):
        self.components = [('', _('home'))]
        for arg in args:
            self.add_component(arg)

    def add_component(self, arg):
        if isinstance(arg, tuple):
            self.components.append(arg)
        else:
            assert isinstance(arg, str)
            self.components.append((arg, arg))
        return self
