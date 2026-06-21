import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


class Company(models.Model):
    """Компания — владелец пространства данных."""
    name = models.CharField(max_length=255)
    api_key = models.CharField(
        max_length=64, unique=True, blank=True,
        help_text='Ключ компании (генерируется автоматически)'
    )
    encryption_key = models.CharField(
        max_length=64, unique=True, blank=True,
        help_text='Ключ для шифрования данных'
    )
    plan = models.ForeignKey(
        'billing.Plan', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='companies',
        help_text='Тарифный пакет компании'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        if not self.encryption_key:
            self.encryption_key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


ACCESS_CHOICES = [
    ('view_calls', 'Просмотр звонков'),
    ('upload_calls', 'Загрузка звонков'),
    ('analyze_calls', 'Анализ звонков'),
    ('view_clients', 'Просмотр клиентов'),
    ('manage_clients', 'Управление клиентами'),
    ('view_analytics', 'Просмотр аналитики'),
    ('manage_staff', 'Управление сотрудниками'),
    ('manage_company', 'Управление компанией'),
]

ACCESS_KEYS = [key for key, _ in ACCESS_CHOICES]


class EmployeeGroup(models.Model):
    """Группа сотрудников с набором доступов, принадлежащая компании."""
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='groups'
    )
    name = models.CharField(max_length=255)
    accesses = models.JSONField(
        default=list, blank=True,
        help_text='Список доступов: view_calls, upload_calls, analyze_calls, ...'
    )
    prompt_lists = models.ManyToManyField(
        'analysis.PromptList', blank=True, related_name='groups',
        help_text='Списки промптов, назначенные группе.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Employee Group'
        verbose_name_plural = 'Employee Groups'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class Employee(models.Model):
    """Сотрудник компании."""
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='employees'
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employee_profile',
        help_text='Связанный пользователь системы'
    )
    group = models.ForeignKey(
        EmployeeGroup,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees',
        help_text='Группа сотрудника'
    )
    department = models.ForeignKey(
        'analysis.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees',
        help_text='Отдел сотрудника (для динамических промптов)'
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    certificate = models.FileField(
        upload_to='certificates/',
        null=True, blank=True,
        help_text='Файл сертификата'
    )
    certificate_expires_at = models.DateField(
        null=True, blank=True,
        help_text='Дата окончания действия сертификата/подписки'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.company.name})'

    @classmethod
    def create_with_user(cls, full_name: str, email: str, company: Company,
                         password: str | None = None, group: EmployeeGroup | None = None,
                         **kwargs):
        """Создать сотрудника и автоматически создать для него пользователя."""
        User = get_user_model()
        username = email.split('@')[0]
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{counter}'
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password or secrets.token_urlsafe(12),
        )
        return cls.objects.create(
            full_name=full_name,
            email=email,
            company=company,
            user=user,
            group=group,
            **kwargs,
        )


class RecordingCategory(models.Model):
    """Категория записи транскрибации."""
    CATEGORY_WORK = 'work_moments'
    CATEGORY_NEGOTIATIONS = 'negotiations'
    CATEGORY_CHOICES = [
        (CATEGORY_WORK, 'Рабочие моменты'),
        (CATEGORY_NEGOTIATIONS, 'Переговоры'),
    ]

    title = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        unique=True,
    )

    class Meta:
        verbose_name = 'Recording Category'
        verbose_name_plural = 'Recording Categories'

    def __str__(self):
        return self.get_title_display()


class TranscriptionRecord(models.Model):
    """Запись: аудио + текст + сотрудник + категория + дата."""
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='transcriptions'
    )
    category = models.ForeignKey(
        RecordingCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transcriptions'
    )
    audio = models.FileField(upload_to='transcriptions/audio/')
    record_datetime = models.DateTimeField(
        help_text='Дата и время записи'
    )
    session_id = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        help_text='ID сессии записи — связывает сегменты с цельным оригиналом.'
    )
    is_original = models.BooleanField(
        default=False,
        help_text='Сплошной оригинал сессии (от-до), без транскрибации.'
    )
    text = models.TextField(blank=True, default='')
    transcript_segments = models.JSONField(
        default=list, blank=True,
        help_text='Сегменты с таймингами: [{start,end,speaker,text}]'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transcription Record'
        verbose_name_plural = 'Transcription Records'
        ordering = ['-record_datetime']

    def __str__(self):
        return f'Запись #{self.id} — {self.employee.full_name}'


class Analysis(models.Model):
    """Анализ записи."""
    record = models.OneToOneField(
        TranscriptionRecord, on_delete=models.CASCADE, related_name='analysis'
    )
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Analysis'
        verbose_name_plural = 'Analyses'
        ordering = ['-created_at']

    def __str__(self):
        return f'Анализ #{self.id} к записи #{self.record_id}'


class Incident(models.Model):
    """Инцидент в записи: временной отрезок + анализ."""
    record = models.ForeignKey(
        TranscriptionRecord, on_delete=models.CASCADE, related_name='incidents'
    )
    analysis = models.ForeignKey(
        Analysis, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='incidents'
    )
    start_minutes = models.FloatField(help_text='Начало инцидента (минуты)')
    end_minutes = models.FloatField(help_text='Конец инцидента (минуты)')
    description = models.TextField(blank=True, default='', help_text='Описание инцидента')
    severity = models.CharField(
        max_length=20, blank=True, default='',
        help_text='Важность: low/medium/high'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Incident'
        verbose_name_plural = 'Incidents'
        ordering = ['record', 'start_minutes']

    def __str__(self):
        return f'Инцидент #{self.id} [{self.start_minutes}–{self.end_minutes} мин] в записи #{self.record_id}'
