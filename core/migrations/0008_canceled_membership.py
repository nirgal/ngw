# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals

import os

from django.conf import settings
from django.db import migrations


def functions_sql():
    sqlfile=os.path.join(settings.BASE_DIR, 'core/migrations/functions.sql')
    with open(sqlfile) as f:
        return f.read()


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0007_event_end_date'),
    ]

    operations = [
        migrations.RunSQL(
            sql=functions_sql()
        ),
        migrations.RunSQL(
            sql = 'UPDATE contact_in_group SET flags = (flags & (~7))<<1|(flags&7)'
            ),
        migrations.RunSQL(
            sql = 'UPDATE group_manage_group SET flags = (flags & (~7))<<1|(flags&7)'
            ),
    ]
