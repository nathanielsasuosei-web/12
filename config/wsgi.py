"""WSGI entry point. Refuses to start in production with unsafe configuration."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.conf import settings  # noqa: E402

from config.production import validate_production_settings  # noqa: E402

validate_production_settings(settings)

application = get_wsgi_application()
