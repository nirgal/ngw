# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def config_eventdefaultperms(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Config = apps.get_model('ngw', 'Config')
    Config.objects.using(db_alias).bulk_create([
        Config(
            id='event_default_perms',
            text='{}',
            ),
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0008_canceled_membership'),
    ]

    operations = [
        migrations.RunPython(
            config_eventdefaultperms,
        ),
    ]
