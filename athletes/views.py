import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from core.mixins import TrainerRequiredMixin
from workouts.models import ExerciseProgressLog, ExercisePrescription, TrainingPlan, WorkoutPlan

from .forms import AnamnesisForm, PhysicalAssessmentForm, StudentRegistrationForm, StudentUpdateForm
from .models import Anamnesis, Athlete, PhysicalAssessment


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
        form.trainer = request.user
        if form.is_valid():
            athlete = form.save(trainer=request.user)
            messages.success(request, f"Aluno {athlete} vinculado com sucesso!")
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

        # Single queryset with all required prefetches — reused for list, chart, and standalone
        workouts = (
            WorkoutPlan.objects.filter(athlete=student)
            .select_related("plan")
            .prefetch_related(
                "exercises__exercise_ref",
                "exercises__load_updates",
                "exercises__progress_logs",
            )
            .order_by("-updated_at")
        )
        ctx["workouts"] = workouts
        ctx["active_workouts"] = sum(1 for w in workouts if w.is_active)
        ctx["standalone_workouts"] = [w for w in workouts if w.plan_id is None]

        # Training plans with nested workouts
        ctx["plans"] = (
            TrainingPlan.objects.filter(athlete=student)
            .prefetch_related("workouts__exercises")
            .order_by("-is_active", "-created_at")
        )

        ctx["recent_logs"] = (
            ExerciseProgressLog.objects.filter(exercise__workout__athlete=student)
            .select_related("exercise__workout")
            .order_by("-created_at")[:15]
        )

        # Profile quick info
        ctx["anamnesis"] = student.latest_anamnesis
        ctx["latest_assessment"] = student.latest_assessment

        # Build chart data grouped by workout — reuse already-prefetched queryset
        chart_data = {}
        for workout in sorted(workouts, key=lambda w: w.name):
            exercises_list = []
            for exercise in workout.exercises.all():
                points = [
                    {
                        "date": u.created_at.strftime("%d/%m/%Y"),
                        "load": float(u.new_load_kg),
                    }
                    for u in exercise.load_updates.all()
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
        student_name = str(athlete)
        athlete.delete()
        messages.success(request, f"Aluno {student_name} desvinculado com sucesso. A conta do usuário foi preservada.")
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
    def _get_athlete(self, request, pk):
        return get_object_or_404(Athlete, pk=pk, trainer=request.user)

    def get(self, request, pk):
        athlete = self._get_athlete(request, pk)
        messages.info(
            request,
            f"O acesso de {athlete} é definido pelo próprio aluno no cadastro da plataforma.",
        )
        return redirect("student-detail", pk=athlete.pk)

    def post(self, request, pk):
        athlete = self._get_athlete(request, pk)
        messages.info(
            request,
            f"O acesso de {athlete} é definido pelo próprio aluno no cadastro da plataforma.",
        )
        return redirect("student-detail", pk=athlete.pk)


# ===========================================================================
# Perfil do Aluno – Ficha Completa (Anamnese + Avaliações)
# ===========================================================================

class StudentProfileView(LoginRequiredMixin, TrainerRequiredMixin, View):
    """Página de perfil completa com abas: Anamnese, Avaliações, Evolução."""

    template_name = "athletes/student_profile.html"

    def get(self, request, pk):
        student = get_object_or_404(Athlete, pk=pk, trainer=request.user)
        tab = request.GET.get("tab", "anamnesis")

        anamnesis = student.latest_anamnesis
        assessments = student.physical_assessments.order_by("-assessed_at")
        latest_assessment = assessments.first()

        # Build evolution chart data (weight + body fat over time)
        evolution_data = self._build_evolution_data(assessments)

        context = {
            "student": student,
            "anamnesis": anamnesis,
            "assessments": assessments,
            "latest_assessment": latest_assessment,
            "evolution_data": json.dumps(evolution_data, ensure_ascii=False),
            "active_tab": tab,
        }
        return render(request, self.template_name, context)

    def _build_evolution_data(self, assessments):
        """Build chart-compatible data from assessment history."""
        points = []
        for a in assessments.order_by("assessed_at"):
            point = {"date": a.assessed_at.strftime("%d/%m/%Y")}
            if a.weight_kg:
                point["weight"] = float(a.weight_kg)
            if a.body_fat_percentage:
                point["body_fat"] = float(a.body_fat_percentage)
            if a.bmi:
                point["bmi"] = float(a.bmi)
            if a.lean_mass_kg:
                point["lean_mass"] = float(a.lean_mass_kg)
            if a.fat_mass_kg:
                point["fat_mass"] = float(a.fat_mass_kg)
            if a.waist_cm:
                point["waist"] = float(a.waist_cm)
            if a.right_arm_cm:
                point["right_arm"] = float(a.right_arm_cm)
            if a.left_arm_cm:
                point["left_arm"] = float(a.left_arm_cm)
            if a.right_thigh_cm:
                point["right_thigh"] = float(a.right_thigh_cm)
            if a.chest_cm:
                point["chest"] = float(a.chest_cm)
            points.append(point)
        return points


class AnamnesisCreateUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    """Cria ou edita a anamnese do aluno."""

    template_name = "athletes/anamnesis_form.html"

    def _get_student(self, request, pk):
        return get_object_or_404(Athlete, pk=pk, trainer=request.user)

    def get(self, request, pk):
        student = self._get_student(request, pk)
        anamnesis = student.latest_anamnesis
        form = AnamnesisForm(instance=anamnesis) if anamnesis else AnamnesisForm()
        return render(request, self.template_name, {
            "form": form,
            "student": student,
            "editing": anamnesis is not None,
        })

    def post(self, request, pk):
        student = self._get_student(request, pk)
        anamnesis = student.latest_anamnesis
        form = AnamnesisForm(request.POST, instance=anamnesis) if anamnesis else AnamnesisForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.athlete = student
            obj.save()
            messages.success(request, "Anamnese salva com sucesso!")
            return redirect("student-profile", pk=student.pk)
        return render(request, self.template_name, {
            "form": form,
            "student": student,
            "editing": anamnesis is not None,
        })


class PhysicalAssessmentCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    """Registra nova avaliação física."""

    template_name = "athletes/assessment_form.html"

    def _get_student(self, request, pk):
        return get_object_or_404(Athlete, pk=pk, trainer=request.user)

    def get(self, request, pk):
        student = self._get_student(request, pk)
        # Pre-fill height from latest assessment (usually doesn't change)
        initial = {}
        latest = student.latest_assessment
        if latest and latest.height_cm:
            initial["height_cm"] = latest.height_cm
        form = PhysicalAssessmentForm(initial=initial)
        return render(request, self.template_name, {"form": form, "student": student})

    def post(self, request, pk):
        student = self._get_student(request, pk)
        form = PhysicalAssessmentForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.athlete = student
            obj.save()
            messages.success(request, "Avaliação física registrada com sucesso!")
            return redirect("student-profile", pk=student.pk)
        return render(request, self.template_name, {"form": form, "student": student})


class PhysicalAssessmentUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
    """Edita uma avaliação física existente."""

    template_name = "athletes/assessment_form.html"

    def _get_objects(self, request, pk, assessment_pk):
        student = get_object_or_404(Athlete, pk=pk, trainer=request.user)
        assessment = get_object_or_404(PhysicalAssessment, pk=assessment_pk, athlete=student)
        return student, assessment

    def get(self, request, pk, assessment_pk):
        student, assessment = self._get_objects(request, pk, assessment_pk)
        form = PhysicalAssessmentForm(instance=assessment)
        return render(request, self.template_name, {"form": form, "student": student, "editing": True})

    def post(self, request, pk, assessment_pk):
        student, assessment = self._get_objects(request, pk, assessment_pk)
        form = PhysicalAssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            form.save()
            messages.success(request, "Avaliação atualizada com sucesso!")
            return redirect("student-profile", pk=student.pk)
        return render(request, self.template_name, {"form": form, "student": student, "editing": True})


class PhysicalAssessmentDeleteView(LoginRequiredMixin, TrainerRequiredMixin, View):
    """Exclui uma avaliação física."""

    def post(self, request, pk, assessment_pk):
        student = get_object_or_404(Athlete, pk=pk, trainer=request.user)
        assessment = get_object_or_404(PhysicalAssessment, pk=assessment_pk, athlete=student)
        assessment.delete()
        messages.success(request, "Avaliação excluída com sucesso.")
        return redirect("student-profile", pk=student.pk)
