from django.contrib.auth import views as auth_views
from django.urls import path

from .views import StudentDashboardView, TrainerDashboardView

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("treinador/", TrainerDashboardView.as_view(), name="trainer-dashboard"),
    path("aluno/", StudentDashboardView.as_view(), name="student-dashboard"),
]
