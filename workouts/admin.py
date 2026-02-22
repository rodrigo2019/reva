from django.contrib import admin

from .models import Exercise, ExercisePrescription, ExerciseProgressLog, LoadUpdate, WorkoutPlan


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
	list_display = ("name", "muscle_group", "equipment", "is_global", "created_by", "updated_at")
	list_filter = ("muscle_group", "equipment", "is_global")
	search_fields = ("name", "description")
	prepopulated_fields = {"slug": ("name",)}


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
