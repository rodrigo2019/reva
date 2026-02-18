from django.urls import path

from .views import (
    ExerciseCreateView,
    UpdateExerciseLoadView,
    WorkoutPlanCreateView,
    WorkoutPlanDetailView,
    WorkoutPlanListView,
)

urlpatterns = [
    path("", WorkoutPlanListView.as_view(), name="workout-list"),
    path("novo/", WorkoutPlanCreateView.as_view(), name="workout-create"),
    path("<int:pk>/", WorkoutPlanDetailView.as_view(), name="workout-detail"),
    path("<int:pk>/exercicios/", ExerciseCreateView.as_view(), name="exercise-create"),
    path(
        "<int:workout_pk>/exercicios/<int:exercise_pk>/carga/",
        UpdateExerciseLoadView.as_view(),
        name="exercise-load-update",
    ),
]
