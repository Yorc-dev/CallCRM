from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import PlanViewSet, OverviewView

router = DefaultRouter()
router.register('plans', PlanViewSet, basename='plan')

urlpatterns = [
    path('overview/', OverviewView.as_view(), name='billing-overview'),
    path('', include(router.urls)),
]
