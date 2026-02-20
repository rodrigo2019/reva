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
		"""Return the Athlete profile, creating one on-the-fly if missing."""
		from athletes.models import Athlete

		try:
			return self.athlete_profile
		except Athlete.DoesNotExist:
			# Auto-create profile; pick first trainer available or provision a default trainer.
			trainer = User.objects.filter(role=UserRole.TRAINER).first()
			if trainer is None:
				base_username = "reva_trainer"
				username = base_username
				counter = 1
				while User.objects.filter(username=username).exists():
					counter += 1
					username = f"{base_username}_{counter}"

				trainer = User.objects.create_user(
					username=username,
					first_name="REVA",
					last_name="Trainer",
					role=UserRole.TRAINER,
					is_staff=True,
				)
			return Athlete.objects.create(user=self, trainer=trainer)
