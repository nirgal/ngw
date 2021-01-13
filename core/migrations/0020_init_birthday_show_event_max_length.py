from django.db import migrations


def initial_data(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    Config = apps.get_model('ngw', 'Config')
    Config.objects.using(db_alias).bulk_create([
        Config(id='birthday_show_event_max_length', text='7'),
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('ngw', '0019_auto_20201119_1549'),
    ]

    operations = [
        migrations.RunPython(
            initial_data,
        ),
    ]
