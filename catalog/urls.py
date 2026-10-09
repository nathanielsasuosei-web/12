from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("beats/", views.beat_list, name="beat_list"),
    path("beats/<slug:slug>/", views.beat_detail, name="beat_detail"),
    path("videos/", views.video_list, name="video_list"),
    path("videos/<slug:slug>/", views.video_detail, name="video_detail"),
]
