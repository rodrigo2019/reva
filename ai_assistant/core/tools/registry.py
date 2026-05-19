"""
REVA AI Assistant — Django ORM Tools.

Provides LangChain-compatible tools that the assistant can call to
create, read, update, and delete records through the Django ORM.

Security notes:
- All queries go through the Django ORM (never raw SQL).
- Write operations are scoped to the current trainer's data.
- Passwords are never exposed; student onboarding links existing student accounts by email.
"""

import json
import logging
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from datetime import date as date_type
from decimal import Decimal
from typing import Any

from accounts.models import User
from ai_assistant.models import AssistantAction
from ai_assistant.services import AssistantActionService, safe_record_tool_execution
from athletes.models import Anamnesis, Athlete, PhysicalAssessment, StudentRelationshipStatus
from athletes.services import AthleteService
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils import timezone
from .base import DjangoOrmTool
from schedule.models import ClassSchedule, PersonalEvent
from schedule.services import PersonalEventService, ScheduleService
from workouts.models import (
    Exercise,
    ExerciseAlternative,
    ExercisePrescription,
    LoadUpdate,
    PlanOrigin,
    TrainingPlan,
    WorkoutPlan,
    WorkoutSession,
    WorkoutSetLog,
)
from workouts.services import WorkoutExecutionService, WorkoutService

logger = logging.getLogger("ai_assistant")

_TOOL_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "reva_assistant_tool_context",
    default=None,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_instance(obj, fields: list[str] | None = None) -> dict[str, Any]:
    """Serialize a Django model instance to a dict.

    Args:
        obj: A Django model instance.
        fields: Optional list of field names to include. If None, all fields are included.

    Returns:
        JSON-safe dict representation.
    """
    data = model_to_dict(obj, fields=fields) if fields else model_to_dict(obj)

    # Convert non-serializable values
    for k, v in list(data.items()):
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()
        elif hasattr(v, "pk"):
            data[k] = v.pk
    return data


def _get_tool_context() -> dict[str, Any]:
    return _TOOL_CONTEXT.get() or {}


def _get_user_from_context(context: dict) -> Any:
    """Retrieve the authenticated User object from the tool context."""

    user_id = context.get("user_id")
    if not user_id:
        raise ValueError("Contexto de usuário ausente.")
    return User.objects.get(pk=user_id)


def _get_trainer_from_context(context: dict) -> Any:
    """Retrieve the trainer User object from the tool context.

    The context must contain user_id set by the orchestrator.
    """
    user_id = context.get("user_id")
    if not user_id:
        raise ValueError("Contexto de usuário ausente — não é possível identificar o treinador.")
    user = User.objects.get(pk=user_id)
    if not getattr(user, "is_trainer", False):
        raise PermissionError("As ferramentas operacionais da REVA estão disponíveis apenas para treinadores.")
    return user


def _get_student_profile_from_context(context: dict) -> Any:
    """Retrieve the current student's Athlete profile from the tool context."""
    user = _get_user_from_context(context)
    if not getattr(user, "is_student", False):
        raise PermissionError("Esta ferramenta está disponível apenas para alunos.")
    profile = user.get_athlete_profile()
    if profile is None:
        raise ValueError("Perfil de aluno indisponível.")
    return user, profile


