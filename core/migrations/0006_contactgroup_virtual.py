# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0005_photofield'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactgroup',
            name='virtual',
            field=models.BooleanField(verbose_name='Virtual', default=False, help_text="Doesn't have any direct members."),
            preserve_default=True,
        ),
    ]
