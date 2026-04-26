from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from athletes.models import Athlete
from workouts.models import WorkoutPlan

from .models import ClassSchedule
from .services import ScheduleService


class ScheduleDomainIsolationTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="schedule-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student_one = User.objects.create_user(
			username="schedule-student-one",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.student_two = User.objects.create_user(
			username="schedule-student-two",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.athlete_one = Athlete.objects.create(user=self.student_one, trainer=self.trainer)
		self.athlete_two = Athlete.objects.create(user=self.student_two, trainer=self.trainer)
		self.workout_one = WorkoutPlan.objects.create(
			athlete=self.athlete_one,
			name="Treino aluno 1",
			created_by=self.trainer,
		)
		self.workout_two = WorkoutPlan.objects.create(
			athlete=self.athlete_two,
			name="Treino aluno 2",
			created_by=self.trainer,
		)
		self.client.force_login(self.trainer)

	def test_class_create_rejects_workout_from_different_athlete(self):
		response = self.client.post(
			reverse("class-create"),
			{
				"athlete": str(self.athlete_one.pk),
				"scheduled_date": "2026-05-04",
				"scheduled_time": "07:00",
				"duration_minutes": "60",
				"workout_plan": str(self.workout_two.pk),
				"status": ClassSchedule.Status.SCHEDULED,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Selecione um treino deste aluno.")
		self.assertEqual(ClassSchedule.objects.count(), 0)

	def test_class_model_rejects_workout_from_different_athlete(self):
		with self.assertRaises(ValidationError):
			ClassSchedule.objects.create(
				trainer=self.trainer,
				athlete=self.athlete_one,
				scheduled_at=timezone.now(),
				duration_minutes=60,
				workout_plan=self.workout_two,
			)

	def test_class_model_rejects_athlete_from_different_trainer(self):
		other_trainer = User.objects.create_user(
			username="schedule-other-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)

		with self.assertRaises(ValidationError):
			ClassSchedule.objects.create(
				trainer=other_trainer,
				athlete=self.athlete_one,
				scheduled_at=timezone.now(),
				duration_minutes=60,
				workout_plan=self.workout_one,
			)

	def test_schedule_service_creates_class_for_owned_athlete(self):
		cls = ScheduleService.create_class(
			self.trainer,
			self.athlete_one,
			timezone.now(),
			duration_minutes=45,
			workout_plan=self.workout_one,
			notes="Service schedule",
		)

		self.assertEqual(cls.trainer, self.trainer)
		self.assertEqual(cls.athlete, self.athlete_one)
		self.assertEqual(cls.workout_plan, self.workout_one)
		self.assertEqual(cls.duration_minutes, 45)

	def test_schedule_service_rejects_workout_from_different_athlete(self):
		with self.assertRaises(ValidationError):
			ScheduleService.create_class(
				self.trainer,
				self.athlete_one,
				timezone.now(),
				workout_plan=self.workout_two,
			)