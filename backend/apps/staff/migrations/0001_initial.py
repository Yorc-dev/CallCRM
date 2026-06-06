import secrets
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('api_key', models.CharField(blank=True, max_length=64, unique=True, help_text='Ключ компании (генерируется автоматически)')),
                ('encryption_key', models.CharField(blank=True, max_length=64, unique=True, help_text='Ключ для шифрования данных')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Company', 'verbose_name_plural': 'Companies', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='RecordingCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(
                    max_length=50,
                    choices=[('work_moments', 'Рабочие моменты'), ('negotiations', 'Переговоры')],
                    unique=True,
                )),
            ],
            options={'verbose_name': 'Recording Category', 'verbose_name_plural': 'Recording Categories'},
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255)),
                ('email', models.EmailField(unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employees', to='staff.company')),
            ],
            options={'verbose_name': 'Employee', 'verbose_name_plural': 'Employees', 'ordering': ['full_name']},
        ),
        migrations.CreateModel(
            name='EmployeeGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('accesses', models.JSONField(blank=True, default=list, help_text='Список доступов из предопределённого набора')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='staff.employee')),
            ],
            options={'verbose_name': 'Employee Group', 'verbose_name_plural': 'Employee Groups', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='TranscriptionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('audio', models.FileField(upload_to='transcriptions/audio/')),
                ('text', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transcriptions', to='staff.employee')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transcriptions', to='staff.recordingcategory')),
            ],
            options={'verbose_name': 'Transcription Record', 'verbose_name_plural': 'Transcription Records', 'ordering': ['-created_at']},
        ),
    ]
