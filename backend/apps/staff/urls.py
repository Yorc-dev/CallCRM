from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    CompanyViewSet, EmployeeViewSet, EmployeeGroupViewSet,
    RecordingCategoryViewSet, TranscriptionRecordViewSet,
    AnalysisViewSet, IncidentViewSet, DeviceBindView,
)

router = DefaultRouter()
router.register('companies', CompanyViewSet, basename='company')
router.register('employees', EmployeeViewSet, basename='employee')
router.register('groups', EmployeeGroupViewSet, basename='employeegroup')
router.register('categories', RecordingCategoryViewSet, basename='recordingcategory')
router.register('transcriptions', TranscriptionRecordViewSet, basename='transcription')
router.register('analyses', AnalysisViewSet, basename='analysis')
router.register('incidents', IncidentViewSet, basename='incident')

urlpatterns = [
    path('device-bind/', DeviceBindView.as_view(), name='device-bind'),
    path('', include(router.urls)),
]
