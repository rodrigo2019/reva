from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole
from athletes.models import Athlete, StudentRelationshipStatus

from .models import Exercise, ExercisePrescription, ExerciseProgressLog, LoadUpdate, TrainingPlan, WorkoutPlan, WorkoutSession, WorkoutSetLog
from .services import WorkoutExecutionService, WorkoutService


class StudentWorkoutAccessTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="coach-workout",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student = User.objects.create_user(
			username="student-workout",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.athlete = Athlete.objects.create(user=self.student, trainer=self.trainer)
		self.workout = WorkoutPlan.objects.create(
			athlete=self.athlete,
			name="Treino A",
			objective="Hipertrofia",
			created_by=self.trainer,
		)
		self.exercise_ref = Exercise.objects.create(name="Agachamento", is_global=True)
		self.exercise = ExercisePrescription.objects.create(
			workout=self.workout,
			exercise_ref=self.exercise_ref,
			sets=4,
			reps="6-8",
			current_load_kg=Decimal("40.00"),
			rest_seconds=120,
		)
		self.client.force_login(self.student)

	def test_student_can_view_own_workouts(self):
		response = self.client.get(reverse("student-workout-list"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Treino A")
		self.assertContains(response, "Agachamento")

	def test_student_cannot_update_load_without_permission(self):
		response = self.client.post(
			reverse("student-exercise-load-update", args=[self.workout.pk, self.exercise.pk]),
			{"new_load_kg": "44", "reason": "Treino leve"},
		)

		self.assertRedirects(response, reverse("student-workout-detail", args=[self.workout.pk]))
		self.exercise.refresh_from_db()
		self.assertEqual(self.exercise.current_load_kg, Decimal("40.00"))

	def test_student_can_update_load_when_trainer_allows(self):
		self.athlete.allow_student_load_updates = True
		self.athlete.save(update_fields=["allow_student_load_updates"])

		response = self.client.post(
			reverse("student-exercise-load-update", args=[self.workout.pk, self.exercise.pk]),
			{"new_load_kg": "44", "reason": "Execução estável"},
		)

		self.assertRedirects(response, reverse("student-workout-detail", args=[self.workout.pk]))
		self.exercise.refresh_from_db()
		self.assertEqual(self.exercise.current_load_kg, Decimal("44.00"))
		self.assertTrue(
			LoadUpdate.objects.filter(
				exercise=self.exercise,
				new_load_kg=Decimal("44.00"),
				updated_by=self.student,
			).exists()
		)

	def test_independent_student_can_update_own_workout_load(self):
		independent_user = User.objects.create_user(
			username="independent-workout-student",
			password="secret123",
			role=UserRole.STUDENT,
		)
		independent_profile = Athlete.objects.create(user=independent_user)
		independent_workout = WorkoutPlan.objects.create(
			athlete=independent_profile,
			name="Treino livre",
			created_by=independent_user,
		)
		independent_exercise = ExercisePrescription.objects.create(
			workout=independent_workout,
			name="Flexao",
			sets=3,
			reps="10",
			current_load_kg=Decimal("0.00"),
		)
		self.client.force_login(independent_user)

		response = self.client.post(
			reverse("student-exercise-load-update", args=[independent_workout.pk, independent_exercise.pk]),
			{"new_load_kg": "5", "reason": "Mochila"},
		)

		self.assertRedirects(response, reverse("student-workout-detail", args=[independent_workout.pk]))
		independent_exercise.refresh_from_db()
		self.assertEqual(independent_exercise.current_load_kg, Decimal("5.00"))
		self.assertTrue(
			LoadUpdate.objects.filter(
				exercise=independent_exercise,
				new_load_kg=Decimal("5.00"),
				updated_by=independent_user,
			).exists()
		)

	def test_student_cannot_update_trainer_prescribed_load_after_relationship_ends(self):
		self.athlete.allow_student_load_updates = True
		self.athlete.trainer = None
		self.athlete.relationship_status = StudentRelationshipStatus.ENDED
		self.athlete.save(update_fields=["allow_student_load_updates", "trainer", "relationship_status"])

		response = self.client.post(
			reverse("student-exercise-load-update", args=[self.workout.pk, self.exercise.pk]),
			{"new_load_kg": "44", "reason": "Vinculo encerrado"},
		)

		self.assertRedirects(response, reverse("student-workout-detail", args=[self.workout.pk]))
		self.exercise.refresh_from_db()
		self.assertEqual(self.exercise.current_load_kg, Decimal("40.00"))


class WorkoutDomainIsolationTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="domain-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student_one = User.objects.create_user(
			username="domain-student-one",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.student_two = User.objects.create_user(
			username="domain-student-two",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.athlete_one = Athlete.objects.create(user=self.student_one, trainer=self.trainer)
		self.athlete_two = Athlete.objects.create(user=self.student_two, trainer=self.trainer)
		self.plan_one = TrainingPlan.objects.create(
			athlete=self.athlete_one,
			name="Plano A",
			created_by=self.trainer,
		)
		self.plan_two = TrainingPlan.objects.create(
			athlete=self.athlete_two,
			name="Plano B",
			created_by=self.trainer,
		)
		self.workout = WorkoutPlan.objects.create(
			athlete=self.athlete_one,
			name="Treino isolado",
			created_by=self.trainer,
		)
		self.client.force_login(self.trainer)

	def test_workout_model_rejects_plan_from_different_athlete(self):
		with self.assertRaises(ValidationError):
			WorkoutPlan.objects.create(
				athlete=self.athlete_one,
				plan=self.plan_two,
				name="Treino inconsistente",
				created_by=self.trainer,
			)

	def test_workout_edit_syncs_athlete_when_plan_is_selected(self):
		response = self.client.post(
			reverse("workout-edit", args=[self.workout.pk]),
			{
				"plan": str(self.plan_two.pk),
				"athlete": str(self.athlete_one.pk),
				"name": "Treino movido para plano",
				"objective": "Ajuste de domínio",
				"is_active": "on",
			},
		)

		self.assertRedirects(response, reverse("workout-detail", args=[self.workout.pk]))
		self.workout.refresh_from_db()
		self.assertEqual(self.workout.plan, self.plan_two)
		self.assertEqual(self.workout.athlete, self.athlete_two)


class WorkoutServiceTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="workout-service-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.other_trainer = User.objects.create_user(
			username="workout-service-other-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student_one = User.objects.create_user(
			username="workout-service-student-one",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.student_two = User.objects.create_user(
			username="workout-service-student-two",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.athlete_one = Athlete.objects.create(user=self.student_one, trainer=self.trainer)
		self.athlete_two = Athlete.objects.create(user=self.student_two, trainer=self.trainer)
		self.plan_two = TrainingPlan.objects.create(
			athlete=self.athlete_two,
			name="Plano aluno dois",
			created_by=self.trainer,
		)
		self.workout = WorkoutPlan.objects.create(
			athlete=self.athlete_one,
			name="Treino service",
			created_by=self.trainer,
		)
		self.exercise_ref = Exercise.objects.create(name="Supino service", is_global=True)
		self.exercise = ExercisePrescription.objects.create(
			workout=self.workout,
			exercise_ref=self.exercise_ref,
			sets=3,
			reps="8-10",
			current_load_kg=Decimal("30.00"),
		)

	def test_create_training_plan_rejects_athlete_from_other_trainer(self):
		with self.assertRaises(PermissionDenied):
			WorkoutService.create_training_plan(
				self.other_trainer,
				self.athlete_one,
				"Plano fora do escopo",
			)

	def test_create_workout_rejects_plan_from_different_athlete(self):
		with self.assertRaises(ValidationError):
			WorkoutService.create_workout(
				self.trainer,
				self.athlete_one,
				"Treino inconsistente",
				plan=self.plan_two,
			)

	def test_update_exercise_load_records_auditable_change_once(self):
		load_update_count = LoadUpdate.objects.filter(exercise=self.exercise).count()
		progress_log_count = ExerciseProgressLog.objects.filter(exercise=self.exercise).count()

		updated, load_update = WorkoutService.update_exercise_load(
			self.trainer,
			self.exercise,
			Decimal("36.50"),
			reason="Progressao planejada",
		)

		self.assertEqual(updated.current_load_kg, Decimal("36.50"))
		self.assertEqual(load_update.previous_load_kg, Decimal("30.00"))
		self.assertEqual(load_update.updated_by, self.trainer)
		self.assertEqual(LoadUpdate.objects.filter(exercise=self.exercise).count(), load_update_count + 1)
		self.assertEqual(ExerciseProgressLog.objects.filter(exercise=self.exercise).count(), progress_log_count + 1)


class WorkoutExecutionServiceTests(TestCase):
	def setUp(self):
		self.trainer = User.objects.create_user(
			username="execution-coach",
			password="secret123",
			role=UserRole.TRAINER,
		)
		self.student = User.objects.create_user(
			username="execution-student",
			password="secret123",
			role=UserRole.STUDENT,
		)
		self.athlete = Athlete.objects.create(user=self.student, trainer=self.trainer)
		self.workout = WorkoutPlan.objects.create(
			athlete=self.athlete,
			name="Treino execucao",
			created_by=self.trainer,
		)
		self.exercise_ref = Exercise.objects.create(name="Levantamento terra", is_global=True)
		self.exercise = ExercisePrescription.objects.create(
			workout=self.workout,
			exercise_ref=self.exercise_ref,
			sets=3,
			reps="5",
			current_load_kg=Decimal("80.00"),
		)

	def test_start_session_reuses_active_session(self):
		first = WorkoutExecutionService.start_session(self.trainer, self.workout)
		second = WorkoutExecutionService.start_session(self.trainer, self.workout)

		self.assertEqual(first.pk, second.pk)
		self.assertEqual(first.status, WorkoutSession.Status.IN_PROGRESS)
		self.assertEqual(WorkoutSession.objects.count(), 1)

	def test_log_set_records_rpe_rir_and_updates_current_load(self):
		session = WorkoutExecutionService.start_session(self.trainer, self.workout)

		set_log = WorkoutExecutionService.log_set(
			self.trainer,
			session,
			self.exercise,
			actual_reps=5,
			load_kg=Decimal("82.50"),
			rpe=Decimal("8.5"),
			rir=Decimal("1.5"),
			notes="Bar speed stable",
		)

		self.assertEqual(set_log.set_number, 1)
		self.assertEqual(set_log.target_reps, "5")
		self.assertEqual(set_log.rpe, Decimal("8.5"))
		self.assertEqual(set_log.rir, Decimal("1.5"))
		self.exercise.refresh_from_db()
		self.assertEqual(self.exercise.current_load_kg, Decimal("82.50"))
		self.assertTrue(
			LoadUpdate.objects.filter(
				exercise=self.exercise,
				new_load_kg=Decimal("82.50"),
				updated_by=self.trainer,
			).exists()
		)

	def test_log_set_rejects_exercise_from_other_workout(self):
		other_workout = WorkoutPlan.objects.create(
			athlete=self.athlete,
			name="Outro treino",
			created_by=self.trainer,
		)
		other_exercise = ExercisePrescription.objects.create(
			workout=other_workout,
			name="Exercicio fora",
			sets=3,
			reps="10",
		)
		session = WorkoutExecutionService.start_session(self.trainer, self.workout)

		with self.assertRaises(PermissionDenied):
			WorkoutExecutionService.log_set(
				self.trainer,
				session,
				other_exercise,
				actual_reps=10,
			)

	def test_finish_session_marks_completion_time(self):
		session = WorkoutExecutionService.start_session(self.trainer, self.workout)

		finished = WorkoutExecutionService.finish_session(self.trainer, session, notes="Good session")

		self.assertEqual(finished.status, WorkoutSession.Status.COMPLETED)
		self.assertIsNotNone(finished.completed_at)
		self.assertEqual(finished.notes, "Good session")

	def test_trainer_session_view_flow_logs_and_finishes(self):
		self.client.force_login(self.trainer)

		response = self.client.get(reverse("workout-session", args=[self.workout.pk]))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "No live session")

		response = self.client.post(reverse("workout-session-start", args=[self.workout.pk]))
		self.assertRedirects(response, reverse("workout-session", args=[self.workout.pk]))
		session = WorkoutSession.objects.get(workout=self.workout)
		response = self.client.get(reverse("workout-session", args=[self.workout.pk]))
		self.assertContains(response, "Log set")

		response = self.client.post(
			reverse("workout-session-set-log", args=[self.workout.pk, session.pk, self.exercise.pk]),
			{"actual_reps": "5", "load_kg": "85", "rpe": "9", "rir": "1", "notes": "Top set"},
		)
		self.assertRedirects(response, reverse("workout-session", args=[self.workout.pk]))
		self.assertTrue(WorkoutSetLog.objects.filter(session=session, exercise=self.exercise, actual_reps=5).exists())

		response = self.client.post(
			reverse("workout-session-finish", args=[self.workout.pk, session.pk]),
			{"notes": "Completed from view"},
		)
		self.assertRedirects(response, reverse("workout-detail", args=[self.workout.pk]))
		session.refresh_from_db()
		self.assertEqual(session.status, WorkoutSession.Status.COMPLETED)
