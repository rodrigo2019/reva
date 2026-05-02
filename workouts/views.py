import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from athletes.models import Athlete, StudentRelationshipStatus
from core.mixins import LinkedStudentRequiredMixin, TrainerRequiredMixin

from .forms import ExerciseAlternativeForm, ExerciseForm, ExerciseUpdateForm, LoadUpdateForm, TrainingPlanForm, WorkoutPlanForm, WorkoutSetLogForm
from .models import ExerciseAlternative, ExercisePrescription, TrainingPlan, WorkoutPlan, WorkoutSession
from .services import WorkoutExecutionService, WorkoutService


def _selected_student_pk(request):
	return request.GET.get("student") or request.GET.get("aluno")


def _selected_status(request):
	status = (request.GET.get("status") or "").strip().lower()
	if status in {"active", "ativo"}:
		return "active"
	if status in {"inactive", "inativo"}:
		return "inactive"
	return ""


def _trainer_plan_queryset(user):
	return TrainingPlan.objects.filter(
		created_by=user,
		athlete__trainer=user,
		athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
	)


def _trainer_workout_queryset(user):
	return WorkoutPlan.objects.filter(
		created_by=user,
		athlete__trainer=user,
		athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
	)


# ──────────────────────────────────────────────
# Training Plan CRUD
# ──────────────────────────────────────────────

class TrainingPlanListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
	model = TrainingPlan
	template_name = "workouts/plan_list.html"
	context_object_name = "plans"
	paginate_by = 12

	def get_queryset(self):
		qs = _trainer_plan_queryset(self.request.user).select_related("athlete__user").prefetch_related("workouts").order_by("-updated_at")
		athlete_pk = _selected_student_pk(self.request)
		status = _selected_status(self.request)
		q = self.request.GET.get("q", "").strip()
		if athlete_pk:
			qs = qs.filter(athlete__pk=athlete_pk)
		if status == "active":
			qs = qs.filter(is_active=True)
		elif status == "inactive":
			qs = qs.filter(is_active=False)
		if q:
			qs = qs.filter(name__icontains=q)
		return qs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["athletes"] = Athlete.objects.filter(
			trainer=self.request.user,
			relationship_status=StudentRelationshipStatus.ACTIVE,
		).select_related("user")
		ctx["selected_athlete"] = _selected_student_pk(self.request) or ""
		ctx["selected_status"] = _selected_status(self.request)
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
		athlete_pk = _selected_student_pk(self.request)
		if athlete_pk:
			try:
				athlete = Athlete.objects.get(
					pk=athlete_pk,
					trainer=self.request.user,
					relationship_status=StudentRelationshipStatus.ACTIVE,
				)
				initial["athlete"] = athlete.pk
			except Athlete.DoesNotExist:
				pass
		return initial

	def form_valid(self, form):
		self.object = WorkoutService.create_training_plan(
			self.request.user,
			form.cleaned_data["athlete"],
			form.cleaned_data["name"],
			objective=form.cleaned_data.get("objective", ""),
			is_active=form.cleaned_data.get("is_active", True),
		)
		messages.success(self.request, "Plan created successfully.")
		return redirect(self.get_success_url())


