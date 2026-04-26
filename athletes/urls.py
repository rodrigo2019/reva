from django.urls import path

from .views import (
    AnamnesisCreateUpdateView,
    PhysicalAssessmentCreateView,
    PhysicalAssessmentDeleteView,
    PhysicalAssessmentUpdateView,
    SetStudentPasswordView,
    StudentCreateView,
    StudentDeleteView,
    StudentDetailView,
    StudentListView,
    StudentProfileView,
    StudentUpdateView,
    TrainerStudentProgressView,
)

urlpatterns = [
    path("", StudentListView.as_view(), name="student-list"),
    path("new/", StudentCreateView.as_view(), name="student-create"),
    path("<int:pk>/", StudentDetailView.as_view(), name="student-detail"),
    path("<int:pk>/edit/", StudentUpdateView.as_view(), name="student-edit"),
    path("<int:pk>/delete/", StudentDeleteView.as_view(), name="student-delete"),
    path("<int:pk>/password/", SetStudentPasswordView.as_view(), name="student-set-password"),
    path("<int:pk>/progress/", TrainerStudentProgressView.as_view(), name="student-progress"),
    # --- Perfil / Ficha completa ---
    path("<int:pk>/profile/", StudentProfileView.as_view(), name="student-profile"),
    path("<int:pk>/anamnesis/", AnamnesisCreateUpdateView.as_view(), name="student-anamnesis"),
    path("<int:pk>/assessments/new/", PhysicalAssessmentCreateView.as_view(), name="student-assessment-create"),
    path("<int:pk>/assessments/<int:assessment_pk>/edit/", PhysicalAssessmentUpdateView.as_view(), name="student-assessment-edit"),
    path("<int:pk>/assessments/<int:assessment_pk>/delete/", PhysicalAssessmentDeleteView.as_view(), name="student-assessment-delete"),
]