def _active_athletes_for_trainer(trainer):
    return Athlete.objects.filter(
        trainer=trainer,
        relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _active_training_plans_for_trainer(trainer):
    return TrainingPlan.objects.filter(
        created_by=trainer,
        athlete__trainer=trainer,
        athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _active_workouts_for_trainer(trainer):
    return WorkoutPlan.objects.filter(
        created_by=trainer,
        athlete__trainer=trainer,
        athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _active_classes_for_trainer(trainer):
    return ClassSchedule.objects.filter(
        trainer=trainer,
        athlete__trainer=trainer,
        athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _exception_message(exc: Exception) -> str:
    messages = getattr(exc, "messages", None)
    if messages:
        return messages[0]
    return str(exc)


def _parse_json_payload(value: Any, default: Any = None) -> Any:
    """Parse a JSON tool argument while accepting already-decoded values."""
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return default


def _tool_proposed_response(
    tool_name: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    *,
    entity_type: str = "",
    entity_id: Any = "",
) -> str:
    context = _get_tool_context()
    user = User.objects.filter(pk=context.get("user_id")).first()
    if user is not None:
        session = AssistantActionService._resolve_session(user, context.get("session_id"))
        AssistantActionService.create_action(
            user=user,
            session=session,
            action_type=tool_name,
            source=AssistantAction.SourceChoices.TOOL,
            status=AssistantAction.StatusChoices.PROPOSED,
            screen_id=context.get("screen_context", ""),
            payload=payload,
            result=result,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    return json.dumps(result, ensure_ascii=False)


def _tool_json_response(
    tool_name: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    *,
    entity_type: str = "",
    entity_id: Any = "",
) -> str:
    safe_record_tool_execution(
        context=_get_tool_context(),
        tool_name=tool_name,
        payload=payload,
        result=result,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: List athletes
# ---------------------------------------------------------------------------

def list_athletes(
    search: str = "",
    limit: int = 20,
) -> str:
    """Lista os alunos do treinador atual.

    Use para consultar quais alunos existem, buscar por nome, ou verificar informações.

    Args:
        search: Texto para filtrar por nome (opcional).
        limit: Número máximo de resultados (padrão 20).

    Returns:
        Lista JSON dos alunos com id, nome, email, notas e data de criação.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    qs = _active_athletes_for_trainer(trainer).select_related("user")
    if search:
        # Support multi-word search: each word must match at least one name field
        words = search.strip().split()
        for word in words:
            qs = qs.filter(
                Q(user__first_name__icontains=word)
                | Q(user__last_name__icontains=word)
                | Q(user__username__icontains=word)
            )
        qs = qs.distinct()

    athletes = []
    for a in qs[:limit]:
        athletes.append({
            "id": a.pk,
            "user_id": a.user_id,
            "name": a.user.get_full_name() or a.user.username,
            "email": a.user.email,
            "username": a.user.username,
            "notes": a.notes,
            "created_at": a.created_at.isoformat(),
        })

    return json.dumps(athletes, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Create athlete (student)
# ---------------------------------------------------------------------------

def create_athlete(
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    notes: str = "",
) -> str:
    """Vincula uma conta de aluno existente ao treinador atual.

    O aluno precisa já ter uma conta de estudante cadastrada na plataforma.
    A ferramenta não cria usuário nem define senha.

    Args:
        first_name: Nome informado pelo treinador, usado apenas como referência.
        last_name: Sobrenome informado pelo treinador, usado apenas como referência.
        email: E-mail da conta de aluno existente (obrigatório).
        notes: Observações sobre o aluno (opcional).

    Returns:
        JSON com os dados do aluno vinculado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"first_name": first_name, "last_name": last_name, "email": email, "notes": notes}

    email = email.strip()
    if not email:
        return _tool_json_response(
            "create_athlete",
            payload,
            {"error": "Informe o e-mail da conta de aluno já cadastrada."},
            entity_type="athlete",
        )

    try:
        athlete = AthleteService.link_existing_student(
            trainer,
            email,
            notes=notes,
            allow_existing_for_trainer=True,
        )
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response(
            "create_athlete",
            payload,
            {"error": _exception_message(exc)},
            entity_type="athlete",
        )

    user = athlete.user

    display_name = user.get_full_name() or " ".join(part.strip() for part in [first_name, last_name] if part.strip()) or user.username
    logger.info("Tool create_athlete: linked athlete %s (id=%d) for trainer %s", display_name, athlete.pk, trainer.username)

    result = {
        "success": True,
        "id": athlete.pk,
        "user_id": user.pk,
        "name": display_name,
        "username": user.username,
        "email": user.email,
        "notes": athlete.notes,
        "message": f"Aluno '{display_name}' vinculado com sucesso!",
    }
    return _tool_json_response("create_athlete", payload, result, entity_type="athlete", entity_id=athlete.pk)


# ---------------------------------------------------------------------------
# TOOL: Update athlete
# ---------------------------------------------------------------------------

def update_athlete(
    athlete_id: int,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    notes: str = "",
) -> str:
    """Atualiza os dados de um aluno existente.

    Somente os campos fornecidos (não vazios) serão atualizados.

    Args:
        athlete_id: ID do aluno a atualizar (obrigatório).
        first_name: Novo primeiro nome (opcional).
        last_name: Novo sobrenome (opcional).
        email: Novo e-mail (opcional).
        notes: Novas observações (opcional).

    Returns:
        JSON com os dados atualizados do aluno.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = _active_athletes_for_trainer(trainer).select_related("user").get(pk=athlete_id)
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    user = athlete.user
    if first_name:
        user.first_name = first_name.strip()
    if last_name:
        user.last_name = last_name.strip()
    if email:
        user.email = email.strip()
    user.save()

    if notes:
        athlete.notes = notes.strip()
        athlete.save()

    logger.info("Tool update_athlete: updated athlete %d", athlete.pk)

    return json.dumps({
        "success": True,
        "id": athlete.pk,
        "name": user.get_full_name(),
        "email": user.email,
        "notes": athlete.notes,
        "message": f"Aluno '{user.get_full_name()}' atualizado com sucesso!",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Delete athlete
# ---------------------------------------------------------------------------

def delete_athlete(athlete_id: int) -> str:
    """Encerra o vínculo operacional com um aluno, preservando conta e histórico.

    Args:
        athlete_id: ID do aluno a excluir (obrigatório).

    Returns:
        JSON confirmando a exclusão.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"athlete_id": athlete_id}

    try:
        athlete = AthleteService.get_owned_athlete(trainer, athlete_id)
    except Exception as exc:
        return _tool_json_response("delete_athlete", payload, {"error": _exception_message(exc)}, entity_type="athlete", entity_id=athlete_id)

    name = athlete.user.get_full_name()
    AthleteService.end_relationship(trainer, athlete)

    logger.info("Tool delete_athlete: ended relationship with athlete '%s' (id=%d)", name, athlete_id)

    result = {
        "success": True,
        "message": f"Vínculo com '{name}' encerrado com sucesso. O perfil e o histórico do aluno foram preservados.",
    }
    return _tool_json_response("delete_athlete", payload, result, entity_type="athlete", entity_id=athlete_id)


# ---------------------------------------------------------------------------
# TOOL: List exercises
# ---------------------------------------------------------------------------

def list_exercises(
    search: str = "",
    muscle_group: str = "",
    equipment: str = "",
    limit: int = 20,
) -> str:
    """Lista exercícios do catálogo disponíveis para o treinador.

    Args:
        search: Filtrar por nome do exercício (opcional).
        muscle_group: Filtrar por grupo muscular: chest, back, shoulders, biceps, triceps, forearms, abs, quadriceps, hamstrings, glutes, calves, full_body, other (opcional).
        equipment: Filtrar por equipamento: barbell, dumbbell, machine, cable, bodyweight, kettlebell, band, smith, other (opcional).
        limit: Número máximo de resultados (padrão 20).

    Returns:
        Lista JSON dos exercícios.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    qs = Exercise.objects.filter(
        is_global=True
    ) | Exercise.objects.filter(created_by=trainer)
    qs = qs.distinct()

    if search:
        qs = qs.filter(name__icontains=search)
    if muscle_group:
        qs = qs.filter(muscle_group=muscle_group)
    if equipment:
        qs = qs.filter(equipment=equipment)

    exercises = []
    for ex in qs[:limit]:
        exercises.append({
            "id": ex.pk,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "muscle_group_label": ex.muscle_group_label,
            "secondary_muscle": ex.secondary_muscle,
            "equipment": ex.equipment,
            "equipment_label": ex.equipment_label,
            "default_sets": ex.default_sets,
            "default_reps": ex.default_reps,
            "default_rest_seconds": ex.default_rest_seconds,
            "description": ex.description[:200] if ex.description else "",
        })

    return json.dumps(exercises, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Create exercise in catalog
# ---------------------------------------------------------------------------

def create_exercise(
    name: str,
    muscle_group: str = "other",
    equipment: str = "other",
    description: str = "",
    secondary_muscle: str = "",
    default_sets: int = 3,
    default_reps: str = "8-12",
    default_rest_seconds: int = 60,
    tips: str = "",
    video_url: str = "",
) -> str:
    """Cria um novo exercício no catálogo do treinador.

    Args:
        name: Nome do exercício (obrigatório).
        muscle_group: Grupo muscular principal — chest, back, shoulders, biceps, triceps, forearms, abs, quadriceps, hamstrings, glutes, calves, full_body, other.
        equipment: Equipamento — barbell, dumbbell, machine, cable, bodyweight, kettlebell, band, smith, other.
        description: Descrição ou instrução do exercício.
        secondary_muscle: Grupo muscular secundário.
        default_sets: Séries padrão (default 3).
        default_reps: Repetições padrão (default "8-12").
        default_rest_seconds: Descanso padrão em segundos (default 60).
        tips: Dicas de execução.
        video_url: URL de vídeo demonstrativo.

    Returns:
        JSON com os dados do exercício criado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    if not name:
        return json.dumps({"error": "Nome do exercício é obrigatório."}, ensure_ascii=False)

    exercise = Exercise.objects.create(
        name=name.strip(),
        muscle_group=muscle_group,
        equipment=equipment,
        description=description.strip(),
        secondary_muscle=secondary_muscle,
        default_sets=default_sets,
        default_reps=default_reps,
        default_rest_seconds=default_rest_seconds,
        tips=tips.strip(),
        video_url=video_url.strip(),
        is_global=False,
        created_by=trainer,
    )

    logger.info("Tool create_exercise: created '%s' (id=%d)", exercise.name, exercise.pk)

    return json.dumps({
        "success": True,
        "id": exercise.pk,
        "name": exercise.name,
        "muscle_group": exercise.muscle_group,
        "equipment": exercise.equipment,
        "message": f"Exercício '{exercise.name}' criado com sucesso!",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: List training plans
# ---------------------------------------------------------------------------

def list_training_plans(
    athlete_id: int = 0,
    search: str = "",
    only_active: bool = True,
    limit: int = 20,
) -> str:
    """Lista os planos de treino do treinador.

    Args:
        athlete_id: Filtrar por aluno específico (0 = todos).
        search: Buscar pelo nome do plano.
        only_active: Se True, retorna apenas planos ativos.
        limit: Máximo de resultados.

    Returns:
        Lista JSON dos planos de treino.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    qs = _active_training_plans_for_trainer(trainer).select_related("athlete__user")
    if athlete_id:
        qs = qs.filter(athlete_id=athlete_id)
    if search:
        qs = qs.filter(name__icontains=search)
    if only_active:
        qs = qs.filter(is_active=True)

    plans = []
    for p in qs[:limit]:
        plans.append({
            "id": p.pk,
            "name": p.name,
            "athlete": p.athlete.user.get_full_name(),
            "athlete_id": p.athlete_id,
            "objective": p.objective,
            "is_active": p.is_active,
            "workout_count": p.workouts.count(),
            "created_at": p.created_at.isoformat(),
        })

    return json.dumps(plans, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Create training plan
# ---------------------------------------------------------------------------

def create_training_plan(
    athlete_id: int,
    name: str,
    objective: str = "",
    is_active: bool = True,
) -> str:
    """Cria um novo plano de treino para um aluno.

    Args:
        athlete_id: ID do aluno (obrigatório).
        name: Nome do plano (ex: "Hipertrofia 2026") (obrigatório).
        objective: Objetivo do plano (opcional).
        is_active: Se o plano está ativo (default True).

    Returns:
        JSON com os dados do plano criado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"athlete_id": athlete_id, "name": name, "objective": objective, "is_active": is_active}

    try:
        plan = WorkoutService.create_training_plan(
            trainer,
            athlete_id,
            name,
            objective=objective,
            is_active=is_active,
        )
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("create_training_plan", payload, {"error": _exception_message(exc)}, entity_type="training_plan")

    athlete = plan.athlete

    logger.info("Tool create_training_plan: created '%s' for athlete %d", plan.name, athlete.pk)

    result = {
        "success": True,
        "id": plan.pk,
        "name": plan.name,
        "athlete": athlete.user.get_full_name(),
        "objective": objective,
        "message": f"Plano '{plan.name}' criado com sucesso para {athlete.user.get_full_name()}!",
    }
    return _tool_json_response("create_training_plan", payload, result, entity_type="training_plan", entity_id=plan.pk)


# ---------------------------------------------------------------------------
# TOOL: List workouts
# ---------------------------------------------------------------------------

def list_workouts(
    athlete_id: int = 0,
    plan_id: int = 0,
    only_active: bool = True,
    limit: int = 20,
) -> str:
    """Lista os treinos existentes.

    Args:
        athlete_id: Filtrar por aluno (0 = todos).
        plan_id: Filtrar por plano de treino (0 = todos).
        only_active: Se True, retorna apenas treinos ativos.
        limit: Máximo de resultados.

    Returns:
        Lista JSON dos treinos com exercícios.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    qs = _active_workouts_for_trainer(trainer).select_related("athlete__user", "plan")
    if athlete_id:
        qs = qs.filter(athlete_id=athlete_id)
    if plan_id:
        qs = qs.filter(plan_id=plan_id)
    if only_active:
        qs = qs.filter(is_active=True)

    workouts = []
    for w in qs[:limit]:
        workouts.append({
            "id": w.pk,
            "name": w.name,
            "athlete": w.athlete.user.get_full_name(),
            "athlete_id": w.athlete_id,
            "plan": w.plan.name if w.plan else None,
            "plan_id": w.plan_id,
            "objective": w.objective,
            "is_active": w.is_active,
            "exercise_count": w.exercises.count(),
            "created_at": w.created_at.isoformat(),
        })

    return json.dumps(workouts, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Create workout
# ---------------------------------------------------------------------------

def create_workout(
    athlete_id: int,
    name: str,
    plan_id: int = 0,
    objective: str = "",
    is_active: bool = True,
) -> str:
    """Cria um novo treino para um aluno.

    Args:
        athlete_id: ID do aluno (obrigatório).
        name: Nome do treino, ex: "Treino A — Costas e Bíceps" (obrigatório).
        plan_id: ID do plano de treino (0 para treino avulso).
        objective: Objetivo do treino (opcional).
        is_active: Se o treino está ativo (default True).

    Returns:
        JSON com os dados do treino criado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"athlete_id": athlete_id, "name": name, "plan_id": plan_id, "objective": objective, "is_active": is_active}

    try:
        workout = WorkoutService.create_workout(
            trainer,
            athlete_id,
            name,
            plan=plan_id or None,
            objective=objective,
            is_active=is_active,
        )
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("create_workout", payload, {"error": _exception_message(exc)}, entity_type="workout")

    athlete = workout.athlete
    plan = workout.plan

    logger.info("Tool create_workout: created '%s' for athlete %d", workout.name, athlete.pk)

    result = {
        "success": True,
        "id": workout.pk,
        "name": workout.name,
        "athlete": athlete.user.get_full_name(),
        "plan": plan.name if plan else None,
        "message": f"Treino '{workout.name}' criado com sucesso para {athlete.user.get_full_name()}!",
    }
    return _tool_json_response("create_workout", payload, result, entity_type="workout", entity_id=workout.pk)


# ---------------------------------------------------------------------------
# TOOL: Add exercise to workout
# ---------------------------------------------------------------------------

def add_exercise_to_workout(
    workout_id: int,
    exercise_id: int = 0,
    custom_name: str = "",
    sets: int = 3,
    reps: str = "8-12",
    current_load_kg: float = 0,
    rest_seconds: int = 60,
    notes: str = "",
) -> str:
    """Adiciona um exercício a um treino existente.

    Pode referenciar um exercício do catálogo (exercise_id) ou criar um personalizado (custom_name).

    Args:
        workout_id: ID do treino (obrigatório).
        exercise_id: ID do exercício do catálogo (0 se personalizado).
        custom_name: Nome personalizado do exercício (se não usar catálogo).
        sets: Número de séries (default 3).
        reps: Repetições, ex: "8-12" ou "10" (default "8-12").
        current_load_kg: Carga atual em kg (0 se sem carga).
        rest_seconds: Descanso em segundos (default 60).
        notes: Observações sobre o exercício (opcional).

    Returns:
        JSON com os dados da prescrição criada.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {
        "workout_id": workout_id,
        "exercise_id": exercise_id,
        "custom_name": custom_name,
        "sets": sets,
        "reps": reps,
        "current_load_kg": current_load_kg,
        "rest_seconds": rest_seconds,
        "notes": notes,
    }

    try:
        workout = _active_workouts_for_trainer(trainer).get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return _tool_json_response("add_exercise_to_workout", payload, {"error": f"Treino com ID {workout_id} não encontrado."}, entity_type="exercise_prescription")

    exercise_ref = None
    if exercise_id:
        try:
            exercise_ref = Exercise.objects.get(Q(is_global=True) | Q(created_by=trainer), pk=exercise_id)
        except Exercise.DoesNotExist:
            return _tool_json_response("add_exercise_to_workout", payload, {"error": f"Exercício com ID {exercise_id} não encontrado."}, entity_type="exercise_prescription")

    if not exercise_ref and not custom_name:
        return _tool_json_response("add_exercise_to_workout", payload, {"error": "Forneça exercise_id ou custom_name."}, entity_type="exercise_prescription")

    # Determine next order — retry on unique constraint violation (parallel tool calls)
    max_retries = 5
    prescription = None
    for attempt in range(max_retries):
        max_order = workout.exercises.aggregate(m=Max("exercise_order"))["m"] or 0
        next_order = max_order + 1  # re-reads each retry so gaps stay minimal

        try:
            prescription = ExercisePrescription.objects.create(
                workout=workout,
                exercise_ref=exercise_ref,
                name=custom_name.strip() if custom_name else "",
                sets=sets,
                reps=str(reps),
                current_load_kg=current_load_kg if current_load_kg else None,
                rest_seconds=rest_seconds,
                exercise_order=next_order,
                notes=notes.strip(),
            )
            break
        except IntegrityError:
            if attempt == max_retries - 1:
                return _tool_json_response("add_exercise_to_workout", payload, {"error": "Não foi possível adicionar o exercício — conflito de ordenação."}, entity_type="exercise_prescription")
            continue

    if prescription is None:
        return _tool_json_response("add_exercise_to_workout", payload, {"error": "Falha ao criar prescrição."}, entity_type="exercise_prescription")

    display = prescription.display_name
    logger.info("Tool add_exercise_to_workout: added '%s' to workout %d", display, workout.pk)

    result = {
        "success": True,
        "prescription_id": prescription.pk,
        "exercise": display,
        "workout": workout.name,
        "sets": sets,
        "reps": reps,
        "load_kg": float(current_load_kg) if current_load_kg else None,
        "order": next_order,
        "message": f"'{display}' adicionado ao treino '{workout.name}' na posição {next_order}!",
    }
    return _tool_json_response("add_exercise_to_workout", payload, result, entity_type="exercise_prescription", entity_id=prescription.pk)


# ---------------------------------------------------------------------------
# TOOL: Update exercise load
# ---------------------------------------------------------------------------

def update_exercise_load(
    prescription_id: int,
    new_load_kg: float,
    reason: str = "",
) -> str:
    """Atualiza a carga de um exercício prescrito em um treino.

    Args:
        prescription_id: ID da prescrição do exercício (obrigatório).
        new_load_kg: Nova carga em kg (obrigatório).
        reason: Motivo da atualização (opcional).

    Returns:
        JSON confirmando a atualização.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"prescription_id": prescription_id, "new_load_kg": new_load_kg, "reason": reason}

    try:
        prescription, load_update = WorkoutService.update_exercise_load(
            trainer,
            prescription_id,
            new_load_kg,
            reason=reason or "Assistant update",
        )
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("update_exercise_load", payload, {"error": _exception_message(exc)}, entity_type="exercise_prescription", entity_id=prescription_id)

    old_load = load_update.previous_load_kg

    logger.info("Tool update_exercise_load: %s load: %s -> %s kg", prescription.display_name, old_load, new_load_kg)

    result = {
        "success": True,
        "exercise": prescription.display_name,
        "previous_load_kg": float(old_load) if old_load else None,
        "new_load_kg": float(new_load_kg),
        "message": f"Carga de '{prescription.display_name}' atualizada para {new_load_kg} kg!",
    }
    return _tool_json_response("update_exercise_load", payload, result, entity_type="exercise_prescription", entity_id=prescription.pk)


# ---------------------------------------------------------------------------
# TOOL: Delete workout
# ---------------------------------------------------------------------------

def delete_workout(workout_id: int) -> str:
    """Exclui um treino e todos os exercícios vinculados.

    ATENÇÃO: Esta ação é irreversível.

    Args:
        workout_id: ID do treino a excluir (obrigatório).

    Returns:
        JSON confirmando a exclusão.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        workout = _active_workouts_for_trainer(trainer).get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return json.dumps({"error": f"Treino com ID {workout_id} não encontrado."}, ensure_ascii=False)

    name = workout.name
    workout.delete()

    logger.info("Tool delete_workout: deleted '%s' (id=%d)", name, workout_id)

    return json.dumps({
        "success": True,
        "message": f"Treino '{name}' excluído com sucesso.",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Get workout details (with exercises)
# ---------------------------------------------------------------------------

def get_workout_detail(workout_id: int) -> str:
    """Retorna os detalhes completos de um treino, incluindo todos os exercícios prescritos.

    Args:
        workout_id: ID do treino (obrigatório).

    Returns:
        JSON com dados do treino e lista de exercícios.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        workout = _active_workouts_for_trainer(trainer).select_related("athlete__user", "plan").get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return json.dumps({"error": f"Treino com ID {workout_id} não encontrado."}, ensure_ascii=False)

    exercises = []
    for ex in workout.exercises.select_related("exercise_ref").all():
        exercises.append({
            "prescription_id": ex.pk,
            "name": ex.display_name,
            "sets": ex.sets,
            "reps": ex.reps,
            "load_kg": float(ex.current_load_kg) if ex.current_load_kg else None,
            "rest_seconds": ex.rest_seconds,
            "order": ex.exercise_order,
            "muscle_group": ex.muscle_group_label,
            "equipment": ex.equipment_label,
            "notes": ex.notes,
        })

    return json.dumps({
        "id": workout.pk,
        "name": workout.name,
        "athlete": workout.athlete.user.get_full_name(),
        "athlete_id": workout.athlete_id,
        "plan": workout.plan.name if workout.plan else None,
        "objective": workout.objective,
        "is_active": workout.is_active,
        "exercises": exercises,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Save anamnesis (create or update)
# ---------------------------------------------------------------------------

def save_anamnesis(
    athlete_id: int,
    date_of_birth: str = "",
    gender: str = "",
    phone: str = "",
    emergency_contact_name: str = "",
    emergency_contact_phone: str = "",
    occupation: str = "",
    training_experience: str = "",
    training_frequency: int | None = None,
    primary_goal: str = "",
    secondary_goal: str = "",
    medical_conditions: str = "",
    medications: str = "",
    injuries_history: str = "",
    surgeries: str = "",
    allergies: str = "",
    pain_complaints: str = "",
    physical_limitations: str = "",
    smoker: bool = False,
    alcohol_consumption: str = "",
    sleep_hours: float | None = None,
    stress_level: str = "",
    dietary_restrictions: str = "",
    supplements: str = "",
    additional_notes: str = "",
) -> str:
    """Salva a anamnese (ficha de saúde) de um aluno. Cria uma nova ou atualiza a mais recente.

    Todos os campos são opcionais exceto athlete_id. Informe apenas os campos que o treinador fornecer.

    Args:
        athlete_id: ID do aluno (obrigatório).
        date_of_birth: Data de nascimento no formato YYYY-MM-DD (opcional).
        gender: Sexo — valores: M (masculino), F (feminino), O (outro) (opcional).
        phone: Telefone do aluno (opcional).
        emergency_contact_name: Nome do contato de emergência (opcional).
        emergency_contact_phone: Telefone do contato de emergência (opcional).
        occupation: Profissão (opcional).
        training_experience: Nível de experiência — valores: none, beginner, intermediate, advanced, elite (opcional).
        training_frequency: Frequência semanal de treino, 0-14 (opcional).
        primary_goal: Objetivo principal — valores: hypertrophy, strength, weight_loss, health, sport, rehab, flexibility, endurance, other (opcional).
        secondary_goal: Objetivo secundário (texto livre) (opcional).
        medical_conditions: Condições médicas / doenças (opcional).
        medications: Medicamentos em uso (opcional).
        injuries_history: Histórico de lesões (opcional).
        surgeries: Cirurgias realizadas (opcional).
        allergies: Alergias (opcional).
        pain_complaints: Queixas de dor / desconfortos (opcional).
        physical_limitations: Limitações físicas (opcional).
        smoker: Fumante — true ou false (padrão false).
        alcohol_consumption: Consumo de álcool — valores: none, social, moderate, frequent (opcional).
        sleep_hours: Horas de sono por noite (opcional).
        stress_level: Nível de estresse — valores: low, moderate, high, very_high (opcional).
        dietary_restrictions: Restrições alimentares (opcional).
        supplements: Suplementos em uso (opcional).
        additional_notes: Texto livre com informações adicionais sobre o aluno (opcional).

    Returns:
        JSON com os dados da anamnese salva.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = Athlete.objects.get(pk=athlete_id, trainer=trainer, relationship_status="active")
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    # Get or create — update existing if one exists, otherwise create new
    anamnesis = athlete.anamnesis_records.order_by("-created_at").first()
    is_new = anamnesis is None
    if is_new:
        anamnesis = Anamnesis(athlete=athlete)

    # Map of fields to update (only set non-empty values)
    if date_of_birth:
        try:
            anamnesis.date_of_birth = date_type.fromisoformat(date_of_birth)
        except ValueError:
            return json.dumps({"error": "Data de nascimento inválida. Use o formato YYYY-MM-DD."}, ensure_ascii=False)

    if gender:
        anamnesis.gender = gender.upper()
    if phone:
        anamnesis.phone = phone.strip()
    if emergency_contact_name:
        anamnesis.emergency_contact_name = emergency_contact_name.strip()
    if emergency_contact_phone:
        anamnesis.emergency_contact_phone = emergency_contact_phone.strip()
    if occupation:
        anamnesis.occupation = occupation.strip()
    if training_experience:
        anamnesis.training_experience = training_experience.strip()
    if training_frequency is not None:
        anamnesis.training_frequency = training_frequency
    if primary_goal:
        anamnesis.primary_goal = primary_goal.strip()
    if secondary_goal:
        anamnesis.secondary_goal = secondary_goal.strip()
    if medical_conditions:
        anamnesis.medical_conditions = medical_conditions.strip()
    if medications:
        anamnesis.medications = medications.strip()
    if injuries_history:
        anamnesis.injuries_history = injuries_history.strip()
    if surgeries:
        anamnesis.surgeries = surgeries.strip()
    if allergies:
        anamnesis.allergies = allergies.strip()
    if pain_complaints:
        anamnesis.pain_complaints = pain_complaints.strip()
    if physical_limitations:
        anamnesis.physical_limitations = physical_limitations.strip()
    # smoker is a boolean — always set it
    anamnesis.smoker = smoker
    if alcohol_consumption:
        anamnesis.alcohol_consumption = alcohol_consumption.strip()
    if sleep_hours is not None:
        anamnesis.sleep_hours = Decimal(str(sleep_hours))
    if stress_level:
        anamnesis.stress_level = stress_level.strip()
    if dietary_restrictions:
        anamnesis.dietary_restrictions = dietary_restrictions.strip()
    if supplements:
        anamnesis.supplements = supplements.strip()
    if additional_notes:
        anamnesis.additional_notes = additional_notes.strip()

    anamnesis.save()

    action = "criada" if is_new else "atualizada"
    logger.info("Tool save_anamnesis: %s anamnesis %d for athlete %d", action, anamnesis.pk, athlete.pk)

    result = {
        "success": True,
        "id": anamnesis.pk,
        "athlete_id": athlete.pk,
        "athlete_name": athlete.user.get_full_name(),
        "is_new": is_new,
        "message": f"Anamnese de '{athlete.user.get_full_name()}' {action} com sucesso!",
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Get anamnesis
# ---------------------------------------------------------------------------

def get_anamnesis(athlete_id: int) -> str:
    """Retorna a anamnese (ficha de saúde) mais recente de um aluno.

    Args:
        athlete_id: ID do aluno (obrigatório).

    Returns:
        JSON com todos os dados da anamnese ou mensagem indicando que não há anamnese.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = Athlete.objects.get(pk=athlete_id, trainer=trainer, relationship_status="active")
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    anamnesis = athlete.latest_anamnesis
    if not anamnesis:
        return json.dumps({
            "athlete_id": athlete.pk,
            "athlete_name": athlete.user.get_full_name(),
            "has_anamnesis": False,
            "message": f"O aluno '{athlete.user.get_full_name()}' ainda não possui anamnese cadastrada.",
        }, ensure_ascii=False)

    data = {
        "athlete_id": athlete.pk,
        "athlete_name": athlete.user.get_full_name(),
        "has_anamnesis": True,
        "id": anamnesis.pk,
        "date_of_birth": anamnesis.date_of_birth.isoformat() if anamnesis.date_of_birth else None,
        "gender": anamnesis.get_gender_display() if anamnesis.gender else None,
        "phone": anamnesis.phone or None,
        "emergency_contact_name": anamnesis.emergency_contact_name or None,
        "emergency_contact_phone": anamnesis.emergency_contact_phone or None,
        "occupation": anamnesis.occupation or None,
        "training_experience": anamnesis.get_training_experience_display() if anamnesis.training_experience else None,
        "training_frequency": anamnesis.training_frequency,
        "primary_goal": anamnesis.get_primary_goal_display() if anamnesis.primary_goal else None,
        "secondary_goal": anamnesis.secondary_goal or None,
        "medical_conditions": anamnesis.medical_conditions or None,
        "medications": anamnesis.medications or None,
        "injuries_history": anamnesis.injuries_history or None,
        "surgeries": anamnesis.surgeries or None,
        "allergies": anamnesis.allergies or None,
        "pain_complaints": anamnesis.pain_complaints or None,
        "physical_limitations": anamnesis.physical_limitations or None,
        "smoker": anamnesis.smoker,
        "alcohol_consumption": anamnesis.get_alcohol_consumption_display() if anamnesis.alcohol_consumption else None,
        "sleep_hours": float(anamnesis.sleep_hours) if anamnesis.sleep_hours else None,
        "stress_level": anamnesis.get_stress_level_display() if anamnesis.stress_level else None,
        "dietary_restrictions": anamnesis.dietary_restrictions or None,
        "supplements": anamnesis.supplements or None,
        "additional_notes": anamnesis.additional_notes or None,
        "updated_at": anamnesis.updated_at.isoformat(),
    }
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Save physical assessment
# ---------------------------------------------------------------------------

def save_physical_assessment(
    athlete_id: int,
    assessed_at: str = "",
    weight_kg: float | None = None,
    height_cm: float | None = None,
    body_fat_percentage: float | None = None,
    neck_cm: float | None = None,
    shoulders_cm: float | None = None,
    chest_cm: float | None = None,
    waist_cm: float | None = None,
    abdomen_cm: float | None = None,
    hips_cm: float | None = None,
    right_arm_cm: float | None = None,
    left_arm_cm: float | None = None,
    right_forearm_cm: float | None = None,
    left_forearm_cm: float | None = None,
    right_thigh_cm: float | None = None,
    left_thigh_cm: float | None = None,
    right_calf_cm: float | None = None,
    left_calf_cm: float | None = None,
    triceps_skinfold_mm: float | None = None,
    subscapular_skinfold_mm: float | None = None,
    suprailiac_skinfold_mm: float | None = None,
    abdominal_skinfold_mm: float | None = None,
    thigh_skinfold_mm: float | None = None,
    chest_skinfold_mm: float | None = None,
    midaxillary_skinfold_mm: float | None = None,
    notes: str = "",
) -> str:
    """Registra uma nova avaliação física (medidas corporais) para um aluno.

    Cria sempre um novo registro — cada avaliação é um snapshot no tempo.
    Informe apenas as medidas que foram coletadas.

    Args:
        athlete_id: ID do aluno (obrigatório).
        assessed_at: Data da avaliação no formato YYYY-MM-DD (opcional, padrão hoje).
        weight_kg: Peso em kg (opcional).
        height_cm: Altura em cm (opcional).
        body_fat_percentage: Percentual de gordura corporal (opcional).
        neck_cm: Circunferência do pescoço em cm (opcional).
        shoulders_cm: Circunferência dos ombros em cm (opcional).
        chest_cm: Circunferência do tórax/peito em cm (opcional).
        waist_cm: Circunferência da cintura em cm (opcional).
        abdomen_cm: Circunferência do abdômen em cm (opcional).
        hips_cm: Circunferência do quadril em cm (opcional).
        right_arm_cm: Circunferência do braço direito em cm (opcional).
        left_arm_cm: Circunferência do braço esquerdo em cm (opcional).
        right_forearm_cm: Circunferência do antebraço direito em cm (opcional).
        left_forearm_cm: Circunferência do antebraço esquerdo em cm (opcional).
        right_thigh_cm: Circunferência da coxa direita em cm (opcional).
        left_thigh_cm: Circunferência da coxa esquerda em cm (opcional).
        right_calf_cm: Circunferência da panturrilha direita em cm (opcional).
        left_calf_cm: Circunferência da panturrilha esquerda em cm (opcional).
        triceps_skinfold_mm: Dobra cutânea tricipital em mm (opcional).
        subscapular_skinfold_mm: Dobra cutânea subescapular em mm (opcional).
        suprailiac_skinfold_mm: Dobra cutânea suprailíaca em mm (opcional).
        abdominal_skinfold_mm: Dobra cutânea abdominal em mm (opcional).
        thigh_skinfold_mm: Dobra cutânea da coxa em mm (opcional).
        chest_skinfold_mm: Dobra cutânea peitoral em mm (opcional).
        midaxillary_skinfold_mm: Dobra cutânea axilar média em mm (opcional).
        notes: Observações da avaliação (opcional).

    Returns:
        JSON com os dados da avaliação criada, incluindo IMC e composição corporal calculados.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = Athlete.objects.get(pk=athlete_id, trainer=trainer, relationship_status="active")
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    assessment = PhysicalAssessment(athlete=athlete)

    # Date
    if assessed_at:
        try:
            assessment.assessed_at = date_type.fromisoformat(assessed_at)
        except ValueError:
            return json.dumps({"error": "Data inválida. Use o formato YYYY-MM-DD."}, ensure_ascii=False)

    # Helper to set decimal fields
    def _set_decimal(field_name, value):
        if value is not None:
            setattr(assessment, field_name, Decimal(str(value)))

    _set_decimal("weight_kg", weight_kg)
    _set_decimal("height_cm", height_cm)
    _set_decimal("body_fat_percentage", body_fat_percentage)
    _set_decimal("neck_cm", neck_cm)
    _set_decimal("shoulders_cm", shoulders_cm)
    _set_decimal("chest_cm", chest_cm)
    _set_decimal("waist_cm", waist_cm)
    _set_decimal("abdomen_cm", abdomen_cm)
    _set_decimal("hips_cm", hips_cm)
    _set_decimal("right_arm_cm", right_arm_cm)
    _set_decimal("left_arm_cm", left_arm_cm)
    _set_decimal("right_forearm_cm", right_forearm_cm)
    _set_decimal("left_forearm_cm", left_forearm_cm)
    _set_decimal("right_thigh_cm", right_thigh_cm)
    _set_decimal("left_thigh_cm", left_thigh_cm)
    _set_decimal("right_calf_cm", right_calf_cm)
    _set_decimal("left_calf_cm", left_calf_cm)
    _set_decimal("triceps_skinfold_mm", triceps_skinfold_mm)
    _set_decimal("subscapular_skinfold_mm", subscapular_skinfold_mm)
    _set_decimal("suprailiac_skinfold_mm", suprailiac_skinfold_mm)
    _set_decimal("abdominal_skinfold_mm", abdominal_skinfold_mm)
    _set_decimal("thigh_skinfold_mm", thigh_skinfold_mm)
    _set_decimal("chest_skinfold_mm", chest_skinfold_mm)
    _set_decimal("midaxillary_skinfold_mm", midaxillary_skinfold_mm)

    if notes:
        assessment.notes = notes.strip()

    assessment.save()

    logger.info("Tool save_physical_assessment: created assessment %d for athlete %d", assessment.pk, athlete.pk)

    result = {
        "success": True,
        "id": assessment.pk,
        "athlete_id": athlete.pk,
        "athlete_name": athlete.user.get_full_name(),
        "assessed_at": assessment.assessed_at.isoformat(),
        "weight_kg": float(assessment.weight_kg) if assessment.weight_kg else None,
        "height_cm": float(assessment.height_cm) if assessment.height_cm else None,
        "body_fat_percentage": float(assessment.body_fat_percentage) if assessment.body_fat_percentage else None,
        "bmi": float(assessment.bmi) if assessment.bmi else None,
        "bmi_classification": assessment.bmi_classification,
        "lean_mass_kg": float(assessment.lean_mass_kg) if assessment.lean_mass_kg else None,
        "fat_mass_kg": float(assessment.fat_mass_kg) if assessment.fat_mass_kg else None,
        "waist_hip_ratio": float(assessment.waist_hip_ratio) if assessment.waist_hip_ratio else None,
        "message": f"Avaliação física de '{athlete.user.get_full_name()}' registrada com sucesso!",
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Get physical assessment (latest)
# ---------------------------------------------------------------------------

def get_physical_assessment(athlete_id: int) -> str:
    """Retorna a avaliação física mais recente de um aluno com todas as medidas e cálculos.

    Args:
        athlete_id: ID do aluno (obrigatório).

    Returns:
        JSON com todas as medidas, IMC, composição corporal, e classificações.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = Athlete.objects.get(pk=athlete_id, trainer=trainer, relationship_status="active")
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    assessment = athlete.latest_assessment
    if not assessment:
        return json.dumps({
            "athlete_id": athlete.pk,
            "athlete_name": athlete.user.get_full_name(),
            "has_assessment": False,
            "message": f"O aluno '{athlete.user.get_full_name()}' ainda não possui avaliação física.",
        }, ensure_ascii=False)

    data = {
        "athlete_id": athlete.pk,
        "athlete_name": athlete.user.get_full_name(),
        "has_assessment": True,
        "id": assessment.pk,
        "assessed_at": assessment.assessed_at.isoformat(),
        # Main data
        "weight_kg": float(assessment.weight_kg) if assessment.weight_kg else None,
        "height_cm": float(assessment.height_cm) if assessment.height_cm else None,
        "body_fat_percentage": float(assessment.body_fat_percentage) if assessment.body_fat_percentage else None,
        # Calculated
        "bmi": float(assessment.bmi) if assessment.bmi else None,
        "bmi_classification": assessment.bmi_classification,
        "lean_mass_kg": float(assessment.lean_mass_kg) if assessment.lean_mass_kg else None,
        "lean_mass_percentage": float(assessment.lean_mass_percentage) if assessment.lean_mass_percentage else None,
        "fat_mass_kg": float(assessment.fat_mass_kg) if assessment.fat_mass_kg else None,
        "waist_hip_ratio": float(assessment.waist_hip_ratio) if assessment.waist_hip_ratio else None,
        # Circumferences
        "neck_cm": float(assessment.neck_cm) if assessment.neck_cm else None,
        "shoulders_cm": float(assessment.shoulders_cm) if assessment.shoulders_cm else None,
        "chest_cm": float(assessment.chest_cm) if assessment.chest_cm else None,
        "waist_cm": float(assessment.waist_cm) if assessment.waist_cm else None,
        "abdomen_cm": float(assessment.abdomen_cm) if assessment.abdomen_cm else None,
        "hips_cm": float(assessment.hips_cm) if assessment.hips_cm else None,
        "right_arm_cm": float(assessment.right_arm_cm) if assessment.right_arm_cm else None,
        "left_arm_cm": float(assessment.left_arm_cm) if assessment.left_arm_cm else None,
        "right_forearm_cm": float(assessment.right_forearm_cm) if assessment.right_forearm_cm else None,
        "left_forearm_cm": float(assessment.left_forearm_cm) if assessment.left_forearm_cm else None,
        "right_thigh_cm": float(assessment.right_thigh_cm) if assessment.right_thigh_cm else None,
        "left_thigh_cm": float(assessment.left_thigh_cm) if assessment.left_thigh_cm else None,
        "right_calf_cm": float(assessment.right_calf_cm) if assessment.right_calf_cm else None,
        "left_calf_cm": float(assessment.left_calf_cm) if assessment.left_calf_cm else None,
        # Skinfolds
        "triceps_skinfold_mm": float(assessment.triceps_skinfold_mm) if assessment.triceps_skinfold_mm else None,
        "subscapular_skinfold_mm": float(assessment.subscapular_skinfold_mm) if assessment.subscapular_skinfold_mm else None,
        "suprailiac_skinfold_mm": float(assessment.suprailiac_skinfold_mm) if assessment.suprailiac_skinfold_mm else None,
        "abdominal_skinfold_mm": float(assessment.abdominal_skinfold_mm) if assessment.abdominal_skinfold_mm else None,
        "thigh_skinfold_mm": float(assessment.thigh_skinfold_mm) if assessment.thigh_skinfold_mm else None,
        "chest_skinfold_mm": float(assessment.chest_skinfold_mm) if assessment.chest_skinfold_mm else None,
        "midaxillary_skinfold_mm": float(assessment.midaxillary_skinfold_mm) if assessment.midaxillary_skinfold_mm else None,
        "notes": assessment.notes or None,
    }
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: List physical assessments history
# ---------------------------------------------------------------------------

def list_physical_assessments(
    athlete_id: int,
    limit: int = 10,
) -> str:
    """Lista o histórico de avaliações físicas de um aluno, da mais recente para a mais antiga.

    Útil para acompanhar a evolução do aluno ao longo do tempo.

    Args:
        athlete_id: ID do aluno (obrigatório).
        limit: Número máximo de avaliações a retornar (padrão 10).

    Returns:
        Lista JSON com resumo de cada avaliação (data, peso, IMC, gordura, etc.).
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = Athlete.objects.get(pk=athlete_id, trainer=trainer, relationship_status="active")
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    assessments = athlete.physical_assessments.order_by("-assessed_at")[:limit]

    results = []
    for a in assessments:
        results.append({
            "id": a.pk,
            "assessed_at": a.assessed_at.isoformat(),
            "weight_kg": float(a.weight_kg) if a.weight_kg else None,
            "height_cm": float(a.height_cm) if a.height_cm else None,
            "body_fat_percentage": float(a.body_fat_percentage) if a.body_fat_percentage else None,
            "bmi": float(a.bmi) if a.bmi else None,
            "bmi_classification": a.bmi_classification,
            "lean_mass_kg": float(a.lean_mass_kg) if a.lean_mass_kg else None,
            "fat_mass_kg": float(a.fat_mass_kg) if a.fat_mass_kg else None,
            "waist_hip_ratio": float(a.waist_hip_ratio) if a.waist_hip_ratio else None,
        })

    return json.dumps({
        "athlete_id": athlete.pk,
        "athlete_name": athlete.user.get_full_name(),
        "total_assessments": athlete.physical_assessments.count(),
        "assessments": results,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOL: Get athlete details with recent activity
# ---------------------------------------------------------------------------

def get_athlete_detail(athlete_id: int) -> str:
    """Retorna detalhes completos de um aluno, incluindo treinos e atividade recente.

    Args:
        athlete_id: ID do aluno (obrigatório).

    Returns:
        JSON com dados do aluno, planos, treinos e últimas atualizações.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        athlete = _active_athletes_for_trainer(trainer).select_related("user").get(pk=athlete_id)
    except Athlete.DoesNotExist:
        return json.dumps({"error": f"Aluno com ID {athlete_id} não encontrado."}, ensure_ascii=False)

    # Plans and workouts
    plans = []
    for plan in athlete.training_plans.all():
        workouts = []
        for w in plan.workouts.all():
            workouts.append({
                "id": w.pk,
                "name": w.name,
                "is_active": w.is_active,
                "exercise_count": w.exercises.count(),
            })
        plans.append({
            "id": plan.pk,
            "name": plan.name,
            "objective": plan.objective,
            "is_active": plan.is_active,
            "workouts": workouts,
        })

    # Standalone workouts
    standalone = []
    for w in athlete.workout_plans.filter(plan__isnull=True):
        standalone.append({
            "id": w.pk,
            "name": w.name,
            "is_active": w.is_active,
            "exercise_count": w.exercises.count(),
        })

    # Recent load updates
    recent_updates = []
    updates = LoadUpdate.objects.filter(
        exercise__workout__athlete=athlete
    ).select_related("exercise").order_by("-created_at")[:10]
    for u in updates:
        recent_updates.append({
            "exercise": u.exercise.display_name,
            "previous_load_kg": float(u.previous_load_kg) if u.previous_load_kg else None,
            "new_load_kg": float(u.new_load_kg),
            "date": u.created_at.isoformat(),
        })

    # Anamnesis summary
    anamnesis_summary = None
    anamnesis = athlete.latest_anamnesis
    if anamnesis:
        anamnesis_summary = {
            "id": anamnesis.pk,
            "primary_goal": anamnesis.get_primary_goal_display() if anamnesis.primary_goal else None,
            "training_experience": anamnesis.get_training_experience_display() if anamnesis.training_experience else None,
            "training_frequency": anamnesis.training_frequency,
            "medical_conditions": anamnesis.medical_conditions or None,
            "injuries_history": anamnesis.injuries_history or None,
            "physical_limitations": anamnesis.physical_limitations or None,
            "updated_at": anamnesis.updated_at.isoformat(),
        }

    # Latest assessment summary
    assessment_summary = None
    assessment = athlete.latest_assessment
    if assessment:
        assessment_summary = {
            "id": assessment.pk,
            "assessed_at": assessment.assessed_at.isoformat(),
            "weight_kg": float(assessment.weight_kg) if assessment.weight_kg else None,
            "height_cm": float(assessment.height_cm) if assessment.height_cm else None,
            "body_fat_percentage": float(assessment.body_fat_percentage) if assessment.body_fat_percentage else None,
            "bmi": float(assessment.bmi) if assessment.bmi else None,
            "bmi_classification": assessment.bmi_classification,
        }

    return json.dumps({
        "id": athlete.pk,
        "name": athlete.user.get_full_name(),
        "email": athlete.user.email,
        "username": athlete.user.username,
        "notes": athlete.notes,
        "created_at": athlete.created_at.isoformat(),
        "anamnesis": anamnesis_summary,
        "latest_assessment": assessment_summary,
        "training_plans": plans,
        "standalone_workouts": standalone,
        "recent_load_updates": recent_updates,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOLS: Agenda de Aulas (ClassSchedule)
# ---------------------------------------------------------------------------

def list_schedule(
    week_start: str = "",
    athlete_id: int = 0,
    limit: int = 50,
) -> str:
    """Lista as aulas agendadas do treinador para uma semana.

    Use para consultar a agenda semanal, verificar horários ocupados,
    ou buscar aulas de um aluno específico.

    Args:
        week_start: Segunda-feira da semana no formato YYYY-MM-DD.
                    Se vazio, usa a semana atual.
        athlete_id: Filtra por aluno (opcional, 0 = todos os alunos).
        limit: Número máximo de resultados (padrão 50).

    Returns:
        JSON com lista de aulas contendo id, aluno, data/hora, duração,
        plano de treino vinculado, status e observações.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    # Resolve week
    if week_start:
        try:
            ref = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            return json.dumps({"error": "Formato de data inválido. Use YYYY-MM-DD."}, ensure_ascii=False)
    else:
        ref = date.today()

    # Monday of the week
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)

    qs = _active_classes_for_trainer(trainer).filter(
        scheduled_at__date__gte=monday,
        scheduled_at__date__lte=sunday,
    ).select_related("athlete__user", "workout_plan")

    if athlete_id:
        qs = qs.filter(athlete_id=athlete_id)

    qs = qs.order_by("scheduled_at")[:limit]

    results = []
    for cls in qs:
        results.append({
            "id": cls.pk,
            "athlete_id": cls.athlete_id,
            "athlete_name": cls.athlete.user.get_full_name(),
            "scheduled_at": cls.scheduled_at.strftime("%Y-%m-%d %H:%M"),
            "duration_minutes": cls.duration_minutes,
            "workout_plan_id": cls.workout_plan_id,
            "workout_plan_name": cls.workout_plan.name if cls.workout_plan else None,
            "status": cls.status,
            "status_label": cls.get_status_display(),
            "notes": cls.notes,
        })

    return json.dumps({
        "week": monday.isoformat(),
        "total": len(results),
        "classes": results,
    }, ensure_ascii=False)


def create_class(
    athlete_id: int,
    scheduled_date: str,
    scheduled_time: str,
    duration_minutes: int = 60,
    workout_plan_id: int = 0,
    status: str = "scheduled",
    notes: str = "",
) -> str:
    """Cria uma nova aula na agenda do treinador.

    Use quando o usuário pedir para agendar uma aula ou marcar um horário com um aluno.

    Args:
        athlete_id: ID do aluno (obrigatório). Use list_athletes para encontrar o ID.
        scheduled_date: Data da aula no formato YYYY-MM-DD (obrigatório).
        scheduled_time: Hora da aula no formato HH:MM, ex: "07:00" (obrigatório).
        duration_minutes: Duração em minutos (padrão 60).
        workout_plan_id: ID do plano de treino para vincular (0 = sem vínculo).
        status: Status da aula: "scheduled" (agendada), "completed" (realizada),
                "cancelled" (cancelada), "no_show" (falta). Padrão: "scheduled".
        notes: Observações sobre a aula (opcional).

    Returns:
        JSON com os dados da aula criada.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {
        "athlete_id": athlete_id,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
        "duration_minutes": duration_minutes,
        "workout_plan_id": workout_plan_id,
        "status": status,
        "notes": notes,
    }

    try:
        scheduled_at = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return _tool_json_response("create_class", payload, {"error": "Data ou hora inválida. Use YYYY-MM-DD e HH:MM."}, entity_type="class_schedule")

    try:
        cls = ScheduleService.create_class(
            trainer,
            athlete_id,
            scheduled_at,
            duration_minutes=duration_minutes,
            workout_plan=workout_plan_id or None,
            status=status,
            notes=notes,
        )
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("create_class", payload, {"error": _exception_message(exc)}, entity_type="class_schedule")

    athlete = cls.athlete
    workout_plan = cls.workout_plan

    logger.info("create_class: aula %d criada para aluno %d pelo treinador %d", cls.pk, athlete_id, trainer.pk)

    result = {
        "success": True,
        "id": cls.pk,
        "athlete_name": athlete.user.get_full_name(),
        "scheduled_at": cls.scheduled_at.strftime("%Y-%m-%d %H:%M"),
        "duration_minutes": cls.duration_minutes,
        "status": cls.status,
        "workout_plan_name": workout_plan.name if workout_plan else None,
        "message": f"Aula agendada para {athlete.user.get_full_name()} em {cls.scheduled_at.strftime('%d/%m/%Y às %H:%M')}.",
    }
    return _tool_json_response("create_class", payload, result, entity_type="class_schedule", entity_id=cls.pk)


def update_class(
    class_id: int,
    scheduled_date: str = "",
    scheduled_time: str = "",
    duration_minutes: int = 0,
    status: str = "",
    workout_plan_id: int = -1,
    notes: str = "",
    athlete_id: int = 0,
) -> str:
    """Atualiza uma aula existente na agenda.

    Use para remarcar horário, alterar status (realizada/cancelada/falta),
    ajustar duração ou trocar o plano de treino vinculado.

    Args:
        class_id: ID da aula (obrigatório). Use list_schedule para encontrar o ID.
        scheduled_date: Nova data no formato YYYY-MM-DD (vazio = não alterar).
        scheduled_time: Novo horário no formato HH:MM (vazio = não alterar).
        duration_minutes: Nova duração em minutos (0 = não alterar).
        status: Novo status: "scheduled", "completed", "cancelled", "no_show"
                (vazio = não alterar).
        workout_plan_id: ID do plano de treino (-1 = não alterar, 0 = remover vínculo).
        notes: Novas observações (vazio = não alterar).
        athlete_id: Novo aluno (0 = não alterar).

    Returns:
        JSON com os dados atualizados da aula.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {
        "class_id": class_id,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
        "duration_minutes": duration_minutes,
        "status": status,
        "workout_plan_id": workout_plan_id,
        "notes": notes,
        "athlete_id": athlete_id,
    }

    cls = _active_classes_for_trainer(trainer).filter(pk=class_id).first()
    if not cls:
        return _tool_json_response("update_class", payload, {"error": f"Aula com ID {class_id} não encontrada."}, entity_type="class_schedule", entity_id=class_id)

    fields = {}

    if scheduled_date or scheduled_time:
        date_str = scheduled_date or cls.scheduled_at.strftime("%Y-%m-%d")
        time_str = scheduled_time or cls.scheduled_at.strftime("%H:%M")
        try:
            fields["scheduled_at"] = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            return _tool_json_response("update_class", payload, {"error": "Data ou hora inválida. Use YYYY-MM-DD e HH:MM."}, entity_type="class_schedule", entity_id=class_id)

    if duration_minutes > 0:
        fields["duration_minutes"] = duration_minutes

    if status:
        fields["status"] = status

    if athlete_id:
        fields["athlete"] = athlete_id

    if workout_plan_id == 0:
        fields["workout_plan"] = None
    elif workout_plan_id > 0:
        fields["workout_plan"] = workout_plan_id

    if notes:
        fields["notes"] = notes

    try:
        cls = ScheduleService.update_class(trainer, cls, **fields)
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("update_class", payload, {"error": _exception_message(exc)}, entity_type="class_schedule", entity_id=class_id)

    logger.info("update_class: aula %d atualizada pelo treinador %d", class_id, trainer.pk)

    result = {
        "success": True,
        "id": cls.pk,
        "athlete_name": cls.athlete.user.get_full_name(),
        "scheduled_at": cls.scheduled_at.strftime("%Y-%m-%d %H:%M"),
        "duration_minutes": cls.duration_minutes,
        "status": cls.status,
        "status_label": cls.get_status_display(),
        "workout_plan_name": cls.workout_plan.name if cls.workout_plan else None,
        "message": f"Aula atualizada com sucesso.",
    }
    return _tool_json_response("update_class", payload, result, entity_type="class_schedule", entity_id=cls.pk)


def delete_class(class_id: int) -> str:
    """Remove uma aula da agenda permanentemente.

    ATENÇÃO: Antes de usar esta ferramenta, confirme com o usuário que deseja excluir a aula.

    Args:
        class_id: ID da aula (obrigatório). Use list_schedule para encontrar o ID.

    Returns:
        JSON confirmando a exclusão.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"class_id": class_id}

    cls = _active_classes_for_trainer(trainer).filter(pk=class_id).first()
    if not cls:
        return _tool_json_response("delete_class", payload, {"error": f"Aula com ID {class_id} não encontrada."}, entity_type="class_schedule", entity_id=class_id)

    info = f"{cls.athlete.user.get_full_name()} em {cls.scheduled_at.strftime('%d/%m/%Y às %H:%M')}"
    cls.delete()

    logger.info("delete_class: aula %d excluída pelo treinador %d", class_id, trainer.pk)

    result = {
        "success": True,
        "message": f"Aula de {info} removida da agenda.",
    }
    return _tool_json_response("delete_class", payload, result, entity_type="class_schedule", entity_id=class_id)


# ---------------------------------------------------------------------------
# TOOL: Update training plan
# ---------------------------------------------------------------------------

def update_training_plan(
    plan_id: int,
    name: str = "",
    objective: str = "",
    is_active: bool | None = None,
) -> str:
    """Atualiza um plano de treino do treinador atual.

    Args:
        plan_id: ID do plano de treino.
        name: Novo nome do plano, se houver.
        objective: Novo objetivo do plano, se houver.
        is_active: Novo status ativo/inativo. Use null para manter.

    Returns:
        JSON com o plano atualizado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"plan_id": plan_id, "name": name, "objective": objective, "is_active": is_active}

    try:
        plan = _active_training_plans_for_trainer(trainer).get(pk=plan_id)
    except TrainingPlan.DoesNotExist:
        return _tool_json_response("update_training_plan", payload, {"error": f"Plano com ID {plan_id} não encontrado."}, entity_type="training_plan", entity_id=plan_id)

    if name:
        plan.name = name.strip()
    if objective:
        plan.objective = objective.strip()
    if is_active is not None:
        plan.is_active = bool(is_active)
    plan.save()

    result = {
        "success": True,
        "id": plan.pk,
        "name": plan.name,
        "objective": plan.objective,
        "is_active": plan.is_active,
        "message": "Plano atualizado com sucesso.",
    }
    return _tool_json_response("update_training_plan", payload, result, entity_type="training_plan", entity_id=plan.pk)


def delete_training_plan(plan_id: int, confirmed: bool = False) -> str:
    """Exclui um plano de treino e seus treinos vinculados após confirmação explícita.

    Args:
        plan_id: ID do plano de treino.
        confirmed: True apenas quando o usuário confirmou a exclusão.

    Returns:
        JSON com solicitação de confirmação ou confirmação da exclusão.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"plan_id": plan_id, "confirmed": confirmed}

    try:
        plan = _active_training_plans_for_trainer(trainer).prefetch_related("workouts").get(pk=plan_id)
    except TrainingPlan.DoesNotExist:
        return _tool_json_response("delete_training_plan", payload, {"error": f"Plano com ID {plan_id} não encontrado."}, entity_type="training_plan", entity_id=plan_id)

    if not confirmed:
        return _tool_proposed_response(
            "delete_training_plan",
            payload,
            {
                "requires_confirmation": True,
                "id": plan.pk,
                "name": plan.name,
                "workout_count": plan.workouts.count(),
                "message": "Confirme para excluir este plano e todos os treinos vinculados.",
            },
            entity_type="training_plan",
            entity_id=plan.pk,
        )

    name = plan.name
    plan.delete()
    result = {"success": True, "message": f"Plano '{name}' excluído com sucesso."}
    return _tool_json_response("delete_training_plan", payload, result, entity_type="training_plan", entity_id=plan_id)


def update_workout(
    workout_id: int,
    name: str = "",
    objective: str = "",
    plan_id: int = -1,
    is_active: bool | None = None,
) -> str:
    """Atualiza dados gerais de um treino.

    Args:
        workout_id: ID do treino.
        name: Novo nome do treino, se houver.
        objective: Novo objetivo do treino, se houver.
        plan_id: -1 mantém o plano atual, 0 remove vínculo, maior que 0 define plano.
        is_active: Novo status ativo/inativo. Use null para manter.

    Returns:
        JSON com o treino atualizado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"workout_id": workout_id, "name": name, "objective": objective, "plan_id": plan_id, "is_active": is_active}

    try:
        workout = _active_workouts_for_trainer(trainer).select_related("athlete", "plan").get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return _tool_json_response("update_workout", payload, {"error": f"Treino com ID {workout_id} não encontrado."}, entity_type="workout", entity_id=workout_id)

    if name:
        workout.name = name.strip()
    if objective:
        workout.objective = objective.strip()
    if is_active is not None:
        workout.is_active = bool(is_active)
    if plan_id == 0:
        workout.plan = None
    elif plan_id > 0:
        try:
            workout.plan = WorkoutService._resolve_owned_plan(trainer, plan_id, athlete=workout.athlete)
        except (PermissionDenied, ValidationError) as exc:
            return _tool_json_response("update_workout", payload, {"error": _exception_message(exc)}, entity_type="workout", entity_id=workout_id)
    workout.save()

    result = {
        "success": True,
        "id": workout.pk,
        "name": workout.name,
        "objective": workout.objective,
        "plan_id": workout.plan_id,
        "is_active": workout.is_active,
        "message": "Treino atualizado com sucesso.",
    }
    return _tool_json_response("update_workout", payload, result, entity_type="workout", entity_id=workout.pk)


def archive_workout(workout_id: int, archived: bool = True) -> str:
    """Arquiva ou restaura um treino sem apagá-lo.

    Args:
        workout_id: ID do treino.
        archived: True para arquivar, False para restaurar.

    Returns:
        JSON com o novo estado do treino.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"workout_id": workout_id, "archived": archived}

    try:
        workout = _active_workouts_for_trainer(trainer).get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return _tool_json_response("archive_workout", payload, {"error": f"Treino com ID {workout_id} não encontrado."}, entity_type="workout", entity_id=workout_id)

    workout.is_archived = bool(archived)
    workout.save(update_fields=["is_archived"])
    state = "arquivado" if workout.is_archived else "restaurado"
    result = {"success": True, "id": workout.pk, "is_archived": workout.is_archived, "message": f"Treino '{workout.name}' {state}."}
    return _tool_json_response("archive_workout", payload, result, entity_type="workout", entity_id=workout.pk)


def _clone_workout_for_trainer(trainer, source_workout, target_athlete, name: str, target_plan=None):
    with transaction.atomic():
        new_workout = WorkoutPlan.objects.create(
            athlete=target_athlete,
            plan=target_plan,
            name=name.strip() or f"Cópia de {source_workout.name}",
            objective=source_workout.objective,
            is_active=source_workout.is_active,
            created_by=trainer,
        )
        for prescription in source_workout.exercises.select_related("exercise_ref").prefetch_related("alternatives__exercise_ref").all():
            new_prescription = ExercisePrescription.objects.create(
                workout=new_workout,
                exercise_ref=prescription.exercise_ref,
                name=prescription.name,
                sets=prescription.sets,
                reps=prescription.reps,
                current_load_kg=prescription.current_load_kg,
                rest_seconds=prescription.rest_seconds,
                exercise_order=prescription.exercise_order,
                notes=prescription.notes,
            )
            for alternative in prescription.alternatives.all():
                ExerciseAlternative.objects.create(
                    prescription=new_prescription,
                    exercise_ref=alternative.exercise_ref,
                    notes=alternative.notes,
                    order=alternative.order,
                )
        return new_workout


def duplicate_workout(workout_id: int, new_name: str = "", target_plan_id: int = -1) -> str:
    """Duplica um treino para o mesmo aluno, preservando exercícios e alternativas.

    Args:
        workout_id: ID do treino de origem.
        new_name: Nome do novo treino. Se vazio, usa "Cópia de ...".
        target_plan_id: -1 mantém plano de origem, 0 cria avulso, maior que 0 vincula ao plano informado.

    Returns:
        JSON com o treino duplicado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"workout_id": workout_id, "new_name": new_name, "target_plan_id": target_plan_id}

    try:
        source = _active_workouts_for_trainer(trainer).select_related("athlete", "plan").get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return _tool_json_response("duplicate_workout", payload, {"error": f"Treino com ID {workout_id} não encontrado."}, entity_type="workout", entity_id=workout_id)

    try:
        if target_plan_id == -1:
            target_plan = source.plan
        elif target_plan_id == 0:
            target_plan = None
        else:
            target_plan = WorkoutService._resolve_owned_plan(trainer, target_plan_id, athlete=source.athlete)
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("duplicate_workout", payload, {"error": _exception_message(exc)}, entity_type="workout", entity_id=workout_id)

    new_workout = _clone_workout_for_trainer(trainer, source, source.athlete, new_name or f"Cópia de {source.name}", target_plan=target_plan)
    result = {
        "success": True,
        "id": new_workout.pk,
        "name": new_workout.name,
        "athlete_id": new_workout.athlete_id,
        "plan_id": new_workout.plan_id,
        "exercise_count": new_workout.exercises.count(),
        "message": f"Treino duplicado como '{new_workout.name}'.",
    }
    return _tool_json_response("duplicate_workout", payload, result, entity_type="workout", entity_id=new_workout.pk)


def copy_workout_to_athlete(
    workout_id: int,
    target_athlete_id: int,
    new_name: str = "",
    target_plan_id: int = 0,
) -> str:
    """Copia um treino para outro aluno do mesmo treinador.

    Args:
        workout_id: ID do treino de origem.
        target_athlete_id: ID do aluno de destino.
        new_name: Nome do novo treino. Se vazio, reaproveita o nome original.
        target_plan_id: 0 cria treino avulso, maior que 0 vincula ao plano de destino.

    Returns:
        JSON com o treino copiado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"workout_id": workout_id, "target_athlete_id": target_athlete_id, "new_name": new_name, "target_plan_id": target_plan_id}

    try:
        source = _active_workouts_for_trainer(trainer).select_related("athlete").get(pk=workout_id)
        target_athlete = AthleteService.get_owned_athlete(trainer, target_athlete_id)
        target_plan = WorkoutService._resolve_owned_plan(trainer, target_plan_id, athlete=target_athlete) if target_plan_id else None
    except (WorkoutPlan.DoesNotExist, PermissionDenied, ValidationError) as exc:
        return _tool_json_response("copy_workout_to_athlete", payload, {"error": _exception_message(exc)}, entity_type="workout")

    new_workout = _clone_workout_for_trainer(trainer, source, target_athlete, new_name or source.name, target_plan=target_plan)
    result = {
        "success": True,
        "id": new_workout.pk,
        "name": new_workout.name,
        "athlete_id": new_workout.athlete_id,
        "athlete_name": new_workout.athlete.user.get_full_name(),
        "exercise_count": new_workout.exercises.count(),
        "message": f"Treino copiado para {new_workout.athlete.user.get_full_name()}.",
    }
    return _tool_json_response("copy_workout_to_athlete", payload, result, entity_type="workout", entity_id=new_workout.pk)


def update_exercise_prescription(
    prescription_id: int,
    exercise_id: int = -1,
    custom_name: str = "",
    sets: int = 0,
    reps: str = "",
    current_load_kg: float | None = None,
    clear_load: bool = False,
    rest_seconds: int = 0,
    notes: str = "",
) -> str:
    """Atualiza uma prescrição de exercício dentro de um treino.

    Args:
        prescription_id: ID da prescrição.
        exercise_id: -1 mantém, 0 remove referência do catálogo, maior que 0 define exercício do catálogo.
        custom_name: Nome personalizado, se houver.
        sets: Novas séries, 0 mantém.
        reps: Novas repetições, vazio mantém.
        current_load_kg: Nova carga, null mantém.
        clear_load: True remove a carga atual.
        rest_seconds: Novo descanso, 0 mantém.
        notes: Novas observações, vazio mantém.

    Returns:
        JSON com a prescrição atualizada.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {
        "prescription_id": prescription_id,
        "exercise_id": exercise_id,
        "custom_name": custom_name,
        "sets": sets,
        "reps": reps,
        "current_load_kg": current_load_kg,
        "clear_load": clear_load,
        "rest_seconds": rest_seconds,
        "notes": notes,
    }

    prescription = ExercisePrescription.objects.select_related("workout", "exercise_ref").filter(
        pk=prescription_id,
        workout__created_by=trainer,
        workout__athlete__trainer=trainer,
        workout__athlete__relationship_status="active",
    ).first()
    if prescription is None:
        return _tool_json_response("update_exercise_prescription", payload, {"error": f"Prescrição com ID {prescription_id} não encontrada."}, entity_type="exercise_prescription", entity_id=prescription_id)

    if exercise_id == 0:
        prescription.exercise_ref = None
    elif exercise_id > 0:
        exercise = Exercise.objects.filter(Q(is_global=True) | Q(created_by=trainer), pk=exercise_id).first()
        if exercise is None:
            return _tool_json_response("update_exercise_prescription", payload, {"error": f"Exercício com ID {exercise_id} não encontrado."}, entity_type="exercise_prescription", entity_id=prescription_id)
        prescription.exercise_ref = exercise
    if custom_name:
        prescription.name = custom_name.strip()
    if sets > 0:
        prescription.sets = sets
    if reps:
        prescription.reps = str(reps).strip()
    if clear_load:
        prescription.current_load_kg = None
    elif current_load_kg is not None:
        prescription.current_load_kg = current_load_kg
    if rest_seconds > 0:
        prescription.rest_seconds = rest_seconds
    if notes:
        prescription.notes = notes.strip()
    prescription.save()

    result = {
        "success": True,
        "prescription_id": prescription.pk,
        "exercise": prescription.display_name,
        "sets": prescription.sets,
        "reps": prescription.reps,
        "load_kg": float(prescription.current_load_kg) if prescription.current_load_kg else None,
        "rest_seconds": prescription.rest_seconds,
        "notes": prescription.notes,
        "message": f"Prescrição de '{prescription.display_name}' atualizada.",
    }
    return _tool_json_response("update_exercise_prescription", payload, result, entity_type="exercise_prescription", entity_id=prescription.pk)


def remove_exercise_from_workout(prescription_id: int, confirmed: bool = False) -> str:
    """Remove uma prescrição de exercício de um treino após confirmação.

    Args:
        prescription_id: ID da prescrição.
        confirmed: True apenas quando o usuário confirmou a remoção.

    Returns:
        JSON com solicitação de confirmação ou confirmação da remoção.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"prescription_id": prescription_id, "confirmed": confirmed}

    prescription = ExercisePrescription.objects.select_related("workout").filter(
        pk=prescription_id,
        workout__created_by=trainer,
        workout__athlete__trainer=trainer,
        workout__athlete__relationship_status="active",
    ).first()
    if prescription is None:
        return _tool_json_response("remove_exercise_from_workout", payload, {"error": f"Prescrição com ID {prescription_id} não encontrada."}, entity_type="exercise_prescription", entity_id=prescription_id)

    if not confirmed:
        return _tool_proposed_response(
            "remove_exercise_from_workout",
            payload,
            {
                "requires_confirmation": True,
                "prescription_id": prescription.pk,
                "exercise": prescription.display_name,
                "workout": prescription.workout.name,
                "message": "Confirme para remover este exercício do treino.",
            },
            entity_type="exercise_prescription",
            entity_id=prescription.pk,
        )

    display = prescription.display_name
    workout_name = prescription.workout.name
    prescription.delete()
    result = {"success": True, "message": f"'{display}' removido do treino '{workout_name}'."}
    return _tool_json_response("remove_exercise_from_workout", payload, result, entity_type="exercise_prescription", entity_id=prescription_id)


def reorder_workout_exercises(workout_id: int, order_json: str) -> str:
    """Reordena todos ou parte dos exercícios de um treino.

    Args:
        workout_id: ID do treino.
        order_json: JSON array com IDs das prescrições na ordem desejada.

    Returns:
        JSON com a nova ordem.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    desired_order = _parse_json_payload(order_json, [])
    payload = {"workout_id": workout_id, "order": desired_order}

    if not isinstance(desired_order, list) or not desired_order:
        return _tool_json_response("reorder_workout_exercises", payload, {"error": "Informe order_json como uma lista de IDs."}, entity_type="workout", entity_id=workout_id)

    try:
        workout = _active_workouts_for_trainer(trainer).get(pk=workout_id)
    except WorkoutPlan.DoesNotExist:
        return _tool_json_response("reorder_workout_exercises", payload, {"error": f"Treino com ID {workout_id} não encontrado."}, entity_type="workout", entity_id=workout_id)

    prescription_ids = [int(item) for item in desired_order]
    if len(set(prescription_ids)) != len(prescription_ids):
        return _tool_json_response("reorder_workout_exercises", payload, {"error": "A lista de ordem possui IDs duplicados."}, entity_type="workout", entity_id=workout_id)

    existing_ids = set(workout.exercises.filter(pk__in=prescription_ids).values_list("pk", flat=True))
    missing_ids = [prescription_id for prescription_id in prescription_ids if prescription_id not in existing_ids]
    if missing_ids:
        return _tool_json_response("reorder_workout_exercises", payload, {"error": f"Prescrições fora do treino: {missing_ids}."}, entity_type="workout", entity_id=workout_id)

    with transaction.atomic():
        for index, prescription_id in enumerate(prescription_ids, start=1):
            ExercisePrescription.objects.filter(pk=prescription_id, workout=workout).update(exercise_order=1000 + index)
        for index, prescription_id in enumerate(prescription_ids, start=1):
            ExercisePrescription.objects.filter(pk=prescription_id, workout=workout).update(exercise_order=index)

    order = [
        {"prescription_id": prescription.pk, "exercise": prescription.display_name, "order": prescription.exercise_order}
        for prescription in workout.exercises.select_related("exercise_ref").all()
    ]
    result = {"success": True, "workout_id": workout.pk, "order": order, "message": "Ordem dos exercícios atualizada."}
    return _tool_json_response("reorder_workout_exercises", payload, result, entity_type="workout", entity_id=workout.pk)


def add_exercise_alternative(prescription_id: int, exercise_id: int, notes: str = "", order: int = 1) -> str:
    """Adiciona uma alternativa de exercício a uma prescrição.

    Args:
        prescription_id: ID da prescrição principal.
        exercise_id: ID do exercício substituto no catálogo.
        notes: Observação sobre quando usar a alternativa.
        order: Ordem de exibição da alternativa.

    Returns:
        JSON com a alternativa criada.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"prescription_id": prescription_id, "exercise_id": exercise_id, "notes": notes, "order": order}

    prescription = ExercisePrescription.objects.filter(
        pk=prescription_id,
        workout__created_by=trainer,
        workout__athlete__trainer=trainer,
        workout__athlete__relationship_status="active",
    ).first()
    exercise = Exercise.objects.filter(Q(is_global=True) | Q(created_by=trainer), pk=exercise_id).first()
    if prescription is None:
        return _tool_json_response("add_exercise_alternative", payload, {"error": f"Prescrição com ID {prescription_id} não encontrada."}, entity_type="exercise_alternative")
    if exercise is None:
        return _tool_json_response("add_exercise_alternative", payload, {"error": f"Exercício com ID {exercise_id} não encontrado."}, entity_type="exercise_alternative")

    alternative = ExerciseAlternative.objects.create(
        prescription=prescription,
        exercise_ref=exercise,
        notes=notes.strip(),
        order=max(1, int(order or 1)),
    )
    result = {
        "success": True,
        "id": alternative.pk,
        "prescription_id": prescription.pk,
        "exercise": exercise.name,
        "message": f"Alternativa '{exercise.name}' adicionada para '{prescription.display_name}'.",
    }
    return _tool_json_response("add_exercise_alternative", payload, result, entity_type="exercise_alternative", entity_id=alternative.pk)


def remove_exercise_alternative(alternative_id: int, confirmed: bool = False) -> str:
    """Remove uma alternativa de exercício após confirmação.

    Args:
        alternative_id: ID da alternativa.
        confirmed: True apenas quando o usuário confirmou a remoção.

    Returns:
        JSON com solicitação de confirmação ou confirmação da remoção.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"alternative_id": alternative_id, "confirmed": confirmed}

    alternative = ExerciseAlternative.objects.select_related("prescription__workout", "exercise_ref").filter(
        pk=alternative_id,
        prescription__workout__created_by=trainer,
        prescription__workout__athlete__trainer=trainer,
        prescription__workout__athlete__relationship_status="active",
    ).first()
    if alternative is None:
        return _tool_json_response("remove_exercise_alternative", payload, {"error": f"Alternativa com ID {alternative_id} não encontrada."}, entity_type="exercise_alternative", entity_id=alternative_id)

    if not confirmed:
        return _tool_proposed_response(
            "remove_exercise_alternative",
            payload,
            {
                "requires_confirmation": True,
                "id": alternative.pk,
                "exercise": alternative.exercise_ref.name,
                "message": "Confirme para remover esta alternativa.",
            },
            entity_type="exercise_alternative",
            entity_id=alternative.pk,
        )

    name = alternative.exercise_ref.name
    alternative.delete()
    result = {"success": True, "message": f"Alternativa '{name}' removida."}
    return _tool_json_response("remove_exercise_alternative", payload, result, entity_type="exercise_alternative", entity_id=alternative_id)


def update_exercise_catalog(
    exercise_id: int,
    name: str = "",
    muscle_group: str = "",
    equipment: str = "",
    description: str = "",
    secondary_muscle: str = "",
    default_sets: int = 0,
    default_reps: str = "",
    default_rest_seconds: int = 0,
    tips: str = "",
    video_url: str = "",
) -> str:
    """Atualiza um exercício do catálogo criado pelo treinador.

    Args:
        exercise_id: ID do exercício do catálogo.
        name: Novo nome, se houver.
        muscle_group: Novo grupo muscular, se houver.
        equipment: Novo equipamento, se houver.
        description: Nova descrição, se houver.
        secondary_muscle: Novo músculo secundário, se houver.
        default_sets: Séries padrão, 0 mantém.
        default_reps: Repetições padrão, vazio mantém.
        default_rest_seconds: Descanso padrão, 0 mantém.
        tips: Novas dicas, se houver.
        video_url: Nova URL de vídeo, se houver.

    Returns:
        JSON com o exercício atualizado.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {
        "exercise_id": exercise_id,
        "name": name,
        "muscle_group": muscle_group,
        "equipment": equipment,
        "description": description,
        "secondary_muscle": secondary_muscle,
        "default_sets": default_sets,
        "default_reps": default_reps,
        "default_rest_seconds": default_rest_seconds,
        "tips": tips,
        "video_url": video_url,
    }

    exercise = Exercise.objects.filter(pk=exercise_id, created_by=trainer, is_global=False).first()
    if exercise is None:
        return _tool_json_response("update_exercise_catalog", payload, {"error": "Exercício não encontrado ou não editável."}, entity_type="exercise", entity_id=exercise_id)

    if name:
        exercise.name = name.strip()
    if muscle_group:
        exercise.muscle_group = muscle_group.strip()
    if equipment:
        exercise.equipment = equipment.strip()
    if description:
        exercise.description = description.strip()
    if secondary_muscle:
        exercise.secondary_muscle = secondary_muscle.strip()
    if default_sets > 0:
        exercise.default_sets = default_sets
    if default_reps:
        exercise.default_reps = default_reps.strip()
    if default_rest_seconds > 0:
        exercise.default_rest_seconds = default_rest_seconds
    if tips:
        exercise.tips = tips.strip()
    if video_url:
        exercise.video_url = video_url.strip()
    exercise.save()

    result = {
        "success": True,
        "id": exercise.pk,
        "name": exercise.name,
        "muscle_group": exercise.muscle_group,
        "equipment": exercise.equipment,
        "message": f"Exercício '{exercise.name}' atualizado.",
    }
    return _tool_json_response("update_exercise_catalog", payload, result, entity_type="exercise", entity_id=exercise.pk)


def delete_exercise_catalog(exercise_id: int, confirmed: bool = False) -> str:
    """Exclui um exercício criado pelo treinador após confirmação.

    Args:
        exercise_id: ID do exercício do catálogo.
        confirmed: True apenas quando o usuário confirmou a exclusão.

    Returns:
        JSON com solicitação de confirmação ou confirmação da exclusão.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"exercise_id": exercise_id, "confirmed": confirmed}
    exercise = Exercise.objects.filter(pk=exercise_id, created_by=trainer, is_global=False).first()
    if exercise is None:
        return _tool_json_response("delete_exercise_catalog", payload, {"error": "Exercício não encontrado ou não removível."}, entity_type="exercise", entity_id=exercise_id)

    if not confirmed:
        return _tool_proposed_response(
            "delete_exercise_catalog",
            payload,
            {
                "requires_confirmation": True,
                "id": exercise.pk,
                "name": exercise.name,
                "message": "Confirme para excluir este exercício do seu catálogo.",
            },
            entity_type="exercise",
            entity_id=exercise.pk,
        )

    name = exercise.name
    exercise.delete()
    result = {"success": True, "message": f"Exercício '{name}' excluído do catálogo."}
    return _tool_json_response("delete_exercise_catalog", payload, result, entity_type="exercise", entity_id=exercise_id)


def set_student_permissions(athlete_id: int, allow_student_load_updates: bool | None = None) -> str:
    """Atualiza permissões operacionais de um aluno vinculado.

    Args:
        athlete_id: ID do aluno.
        allow_student_load_updates: Permite ou bloqueia atualização de carga pelo aluno.

    Returns:
        JSON com as permissões atualizadas.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"athlete_id": athlete_id, "allow_student_load_updates": allow_student_load_updates}

    try:
        athlete = AthleteService.get_owned_athlete(trainer, athlete_id)
    except Exception as exc:
        return _tool_json_response("set_student_permissions", payload, {"error": _exception_message(exc)}, entity_type="athlete", entity_id=athlete_id)

    if allow_student_load_updates is not None:
        athlete.allow_student_load_updates = bool(allow_student_load_updates)
        athlete.save(update_fields=["allow_student_load_updates"])

    result = {
        "success": True,
        "athlete_id": athlete.pk,
        "athlete_name": athlete.user.get_full_name(),
        "allow_student_load_updates": athlete.allow_student_load_updates,
        "message": "Permissões do aluno atualizadas.",
    }
    return _tool_json_response("set_student_permissions", payload, result, entity_type="athlete", entity_id=athlete.pk)


