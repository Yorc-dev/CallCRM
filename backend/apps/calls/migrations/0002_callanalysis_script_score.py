from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='callanalysis',
            name='script_score',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
