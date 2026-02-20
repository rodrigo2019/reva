from django.contrib import admin

from .models import ExercisePrescription, ExerciseProgressLog, LoadUpdate, WorkoutPlan


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
	list_display = ("name", "athlete", "is_active", "updated_at")


@admin.register(ExercisePrescription)
class ExercisePrescriptionAdmin(admin.ModelAdmin):
	list_display = ("name", "workout", "sets", "reps", "current_load_kg", "rest_seconds", "exercise_order")


@admin.register(LoadUpdate)
class LoadUpdateAdmin(admin.ModelAdmin):
	list_display = ("exercise", "previous_load_kg", "new_load_kg", "created_at")


@admin.register(ExerciseProgressLog)
class ExerciseProgressLogAdmin(admin.ModelAdmin):
	list_display = ("exercise", "sets", "reps", "load_kg", "rest_seconds", "created_at")
	list_filter = ("exercise__workout",)
	ordering = ("-created_at",)
