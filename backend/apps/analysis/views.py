from rest_framework import viewsets, permissions, mixins
from rest_framework.response import Response

from .models import Department, CompanyAnalysisSettings, AnalysisCriterion
from .serializers import (
    DepartmentSerializer, CompanyAnalysisSettingsSerializer, AnalysisCriterionSerializer,
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


class AnalysisCriterionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = AnalysisCriterionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = self.scope(AnalysisCriterion.objects.select_related('company', 'department').all())
        department_id = self.request.query_params.get('department')
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs
