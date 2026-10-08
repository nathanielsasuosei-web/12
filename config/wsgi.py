import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Refuse to serve an incomplete production configuration. This runs here rather than when the
# settings are imported, so that Vercel's build can still read them (see config/production.py).
from config.production import check_production_config  # noqa: E402

check_production_config()

application = get_wsgi_application()
