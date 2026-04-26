import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from core.mixins import StudentRequiredMixin
from .services import ProgressService


class StudentProgressView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
	template_name = "progress/my_progress.html"

	def get(self, request, *args, **kwargs):
		request.user.get_athlete_profile()
		return super().get(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		chart_payload = ProgressService.get_exercise_evolution(self.request.user)
		context["chart_payload"] = json.dumps(chart_payload, ensure_ascii=False)
		return context
