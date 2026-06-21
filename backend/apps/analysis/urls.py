from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    DepartmentViewSet, CompanyAnalysisSettingsViewSet, AnalysisCriterionViewSet,
    PromptListViewSet, IngestAudioView,
)

router = DefaultRouter()
router.register('departments', DepartmentViewSet, basename='department')
router.register('settings', CompanyAnalysisSettingsViewSet, basename='analysissettings')
router.register('prompt-lists', PromptListViewSet, basename='promptlist')
router.register('criteria', AnalysisCriterionViewSet, basename='analysiscriterion')

urlpatterns = [
    path('ingest/', IngestAudioView.as_view(), name='audio-ingest'),
    path('', include(router.urls)),
]
