from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from athletes.models import Athlete
from schedule.models import ClassSchedule
from workouts.models import Exercise, ExercisePrescription, LoadUpdate, TrainingPlan, WorkoutPlan

from .models import User, UserRole


class IndependentStudentAccessTests(TestCase):
	def setUp(self):
		self.student = User.objects.create_user(
			username="aluno-solto",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.client.force_login(self.student)

	def test_independent_student_dashboard_creates_profile_and_renders(self):
		response = self.client.get(reverse("student-dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Modo independente ativo")
		profile = Athlete.objects.get(user=self.student)
		self.assertIsNone(profile.trainer)
		self.assertTrue(profile.is_independent)

	def test_independent_student_progress_renders(self):
		response = self.client.get(reverse("my-progress"))

		self.assertEqual(response.status_code, 200)

	def test_independent_student_chat_renders(self):
		response = self.client.get(reverse("ai-chat"))

		self.assertEqual(response.status_code, 200)

	def test_independent_student_profile_renders(self):
		response = self.client.get(reverse("student-self-profile"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Modo independente")

	def test_independent_student_workout_list_renders(self):
		response = self.client.get(reverse("student-workout-list"))

		self.assertEqual(response.status_code, 200)


class TrainerOperationalDashboardTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="dashboard-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student = User.objects.create_user(
			username="dashboard-student",
			password="secret123",
			role=UserRole.STUDENT,
			first_name="Ana",
			last_name="Silva",
		)
		self.stale_student = User.objects.create_user(
			username="dashboard-stale",
			password="secret123",
			role=UserRole.STUDENT,
			first_name="Bruno",
			last_name="Lento",
		)
		self.athlete = Athlete.objects.create(user=self.student, trainer=self.trainer)
		self.stale_athlete = Athlete.objects.create(user=self.stale_student, trainer=self.trainer)
		self.plan = TrainingPlan.objects.create(
			athlete=self.athlete,
			name="Plano antigo",
			created_by=self.trainer,
		)
		TrainingPlan.objects.filter(pk=self.plan.pk).update(
			updated_at=timezone.now() - timezone.timedelta(days=45)
		)
		self.workout = WorkoutPlan.objects.create(
			athlete=self.athlete,
			plan=self.plan,
			name="Treino operacional",
			created_by=self.trainer,
		)
		self.exercise_ref = Exercise.objects.create(name="Supino dashboard", is_global=True)
		self.exercise = ExercisePrescription.objects.create(
			workout=self.workout,
			exercise_ref=self.exercise_ref,
			sets=3,
			reps="8",
			current_load_kg=Decimal("50.00"),
		)
		LoadUpdate.objects.create(
			exercise=self.exercise,
			previous_load_kg=Decimal("50.00"),
			new_load_kg=Decimal("70.00"),
			updated_by=self.trainer,
		)

		now = timezone.now()
		ClassSchedule.objects.create(
			trainer=self.trainer,
			athlete=self.athlete,
			scheduled_at=now.replace(hour=10, minute=0, second=0, microsecond=0),
			duration_minutes=60,
			workout_plan=self.workout,
		)
		ClassSchedule.objects.create(
			trainer=self.trainer,
			athlete=self.athlete,
			scheduled_at=now - timezone.timedelta(days=2),
			duration_minutes=60,
			workout_plan=self.workout,
			status=ClassSchedule.Status.NO_SHOW,
		)
		self.client.force_login(self.trainer)

	def test_trainer_dashboard_surfaces_operational_today_context(self):
		response = self.client.get(reverse("trainer-dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["today_class_count"], 1)
		self.assertEqual(response.context["load_jump_count"], 1)
		self.assertEqual(response.context["no_show_count"], 1)
		self.assertIn(
			self.stale_athlete.pk,
			[item["athlete"].pk for item in response.context["students_needing_attention"]],
		)
		self.assertContains(response, "Hoje")
		self.assertContains(response, "Aulas de hoje")
		self.assertContains(response, "Ana Silva")
		self.assertContains(response, "Carga subiu 40%")
		self.assertContains(response, "Falta registrada")
		self.assertContains(response, "Plano antigo")

	def test_trainer_dashboard_does_not_show_other_trainer_data(self):
		other_trainer = User.objects.create_user(
			username="dashboard-other-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		other_student = User.objects.create_user(
			username="dashboard-other-student",
			password="secret123",
			role=UserRole.STUDENT,
			first_name="Outro",
			last_name="Aluno",
		)
		other_athlete = Athlete.objects.create(user=other_student, trainer=other_trainer)
		other_workout = WorkoutPlan.objects.create(
			athlete=other_athlete,
			name="Treino oculto",
			created_by=other_trainer,
		)
		ClassSchedule.objects.create(
			trainer=other_trainer,
			athlete=other_athlete,
			scheduled_at=timezone.now().replace(hour=11, minute=0, second=0, microsecond=0),
			duration_minutes=60,
			workout_plan=other_workout,
		)

		response = self.client.get(reverse("trainer-dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "Outro Aluno")
		self.assertNotContains(response, "Treino oculto")