def _schedule_conflicts_for_trainer(trainer, scheduled_at, duration_minutes: int, exclude_class_id: int = 0):
    start_at = scheduled_at
    end_at = scheduled_at + timedelta(minutes=max(1, int(duration_minutes or 60)))
    classes = _active_classes_for_trainer(trainer).filter(scheduled_at__date=scheduled_at.date()).select_related("athlete__user", "workout_plan")
    if exclude_class_id:
        classes = classes.exclude(pk=exclude_class_id)

    conflicts = []
    for class_schedule in classes:
        class_start = class_schedule.scheduled_at
        class_end = class_start + timedelta(minutes=class_schedule.duration_minutes)
        if class_start < end_at and class_end > start_at:
            conflicts.append(class_schedule)
    return conflicts


def check_schedule_conflicts(
    scheduled_date: str,
    scheduled_time: str,
    duration_minutes: int = 60,
    exclude_class_id: int = 0,
) -> str:
    """Verifica conflitos de horário na agenda do treinador.

    Args:
        scheduled_date: Data no formato YYYY-MM-DD.
        scheduled_time: Hora no formato HH:MM.
        duration_minutes: Duração da aula.
        exclude_class_id: ID de aula a ignorar ao remarcar.

    Returns:
        JSON com conflitos encontrados.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"scheduled_date": scheduled_date, "scheduled_time": scheduled_time, "duration_minutes": duration_minutes, "exclude_class_id": exclude_class_id}

    try:
        scheduled_at = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return json.dumps({"error": "Data ou hora inválida. Use YYYY-MM-DD e HH:MM."}, ensure_ascii=False)

    conflicts = _schedule_conflicts_for_trainer(trainer, scheduled_at, duration_minutes, exclude_class_id=exclude_class_id)
    result = {
        "has_conflicts": bool(conflicts),
        "conflicts": [
            {
                "id": class_schedule.pk,
                "athlete_id": class_schedule.athlete_id,
                "athlete_name": class_schedule.athlete.user.get_full_name(),
                "scheduled_at": class_schedule.scheduled_at.strftime("%Y-%m-%d %H:%M"),
                "duration_minutes": class_schedule.duration_minutes,
                "status": class_schedule.status,
            }
            for class_schedule in conflicts
        ],
    }
    return json.dumps(result, ensure_ascii=False)


def find_available_schedule_slots(
    scheduled_date: str,
    duration_minutes: int = 60,
    day_start: str = "06:00",
    day_end: str = "22:00",
    step_minutes: int = 30,
    limit: int = 12,
) -> str:
    """Encontra horários livres na agenda de um dia.

    Args:
        scheduled_date: Data no formato YYYY-MM-DD.
        duration_minutes: Duração desejada da aula.
        day_start: Hora inicial de busca no formato HH:MM.
        day_end: Hora final de busca no formato HH:MM.
        step_minutes: Intervalo entre sugestões.
        limit: Máximo de horários retornados.

    Returns:
        JSON com horários livres sugeridos.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        cursor = datetime.strptime(f"{scheduled_date} {day_start}", "%Y-%m-%d %H:%M")
        end_search = datetime.strptime(f"{scheduled_date} {day_end}", "%Y-%m-%d %H:%M")
    except ValueError:
        return json.dumps({"error": "Data ou hora inválida. Use YYYY-MM-DD e HH:MM."}, ensure_ascii=False)

    step = timedelta(minutes=max(5, int(step_minutes or 30)))
    duration = max(1, int(duration_minutes or 60))
    slots = []
    while cursor + timedelta(minutes=duration) <= end_search and len(slots) < limit:
        if not _schedule_conflicts_for_trainer(trainer, cursor, duration):
            slots.append({"date": cursor.strftime("%Y-%m-%d"), "time": cursor.strftime("%H:%M")})
        cursor += step

    return json.dumps({"date": scheduled_date, "duration_minutes": duration, "slots": slots}, ensure_ascii=False)


