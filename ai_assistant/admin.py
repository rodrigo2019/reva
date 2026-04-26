from django.contrib import admin

from .models import AssistantAction, AssistantMessage, AssistantSession, AudioTranscription, LLMModel


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "model", "tag", "is_active", "display_order")
    list_filter = ("provider", "tag", "is_active")
    list_editable = ("display_order", "is_active")
    ordering = ("display_order",)


@admin.register(AssistantSession)
class AssistantSessionAdmin(admin.ModelAdmin):
    list_display = ("uuid_code", "user", "title", "screen_context", "is_active", "created_at")
    list_filter = ("is_active", "screen_context")
    search_fields = ("uuid_code", "title", "user__username")
    raw_id_fields = ("user",)


@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "get_user", "sender", "content_preview", "llm_model", "created_at")
    list_filter = ("sender",)
    search_fields = ("content", "session__user__username")
    raw_id_fields = ("session",)

    @admin.display(description="Usuário")
    def get_user(self, obj):
        return obj.session.user.username

    @admin.display(description="Conteúdo")
    def content_preview(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content


@admin.register(AssistantAction)
class AssistantActionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "action_type", "source", "status", "entity_type", "entity_id", "created_at")
    list_filter = ("source", "status", "action_type", "screen_id")
    search_fields = ("action_type", "label", "entity_type", "entity_id", "user__username")
    raw_id_fields = ("user", "session")
    readonly_fields = ("payload", "result", "error", "created_at", "executed_at")


@admin.register(AudioTranscription)
class AudioTranscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "model_name", "audio_size", "input_tokens", "output_tokens", "created_at")
    list_filter = ("model_name",)
    search_fields = ("content", "user__username")
    raw_id_fields = ("user",)
    readonly_fields = ("input_tokens", "output_tokens", "audio_size", "audio_content_type")
