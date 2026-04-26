from django.urls import path

from .assistant_views import (
    AssistantContextView,
    AssistantExecuteActionView,
    AssistantSendMessageView,
    AssistantVoiceMessageView,
)

urlpatterns = [
    path("mensagem/", AssistantSendMessageView.as_view(), name="assistant-send"),
    path("voz/", AssistantVoiceMessageView.as_view(), name="assistant-voice"),
    path("contexto/", AssistantContextView.as_view(), name="assistant-context"),
    path("acao/", AssistantExecuteActionView.as_view(), name="assistant-action"),
]
