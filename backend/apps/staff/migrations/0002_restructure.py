import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staff', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. CompanySettings singleton
        migrations.CreateModel(
            name='CompanySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(
                    choices=[('single', 'Одна компания'), ('multiple', 'Несколько компаний')],
                    default='single', max_length=10,
                )),
            ],
            options={'verbose_name': 'Company Settings', 'verbose_name_plural': 'Company Settings'},
        ),

        # 2. EmployeeGroup: remove employee FK, add company FK
        migrations.RemoveField(model_name='employeegroup', name='employee'),
        migrations.AddField(
            model_name='employeegroup',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='groups',
                to='staff.company',
                null=True,
            ),
        ),
        # Make company non-nullable after data settled (new groups always have company)
        migrations.AlterField(
            model_name='employeegroup',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='groups',
                to='staff.company',
            ),
        ),
        # 3. Employee: add user, group, certificate, certificate_expires_at
        migrations.AddField(
            model_name='employee',
            name='user',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='employee_profile',
                to=settings.AUTH_USER_MODEL,
                help_text='Связанный пользователь системы',
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='group',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='employees',
                to='staff.employeegroup',
                help_text='Группа сотрудника',
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='certificate',
            field=models.FileField(
                blank=True, null=True,
                upload_to='certificates/',
                help_text='Файл сертификата',
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='certificate_expires_at',
            field=models.DateField(
                blank=True, null=True,
                help_text='Дата окончания действия сертификата/подписки',
            ),
        ),

        # 4. TranscriptionRecord: add record_datetime
        migrations.AddField(
            model_name='transcriptionrecord',
            name='record_datetime',
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text='Дата и время записи',
            ),
            preserve_default=False,
        ),

        # 5. Analysis model
        migrations.CreateModel(
            name='Analysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('record', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='analysis',
                    to='staff.transcriptionrecord',
                )),
            ],
            options={'verbose_name': 'Analysis', 'verbose_name_plural': 'Analyses', 'ordering': ['-created_at']},
        ),

        # 6. Incident model
        migrations.CreateModel(
            name='Incident',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_minutes', models.FloatField(help_text='Начало инцидента (минуты)')),
                ('end_minutes', models.FloatField(help_text='Конец инцидента (минуты)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('record', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='incidents',
                    to='staff.transcriptionrecord',
                )),
                ('analysis', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='incidents',
                    to='staff.analysis',
                )),
            ],
            options={'verbose_name': 'Incident', 'verbose_name_plural': 'Incidents', 'ordering': ['record', 'start_minutes']},
        ),
    ]
