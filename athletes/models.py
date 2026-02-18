from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Athlete(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="athlete_profile")
	trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="athletes")
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def clean(self):
		if self.user_id == self.trainer_id:
			raise ValidationError("Treinador e aluno não podem ser a mesma pessoa.")
		if hasattr(self.user, "is_student") and not self.user.is_student:
			raise ValidationError("O perfil de atleta deve estar vinculado a um usuário aluno.")
		if hasattr(self.trainer, "is_trainer") and not self.trainer.is_trainer:
			raise ValidationError("O treinador vinculado deve ter perfil de treinador.")

	def __str__(self):
		return f"{self.user.get_full_name() or self.user.username}"
