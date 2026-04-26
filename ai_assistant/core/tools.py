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
from typing import Any

from langchain_core.tools import tool

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
    from django.forms.models import model_to_dict

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


def _get_trainer_from_context(context: dict) -> Any:
    """Retrieve the trainer User object from the tool context.

    The context must contain user_id set by the orchestrator.
    """
    from accounts.models import User

    user_id = context.get("user_id")
    if not user_id:
        raise ValueError("Contexto de usuário ausente — não é possível identificar o treinador.")
    user = User.objects.get(pk=user_id)
    if not getattr(user, "is_trainer", False):
        raise PermissionError("As ferramentas operacionais da REVA estão disponíveis apenas para treinadores.")
    return user


def _active_athletes_for_trainer(trainer):
    from athletes.models import Athlete, StudentRelationshipStatus

    return Athlete.objects.filter(
        trainer=trainer,
        relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _active_training_plans_for_trainer(trainer):
    from athletes.models import StudentRelationshipStatus
    from workouts.models import TrainingPlan

    return TrainingPlan.objects.filter(
        created_by=trainer,
        athlete__trainer=trainer,
        athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _active_workouts_for_trainer(trainer):
    from athletes.models import StudentRelationshipStatus
    from workouts.models import WorkoutPlan

    return WorkoutPlan.objects.filter(
        created_by=trainer,
        athlete__trainer=trainer,
        athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
    )


def _active_classes_for_trainer(trainer):
    from athletes.models import StudentRelationshipStatus
    from schedule.models import ClassSchedule

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


def _tool_json_response(
    tool_name: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    *,
    entity_type: str = "",
    entity_id: Any = "",
) -> str:
    from ai_assistant.services import safe_record_tool_execution

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

@tool
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
    from athletes.models import Athlete

    context = _get_tool_context()
    trainer = _get_trainer_from_context(context)

    from django.db.models import Q

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

@tool
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
    from django.core.exceptions import PermissionDenied, ValidationError

    from athletes.services import AthleteService

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

@tool
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
    from athletes.models import Athlete

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

@tool
def delete_athlete(athlete_id: int) -> str:
    """Encerra o vínculo operacional com um aluno, preservando conta e histórico.

    Args:
        athlete_id: ID do aluno a excluir (obrigatório).

    Returns:
        JSON confirmando a exclusão.
    """
    from athletes.services import AthleteService

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

@tool
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
    from workouts.models import Exercise

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

@tool
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
    from workouts.models import Exercise

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

@tool
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
    from workouts.models import TrainingPlan

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

@tool
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
    from django.core.exceptions import PermissionDenied, ValidationError

    from workouts.services import WorkoutService

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

@tool
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
    from workouts.models import WorkoutPlan

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

@tool
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
    from django.core.exceptions import PermissionDenied, ValidationError

    from workouts.services import WorkoutService

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

@tool
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
    from workouts.models import Exercise, ExercisePrescription, WorkoutPlan

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
        from django.db.models import Q
        try:
            exercise_ref = Exercise.objects.get(Q(is_global=True) | Q(created_by=trainer), pk=exercise_id)
        except Exercise.DoesNotExist:
            return _tool_json_response("add_exercise_to_workout", payload, {"error": f"Exercício com ID {exercise_id} não encontrado."}, entity_type="exercise_prescription")

    if not exercise_ref and not custom_name:
        return _tool_json_response("add_exercise_to_workout", payload, {"error": "Forneça exercise_id ou custom_name."}, entity_type="exercise_prescription")

    # Determine next order — retry on unique constraint violation (parallel tool calls)
    from django.db import IntegrityError
    from django.db.models import Max

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

@tool
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
    from django.core.exceptions import PermissionDenied, ValidationError

    from workouts.services import WorkoutService

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

@tool
def delete_workout(workout_id: int) -> str:
    """Exclui um treino e todos os exercícios vinculados.

    ATENÇÃO: Esta ação é irreversível.

    Args:
        workout_id: ID do treino a excluir (obrigatório).

    Returns:
        JSON confirmando a exclusão.
    """
    from workouts.models import WorkoutPlan

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

@tool
def get_workout_detail(workout_id: int) -> str:
    """Retorna os detalhes completos de um treino, incluindo todos os exercícios prescritos.

    Args:
        workout_id: ID do treino (obrigatório).

    Returns:
        JSON com dados do treino e lista de exercícios.
    """
    from workouts.models import WorkoutPlan

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

@tool
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
    from athletes.models import Anamnesis, Athlete
    from decimal import Decimal
    from datetime import date as date_type

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

@tool
def get_anamnesis(athlete_id: int) -> str:
    """Retorna a anamnese (ficha de saúde) mais recente de um aluno.

    Args:
        athlete_id: ID do aluno (obrigatório).

    Returns:
        JSON com todos os dados da anamnese ou mensagem indicando que não há anamnese.
    """
    from athletes.models import Athlete

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

@tool
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
    from athletes.models import Athlete, PhysicalAssessment
    from decimal import Decimal
    from datetime import date as date_type

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

@tool
def get_physical_assessment(athlete_id: int) -> str:
    """Retorna a avaliação física mais recente de um aluno com todas as medidas e cálculos.

    Args:
        athlete_id: ID do aluno (obrigatório).

    Returns:
        JSON com todas as medidas, IMC, composição corporal, e classificações.
    """
    from athletes.models import Athlete

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

@tool
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
    from athletes.models import Athlete

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

@tool
def get_athlete_detail(athlete_id: int) -> str:
    """Retorna detalhes completos de um aluno, incluindo treinos e atividade recente.

    Args:
        athlete_id: ID do aluno (obrigatório).

    Returns:
        JSON com dados do aluno, planos, treinos e últimas atualizações.
    """
    from athletes.models import Athlete
    from workouts.models import LoadUpdate

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

@tool
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
    from datetime import date, datetime, timedelta

    from schedule.models import ClassSchedule

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


@tool
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
    from datetime import datetime

    from django.core.exceptions import PermissionDenied, ValidationError

    from schedule.services import ScheduleService

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


@tool
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
    from django.core.exceptions import PermissionDenied, ValidationError

    from schedule.models import ClassSchedule
    from schedule.services import ScheduleService

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
            from datetime import datetime
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


@tool
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
# Collect all tools
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    list_athletes,
    create_athlete,
    update_athlete,
    delete_athlete,
    list_exercises,
    create_exercise,
    list_training_plans,
    create_training_plan,
    list_workouts,
    create_workout,
    add_exercise_to_workout,
    update_exercise_load,
    delete_workout,
    get_workout_detail,
    get_athlete_detail,
    save_anamnesis,
    get_anamnesis,
    save_physical_assessment,
    get_physical_assessment,
    list_physical_assessments,
    list_schedule,
    create_class,
    update_class,
    delete_class,
]


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

    from accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("set_tools_context: user %s not found; tools disabled", user_id)
        return []

    if not getattr(user, "is_trainer", False):
        logger.info("set_tools_context: user %s is not a trainer; tools disabled", user_id)
        return []

    return list(ALL_TOOLS)
