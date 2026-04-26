from django import forms

from athletes.models import Athlete, StudentRelationshipStatus

from .models import Exercise, ExerciseAlternative, ExercisePrescription, TrainingPlan, WorkoutPlan


class TrainingPlanForm(forms.ModelForm):
    class Meta:
        model = TrainingPlan
        fields = ["athlete", "name", "objective", "is_active"]

    def __init__(self, *args, trainer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trainer = trainer
        if trainer is not None:
            self.fields["athlete"].queryset = Athlete.objects.filter(
                trainer=trainer,
                relationship_status=StudentRelationshipStatus.ACTIVE,
            )

    def clean_athlete(self):
        athlete = self.cleaned_data.get("athlete")
        if self.trainer is not None and athlete is not None and (not athlete.has_active_trainer or athlete.trainer_id != self.trainer.id):
            raise forms.ValidationError("Selecione um aluno vinculado a você.")
        return athlete


class WorkoutPlanForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlan
        fields = ["plan", "athlete", "name", "objective", "is_active"]

    def __init__(self, *args, trainer=None, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trainer = trainer
        self.plan_context = plan
        if trainer is not None:
            self.fields["athlete"].queryset = Athlete.objects.filter(
                trainer=trainer,
                relationship_status=StudentRelationshipStatus.ACTIVE,
            )
            self.fields["plan"].queryset = TrainingPlan.objects.filter(
                created_by=trainer,
                athlete__trainer=trainer,
                athlete__relationship_status=StudentRelationshipStatus.ACTIVE,
            )
        self.fields["plan"].required = False
        # When creating from a plan context, pre-select and lock
        if plan is not None:
            self.fields["plan"].initial = plan.pk
            self.fields["plan"].widget = forms.HiddenInput()
            self.fields["athlete"].initial = plan.athlete.pk
            self.fields["athlete"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        athlete = cleaned.get("athlete")
        plan = cleaned.get("plan") or self.plan_context

        if self.trainer is not None and athlete is not None and (not athlete.has_active_trainer or athlete.trainer_id != self.trainer.id):
            self.add_error("athlete", "Selecione um aluno vinculado a você.")

        if plan is not None:
            if self.trainer is not None and plan.created_by_id != self.trainer.id:
                self.add_error("plan", "Selecione um plano criado por você.")
            if self.trainer is not None and (not plan.athlete.has_active_trainer or plan.athlete.trainer_id != self.trainer.id):
                self.add_error("plan", "Selecione um plano de um aluno vinculado a você.")
            cleaned["plan"] = plan
            cleaned["athlete"] = plan.athlete

        return cleaned


class ExerciseAlternativeForm(forms.ModelForm):
    class Meta:
        model = ExerciseAlternative
        fields = ["exercise_ref", "notes", "order"]

    def __init__(self, *args, trainer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        if trainer:
            self.fields["exercise_ref"].queryset = Exercise.objects.filter(
                Q(is_global=True) | Q(created_by=trainer)
            )
        else:
            self.fields["exercise_ref"].queryset = Exercise.objects.filter(is_global=True)


class ExerciseCatalogForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = [
            "name",
            "description",
            "muscle_group",
            "secondary_muscle",
            "equipment",
            "image",
            "video_url",
            "default_sets",
            "default_reps",
            "default_rest_seconds",
            "tips",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "tips": forms.Textarea(attrs={"rows": 3}),
        }


class ExerciseForm(forms.ModelForm):
    """Form for adding an exercise to a workout — supports catalog ref or custom name."""
    exercise_ref = forms.ModelChoiceField(
        queryset=Exercise.objects.none(),
        required=False,
        label="Exercício do catálogo",
    )

    class Meta:
        model = ExercisePrescription
        fields = ["exercise_ref", "name", "sets", "reps", "current_load_kg", "rest_seconds", "exercise_order", "notes"]

    def __init__(self, *args, trainer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        if trainer:
            self.fields["exercise_ref"].queryset = Exercise.objects.filter(
                Q(is_global=True) | Q(created_by=trainer)
            )
        else:
            self.fields["exercise_ref"].queryset = Exercise.objects.filter(is_global=True)

    def clean(self):
        cleaned = super().clean()
        exercise_ref = cleaned.get("exercise_ref")
        name = cleaned.get("name", "").strip()
        if not exercise_ref and not name:
            raise forms.ValidationError(
                "Selecione um exercício do catálogo ou informe um nome customizado."
            )
        return cleaned


class ExerciseUpdateForm(forms.ModelForm):
    """Form for updating all tracked fields of an exercise."""

    class Meta:
        model = ExercisePrescription
        fields = ["name", "sets", "reps", "current_load_kg", "rest_seconds", "notes"]


class LoadUpdateForm(forms.Form):
    new_load_kg = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0)
    reason = forms.CharField(required=False, max_length=255)


class WorkoutSetLogForm(forms.Form):
    actual_reps = forms.IntegerField(min_value=0, max_value=999)
    load_kg = forms.DecimalField(required=False, max_digits=6, decimal_places=2, min_value=0)
    rpe = forms.DecimalField(required=False, max_digits=3, decimal_places=1, min_value=1, max_value=10)
    rir = forms.DecimalField(required=False, max_digits=3, decimal_places=1, min_value=0, max_value=10)
    notes = forms.CharField(required=False, max_length=255)
