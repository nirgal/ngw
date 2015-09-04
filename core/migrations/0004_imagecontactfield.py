# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0003_filecontactfield'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.filecontactfield',),
        ),
    ]
