from django.conf import settings
from django.db import models
from django.urls import reverse

from athletes.models import Athlete


class MuscleGroup(models.TextChoices):
	CHEST = "chest", "Peito"
	BACK = "back", "Costas"
	SHOULDERS = "shoulders", "Ombros"
	BICEPS = "biceps", "Bíceps"
	TRICEPS = "triceps", "Tríceps"
	FOREARMS = "forearms", "Antebraço"
	ABS = "abs", "Abdômen"
	QUADRICEPS = "quadriceps", "Quadríceps"
	HAMSTRINGS = "hamstrings", "Posteriores"
	GLUTES = "glutes", "Glúteos"
	CALVES = "calves", "Panturrilha"
	FULL_BODY = "full_body", "Corpo inteiro"
	OTHER = "other", "Outro"


class Equipment(models.TextChoices):
	BARBELL = "barbell", "Barra"
	DUMBBELL = "dumbbell", "Haltere"
	MACHINE = "machine", "Máquina"
	CABLE = "cable", "Cabo/Polia"
	BODYWEIGHT = "bodyweight", "Peso corporal"
	KETTLEBELL = "kettlebell", "Kettlebell"
	BAND = "band", "Elástico"
	SMITH = "smith", "Smith Machine"
	OTHER = "other", "Outro"


def exercise_image_path(instance, filename):
	ext = filename.rsplit(".", 1)[-1].lower()
	return f"exercises/{instance.pk or 'tmp'}_{instance.slug}.{ext}"


class Exercise(models.Model):
	"""
	Catálogo de exercícios com foto, grupo muscular e equipamento.
	Pode ser global (created_by=None) ou criado por um treinador específico.
	"""
	name = models.CharField("Nome", max_length=150)
	slug = models.SlugField(max_length=160, blank=True)
	description = models.TextField("Descrição / instrução", blank=True)
	muscle_group = models.CharField(
		"Grupo muscular",
		max_length=20,
		choices=MuscleGroup.choices,
		default=MuscleGroup.OTHER,
	)
	secondary_muscle = models.CharField(
		"Músculo secundário",
		max_length=20,
		choices=MuscleGroup.choices,
		blank=True,
		default="",
	)
	equipment = models.CharField(
		"Equipamento",
		max_length=20,
		choices=Equipment.choices,
		default=Equipment.OTHER,
	)
	image = models.ImageField(
		"Foto do exercício",
		upload_to=exercise_image_path,
		blank=True,
		null=True,
	)
	video_url = models.URLField("URL de vídeo demonstrativo", blank=True)
	default_sets = models.PositiveSmallIntegerField("Séries padrão", default=3)
	default_reps = models.CharField("Reps padrão", max_length=30, default="8-12")
	default_rest_seconds = models.PositiveIntegerField("Descanso padrão (s)", default=60)
	tips = models.TextField("Dicas de execução", blank=True)
	is_global = models.BooleanField(
		"Disponível para todos",
		default=False,
		help_text="Exercícios globais ficam visíveis para todos os treinadores.",
	)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="created_exercises",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["muscle_group", "name"]

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		if not self.slug:
			from django.utils.text import slugify
			base = slugify(self.name)
			slug = base
			counter = 1
			while Exercise.objects.filter(slug=slug).exclude(pk=self.pk).exists():
				slug = f"{base}-{counter}"
				counter += 1
			self.slug = slug
		super().save(*args, **kwargs)
		# Re-save image with correct pk path if needed
		if self.image and "tmp_" in self.image.name:
			old_name = self.image.name
			new_name = exercise_image_path(self, old_name.rsplit("/", 1)[-1])
			if old_name != new_name:
				import os
				from django.core.files.storage import default_storage
				if default_storage.exists(old_name):
					default_storage.save(new_name, self.image)
					default_storage.delete(old_name)
					Exercise.objects.filter(pk=self.pk).update(image=new_name)

	def get_absolute_url(self):
		return reverse("exercise-catalog-detail", kwargs={"pk": self.pk})

	@property
	def muscle_group_label(self):
		return self.get_muscle_group_display()

	@property
	def equipment_label(self):
		return self.get_equipment_display()


class TrainingPlan(models.Model):
	"""
	High-level training plan (e.g. "Hipertrofia 2026").
	Contains multiple WorkoutPlans (e.g. Treino A — Costas, Treino B — Peito).
	"""
	athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="training_plans")
	name = models.CharField("Nome do plano", max_length=150)
	objective = models.CharField("Objetivo", max_length=300, blank=True)
	is_active = models.BooleanField("Ativo", default=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="created_plans",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-updated_at"]

	def __str__(self):
		return f"{self.name} — {self.athlete}"

	def get_absolute_url(self):
		return reverse("plan-detail", kwargs={"pk": self.pk})


class WorkoutPlan(models.Model):
	plan = models.ForeignKey(
		TrainingPlan,
		on_delete=models.CASCADE,
		related_name="workouts",
		null=True,
		blank=True,
	)
	athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="workout_plans")
	name = models.CharField(max_length=120)
	objective = models.CharField(max_length=200, blank=True)
	is_active = models.BooleanField(default=True)
	is_archived = models.BooleanField("Arquivado", default=False)
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
	exercise_ref = models.ForeignKey(
		Exercise,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="prescriptions",
		verbose_name="Exercício do catálogo",
	)
	name = models.CharField(max_length=120, blank=True)
	sets = models.PositiveSmallIntegerField(default=3)
	reps = models.CharField(max_length=30, default="8-12")
	current_load_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	rest_seconds = models.PositiveIntegerField(default=60)
	exercise_order = models.PositiveSmallIntegerField(default=1)
	notes = models.CharField(max_length=255, blank=True)

	class Meta:
		ordering = ["exercise_order", "id"]
		unique_together = ("workout", "exercise_order")

	@property
	def display_name(self):
		if self.exercise_ref:
			return self.exercise_ref.name
		return self.name or "Exercício sem nome"

	@property
	def image(self):
		if self.exercise_ref and self.exercise_ref.image:
			return self.exercise_ref.image
		return None

	@property
	def muscle_group_label(self):
		if self.exercise_ref:
			return self.exercise_ref.muscle_group_label
		return ""

	@property
	def equipment_label(self):
		if self.exercise_ref:
			return self.exercise_ref.equipment_label
		return ""

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
		return self.display_name


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


class ExerciseAlternative(models.Model):
	"""
	Alternative/substitute exercise for a prescription.
	When the main exercise equipment is occupied, the student can use one of these.
	"""
	prescription = models.ForeignKey(
		ExercisePrescription,
		on_delete=models.CASCADE,
		related_name="alternatives",
	)
	exercise_ref = models.ForeignKey(
		Exercise,
		on_delete=models.CASCADE,
		related_name="used_as_alternative",
		verbose_name="Exercício substituto",
	)
	notes = models.CharField("Observação", max_length=255, blank=True)
	order = models.PositiveSmallIntegerField(default=1)

	class Meta:
		ordering = ["order", "id"]

	def __str__(self):
		return f"Alt. para {self.prescription.display_name}: {self.exercise_ref.name}"
