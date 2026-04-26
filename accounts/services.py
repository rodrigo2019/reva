import json

from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from athletes.models import Athlete, StudentRelationshipStatus
from schedule.models import ClassSchedule
from workouts.models import ExercisePrescription, LoadUpdate, TrainingPlan, WorkoutPlan


class TrainerDashboardService:
	STALE_DAYS = 10
	PLAN_REVIEW_DAYS = 30
	LOAD_JUMP_PERCENT = 20

	@classmethod
	def build_context(cls, trainer):
		now = timezone.now()
		start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
		end_today = start_today + timezone.timedelta(days=1)
		seven_days_ago = now - timezone.timedelta(days=7)
		thirty_days_ago = now - timezone.timedelta(days=30)
		stale_cutoff = now - timezone.timedelta(days=cls.STALE_DAYS)
		plan_review_cutoff = now - timezone.timedelta(days=cls.PLAN_REVIEW_DAYS)

		athletes = Athlete.objects.filter(
			trainer=trainer,
			relationship_status=StudentRelationshipStatus.ACTIVE,
		).select_related("user")
		recent_updates = list(
			LoadUpdate.objects.filter(
				exercise__workout__created_by=trainer,
				exercise__workout__athlete__trainer=trainer,
				exercise__workout__athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
			)
			.select_related("exercise__exercise_ref", "exercise__workout__athlete__user")
			.order_by("-created_at")[:10]
		)
		today_classes = list(
			ClassSchedule.objects.filter(
				trainer=trainer,
				athlete__trainer=trainer,
				athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
				scheduled_at__gte=start_today,
				scheduled_at__lt=end_today,
			)
			.select_related("athlete__user", "workout_plan")
			.order_by("scheduled_at")
		)
		upcoming_classes = list(
			ClassSchedule.objects.filter(
				trainer=trainer,
				athlete__trainer=trainer,
				athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
				scheduled_at__gte=end_today,
				scheduled_at__lt=end_today + timezone.timedelta(days=7),
				status=ClassSchedule.Status.SCHEDULED,
			)
			.select_related("athlete__user", "workout_plan")
			.order_by("scheduled_at")[:6]
		)
		no_show_alerts = list(
			ClassSchedule.objects.filter(
				trainer=trainer,
				athlete__trainer=trainer,
				athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
				status=ClassSchedule.Status.NO_SHOW,
				scheduled_at__gte=now - timezone.timedelta(days=14),
			)
			.select_related("athlete__user", "workout_plan")
			.order_by("-scheduled_at")[:5]
		)

		athletes_with_activity = list(
			athletes.annotate(
				last_load_update_at=Max("workout_plans__exercises__load_updates__created_at"),
				last_session_at=Max("workout_sessions__started_at"),
			).order_by("-last_session_at", "-last_load_update_at", "user__first_name")
		)
		for athlete in athletes_with_activity:
			athlete.last_activity = cls._latest_datetime(
				athlete.last_session_at,
				athlete.last_load_update_at,
			)

		active_student_count = sum(
			1 for athlete in athletes_with_activity
			if athlete.last_activity and athlete.last_activity >= thirty_days_ago
		)
		students_needing_attention = [
			{
				"athlete": athlete,
				"last_activity": athlete.last_activity,
				"reason": cls._attention_reason(athlete.last_activity, cls.STALE_DAYS),
			}
			for athlete in athletes_with_activity
			if athlete.last_activity is None or athlete.last_activity < stale_cutoff
		][:6]

		incomplete_profiles = cls._incomplete_profiles(athletes, now)
		plans_to_review = list(
			TrainingPlan.objects.filter(
				created_by=trainer,
				athlete__trainer=trainer,
				athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
				is_active=True,
				updated_at__lte=plan_review_cutoff,
			)
			.select_related("athlete__user")
			.order_by("updated_at")[:6]
		)
		load_jump_alerts = cls._load_jump_alerts(trainer, now)

		chart_labels, chart_values = cls._weekly_load_update_chart(trainer, now, seven_days_ago)
		metrics = {
			"today_class_count": len(today_classes),
			"attention_count": len(students_needing_attention),
			"incomplete_profile_count": len(incomplete_profiles),
			"plan_review_count": len(plans_to_review),
			"load_jump_count": len(load_jump_alerts),
			"no_show_count": len(no_show_alerts),
		}

		return {
			"athlete_count": athletes.count(),
			"active_student_count": active_student_count,
			"plan_count": TrainingPlan.objects.filter(created_by=trainer, athlete__trainer=trainer, athlete__relationship_status=StudentRelationshipStatus.ACTIVE).count(),
			"workout_count": WorkoutPlan.objects.filter(created_by=trainer, athlete__trainer=trainer, athlete__relationship_status=StudentRelationshipStatus.ACTIVE).count(),
			"active_workout_count": WorkoutPlan.objects.filter(created_by=trainer, athlete__trainer=trainer, athlete__relationship_status=StudentRelationshipStatus.ACTIVE, is_active=True).count(),
			"exercise_count": ExercisePrescription.objects.filter(workout__created_by=trainer, workout__athlete__trainer=trainer, workout__athlete__relationship_status=StudentRelationshipStatus.ACTIVE).count(),
			"recent_updates": recent_updates,
			"athletes": athletes_with_activity[:8],
			"seven_days_ago": seven_days_ago,
			"today_classes": today_classes,
			"upcoming_classes": upcoming_classes,
			"students_needing_attention": students_needing_attention,
			"incomplete_profiles": incomplete_profiles,
			"plans_to_review": plans_to_review,
			"load_jump_alerts": load_jump_alerts,
			"no_show_alerts": no_show_alerts,
			"suggested_tasks": cls._suggested_tasks(metrics),
			"chart_labels": json.dumps(chart_labels),
			"chart_values": json.dumps(chart_values),
			**metrics,
		}

	@staticmethod
	def _latest_datetime(*values):
		present_values = [value for value in values if value is not None]
		return max(present_values) if present_values else None

	@staticmethod
	def _attention_reason(last_activity, stale_days):
		if last_activity is None:
			return "Sem execucao registrada"
		return f"Sem treino ha mais de {stale_days} dias"

	@staticmethod
	def _incomplete_profiles(athletes, now):
		rows = athletes.annotate(
			anamnesis_count=Count("anamnesis_records", distinct=True),
			assessment_count=Count("physical_assessments", distinct=True),
			active_plan_count=Count(
				"training_plans",
				filter=Q(training_plans__is_active=True),
				distinct=True,
			),
			upcoming_class_count=Count(
				"scheduled_classes",
				filter=Q(
					scheduled_classes__scheduled_at__gte=now,
					scheduled_classes__status=ClassSchedule.Status.SCHEDULED,
				),
				distinct=True,
			),
		).order_by("user__first_name", "user__last_name")

		items = []
		for athlete in rows:
			missing = []
			if athlete.anamnesis_count == 0:
				missing.append("anamnese")
			if athlete.assessment_count == 0:
				missing.append("avaliacao")
			if athlete.active_plan_count == 0:
				missing.append("plano ativo")
			if athlete.upcoming_class_count == 0:
				missing.append("proxima aula")
			if missing:
				items.append({"athlete": athlete, "missing": missing})
		return items[:6]

	@classmethod
	def _load_jump_alerts(cls, trainer, now):
		updates = (
			LoadUpdate.objects.filter(
				exercise__workout__created_by=trainer,
				exercise__workout__athlete__trainer=trainer,
				exercise__workout__athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
				created_at__gte=now - timezone.timedelta(days=14),
				previous_load_kg__isnull=False,
			)
			.select_related("exercise__exercise_ref", "exercise__workout__athlete__user")
			.order_by("-created_at")[:30]
		)

		alerts = []
		for update in updates:
			if not update.previous_load_kg or update.previous_load_kg <= 0:
				continue
			percent = ((update.new_load_kg - update.previous_load_kg) / update.previous_load_kg) * 100
			if percent >= cls.LOAD_JUMP_PERCENT:
				alerts.append({"update": update, "percent": round(float(percent))})
		return alerts[:5]

	@staticmethod
	def _weekly_load_update_chart(trainer, now, seven_days_ago):
		daily_updates = (
			LoadUpdate.objects.filter(
				exercise__workout__created_by=trainer,
				exercise__workout__athlete__trainer=trainer,
				exercise__workout__athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
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
		return chart_labels, chart_values

	@staticmethod
	def _suggested_tasks(metrics):
		tasks = []
		if metrics["today_class_count"]:
			tasks.append({
				"title": "Conduzir aulas de hoje",
				"detail": f"{metrics['today_class_count']} aula(s) na agenda",
				"url": reverse("schedule"),
				"tone": "primary",
			})
		if metrics["attention_count"]:
			tasks.append({
				"title": "Revisar alunos sem atividade",
				"detail": f"{metrics['attention_count']} aluno(s) sem sinal recente",
				"url": reverse("student-list"),
				"tone": "warning",
			})
		if metrics["incomplete_profile_count"]:
			tasks.append({
				"title": "Completar perfis",
				"detail": f"{metrics['incomplete_profile_count']} perfil(is) com pendencias",
				"url": reverse("student-list"),
				"tone": "secondary",
			})
		if metrics["plan_review_count"]:
			tasks.append({
				"title": "Revisar planos antigos",
				"detail": f"{metrics['plan_review_count']} plano(s) ativos sem revisao recente",
				"url": reverse("plan-list"),
				"tone": "accent",
			})
		if metrics["load_jump_count"]:
			tasks.append({
				"title": "Checar saltos de carga",
				"detail": f"{metrics['load_jump_count']} atualizacao(oes) acima do esperado",
				"url": "#alertas-operacionais",
				"tone": "error",
			})
		return tasks[:5]