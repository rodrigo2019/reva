from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole

from .models import Athlete


class StudentLinkingFlowTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.client.force_login(self.trainer)

	def test_trainer_links_existing_student_by_email(self):
		student_user = User.objects.create_user(
			username="ana",
			password="secret123",
			first_name="Ana",
			last_name="Silva",
			email="ana@example.com",
			role=UserRole.STUDENT,
		)

		response = self.client.post(
			reverse("student-create"),
			{"email": "ANA@example.com", "notes": "Hipertrofia"},
		)

		self.assertRedirects(response, reverse("student-list"))
		athlete = Athlete.objects.get(user=student_user)
		self.assertEqual(athlete.trainer, self.trainer)
		self.assertEqual(athlete.notes, "Hipertrofia")

	def test_trainer_cannot_link_student_already_linked(self):
		other_trainer = User.objects.create_user(
			username="other-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		student_user = User.objects.create_user(
			username="bia",
			password="secret123",
			email="bia@example.com",
			role=UserRole.STUDENT,
		)
		Athlete.objects.create(user=student_user, trainer=other_trainer)

		response = self.client.post(reverse("student-create"), {"email": "bia@example.com"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "já está vinculado a outro treinador")
		self.assertEqual(Athlete.objects.filter(user=student_user).count(), 1)

	def test_delete_unlinks_student_but_keeps_user_account(self):
		student_user = User.objects.create_user(
			username="carlos",
			password="secret123",
			email="carlos@example.com",
			role=UserRole.STUDENT,
		)
		athlete = Athlete.objects.create(user=student_user, trainer=self.trainer)

		response = self.client.post(reverse("student-delete", args=[athlete.pk]))

		self.assertRedirects(response, reverse("student-list"))
		self.assertFalse(Athlete.objects.filter(pk=athlete.pk).exists())
		self.assertTrue(User.objects.filter(pk=student_user.pk).exists())
