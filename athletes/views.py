import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from workouts.models import ExerciseProgressLog, WorkoutPlan

from .forms import StudentRegistrationForm
from .models import Athlete


class TrainerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_trainer


class StudentListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
    model = Athlete
    template_name = "athletes/student_list.html"
    context_object_name = "students"

    def get_queryset(self):
        return (
            Athlete.objects.filter(trainer=self.request.user)
            .select_related("user")
            .prefetch_related("workout_plans")
        )


class StudentCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "athletes/student_create.html"

    def get(self, request):
        form = StudentRegistrationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            athlete = form.save(trainer=request.user)
            messages.success(request, f"Aluno {athlete} cadastrado com sucesso!")
            from django.shortcuts import redirect

            return redirect("student-list")
        return render(request, self.template_name, {"form": form})


class StudentDetailView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
    model = Athlete
    template_name = "athletes/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return Athlete.objects.filter(trainer=self.request.user).select_related("user")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = self.object
        workouts = (
            WorkoutPlan.objects.filter(athlete=student)
            .prefetch_related("exercises__progress_logs")
            .order_by("-updated_at")
        )
        ctx["workouts"] = workouts
        ctx["active_workouts"] = workouts.filter(is_active=True).count()

        ctx["recent_logs"] = (
            ExerciseProgressLog.objects.filter(exercise__workout__athlete=student)
            .select_related("exercise__workout")
            .order_by("-created_at")[:15]
        )

        # Build chart data
        chart_exercises = []
        for workout in workouts:
            for exercise in workout.exercises.all():
                logs = exercise.progress_logs.order_by("created_at")
                if logs.exists():
                    chart_exercises.append(
                        {
                            "name": f"{exercise.name} ({workout.name})",
                            "data": [
                                {
                                    "date": log.created_at.strftime("%d/%m/%Y"),
                                    "load": float(log.load_kg) if log.load_kg else 0,
                                    "sets": log.sets,
                                    "reps": log.reps,
                                }
                                for log in logs
                            ],
                        }
                    )
        ctx["chart_data"] = json.dumps(chart_exercises, ensure_ascii=False)
        ctx["create_workout_url"] = reverse("workout-create") + f"?aluno={student.pk}"
        return ctx
