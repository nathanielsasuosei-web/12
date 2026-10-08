"""Checks that a production deployment has the configuration it needs.

config/wsgi.py runs check_production_config() before it creates the WSGI application, and
`manage.py check_production` runs the same checks as the Vercel build command (vercel.json).
They are deliberately not run when settings are imported: Vercel imports config/settings.py
while it builds, to find the WSGI app and run collectstatic, and that step does not need
the runtime secrets.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def production_config_errors():
    """Return one message for each setting that stops the current configuration from serving production."""
    errors = []
    if settings.IS_VERCEL_DEPLOY and settings.DEBUG:
        errors.append("Vercel deployments must set DJANGO_DEBUG=0.")
    if not settings.DEBUG:
        if settings.IS_VERCEL_DEPLOY and not settings.DATABASE_URL:
            errors.append("Vercel deployments require DATABASE_URL; SQLite storage is not persistent.")
        if len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY == settings.DEV_SECRET_KEY:
            errors.append("Set DJANGO_SECRET_KEY to a random value of at least 32 characters.")
        if not settings.PAYSTACK_SECRET_KEY or settings.PAYMENT_PROVIDER != "paystack":
            errors.append(
                "Production requires PAYSTACK_SECRET_KEY and PAYMENT_PROVIDER=paystack; "
                "mock checkout is local-only."
            )
    return errors


def check_production_config():
    """Raise ImproperlyConfigured that lists every production setting that is missing or unsafe."""
    errors = production_config_errors()
    if errors:
        raise ImproperlyConfigured("Production configuration is incomplete:\n- " + "\n- ".join(errors))
