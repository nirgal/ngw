# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0009_config_eventdefaultperms'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ChoiceContactField',
        ),
        migrations.DeleteModel(
            name='DateContactField',
        ),
        migrations.DeleteModel(
            name='DateTimeContactField',
        ),
        migrations.DeleteModel(
            name='EmailContactField',
        ),
        migrations.DeleteModel(
            name='FileContactField',
        ),
        migrations.DeleteModel(
            name='ImageContactField',
        ),
        migrations.DeleteModel(
            name='LongTextContactField',
        ),
        migrations.DeleteModel(
            name='MultipleChoiceContactField',
        ),
        migrations.DeleteModel(
            name='MultipleDoubleChoiceContactField',
        ),
        migrations.DeleteModel(
            name='NumberContactField',
        ),
        migrations.DeleteModel(
            name='PasswordContactField',
        ),
        migrations.DeleteModel(
            name='PhoneContactField',
        ),
        migrations.DeleteModel(
            name='RibContactField',
        ),
        migrations.DeleteModel(
            name='TextContactField',
        ),
    ]
