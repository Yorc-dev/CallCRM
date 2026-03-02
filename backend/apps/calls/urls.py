from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, CallViewSet, IntakeAudioView

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'calls', CallViewSet, basename='call')

urlpatterns = [
    path('', include(router.urls)),
    path('intake/audio/', IntakeAudioView.as_view(), name='intake-audio'),
]
