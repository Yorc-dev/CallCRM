from django.urls import path
from .views import OverviewView, OperatorsView, CategoriesView

urlpatterns = [
    path('overview', OverviewView.as_view(), name='analytics-overview'),
    path('operators', OperatorsView.as_view(), name='analytics-operators'),
    path('categories', CategoriesView.as_view(), name='analytics-categories'),
]
