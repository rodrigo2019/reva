from django import forms
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError

from .models import Anamnesis, Athlete, PhysicalAssessment
from .services import AthleteService


class StudentRegistrationForm(forms.Form):
    email = forms.EmailField(label="Email do aluno")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Observações",
    )

    linked_user = None

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        try:
            self.linked_user = AthleteService.resolve_linkable_student(getattr(self, "trainer", None), email)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise forms.ValidationError(str(exc)) from exc
        return email

    def save(self, trainer):
        return AthleteService.link_existing_student(
            trainer,
            self.cleaned_data["email"],
            notes=self.cleaned_data.get("notes", ""),
        )


class StudentUpdateForm(forms.Form):
    """Form for editing student data (user fields + athlete notes)."""
    first_name = forms.CharField(max_length=150, label="Nome")
    last_name = forms.CharField(max_length=150, label="Sobrenome")
    email = forms.EmailField(required=False, label="Email")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Observações",
    )
    allow_student_load_updates = forms.BooleanField(
        required=False,
        label="Permitir que o aluno atualize a própria carga",
    )

    def __init__(self, *args, athlete=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.athlete = athlete
        if athlete and not args and not kwargs.get("data"):
            self.initial["first_name"] = athlete.user.first_name
            self.initial["last_name"] = athlete.user.last_name
            self.initial["email"] = athlete.user.email
            self.initial["notes"] = athlete.notes
            self.initial["allow_student_load_updates"] = athlete.allow_student_load_updates

    def save(self):
        self.athlete.user.first_name = self.cleaned_data.get("first_name", "")
        self.athlete.user.last_name = self.cleaned_data.get("last_name", "")
        self.athlete.user.email = self.cleaned_data.get("email", "")
        self.athlete.user.save(update_fields=["first_name", "last_name", "email"])
        self.athlete.notes = self.cleaned_data.get("notes", "")
        self.athlete.allow_student_load_updates = self.cleaned_data.get("allow_student_load_updates", False)
        self.athlete.save(update_fields=["notes", "allow_student_load_updates"])
        return self.athlete


class SetStudentPasswordForm(forms.Form):
    """Trainer sets or resets a student's login password."""
    password = forms.CharField(
        min_length=6,
        max_length=128,
        widget=forms.PasswordInput,
        label="Nova senha",
    )
    password_confirm = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput,
        label="Confirmar senha",
    )

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        pw2 = cleaned.get("password_confirm")
        if pw and pw2 and pw != pw2:
            raise forms.ValidationError("As senhas não coincidem.")
        return cleaned


# ---------------------------------------------------------------------------
# Anamnese
# ---------------------------------------------------------------------------

class AnamnesisForm(forms.ModelForm):
    """Formulário completo de anamnese."""

    class Meta:
        model = Anamnesis
        exclude = ("athlete", "created_at", "updated_at")
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "input w-full"}),
            "gender": forms.Select(attrs={"class": "select w-full"}),
            "phone": forms.TextInput(attrs={"class": "input w-full", "placeholder": "(11) 99999-9999"}),
            "emergency_contact_name": forms.TextInput(attrs={"class": "input w-full", "placeholder": "Nome do contato"}),
            "emergency_contact_phone": forms.TextInput(attrs={"class": "input w-full", "placeholder": "(11) 99999-9999"}),
            "occupation": forms.TextInput(attrs={"class": "input w-full", "placeholder": "Ex: Engenheiro, Estudante…"}),
            "training_experience": forms.Select(attrs={"class": "select w-full"}),
            "training_frequency": forms.NumberInput(attrs={"class": "input w-full", "min": 0, "max": 14, "placeholder": "Ex: 4"}),
            "primary_goal": forms.Select(attrs={"class": "select w-full"}),
            "secondary_goal": forms.TextInput(attrs={"class": "input w-full", "placeholder": "Objetivo adicional…"}),
            "medical_conditions": forms.Textarea(attrs={"class": "textarea w-full", "rows": 3, "placeholder": "Hipertensão, diabetes, asma…"}),
            "medications": forms.Textarea(attrs={"class": "textarea w-full", "rows": 2, "placeholder": "Liste medicamentos em uso…"}),
            "injuries_history": forms.Textarea(attrs={"class": "textarea w-full", "rows": 3, "placeholder": "Descreva lesões passadas ou atuais…"}),
            "surgeries": forms.Textarea(attrs={"class": "textarea w-full", "rows": 2, "placeholder": "Cirurgias realizadas…"}),
            "allergies": forms.Textarea(attrs={"class": "textarea w-full", "rows": 2, "placeholder": "Alergias conhecidas…"}),
            "pain_complaints": forms.Textarea(attrs={"class": "textarea w-full", "rows": 3, "placeholder": "Dor articular, muscular, postural…"}),
            "physical_limitations": forms.Textarea(attrs={"class": "textarea w-full", "rows": 3, "placeholder": "Movimentos que não pode realizar…"}),
            "smoker": forms.CheckboxInput(attrs={"class": "toggle toggle-primary"}),
            "alcohol_consumption": forms.Select(attrs={"class": "select w-full"}),
            "sleep_hours": forms.NumberInput(attrs={"class": "input w-full", "min": 0, "max": 24, "step": "0.5", "placeholder": "Ex: 7.5"}),
            "stress_level": forms.Select(attrs={"class": "select w-full"}),
            "dietary_restrictions": forms.Textarea(attrs={"class": "textarea w-full", "rows": 2, "placeholder": "Intolerância, dieta vegetariana…"}),
            "supplements": forms.Textarea(attrs={"class": "textarea w-full", "rows": 2, "placeholder": "Whey, creatina, multivitamínico…"}),
            "additional_notes": forms.Textarea(attrs={"class": "textarea w-full", "rows": 6, "placeholder": "Escreva qualquer informação relevante em texto livre. A IA vai organizar e formatar depois…"}),
        }


# ---------------------------------------------------------------------------
# Avaliação Física
# ---------------------------------------------------------------------------

class PhysicalAssessmentForm(forms.ModelForm):
    """Formulário de avaliação física / medidas corporais."""

    class Meta:
        model = PhysicalAssessment
        exclude = ("athlete", "created_at")
        widgets = {
            "assessed_at": forms.DateInput(attrs={"type": "date", "class": "input w-full"}),
            "weight_kg": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "Ex: 75.5"}),
            "height_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "Ex: 175.0"}),
            "body_fat_percentage": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "Ex: 15.0"}),
            "neck_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "shoulders_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "chest_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "waist_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "abdomen_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "hips_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "right_arm_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "left_arm_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "right_forearm_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "left_forearm_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "right_thigh_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "left_thigh_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "right_calf_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "left_calf_cm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "cm"}),
            "triceps_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "subscapular_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "suprailiac_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "abdominal_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "thigh_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "chest_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "midaxillary_skinfold_mm": forms.NumberInput(attrs={"class": "input w-full", "step": "0.1", "placeholder": "mm"}),
            "notes": forms.Textarea(attrs={"class": "textarea w-full", "rows": 3, "placeholder": "Observações sobre esta avaliação…"}),
        }
