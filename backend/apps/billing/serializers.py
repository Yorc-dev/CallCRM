from rest_framework import serializers
from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    company_count = serializers.IntegerField(source='companies.count', read_only=True)

    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'description', 'max_users', 'price',
            'features', 'is_active', 'company_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
