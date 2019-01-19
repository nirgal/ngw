import logging

from django.core.management.base import BaseCommand

from ngw.core import perms
from ngw.core.models import GROUP_EVERYBODY, Contact


class Command(BaseCommand):
    help = 'Recover lost contacts'

    def handle(self, *args, **options):
        logger = logging.getLogger('contactrecover')
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{asctime} {name} {levelname!s:8} {message}', style='{'))
        logger.addHandler(handler)
        logger.propagate = False
        verbosity = int(options['verbosity'])
        if verbosity == 0:
            logger.setLevel(logging.ERROR)
        elif verbosity == 1:
            logger.setLevel(logging.WARNING)
        elif verbosity == 2:
            logger.setLevel(logging.INFO)
        elif verbosity == 3:
            logger.setLevel(logging.DEBUG)

        for contact in Contact.objects.extra(where=[
                ('NOT EXISTS (SELECT * FROM contact_in_group'
                 ' WHERE contact_id=contact.id'
                 ' AND group_id IN (SELECT self_and_subgroups({}))'
                 ' AND flags & {} <> 0)')
                .format(GROUP_EVERYBODY, perms.MEMBER)]):
            logger.error('%s (#%s) is not member of group EVERYBODY',
                         contact.name,
                         contact.id)
