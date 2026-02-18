from django.urls import path

from .views import StudentProgressView

urlpatterns = [
    path("meu/", StudentProgressView.as_view(), name="my-progress"),
]
