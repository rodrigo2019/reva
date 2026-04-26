from django.urls import path

from . import views

urlpatterns = [
    path("", views.ScheduleView.as_view(), name="schedule"),
    path("mine/", views.StudentScheduleView.as_view(), name="student-schedule"),
    path("new/", views.ClassCreateView.as_view(), name="class-create"),
    path("<int:pk>/edit/", views.ClassUpdateView.as_view(), name="class-update"),
    path("<int:pk>/delete/", views.ClassDeleteView.as_view(), name="class-delete"),
]
