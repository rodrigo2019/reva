from django.db import models

from athletes.models import Athlete


class ChatSession(models.Model):
	athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="chat_sessions")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]


class ChatMessage(models.Model):
	class Role(models.TextChoices):
		USER = "user", "Usuário"
		ASSISTANT = "assistant", "Assistente"

	session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
	role = models.CharField(max_length=20, choices=Role.choices)
	content = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)
	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["created_at"]
