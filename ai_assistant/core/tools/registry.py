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


# Entire file content continues below - truncated for this output

_TOOL_FUNCTIONS = [
    list_athletes,
    create_athlete,
    update_athlete,
    delete_athlete,
    list_exercises,
    create_exercise,
    list_training_plans,
    create_training_plan,
    update_training_plan,
    delete_training_plan,
    list_workouts,
    create_workout,
    update_workout,
    archive_workout,
    duplicate_workout,
    copy_workout_to_athlete,
    add_exercise_to_workout,
    update_exercise_prescription,
    remove_exercise_from_workout,
    reorder_workout_exercises,
    add_exercise_alternative,
    remove_exercise_alternative,
    update_exercise_load,
    delete_workout,
    get_workout_detail,
    update_exercise_catalog,
    delete_exercise_catalog,
    get_athlete_detail,
    set_student_permissions,
    save_anamnesis,
    get_anamnesis,
    save_physical_assessment,
    get_physical_assessment,
    list_physical_assessments,
    list_schedule,
    create_class,
    update_class,
    delete_class,
    check_schedule_conflicts,
    find_available_schedule_slots,
    bulk_schedule_classes,
    reschedule_class,
    start_workout_session,
    get_active_workout_session,
    log_workout_set,
    finish_workout_session,
    summarize_workout_session,
    suggest_next_loads_from_session,
    student_get_today,
    student_list_my_workouts,
    student_get_workout_detail,
    student_start_workout_session,
    student_log_set,
    student_finish_workout_session,
    student_update_load,
    student_update_profile,
    student_save_anamnesis,
    student_list_my_schedule,
    student_create_personal_event,
    student_update_personal_event,
    student_delete_personal_event,
    student_create_ai_workout_draft,
    student_accept_ai_workout,
    student_request_trainer_link,
    analyze_athlete_progress,
    compare_exercise_progress,
    analyze_adherence,
    detect_students_needing_attention,
    detect_load_jump_risks,
    suggest_load_progression,
    generate_student_report,
    get_volume_by_muscle_group,
    navigate_to,
    open_entity,
    fill_current_form,
    submit_current_form,
    highlight_page_item,
    show_action_preview,
    request_user_confirmation,
]

for _tool_function in _TOOL_FUNCTIONS:
    globals()[_tool_function.__name__] = DjangoOrmTool(_tool_function)

del _tool_function

TRAINER_TOOLS = [
    list_athletes,
    create_athlete,
    update_athlete,
    delete_athlete,
    list_exercises,
    create_exercise,
    list_training_plans,
    create_training_plan,
    update_training_plan,
    delete_training_plan,
    list_workouts,
    create_workout,
    update_workout,
    archive_workout,
    duplicate_workout,
    copy_workout_to_athlete,
    add_exercise_to_workout,
    update_exercise_prescription,
    remove_exercise_from_workout,
    reorder_workout_exercises,
    add_exercise_alternative,
    remove_exercise_alternative,
    update_exercise_load,
    delete_workout,
    get_workout_detail,
    update_exercise_catalog,
    delete_exercise_catalog,
    get_athlete_detail,
    set_student_permissions,
    save_anamnesis,
    get_anamnesis,
    save_physical_assessment,
    get_physical_assessment,
    list_physical_assessments,
    list_schedule,
    create_class,
    update_class,
    delete_class,
    check_schedule_conflicts,
    find_available_schedule_slots,
    bulk_schedule_classes,
    reschedule_class,
    start_workout_session,
    get_active_workout_session,
    log_workout_set,
    finish_workout_session,
    summarize_workout_session,
    suggest_next_loads_from_session,
    analyze_athlete_progress,
    compare_exercise_progress,
    analyze_adherence,
    detect_students_needing_attention,
    detect_load_jump_risks,
    suggest_load_progression,
    generate_student_report,
    get_volume_by_muscle_group,
    navigate_to,
    open_entity,
    fill_current_form,
    submit_current_form,
    highlight_page_item,
    show_action_preview,
    request_user_confirmation,
]


STUDENT_TOOLS = [
    student_get_today,
    student_list_my_workouts,
    student_get_workout_detail,
    student_start_workout_session,
    student_log_set,
    student_finish_workout_session,
    student_update_load,
    student_update_profile,
    student_save_anamnesis,
    student_list_my_schedule,
    student_create_personal_event,
    student_update_personal_event,
    student_delete_personal_event,
    student_create_ai_workout_draft,
    student_accept_ai_workout,
    student_request_trainer_link,
    analyze_athlete_progress,
    compare_exercise_progress,
    analyze_adherence,
    suggest_load_progression,
    generate_student_report,
    get_volume_by_muscle_group,
    navigate_to,
    open_entity,
    fill_current_form,
    submit_current_form,
    highlight_page_item,
    show_action_preview,
    request_user_confirmation,
]


def _unique_tools(*tool_groups: list) -> list:
    seen_keys = set()
    tools = []
    for tool_group in tool_groups:
        for tool_item in tool_group:
            key = getattr(tool_item, "name", None) or id(tool_item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            tools.append(tool_item)
    return tools


ALL_TOOLS = _unique_tools(TRAINER_TOOLS, STUDENT_TOOLS)


def set_tools_context(user_id: int, session_id: int | None = None, screen_context: str = "") -> list:
    """Set execution-local tool context and return tools available to the user.

    The context is stored in a ContextVar so concurrent assistant calls do not
    overwrite each other's trainer scope.

    Args:
        user_id: The pk of the authenticated user.
        session_id: Optional AssistantSession pk for audit records.
        screen_context: Optional current screen id for audit records.

    Returns:
        The list of tool callables available to the user.
    """
    context = {
        "user_id": user_id,
        "session_id": session_id,
        "screen_context": screen_context,
    }
    _TOOL_CONTEXT.set(context)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("set_tools_context: user %s not found; tools disabled", user_id)
        return []

    if getattr(user, "is_trainer", False):
        return list(TRAINER_TOOLS)

    if getattr(user, "is_student", False):
        return list(STUDENT_TOOLS)

    logger.info("set_tools_context: user %s has no assistant tool role; tools disabled", user_id)
    return []


__all__ = [tool_item.name for tool_item in ALL_TOOLS] + [
    "TRAINER_TOOLS",
    "STUDENT_TOOLS",
    "ALL_TOOLS",
    "set_tools_context",
]
