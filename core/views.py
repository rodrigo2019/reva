from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView, View


class LandingPageView(TemplateView):
	template_name = "core/landing.html"


class HomeRedirectView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		if request.user.is_trainer:
			return redirect("trainer-dashboard")
		return redirect("student-dashboard")
