# -*- coding: utf-8 -*-
# flake8: noqa

from __future__ import unicode_literals

import os

from django.conf import settings
from django.db import migrations, models


def initial_data(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    Config = apps.get_model('ngw', 'Config')
    Config.objects.using(db_alias).bulk_create([
        Config(id='columns', text='name,field_7,field_8,field_10'),
        Config(id='banner', text='<big>NGW</big> Group Ware'),
        Config(id='phpbb acl dictionary', text=''),
        Config(id='query_page_length', text='100'),
        Config(id='db version', text='25'),
    ])

    ChoiceGroup = apps.get_model('ngw', 'ChoiceGroup')
    countries = ChoiceGroup(id=1, sort_by_key=False)
    passstatus = ChoiceGroup(id=41, sort_by_key=True)
    ChoiceGroup.objects.using(db_alias).bulk_create([
        countries,
        passstatus,
    ])

    Choice = apps.get_model('ngw', 'Choice')
    Choice.objects.using(db_alias).bulk_create([
        Choice(choice_group_id=countries.id,
               key='fr', value='France'),
        Choice(choice_group_id=countries.id,
               key='uk', value='United Kingdom'),
        Choice(choice_group_id=countries.id,
               key='ch', value='Switzerland'),
        Choice(choice_group_id=countries.id,
               key='it', value='Italy'),

        Choice(choice_group_id=passstatus.id,
               key='1', value='Generated'),
        Choice(choice_group_id=passstatus.id,
               key='2', value='User defined'),
        Choice(choice_group_id=passstatus.id,
               key='3', value='Generated and mailed'),
    ])

    ContactGroup = apps.get_model('ngw', 'ContactGroup')
    ContactGroup.objects.using(db_alias).bulk_create([
        ContactGroup(
            id=1,
            name='Contacts',
            description='Ensemble des contacts',
            field_group=True,
            date=None,
            end_date=None,
            budget_code='',
            system=True,
            mailman_address='',
            sticky=False),
        ContactGroup(
            id=2,
            name='Utilisateurs',
            description='Ensemble des personnes qui ont un identifiant et un'
                        'mot de passe.\r\nVoir aussi "Utilisateurs NGW" et '
                        '"Utilisateurs Forum".',
            field_group=True,
            date=None,
            end_date=None,
            budget_code='',
            system=True,
            mailman_address='',
            sticky=False),
        ContactGroup(
            id=8,
            name='Admins',
            description="Ils peuvent ajouter des contacts dans n'importe quel"
                        " groupe, et tout voir.",
            field_group=True,
            date=None,
            end_date=None,
            budget_code='',
            system=True,
            mailman_address='',
            sticky=False),
        ContactGroup(
            id=9,
            name='Observateurs',
            description="Ils peuvent tout voir, mais n'ont pas accès en"
                        " écriture sur les groupes.",
            field_group=True,
            date=None,
            end_date=None,
            budget_code='',
            system=True,
            mailman_address='',
            sticky=False),
        ContactGroup(
            id=52,
            name='NGW Users',
            description='People in that group can connect to NGW interface.',
            field_group=True,
            date=None,
            end_date=None,
            budget_code='',
            system=True,
            mailman_address='',
            sticky=False),
        ContactGroup(
            id=53,
            name='Utilisateurs',
            description='Les personnes de ce groupe peuvent se connecter au '
                        ' forum (non disponible).',
            field_group=True,
            date=None,
            end_date=None,
            budget_code='',
            system=True,
            mailman_address='',
            sticky=False),
        ])

    ContactField = apps.get_model('ngw', 'ContactField')
    ContactField.objects.using(db_alias).bulk_create([
        ContactField(
            id=1,
            name='Login',
            hint='Nom avec lequel vous vous connectez au système',
            type='TEXT',
            contact_group_id=2,
            sort_weight=390,
            choice_group_id=None,
            system=True,
            default=''),
        ContactField(
            id=2,
            name='Mot de passe',
            hint='Ne pas modifier. Utiliser le bouton "Change password" après'
                 " avoir cliqué sur votre nom en haut à droite.",
            type='PASSWORD',
            contact_group_id=2,
            sort_weight=400,
            choice_group_id=None,
            system=True,
            default=''),
        ContactField(
            id=3,
            name='Dernière connexion',
            hint="Ce champ est mis à jour automatiquement",
            type='DATETIME',
            contact_group_id=2,
            sort_weight=440,
            choice_group_id=None,
            system=True),
        ContactField(
            id=4,
            name='Colonnes',
            hint='Ce champ est mis à jour automatiquement',
            type='TEXT',
            contact_group_id=52,
            sort_weight=450,
            choice_group_id=None,
            system=True),
        ContactField(
            id=5,
            name='Filtres personnels',
            hint='Ce champ est mis à jour automatiquement',
            type='TEXT',
            contact_group_id=52,
            sort_weight=460,
            choice_group_id=None,
            system=True),
        ContactField(
            id=7,
            name='Courriel',
            hint='',
            type='EMAIL',
            contact_group_id=1,
            sort_weight=10,
            choice_group_id=None,
            system=True),
        ContactField(
            id=9,
            name='Rue',
            hint='',
            type='LONGTEXT',
            contact_group_id=1,
            sort_weight=110,
            choice_group_id=None,
            system=True),
        ContactField(
            id=10,
            name='Tél.fixe',
            hint='',
            type='PHONE',
            contact_group_id=1,
            sort_weight=30,
            choice_group_id=None,
            system=True),
        ContactField(
            id=11,
            name='Code postal',
            hint='',
            type='TEXT',
            contact_group_id=1,
            sort_weight=120,
            choice_group_id=None,
            system=True),
        ContactField(
            id=14,
            name='Ville',
            hint='',
            type='TEXT',
            contact_group_id=1,
            sort_weight=140,
            choice_group_id=None,
            system=True),
        ContactField(
            id=48,
            name='Pays',
            hint='',
            type='CHOICE',
            contact_group_id=1,
            sort_weight=140,
            choice_group_id=1,
            system=True),
        ContactField(
            id=75,
            name='Status du mot de passe',
            hint='Mis à jour automatiquement',
            type='CHOICE',
            contact_group_id=52,
            sort_weight=420,
            choice_group_id=41,
            system=True),
        ContactField(
            id=83,
            name='Groupe par défaut',
            hint="Identifiant du groupe qui obtient automatiquement les"
                 " privilèges d'opérateur quand cet utilisateur crée un"
                 " groupe.",
            type='TEXT',
            contact_group_id=52,
            sort_weight=430,
            choice_group_id=None,
            system=True),
        ])

    GroupInGroup = apps.get_model('ngw', 'GroupInGroup')
    GroupInGroup.objects.using(db_alias).bulk_create([
        GroupInGroup(father_id=1, subgroup_id=2),
        GroupInGroup(father_id=2, subgroup_id=53),
        GroupInGroup(father_id=2, subgroup_id=52),
        GroupInGroup(father_id=52, subgroup_id=8),
        GroupInGroup(father_id=52, subgroup_id=9),
        ])


def functions_sql():
    sqlfile=os.path.join(settings.BASE_DIR, 'core/migrations/functions.sql')
    with open(sqlfile) as f:
        return f.read()


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(unique=True, verbose_name='Name', max_length=255)),
            ],
            options={
                'verbose_name_plural': 'contacts',
                'verbose_name': 'contact',
                'db_table': 'contact',
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('django_id', models.AutoField(serialize=False, primary_key=True)),
                ('key', models.CharField(verbose_name='Key', max_length=255)),
                ('value', models.CharField(verbose_name='Value', max_length=255)),
            ],
            options={
                'verbose_name_plural': 'choices',
                'verbose_name': 'choice',
                'db_table': 'choice',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ChoiceGroup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('sort_by_key', models.BooleanField(default=False, verbose_name='Sort by key')),
            ],
            options={
                'verbose_name_plural': 'choices lists',
                'verbose_name': 'choices list',
                'db_table': 'choice_group',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Config',
            fields=[
                ('id', models.CharField(serialize=False, primary_key=True, max_length=32)),
                ('text', models.TextField(blank=True)),
            ],
            options={
                'verbose_name_plural': 'configs',
                'verbose_name': 'config',
                'db_table': 'config',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContactField',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(verbose_name='Name', max_length=255)),
                ('hint', models.TextField(blank=True, verbose_name='Hint')),
                ('type', models.CharField(default='TEXT', verbose_name='Type', max_length=15)),
                ('sort_weight', models.IntegerField()),
                ('system', models.BooleanField(default=False, verbose_name='System locked')),
                ('default', models.TextField(blank=True, verbose_name='Default value')),
                ('choice_group', models.ForeignKey(to='ngw.ChoiceGroup', null=True, verbose_name='Choice group', blank=True, on_delete=models.CASCADE)),
                ('choice_group2', models.ForeignKey(to='ngw.ChoiceGroup', null=True, verbose_name='Second choice group', related_name='second_choices_set', blank=True, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'contact fields',
                'verbose_name': 'contact field',
                'db_table': 'contact_field',
                'ordering': ('sort_weight',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContactFieldValue',
            fields=[
                ('django_id', models.AutoField(serialize=False, primary_key=True)),
                ('value', models.TextField(blank=True)),
                ('contact', models.ForeignKey(related_name='values', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
                ('contact_field', models.ForeignKey(related_name='values', to='ngw.ContactField', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'contact field values',
                'verbose_name': 'contact field value',
                'db_table': 'contact_field_value',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContactGroup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(verbose_name='Name', max_length=255)),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('field_group', models.BooleanField(default=False, verbose_name='Field group', help_text='Does that group yield specific fields to its members?')),
                ('date', models.DateField(blank=True, verbose_name='Date', null=True)),
                ('end_date', models.DateField(null=True, blank=True, verbose_name='End date', help_text='Included. Last day.')),
                ('budget_code', models.CharField(blank=True, verbose_name='Budget code', max_length=10)),
                ('system', models.BooleanField(default=False, verbose_name='System locked')),
                ('mailman_address', models.CharField(help_text='Mailing list address, if the group is linked to a mailing list.', blank=True, verbose_name='Mailman address', max_length=255)),
                ('sticky', models.BooleanField(default=False, verbose_name='Sticky', help_text='If set, automatic membership because of subgroups becomes permanent. Use with caution.')),
            ],
            options={
                'verbose_name_plural': 'contact groups',
                'verbose_name': 'contact group',
                'db_table': 'contact_group',
                'ordering': ('-date', 'name'),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContactGroupNews',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('date', models.DateTimeField()),
                ('title', models.CharField(verbose_name='title', max_length=64)),
                ('text', models.TextField(verbose_name='text')),
                ('author', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)),
                ('contact_group', models.ForeignKey(to='ngw.ContactGroup', null=True, related_name='news_set', blank=True, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'news',
                'verbose_name': 'news item',
                'db_table': 'contact_group_news',
                'ordering': ('-date',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContactInGroup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('flags', models.IntegerField()),
                ('note', models.TextField(blank=True)),
                ('contact', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
                ('group', models.ForeignKey(to='ngw.ContactGroup', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'contacts in group',
                'verbose_name': 'contact in group',
                'db_table': 'contact_in_group',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ContactMsg',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('send_date', models.DateTimeField()),
                ('read_date', models.DateTimeField(null=True, blank=True)),
                ('is_answer', models.BooleanField(default=False)),
                ('subject', models.CharField(default='No title', verbose_name='Subject', max_length=64)),
                ('text', models.TextField()),
                ('sync_info', models.TextField(blank=True)),
                ('contact', models.ForeignKey(to=settings.AUTH_USER_MODEL, verbose_name='Contact', on_delete=models.CASCADE)),
                ('group', models.ForeignKey(related_name='message_set', to='ngw.ContactGroup', on_delete=models.CASCADE)),
                ('read_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='msgreader', null=True, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'messages',
                'verbose_name': 'message',
                'db_table': 'contact_message',
                'ordering': ('-send_date',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupInGroup',
            fields=[
                ('django_id', models.AutoField(serialize=False, primary_key=True)),
                ('father', models.ForeignKey(related_name='direct_gig_subgroups', to='ngw.ContactGroup', on_delete=models.CASCADE)),
                ('subgroup', models.ForeignKey(related_name='direct_gig_supergroups', to='ngw.ContactGroup', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'groups in group',
                'verbose_name': 'group in group',
                'db_table': 'group_in_group',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupManageGroup',
            fields=[
                ('django_id', models.AutoField(serialize=False, primary_key=True)),
                ('flags', models.IntegerField()),
                ('father', models.ForeignKey(related_name='direct_gmg_subgroups', to='ngw.ContactGroup', on_delete=models.CASCADE)),
                ('subgroup', models.ForeignKey(related_name='direct_gmg_supergroups', to='ngw.ContactGroup', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'groups managing group',
                'verbose_name': 'group managing group',
                'db_table': 'group_manage_group',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('dt', models.DateTimeField(auto_now=True, verbose_name='Date UTC')),
                ('action', models.IntegerField(verbose_name='Action')),
                ('target', models.TextField()),
                ('target_repr', models.TextField(verbose_name='Target')),
                ('property', models.TextField(null=True, blank=True)),
                ('property_repr', models.TextField(blank=True, verbose_name='Property', null=True)),
                ('change', models.TextField(blank=True, verbose_name='Change', null=True)),
                ('contact', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'logs',
                'verbose_name': 'log',
                'db_table': 'log',
                'ordering': ('-dt',),
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='groupmanagegroup',
            unique_together=set([('father', 'subgroup')]),
        ),
        migrations.AlterIndexTogether(
            name='groupmanagegroup',
            index_together=set([('father', 'subgroup')]),
        ),
        migrations.AlterUniqueTogether(
            name='groupingroup',
            unique_together=set([('father', 'subgroup')]),
        ),
        migrations.AlterIndexTogether(
            name='groupingroup',
            index_together=set([('father', 'subgroup')]),
        ),
        migrations.AlterUniqueTogether(
            name='contactfieldvalue',
            unique_together=set([('contact', 'contact_field')]),
        ),
        migrations.AlterIndexTogether(
            name='contactfieldvalue',
            index_together=set([('contact', 'contact_field')]),
        ),
        migrations.AddField(
            model_name='contactfield',
            name='contact_group',
            field=models.ForeignKey(to='ngw.ContactGroup', verbose_name='Only for', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='choice',
            name='choice_group',
            field=models.ForeignKey(related_name='choices', to='ngw.ChoiceGroup', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='choice',
            unique_together=set([('choice_group', 'key')]),
        ),
        migrations.AlterIndexTogether(
            name='choice',
            index_together=set([('choice_group', 'key')]),
        ),
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

        migrations.RunSQL(
            sql=functions_sql()
        ),

        migrations.RunPython(
            initial_data,
        ),

        migrations.RunSQL(sql='''
            SELECT pg_catalog.setval('choice_group_id_seq', 100, true);
            SELECT pg_catalog.setval('contact_group_id_seq', 100, true);
            SELECT pg_catalog.setval('contact_field_id_seq', 100, true);
            '''),
    ]
