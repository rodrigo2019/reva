from django.urls import path

from .exercise_views import (
    ExerciseCatalogCreateView,
    ExerciseCatalogDeleteView,
    ExerciseCatalogDetailView,
    ExerciseCatalogListView,
    ExerciseCatalogSearchView,
    ExerciseCatalogUpdateView,
)

urlpatterns = [
    path("", ExerciseCatalogListView.as_view(), name="exercise-catalog-list"),
    path("novo/", ExerciseCatalogCreateView.as_view(), name="exercise-catalog-create"),
    path("buscar/", ExerciseCatalogSearchView.as_view(), name="exercise-catalog-search"),
    path("<int:pk>/", ExerciseCatalogDetailView.as_view(), name="exercise-catalog-detail"),
    path("<int:pk>/editar/", ExerciseCatalogUpdateView.as_view(), name="exercise-catalog-edit"),
    path("<int:pk>/excluir/", ExerciseCatalogDeleteView.as_view(), name="exercise-catalog-delete"),
]
