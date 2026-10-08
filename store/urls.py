from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("beats/", views.beat_list, name="beat_list"),
    path("beats/<int:pk>/", views.beat_detail, name="beat_detail"),
    path("beats/<int:pk>/buy/", views.checkout, name="checkout"),
    path("videos/", views.video_list, name="video_list"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("payments/return/", views.payment_return, name="payment_return"),
    path("payments/webhook/", views.payment_webhook, name="payment_webhook"),
    path("payments/mock/<str:reference>/", views.mock_checkout, name="mock_checkout"),
    path("download/<uuid:token>/", views.download, name="download"),
]
