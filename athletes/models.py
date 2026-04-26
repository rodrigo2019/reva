from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class StudentRelationshipStatus(models.TextChoices):
	INDEPENDENT = "independent", "Independente"
	INVITED = "invited", "Convite pendente"
	ACTIVE = "active", "Acompanhado"
	PAUSED = "paused", "Pausado"
	ENDED = "ended", "Encerrado"


class Athlete(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="athlete_profile")
	trainer = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		related_name="athletes",
		null=True,
		blank=True,
	)
	relationship_status = models.CharField(
		max_length=20,
		choices=StudentRelationshipStatus.choices,
		default=StudentRelationshipStatus.INDEPENDENT,
	)
	notes = models.TextField(blank=True)
	allow_student_load_updates = models.BooleanField(
		default=False,
		verbose_name="Permitir atualizacao de carga pelo aluno",
		help_text="Quando ativo, o aluno pode registrar a propria evolucao de carga nos treinos.",
	)
	relationship_started_at = models.DateTimeField(null=True, blank=True)
	relationship_ended_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def clean(self):
		if self.trainer_id and self.user_id == self.trainer_id:
			raise ValidationError("Treinador e aluno não podem ser a mesma pessoa.")
		if hasattr(self.user, "is_student") and not self.user.is_student:
			raise ValidationError("O perfil de atleta deve estar vinculado a um usuário aluno.")
		if self.trainer_id and hasattr(self.trainer, "is_trainer") and not self.trainer.is_trainer:
			raise ValidationError("O treinador vinculado deve ter perfil de treinador.")
		if self.trainer_id and self.relationship_status == StudentRelationshipStatus.INDEPENDENT:
			raise ValidationError("Aluno com treinador ativo nao pode estar marcado como independente.")
		if not self.trainer_id and self.relationship_status == StudentRelationshipStatus.ACTIVE:
			raise ValidationError("Vinculo ativo requer um treinador.")

	def save(self, *args, **kwargs):
		update_fields = kwargs.get("update_fields")
		changed_fields = set()
		if self.trainer_id and self.relationship_status in {
			StudentRelationshipStatus.INDEPENDENT,
			StudentRelationshipStatus.ENDED,
		}:
			self.relationship_status = StudentRelationshipStatus.ACTIVE
			changed_fields.add("relationship_status")
			if self.relationship_started_at is None:
				self.relationship_started_at = timezone.now()
				changed_fields.add("relationship_started_at")
			self.relationship_ended_at = None
			changed_fields.add("relationship_ended_at")
		elif not self.trainer_id and self.relationship_status == StudentRelationshipStatus.ACTIVE:
			self.relationship_status = StudentRelationshipStatus.INDEPENDENT
			changed_fields.add("relationship_status")
		if update_fields is not None and changed_fields:
			kwargs["update_fields"] = set(update_fields) | changed_fields
		self.full_clean()
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.user.get_full_name() or self.user.username}"

	@property
	def latest_anamnesis(self):
		return self.anamnesis_records.order_by("-created_at").first()

	@property
	def latest_assessment(self):
		return self.physical_assessments.order_by("-assessed_at").first()

	@property
	def has_active_trainer(self):
		return self.trainer_id is not None and self.relationship_status == StudentRelationshipStatus.ACTIVE

	@property
	def is_independent(self):
		return not self.has_active_trainer

	@property
	def can_manage_own_loads(self):
		return self.is_independent or self.allow_student_load_updates


# ---------------------------------------------------------------------------
# Anamnesis – Ficha de Anamnese do Aluno
# ---------------------------------------------------------------------------

class GenderChoices(models.TextChoices):
	MALE = "M", "Masculino"
	FEMALE = "F", "Feminino"
	OTHER = "O", "Outro"


class TrainingExperienceChoices(models.TextChoices):
	NONE = "none", "Nenhuma (sedentário)"
	BEGINNER = "beginner", "Iniciante (< 6 meses)"
	INTERMEDIATE = "intermediate", "Intermediário (6 meses – 2 anos)"
	ADVANCED = "advanced", "Avançado (2 – 5 anos)"
	ELITE = "elite", "Elite (> 5 anos)"


class PrimaryGoalChoices(models.TextChoices):
	HYPERTROPHY = "hypertrophy", "Hipertrofia"
	STRENGTH = "strength", "Força"
	WEIGHT_LOSS = "weight_loss", "Emagrecimento"
	HEALTH = "health", "Saúde e qualidade de vida"
	SPORT = "sport", "Performance esportiva"
	REHAB = "rehab", "Reabilitação"
	FLEXIBILITY = "flexibility", "Flexibilidade / Mobilidade"
	ENDURANCE = "endurance", "Resistência / Condicionamento"
	OTHER = "other", "Outro"


