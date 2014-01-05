#!/usr/bin/python

from __future__ import print_function, unicode_literals
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ngw.settings')
    sys.path.append('/usr/lib')

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
