import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from athletes.models import Athlete
from core.mixins import TrainerRequiredMixin

from .forms import ExerciseAlternativeForm, ExerciseForm, ExerciseUpdateForm, LoadUpdateForm, TrainingPlanForm, WorkoutPlanForm
from .models import ExerciseAlternative, ExercisePrescription, ExerciseProgressLog, LoadUpdate, TrainingPlan, WorkoutPlan


# ──────────────────────────────────────────────
# Training Plan CRUD
# ──────────────────────────────────────────────

class TrainingPlanListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
	model = TrainingPlan
	template_name = "workouts/plan_list.html"
	context_object_name = "plans"
	paginate_by = 12

	def get_queryset(self):
		qs = TrainingPlan.objects.filter(created_by=self.request.user).select_related("athlete__user").prefetch_related("workouts").order_by("-updated_at")
		athlete_pk = self.request.GET.get("aluno")
		status = self.request.GET.get("status")
		q = self.request.GET.get("q", "").strip()
		if athlete_pk:
			qs = qs.filter(athlete__pk=athlete_pk)
		if status == "ativo":
			qs = qs.filter(is_active=True)
		elif status == "inativo":
			qs = qs.filter(is_active=False)
		if q:
			qs = qs.filter(name__icontains=q)
		return qs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["athletes"] = Athlete.objects.filter(trainer=self.request.user).select_related("user")
		ctx["selected_athlete"] = self.request.GET.get("aluno", "")
		ctx["selected_status"] = self.request.GET.get("status", "")
		ctx["search_query"] = self.request.GET.get("q", "")
		return ctx


class TrainingPlanCreateView(LoginRequiredMixin, TrainerRequiredMixin, CreateView):
	model = TrainingPlan
	form_class = TrainingPlanForm
	template_name = "workouts/plan_form.html"

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["trainer"] = self.request.user
		return kwargs

	def get_initial(self):
		initial = super().get_initial()
		athlete_pk = self.request.GET.get("aluno")
		if athlete_pk:
			try:
				athlete = Athlete.objects.get(pk=athlete_pk, trainer=self.request.user)
				initial["athlete"] = athlete.pk
			except Athlete.DoesNotExist:
				pass
		return initial

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		messages.success(self.request, "Plano criado com sucesso.")
		return super().form_valid(form)


class TrainingPlanDetailView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
	model = TrainingPlan
	template_name = "workouts/plan_detail.html"
	context_object_name = "plan"

	def get_queryset(self):
		return TrainingPlan.objects.filter(created_by=self.request.user).select_related("athlete__user").prefetch_related(
			"workouts__exercises__exercise_ref",
		)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		workouts = self.object.workouts.all()
		ctx["active_workouts"] = workouts.filter(is_active=True, is_archived=False)
		ctx["archived_workouts"] = workouts.filter(is_archived=True)
		return ctx


class TrainingPlanUpdateView(LoginRequiredMixin, TrainerRequiredMixin, UpdateView):
	model = TrainingPlan
	form_class = TrainingPlanForm
	template_name = "workouts/plan_form.html"

	def get_queryset(self):
		return TrainingPlan.objects.filter(created_by=self.request.user)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["trainer"] = self.request.user
		return kwargs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["editing"] = True
		return ctx

	def form_valid(self, form):
		messages.success(self.request, "Plano atualizado com sucesso.")
		return super().form_valid(form)


class TrainingPlanDeleteView(LoginRequiredMixin, TrainerRequiredMixin, DeleteView):
	model = TrainingPlan
	template_name = "workouts/plan_confirm_delete.html"
	success_url = reverse_lazy("plan-list")

	def get_queryset(self):
		return TrainingPlan.objects.filter(created_by=self.request.user)

	def form_valid(self, form):
		messages.success(self.request, "Plano excluído com sucesso.")
		return super().form_valid(form)


# ──────────────────────────────────────────────
# Workout Plan CRUD
# ──────────────────────────────────────────────


class WorkoutPlanListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
	model = WorkoutPlan
	template_name = "workouts/trainer_workout_list.html"
	context_object_name = "workouts"
	paginate_by = 12

	def get_queryset(self):
		qs = WorkoutPlan.objects.filter(created_by=self.request.user, is_archived=False).select_related("athlete__user", "plan").order_by("-updated_at")
		athlete_pk = self.request.GET.get("aluno")
		status = self.request.GET.get("status")
		q = self.request.GET.get("q", "").strip()
		if athlete_pk:
			qs = qs.filter(athlete__pk=athlete_pk)
		if status == "ativo":
			qs = qs.filter(is_active=True)
		elif status == "inativo":
			qs = qs.filter(is_active=False)
		if q:
			qs = qs.filter(name__icontains=q)
		return qs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["athletes"] = Athlete.objects.filter(trainer=self.request.user).select_related("user")
		ctx["selected_athlete"] = self.request.GET.get("aluno", "")
		ctx["selected_status"] = self.request.GET.get("status", "")
		ctx["search_query"] = self.request.GET.get("q", "")
		return ctx


