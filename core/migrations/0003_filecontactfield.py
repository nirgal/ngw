# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0002_auto_20150414_1708'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
    ]
