from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView


class TrainerRequiredMixin(UserPassesTestMixin):
	def test_func(self):
		return self.request.user.is_authenticated and self.request.user.is_trainer


class StudentRequiredMixin(UserPassesTestMixin):
	def test_func(self):
		return self.request.user.is_authenticated and self.request.user.is_student


class TrainerDashboardView(LoginRequiredMixin, TrainerRequiredMixin, TemplateView):
	template_name = "accounts/trainer_dashboard.html"


class StudentDashboardView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
	template_name = "accounts/student_dashboard.html"
