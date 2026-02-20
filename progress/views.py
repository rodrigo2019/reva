import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from workouts.models import ExercisePrescription


class StudentRequiredMixin(UserPassesTestMixin):
	def test_func(self):
		return self.request.user.is_authenticated and self.request.user.is_student


class StudentProgressView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
	template_name = "progress/my_progress.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		profile = self.request.user.get_athlete_profile()
		exercises = ExercisePrescription.objects.filter(workout__athlete=profile).prefetch_related("load_updates")

		chart_payload = {}
		for exercise in exercises:
			chart_payload[exercise.name] = [
				{
					"date": update.created_at.strftime("%d/%m"),
					"load": float(update.new_load_kg),
				}
				for update in exercise.load_updates.order_by("created_at")
			]

		context["chart_payload"] = json.dumps(chart_payload, ensure_ascii=False)
		return context
