from django.conf import settings


def site(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "MAX_DOWNLOADS_PER_ORDER": settings.MAX_DOWNLOADS_PER_ORDER,
    }
