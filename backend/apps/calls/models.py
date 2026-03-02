from django.conf import settings
from django.db import models


class Client(models.Model):
    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_UNKNOWN = 'unknown'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_UNKNOWN, 'Unknown'),
    ]

    LANGUAGE_RU = 'ru'
    LANGUAGE_KK = 'kk'
    LANGUAGE_CHOICES = [
        (LANGUAGE_RU, 'Russian'),
        (LANGUAGE_KK, 'Kazakh'),
    ]

    primary_phone = models.CharField(max_length=30)
    name = models.CharField(max_length=255, blank=True, default='')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default=GENDER_UNKNOWN)
    language_hint = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default=LANGUAGE_RU)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name or self.primary_phone}'


class Call(models.Model):
    STATUS_NEW = 'new'
    STATUS_UPLOADED = 'uploaded'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_UPLOADED, 'Uploaded'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='calls'
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='calls'
    )
    call_datetime = models.DateTimeField()
    duration_sec = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    category = models.CharField(max_length=100, null=True, blank=True)
    external_call_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    from_phone = models.CharField(max_length=30, null=True, blank=True)
    to_phone = models.CharField(max_length=30, null=True, blank=True)
    external_recording_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-call_datetime']

    def __str__(self):
        return f'Call {self.id} [{self.status}] by {self.operator}'


class CallRecording(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='recordings')
    file = models.FileField(upload_to='recordings/')
    mime_type = models.CharField(max_length=50, default='audio/mpeg')
    size_bytes = models.IntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Recording for Call {self.call_id}'


class CallAnalysis(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE, related_name='analysis')
    asr_language = models.CharField(max_length=10, default='ru')
    transcript_text = models.TextField(default='')
    summary_short = models.TextField(default='')
    summary_structured = models.JSONField(default=dict)
    client_draft = models.JSONField(default=dict)
    operator_coaching = models.JSONField(default=dict)
    script_compliance = models.JSONField(default=dict)
    script_score = models.FloatField(null=True, blank=True)
    model_info = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Analysis for Call {self.call_id}'


class ScriptTemplate(models.Model):
    LANGUAGE_RU = 'ru'
    LANGUAGE_KK = 'kk'
    LANGUAGE_CHOICES = [
        (LANGUAGE_RU, 'Russian'),
        (LANGUAGE_KK, 'Kazakh'),
    ]

    name = models.CharField(max_length=255)
    version = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default=LANGUAGE_RU)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} v{self.version} ({self.language})'


class ScriptStep(models.Model):
    STEP_KEYS = [
        ('greeting', 'Greeting'),
        ('name_ask', 'Name Ask'),
        ('confirmation', 'Confirmation'),
        ('need_identification', 'Need Identification'),
        ('solution_offer', 'Solution Offer'),
        ('deadline', 'Deadline'),
        ('closing', 'Closing'),
    ]

    template = models.ForeignKey(ScriptTemplate, on_delete=models.CASCADE, related_name='steps')
    order = models.IntegerField(default=0)
    key = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, default='')
    keywords = models.JSONField(default=list)
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.template.name} - Step {self.order}: {self.key}'


class ExternalIdentity(models.Model):
    ENTITY_CLIENT = 'client'
    ENTITY_OPERATOR = 'operator'
    ENTITY_CALL = 'call'
    ENTITY_CHOICES = [
        (ENTITY_CLIENT, 'Client'),
        (ENTITY_OPERATOR, 'Operator'),
        (ENTITY_CALL, 'Call'),
    ]

    provider = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES)
    external_id = models.CharField(max_length=255)
    internal_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('provider', 'entity_type', 'external_id')]

    def __str__(self):
        return f'{self.provider}:{self.entity_type}:{self.external_id} -> {self.internal_id}'
