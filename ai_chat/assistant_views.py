"""
Mocked API endpoints for the REVA global assistant.
All responses simulate realistic AI assistant behaviour but use hardcoded data.
"""
import json
import time
import random

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required


MOCKED_RESPONSES = {
    "greeting": [
        "Hi! 👋 I'm REVA, your assistant. How can I help today?",
        "Hello! I'm here to help. What do you need?",
        "Hey! Ready to help. Just tell me what you need! 💪",
    ],
    "workout": [
        "Analyzing your workouts... You have 3 active workouts this week. Want me to show the details of one?",
        "I noticed your last workout was 2 days ago. How about training today? I can show the next one in the sequence.",
        "Your bench press progress looks great! You added 5 kg over the last 3 weeks. Keep it up! 🔥",
    ],
    "exercise": [
        "I found 24 exercises in the catalog. I can filter by muscle group if you want.",
        "Proper squat form means keeping your feet shoulder-width apart, your back straight, and lowering until your thighs are parallel to the floor.",
        "For hypertrophy, 8-12 reps with moderate to high load is usually recommended. Want me to adjust a workout?",
    ],
    "progress": [
        "Your overall progress is positive! 📈 In the last 4 weeks you increased load in 5 exercises.",
        "Reviewing your history... you've been consistent, averaging 4 training sessions per week. Excellent work!",
        "Based on your progress, I suggest increasing your leg press load by 10% in the next session.",
    ],
    "student": [
        "You currently have 12 active students. 3 of them have not logged a workout in more than 5 days.",
        "Student Joao Silva completed 100% of this week's workouts. Great highlight! ⭐",
        "I can generate an attendance report for your students. Which period do you want?",
    ],
    "general": [
        "Got it. Let me process that... I can help with workouts, exercises, student progress, and more. What would you like first?",
        "Good question. Based on the platform data, I can give you a detailed analysis. Want me to go deeper?",
        "Alright, I'll check that for you. In the meantime, remember that you can ask me to create workouts, log progress, and more.",
    ],
}

SCREEN_CAPABILITIES = {
    "trainer-dashboard": {
        "screen": "Coach Dashboard",
        "actions": ["ver_resumo_alunos", "criar_treino", "ver_progresso_geral"],
        "suggestions": [
            "Show a summary of my students",
            "Which students missed training this week?",
            "Create a new workout",
        ],
    },
    "student-dashboard": {
        "screen": "Student Dashboard",
        "actions": ["ver_treino_hoje", "registrar_progresso", "ver_historico"],
        "suggestions": [
            "What is my workout for today?",
            "Show my recent progress",
            "I want to log my training",
        ],
    },
    "student-list": {
        "screen": "Student List",
        "actions": ["buscar_aluno", "adicionar_aluno", "ver_estatisticas"],
        "suggestions": [
            "Which students are inactive?",
            "Add a new student",
            "Show overall statistics",
        ],
    },
    "workout-list": {
        "screen": "Workout List",
        "actions": ["criar_treino", "duplicar_treino", "filtrar_treinos"],
        "suggestions": [
            "Create a chest and triceps workout",
            "Show the most recent workouts",
            "Duplicate the last workout",
        ],
    },
    "exercise-catalog": {
        "screen": "Exercise Catalog",
        "actions": ["buscar_exercicio", "adicionar_exercicio", "filtrar_grupo"],
        "suggestions": [
            "Show back exercises",
            "Add a new exercise",
            "What is the best exercise for glutes?",
        ],
    },
    "my-progress": {
        "screen": "My Progress",
        "actions": ["ver_evolucao", "comparar_periodos", "exportar_dados"],
        "suggestions": [
            "How is my bench press progress?",
            "Compare last month with this month",
            "Which exercises improved the most?",
        ],
    },
    "default": {
        "screen": "General Page",
        "actions": ["navegar", "buscar", "ajuda"],
        "suggestions": [
            "What can you do for me?",
            "Take me to my workouts",
            "Show my progress",
        ],
    },
}


