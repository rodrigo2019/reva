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
		previous_load = None
		is_create = self.pk is None
		if not is_create:
			previous_load = (
				ExercisePrescription.objects.filter(pk=self.pk).values_list("current_load_kg", flat=True).first()
			)

		super().save(*args, **kwargs)

		load_changed = previous_load != self.current_load_kg
		should_create_history = self.current_load_kg is not None and (is_create or load_changed)
		if should_create_history:
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
