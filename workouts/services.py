from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from athletes.models import Athlete
from athletes.services import AthleteService

from .models import ExercisePrescription, ExerciseProgressLog, LoadUpdate, TrainingPlan, WorkoutPlan, WorkoutSession, WorkoutSetLog


class WorkoutService:
    @staticmethod
    def require_trainer(user):
        if user is None or not getattr(user, "is_trainer", False):
            raise PermissionDenied("Apenas treinadores podem gerenciar treinos.")
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
    def _resolve_owned_plan(cls, trainer, plan, athlete=None):
        if not plan:
            return None
        trainer = cls.require_trainer(trainer)
        if isinstance(plan, TrainingPlan):
            training_plan = plan
        else:
            try:
                training_plan = TrainingPlan.objects.select_related("athlete").get(pk=plan, created_by=trainer)
            except TrainingPlan.DoesNotExist as exc:
                raise PermissionDenied("Plano nao encontrado ou fora do seu escopo.") from exc

        if training_plan.created_by_id != trainer.id:
            raise PermissionDenied("Plano nao encontrado ou fora do seu escopo.")
        if not training_plan.athlete.has_active_trainer or training_plan.athlete.trainer_id != trainer.id:
            raise PermissionDenied("Plano nao encontrado ou fora do seu escopo.")
        if athlete is not None and training_plan.athlete_id != athlete.pk:
            raise ValidationError("O plano informado nao pertence ao aluno selecionado.")
        return training_plan

    @staticmethod
    def student_can_update_workout_loads(user, workout):
        if user is None or not getattr(user, "is_student", False):
            return False
        profile = user.get_athlete_profile()
        if profile is None or workout.athlete_id != profile.id or workout.is_archived:
            return False
        if workout.created_by_id == user.id:
            return True
        return profile.has_active_trainer and profile.allow_student_load_updates

    @classmethod
    def create_training_plan(cls, trainer, athlete, name, objective="", is_active=True):
        trainer = cls.require_trainer(trainer)
        athlete = cls._resolve_owned_athlete(trainer, athlete)
        name = (name or "").strip()
        if not name:
            raise ValidationError("Nome do plano é obrigatório.")

        with transaction.atomic():
            return TrainingPlan.objects.create(
                athlete=athlete,
                name=name,
                objective=(objective or "").strip(),
                is_active=bool(is_active),
                created_by=trainer,
            )

    @classmethod
    def create_workout(cls, trainer, athlete, name, plan=None, objective="", is_active=True):
        trainer = cls.require_trainer(trainer)
        athlete = cls._resolve_owned_athlete(trainer, athlete)
        training_plan = cls._resolve_owned_plan(trainer, plan, athlete=athlete)
        name = (name or "").strip()
        if not name:
            raise ValidationError("Nome do treino é obrigatório.")

        with transaction.atomic():
            return WorkoutPlan.objects.create(
                athlete=athlete,
                plan=training_plan,
                name=name,
                objective=(objective or "").strip(),
                is_active=bool(is_active),
                created_by=trainer,
            )

    @classmethod
    def _resolve_prescription_for_load(cls, user, prescription):
        try:
            if isinstance(prescription, ExercisePrescription):
                prescription = ExercisePrescription.objects.select_related("workout__athlete").get(pk=prescription.pk)
            else:
                prescription = ExercisePrescription.objects.select_related("workout__athlete").get(pk=prescription)
        except ExercisePrescription.DoesNotExist as exc:
            raise PermissionDenied("Prescricao nao encontrada ou fora do seu escopo.") from exc

        if getattr(user, "is_trainer", False):
            athlete = prescription.workout.athlete
            if prescription.workout.created_by_id != user.id or not athlete.has_active_trainer or athlete.trainer_id != user.id:
                raise PermissionDenied("Prescricao nao encontrada ou fora do seu escopo.")
            return prescription

        if getattr(user, "is_student", False):
            profile = user.get_athlete_profile()
            if profile is None or prescription.workout.athlete_id != profile.id or prescription.workout.is_archived:
                raise PermissionDenied("Prescricao nao encontrada ou fora do seu escopo.")
            if not cls.student_can_update_workout_loads(user, prescription.workout):
                raise PermissionDenied("Este treino exige aprovacao do professor para atualizar cargas.")
            return prescription

        raise PermissionDenied("Usuario sem permissao para atualizar cargas.")

    @staticmethod
    def _normalize_load(value):
        try:
            load = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("Informe uma carga valida.") from exc
        if load < 0:
            raise ValidationError("A carga nao pode ser negativa.")
        return load

    @classmethod
    def update_exercise_load(cls, user, prescription, new_load_kg, reason=""):
        load = cls._normalize_load(new_load_kg)
        prescription = cls._resolve_prescription_for_load(user, prescription)
        reason_text = (reason or "Manual update").strip() or "Manual update"

        with transaction.atomic():
            locked = ExercisePrescription.objects.select_for_update().select_related("workout__athlete").get(pk=prescription.pk)
            cls._resolve_prescription_for_load(user, locked)
            previous_load = locked.current_load_kg
            ExercisePrescription.objects.filter(pk=locked.pk).update(current_load_kg=load)
            load_update = LoadUpdate.objects.create(
                exercise=locked,
                previous_load_kg=previous_load,
                new_load_kg=load,
                reason=reason_text,
                updated_by=user,
            )
            ExerciseProgressLog.objects.create(
                exercise=locked,
                sets=locked.sets,
                reps=locked.reps,
                load_kg=load,
                rest_seconds=locked.rest_seconds,
                notes=reason_text,
                updated_by=user,
            )
            locked.current_load_kg = load
        return locked, load_update


