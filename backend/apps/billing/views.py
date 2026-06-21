from django.db.models import Count, Max
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Plan
from .serializers import PlanSerializer
from apps.calls.permissions import IsChiefOrAdmin


class PlanViewSet(viewsets.ModelViewSet):
    """CRUD по тарифным пакетам. Только админ/руководитель."""
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]


class OverviewView(APIView):
    """Главная АИС: сводка по всем компаниям — подписка, стоимость, активность."""
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]

    def get(self, request):
        from apps.staff.models import Company
        companies = (
            Company.objects.select_related('plan')
            .annotate(
                users=Count('employees', distinct=True),
                last_activity=Max('employees__transcriptions__record_datetime'),
                records=Count('employees__transcriptions', distinct=True),
            )
            .order_by('name')
        )
        rows = []
        total_cost = 0
        for c in companies:
            cost = c.plan.cost_for(c.users) if c.plan_id else None
            if cost:
                total_cost += float(cost)
            rows.append({
                'id': c.id,
                'name': c.name,
                'plan': c.plan.name if c.plan_id else None,
                'billing_type': c.plan.get_billing_type_display() if c.plan_id else None,
                'users': c.users,
                'max_users': c.plan.max_users if c.plan_id else None,
                'monthly_cost': float(cost) if cost is not None else None,
                'records': c.records,
                'last_activity': c.last_activity.isoformat() if c.last_activity else None,
                'api_key': c.api_key,
            })
        return Response({
            'companies': rows,
            'totals': {
                'companies': len(rows),
                'monthly_cost': total_cost,
                'active_subscriptions': sum(1 for r in rows if r['plan']),
            },
        })
