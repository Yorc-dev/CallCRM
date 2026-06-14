from rest_framework import viewsets, permissions
from .models import Plan
from .serializers import PlanSerializer
from apps.calls.permissions import IsChiefOrAdmin


class PlanViewSet(viewsets.ModelViewSet):
    """CRUD по тарифным пакетам. Только админ/руководитель."""
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]
