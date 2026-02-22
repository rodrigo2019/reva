from django.urls import path

from .views import (
    AddAlternativeView,
    ArchiveWorkoutView,
    ExerciseCreateView,
    ExerciseDeleteView,
    ExerciseProgressDataView,
    ExerciseUpdateView,
    RemoveAlternativeView,
    TrainingPlanCreateView,
    TrainingPlanDeleteView,
    TrainingPlanDetailView,
    TrainingPlanListView,
    TrainingPlanUpdateView,
    UpdateExerciseLoadView,
    WorkoutPlanCreateView,
    WorkoutPlanDeleteView,
    WorkoutPlanDetailView,
    WorkoutPlanListView,
    WorkoutPlanUpdateView,
    WorkoutSessionView,
)

urlpatterns = [
    # ── Training Plans ──
    path("planos/", TrainingPlanListView.as_view(), name="plan-list"),
    path("planos/novo/", TrainingPlanCreateView.as_view(), name="plan-create"),
    path("planos/<int:pk>/", TrainingPlanDetailView.as_view(), name="plan-detail"),
    path("planos/<int:pk>/editar/", TrainingPlanUpdateView.as_view(), name="plan-edit"),
    path("planos/<int:pk>/excluir/", TrainingPlanDeleteView.as_view(), name="plan-delete"),
    path("planos/<int:plan_pk>/novo-treino/", WorkoutPlanCreateView.as_view(), name="plan-workout-create"),

    # ── Workouts ──
    path("", WorkoutPlanListView.as_view(), name="workout-list"),
    path("novo/", WorkoutPlanCreateView.as_view(), name="workout-create"),
    path("<int:pk>/", WorkoutPlanDetailView.as_view(), name="workout-detail"),
    path("<int:pk>/editar/", WorkoutPlanUpdateView.as_view(), name="workout-edit"),
    path("<int:pk>/sessao/", WorkoutSessionView.as_view(), name="workout-session"),
    path("<int:pk>/excluir/", WorkoutPlanDeleteView.as_view(), name="workout-delete"),
    path("<int:pk>/arquivar/", ArchiveWorkoutView.as_view(), name="workout-archive"),

    # ── Exercises ──
    path("<int:pk>/exercicios/", ExerciseCreateView.as_view(), name="exercise-create"),
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/carga/",
        UpdateExerciseLoadView.as_view(),
        name="exercise-load-update",
    ),
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/editar/",
        ExerciseUpdateView.as_view(),
        name="exercise-update",
    ),
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/excluir/",
        ExerciseDeleteView.as_view(),
        name="exercise-delete",
    ),
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/progresso/",
        ExerciseProgressDataView.as_view(),
        name="exercise-progress-data",
    ),

    # ── Exercise Alternatives ──
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/substituto/",
        AddAlternativeView.as_view(),
        name="exercise-add-alternative",
    ),
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/substituto/<int:alt_pk>/excluir/",
        RemoveAlternativeView.as_view(),
        name="exercise-remove-alternative",
    ),
]
