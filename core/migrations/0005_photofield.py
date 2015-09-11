# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def photo_field(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    ContactField = apps.get_model('ngw', 'ContactField')
    ContactField.objects.using(db_alias).bulk_create([
        ContactField(
            id=8,
            name='Photo',
            hint='',
            type='IMAGE',
            contact_group_id=1,
            sort_weight=5,
            choice_group_id=None,
            system=True),
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0004_imagecontactfield'),
    ]

    operations = [
        migrations.RunPython(
            photo_field,
        ),
    ]
