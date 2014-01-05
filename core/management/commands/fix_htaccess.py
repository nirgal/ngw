# -*- encoding: utf-8 -*-

from __future__ import print_function
from django.core.management.base import NoArgsCommand
from ngw.core.models import ContactGroup

class Command(NoArgsCommand):
    help = 'Creates missing folders and their .htaccess after db restore'

    def handle_noargs(self, **options):
        for g in ContactGroup.objects.all():
            g.check_static_folder_created()
