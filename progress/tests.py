from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from accounts.models import User, UserRole
from athletes.models import Athlete
from workouts.models import Exercise, ExercisePrescription, WorkoutPlan

from .services import ProgressService


class ProgressServiceTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="progress-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.other_trainer = User.objects.create_user(
			username="progress-other-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student = User.objects.create_user(
			username="progress-student",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.other_student = User.objects.create_user(
			username="progress-other-student",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.athlete = Athlete.objects.create(user=self.student, trainer=self.trainer)
		self.other_athlete = Athlete.objects.create(user=self.other_student, trainer=self.other_trainer)
		self.workout = WorkoutPlan.objects.create(
			athlete=self.athlete,
			name="Treino progresso",
			created_by=self.trainer,
		)
		exercise_ref = Exercise.objects.create(name="Remada progresso", is_global=True)
		self.exercise = ExercisePrescription.objects.create(
			workout=self.workout,
			exercise_ref=exercise_ref,
			sets=3,
			reps="10",
			current_load_kg=Decimal("25.00"),
		)

	def test_student_gets_own_chart_payload(self):
		payload = ProgressService.get_exercise_evolution(self.student)

		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["exercise"], "Remada progresso")
		self.assertEqual(payload[0]["workout"], "Treino progresso")
		self.assertEqual(payload[0]["points"][0]["load"], 25.0)

	def test_trainer_cannot_read_other_trainer_athlete_progress(self):
		with self.assertRaises(PermissionDenied):
			ProgressService.get_exercise_evolution(self.trainer, self.other_athlete)
