"""
Models for the REVA AI Assistant module.

Based on the ai_engine architecture, simplified for the REVA fitness platform.
Provides LLM model configuration, assistant session management, and message persistence.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# Audio Transcription pricing constants (USD per 1M tokens)
# ---------------------------------------------------------------------------
AUDIO_MODEL_NAME = "gpt-4o-transcribe"
AUDIO_INPUT_PRICE_PER_1M_TOKENS = 6.00
AUDIO_OUTPUT_PRICE_PER_1M_TOKENS = 10.00

class LLMModel(models.Model):
    """Represents a configurable LLM deployment with pricing information."""

    class ProviderChoices(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        ANTHROPIC = "anthropic", "Anthropic"
        DEEPSEEK = "deepseek", "DeepSeek"
        GOOGLE = "google", "Google"

    class ModelChoices(models.TextChoices):
        # OpenAI models
        GPT4O = "gpt-4o", "GPT-4o"
        GPT4O_MINI = "gpt-4o-mini", "GPT-4o Mini"
        GPT41 = "gpt-4.1", "GPT-4.1"
        GPT41_MINI = "gpt-4.1-mini", "GPT-4.1 Mini"
        GPT41_NANO = "gpt-4.1-nano", "GPT-4.1 Nano"
        GPT5 = "gpt-5", "GPT-5"
        GPT5_MINI = "gpt-5-mini", "GPT-5 Mini"
        GPT5_NANO = "gpt-5-nano", "GPT-5 Nano"
        O3 = "o3", "O3"
        O4_MINI = "o4-mini", "O4 Mini"
        # Anthropic models
        CLAUDE_SONNET_4 = "claude-sonnet-4-20250514", "Claude Sonnet 4"
        CLAUDE_HAIKU_35 = "claude-3-5-haiku-20241022", "Claude 3.5 Haiku"
        # DeepSeek models
        DEEPSEEK_R1 = "DeepSeek-R1", "DeepSeek R1"
        DEEPSEEK_V3 = "DeepSeek-V3", "DeepSeek V3"
        # Google models
        GEMINI_25_FLASH = "gemini-2.5-flash", "Gemini 2.5 Flash"
        GEMINI_25_PRO = "gemini-2.5-pro", "Gemini 2.5 Pro"

    class TagChoices(models.TextChoices):
        RECOMMENDED = "recommended", "Recomendado"
        REGULAR = "regular", "Regular"

    name = models.CharField(max_length=50, verbose_name="Nome")
    description = models.TextField(blank=True, default="", verbose_name="Descrição")
    provider = models.CharField(
        max_length=25,
        choices=ProviderChoices.choices,
        verbose_name="Provedor",
    )
    model = models.CharField(
        max_length=50,
        choices=ModelChoices.choices,
        verbose_name="Modelo",
    )
    tag = models.CharField(
        max_length=15,
        choices=TagChoices.choices,
        default=TagChoices.REGULAR,
        verbose_name="Tag",
    )
    temperature = models.FloatField(default=0.5, verbose_name="Temperatura")
    display_order = models.PositiveIntegerField(default=0, verbose_name="Ordem de exibição")
    input_price_per_1m_tokens = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name="Preço input/1M tokens",
    )
    output_price_per_1m_tokens = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name="Preço output/1M tokens",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Modelo LLM"
        verbose_name_plural = "Modelos LLM"

    def __str__(self):
        return f"{self.name} ({self.provider})"

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost for a given number of input and output tokens."""
        input_cost = (input_tokens / 1_000_000) * float(self.input_price_per_1m_tokens)
        output_cost = (output_tokens / 1_000_000) * float(self.output_price_per_1m_tokens)
        return input_cost + output_cost


