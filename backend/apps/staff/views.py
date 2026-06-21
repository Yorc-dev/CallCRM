from rest_framework import viewsets, permissions, mixins, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import (
    Company, Employee, EmployeeGroup,
    RecordingCategory, TranscriptionRecord, Analysis, Incident, ACCESS_CHOICES,
)
from .serializers import (
    CompanySerializer, EmployeeSerializer,
    EmployeeGroupSerializer, RecordingCategorySerializer,
    TranscriptionRecordSerializer, AnalysisSerializer, IncidentSerializer,
)
from apps.calls.permissions import IsChiefOrAdmin


def resolve_company_employee(company_key: str, email: str, password: str = None):
    """Привязка устройства: ключ компании + сотрудник.

    Возвращает (company, employee, error_str). Если password задан — проверяет его.
    """
    company_key = (company_key or '').strip()
    email = (email or '').strip()
    company = Company.objects.filter(api_key=company_key).first()
    if not company:
        import logging
        logging.getLogger('django').warning(
            'device-bind: ключ не найден, получено %r (len=%d)', company_key, len(company_key)
        )
        return None, None, 'Неверный ключ компании'
    employee = Employee.objects.select_related('user').filter(
        company=company, email__iexact=email
    ).first()
    if not employee:
        return company, None, 'Сотрудник с таким email не найден в компании'
    if password is not None:
        if not employee.user or not employee.user.check_password(password):
            return company, None, 'Неверный пароль'
    return company, employee, None


class DeviceBindView(APIView):
    """Привязка десктоп-устройства к компании+сотруднику по ключу компании.

    Десктоп шлёт ключ компании + email + пароль сотрудника. Без JWT.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        company_key = request.data.get('company_key', '')
        email = request.data.get('email', '')
        password = request.data.get('password', '')
        company, employee, err = resolve_company_employee(company_key, email, password)
        if err:
            return Response({'ok': False, 'detail': err}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({
            'ok': True,
            'company_id': company.id,
            'company_name': company.name,
            'employee_id': employee.id,
            'employee_name': employee.full_name,
        })


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
        # Фильтр по диапазону даты/времени (для ленты): from / to (ISO)
        dt_from = self.request.query_params.get('from')
        dt_to = self.request.query_params.get('to')
        from django.utils.dateparse import parse_datetime, parse_date
        if dt_from:
            v = parse_datetime(dt_from) or parse_date(dt_from)
            if v:
                qs = qs.filter(record_datetime__gte=v)
        if dt_to:
            v = parse_datetime(dt_to) or parse_date(dt_to)
            if v:
                qs = qs.filter(record_datetime__lte=v)
        # Лента — по возрастанию времени, если запрошено
        if self.request.query_params.get('order') == 'asc':
            qs = qs.order_by('record_datetime')
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
        # Фильтр по сотруднику
        employee_id = self.request.query_params.get('employee')
        if employee_id:
            qs = qs.filter(record__employee_id=employee_id)
        # Фильтр по диапазону даты/времени записи
        from django.utils.dateparse import parse_datetime, parse_date
        dt_from = self.request.query_params.get('from')
        dt_to = self.request.query_params.get('to')
        if dt_from:
            v = parse_datetime(dt_from) or parse_date(dt_from)
            if v:
                qs = qs.filter(record__record_datetime__gte=v)
        if dt_to:
            v = parse_datetime(dt_to) or parse_date(dt_to)
            if v:
                qs = qs.filter(record__record_datetime__lte=v)
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
