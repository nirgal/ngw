# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2019-01-31 13:28
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0010_auto_drop_proxy_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChoiceContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='DateContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='DateTimeContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='EmailContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='FileContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='LongTextContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='MultipleChoiceContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='MultipleDoubleChoiceContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='NumberContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='PasswordContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='PhoneContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='RibContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
        migrations.CreateModel(
            name='TextContactField',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('ngw.contactfield',),
        ),
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
