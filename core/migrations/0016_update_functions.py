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
        ('ngw', '0015_contactgroup_busy'),
    ]

    operations = [
        migrations.RunSQL(
            sql=functions_sql()
        ),
    ]
