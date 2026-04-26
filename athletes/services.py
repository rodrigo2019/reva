from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserRole

from .models import Athlete, StudentRelationshipStatus


class AthleteService:
    @staticmethod
    def require_trainer(user):
        if user is None or not getattr(user, "is_trainer", False):
            raise PermissionDenied("Apenas treinadores podem gerenciar alunos.")
        return user

    @classmethod
    def get_owned_athlete(cls, trainer, athlete_id):
        trainer = cls.require_trainer(trainer)
        try:
            return Athlete.objects.select_related("user", "trainer").get(
                pk=athlete_id,
                trainer=trainer,
                relationship_status=StudentRelationshipStatus.ACTIVE,
            )
        except Athlete.DoesNotExist as exc:
            raise PermissionDenied("Aluno nao encontrado ou fora do seu escopo.") from exc

    @staticmethod
    def require_student(user):
        if user is None or not getattr(user, "is_student", False):
            raise PermissionDenied("Apenas alunos podem manter um perfil de treino.")
        return user

    @classmethod
    def get_or_create_student_profile(cls, user):
        user = cls.require_student(user)
        profile, _ = Athlete.objects.get_or_create(user=user)
        return profile

    @classmethod
    def resolve_linkable_student(cls, trainer, email):
        cls.require_trainer(trainer)
        email = (email or "").strip()
        if not email:
            raise ValidationError("Informe o e-mail da conta de aluno ja cadastrada.")

        users = User.objects.filter(email__iexact=email).order_by("pk")
        count = users.count()
        if count == 0:
            raise ValidationError(
                "Nenhum usuário com este e-mail foi encontrado. O aluno precisa se cadastrar primeiro na plataforma.",
            )
        if count > 1:
            raise ValidationError(
                "Há mais de uma conta com este e-mail. Regularize o cadastro antes de fazer o vínculo.",
            )

        user = users.first()
        if user.role != UserRole.STUDENT:
            raise ValidationError("O e-mail informado pertence a uma conta que não é de aluno.")

        existing = Athlete.objects.filter(user=user).select_related("trainer").first()
        if existing is not None and existing.has_active_trainer:
            if existing.trainer_id == trainer.id:
                raise ValidationError("Este aluno já está vinculado a você.")
            raise ValidationError("Este aluno já está vinculado a outro treinador.")

        return user

    @classmethod
    def link_existing_student(cls, trainer, email, notes="", allow_existing_for_trainer=False):
        trainer = cls.require_trainer(trainer)
        with transaction.atomic():
            try:
                user = cls.resolve_linkable_student(trainer, email)
            except ValidationError:
                if allow_existing_for_trainer:
                    existing = Athlete.objects.filter(
                        user__email__iexact=(email or "").strip(),
                        trainer=trainer,
                    ).select_related("user").first()
                    if existing is not None:
                        return existing
                raise
            athlete, _ = Athlete.objects.select_for_update().get_or_create(user=user)
            if athlete.has_active_trainer:
                if athlete.trainer_id == trainer.id and allow_existing_for_trainer:
                    return athlete
                raise ValidationError("Este aluno já está vinculado a outro treinador.")

            athlete.trainer = trainer
            athlete.relationship_status = StudentRelationshipStatus.ACTIVE
            athlete.relationship_started_at = timezone.now()
            athlete.relationship_ended_at = None
            athlete.notes = (notes or "").strip()
            athlete.save(update_fields=[
                "trainer",
                "relationship_status",
                "relationship_started_at",
                "relationship_ended_at",
                "notes",
            ])
            return athlete

    @classmethod
    def end_relationship(cls, trainer, athlete):
        trainer = cls.require_trainer(trainer)
        athlete = cls.get_owned_athlete(trainer, athlete.pk if isinstance(athlete, Athlete) else athlete)
        athlete.trainer = None
        athlete.relationship_status = StudentRelationshipStatus.ENDED
        athlete.relationship_ended_at = timezone.now()
        athlete.allow_student_load_updates = False
        athlete.save(update_fields=["trainer", "relationship_status", "relationship_ended_at", "allow_student_load_updates"])
        return athlete
