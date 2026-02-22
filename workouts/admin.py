from django.contrib import admin

from .models import (
	Exercise,
	ExerciseAlternative,
	ExercisePrescription,
	ExerciseProgressLog,
	LoadUpdate,
	TrainingPlan,
	WorkoutPlan,
)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
	list_display = ("name", "muscle_group", "equipment", "is_global", "created_by", "updated_at")
	list_filter = ("muscle_group", "equipment", "is_global")
	search_fields = ("name", "description")
	prepopulated_fields = {"slug": ("name",)}


class WorkoutInline(admin.TabularInline):
	model = WorkoutPlan
	extra = 0
	fields = ("name", "objective", "is_active", "is_archived")
	show_change_link = True


@admin.register(TrainingPlan)
class TrainingPlanAdmin(admin.ModelAdmin):
	list_display = ("name", "athlete", "is_active", "created_by", "updated_at")
	list_filter = ("is_active",)
	search_fields = ("name", "athlete__user__first_name", "athlete__user__last_name")
	inlines = [WorkoutInline]


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
	list_display = ("name", "plan", "athlete", "is_active", "is_archived", "updated_at")
	list_filter = ("is_active", "is_archived")


class ExerciseAlternativeInline(admin.TabularInline):
	model = ExerciseAlternative
	extra = 0


@admin.register(ExercisePrescription)
class ExercisePrescriptionAdmin(admin.ModelAdmin):
	list_display = ("name", "workout", "sets", "reps", "current_load_kg", "rest_seconds", "exercise_order")
	inlines = [ExerciseAlternativeInline]


@admin.register(ExerciseAlternative)
class ExerciseAlternativeAdmin(admin.ModelAdmin):
	list_display = ("prescription", "exercise_ref", "order", "notes")


@admin.register(LoadUpdate)
class LoadUpdateAdmin(admin.ModelAdmin):
	list_display = ("exercise", "previous_load_kg", "new_load_kg", "created_at")


@admin.register(ExerciseProgressLog)
class ExerciseProgressLogAdmin(admin.ModelAdmin):
	list_display = ("exercise", "sets", "reps", "load_kg", "rest_seconds", "created_at")
	list_filter = ("exercise__workout",)
	ordering = ("-created_at",)
