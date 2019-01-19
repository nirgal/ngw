import subprocess

from django.core.management.base import BaseCommand
from django.utils.encoding import force_str

from ngw.core.models import ContactMsg


class Command(BaseCommand):
    help = 'Try to decrypt a message with an AES passphrase'

    def add_arguments(self, parser):
        parser.add_argument('msgid', type=int)
        parser.add_argument('aeskey')

    def handle(self, *args, **options):
        msgid = int(options['msgid'])
        passphrase = options['aeskey']

        msg = ContactMsg.objects.get(pk=msgid)
        msgtext = msg.text.encode('utf-8')

        print(msg.text)
        cleartext = subprocess.check_output(
            ['openssl', 'enc', '-aes-256-cbc',
             '-pass', 'pass:%s' % passphrase,
             '-d', '-base64', '-A'],
            input=msgtext)
        cleartext = force_str(cleartext)
        print(cleartext)

        msg.text = cleartext
        msg.read_date = None
        msg.read_by = None
        msg.save()
