from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("suggest/", views.suggest, name="suggest"),
    path("plan/", views.plan, name="plan"),
    path("corridor/", views.corridor_weather, name="corridor"),
]
