from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from athletes.models import Athlete
from core.mixins import LinkedStudentRequiredMixin, StudentRequiredMixin, TrainerRequiredMixin
from schedule.models import ClassSchedule
from workouts.models import ExercisePrescription, LoadUpdate, WorkoutPlan

from .services import TrainerDashboardService


class TrainerDashboardView(LoginRequiredMixin, TrainerRequiredMixin, TemplateView):
    template_name = "accounts/trainer_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(TrainerDashboardService.build_context(self.request.user))
        return ctx


class StudentDashboardView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = "accounts/student_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.request.user.get_athlete_profile()

        ctx["profile"] = profile
        ctx["is_linked"] = profile.has_active_trainer
        ctx["is_independent"] = profile.is_independent
        ctx["workout_count"] = WorkoutPlan.objects.filter(athlete=profile, is_active=True).count()
        ctx["exercise_count"] = ExercisePrescription.objects.filter(workout__athlete=profile).count()
        ctx["recent_updates"] = (
            LoadUpdate.objects.filter(exercise__workout__athlete=profile)
            .select_related("exercise")
            .order_by("-created_at")[:6]
        )
        ctx["latest_assessment"] = profile.latest_assessment
        ctx["anamnesis"] = profile.latest_anamnesis
        ctx["next_class"] = (
            ClassSchedule.objects.filter(athlete=profile, scheduled_at__gte=timezone.now())
            .select_related("workout_plan")
            .order_by("scheduled_at")
            .first()
        )
        ctx["upcoming_class_count"] = ClassSchedule.objects.filter(
            athlete=profile,
            scheduled_at__gte=timezone.now(),
        ).count()
        return ctx


class StudentSelfProfileView(LoginRequiredMixin, LinkedStudentRequiredMixin, TemplateView):
    template_name = "accounts/student_profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.request.user.get_athlete_profile()
        assessments = profile.physical_assessments.order_by("-assessed_at")[:5]
        ctx["profile"] = profile
        ctx["is_independent"] = profile.is_independent
        ctx["anamnesis"] = profile.latest_anamnesis
        ctx["latest_assessment"] = profile.latest_assessment
        ctx["assessments"] = assessments
        ctx["next_class"] = (
            ClassSchedule.objects.filter(athlete=profile, scheduled_at__gte=timezone.now())
            .select_related("workout_plan")
            .order_by("scheduled_at")
            .first()
        )
        ctx["active_workouts"] = WorkoutPlan.objects.filter(
            athlete=profile,
            is_active=True,
            is_archived=False,
        ).count()
        return ctx
