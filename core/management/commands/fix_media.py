from django.core.management.base import BaseCommand

from ngw.core.models import ContactGroup


class Command(BaseCommand):
    help = 'Creates missing media folders'

    def handle(self, *args, **options):
        for group in ContactGroup.objects.all():
            group.check_static_folder_created()
