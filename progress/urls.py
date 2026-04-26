from django.urls import path

from .views import StudentProgressView

urlpatterns = [
    path("mine/", StudentProgressView.as_view(), name="my-progress"),
]
