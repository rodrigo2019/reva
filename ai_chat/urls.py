from django.urls import path

from .views import ChatMessageCreateView, ChatView

urlpatterns = [
    path("", ChatView.as_view(), name="ai-chat"),
    path("enviar/", ChatMessageCreateView.as_view(), name="ai-chat-send"),
]
