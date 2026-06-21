from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import Department, CompanyAnalysisSettings, AnalysisCriterion, PromptList
from .serializers import (
    DepartmentSerializer, CompanyAnalysisSettingsSerializer, AnalysisCriterionSerializer,
    PromptListSerializer,
)
from apps.staff.views import CompanyScopedMixin


class DepartmentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = self.scope(Department.objects.select_related('company').all())
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs


class CompanyAnalysisSettingsViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = CompanyAnalysisSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope(CompanyAnalysisSettings.objects.select_related('company').all())


class PromptListViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = PromptListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope(PromptList.objects.select_related('company').all())


class AnalysisCriterionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = AnalysisCriterionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = self.scope(AnalysisCriterion.objects
                        .select_related('company', 'department', 'group', 'prompt_list').all())
        department_id = self.request.query_params.get('department')
        if department_id:
            qs = qs.filter(department_id=department_id)
        prompt_list_id = self.request.query_params.get('prompt_list')
        if prompt_list_id:
            qs = qs.filter(prompt_list_id=prompt_list_id)
        return qs


class IngestAudioView(APIView):
    """M2M-приём аудио от ingest-сервиса. Создаёт запись и ставит транскрибацию.

    Аутентификация — shared-token в заголовке X-Ingest-Token (без JWT).
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        token = request.headers.get('X-Ingest-Token', '')
        if not token or token != getattr(settings, 'INGEST_TOKEN', None):
            return Response({'detail': 'Invalid ingest token'}, status=status.HTTP_401_UNAUTHORIZED)

        audio = request.FILES.get('audio')
        if not audio:
            return Response({'detail': 'audio file required'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.staff.models import Employee, TranscriptionRecord
        from apps.staff.views import resolve_company_employee

        # Привязка по ключу компании + email сотрудника (как с десктоп-устройства)
        company_key = request.data.get('company_key', '')
        email = request.data.get('email', '')
        employee = None
        if company_key and email:
            _company, employee, err = resolve_company_employee(company_key, email)
            if err:
                return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Фолбэк: явный employee_id, иначе первый (для отладки/совместимости)
            emp_id = request.data.get('employee_id')
            if emp_id:
                employee = Employee.objects.filter(pk=emp_id).first()
            if employee is None:
                employee = Employee.objects.order_by('id').first()
        if employee is None:
            return Response(
                {'detail': 'Не удалось определить сотрудника для записи'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recorded_at = parse_datetime(request.data.get('recorded_at') or '') or timezone.now()
        is_original = str(request.data.get('is_original', '')).lower() in ('1', 'true', 'yes')
        session_id = request.data.get('session_id', '') or ''
        rec = TranscriptionRecord.objects.create(
            employee=employee, record_datetime=recorded_at, audio=audio,
            session_id=session_id, is_original=is_original,
        )

        # Транскрибируем и сегменты, и сплошной оригинал.
        # Оригинал = весь разговор → диаризация делит спикеров «кто что говорил».
        from apps.analysis.tasks import transcribe_recording
        transcribe_recording.delay(rec.id)

        return Response(
            {'status': 'accepted', 'record_id': rec.id, 'is_original': is_original,
             'session_id': session_id, 'device_id': request.data.get('device_id')},
            status=status.HTTP_202_ACCEPTED,
        )
