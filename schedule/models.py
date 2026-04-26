from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from athletes.models import Athlete
from workouts.models import WorkoutPlan


class ClassSchedule(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", _("Agendada")
        COMPLETED = "completed", _("Realizada")
        CANCELLED = "cancelled", _("Cancelada")
        NO_SHOW = "no_show", _("Falta")

    trainer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="scheduled_classes",
        verbose_name="Treinador",
    )
    athlete = models.ForeignKey(
        Athlete,
        on_delete=models.CASCADE,
        related_name="scheduled_classes",
        verbose_name="Aluno",
    )
    scheduled_at = models.DateTimeField(verbose_name="Data e hora")
    duration_minutes = models.PositiveIntegerField(default=60, verbose_name="Duração (min)")
    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_classes",
        verbose_name="Plano de treino",
    )
    status = models.CharField(
        max_length=20,
        choices=Status,
        default=Status.SCHEDULED,
        verbose_name="Status",
    )
    notes = models.TextField(blank=True, verbose_name="Observações")

    class Meta:
        ordering = ["scheduled_at"]
        verbose_name = "Aula"
        verbose_name_plural = "Aulas"

    def clean(self):
        if self.athlete_id and self.trainer_id and (not self.athlete.has_active_trainer or self.athlete.trainer_id != self.trainer_id):
            raise ValidationError("A aula deve pertencer a um aluno vinculado ao treinador.")
        if self.workout_plan_id and self.athlete_id and self.workout_plan.athlete_id != self.athlete_id:
            raise ValidationError("O treino da aula deve pertencer ao aluno selecionado.")
        if self.workout_plan_id and self.trainer_id and self.workout_plan.created_by_id != self.trainer_id:
            raise ValidationError("O treino da aula deve pertencer ao treinador da aula.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.athlete} — {self.scheduled_at:%d/%m %H:%M}"

    @property
    def status_badge_class(self):
        return {
            self.Status.SCHEDULED: "badge-info",
            self.Status.COMPLETED: "badge-success",
            self.Status.CANCELLED: "badge-ghost",
            self.Status.NO_SHOW: "badge-error",
        }.get(self.status, "badge-ghost")