class TrainingPlanDetailView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
	model = TrainingPlan
	template_name = "workouts/plan_detail.html"
	context_object_name = "plan"

	def get_queryset(self):
		return _trainer_plan_queryset(self.request.user).select_related("athlete__user").prefetch_related(
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
		return _trainer_plan_queryset(self.request.user)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["trainer"] = self.request.user
		return kwargs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["editing"] = True
		return ctx

	def form_valid(self, form):
		messages.success(self.request, "Plan updated successfully.")
		return super().form_valid(form)


class TrainingPlanDeleteView(LoginRequiredMixin, TrainerRequiredMixin, DeleteView):
	model = TrainingPlan
	template_name = "workouts/plan_confirm_delete.html"
	success_url = reverse_lazy("plan-list")

	def get_queryset(self):
		return _trainer_plan_queryset(self.request.user)

	def form_valid(self, form):
		messages.success(self.request, "Plan deleted successfully.")
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
		qs = _trainer_workout_queryset(self.request.user).filter(is_archived=False).select_related("athlete__user", "plan").order_by("-updated_at")
		athlete_pk = _selected_student_pk(self.request)
		status = _selected_status(self.request)
		q = self.request.GET.get("q", "").strip()
		if athlete_pk:
			qs = qs.filter(athlete__pk=athlete_pk)
		if status == "active":
			qs = qs.filter(is_active=True)
		elif status == "inactive":
			qs = qs.filter(is_active=False)
		if q:
			qs = qs.filter(name__icontains=q)
		return qs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["athletes"] = Athlete.objects.filter(
			trainer=self.request.user,
			relationship_status=StudentRelationshipStatus.ACTIVE,
		).select_related("user")
		ctx["selected_athlete"] = _selected_student_pk(self.request) or ""
		ctx["selected_status"] = _selected_status(self.request)
		ctx["search_query"] = self.request.GET.get("q", "")
		return ctx


class WorkoutPlanCreateView(LoginRequiredMixin, TrainerRequiredMixin, CreateView):
	model = WorkoutPlan
	form_class = WorkoutPlanForm
	template_name = "workouts/workout_form.html"

	def get_plan(self):
		plan_pk = self.request.GET.get("plan") or self.request.GET.get("plano") or self.kwargs.get("plan_pk")
		if plan_pk:
			return get_object_or_404(_trainer_plan_queryset(self.request.user), pk=plan_pk)
		return None

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["trainer"] = self.request.user
		kwargs["plan"] = self.get_plan()
		return kwargs

	def get_initial(self):
		initial = super().get_initial()
		athlete_pk = _selected_student_pk(self.request)
		if athlete_pk:
			try:
				athlete = Athlete.objects.get(
					pk=athlete_pk,
					trainer=self.request.user,
					relationship_status=StudentRelationshipStatus.ACTIVE,
				)
				initial["athlete"] = athlete.pk
			except Athlete.DoesNotExist:
				pass
		return initial

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["preselected_athlete"] = _selected_student_pk(self.request) or ""
		plan = self.get_plan()
		if plan:
			ctx["plan"] = plan
		return ctx

	def form_valid(self, form):
		plan = form.cleaned_data.get("plan")
		athlete = plan.athlete if plan else form.cleaned_data["athlete"]
		self.object = WorkoutService.create_workout(
			self.request.user,
			athlete,
			form.cleaned_data["name"],
			plan=plan,
			objective=form.cleaned_data.get("objective", ""),
			is_active=form.cleaned_data.get("is_active", True),
		)
		messages.success(self.request, "Workout created successfully.")
		return redirect(self.get_success_url())

	def get_success_url(self):
		if self.object.plan:
			return reverse("plan-detail", kwargs={"pk": self.object.plan.pk})
		return self.object.get_absolute_url()


class WorkoutPlanUpdateView(LoginRequiredMixin, TrainerRequiredMixin, UpdateView):
	model = WorkoutPlan
	form_class = WorkoutPlanForm
	template_name = "workouts/workout_form.html"

	def get_queryset(self):
		return _trainer_workout_queryset(self.request.user)

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
		messages.success(self.request, "Workout updated successfully.")
		return super().form_valid(form)


class WorkoutPlanDeleteView(LoginRequiredMixin, TrainerRequiredMixin, DeleteView):
	model = WorkoutPlan
	template_name = "workouts/workout_confirm_delete.html"

	def get_queryset(self):
		return _trainer_workout_queryset(self.request.user)

	def form_valid(self, form):
		plan = self.object.plan
		messages.success(self.request, "Workout deleted successfully.")
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
		return _trainer_workout_queryset(self.request.user).select_related("plan", "athlete__user").prefetch_related(
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


class StudentWorkoutListView(LoginRequiredMixin, LinkedStudentRequiredMixin, ListView):
	model = WorkoutPlan
	template_name = "workouts/student_workout_list.html"
	context_object_name = "workouts"

	def get_queryset(self):
		profile = self.request.user.get_athlete_profile()
		return (
			WorkoutPlan.objects.filter(athlete=profile, is_archived=False)
			.select_related("plan")
			.prefetch_related("exercises__exercise_ref")
			.order_by("-is_active", "name")
		)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["profile"] = self.request.user.get_athlete_profile()
		return ctx


class StudentWorkoutDetailView(LoginRequiredMixin, LinkedStudentRequiredMixin, DetailView):
	model = WorkoutPlan
	template_name = "workouts/student_workout_detail.html"
	context_object_name = "workout"

	def get_queryset(self):
		profile = self.request.user.get_athlete_profile()
		return (
			WorkoutPlan.objects.filter(athlete=profile, is_archived=False)
			.select_related("plan", "athlete__trainer")
			.prefetch_related(
				"exercises__exercise_ref",
				"exercises__load_updates",
				"exercises__alternatives__exercise_ref",
			)
		)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		profile = self.request.user.get_athlete_profile()
		ctx["profile"] = profile
		ctx["can_update_loads"] = WorkoutService.student_can_update_workout_loads(self.request.user, self.object)
		ctx["load_form"] = LoadUpdateForm()

		exercises = list(self.object.exercises.all())
		total_sets = 0
		total_load = 0
		muscle_groups: list[str] = []
		for ex in exercises:
			total_sets += ex.sets or 0
			if ex.current_load_kg:
				total_load += float(ex.current_load_kg) * (ex.sets or 0)
			label = ex.muscle_group_label
			if label and label not in muscle_groups:
				muscle_groups.append(label)
		# Rough estimate: ~45s per set + rest seconds
		estimated_seconds = sum(((ex.sets or 0) * (45 + (ex.rest_seconds or 0))) for ex in exercises)
		ctx["stats"] = {
			"exercise_count": len(exercises),
			"total_sets": total_sets,
			"estimated_minutes": int(round(estimated_seconds / 60)) if estimated_seconds else 0,
			"muscle_groups": muscle_groups,
			"total_load_kg": round(total_load, 1) if total_load else 0,
		}
		return ctx


class ExerciseCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=pk)
		form = ExerciseForm(request.POST, trainer=request.user)
		if form.is_valid():
			exercise = form.save(commit=False)
			exercise.workout = workout
			# If exercise_ref is set but name is blank, use the catalog name
			if exercise.exercise_ref and not exercise.name:
				exercise.name = exercise.exercise_ref.name
			exercise.save()
			messages.success(request, f"Exercise '{exercise.display_name}' added successfully.")
		return redirect("workout-detail", pk=workout.pk)


class ExerciseUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Update all tracked fields of an exercise. Creates progress log on save()."""

	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = ExerciseUpdateForm(request.POST, instance=exercise)
		if form.is_valid():
			form.save()  # save() creates ExerciseProgressLog + LoadUpdate automatically
			messages.success(request, "Exercise updated successfully.")
		return redirect("workout-detail", pk=workout.pk)


class ExerciseDeleteView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		name = exercise.display_name
		exercise.delete()
		messages.success(request, f"Exercise '{name}' deleted.")
		return redirect("workout-detail", pk=workout.pk)


class UpdateExerciseLoadView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = LoadUpdateForm(request.POST)
		if form.is_valid():
			new_load = form.cleaned_data["new_load_kg"]
			exercise, _ = WorkoutService.update_exercise_load(
				request.user,
				exercise,
				new_load,
				reason=form.cleaned_data["reason"] or "Manual update",
			)
			messages.success(request, f"Load updated to {new_load} kg.")
		return redirect("workout-detail", pk=workout.pk)


class StudentUpdateExerciseLoadView(LoginRequiredMixin, LinkedStudentRequiredMixin, View):
	def post(self, request, workout_pk, exercise_pk):
		profile = request.user.get_athlete_profile()
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, athlete=profile, is_archived=False)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)

		if not WorkoutService.student_can_update_workout_loads(request.user, workout):
			messages.warning(request, "Este treino exige aprovacao do professor para atualizar cargas.")
			return redirect("student-workout-detail", pk=workout.pk)

		form = LoadUpdateForm(request.POST)
		if form.is_valid():
			new_load = form.cleaned_data["new_load_kg"]
			reason = form.cleaned_data["reason"] or "Student submitted update"
			exercise, _ = WorkoutService.update_exercise_load(
				request.user,
				exercise,
				new_load,
				reason=reason,
			)
			messages.success(request, f"Your load for {exercise.display_name} was updated to {new_load} kg.")
		return redirect("student-workout-detail", pk=workout.pk)


class ExerciseProgressDataView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""JSON endpoint returning progress log data for charts."""

	def get(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
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
		return _trainer_workout_queryset(self.request.user).select_related(
			"athlete__user"
		).prefetch_related("exercises__exercise_ref", "exercises__alternatives__exercise_ref", "sessions__set_logs")

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		exercises = list(self.object.exercises.select_related("exercise_ref").prefetch_related("alternatives__exercise_ref").all())
		active_session = WorkoutExecutionService.get_active_session(self.request.user, self.object)
		if active_session is not None:
			logs_by_exercise = {}
			for set_log in active_session.set_logs.select_related("exercise", "exercise__exercise_ref").order_by("exercise__exercise_order", "set_number"):
				logs_by_exercise.setdefault(set_log.exercise_id, []).append(set_log)
			for exercise in exercises:
				logs = logs_by_exercise.get(exercise.pk, [])
				exercise.session_logs = logs
				exercise.next_set_number = len(logs) + 1
		else:
			for exercise in exercises:
				exercise.session_logs = []
				exercise.next_set_number = 1

		ctx["exercises"] = exercises
		ctx["active_session"] = active_session
		ctx["set_log_form"] = WorkoutSetLogForm()
		ctx["recent_sessions"] = (
			WorkoutSession.objects.filter(workout=self.object, trainer=self.request.user)
			.prefetch_related("set_logs")
			.order_by("-started_at")[:5]
		)
		return ctx


class WorkoutSessionStartView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=pk)
		try:
			session = WorkoutExecutionService.start_session(request.user, workout)
			messages.success(request, f"Session #{session.pk} started.")
		except (PermissionDenied, ValidationError) as exc:
			messages.error(request, getattr(exc, "messages", [str(exc)])[0])
		return redirect("workout-session", pk=workout.pk)


class WorkoutSessionSetLogCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, session_pk, exercise_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		form = WorkoutSetLogForm(request.POST)
		if form.is_valid():
			try:
				set_log = WorkoutExecutionService.log_set(
					request.user,
					session_pk,
					exercise_pk,
					actual_reps=form.cleaned_data["actual_reps"],
					load_kg=form.cleaned_data.get("load_kg"),
					rpe=form.cleaned_data.get("rpe"),
					rir=form.cleaned_data.get("rir"),
					notes=form.cleaned_data.get("notes", ""),
				)
				messages.success(request, f"Set {set_log.set_number} logged for {set_log.exercise.display_name}.")
			except (PermissionDenied, ValidationError) as exc:
				messages.error(request, getattr(exc, "messages", [str(exc)])[0])
		else:
			messages.error(request, "Check reps, load, RPE and RIR before logging the set.")
		return redirect("workout-session", pk=workout.pk)


class WorkoutSessionFinishView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, session_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		try:
			session = WorkoutExecutionService.finish_session(
				request.user,
				session_pk,
				notes=request.POST.get("notes", ""),
			)
			messages.success(request, f"Session #{session.pk} completed.")
		except (PermissionDenied, ValidationError) as exc:
			messages.error(request, getattr(exc, "messages", [str(exc)])[0])
		return redirect("workout-detail", pk=workout.pk)


# ──────────────────────────────────────────────
# Exercise Alternative Management
# ──────────────────────────────────────────────

class AddAlternativeView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Add an alternative exercise to a prescription."""

	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		prescription = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = ExerciseAlternativeForm(request.POST, trainer=request.user)
		if form.is_valid():
			alt = form.save(commit=False)
			alt.prescription = prescription
			alt.save()
			messages.success(request, f"Alternative '{alt.exercise_ref.name}' added.")
		else:
			messages.error(request, "Could not add alternative.")
		return redirect("workout-detail", pk=workout.pk)


class RemoveAlternativeView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Remove an alternative exercise from a prescription."""

	def post(self, request, workout_pk, exercise_pk, alt_pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=workout_pk)
		prescription = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		alt = get_object_or_404(ExerciseAlternative, pk=alt_pk, prescription=prescription)
		name = alt.exercise_ref.name
		alt.delete()
		messages.success(request, f"Alternative '{name}' removed.")
		return redirect("workout-detail", pk=workout.pk)


class ArchiveWorkoutView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Toggle archived state of a workout."""

	def post(self, request, pk):
		workout = get_object_or_404(_trainer_workout_queryset(request.user), pk=pk)
		workout.is_archived = not workout.is_archived
		workout.save(update_fields=["is_archived"])
		status = "archived" if workout.is_archived else "restored"
		messages.success(request, f"Workout {status} successfully.")
		if workout.plan:
			return redirect("plan-detail", pk=workout.plan.pk)
		return redirect("workout-list")

