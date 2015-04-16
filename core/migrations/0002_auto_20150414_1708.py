# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactgroupnews',
            name='author',
            field=models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, blank=True, on_delete=django.db.models.deletion.SET_NULL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contactgroupnews',
            name='contact_group',
            field=models.ForeignKey(null=True, to='ngw.ContactGroup', blank=True, related_name='news_set', on_delete=django.db.models.deletion.SET_NULL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contactmsg',
            name='read_by',
            field=models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, related_name='msgreader', on_delete=django.db.models.deletion.SET_NULL),
            preserve_default=True,
        ),
    ]
