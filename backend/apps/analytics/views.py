from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from apps.calls.models import Call
from apps.calls.permissions import IsChiefOrAdmin


def parse_date_range(request):
    from_date = request.query_params.get('from')
    to_date = request.query_params.get('to')
    filters = {}
    if from_date:
        filters['call_datetime__date__gte'] = parse_date(from_date)
    if to_date:
        filters['call_datetime__date__lte'] = parse_date(to_date)
    return filters


class OverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]

    def get(self, request):
        filters = parse_date_range(request)
        qs = Call.objects.filter(**filters)

        total_calls = qs.count()
        done_calls = qs.filter(status='done').count()
        failed_calls = qs.filter(status='failed').count()
        avg_duration = qs.aggregate(avg=Avg('duration_sec'))['avg']

        calls_per_day = list(
            qs.annotate(date=TruncDate('call_datetime'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
            .values('date', 'count')
        )
        # Serialize dates to strings
        calls_per_day = [
            {'date': str(row['date']), 'count': row['count']}
            for row in calls_per_day
        ]

        avg_script_score = qs.filter(
            status='done', analysis__script_score__isnull=False
        ).aggregate(avg=Avg('analysis__script_score'))['avg']

        return Response({
            'total_calls': total_calls,
            'done_calls': done_calls,
            'failed_calls': failed_calls,
            'avg_duration_sec': round(avg_duration, 1) if avg_duration else None,
            'calls_per_day': calls_per_day,
            'avg_script_score': min(int(round(avg_script_score * 100)), 100) if avg_script_score is not None else None,
        })


class OperatorsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]

    def get(self, request):
        filters = parse_date_range(request)
        qs = (
            Call.objects.filter(**filters)
            .values('operator__id', 'operator__username', 'operator__first_name', 'operator__last_name')
            .annotate(
                total=Count('id'),
                done=Count('id', filter=Q(status='done')),
                failed=Count('id', filter=Q(status='failed')),
                avg_duration=Avg('duration_sec'),
                avg_script_score=Avg(
                    'analysis__script_score',
                    filter=Q(status='done', analysis__script_score__isnull=False),
                ),
            )
            .order_by('-total')
        )

        results = []
        for row in qs:
            results.append({
                'operator_id': row['operator__id'],
                'username': row['operator__username'],
                'full_name': f"{row['operator__first_name']} {row['operator__last_name']}".strip(),
                'total_calls': row['total'],
                'done_calls': row['done'],
                'failed_calls': row['failed'],
                'avg_duration_sec': round(row['avg_duration'], 1) if row['avg_duration'] else None,
                'avg_script_score': min(int(round(row['avg_script_score'] * 100)), 100) if row['avg_script_score'] is not None else None,
            })

        return Response(results)


class CategoriesView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsChiefOrAdmin]

    def get(self, request):
        filters = parse_date_range(request)
        qs = (
            Call.objects.filter(**filters)
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        results = [
            {'category': row['category'] or 'uncategorized', 'count': row['count']}
            for row in qs
        ]

        return Response(results)