class AlcoholConsumptionChoices(models.TextChoices):
	NONE = "none", "Não consome"
	SOCIAL = "social", "Social (eventual)"
	MODERATE = "moderate", "Moderado (1-2x/semana)"
	FREQUENT = "frequent", "Frequente (3+x/semana)"


class StressLevelChoices(models.TextChoices):
	LOW = "low", "Baixo"
	MODERATE = "moderate", "Moderado"
	HIGH = "high", "Alto"
	VERY_HIGH = "very_high", "Muito alto"


class Anamnesis(models.Model):
	"""Ficha de anamnese completa do aluno — dados pessoais, saúde e estilo de vida."""

	athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="anamnesis_records")

	# --- Dados pessoais ---
	date_of_birth = models.DateField("Data de nascimento", null=True, blank=True)
	gender = models.CharField("Sexo", max_length=1, choices=GenderChoices.choices, blank=True)
	phone = models.CharField("Telefone", max_length=20, blank=True)
	emergency_contact_name = models.CharField("Contato de emergência", max_length=200, blank=True)
	emergency_contact_phone = models.CharField("Telefone emergência", max_length=20, blank=True)
	occupation = models.CharField("Profissão", max_length=150, blank=True)

	# --- Experiência e objetivo ---
	training_experience = models.CharField(
		"Nível de experiência",
		max_length=20,
		choices=TrainingExperienceChoices.choices,
		blank=True,
	)
	training_frequency = models.PositiveSmallIntegerField(
		"Frequência semanal de treino",
		null=True, blank=True,
		validators=[MinValueValidator(0), MaxValueValidator(14)],
		help_text="Quantas vezes por semana o aluno treina ou pretende treinar",
	)
	primary_goal = models.CharField(
		"Objetivo principal",
		max_length=20,
		choices=PrimaryGoalChoices.choices,
		blank=True,
	)
	secondary_goal = models.CharField("Objetivo secundário", max_length=200, blank=True)

	# --- Saúde e histórico médico ---
	medical_conditions = models.TextField(
		"Condições médicas / Doenças",
		blank=True,
		help_text="Ex.: hipertensão, diabetes, asma, cardiopatia…",
	)
	medications = models.TextField("Medicamentos em uso", blank=True)
	injuries_history = models.TextField(
		"Histórico de lesões",
		blank=True,
		help_text="Descreva lesões passadas ou atuais",
	)
	surgeries = models.TextField("Cirurgias realizadas", blank=True)
	allergies = models.TextField("Alergias", blank=True)
	pain_complaints = models.TextField(
		"Queixas de dor / Desconfortos",
		blank=True,
		help_text="Dor articular, muscular, postural etc.",
	)
	physical_limitations = models.TextField(
		"Limitações físicas",
		blank=True,
		help_text="Movimentos que não consegue realizar, restrições médicas…",
	)

	# --- Estilo de vida ---
	smoker = models.BooleanField("Fumante", default=False)
	alcohol_consumption = models.CharField(
		"Consumo de álcool",
		max_length=10,
		choices=AlcoholConsumptionChoices.choices,
		default=AlcoholConsumptionChoices.NONE,
		blank=True,
	)
	sleep_hours = models.DecimalField(
		"Horas de sono por noite",
		max_digits=3, decimal_places=1,
		null=True, blank=True,
		validators=[MinValueValidator(0), MaxValueValidator(24)],
	)
	stress_level = models.CharField(
		"Nível de estresse",
		max_length=10,
		choices=StressLevelChoices.choices,
		blank=True,
	)

	# --- Alimentação ---
	dietary_restrictions = models.TextField(
		"Restrições alimentares",
		blank=True,
		help_text="Intolerância, dieta vegetariana, etc.",
	)
	supplements = models.TextField("Suplementos em uso", blank=True)

	# --- Campo livre / texto corrido ---
	additional_notes = models.TextField(
		"Anamnese geral (texto livre)",
		blank=True,
		help_text="Escreva aqui qualquer informação adicional. A IA irá organizar e formatar.",
	)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = "Anamnese"
		verbose_name_plural = "Anamneses"
		ordering = ["-created_at"]

	def __str__(self):
		return f"Anamnese de {self.athlete} — {self.created_at:%d/%m/%Y}"


# ---------------------------------------------------------------------------
# PhysicalAssessment – Avaliação Física / Medidas Corporais
# ---------------------------------------------------------------------------

