from django.conf import settings
from django.db import models
from django.urls import reverse

from athletes.models import Athlete


class WorkoutPlan(models.Model):
	athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="workout_plans")
	name = models.CharField(max_length=120)
	objective = models.CharField(max_length=200, blank=True)
	is_active = models.BooleanField(default=True)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_workouts")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-updated_at"]

	def __str__(self):
		return f"{self.name} - {self.athlete}"

	def get_absolute_url(self):
		return reverse("workout-detail", kwargs={"pk": self.pk})


TRACKED_FIELDS = ("sets", "reps", "current_load_kg", "rest_seconds")


class ExercisePrescription(models.Model):
	workout = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="exercises")
	name = models.CharField(max_length=120)
	sets = models.PositiveSmallIntegerField(default=3)
	reps = models.CharField(max_length=30, default="8-12")
	current_load_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	rest_seconds = models.PositiveIntegerField(default=60)
	exercise_order = models.PositiveSmallIntegerField(default=1)
	notes = models.CharField(max_length=255, blank=True)

	class Meta:
		ordering = ["exercise_order", "id"]
		unique_together = ("workout", "exercise_order")

	def save(self, *args, **kwargs):
		is_create = self.pk is None
		previous = None

		if not is_create:
			previous = (
				ExercisePrescription.objects.filter(pk=self.pk)
				.values(*TRACKED_FIELDS)
				.first()
			)

		super().save(*args, **kwargs)

		# Determine if any tracked field changed
		should_log = is_create
		if previous and not is_create:
			should_log = any(
				previous[field] != getattr(self, field) for field in TRACKED_FIELDS
			)

		if should_log:
			ExerciseProgressLog.objects.create(
				exercise=self,
				sets=self.sets,
				reps=self.reps,
				load_kg=self.current_load_kg,
				rest_seconds=self.rest_seconds,
				notes=self.notes,
			)

		# Backward-compat: also create LoadUpdate when load changes
		previous_load = previous["current_load_kg"] if previous else None
		load_changed = previous_load != self.current_load_kg
		if self.current_load_kg is not None and (is_create or load_changed):
			LoadUpdate.objects.create(
				exercise=self,
				previous_load_kg=previous_load,
				new_load_kg=self.current_load_kg,
				reason="Atualização automática",
			)

	def __str__(self):
		return self.name


class LoadUpdate(models.Model):
	exercise = models.ForeignKey(ExercisePrescription, on_delete=models.CASCADE, related_name="load_updates")
	previous_load_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	new_load_kg = models.DecimalField(max_digits=6, decimal_places=2)
	reason = models.CharField(max_length=255, blank=True)
	updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.exercise.name}: {self.new_load_kg} kg"


class ExerciseProgressLog(models.Model):
	"""Snapshot of all exercise parameters every time a change is made."""
	exercise = models.ForeignKey(ExercisePrescription, on_delete=models.CASCADE, related_name="progress_logs")
	sets = models.PositiveSmallIntegerField()
	reps = models.CharField(max_length=30)
	load_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	rest_seconds = models.PositiveIntegerField()
	notes = models.CharField(max_length=255, blank=True)
	updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.exercise.name}: {self.sets}x{self.reps} @ {self.load_kg or 0}kg"