class WorkoutExecutionService:
    @staticmethod
    def require_trainer(user):
        return WorkoutService.require_trainer(user)

    @classmethod
    def _resolve_workout(cls, trainer, workout):
        trainer = cls.require_trainer(trainer)
        if isinstance(workout, WorkoutPlan):
            resolved = workout
        else:
            resolved = WorkoutPlan.objects.select_related("athlete").filter(pk=workout, created_by=trainer).first()
            if resolved is None:
                raise PermissionDenied("Treino nao encontrado ou fora do seu escopo.")

        if resolved.created_by_id != trainer.id:
            raise PermissionDenied("Treino nao encontrado ou fora do seu escopo.")
        if not resolved.athlete.has_active_trainer or resolved.athlete.trainer_id != trainer.id:
            raise PermissionDenied("Treino nao encontrado ou fora do seu escopo.")
        if resolved.is_archived:
            raise ValidationError("Nao e possivel executar um treino arquivado.")
        return resolved

    @classmethod
    def _resolve_session(cls, trainer, session):
        trainer = cls.require_trainer(trainer)
        if isinstance(session, WorkoutSession):
            resolved = WorkoutSession.objects.select_related("workout", "athlete").get(pk=session.pk)
        else:
            resolved = WorkoutSession.objects.select_related("workout", "athlete").filter(pk=session, trainer=trainer).first()
            if resolved is None:
                raise PermissionDenied("Sessao nao encontrada ou fora do seu escopo.")

        if resolved.trainer_id != trainer.id:
            raise PermissionDenied("Sessao nao encontrada ou fora do seu escopo.")
        if not resolved.athlete.has_active_trainer or resolved.athlete.trainer_id != trainer.id:
            raise PermissionDenied("Sessao nao encontrada ou fora do seu escopo.")
        return resolved

    @classmethod
    def get_active_session(cls, trainer, workout):
        workout = cls._resolve_workout(trainer, workout)
        return (
            WorkoutSession.objects.filter(
                workout=workout,
                trainer=trainer,
                status=WorkoutSession.Status.IN_PROGRESS,
            )
            .select_related("workout", "athlete")
            .order_by("-started_at")
            .first()
        )

    @classmethod
    def start_session(cls, trainer, workout):
        trainer = cls.require_trainer(trainer)
        workout = cls._resolve_workout(trainer, workout)
        with transaction.atomic():
            existing = cls.get_active_session(trainer, workout)
            if existing is not None:
                return existing
            return WorkoutSession.objects.create(
                workout=workout,
                athlete=workout.athlete,
                trainer=trainer,
            )

    @classmethod
    def log_set(cls, trainer, session, exercise, actual_reps, load_kg=None, rpe=None, rir=None, notes=""):
        trainer = cls.require_trainer(trainer)
        session = cls._resolve_session(trainer, session)
        if session.status != WorkoutSession.Status.IN_PROGRESS:
            raise ValidationError("A sessao precisa estar em andamento para registrar series.")

        if isinstance(exercise, ExercisePrescription):
            prescription = exercise
        else:
            prescription = ExercisePrescription.objects.select_related("workout").filter(pk=exercise).first()
            if prescription is None:
                raise PermissionDenied("Exercicio nao encontrado ou fora do seu escopo.")

        if prescription.workout_id != session.workout_id or prescription.workout.created_by_id != trainer.id:
            raise PermissionDenied("Exercicio nao encontrado ou fora do seu escopo.")

        with transaction.atomic():
            set_number = (WorkoutSetLog.objects.filter(session=session, exercise=prescription).aggregate(max_set=Max("set_number"))["max_set"] or 0) + 1
            set_log = WorkoutSetLog.objects.create(
                session=session,
                exercise=prescription,
                set_number=set_number,
                target_reps=prescription.reps,
                actual_reps=actual_reps,
                load_kg=load_kg,
                rpe=rpe,
                rir=rir,
                notes=(notes or "").strip(),
            )
            if set_log.load_kg is not None and prescription.current_load_kg != set_log.load_kg:
                WorkoutService.update_exercise_load(
                    trainer,
                    prescription,
                    set_log.load_kg,
                    reason=f"Execucao da sessao #{session.pk}",
                )
        return set_log

    @classmethod
    def finish_session(cls, trainer, session, notes=""):
        session = cls._resolve_session(trainer, session)
        if session.status != WorkoutSession.Status.IN_PROGRESS:
            return session
        with transaction.atomic():
            session.status = WorkoutSession.Status.COMPLETED
            session.completed_at = timezone.now()
            if notes:
                session.notes = notes.strip()
            session.save()
        return session
