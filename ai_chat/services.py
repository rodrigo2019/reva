import os

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from workouts.models import LoadUpdate


def _build_progress_context(athlete):
    updates = (
        LoadUpdate.objects.filter(exercise__workout__athlete=athlete)
        .select_related("exercise")
        .order_by("-created_at")[:8]
    )
    if not updates:
        return "Sem histórico de carga registrado até o momento."

    lines = []
    for item in updates:
        previous = f"{item.previous_load_kg}kg" if item.previous_load_kg is not None else "início"
        lines.append(f"- {item.exercise.name}: {previous} -> {item.new_load_kg}kg em {item.created_at:%d/%m}")
    return "\n".join(lines)


def generate_contextual_reply(athlete, question):
    progress_context = _build_progress_context(athlete)
    system_prompt = (
        "Você é o assistente do treinador REVA. Responda em português brasileiro, "
        "de forma objetiva, segura e motivadora, sem prescrever condutas médicas."
        f"\n\nContexto recente do aluno:\n{progress_context}"
    )

    model_name = os.getenv("REVA_LLM_MODEL", "openai:gpt-4o-mini")
    try:
        llm = init_chat_model(model_name)
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=question)])
        return response.content
    except Exception:
        return (
            "Pelo histórico recente, sua evolução parece consistente. "
            "Mantenha a técnica correta e alinhe qualquer aumento de carga com seu treinador."
        )
