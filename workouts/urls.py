from django.urls import path

from .views import (
    ExerciseCreateView,
    ExerciseDeleteView,
    ExerciseProgressDataView,
    ExerciseUpdateView,
    UpdateExerciseLoadView,
    WorkoutPlanCreateView,
    WorkoutPlanDeleteView,
    WorkoutPlanDetailView,
    WorkoutPlanListView,
    WorkoutPlanUpdateView,
)

urlpatterns = [
    path("", WorkoutPlanListView.as_view(), name="workout-list"),
    path("novo/", WorkoutPlanCreateView.as_view(), name="workout-create"),
    path("<int:pk>/", WorkoutPlanDetailView.as_view(), name="workout-detail"),
    path("<int:pk>/editar/", WorkoutPlanUpdateView.as_view(), name="workout-edit"),
    path("<int:pk>/excluir/", WorkoutPlanDeleteView.as_view(), name="workout-delete"),
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
]
