# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals

import os

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0007_event_end_date'),
    ]

    operations = [
        migrations.RunSQL(
            sql=open(os.path.join(settings.BASE_DIR, 'core/migrations/functions.sql')).read()
        ),
        migrations.RunSQL(
            sql = 'UPDATE contact_in_group SET flags = (flags & (~7))<<1|(flags&7)'
            ),
        migrations.RunSQL(
            sql = 'UPDATE group_manage_group SET flags = (flags & (~7))<<1|(flags&7)'
            ),
    ]
