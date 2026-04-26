from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from athletes.models import Athlete
from athletes.services import AthleteService
from workouts.models import WorkoutPlan

from .models import ClassSchedule


class ScheduleService:
    @staticmethod
    def require_trainer(user):
        if user is None or not getattr(user, "is_trainer", False):
            raise PermissionDenied("Apenas treinadores podem gerenciar a agenda.")
        return user

    @classmethod
    def _resolve_owned_athlete(cls, trainer, athlete):
        trainer = cls.require_trainer(trainer)
        if isinstance(athlete, Athlete):
            if not athlete.has_active_trainer or athlete.trainer_id != trainer.id:
                raise PermissionDenied("Aluno nao encontrado ou fora do seu escopo.")
            return athlete
        return AthleteService.get_owned_athlete(trainer, athlete)

    @classmethod
    def _resolve_workout_plan(cls, trainer, athlete, workout_plan):
        if not workout_plan:
            return None
        trainer = cls.require_trainer(trainer)
        if isinstance(workout_plan, WorkoutPlan):
            plan = workout_plan
        else:
            plan = WorkoutPlan.objects.filter(pk=workout_plan, created_by=trainer, is_archived=False).first()
            if plan is None:
                raise PermissionDenied("Treino nao encontrado ou fora do seu escopo.")

        if plan.created_by_id != trainer.id or plan.is_archived:
            raise PermissionDenied("Treino nao encontrado ou fora do seu escopo.")
        if not plan.athlete.has_active_trainer or plan.athlete.trainer_id != trainer.id:
            raise PermissionDenied("Treino nao encontrado ou fora do seu escopo.")
        if plan.athlete_id != athlete.pk:
            raise ValidationError("O treino informado nao pertence ao aluno selecionado.")
        return plan

    @staticmethod
    def _normalize_status(status):
        valid_statuses = [choice[0] for choice in ClassSchedule.Status.choices]
        if not status:
            return ClassSchedule.Status.SCHEDULED
        if status not in valid_statuses:
            return ClassSchedule.Status.SCHEDULED
        return status

    @classmethod
    def create_class(
        cls,
        trainer,
        athlete,
        scheduled_at,
        duration_minutes=60,
        workout_plan=None,
        status=ClassSchedule.Status.SCHEDULED,
        notes="",
    ):
        trainer = cls.require_trainer(trainer)
        athlete = cls._resolve_owned_athlete(trainer, athlete)
        workout_plan = cls._resolve_workout_plan(trainer, athlete, workout_plan)
        duration_minutes = max(1, int(duration_minutes or 60))

        with transaction.atomic():
            return ClassSchedule.objects.create(
                trainer=trainer,
                athlete=athlete,
                scheduled_at=scheduled_at,
                duration_minutes=duration_minutes,
                workout_plan=workout_plan,
                status=cls._normalize_status(status),
                notes=(notes or "").strip(),
            )

    @classmethod
    def update_class(cls, trainer, class_obj, **fields):
        trainer = cls.require_trainer(trainer)
        if class_obj.trainer_id != trainer.id:
            raise PermissionDenied("Aula nao encontrada ou fora do seu escopo.")

        athlete = fields.get("athlete", class_obj.athlete)
        athlete = cls._resolve_owned_athlete(trainer, athlete)

        workout_plan_marker = object()
        workout_plan_value = fields.get("workout_plan", workout_plan_marker)
        if workout_plan_value is workout_plan_marker:
            workout_plan = class_obj.workout_plan
        else:
            workout_plan = cls._resolve_workout_plan(trainer, athlete, workout_plan_value)

        if workout_plan is not None and workout_plan.athlete_id != athlete.pk:
            raise ValidationError("O treino vinculado precisa pertencer ao aluno da aula.")

        with transaction.atomic():
            class_obj.athlete = athlete
            if "scheduled_at" in fields:
                class_obj.scheduled_at = fields["scheduled_at"]
            if "duration_minutes" in fields:
                class_obj.duration_minutes = max(1, int(fields["duration_minutes"] or 60))
            if "status" in fields:
                class_obj.status = cls._normalize_status(fields["status"])
            if workout_plan_value is not workout_plan_marker:
                class_obj.workout_plan = workout_plan
            if "notes" in fields:
                class_obj.notes = (fields["notes"] or "").strip()
            class_obj.save()
        return class_obj