def bulk_schedule_classes(classes_json: str) -> str:
    """Agenda várias aulas de uma vez a partir de uma lista JSON.

    Args:
        classes_json: JSON array com objetos contendo athlete_id, scheduled_date, scheduled_time,
            duration_minutes, workout_plan_id, status e notes.

    Returns:
        JSON com aulas criadas e erros por item.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    items = _parse_json_payload(classes_json, [])
    payload = {"classes": items}

    if not isinstance(items, list) or not items:
        return _tool_json_response("bulk_schedule_classes", payload, {"error": "Informe classes_json como uma lista de aulas."}, entity_type="class_schedule")
    if len(items) > 30:
        return _tool_json_response("bulk_schedule_classes", payload, {"error": "Limite de 30 aulas por chamada."}, entity_type="class_schedule")

    created = []
    errors = []
    for index, item in enumerate(items, start=1):
        try:
            scheduled_at = datetime.strptime(f"{item.get('scheduled_date', '')} {item.get('scheduled_time', '')}", "%Y-%m-%d %H:%M")
            class_schedule = ScheduleService.create_class(
                trainer,
                int(item.get("athlete_id", 0)),
                scheduled_at,
                duration_minutes=int(item.get("duration_minutes") or 60),
                workout_plan=int(item.get("workout_plan_id") or 0) or None,
                status=item.get("status") or "scheduled",
                notes=item.get("notes") or "",
            )
            created.append({
                "id": class_schedule.pk,
                "athlete_name": class_schedule.athlete.user.get_full_name(),
                "scheduled_at": class_schedule.scheduled_at.strftime("%Y-%m-%d %H:%M"),
            })
        except (TypeError, ValueError, PermissionDenied, ValidationError) as exc:
            errors.append({"index": index, "error": _exception_message(exc)})

    result = {"success": not errors, "created": created, "errors": errors, "message": f"{len(created)} aula(s) agendada(s)."}
    return _tool_json_response("bulk_schedule_classes", payload, result, entity_type="class_schedule")


def reschedule_class(
    class_id: int,
    scheduled_date: str,
    scheduled_time: str,
    duration_minutes: int = 0,
) -> str:
    """Remarca uma aula existente para nova data e horário.

    Args:
        class_id: ID da aula.
        scheduled_date: Nova data no formato YYYY-MM-DD.
        scheduled_time: Novo horário no formato HH:MM.
        duration_minutes: Nova duração, 0 mantém a duração atual.

    Returns:
        JSON com a aula remarcada.
    """
    return update_class.invoke({
        "class_id": class_id,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
        "duration_minutes": duration_minutes,
        "status": "",
        "workout_plan_id": -1,
        "notes": "",
        "athlete_id": 0,
    })


# ---------------------------------------------------------------------------
# TOOLS: Sessão de treino
# ---------------------------------------------------------------------------

def _serialize_workout_session(session) -> dict[str, Any]:
    logs = []
    for set_log in session.set_logs.select_related("exercise", "exercise__exercise_ref").order_by("exercise__exercise_order", "set_number"):
        logs.append({
            "id": set_log.pk,
            "exercise_id": set_log.exercise_id,
            "exercise": set_log.exercise.display_name,
            "set_number": set_log.set_number,
            "target_reps": set_log.target_reps,
            "actual_reps": set_log.actual_reps,
            "load_kg": float(set_log.load_kg) if set_log.load_kg is not None else None,
            "rpe": float(set_log.rpe) if set_log.rpe is not None else None,
            "rir": float(set_log.rir) if set_log.rir is not None else None,
            "notes": set_log.notes,
        })

    return {
        "id": session.pk,
        "workout_id": session.workout_id,
        "workout": session.workout.name,
        "athlete_id": session.athlete_id,
        "athlete_name": session.athlete.user.get_full_name(),
        "status": session.status,
        "started_at": session.started_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "duration_minutes": session.duration_minutes,
        "notes": session.notes,
        "set_logs": logs,
    }


def start_workout_session(workout_id: int) -> str:
    """Inicia uma sessão de treino para o treinador conduzir na academia.

    Args:
        workout_id: ID do treino.

    Returns:
        JSON com a sessão ativa.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"workout_id": workout_id}

    try:
        session = WorkoutExecutionService.start_session(trainer, workout_id)
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("start_workout_session", payload, {"error": _exception_message(exc)}, entity_type="workout", entity_id=workout_id)

    result = {"success": True, "session": _serialize_workout_session(session), "message": f"Sessão #{session.pk} iniciada."}
    return _tool_json_response("start_workout_session", payload, result, entity_type="workout_session", entity_id=session.pk)


