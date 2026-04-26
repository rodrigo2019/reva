from django.core.exceptions import PermissionDenied, ValidationError

from athletes.models import Athlete
from workouts.models import ExercisePrescription


class ProgressService:
    @classmethod
    def _resolve_athlete(cls, user, athlete=None):
        if getattr(user, "is_student", False):
            profile = user.get_athlete_profile()
            if profile is None:
                raise ValidationError("Seu perfil de treino ainda nao esta disponivel.")
            if athlete is not None:
                athlete_id = athlete.pk if isinstance(athlete, Athlete) else int(athlete)
                if athlete_id != profile.pk:
                    raise PermissionDenied("Voce nao pode acessar o progresso de outro aluno.")
            return profile

        if getattr(user, "is_trainer", False):
            if athlete is None:
                raise ValidationError("Informe um aluno para consultar progresso como treinador.")
            if isinstance(athlete, Athlete):
                profile = athlete
            else:
                profile = Athlete.objects.select_related("user", "trainer").get(pk=athlete)
            if not profile.has_active_trainer or profile.trainer_id != user.id:
                raise PermissionDenied("Aluno nao encontrado ou fora do seu escopo.")
            return profile

        raise PermissionDenied("Usuario sem permissao para consultar progresso.")

    @classmethod
    def get_exercise_evolution(cls, user, athlete=None):
        profile = cls._resolve_athlete(user, athlete)
        exercises = (
            ExercisePrescription.objects.filter(workout__athlete=profile)
            .select_related("workout", "exercise_ref")
            .prefetch_related("load_updates")
            .order_by("workout__name", "exercise_order", "pk")
        )

        chart_payload = []
        for exercise in exercises:
            points = [
                {"date": update.created_at.strftime("%d/%m/%Y"), "load": float(update.new_load_kg)}
                for update in exercise.load_updates.order_by("created_at")
            ]
            if points:
                chart_payload.append({
                    "id": exercise.pk,
                    "exercise": exercise.display_name,
                    "workout": exercise.workout.name,
                    "points": points,
                })
        return chart_payload
