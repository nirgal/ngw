import logging
from django.core.management.base import NoArgsCommand
from ngw.core.models import Contact, GROUP_EVERYBODY
from ngw.core import perms

class Command(NoArgsCommand):
    help = 'Recover lost contacts'

    def handle_noargs(self, **options):
        logger = logging.getLogger('contactrecover')
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s'))
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

        for contact in Contact.objects.extra(where=['NOT EXISTS (SELECT * FROM contact_in_group WHERE contact_id=contact.id AND group_id IN (SELECT self_and_subgroups(%s)) AND flags & %s <> 0)' % (GROUP_EVERYBODY, perms.MEMBER)]):
            logger.error('%s is not member of group EVERYBODY', contact)
