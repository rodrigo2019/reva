from django.contrib import admin

from .models import ExercisePrescription, LoadUpdate, WorkoutPlan


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
	list_display = ("name", "athlete", "is_active", "updated_at")


@admin.register(ExercisePrescription)
class ExercisePrescriptionAdmin(admin.ModelAdmin):
	list_display = ("name", "workout", "current_load_kg", "exercise_order")


@admin.register(LoadUpdate)
class LoadUpdateAdmin(admin.ModelAdmin):
	list_display = ("exercise", "previous_load_kg", "new_load_kg", "created_at")

# Register your models here.
