from django import forms

from athletes.models import Athlete

from .models import ExercisePrescription, WorkoutPlan


class WorkoutPlanForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlan
        fields = ["athlete", "name", "objective", "is_active"]

    def __init__(self, *args, trainer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if trainer is not None:
            self.fields["athlete"].queryset = Athlete.objects.filter(trainer=trainer)


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = ExercisePrescription
        fields = ["name", "sets", "reps", "current_load_kg", "rest_seconds", "exercise_order", "notes"]


class LoadUpdateForm(forms.Form):
    new_load_kg = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0)
    reason = forms.CharField(required=False, max_length=255)
