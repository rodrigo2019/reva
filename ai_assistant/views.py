"""
REVA AI Assistant — API Views.

Real AI-powered endpoints replacing the mocked assistant views.
Supports SSE streaming, voice transcription, context-aware suggestions, and action execution.
"""

import io
import json
import logging
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View

from .models import (
    AUDIO_MODEL_NAME,
    AssistantMessage,
    AssistantSession,
    AudioTranscription,
    calculate_audio_transcription_cost,
)
from .services import AssistantActionService

logger = logging.getLogger("ai_assistant")

# Screen capabilities for context-aware suggestions
SCREEN_CAPABILITIES = {
    "trainer-dashboard": {
        "screen": "Hoje do treinador",
        "suggestions": [
            "Quais sao as tres prioridades de hoje?",
            "Quais alunos precisam de atencao?",
            "Resuma os alertas operacionais",
        ],
    },
    "student-dashboard": {
        "screen": "Student Dashboard",
        "suggestions": [
            "What is my workout for today?",
            "Show my recent progress",
            "How are my load progressions going?",
        ],
    },
    "student-list": {
        "screen": "Student List",
        "suggestions": [
            "Which students are inactive?",
            "Help me organize students",
            "Show overall student statistics",
        ],
    },
    "workout-list": {
        "screen": "Workout List",
        "suggestions": [
            "Create a chest and triceps workout",
            "Suggest a weekly periodization",
            "How should I organize workouts for hypertrophy?",
        ],
    },
    "exercise-catalog": {
        "screen": "Exercise Catalog",
        "suggestions": [
            "Show back exercises",
            "What is the correct squat technique?",
            "Suggest alternatives for the barbell bench press",
        ],
    },
    "my-progress": {
        "screen": "My Progress",
        "suggestions": [
            "How is my bench press progress?",
            "Which exercises improved the most?",
            "What can I improve in my workouts?",
        ],
    },
    "student-detail": {
        "screen": "Student Detail",
        "suggestions": [
            "Show this student's workouts",
            "How is this student's load progression?",
            "Create a new workout for this student",
        ],
    },
    "student-profile": {
        "screen": "Perfil do aluno",
        "suggestions": [
            "Quais dados deste perfil ainda faltam?",
            "Ajude a completar a anamnese",
            "Resuma pontos de atencao do aluno",
        ],
    },
    "schedule": {
        "screen": "Schedule",
        "suggestions": [
            "Show my schedule for this week",
            "Schedule a class for a student",
            "Which students have class today?",
        ],
    },
    "schedule-form": {
        "screen": "Schedule Class",
        "suggestions": [
            "What is the best time to schedule it?",
            "Schedule a 60-minute class for tomorrow",
            "Help me fill out this form",
        ],
    },
    "student-create": {
        "screen": "Link Student",
        "suggestions": [
            "Which email should I use to link this student?",
            "What if the student has not signed up yet?",
        ],
    },
    "student-edit": {
        "screen": "Edit Student",
        "suggestions": [
            "Which notes should I record about this student?",
            "Help me update the information",
        ],
    },
    "student-progress": {
        "screen": "Student Progress",
        "suggestions": [
            "Which exercises improved the most for this student?",
            "How is the load progression going?",
            "Suggest adjustments for the next cycle",
        ],
    },
    "workout-detail": {
        "screen": "Workout Detail",
        "suggestions": [
            "Add an exercise to this workout",
            "How can I optimize the exercise order?",
            "Suggest load and volume adjustments",
        ],
    },
    "plan-list": {
        "screen": "Plan List",
        "suggestions": [
            "Help me create a weekly training plan",
            "How should I structure a periodization?",
            "Show active plans",
        ],
    },
    "plan-detail": {
        "screen": "Detalhe do plano",
        "suggestions": [
            "O que devo revisar neste plano?",
            "Sugira ajustes para o proximo ciclo",
            "Resuma a estrutura do plano",
        ],
    },
    "plan-form": {
        "screen": "Formulario de plano",
        "suggestions": [
            "Ajude a criar um plano semanal",
            "Sugira uma periodizacao inicial",
            "Quais campos devo preencher primeiro?",
        ],
    },
    "default": {
        "screen": "General Page",
        "suggestions": [
            "What can you do for me?",
            "Help me with my workouts",
            "Show my progress",
        ],
    },
}


