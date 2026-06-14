from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    DepartmentViewSet, CompanyAnalysisSettingsViewSet, AnalysisCriterionViewSet,
)

router = DefaultRouter()
router.register('departments', DepartmentViewSet, basename='department')
router.register('settings', CompanyAnalysisSettingsViewSet, basename='analysissettings')
router.register('criteria', AnalysisCriterionViewSet, basename='analysiscriterion')

urlpatterns = [
    path('', include(router.urls)),
]
