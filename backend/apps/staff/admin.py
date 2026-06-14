from django.contrib import admin
from .models import (
    Company, EmployeeGroup, Employee,
    RecordingCategory, TranscriptionRecord, Analysis, Incident,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'api_key', 'created_at']
    search_fields = ['name']
    readonly_fields = ['api_key', 'encryption_key', 'created_at', 'updated_at']


@admin.register(EmployeeGroup)
class EmployeeGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'company', 'accesses', 'created_at']
    list_filter = ['company']
    search_fields = ['name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'email', 'company', 'group', 'certificate_expires_at', 'created_at']
    list_filter = ['company', 'group']
    search_fields = ['full_name', 'email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RecordingCategory)
class RecordingCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'title']


@admin.register(TranscriptionRecord)
class TranscriptionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'employee', 'category', 'record_datetime', 'created_at']
    list_filter = ['category', 'employee__company']
    search_fields = ['employee__full_name', 'text']


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'record', 'created_at']
    search_fields = ['description', 'record__employee__full_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['id', 'record', 'start_minutes', 'end_minutes', 'analysis', 'created_at']
    list_filter = ['record__employee__company']
    search_fields = ['record__employee__full_name']
