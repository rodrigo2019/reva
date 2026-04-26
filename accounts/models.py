from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
	TRAINER = "trainer", "Treinador"
	STUDENT = "student", "Aluno"


class User(AbstractUser):
	role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)

	@property
	def is_trainer(self):
		return self.role == UserRole.TRAINER

	@property
	def is_student(self):
		return self.role == UserRole.STUDENT

	def get_athlete_profile(self):
		"""Return the student's independent profile, creating it lazily when needed."""
		profile = getattr(self, "athlete_profile", None)
		if profile is not None or not self.is_student or self.pk is None:
			return profile
		from athletes.models import Athlete
		return Athlete.objects.create(user=self)
