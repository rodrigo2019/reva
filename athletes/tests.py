from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole

from .models import Athlete, StudentRelationshipStatus
from .services import AthleteService


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

	def test_trainer_cannot_link_missing_student_account(self):
		response = self.client.post(reverse("student-create"), {"email": "missing@example.com"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "O aluno precisa se cadastrar primeiro")
		self.assertEqual(Athlete.objects.count(), 0)

	def test_trainer_cannot_link_trainer_account(self):
		trainer_user = User.objects.create_user(
			username="trainer-as-student",
			password="secret123",
			email="trainer@example.com",
			role=UserRole.TRAINER,
		)

		response = self.client.post(reverse("student-create"), {"email": trainer_user.email})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "não é de aluno")
		self.assertEqual(Athlete.objects.count(), 0)

	def test_trainer_cannot_access_other_trainer_student_detail(self):
		other_trainer = User.objects.create_user(
			username="other-detail-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		student_user = User.objects.create_user(
			username="detail-student",
			password="secret123",
			email="detail@example.com",
			role=UserRole.STUDENT,
		)
		athlete = Athlete.objects.create(user=student_user, trainer=other_trainer)

		response = self.client.get(reverse("student-detail", args=[athlete.pk]))

		self.assertEqual(response.status_code, 404)

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
		athlete.refresh_from_db()
		self.assertIsNone(athlete.trainer)
		self.assertEqual(athlete.relationship_status, StudentRelationshipStatus.ENDED)
		self.assertTrue(User.objects.filter(pk=student_user.pk).exists())


class AthleteServiceTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="service-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.other_trainer = User.objects.create_user(
			username="service-other-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student = User.objects.create_user(
			username="service-student",
			password="secret123",
			email="service-student@example.com",
			role=UserRole.STUDENT,
		)

	def test_link_existing_student_creates_scoped_athlete(self):
		athlete = AthleteService.link_existing_student(
			self.trainer,
			"SERVICE-STUDENT@example.com",
			notes="Service onboarding",
		)

		self.assertEqual(athlete.user, self.student)
		self.assertEqual(athlete.trainer, self.trainer)
		self.assertEqual(athlete.relationship_status, StudentRelationshipStatus.ACTIVE)
		self.assertEqual(athlete.notes, "Service onboarding")

	def test_link_existing_student_reuses_independent_profile(self):
		profile = Athlete.objects.create(user=self.student)

		athlete = AthleteService.link_existing_student(
			self.trainer,
			"SERVICE-STUDENT@example.com",
			notes="Convite aceito",
		)

		self.assertEqual(athlete.pk, profile.pk)
		self.assertEqual(athlete.trainer, self.trainer)
		self.assertEqual(athlete.relationship_status, StudentRelationshipStatus.ACTIVE)
		self.assertEqual(athlete.notes, "Convite aceito")

	def test_non_trainer_cannot_link_student(self):
		with self.assertRaises(PermissionDenied):
			AthleteService.link_existing_student(self.student, self.student.email)

	def test_get_owned_athlete_rejects_other_trainer_scope(self):
		athlete = Athlete.objects.create(user=self.student, trainer=self.other_trainer)

		with self.assertRaises(PermissionDenied):
			AthleteService.get_owned_athlete(self.trainer, athlete.pk)
