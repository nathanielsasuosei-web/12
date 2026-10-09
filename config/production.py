"""Startup checks that stop the site running in production with unsafe settings."""

from django.core.exceptions import ImproperlyConfigured

from config.settings import DEV_SECRET_KEY


def production_problems(settings):
    """Return a list of human-readable problems. Empty when production is safe."""
    if settings.DEBUG:
        return []

    problems = []
    if settings.SECRET_KEY == DEV_SECRET_KEY or len(settings.SECRET_KEY) < 50:
        problems.append("DJANGO_SECRET_KEY must be set to a random value of at least 50 characters.")
    if not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
        problems.append("DJANGO_ALLOWED_HOSTS must list your domain, for example beats.example.com.")
    if not settings.SITE_URL.startswith("https://"):
        problems.append("SITE_URL must start with https:// so download and payment links work.")
    if settings.PAYMENT_PROVIDER != "paystack":
        problems.append("PAYMENT_PROVIDER must be 'paystack' in production. The mock checkout is development only.")
    if not settings.PAYSTACK_SECRET_KEY:
        problems.append("PAYSTACK_SECRET_KEY is required in production.")
    if not settings.PRODUCER_EMAIL:
        problems.append("PRODUCER_EMAIL is required so sales and messages reach the producer.")
    if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
        problems.append("Email must use SMTP in production. Set EMAIL_BACKEND and the EMAIL_HOST settings.")
    return problems


def validate_production_settings(settings):
    problems = production_problems(settings)
    if problems:
        raise ImproperlyConfigured("Unsafe production configuration:\n- " + "\n- ".join(problems))
