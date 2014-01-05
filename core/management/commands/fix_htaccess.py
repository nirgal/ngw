# -*- encoding: utf-8 -*-

from __future__ import print_function, unicode_literals
from django.core.management.base import NoArgsCommand
from ngw.core.models import ContactGroup

class Command(NoArgsCommand):
    help = 'Creates missing folders and their .htaccess after db restore'

    def handle_noargs(self, **options):
        for group in ContactGroup.objects.all():
            group.check_static_folder_created()
