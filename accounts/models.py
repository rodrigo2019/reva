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
		"""Return the linked Athlete profile, if the student has already been correlated to a trainer."""
		return getattr(self, "athlete_profile", None)
