from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import (
    CompanySettings, Company, Employee, EmployeeGroup,
    RecordingCategory, TranscriptionRecord, Analysis, Incident, ACCESS_CHOICES,
)
from .serializers import (
    CompanySettingsSerializer, CompanySerializer, EmployeeSerializer,
    EmployeeGroupSerializer, RecordingCategorySerializer,
    TranscriptionRecordSerializer, AnalysisSerializer, IncidentSerializer,
)
from apps.calls.permissions import IsChiefOrAdmin


def user_company_id(user):
    """ID компании пользователя через его профиль сотрудника (или None)."""
    emp = getattr(user, 'employee_profile', None)
    return emp.company_id if emp else None


def is_global_admin(user):
    """Админ видит все компании; суперюзер — тоже."""
    return getattr(user, 'is_superuser', False) or getattr(user, 'role', None) == 'admin'


class CompanyScopedMixin:
    """Ограничивает queryset компанией пользователя. Админ видит всё.

    Подклассы задают `company_lookup` — путь к company_id в модели.
    """
    company_lookup = 'company_id'

    def scope(self, qs):
        user = self.request.user
        if is_global_admin(user):
            return qs
        cid = user_company_id(user)
        if cid is None:
            return qs.none()
        return qs.filter(**{self.company_lookup: cid})


class CompanySettingsViewSet(mixins.RetrieveModelMixin,
                             mixins.UpdateModelMixin,
                             mixins.ListModelMixin,
                             viewsets.GenericViewSet):
    """Singleton-настройки: режим одна/несколько компаний."""
    serializer_class = CompanySettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]

    def get_queryset(self):
        return CompanySettings.objects.all()

    def get_object(self):
        return CompanySettings.get()

    def list(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)


class CompanyViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]
    company_lookup = 'id'

    def get_queryset(self):
        return self.scope(Company.objects.all())

    @action(detail=True, methods=['post'], url_path='regenerate-keys')
    def regenerate_keys(self, request, pk=None):
        import secrets
        company = self.get_object()
        company.api_key = secrets.token_hex(32)
        company.encryption_key = secrets.token_hex(32)
        company.save(update_fields=['api_key', 'encryption_key'])
        return Response(CompanySerializer(company).data)


class EmployeeViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def get_queryset(self):
        qs = self.scope(Employee.objects.select_related('company', 'group', 'user').all())
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search))
        return qs


class EmployeeGroupViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = EmployeeGroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = self.scope(EmployeeGroup.objects.select_related('company').all())
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs

    @action(detail=False, methods=['get'], url_path='available-accesses')
    def available_accesses(self, request):
        return Response([{'value': k, 'label': v} for k, v in ACCESS_CHOICES])


class RecordingCategoryViewSet(viewsets.ModelViewSet):
    queryset = RecordingCategory.objects.all()
    serializer_class = RecordingCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class TranscriptionRecordViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = TranscriptionRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    company_lookup = 'employee__company_id'

    def get_queryset(self):
        qs = self.scope(TranscriptionRecord.objects
                        .select_related('employee', 'category', 'analysis')
                        .all())
        employee_id = self.request.query_params.get('employee')
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        category_id = self.request.query_params.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class AnalysisViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = AnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]
    company_lookup = 'record__employee__company_id'

    def get_queryset(self):
        qs = self.scope(Analysis.objects
                        .select_related('record__employee')
                        .prefetch_related('incidents').all())
        record_id = self.request.query_params.get('record')
        if record_id:
            qs = qs.filter(record_id=record_id)
        return qs


class IncidentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = IncidentSerializer
    permission_classes = [permissions.IsAuthenticated]
    company_lookup = 'record__employee__company_id'

    def get_queryset(self):
        qs = self.scope(Incident.objects
                        .select_related('record__employee', 'analysis').all())
        record_id = self.request.query_params.get('record')
        if record_id:
            qs = qs.filter(record_id=record_id)
        analysis_id = self.request.query_params.get('analysis')
        if analysis_id:
            qs = qs.filter(analysis_id=analysis_id)
        return qs
