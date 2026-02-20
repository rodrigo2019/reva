from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from athletes.models import Athlete

from .forms import ExerciseForm, ExerciseUpdateForm, LoadUpdateForm, WorkoutPlanForm
from .models import ExercisePrescription, ExerciseProgressLog, LoadUpdate, WorkoutPlan


class TrainerRequiredMixin(UserPassesTestMixin):
	def test_func(self):
		return self.request.user.is_authenticated and self.request.user.is_trainer


class WorkoutPlanListView(LoginRequiredMixin, TrainerRequiredMixin, ListView):
	model = WorkoutPlan
	template_name = "workouts/trainer_workout_list.html"
	context_object_name = "workouts"

	def get_queryset(self):
		return WorkoutPlan.objects.filter(created_by=self.request.user).select_related("athlete__user")


class WorkoutPlanCreateView(LoginRequiredMixin, TrainerRequiredMixin, CreateView):
	model = WorkoutPlan
	form_class = WorkoutPlanForm
	template_name = "workouts/workout_form.html"

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

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["preselected_athlete"] = self.request.GET.get("aluno", "")
		return ctx

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		return super().form_valid(form)


class WorkoutPlanDetailView(LoginRequiredMixin, TrainerRequiredMixin, DetailView):
	model = WorkoutPlan
	template_name = "workouts/workout_detail.html"
	context_object_name = "workout"

	def get_queryset(self):
		return WorkoutPlan.objects.filter(created_by=self.request.user).prefetch_related(
			"exercises__load_updates", "exercises__progress_logs"
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["exercise_form"] = ExerciseForm()
		context["load_form"] = LoadUpdateForm()
		return context


class ExerciseCreateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, pk):
		workout = get_object_or_404(WorkoutPlan, pk=pk, created_by=request.user)
		form = ExerciseForm(request.POST)
		if form.is_valid():
			exercise = form.save(commit=False)
			exercise.workout = workout
			exercise.save()
		return redirect("workout-detail", pk=workout.pk)


class ExerciseUpdateView(LoginRequiredMixin, TrainerRequiredMixin, View):
	"""Update all tracked fields of an exercise. Creates progress log on save()."""

	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		form = ExerciseUpdateForm(request.POST, instance=exercise)
		if form.is_valid():
			form.save()  # save() creates ExerciseProgressLog + LoadUpdate automatically
		return redirect("workout-detail", pk=workout.pk)


class ExerciseDeleteView(LoginRequiredMixin, TrainerRequiredMixin, View):
	def post(self, request, workout_pk, exercise_pk):
		workout = get_object_or_404(WorkoutPlan, pk=workout_pk, created_by=request.user)
		exercise = get_object_or_404(ExercisePrescription, pk=exercise_pk, workout=workout)
		exercise.delete()
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

