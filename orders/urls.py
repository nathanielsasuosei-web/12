from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("account/", views.my_orders, name="my_orders"),
    path("start/<slug:slug>/", views.start_order, name="start"),
    path("<str:reference>/", views.order_detail, name="order_detail"),
    path("<str:reference>/pay/", views.pay_order, name="pay"),
    path("<str:reference>/mock-checkout/", views.mock_checkout, name="mock_checkout"),
    path("paystack/callback/", views.paystack_callback, name="paystack_callback"),
    path("paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    path("download/<str:token>/", views.download, name="download"),
]