def _get_or_create_session(user, screen_id="default"):
    """Get the active assistant session for a user, or create one.

    Each user has one active global assistant session.
    """
    session = (
        AssistantSession.objects.filter(user=user, is_active=True)
        .order_by("-updated_at")
        .first()
    )
    if session is None:
        session = AssistantSession.objects.create(
            user=user,
            title="Conversa com REVA",
            screen_context=screen_id,
        )
    else:
        # Update screen context if changed
        if session.screen_context != screen_id:
            session.screen_context = screen_id
            session.save(update_fields=["screen_context", "updated_at"])
    return session


def _get_orchestrator(screen_context="default", user_id=None, session_id=None):
    """Create a new AssistantOrchestrator instance."""
    from ai_assistant.core.assistant import AssistantOrchestrator

    return AssistantOrchestrator(
        screen_context=screen_context,
        user_id=user_id,
        assistant_session_id=session_id,
    )


@method_decorator(login_required, name="dispatch")
class AssistantSendMessageView(View):
    """Receive a text message and return an AI-powered response via SSE streaming."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        message = body.get("message", "").strip()
        screen_id = body.get("screen_id", "default")
        page_context = body.get("page_context")  # dict from JS capturePageContext()

        if not message:
            return JsonResponse({"error": "Empty message"}, status=400)

        # Get or create session
        session = _get_or_create_session(request.user, screen_id)

        # Save user message
        AssistantMessage.objects.create(
            session=session,
            content=message,
            sender=AssistantMessage.SenderChoices.USER,
            screen_id=screen_id,
        )

        # Check if SSE streaming is requested
        accept = request.headers.get("Accept", "")
        if "text/event-stream" in accept:
            return self._stream_response(session, message, screen_id, request.user.pk, page_context)
        return self._json_response(session, message, screen_id, request.user.pk, page_context)

    def _stream_response(self, session, message, screen_id, user_id, page_context):
        """Return an SSE streaming response."""

        def event_stream():
            full_response = []
            input_tokens = 0
            output_tokens = 0

            try:
                orchestrator = _get_orchestrator(screen_context=screen_id, user_id=user_id, session_id=session.pk)
                thread_id = str(session.uuid_code)

                for chunk in orchestrator.stream_chat(
                    user_message=message,
                    thread_id=thread_id,
                    page_context=page_context,
                ):
                    chunk_type = chunk.get("type", "")
                    content = chunk.get("content", "")

                    if chunk_type == "response" and content:
                        full_response.append(content)
                        data = json.dumps({"text": content})
                        yield f"data: {data}\n\n"
                    elif chunk_type == "reasoning" and content:
                        data = json.dumps({"reasoning": content})
                        yield f"event: reasoning\ndata: {data}\n\n"
                    elif chunk_type == "tool_call" and content:
                        data = json.dumps({"tool_call": content})
                        yield f"data: {data}\n\n"
                    elif chunk_type == "tool_result" and content:
                        data = json.dumps({"tool_result": content})
                        yield f"data: {data}\n\n"

                input_tokens = orchestrator.last_input_tokens
                output_tokens = orchestrator.last_output_tokens

            except Exception as e:
                logger.exception("Error streaming assistant response: %s", e)
                error_msg = "Sorry, I ran into a problem processing your message. Please try again."
                full_response.append(error_msg)
                data = json.dumps({"text": error_msg})
                yield f"data: {data}\n\n"

            # Save assistant message
            final_content = "".join(full_response)
            if final_content:
                AssistantMessage.objects.create(
                    session=session,
                    content=final_content,
                    sender=AssistantMessage.SenderChoices.ASSISTANT,
                    screen_id=session.screen_context,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            yield "event: end\ndata: end\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    def _json_response(self, session, message, screen_id, user_id, page_context):
        """Return a standard JSON response (non-streaming fallback)."""
        try:
            orchestrator = _get_orchestrator(screen_context=screen_id, user_id=user_id, session_id=session.pk)
            thread_id = str(session.uuid_code)

            result = orchestrator.invoke_chat(
                user_message=message,
                thread_id=thread_id,
                page_context=page_context,
            )

            content = result.get("content", "")
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)

            # Save assistant message
            if content:
                AssistantMessage.objects.create(
                    session=session,
                    content=content,
                    sender=AssistantMessage.SenderChoices.ASSISTANT,
                    screen_id=session.screen_context,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        except Exception as e:
            logger.exception("Error generating assistant response: %s", e)
            content = "Sorry, I ran into a problem processing your message. Please try again."

        return JsonResponse({
            "id": f"msg_{int(time.time() * 1000)}",
            "role": "assistant",
            "content": content,
            "screen_id": screen_id,
            "actions": [],
            "timestamp": time.time(),
        })


@method_decorator(login_required, name="dispatch")
class AssistantVoiceMessageView(View):
    """Receive audio, transcribe it with Azure OpenAI, and return AI response."""

    def post(self, request):
        audio_file = request.FILES.get("audio")
        screen_id = request.POST.get("screen_id", "default")

        if not audio_file:
            return JsonResponse({"error": "No audio received"}, status=400)

        session = _get_or_create_session(request.user, screen_id)

        try:
            # Transcribe audio using Azure OpenAI
            transcription = self._transcribe_audio(request.user, session, audio_file)

            if not transcription:
                return JsonResponse({
                    "id": f"msg_{int(time.time() * 1000)}",
                    "role": "assistant",
                    "transcription": "",
                    "content": "I couldn't understand the audio. Please try again or type your message.",
                    "screen_id": screen_id,
                    "actions": [],
                    "timestamp": time.time(),
                })

            # Save user message (transcribed text)
            AssistantMessage.objects.create(
                session=session,
                content=transcription,
                sender=AssistantMessage.SenderChoices.USER,
                screen_id=screen_id,
                metadata={"source": "voice"},
            )

            # Generate AI response
            orchestrator = _get_orchestrator(screen_context=screen_id, user_id=request.user.pk, session_id=session.pk)
            thread_id = str(session.uuid_code)
            result = orchestrator.invoke_chat(
                user_message=transcription,
                thread_id=thread_id,
            )

            content = result.get("content", "")
            if content:
                AssistantMessage.objects.create(
                    session=session,
                    content=content,
                    sender=AssistantMessage.SenderChoices.ASSISTANT,
                    screen_id=screen_id,
                    input_tokens=result.get("input_tokens", 0),
                    output_tokens=result.get("output_tokens", 0),
                )

            return JsonResponse({
                "id": f"msg_{int(time.time() * 1000)}",
                "role": "assistant",
                "transcription": transcription,
                "content": content,
                "screen_id": screen_id,
                "actions": [],
                "timestamp": time.time(),
            })

        except Exception as e:
            logger.exception("Error processing voice message: %s", e)
            return JsonResponse({
                "id": f"msg_{int(time.time() * 1000)}",
                "role": "assistant",
                "transcription": "",
                "content": "There was a problem processing the voice message. Please try again.",
                "screen_id": screen_id,
                "actions": [],
                "timestamp": time.time(),
            })

    def _transcribe_audio(self, user, session, audio_file):
        """Transcribe audio using Azure OpenAI and persist an AudioTranscription record.

        Based on the ai_engine AudioTranscriptionView pattern — reads audio into
        memory, sends via BytesIO with ``response_format="json"``, and tracks
        input/output tokens and cost.

        Args:
            user: The requesting user.
            session: The assistant session.
            audio_file: The uploaded audio file (InMemoryUploadedFile / TemporaryUploadedFile).

        Returns:
            Transcribed text string, or empty string on failure.
        """
        try:
            from openai import AzureOpenAI

            api_key = getattr(settings, "AZURE_OPENAI_API_KEY", "")
            endpoint = getattr(settings, "AZURE_OPENAI_ENDPOINT", "")
            transcription_model = getattr(settings, "AI_TRANSCRIPTION_MODEL", AUDIO_MODEL_NAME)

            if not api_key or not endpoint:
                logger.warning("Azure OpenAI credentials not configured for transcription")
                return ""

            # Read the audio content into memory once
            audio_data = audio_file.read()
            if not audio_data:
                logger.warning("Empty audio file received")
                return ""

            audio_name = getattr(audio_file, "name", "audio.webm")
            audio_content_type = getattr(audio_file, "content_type", "audio/webm")
            audio_size = len(audio_data)

            # Create a BytesIO buffer with a name attribute (required by the OpenAI SDK)
            buffer = io.BytesIO(audio_data)
            buffer.name = audio_name

            client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version="2025-04-01-preview",
            )

            try:
                resp = client.audio.transcriptions.create(
                    model=transcription_model,
                    file=buffer,
                    response_format="json",
                )
            finally:
                try:
                    client.close()
                except Exception:
                    pass

            transcription_text = getattr(resp, "text", None) or ""
            transcription_text = transcription_text.strip()

            # Extract token usage from the response
            usage = getattr(resp, "usage", None)
            input_tokens = 0
            output_tokens = 0
            if usage is not None:
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0

            # Persist AudioTranscription record with the audio saved via ContentFile
            transcription = AudioTranscription(
                user=user,
                session=session,
                content=transcription_text,
                audio_content_type=audio_content_type,
                audio_size=audio_size,
                model_name=transcription_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            transcription.audio_file.save(audio_name, ContentFile(audio_data), save=False)
            transcription.save()

            # Log cost information
            if input_tokens or output_tokens:
                cost = calculate_audio_transcription_cost(input_tokens, output_tokens)
                logger.info(
                    "Audio transcribed: %d chars, cost=$%.6f (in=%d, out=%d) for user %s",
                    len(transcription_text),
                    cost,
                    input_tokens,
                    output_tokens,
                    user,
                )
            else:
                logger.info("Audio transcribed: %d chars (no usage data) for user %s", len(transcription_text), user)

            return transcription_text

        except ImportError:
            logger.warning("openai package not installed — audio transcription unavailable")
            return ""
        except Exception as e:
            logger.exception("Audio transcription failed: %s", e)
            return ""


@method_decorator(login_required, name="dispatch")
class AssistantContextView(View):
    """Return contextual information and suggestions based on the current screen."""

    def get(self, request):
        screen_id = request.GET.get("screen_id", "default")
        context = SCREEN_CAPABILITIES.get(screen_id, SCREEN_CAPABILITIES["default"])

        return JsonResponse({
            "screen_id": screen_id,
            "screen_name": context["screen"],
            "suggestions": context["suggestions"],
            "recent_actions": AssistantActionService.recent_actions_for_user(request.user),
            "user": {
                "name": request.user.get_full_name() or request.user.username,
                "role": "trainer" if request.user.is_trainer else "student",
            },
        })


@method_decorator(login_required, name="dispatch")
class AssistantExecuteActionView(View):
    """Execute an action suggested by the assistant.

    Currently returns success — will be connected to real tools in the future.
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        action_type = body.get("action_type", "")
        action_params = body.get("params", {})
        screen_id = body.get("screen_id", "default")
        session = _get_or_create_session(request.user, screen_id)

        result = AssistantActionService.execute_client_action(
            user=request.user,
            session=session,
            action_type=action_type,
            params=action_params,
            screen_id=screen_id,
        )
        result["action_type"] = action_type
        return JsonResponse(result)


@method_decorator(login_required, name="dispatch")
class AssistantClearView(View):
    """Clear the current assistant session and start fresh."""

    def post(self, request):
        # Deactivate current session
        AssistantSession.objects.filter(user=request.user, is_active=True).update(
            is_active=False
        )

        return JsonResponse({
            "success": True,
            "message": "Conversation cleared successfully.",
        })
