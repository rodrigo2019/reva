from django.test import TestCase
from django.urls import reverse

from .models import User, UserRole


class StudentAccessWithoutLinkTests(TestCase):
	def setUp(self):
		self.student = User.objects.create_user(
			username="aluno-solto",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.client.force_login(self.student)

	def test_unlinked_student_dashboard_renders_empty_state(self):
		response = self.client.get(reverse("student-dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Perfil aguardando vínculo")

	def test_unlinked_student_progress_redirects_to_dashboard(self):
		response = self.client.get(reverse("my-progress"))

		self.assertRedirects(response, reverse("student-dashboard"))

	def test_unlinked_student_chat_redirects_to_dashboard(self):
		response = self.client.get(reverse("ai-chat"))

		self.assertRedirects(response, reverse("student-dashboard"))