def _classify_intent(message: str) -> str:
    """Simple keyword-based intent classification (mocked)."""
    msg = message.lower()
    if any(w in msg for w in ["olá", "oi", "hey", "hello", "hi", "bom dia", "boa tarde", "boa noite", "e aí"]):
        return "greeting"
    if any(w in msg for w in ["treino", "workout", "series", "série", "session", "sessão", "treinar", "train"]):
        return "workout"
    if any(w in msg for w in ["exercício", "exercicio", "exercise", "bench", "supino", "squat", "agachamento", "execution", "execução"]):
        return "exercise"
    if any(w in msg for w in ["progresso", "progress", "evolução", "carga", "load", "resultado", "result", "desempenho", "performance"]):
        return "progress"
    if any(w in msg for w in ["aluno", "alunos", "student", "students", "estudante", "atleta"]):
        return "student"
    return "general"


@method_decorator(login_required, name="dispatch")
class AssistantSendMessageView(View):
    """Receive a text message and return a mocked assistant response."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        message = body.get("message", "").strip()
        screen_id = body.get("screen_id", "default")

        if not message:
            return JsonResponse({"error": "Empty message"}, status=400)

        intent = _classify_intent(message)
        response_text = random.choice(MOCKED_RESPONSES[intent])

        # Simulate potential actions the assistant would take
        actions_taken = []
        if intent == "workout" and "crie" in message.lower():
            actions_taken.append({
                "type": "navigate",
                "url": "/workouts/new/",
                "label": "Create new workout",
            })
        elif intent == "progress":
            actions_taken.append({
                "type": "navigate",
                "url": "/progress/mine/",
                "label": "View progress",
            })

        return JsonResponse({
            "id": f"msg_{int(time.time() * 1000)}",
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "screen_id": screen_id,
            "actions": actions_taken,
            "timestamp": time.time(),
        })


@method_decorator(login_required, name="dispatch")
class AssistantVoiceMessageView(View):
    """Receive an audio blob and return a mocked transcription + response."""

    def post(self, request):
        audio_file = request.FILES.get("audio")
        screen_id = request.POST.get("screen_id", "default")

        if not audio_file:
            return JsonResponse({"error": "No audio received"}, status=400)

        # Mocked transcription
        mocked_transcriptions = [
            "What is my workout for today?",
            "Show my bench press progress",
            "I want to create a new workout",
            "How is my students' attendance?",
        ]
        transcription = random.choice(mocked_transcriptions)
        intent = _classify_intent(transcription)
        response_text = random.choice(MOCKED_RESPONSES[intent])

        return JsonResponse({
            "id": f"msg_{int(time.time() * 1000)}",
            "role": "assistant",
            "transcription": transcription,
            "content": response_text,
            "intent": intent,
            "screen_id": screen_id,
            "actions": [],
            "timestamp": time.time(),
        })


@method_decorator(login_required, name="dispatch")
class AssistantContextView(View):
    """Return contextual information and suggestions based on the current screen."""

    def get(self, request):
        screen_id = request.GET.get("screen_id", "default")
        context = SCREEN_CAPABILITIES.get(screen_id, SCREEN_CAPABILITIES["default"])

        return JsonResponse({
            "screen_id": screen_id,
            "screen_name": context["screen"],
            "available_actions": context["actions"],
            "suggestions": context["suggestions"],
            "user": {
                "name": request.user.get_full_name() or request.user.username,
                "role": "trainer" if request.user.is_trainer else "student",
            },
        })


@method_decorator(login_required, name="dispatch")
class AssistantExecuteActionView(View):
    """Mocked endpoint to execute an action suggested by the assistant."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        action_type = body.get("action_type", "")
        action_params = body.get("params", {})

        # All actions are mocked — just return success
        return JsonResponse({
            "success": True,
            "action_type": action_type,
            "message": f"Action '{action_type}' executed successfully (mocked).",
            "result": {
                "action_type": action_type,
                "params": action_params,
                "executed_at": time.time(),
            },
        })
