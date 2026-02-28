from django.contrib import admin

from .models import Anamnesis, Athlete, PhysicalAssessment


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
	list_display = ("user", "trainer", "created_at")


@admin.register(Anamnesis)
class AnamnesisAdmin(admin.ModelAdmin):
	list_display = ("athlete", "primary_goal", "training_experience", "updated_at")
	list_filter = ("primary_goal", "training_experience", "gender")
	search_fields = ("athlete__user__first_name", "athlete__user__last_name")


@admin.register(PhysicalAssessment)
class PhysicalAssessmentAdmin(admin.ModelAdmin):
	list_display = ("athlete", "assessed_at", "weight_kg", "height_cm", "body_fat_percentage")
	list_filter = ("assessed_at",)
	search_fields = ("athlete__user__first_name", "athlete__user__last_name")
	date_hierarchy = "assessed_at"
