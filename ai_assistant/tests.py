import json
from contextvars import copy_context
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from ai_assistant.core.tools import add_exercise_to_workout, create_athlete, create_training_plan, create_workout, delete_athlete, delete_class, delete_workout, get_workout_detail, list_athletes, list_schedule, list_workouts, set_tools_context, update_class
from ai_assistant.models import AssistantAction, AssistantSession
from athletes.models import Athlete, StudentRelationshipStatus
from schedule.models import ClassSchedule
from workouts.models import TrainingPlan, WorkoutPlan


class AIAssistantToolContextTests(TestCase):
    def setUp(self):
        self.trainer_one = User.objects.create_user(
            username="coach-one",
            password="secret123",
            role=UserRole.TRAINER,
        )
        self.trainer_two = User.objects.create_user(
            username="coach-two",
            password="secret123",
            role=UserRole.TRAINER,
        )
        self.student_one = User.objects.create_user(
            username="student-one",
            password="secret123",
            first_name="Ana",
            last_name="Silva",
            email="ana@example.com",
            role=UserRole.STUDENT,
        )
        self.student_two = User.objects.create_user(
            username="student-two",
            password="secret123",
            first_name="Bruno",
            last_name="Costa",
            email="bruno@example.com",
            role=UserRole.STUDENT,
        )
        self.unlinked_student = User.objects.create_user(
            username="unlinked-student",
            password="secret123",
            first_name="Carla",
            last_name="Moura",
            email="carla@example.com",
            role=UserRole.STUDENT,
        )
        Athlete.objects.create(user=self.student_one, trainer=self.trainer_one)
        Athlete.objects.create(user=self.student_two, trainer=self.trainer_two)

    def _list_athlete_names(self):
        payload = list_athletes.invoke({"search": "", "limit": 20})
        return [athlete["name"] for athlete in json.loads(payload)]

    def _end_relationship(self, athlete):
        athlete.trainer = None
        athlete.relationship_status = StudentRelationshipStatus.ENDED
        athlete.save(update_fields=["trainer", "relationship_status"])
        return athlete

    def test_tool_context_is_isolated_between_execution_contexts(self):
        def configure_and_list(user_id):
            tools = set_tools_context(user_id)
            self.assertIn(list_athletes, tools)
            return self._list_athlete_names()

        trainer_one_context = copy_context()
        trainer_two_context = copy_context()

        trainer_one_names = trainer_one_context.run(configure_and_list, self.trainer_one.pk)
        trainer_two_names = trainer_two_context.run(configure_and_list, self.trainer_two.pk)
        trainer_one_names_again = trainer_one_context.run(self._list_athlete_names)

        self.assertEqual(trainer_one_names, ["Ana Silva"])
        self.assertEqual(trainer_two_names, ["Bruno Costa"])
        self.assertEqual(trainer_one_names_again, ["Ana Silva"])

    def test_student_context_does_not_expose_operational_tools(self):
        tools = set_tools_context(self.unlinked_student.pk)

        self.assertEqual(tools, [])
        with self.assertRaises(PermissionError):
            self._list_athlete_names()

    def test_create_athlete_links_existing_student_account(self):
        set_tools_context(self.trainer_one.pk)
        user_count = User.objects.count()

        payload = create_athlete.invoke({
            "first_name": "Carla",
            "last_name": "Moura",
            "email": "CARLA@example.com",
            "notes": "Onboarding por e-mail",
        })
        data = json.loads(payload)

        self.assertTrue(data["success"])
        self.assertEqual(User.objects.count(), user_count)
        athlete = Athlete.objects.get(user=self.unlinked_student)
        self.assertEqual(athlete.trainer, self.trainer_one)
        self.assertEqual(athlete.notes, "Onboarding por e-mail")

    def test_create_athlete_rejects_missing_student_account(self):
        set_tools_context(self.trainer_one.pk)
        user_count = User.objects.count()

        payload = create_athlete.invoke({
            "first_name": "Nova",
            "last_name": "Pessoa",
            "email": "missing@example.com",
        })
        data = json.loads(payload)

        self.assertIn("error", data)
        self.assertEqual(User.objects.count(), user_count)
        self.assertFalse(Athlete.objects.filter(user__email="missing@example.com").exists())

    def test_create_training_plan_tool_creates_scoped_plan(self):
        set_tools_context(self.trainer_one.pk)
        athlete = Athlete.objects.get(user=self.student_one)

        payload = create_training_plan.invoke({
            "athlete_id": athlete.pk,
            "name": "Plano service IA",
            "objective": "Forca",
            "is_active": True,
        })
        data = json.loads(payload)

        self.assertTrue(data["success"])
        plan = TrainingPlan.objects.get(pk=data["id"])
        self.assertEqual(plan.created_by, self.trainer_one)
        self.assertEqual(plan.athlete, athlete)

    def test_create_workout_tool_has_valid_payload_and_creates_workout(self):
        set_tools_context(self.trainer_one.pk)
        athlete = Athlete.objects.get(user=self.student_one)

        payload = create_workout.invoke({
            "athlete_id": athlete.pk,
            "name": "Treino IA",
            "objective": "Hipertrofia",
            "is_active": True,
        })
        data = json.loads(payload)

        self.assertTrue(data["success"])
        workout = WorkoutPlan.objects.get(pk=data["id"])
        self.assertEqual(workout.created_by, self.trainer_one)
        self.assertEqual(workout.athlete, athlete)

    def test_list_workouts_excludes_students_without_active_relationship(self):
        set_tools_context(self.trainer_one.pk)
        active_athlete = Athlete.objects.get(user=self.student_one)
        active_workout = WorkoutPlan.objects.create(
            athlete=active_athlete,
            name="Treino ativo",
            created_by=self.trainer_one,
        )
        ended_user = User.objects.create_user(
            username="ended-student",
            password="secret123",
            first_name="Davi",
            last_name="Finalizado",
            email="davi@example.com",
            role=UserRole.STUDENT,
        )
        ended_athlete = Athlete.objects.create(user=ended_user, trainer=self.trainer_one)
        WorkoutPlan.objects.create(
            athlete=ended_athlete,
            name="Treino encerrado",
            created_by=self.trainer_one,
        )
        ended_athlete.trainer = None
        ended_athlete.relationship_status = StudentRelationshipStatus.ENDED
        ended_athlete.save(update_fields=["trainer", "relationship_status"])

        payload = list_workouts.invoke({"athlete_id": 0, "plan_id": 0, "only_active": True, "limit": 20})
        names = [item["name"] for item in json.loads(payload)]

        self.assertIn(active_workout.name, names)
        self.assertNotIn("Treino encerrado", names)

    def test_delete_athlete_tool_ends_relationship_without_deleting_student(self):
        set_tools_context(self.trainer_one.pk)
        athlete = Athlete.objects.get(user=self.student_one)
        student_id = self.student_one.pk

        payload = delete_athlete.invoke({"athlete_id": athlete.pk})
        data = json.loads(payload)

        self.assertTrue(data["success"])
        athlete.refresh_from_db()
        self.assertIsNone(athlete.trainer)
        self.assertEqual(athlete.relationship_status, StudentRelationshipStatus.ENDED)
        self.assertTrue(User.objects.filter(pk=student_id).exists())

    def test_workout_tools_reject_students_without_active_relationship(self):
        set_tools_context(self.trainer_one.pk)
        ended_user = User.objects.create_user(
            username="ended-workout-student",
            password="secret123",
            first_name="Eva",
            last_name="Encerrada",
            email="eva@example.com",
            role=UserRole.STUDENT,
        )
        ended_athlete = Athlete.objects.create(user=ended_user, trainer=self.trainer_one)
        workout = WorkoutPlan.objects.create(
            athlete=ended_athlete,
            name="Treino fora de escopo",
            created_by=self.trainer_one,
        )
        self._end_relationship(ended_athlete)

        add_payload = add_exercise_to_workout.invoke({"workout_id": workout.pk, "custom_name": "Agachamento"})
        detail_payload = get_workout_detail.invoke({"workout_id": workout.pk})
        delete_payload = delete_workout.invoke({"workout_id": workout.pk})

        self.assertIn("error", json.loads(add_payload))
        self.assertIn("error", json.loads(detail_payload))
        self.assertIn("error", json.loads(delete_payload))
        self.assertTrue(WorkoutPlan.objects.filter(pk=workout.pk).exists())

    def test_schedule_tools_reject_students_without_active_relationship(self):
        set_tools_context(self.trainer_one.pk)
        ended_user = User.objects.create_user(
            username="ended-schedule-student",
            password="secret123",
            first_name="Felipe",
            last_name="Encerrado",
            email="felipe@example.com",
            role=UserRole.STUDENT,
        )
        ended_athlete = Athlete.objects.create(user=ended_user, trainer=self.trainer_one)
        scheduled_at = timezone.now() + timedelta(days=1)
        class_schedule = ClassSchedule.objects.create(
            trainer=self.trainer_one,
            athlete=ended_athlete,
            scheduled_at=scheduled_at,
            duration_minutes=60,
        )
        self._end_relationship(ended_athlete)
        monday = (scheduled_at.date() - timedelta(days=scheduled_at.weekday())).isoformat()

        list_payload = list_schedule.invoke({"week_start": monday, "athlete_id": 0, "limit": 50})
        update_payload = update_class.invoke({"class_id": class_schedule.pk, "status": "completed"})
        delete_payload = delete_class.invoke({"class_id": class_schedule.pk})

        self.assertEqual(json.loads(list_payload)["total"], 0)
        self.assertIn("error", json.loads(update_payload))
        self.assertIn("error", json.loads(delete_payload))
        self.assertTrue(ClassSchedule.objects.filter(pk=class_schedule.pk).exists())

    def test_successful_tool_execution_records_assistant_action(self):
        session = AssistantSession.objects.create(user=self.trainer_one, screen_context="workout-detail")
        set_tools_context(self.trainer_one.pk, session_id=session.pk, screen_context="workout-detail")
        athlete = Athlete.objects.get(user=self.student_one)

        payload = create_training_plan.invoke({
            "athlete_id": athlete.pk,
            "name": "Plano auditado",
            "objective": "Auditoria IA",
            "is_active": True,
        })
        data = json.loads(payload)

        action = AssistantAction.objects.get(action_type="create_training_plan", entity_id=str(data["id"]))
        self.assertEqual(action.user, self.trainer_one)
        self.assertEqual(action.session, session)
        self.assertEqual(action.status, AssistantAction.StatusChoices.EXECUTED)
        self.assertEqual(action.source, AssistantAction.SourceChoices.TOOL)
        self.assertEqual(action.screen_id, "workout-detail")
        self.assertEqual(action.entity_type, "training_plan")
        self.assertEqual(action.payload["athlete_id"], athlete.pk)

    def test_failed_tool_execution_records_failed_assistant_action(self):
        session = AssistantSession.objects.create(user=self.trainer_one, screen_context="workout-detail")
        set_tools_context(self.trainer_one.pk, session_id=session.pk, screen_context="workout-detail")

        payload = create_training_plan.invoke({
            "athlete_id": 999999,
            "name": "Plano impossivel",
        })
        data = json.loads(payload)

        self.assertIn("error", data)
        action = AssistantAction.objects.get(action_type="create_training_plan")
        self.assertEqual(action.status, AssistantAction.StatusChoices.FAILED)
        self.assertEqual(action.session, session)
        self.assertTrue(action.error)

    def test_action_endpoint_records_client_action_for_review(self):
        self.client.force_login(self.trainer_one)

        response = self.client.post(
            reverse("assistant-action"),
            data=json.dumps({
                "action_type": "fill_form",
                "params": {"label": "Fill student form"},
                "screen_id": "student-detail",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], AssistantAction.StatusChoices.PROPOSED)
        action = AssistantAction.objects.get(pk=data["action_id"])
        self.assertEqual(action.user, self.trainer_one)
        self.assertEqual(action.source, AssistantAction.SourceChoices.UI)
        self.assertEqual(action.screen_id, "student-detail")
        self.assertEqual(action.payload["label"], "Fill student form")

    def test_context_endpoint_returns_recent_actions(self):
        self.client.force_login(self.trainer_one)
        AssistantAction.objects.create(
            user=self.trainer_one,
            action_type="create_workout",
            label="Create workout",
            status=AssistantAction.StatusChoices.EXECUTED,
        )

        response = self.client.get(reverse("assistant-context"), {"screen_id": "workout-detail"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["recent_actions"][0]["type"], "create_workout")
        self.assertEqual(data["recent_actions"][0]["status"], AssistantAction.StatusChoices.EXECUTED)
