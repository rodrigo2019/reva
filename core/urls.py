from django.urls import path

from .views import HomeRedirectView, LandingPageView

urlpatterns = [
    path("", LandingPageView.as_view(), name="landing"),
    path("home/", HomeRedirectView.as_view(), name="home"),
]