class WorkoutPlanCreateView(LoginRequiredMixin, TrainerRequiredMixin, CreateView):
	model = WorkoutPlan
	form_class = WorkoutPlanForm
	template_name = "workouts/workout_form.html"

	def get_plan(self):
		plan_pk = self.request.GET.get("plano") or self.kwargs.get("plan_pk")
		if plan_pk:
			return get_object_or_404(TrainingPlan, pk=plan_pk, created_by=self.request.user)
		return None

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["trainer"] = self.request.user
		kwargs["plan"] = self.get_plan()
		return kwargs

	def get_initial(self):
		initial = super().get_initial()
		athlete_pk = self.request.GET.get("aluno")
		if athlete_pk:
			try:
				athlete = Athlete.objects.get(pk=athlete_pk, trainer=self.request.user)
				initial["athlete"] = athlete.pk
			except Athlete.DoesNotExist:
				pass
		return initial

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["preselected_athlete"] = self.request.GET.get("aluno", "")
		plan = self.get_plan()
		if plan:
			ctx["plan"] = plan
		return ctx

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		# If plan is set, sync athlete from plan
		plan = form.cleaned_data.get("plan")
		if plan:
			form.instance.athlete = plan.athlete
		messages.success(self.request, "Treino criado com sucesso.")
		return super().form_valid(form)

	def get_success_url(self):
		if self.object.plan:
			return reverse("plan-detail", kwargs={"pk": self.object.plan.pk})
		return self.object.get_absolute_url()


class WorkoutPlanUpdateView(LoginRequiredMixin, TrainerRequiredMixin, UpdateView):
	model = WorkoutPlan
	form_class = WorkoutPlanForm
	template_name = "workouts/workout_form.html"

	def get_queryset(self):
		return WorkoutPlan.objects.filter(created_by=self.request.user)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["trainer"] = self.request.user
		kwargs["plan"] = None  # don't lock on edit
		return kwargs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["editing"] = True
		return ctx

	def form_valid(self, form):
		messages.success(self.request, "Treino atualizado com sucesso.")
		return super().form_valid(form)


class WorkoutPlanDeleteView(LoginRequiredMixin, TrainerRequiredMixin, DeleteView):
	model = WorkoutPlan
	template_name = "workouts/workout_confirm_delete.html"

	def get_queryset(self):
		return WorkoutPlan.objects.filter(created_by=self.request.user)

	def form_valid(self, form):
		plan = self.object.plan
		messages.success(self.request, "Treino excluído com sucesso.")
		response = super().form_valid(form)
		return response

	def get_success_url(self):
		# Redirect to plan detail if the workout belonged to a plan
		plan_pk = self.request.POST.get("plan_pk") or (self.object.plan_id if hasattr(self, "object") and self.object else None)
		if plan_pk:
			return reverse("plan-detail", kwargs={"pk": plan_pk})
		return reverse_lazy("workout-list")


class WorkoutPlanDetailView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
	model = WorkoutPlan
	template_name = "workouts/workout_detail.html"
	context_object_name = "workout"

	def get_queryset(self):
		return WorkoutPlan.objects.filter(created_by=self.request.user).select_related("plan", "athlete__user").prefetch_related(
			"exercises__exercise_ref", "exercises__load_updates", "exercises__progress_logs",
			"exercises__alternatives__exercise_ref",
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["exercise_form"] = ExerciseForm(trainer=self.request.user)
		context["alternative_form"] = ExerciseAlternativeForm(trainer=self.request.user)
		context["load_form"] = LoadUpdateForm()
		exercises = self.object.exercises.all()
		context["exercise_count"] = exercises.count()
		muscle_groups = set()
		total_load_updates = 0
		exercise_charts = {}
		for ex in exercises:
			if ex.exercise_ref and ex.exercise_ref.muscle_group:
				muscle_groups.add(ex.exercise_ref.muscle_group)
			updates = list(
				ex.load_updates
				.filter(new_load_kg__isnull=False)
				.order_by("created_at")
				.values_list("created_at", "new_load_kg")
			)
			total_load_updates += len(updates)
			if updates:
				exercise_charts[ex.pk] = [
					{"date": dt.strftime("%d/%m"), "load": float(load)}
					for dt, load in updates
				]
		context["muscle_groups_count"] = len(muscle_groups)
		context["total_load_updates"] = total_load_updates
		context["exercise_charts_json"] = json.dumps(exercise_charts)
		return context


class ExerciseCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, pk):
		workout = get_object_or_404(WorkoutPlan, pk=pk, created_by=request.user)
		form = ExerciseForm(request.POST, trainer=request.user)
		if form.is_valid():
			exercise = form.save(commit=False)
			exercise.workout = workout
			# If exercise_ref is set but name is blank, use the catalog name
			if exercise.exercise_ref and not exercise.name:
				exercise.name = exercise.exercise_ref.name
			exercise.save()
			messages.success(request, f"Exercício '{exercise.display_name}' adicionado com sucesso.")
		return redirect("workout-detail", pk=workout.pk)


class ExerciseUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Update all tracked fields of an exercise. Creates progress log on save()."""

	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = ExerciseUpdateForm(request.POST, instance=exercise)
		if form.is_valid():
			form.save()  # save() creates ExerciseProgressLog + LoadUpdate automatically
			messages.success(request, "Exercício atualizado com sucesso.")
		return redirect("workout-detail", pk=workout.pk)


class ExerciseDeleteView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		name = exercise.display_name
		exercise.delete()
		messages.success(request, f"Exercício '{name}' excluído.")
		return redirect("workout-detail", pk=workout.pk)


class UpdateExerciseLoadView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = LoadUpdateForm(request.POST)
		if form.is_valid():
			with transaction.atomic():
				previous_load = exercise.current_load_kg
				new_load = form.cleaned_data["new_load_kg"]
				reason = form.cleaned_data["reason"]
				ExercisePrescription.objects.filter(pk=exercise.pk).update(current_load_kg=new_load)
				LoadUpdate.objects.create(
					exercise=exercise,
					previous_load_kg=previous_load,
					new_load_kg=new_load,
					reason=reason or "Atualização manual",
					updated_by=request.user,
				)
				# Also create progress log for load-only update
				ExerciseProgressLog.objects.create(
					exercise=exercise,
					sets=exercise.sets,
					reps=exercise.reps,
					load_kg=new_load,
					rest_seconds=exercise.rest_seconds,
					notes=reason or "Atualização de carga",
					updated_by=request.user,
				)
			messages.success(request, f"Carga atualizada para {new_load}kg.")
		return redirect("workout-detail", pk=workout.pk)


class ExerciseProgressDataView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""JSON endpoint returning progress log data for charts."""

	def get(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		logs = exercise.progress_logs.order_by("created_at")
		data = [
			{
				"date": log.created_at.strftime("%d/%m/%Y"),
				"load": float(log.load_kg) if log.load_kg else 0,
				"sets": log.sets,
				"reps": log.reps,
				"rest": log.rest_seconds,
			}
			for log in logs
		]
		return JsonResponse({"exercise": exercise.name, "data": data})


class WorkoutSessionView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
	"""Lean, mobile-first live-session view for trainers coaching in the gym."""
	model = WorkoutPlan
	template_name = "workouts/workout_session.html"
	context_object_name = "workout"

	def get_queryset(self):
		return WorkoutPlan.objects.filter(created_by=self.request.user).select_related(
			"athlete__user"
		).prefetch_related("exercises__exercise_ref", "exercises__alternatives__exercise_ref")

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["exercises"] = self.object.exercises.select_related("exercise_ref").prefetch_related("alternatives__exercise_ref").all()
		return ctx


# ──────────────────────────────────────────────
# Exercise Alternative Management
# ──────────────────────────────────────────────

class AddAlternativeView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Add an alternative exercise to a prescription."""

	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		prescription = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = ExerciseAlternativeForm(request.POST, trainer=request.user)
		if form.is_valid():
			alt = form.save(commit=False)
			alt.prescription = prescription
			alt.save()
			messages.success(request, f"Substituto '{alt.exercise_ref.name}' adicionado.")
		else:
			messages.error(request, "Erro ao adicionar substituto.")
		return redirect("workout-detail", pk=workout.pk)


class RemoveAlternativeView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Remove an alternative exercise from a prescription."""

	def post(self, request, workout_pk, exercise_pk, alt_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		prescription = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		alt = get_object_or_404(ExerciseAlternative, pk=alt_pk, prescription=prescription)
		name = alt.exercise_ref.name
		alt.delete()
		messages.success(request, f"Substituto '{name}' removido.")
		return redirect("workout-detail", pk=workout.pk)


class ArchiveWorkoutView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Toggle archived state of a workout."""

	def post(self, request, pk):
		workout = get_object_or_404(WorkoutPlan, pk=pk, created_by=request.user)
		workout.is_archived = not workout.is_archived
		workout.save(update_fields=["is_archived"])
		status = "arquivado" if workout.is_archived else "desarquivado"
		messages.success(request, f"Treino {status} com sucesso.")
		if workout.plan:
			return redirect("plan-detail", pk=workout.plan.pk)
		return redirect("workout-list")

