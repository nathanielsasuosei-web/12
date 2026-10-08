from django.conf import settings


def site(request):
    return {"SITE_NAME": settings.SITE_NAME, "CURRENCY": settings.PAYMENT_CURRENCY}
