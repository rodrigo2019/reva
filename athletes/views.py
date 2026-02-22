import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from workouts.models import ExerciseProgressLog, ExercisePrescription, TrainingPlan, WorkoutPlan

from .forms import SetStudentPasswordForm, StudentRegistrationForm, StudentUpdateForm
from .models import Athlete


class TrainerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_trainer


class StudentListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
    model = Athlete
    template_name = "athletes/student_list.html"
    context_object_name = "students"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Athlete.objects.filter(trainer=self.request.user)
            .select_related("user")
            .prefetch_related("workout_plans")
        )
        q = self.request.GET.get("q", "").strip()
        sort = self.request.GET.get("sort", "nome")
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(user__username__icontains=q))
        if sort == "recente":
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("user__first_name", "user__last_name")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_query"] = self.request.GET.get("q", "")
        ctx["current_sort"] = self.request.GET.get("sort", "nome")
        return ctx


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

        # Training plans with nested workouts
        ctx["plans"] = (
            TrainingPlan.objects.filter(athlete=student)
            .prefetch_related("workouts__exercises")
            .order_by("-is_active", "-created_at")
        )
        # Standalone workouts (not in any plan)
        ctx["standalone_workouts"] = workouts.filter(plan__isnull=True)

        ctx["recent_logs"] = (
            ExerciseProgressLog.objects.filter(exercise__workout__athlete=student)
            .select_related("exercise__workout")
            .order_by("-created_at")[:15]
        )

        # Build chart data grouped by workout
        workouts_for_chart = (
            WorkoutPlan.objects.filter(athlete=student)
            .prefetch_related("exercises__exercise_ref", "exercises__load_updates")
            .order_by("name")
        )
        chart_data = {}
        for workout in workouts_for_chart:
            exercises_list = []
            for exercise in workout.exercises.all():
                points = [
                    {
                        "date": u.created_at.strftime("%d/%m/%Y"),
                        "load": float(u.new_load_kg),
                    }
                    for u in exercise.load_updates.order_by("created_at")
                    if u.new_load_kg is not None
                ]
                if points:
                    exercises_list.append({
                        "id": exercise.pk,
                        "name": exercise.display_name,
                        "points": points,
                    })
            if exercises_list:
                chart_data[workout.name] = exercises_list
        ctx["chart_data"] = json.dumps(chart_data, ensure_ascii=False)
        ctx["create_workout_url"] = reverse("workout-create") + f"?aluno={student.pk}"
        return ctx


class StudentUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "athletes/student_edit.html"

    def _get_athlete(self, request, pk):
        return get_object_or_404(Athlete, pk=pk, trainer=request.user)

    def get(self, request, pk):
        athlete = self._get_athlete(request, pk)
        form = StudentUpdateForm(athlete=athlete)
        return render(request, self.template_name, {"form": form, "student": athlete})

    def post(self, request, pk):
        athlete = self._get_athlete(request, pk)
        form = StudentUpdateForm(request.POST, athlete=athlete)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados do aluno atualizados com sucesso!")
            return redirect("student-detail", pk=athlete.pk)
        return render(request, self.template_name, {"form": form, "student": athlete})


class StudentDeleteView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "athletes/student_confirm_delete.html"

    def _get_athlete(self, request, pk):
        return get_object_or_404(Athlete, pk=pk, trainer=request.user)

    def get(self, request, pk):
        athlete = self._get_athlete(request, pk)
        return render(request, self.template_name, {"student": athlete})

    def post(self, request, pk):
        athlete = self._get_athlete(request, pk)
        user = athlete.user
        athlete.delete()
        user.delete()
        messages.success(request, "Aluno excluído com sucesso.")
        return redirect("student-list")


class TrainerStudentProgressView(LoginRequiredMixin, TrainerRequiredMixin, TemplateView):
    template_name = "athletes/student_progress.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = get_object_or_404(Athlete, pk=self.kwargs["pk"], trainer=self.request.user)
        context["student"] = student

        exercises = (
            ExercisePrescription.objects
            .filter(workout__athlete=student)
            .select_related("workout", "exercise_ref")
            .prefetch_related("load_updates")
            .order_by("workout__name", "exercise_order")
        )

        chart_payload = []
        for exercise in exercises:
            points = [
                {
                    "date": update.created_at.strftime("%d/%m/%Y"),
                    "load": float(update.new_load_kg),
                }
                for update in exercise.load_updates.order_by("created_at")
                if update.new_load_kg is not None
            ]
            if not points:
                continue
            chart_payload.append({
                "id": exercise.pk,
                "exercise": exercise.display_name,
                "workout": exercise.workout.name,
                "points": points,
            })

        context["chart_payload"] = json.dumps(chart_payload, ensure_ascii=False)
        return context


class SetStudentPasswordView(LoginRequiredMixin, TrainerRequiredMixin, View):
    template_name = "athletes/student_set_password.html"

    def _get_athlete(self, request, pk):
        return get_object_or_404(Athlete, pk=pk, trainer=request.user)

    def get(self, request, pk):
        athlete = self._get_athlete(request, pk)
        form = SetStudentPasswordForm()
        return render(request, self.template_name, {"form": form, "student": athlete})

    def post(self, request, pk):
        athlete = self._get_athlete(request, pk)
        form = SetStudentPasswordForm(request.POST)
        if form.is_valid():
            athlete.user.set_password(form.cleaned_data["password"])
            athlete.user.save()
            messages.success(request, f"Senha de {athlete} definida com sucesso!")
            return redirect("student-detail", pk=athlete.pk)
        return render(request, self.template_name, {"form": form, "student": athlete})