def get_active_workout_session(workout_id: int) -> str:
    """Retorna a sessão ativa de um treino, se existir.

    Args:
        workout_id: ID do treino.

    Returns:
        JSON com a sessão ativa ou indicação de ausência.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"workout_id": workout_id}

    try:
        session = WorkoutExecutionService.get_active_session(trainer, workout_id)
    except (PermissionDenied, ValidationError) as exc:
        return json.dumps({"error": _exception_message(exc)}, ensure_ascii=False)

    if session is None:
        return json.dumps({"workout_id": workout_id, "has_active_session": False}, ensure_ascii=False)
    return json.dumps({"workout_id": workout_id, "has_active_session": True, "session": _serialize_workout_session(session)}, ensure_ascii=False)


def log_workout_set(
    session_id: int,
    prescription_id: int,
    actual_reps: int,
    load_kg: float | None = None,
    rpe: float | None = None,
    rir: float | None = None,
    notes: str = "",
) -> str:
    """Registra uma série executada em uma sessão de treino.

    Args:
        session_id: ID da sessão ativa.
        prescription_id: ID da prescrição do exercício.
        actual_reps: Repetições realizadas.
        load_kg: Carga usada, se houver.
        rpe: Esforço percebido de 1 a 10, se informado.
        rir: Repetições em reserva de 0 a 10, se informado.
        notes: Observações da série.

    Returns:
        JSON com a série registrada.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {
        "session_id": session_id,
        "prescription_id": prescription_id,
        "actual_reps": actual_reps,
        "load_kg": load_kg,
        "rpe": rpe,
        "rir": rir,
        "notes": notes,
    }

    try:
        set_log = WorkoutExecutionService.log_set(
            trainer,
            session_id,
            prescription_id,
            actual_reps=actual_reps,
            load_kg=load_kg,
            rpe=rpe,
            rir=rir,
            notes=notes,
        )
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("log_workout_set", payload, {"error": _exception_message(exc)}, entity_type="workout_set_log")

    result = {
        "success": True,
        "id": set_log.pk,
        "session_id": set_log.session_id,
        "exercise": set_log.exercise.display_name,
        "set_number": set_log.set_number,
        "actual_reps": set_log.actual_reps,
        "load_kg": float(set_log.load_kg) if set_log.load_kg is not None else None,
        "rpe": float(set_log.rpe) if set_log.rpe is not None else None,
        "rir": float(set_log.rir) if set_log.rir is not None else None,
        "message": f"Série {set_log.set_number} registrada para {set_log.exercise.display_name}.",
    }
    return _tool_json_response("log_workout_set", payload, result, entity_type="workout_set_log", entity_id=set_log.pk)


