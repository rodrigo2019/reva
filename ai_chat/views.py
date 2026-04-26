from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from .models import ChatMessage, ChatSession
from .services import generate_contextual_reply


class StudentRequiredMixin(UserPassesTestMixin):
	def test_func(self):
		return self.request.user.is_authenticated and self.request.user.is_student

	def handle_no_permission(self):
		if self.request.user.is_authenticated:
			django_messages.warning(self.request, "AI chat is available only for students.")
			return redirect("trainer-dashboard")
		return super().handle_no_permission()


class ChatView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
	template_name = "ai_chat/chat.html"

	def get(self, request, *args, **kwargs):
		request.user.get_athlete_profile()
		return super().get(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		profile = self.request.user.get_athlete_profile()
		session, _ = ChatSession.objects.get_or_create(athlete=profile)
		context["session"] = session
		context["messages"] = session.messages.all()
		return context


class ChatMessageCreateView(LoginRequiredMixin, StudentRequiredMixin, View):
	def post(self, request):
		question = request.POST.get("question", "").strip()
		if not question:
			return redirect("ai-chat")

		profile = request.user.get_athlete_profile()

		session, _ = ChatSession.objects.get_or_create(athlete=profile)
		ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=question)

		answer = generate_contextual_reply(profile, question)
		ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=answer)
		return redirect("ai-chat")
