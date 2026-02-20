from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from athletes.models import Athlete
from workouts.models import ExercisePrescription, LoadUpdate, WorkoutPlan


class TrainerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_trainer


class StudentRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_student


class TrainerDashboardView(LoginRequiredMixin, TrainerRequiredMixin, TemplateView):
    template_name = "accounts/trainer_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["athlete_count"] = Athlete.objects.filter(trainer=user).count()
        ctx["workout_count"] = WorkoutPlan.objects.filter(created_by=user).count()
        ctx["active_workout_count"] = WorkoutPlan.objects.filter(created_by=user, is_active=True).count()
        ctx["recent_updates"] = (
            LoadUpdate.objects.filter(exercise__workout__created_by=user)
            .select_related("exercise__workout__athlete__user")
            .order_by("-created_at")[:8]
        )
        ctx["athletes"] = Athlete.objects.filter(trainer=user).select_related("user")
        return ctx


class StudentDashboardView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = "accounts/student_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.request.user.get_athlete_profile()
        ctx["workout_count"] = WorkoutPlan.objects.filter(athlete=profile, is_active=True).count()
        ctx["exercise_count"] = ExercisePrescription.objects.filter(workout__athlete=profile).count()
        ctx["recent_updates"] = (
            LoadUpdate.objects.filter(exercise__workout__athlete=profile)
            .select_related("exercise")
            .order_by("-created_at")[:6]
        )
        return ctx
