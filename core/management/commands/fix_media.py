# -*- encoding: utf-8 -*-

from django.core.management.base import NoArgsCommand
from ngw.core.models import ContactGroup

class Command(NoArgsCommand):
    help = 'Creates missing media folders'

    def handle_noargs(self, **options):
        for group in ContactGroup.objects.all():
            group.check_static_folder_created()
