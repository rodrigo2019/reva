from django.urls import path

from .views import (
    AddAlternativeView,
    ArchiveWorkoutView,
    ExerciseCreateView,
    ExerciseDeleteView,
    ExerciseProgressDataView,
    ExerciseUpdateView,
    RemoveAlternativeView,
    StudentUpdateExerciseLoadView,
    StudentWorkoutDetailView,
    StudentWorkoutListView,
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
    WorkoutSessionFinishView,
    WorkoutSessionSetLogCreateView,
    WorkoutSessionStartView,
    WorkoutSessionView,
)

urlpatterns = [
    path("my/", StudentWorkoutListView.as_view(), name="student-workout-list"),
    path("my/<int:pk>/", StudentWorkoutDetailView.as_view(), name="student-workout-detail"),
    path(
        "my/<int:workout_pk>/exercises/<int:exercise_pk>/load/",
        StudentUpdateExerciseLoadView.as_view(),
        name="student-exercise-load-update",
    ),

    # ── Training Plans ──
    path("plans/", TrainingPlanListView.as_view(), name="plan-list"),
    path("plans/new/", TrainingPlanCreateView.as_view(), name="plan-create"),
    path("plans/<int:pk>/", TrainingPlanDetailView.as_view(), name="plan-detail"),
    path("plans/<int:pk>/edit/", TrainingPlanUpdateView.as_view(), name="plan-edit"),
    path("plans/<int:pk>/delete/", TrainingPlanDeleteView.as_view(), name="plan-delete"),
    path("plans/<int:plan_pk>/workouts/new/", WorkoutPlanCreateView.as_view(), name="plan-workout-create"),

    # ── Workouts ──
    path("", WorkoutPlanListView.as_view(), name="workout-list"),
    path("new/", WorkoutPlanCreateView.as_view(), name="workout-create"),
    path("<int:pk>/", WorkoutPlanDetailView.as_view(), name="workout-detail"),
    path("<int:pk>/edit/", WorkoutPlanUpdateView.as_view(), name="workout-edit"),
    path("<int:pk>/session/", WorkoutSessionView.as_view(), name="workout-session"),
    path("<int:pk>/session/start/", WorkoutSessionStartView.as_view(), name="workout-session-start"),
    path(
        "<int:workout_pk>/session/<int:session_pk>/exercises/<int:exercise_pk>/sets/",
        WorkoutSessionSetLogCreateView.as_view(),
        name="workout-session-set-log",
    ),
    path(
        "<int:workout_pk>/session/<int:session_pk>/finish/",
        WorkoutSessionFinishView.as_view(),
        name="workout-session-finish",
    ),
    path("<int:pk>/delete/", WorkoutPlanDeleteView.as_view(), name="workout-delete"),
    path("<int:pk>/archive/", ArchiveWorkoutView.as_view(), name="workout-archive"),

    # ── Exercises ──
    path("<int:pk>/exercises/", ExerciseCreateView.as_view(), name="exercise-create"),
    path(
        "<int:workout_pk>/exercises/<int:exercise_pk>/load/",
        UpdateExerciseLoadView.as_view(),
        name="exercise-load-update",
    ),
    path(
        "<int:workout_pk>/exercises/<int:exercise_pk>/edit/",
        ExerciseUpdateView.as_view(),
        name="exercise-update",
    ),
    path(
        "<int:workout_pk>/exercises/<int:exercise_pk>/delete/",
        ExerciseDeleteView.as_view(),
        name="exercise-delete",
    ),
    path(
        "<int:workout_pk>/exercises/<int:exercise_pk>/progress/",
        ExerciseProgressDataView.as_view(),
        name="exercise-progress-data",
    ),

    # ── Exercise Alternatives ──
    path(
        "<int:workout_pk>/exercises/<int:exercise_pk>/alternatives/",
        AddAlternativeView.as_view(),
        name="exercise-add-alternative",
    ),
    path(
        "<int:workout_pk>/exercises/<int:exercise_pk>/alternatives/<int:alt_pk>/delete/",
        RemoveAlternativeView.as_view(),
        name="exercise-remove-alternative",
    ),
]
