from django.urls import path
from .views import AssistantCriteriaView, AssistantQueryView

urlpatterns = [
    path('criteria/', AssistantCriteriaView.as_view(), name='assistant-criteria'),
    path('query/', AssistantQueryView.as_view(), name='assistant-query'),
]
