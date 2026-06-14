from rest_framework import serializers
from .models import Department, CompanyAnalysisSettings, AnalysisCriterion


class DepartmentSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    employee_count = serializers.IntegerField(source='employees.count', read_only=True)

    class Meta:
        model = Department
        fields = [
            'id', 'company', 'company_name', 'name', 'description',
            'is_active', 'employee_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CompanyAnalysisSettingsSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanyAnalysisSettings
        fields = ['id', 'company', 'company_name', 'enabled', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class AnalysisCriterionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = AnalysisCriterion
        fields = [
            'id', 'company', 'company_name', 'department', 'department_name',
            'group', 'group_name',
            'name', 'prompt_text', 'enabled', 'order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        company = attrs.get('company') or getattr(self.instance, 'company', None)
        dept = attrs.get('department') or getattr(self.instance, 'department', None)
        group = attrs.get('group') or getattr(self.instance, 'group', None)
        if dept and company and dept.company_id != company.id:
            raise serializers.ValidationError({'department': 'Отдел принадлежит другой компании.'})
        if group and company and group.company_id != company.id:
            raise serializers.ValidationError({'group': 'Группа принадлежит другой компании.'})
        if dept and group:
            raise serializers.ValidationError(
                'Укажите либо отдел, либо группу, но не оба сразу.'
            )
        return attrs