class AssistantSession(models.Model):
    """Persistent session for the global assistant conversations."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_sessions",
        verbose_name="Usuário",
    )
    uuid_code = models.CharField(
        max_length=100,
        unique=True,
        default=uuid.uuid4,
        verbose_name="UUID",
    )
    title = models.CharField(max_length=200, blank=True, default="", verbose_name="Título")
    llm_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Modelo LLM",
    )
    screen_context = models.CharField(
        max_length=50,
        blank=True,
        default="default",
        verbose_name="Contexto de tela",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Sessão do Assistente"
        verbose_name_plural = "Sessões do Assistente"
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
            models.Index(fields=["uuid_code"]),
        ]

    def __str__(self):
        return f"Session {self.uuid_code[:8]} - {self.user.username}"

    def get_recent_messages(self, limit=50):
        """Return recent messages for this session."""
        return self.messages.order_by("-created_at")[:limit][::-1]


class AssistantMessage(models.Model):
    """Individual message in an assistant session."""

    class SenderChoices(models.TextChoices):
        USER = "user", "Usuário"
        ASSISTANT = "assistant", "Assistente"
        SYSTEM = "system", "Sistema"

    session = models.ForeignKey(
        AssistantSession,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Sessão",
    )
    content = models.TextField(verbose_name="Conteúdo")
    sender = models.CharField(
        max_length=20,
        choices=SenderChoices.choices,
        verbose_name="Remetente",
    )
    screen_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Tela de origem",
    )
    input_tokens = models.IntegerField(default=0, verbose_name="Tokens de entrada")
    output_tokens = models.IntegerField(default=0, verbose_name="Tokens de saída")
    llm_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        verbose_name="Modelo utilizado",
    )
    reasoning = models.TextField(blank=True, default="", verbose_name="Raciocínio")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Mensagem do Assistente"
        verbose_name_plural = "Mensagens do Assistente"
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        preview = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return f"[{self.sender}] {preview}"


class AssistantAction(models.Model):
    """Auditable action proposed or executed by the assistant."""

    class SourceChoices(models.TextChoices):
        TOOL = "tool", "Tool"
        UI = "ui", "UI"

    class StatusChoices(models.TextChoices):
        PROPOSED = "proposed", "Proposta"
        EXECUTED = "executed", "Executada"
        FAILED = "failed", "Falhou"
        REJECTED = "rejected", "Rejeitada"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_actions",
        verbose_name="Usuario",
    )
    session = models.ForeignKey(
        AssistantSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
        verbose_name="Sessao",
    )
    action_type = models.CharField(max_length=100, verbose_name="Tipo da acao")
    label = models.CharField(max_length=200, blank=True, default="", verbose_name="Rotulo")
    source = models.CharField(max_length=20, choices=SourceChoices.choices, default=SourceChoices.TOOL)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PROPOSED)
    screen_id = models.CharField(max_length=50, blank=True, default="", verbose_name="Tela")
    entity_type = models.CharField(max_length=80, blank=True, default="", verbose_name="Entidade")
    entity_id = models.CharField(max_length=80, blank=True, default="", verbose_name="ID da entidade")
    payload = models.JSONField(default=dict, blank=True, verbose_name="Payload")
    result = models.JSONField(default=dict, blank=True, verbose_name="Resultado")
    error = models.TextField(blank=True, default="", verbose_name="Erro")
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Acao do Assistente"
        verbose_name_plural = "Acoes do Assistente"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["session", "-created_at"]),
            models.Index(fields=["action_type", "status"]),
        ]

    def __str__(self):
        return f"{self.action_type} ({self.status})"


def audio_upload_to(instance: "AudioTranscription", filename: str) -> str:
    """Upload path for audio files organised by date."""
    now = timezone.now()
    return f"audio/transcriptions/{now:%Y/%m/%d}/{filename}"


def calculate_audio_transcription_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost of an audio transcription based on token usage."""
    input_cost = (input_tokens / 1_000_000) * AUDIO_INPUT_PRICE_PER_1M_TOKENS
    output_cost = (output_tokens / 1_000_000) * AUDIO_OUTPUT_PRICE_PER_1M_TOKENS
    return input_cost + output_cost


class AudioTranscription(models.Model):
    """Record of an audio-to-text transcription request.

    Stores the original audio file, the transcribed text, token usage and the
    cost of the operation.  Based on the ai_engine AudioTranscription model.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audio_transcriptions",
        verbose_name="Usuário",
    )
    session = models.ForeignKey(
        AssistantSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transcriptions",
        verbose_name="Sessão",
    )

    # Transcription result
    content = models.TextField(
        blank=True,
        default="",
        verbose_name="Texto transcrito",
        help_text="The transcribed text returned by the model",
    )

    # Audio file
    audio_file = models.FileField(
        upload_to=audio_upload_to,
        verbose_name="Arquivo de áudio",
        help_text="The original audio file that was transcribed",
    )
    audio_content_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Tipo do áudio",
        help_text="MIME type of the uploaded audio (e.g. audio/mpeg, audio/webm)",
    )
    audio_size = models.PositiveIntegerField(
        default=0,
        verbose_name="Tamanho do áudio (bytes)",
        help_text="Size of the audio file in bytes",
    )
    audio_duration_seconds = models.FloatField(
        default=0,
        verbose_name="Duração (s)",
        help_text="Duration of the audio in seconds (when available)",
    )

    # Model & tokens
    model_name = models.CharField(
        max_length=50,
        default=AUDIO_MODEL_NAME,
        verbose_name="Modelo de transcrição",
        help_text="Name of the audio model used for transcription",
    )
    input_tokens = models.IntegerField(
        default=0,
        verbose_name="Tokens de entrada",
        help_text="Number of input (audio) tokens consumed",
    )
    output_tokens = models.IntegerField(
        default=0,
        verbose_name="Tokens de saída",
        help_text="Number of output (text) tokens produced",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transcrição de Áudio"
        verbose_name_plural = "Transcrições de Áudio"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="ai_audio_user_created_idx"),
        ]

    def __str__(self):
        preview = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return f"AudioTranscription({self.model_name}): {preview}"

    def calculate_cost(self) -> float:
        """Calculate the cost based on token usage and the audio pricing constants."""
        return calculate_audio_transcription_cost(self.input_tokens, self.output_tokens)