class PhysicalAssessment(models.Model):
	"""Registro de avaliação física com medidas antropométricas."""

	athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="physical_assessments")

	assessed_at = models.DateField("Data da avaliação", default=timezone.now)

	# --- Dados principais ---
	weight_kg = models.DecimalField(
		"Peso (kg)", max_digits=5, decimal_places=2,
		null=True, blank=True,
		validators=[MinValueValidator(Decimal("10")), MaxValueValidator(Decimal("400"))],
	)
	height_cm = models.DecimalField(
		"Altura (cm)", max_digits=5, decimal_places=1,
		null=True, blank=True,
		validators=[MinValueValidator(Decimal("50")), MaxValueValidator(Decimal("300"))],
	)
	body_fat_percentage = models.DecimalField(
		"Gordura corporal (%)", max_digits=4, decimal_places=1,
		null=True, blank=True,
		validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("70"))],
	)

	# --- Circunferências (cm) ---
	neck_cm = models.DecimalField("Pescoço (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	shoulders_cm = models.DecimalField("Ombros (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	chest_cm = models.DecimalField("Tórax / Peito (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	waist_cm = models.DecimalField("Cintura (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	abdomen_cm = models.DecimalField("Abdômen (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	hips_cm = models.DecimalField("Quadril (cm)", max_digits=5, decimal_places=1, null=True, blank=True)

	right_arm_cm = models.DecimalField("Braço direito (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	left_arm_cm = models.DecimalField("Braço esquerdo (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	right_forearm_cm = models.DecimalField("Antebraço direito (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	left_forearm_cm = models.DecimalField("Antebraço esquerdo (cm)", max_digits=5, decimal_places=1, null=True, blank=True)

	right_thigh_cm = models.DecimalField("Coxa direita (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	left_thigh_cm = models.DecimalField("Coxa esquerda (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	right_calf_cm = models.DecimalField("Panturrilha direita (cm)", max_digits=5, decimal_places=1, null=True, blank=True)
	left_calf_cm = models.DecimalField("Panturrilha esquerda (cm)", max_digits=5, decimal_places=1, null=True, blank=True)

	# --- Dobras cutâneas (mm) – opcional ---
	triceps_skinfold_mm = models.DecimalField("Dobra tricipital (mm)", max_digits=4, decimal_places=1, null=True, blank=True)
	subscapular_skinfold_mm = models.DecimalField("Dobra subescapular (mm)", max_digits=4, decimal_places=1, null=True, blank=True)
	suprailiac_skinfold_mm = models.DecimalField("Dobra suprailíaca (mm)", max_digits=4, decimal_places=1, null=True, blank=True)
	abdominal_skinfold_mm = models.DecimalField("Dobra abdominal (mm)", max_digits=4, decimal_places=1, null=True, blank=True)
	thigh_skinfold_mm = models.DecimalField("Dobra da coxa (mm)", max_digits=4, decimal_places=1, null=True, blank=True)
	chest_skinfold_mm = models.DecimalField("Dobra peitoral (mm)", max_digits=4, decimal_places=1, null=True, blank=True)
	midaxillary_skinfold_mm = models.DecimalField("Dobra axilar média (mm)", max_digits=4, decimal_places=1, null=True, blank=True)

	notes = models.TextField("Observações da avaliação", blank=True)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Avaliação Física"
		verbose_name_plural = "Avaliações Físicas"
		ordering = ["-assessed_at"]

	def __str__(self):
		return f"Avaliação de {self.athlete} — {self.assessed_at:%d/%m/%Y}"

	@property
	def bmi(self):
		"""Calcula o IMC (Índice de Massa Corporal)."""
		if self.weight_kg and self.height_cm and self.height_cm > 0:
			height_m = self.height_cm / Decimal("100")
			return round(self.weight_kg / (height_m ** 2), 1)
		return None

	@property
	def bmi_classification(self):
		"""Classificação do IMC segundo a OMS."""
		bmi = self.bmi
		if bmi is None:
			return ""
		if bmi < 18.5:
			return "Abaixo do peso"
		elif bmi < 25:
			return "Peso normal"
		elif bmi < 30:
			return "Sobrepeso"
		elif bmi < 35:
			return "Obesidade Grau I"
		elif bmi < 40:
			return "Obesidade Grau II"
		else:
			return "Obesidade Grau III"

	@property
	def lean_mass_kg(self):
		"""Massa magra estimada."""
		if self.weight_kg and self.body_fat_percentage:
			fat_mass = self.weight_kg * (self.body_fat_percentage / Decimal("100"))
			return round(self.weight_kg - fat_mass, 1)
		return None

	@property
	def fat_mass_kg(self):
		"""Massa gorda estimada."""
		if self.weight_kg and self.body_fat_percentage:
			return round(self.weight_kg * (self.body_fat_percentage / Decimal("100")), 1)
		return None

	@property
	def waist_hip_ratio(self):
		"""Relação cintura-quadril (RCQ)."""
		if self.waist_cm and self.hips_cm and self.hips_cm > 0:
			return round(self.waist_cm / self.hips_cm, 2)
		return None

	@property
	def lean_mass_percentage(self):
		"""Percentual de massa magra (100 - gordura)."""
		if self.body_fat_percentage:
			return round(Decimal("100") - self.body_fat_percentage, 1)
		return None
