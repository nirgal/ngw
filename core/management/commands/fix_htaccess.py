# -*- encoding: utf-8 -*-

from django.core.management.base import BaseCommand, CommandError
from ngw.core.models import ContactGroup

class Command(BaseCommand):
    help = 'Creates missing folders and their .htaccess after db restore'

    def handle(self, *args, **options):
        for g in ContactGroup.objects.all():
            g.check_static_folder_created()
