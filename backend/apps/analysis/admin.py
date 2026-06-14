from django.contrib import admin
from .models import Department, CompanyAnalysisSettings, AnalysisCriterion


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'company', 'is_active', 'created_at']
    list_filter = ['company', 'is_active']
    search_fields = ['name']


@admin.register(CompanyAnalysisSettings)
class CompanyAnalysisSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'enabled', 'updated_at']
    list_filter = ['enabled']


@admin.register(AnalysisCriterion)
class AnalysisCriterionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'company', 'department', 'enabled', 'order']
    list_filter = ['company', 'department', 'enabled']
    search_fields = ['name', 'prompt_text']
