from django.contrib import admin
from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'max_users', 'price', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