def finish_workout_session(session_id: int, notes: str = "") -> str:
    """Finaliza uma sessão de treino em andamento.

    Args:
        session_id: ID da sessão.
        notes: Observações finais da sessão.

    Returns:
        JSON com a sessão finalizada.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)
    payload = {"session_id": session_id, "notes": notes}

    try:
        session = WorkoutExecutionService.finish_session(trainer, session_id, notes=notes)
    except (PermissionDenied, ValidationError) as exc:
        return _tool_json_response("finish_workout_session", payload, {"error": _exception_message(exc)}, entity_type="workout_session", entity_id=session_id)

    result = {"success": True, "session": _serialize_workout_session(session), "message": f"Sessão #{session.pk} finalizada."}
    return _tool_json_response("finish_workout_session", payload, result, entity_type="workout_session", entity_id=session.pk)


def summarize_workout_session(session_id: int) -> str:
    """Resume volume, séries e duração de uma sessão de treino.

    Args:
        session_id: ID da sessão.

    Returns:
        JSON com resumo operacional da sessão.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        session = WorkoutExecutionService._resolve_session(trainer, session_id)
    except PermissionDenied as exc:
        return json.dumps({"error": _exception_message(exc)}, ensure_ascii=False)

    logs = list(session.set_logs.select_related("exercise", "exercise__exercise_ref"))
    total_sets = len(logs)
    total_reps = sum(log.actual_reps for log in logs)
    total_volume = sum(float(log.load_kg or 0) * log.actual_reps for log in logs)
    exercises = {}
    for set_log in logs:
        entry = exercises.setdefault(set_log.exercise_id, {
            "exercise_id": set_log.exercise_id,
            "exercise": set_log.exercise.display_name,
            "sets": 0,
            "reps": 0,
            "volume_kg": 0.0,
        })
        entry["sets"] += 1
        entry["reps"] += set_log.actual_reps
        entry["volume_kg"] += float(set_log.load_kg or 0) * set_log.actual_reps

    result = {
        "session_id": session.pk,
        "workout": session.workout.name,
        "athlete_name": session.athlete.user.get_full_name(),
        "status": session.status,
        "duration_minutes": session.duration_minutes,
        "total_sets": total_sets,
        "total_reps": total_reps,
        "total_volume_kg": round(total_volume, 2),
        "exercises": list(exercises.values()),
    }
    return json.dumps(result, ensure_ascii=False)


