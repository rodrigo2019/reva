from django.contrib.auth import views as auth_views
from django.urls import path

from .views import StudentDashboardView, StudentSelfProfileView, TrainerDashboardView

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("coach/", TrainerDashboardView.as_view(), name="trainer-dashboard"),
    path("student/", StudentDashboardView.as_view(), name="student-dashboard"),
    path("student/profile/", StudentSelfProfileView.as_view(), name="student-self-profile"),
]
