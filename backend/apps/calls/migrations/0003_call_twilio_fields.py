from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0002_callanalysis_script_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='external_call_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='call',
            name='from_phone',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='call',
            name='to_phone',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='call',
            name='external_recording_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]
