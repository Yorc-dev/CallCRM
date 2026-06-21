from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import (
    Company, EmployeeGroup, Employee,
    RecordingCategory, TranscriptionRecord, Analysis, Incident,
    ACCESS_CHOICES, ACCESS_KEYS,
)

User = get_user_model()


# --------------------------------------------------------------------------- #
#  Company
# --------------------------------------------------------------------------- #
class CompanySerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True, default=None)
    max_users = serializers.IntegerField(source='plan.max_users', read_only=True, default=None)
    user_count = serializers.IntegerField(source='employees.count', read_only=True)
    monthly_cost = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'api_key', 'encryption_key', 'plan', 'plan_name',
            'max_users', 'user_count', 'monthly_cost', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'api_key', 'encryption_key', 'created_at', 'updated_at']

    def get_monthly_cost(self, obj):
        if obj.plan_id and obj.plan:
            return obj.plan.cost_for(obj.employees.count())
        return None


# --------------------------------------------------------------------------- #
#  Employee group
# --------------------------------------------------------------------------- #
class EmployeeGroupSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    available_accesses = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(source='employees.count', read_only=True)

    class Meta:
        model = EmployeeGroup
        fields = [
            'id', 'company', 'company_name', 'name',
            'accesses', 'available_accesses', 'prompt_lists', 'employee_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_available_accesses(self, obj):
        return [{'value': k, 'label': v} for k, v in ACCESS_CHOICES]

    def validate_accesses(self, value):
        invalid = [a for a in value if a not in ACCESS_KEYS]
        if invalid:
            raise serializers.ValidationError(f'Недопустимые доступы: {invalid}')
        return value


# --------------------------------------------------------------------------- #
#  Employee
# --------------------------------------------------------------------------- #
class EmployeeSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)

    # Поля пользователя (только при записи)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False,
                                     help_text='Пароль. Обязателен при создании.')
    role = serializers.ChoiceField(
        choices=User.ROLE_CHOICES, write_only=True, required=False, default=User.ROLE_OPERATOR
    )

    # Информация о пользователе (только на чтение)
    username = serializers.CharField(source='user.username', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)

    certificate_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'company', 'company_name', 'group', 'group_name',
            'department', 'department_name',
            'full_name', 'email',
            'certificate', 'certificate_url', 'certificate_expires_at',
            # write-only
            'password', 'role',
            # read-only user info
            'username', 'user_id', 'user_role',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'company': {'required': False},
            'certificate': {'write_only': True, 'required': False},
        }

    def get_certificate_url(self, obj):
        request = self.context.get('request')
        if obj.certificate and request:
            return request.build_absolute_uri(obj.certificate.url)
        return None

    def _resolve_company(self, attrs):
        """Компания указывается явно при создании сотрудника."""
        company = attrs.get('company')
        if company is None:
            raise serializers.ValidationError(
                {'company': 'Поле company обязательно при создании сотрудника.'}
            )
        return company

    def validate(self, attrs):
        if not self.instance:
            if not attrs.get('password'):
                raise serializers.ValidationError({'password': 'Пароль обязателен при создании сотрудника.'})
            attrs['company'] = self._resolve_company(attrs)
            self._check_user_limit(attrs['company'])

        # Группа должна принадлежать той же компании
        group = attrs.get('group')
        company = attrs.get('company') or (self.instance and self.instance.company)
        if group and company and group.company_id != company.id:
            raise serializers.ValidationError({'group': 'Группа принадлежит другой компании.'})

        # Отдел должен принадлежать той же компании
        department = attrs.get('department')
        if department and company and department.company_id != company.id:
            raise serializers.ValidationError({'department': 'Отдел принадлежит другой компании.'})
        return attrs

    def _check_user_limit(self, company):
        """Лимит пользователей по тарифному пакету компании."""
        plan = getattr(company, 'plan', None)
        if plan and plan.max_users is not None:
            current = company.employees.count()
            if current >= plan.max_users:
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f'Достигнут лимит пакета «{plan.name}»: '
                        f'{plan.max_users} пользователей. Обновите тариф.'
                    ]
                })

    def create(self, validated_data):
        password = validated_data.pop('password')
        role = validated_data.pop('role', User.ROLE_OPERATOR)

        email = validated_data['email']
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
        )
        return Employee.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        role = validated_data.pop('role', None)

        if instance.user:
            if password:
                instance.user.set_password(password)
            if role:
                instance.user.role = role
            new_email = validated_data.get('email', instance.email)
            if new_email != instance.email:
                instance.user.email = new_email
            instance.user.save()

        return super().update(instance, validated_data)


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """Компактный профиль сотрудника для встраивания в представление пользователя."""
    company_id = serializers.IntegerField(source='company.id', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    group_id = serializers.IntegerField(source='group.id', read_only=True, default=None)
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    accesses = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'full_name', 'email',
            'company_id', 'company_name',
            'group_id', 'group_name', 'accesses',
            'certificate_url', 'certificate_expires_at',
        ]

    def get_accesses(self, obj):
        return obj.group.accesses if obj.group else []

    def get_certificate_url(self, obj):
        request = self.context.get('request')
        if obj.certificate and request:
            return request.build_absolute_uri(obj.certificate.url)
        return obj.certificate.url if obj.certificate else None


# --------------------------------------------------------------------------- #
#  Recording / Transcription / Analysis / Incident
# --------------------------------------------------------------------------- #
class RecordingCategorySerializer(serializers.ModelSerializer):
    title_display = serializers.CharField(source='get_title_display', read_only=True)

    class Meta:
        model = RecordingCategory
        fields = ['id', 'title', 'title_display']


class IncidentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='record.employee.full_name', read_only=True)
    company_name = serializers.CharField(source='record.employee.company.name', read_only=True)
    record_datetime = serializers.DateTimeField(source='record.record_datetime', read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'record', 'analysis', 'start_minutes', 'end_minutes',
            'description', 'severity',
            'employee_name', 'company_name', 'record_datetime', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        start = attrs.get('start_minutes', getattr(self.instance, 'start_minutes', None))
        end = attrs.get('end_minutes', getattr(self.instance, 'end_minutes', None))
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError({'end_minutes': 'Конец не может быть раньше начала.'})
        return attrs


class AnalysisSerializer(serializers.ModelSerializer):
    incidents = IncidentSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source='record.employee.full_name', read_only=True)
    company_name = serializers.CharField(source='record.employee.company.name', read_only=True)
    record_datetime = serializers.DateTimeField(source='record.record_datetime', read_only=True)

    class Meta:
        model = Analysis
        fields = [
            'id', 'record', 'description', 'incidents',
            'employee_name', 'company_name', 'record_datetime',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TranscriptionRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    category_title = serializers.CharField(source='category.get_title_display', read_only=True)
    audio_url = serializers.SerializerMethodField()
    analysis = AnalysisSerializer(read_only=True)

    class Meta:
        model = TranscriptionRecord
        fields = [
            'id', 'employee', 'employee_name', 'category', 'category_title',
            'audio', 'audio_url', 'record_datetime', 'session_id', 'is_original',
            'text', 'analysis', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'audio': {'write_only': True}}

    def get_audio_url(self, obj):
        request = self.context.get('request')
        if obj.audio and request:
            return request.build_absolute_uri(obj.audio.url)
        return None
