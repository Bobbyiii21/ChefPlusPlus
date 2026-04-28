from django.contrib import admin
from .models import AccuracyTestCase, AccuracyTestRun, DatabaseFile


class DatabaseFileAdmin(admin.ModelAdmin):
    ordering = ['id', 'name']
    search_fields = ['name']
    model = DatabaseFile


class AccuracyTestCaseAdmin(admin.ModelAdmin):
    ordering = ['name']
    search_fields = ['name', 'question']
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    model = AccuracyTestCase


class AccuracyTestRunAdmin(admin.ModelAdmin):
    ordering = ['-created_at']
    search_fields = ['test_case__name', 'actual_answer', 'error_message']
    list_display = ['test_case', 'status', 'response_time_ms', 'created_at']
    list_filter = ['status']
    model = AccuracyTestRun


admin.site.register(DatabaseFile, DatabaseFileAdmin)
admin.site.register(AccuracyTestCase, AccuracyTestCaseAdmin)
admin.site.register(AccuracyTestRun, AccuracyTestRunAdmin)