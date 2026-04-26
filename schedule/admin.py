from django.contrib import admin

from .models import ClassSchedule


@admin.register(ClassSchedule)
class ClassScheduleAdmin(admin.ModelAdmin):
    list_display = ("athlete", "trainer", "scheduled_at", "duration_minutes", "status")
    list_filter = ("status", "trainer")
    search_fields = ("athlete__user__first_name", "athlete__user__last_name")
    date_hierarchy = "scheduled_at"