def suggest_next_loads_from_session(session_id: int, default_step_kg: float = 2.5) -> str:
    """Sugere próximas cargas com base em uma sessão registrada.

    Args:
        session_id: ID da sessão.
        default_step_kg: Incremento base em kg para exercícios de membros superiores.

    Returns:
        JSON com sugestões não aplicadas de progressão de carga.
    """
    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    try:
        session = WorkoutExecutionService._resolve_session(trainer, session_id)
    except PermissionDenied as exc:
        return json.dumps({"error": _exception_message(exc)}, ensure_ascii=False)

    suggestions = []
    prescriptions = session.workout.exercises.select_related("exercise_ref").prefetch_related("execution_logs")
    for prescription in prescriptions:
        logs = list(session.set_logs.filter(exercise=prescription).order_by("set_number"))
        if not logs:
            continue

        logged_loads = [float(log.load_kg) for log in logs if log.load_kg is not None]
        if not logged_loads:
            continue

        latest_load = logged_loads[-1]
        rpe_values = [float(log.rpe) for log in logs if log.rpe is not None]
        rir_values = [float(log.rir) for log in logs if log.rir is not None]
        average_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None
        average_rir = sum(rir_values) / len(rir_values) if rir_values else None
        lower_body_groups = {"quadriceps", "hamstrings", "glutes", "calves"}
        muscle_group = prescription.exercise_ref.muscle_group if prescription.exercise_ref else ""
        step = 5.0 if muscle_group in lower_body_groups else float(default_step_kg or 2.5)

        should_progress = False
        reason = "Manter carga e observar consistência."
        if average_rir is not None and average_rir >= 2:
            should_progress = True
            reason = "RIR médio indica margem para progressão."
        elif average_rpe is not None and average_rpe <= 7.5:
            should_progress = True
            reason = "RPE médio moderado indica margem para progressão."

        suggested_load = latest_load + step if should_progress else latest_load
        suggestions.append({
            "prescription_id": prescription.pk,
            "exercise": prescription.display_name,
            "current_load_kg": float(prescription.current_load_kg) if prescription.current_load_kg is not None else None,
            "session_load_kg": latest_load,
            "suggested_next_load_kg": round(suggested_load, 2),
            "average_rpe": round(average_rpe, 1) if average_rpe is not None else None,
            "average_rir": round(average_rir, 1) if average_rir is not None else None,
            "reason": reason,
        })

    return json.dumps({"session_id": session.pk, "suggestions": suggestions}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TOOLS: Aluno
# ---------------------------------------------------------------------------

def _student_workout_queryset(profile):
    return WorkoutPlan.objects.filter(athlete=profile, is_archived=False)


def _serialize_workout_for_student(workout) -> dict[str, Any]:
    return {
        "id": workout.pk,
        "name": workout.name,
        "plan": workout.plan.name if workout.plan else None,
        "plan_id": workout.plan_id,
        "objective": workout.objective,
        "origin": workout.origin,
        "is_active": workout.is_active,
        "exercise_count": workout.exercises.count(),
    }


def student_get_today() -> str:
    """Retorna o resumo do dia para o aluno autenticado.

    Returns:
        JSON com próximo treino, próxima aula, progresso recente e estado do vínculo.
    """
    context = _get_tool_context()
    _, profile = _get_student_profile_from_context(context)
    now = timezone.now()

    next_class = ClassSchedule.objects.filter(athlete=profile, scheduled_at__gte=now).select_related("workout_plan", "trainer").order_by("scheduled_at").first()
    suggested_workout = _student_workout_queryset(profile).filter(is_active=True).select_related("plan").prefetch_related("exercises").order_by("name").first()
    recent_updates = LoadUpdate.objects.filter(exercise__workout__athlete=profile).select_related("exercise").order_by("-created_at")[:5]

    return json.dumps({
        "athlete_id": profile.pk,
        "relationship_status": profile.relationship_status,
        "has_active_trainer": profile.has_active_trainer,
        "trainer_name": profile.trainer.get_full_name() if profile.trainer else None,
        "suggested_workout": _serialize_workout_for_student(suggested_workout) if suggested_workout else None,
        "next_class": {
            "id": next_class.pk,
            "scheduled_at": next_class.scheduled_at.strftime("%Y-%m-%d %H:%M"),
            "trainer_name": next_class.trainer.get_full_name(),
            "workout_plan": next_class.workout_plan.name if next_class.workout_plan else None,
            "status": next_class.status,
        } if next_class else None,
        "recent_load_updates": [
            {
                "exercise": update.exercise.display_name,
                "previous_load_kg": float(update.previous_load_kg) if update.previous_load_kg else None,
                "new_load_kg": float(update.new_load_kg),
                "created_at": update.created_at.isoformat(),
            }
            for update in recent_updates
        ],
    }, ensure_ascii=False)


def student_list_my_workouts(only_active: bool = True, limit: int = 20) -> str:
    """Lista os treinos do aluno autenticado.

    Args:
        only_active: Se True, mostra apenas treinos ativos.
        limit: Máximo de resultados.

    Returns:
        Lista JSON de treinos do aluno.
    """
    context = _get_tool_context()
    _, profile = _get_student_profile_from_context(context)
    workouts = _student_workout_queryset(profile).select_related("plan").prefetch_related("exercises")
    if only_active:
        workouts = workouts.filter(is_active=True)
    return json.dumps([_serialize_workout_for_student(workout) for workout in workouts[:limit]], ensure_ascii=False)


def student_get_workout_detail(workout_id: int) -> str:
    """Retorna detalhes de um treino do aluno autenticado.

    Args:
        workout_id: ID do treino.

    Returns:
        JSON com exercícios prescritos, alternativas e parâmetros.
    """
    context = _get_tool_context()
    _, profile = _get_student_profile_from_context(context)
    workout = _student_workout_queryset(profile).select_related("plan").prefetch_related("exercises__exercise_ref", "exercises__alternatives__exercise_ref").filter(pk=workout_id).first()
    if workout is None:
        return json.dumps({"error": f"Treino com ID {workout_id} não encontrado."}, ensure_ascii=False)

    exercises = []
    for prescription in workout.exercises.select_related("exercise_ref").prefetch_related("alternatives__exercise_ref").all():
        exercises.append({
            "prescription_id": prescription.pk,
            "name": prescription.display_name,
            "sets": prescription.sets,
            "reps": prescription.reps,
            "load_kg": float(prescription.current_load_kg) if prescription.current_load_kg else None,
            "rest_seconds": prescription.rest_seconds,
            "order": prescription.exercise_order,
            "notes": prescription.notes,
            "muscle_group": prescription.muscle_group_label,
            "equipment": prescription.equipment_label,
            "alternatives": [
                {
                    "id": alternative.pk,
                    "exercise_id": alternative.exercise_ref_id,
                    "exercise": alternative.exercise_ref.name,
                    "notes": alternative.notes,
                }
                for alternative in prescription.alternatives.all()
            ],
        })

    result = _serialize_workout_for_student(workout)
    result["exercises"] = exercises
    return json.dumps(result, ensure_ascii=False)


def student_start_workout_session(workout_id: int) -> str:
    """Inicia uma sessão de treino para o aluno autenticado.

    Args:
        workout_id: ID do treino do aluno.

    Returns:
        JSON com a sessão ativa.
    """
    context = _get_tool_context()
    _, profile = _get_student_profile_from_context(context)
    workout = _student_workout_queryset(profile).filter(pk=workout_id).first()
    payload = {"workout_id": workout_id}
    if workout is None:
        return _tool_json_response("student_start_workout_session", payload, {"error": f"Treino com ID {workout_id} não encontrado."}, entity_type="workout", entity_id=workout_id)

    session = WorkoutSession.objects.filter(workout=workout, athlete=profile, trainer__isnull=True, status=WorkoutSession.Status.IN_PROGRESS).order_by("-started_at").first()
    if session is None:
        session = WorkoutSession.objects.create(workout=workout, athlete=None)