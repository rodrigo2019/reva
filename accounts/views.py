import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView

from athletes.models import Athlete
from core.mixins import StudentRequiredMixin, TrainerRequiredMixin
from workouts.models import ExercisePrescription, LoadUpdate, TrainingPlan, WorkoutPlan


class TrainerDashboardView(LoginRequiredMixin, TrainerRequiredMixin, TemplateView):
    template_name = "accounts/trainer_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        seven_days_ago = now - timezone.timedelta(days=7)

        athletes = Athlete.objects.filter(trainer=user).select_related("user")
        ctx["athlete_count"] = athletes.count()
        ctx["plan_count"] = TrainingPlan.objects.filter(created_by=user).count()
        ctx["workout_count"] = WorkoutPlan.objects.filter(created_by=user).count()
        ctx["active_workout_count"] = WorkoutPlan.objects.filter(created_by=user, is_active=True).count()
        ctx["exercise_count"] = ExercisePrescription.objects.filter(workout__created_by=user).count()
        ctx["recent_updates"] = (
            LoadUpdate.objects.filter(exercise__workout__created_by=user)
            .select_related("exercise__exercise_ref", "exercise__workout__athlete__user")
            .order_by("-created_at")[:10]
        )

        # Annotate athletes with last activity date
        athletes_with_activity = athletes.annotate(
            last_activity=Max("workout_plans__exercises__load_updates__created_at")
        ).order_by("-last_activity")
        ctx["athletes"] = athletes_with_activity
        ctx["seven_days_ago"] = seven_days_ago

        # Weekly activity data (last 7 days) — count of load updates per day
        daily_updates = (
            LoadUpdate.objects.filter(
                exercise__workout__created_by=user,
                created_at__gte=seven_days_ago,
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        day_map = {entry["day"]: entry["count"] for entry in daily_updates}
        chart_labels = []
        chart_values = []
        for i in range(7):
            d = (now - timezone.timedelta(days=6 - i)).date()
            chart_labels.append(d.strftime("%d/%m"))
            chart_values.append(day_map.get(d, 0))
        ctx["chart_labels"] = json.dumps(chart_labels)
        ctx["chart_values"] = json.dumps(chart_values)

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
