# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import F


def event_end_date(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    ContactGroup = apps.get_model('ngw', 'ContactGroup')
    (
        ContactGroup
        .objects.using(db_alias)
        .filter(date__isnull=False)
        .filter(end_date__isnull=True)
        .update(end_date=F('date'))
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0006_contactgroup_virtual'),
    ]

    operations = [
        migrations.RunPython(
            event_end_date,
        ),
    ]
