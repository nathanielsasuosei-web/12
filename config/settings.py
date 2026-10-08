"""Settings for the "12" beat store. Most values can be overridden with environment variables."""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def vercel_hosts():
    """Include the deployment URLs Vercel assigns to preview and production builds."""
    hosts = []
    for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        host = env(name, "").strip()
        if host.startswith("https://"):
            host = host[len("https://"):]
        elif host.startswith("http://"):
            host = host[len("http://"):]
        host = host.rstrip("/")
        if host and host not in hosts:
            hosts.append(host)
    return hosts


VERCEL_HOSTS = vercel_hosts()
VERCEL_ENVIRONMENT = env("VERCEL_ENV", "").strip().lower()
IS_VERCEL_DEPLOY = env_bool("VERCEL", False) and VERCEL_ENVIRONMENT != "development"

SITE_NAME = env("SITE_NAME", "12")
SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me-in-production")  # must be set in production
DEBUG = env_bool("DJANGO_DEBUG", not IS_VERCEL_DEPLOY)
ALLOWED_HOSTS = list(dict.fromkeys(
    env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,.e2b.app") + VERCEL_HOSTS
))
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.e2b.app,http://localhost:8000")
    + [f"https://{host}" for host in VERCEL_HOSTS]
))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "store",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "store.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = env("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(env("DB_CONN_MAX_AGE", "600")),
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

# Email: console backend by default (emails print to the server log).
# Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend plus the EMAIL_* values for real delivery.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "12 Beats <noreply@example.com>")
# Address that receives a "new sale" notification for every paid order.
PRODUCER_EMAIL = env("PRODUCER_EMAIL", "")
# Beats up to this size are attached to the purchase email; larger ones are sent as a download link only.
EMAIL_ATTACH_MAX_BYTES = int(env("EMAIL_ATTACH_MAX_BYTES", str(15 * 1024 * 1024)))

# Payments. "paystack" supports mobile money and bank channels in supported African countries.
# "mock" simulates checkout locally (used automatically when no Paystack key is configured).
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", "")
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", "paystack" if PAYSTACK_SECRET_KEY else "mock")
PAYMENT_CURRENCY = env("PAYMENT_CURRENCY", "GHS")
PAYMENT_CHANNELS = env_list("PAYMENT_CHANNELS", "mobile_money,bank")

# Production hardening (only when DEBUG is off, so local development stays plain HTTP).
if IS_VERCEL_DEPLOY and DEBUG:
    raise ImproperlyConfigured("Vercel deployments must set DJANGO_DEBUG=0.")

if not DEBUG:
    if IS_VERCEL_DEPLOY and not DATABASE_URL:
        raise ImproperlyConfigured("Vercel deployments require DATABASE_URL; SQLite storage is not persistent.")
    if len(SECRET_KEY) < 32 or SECRET_KEY == "dev-insecure-change-me-in-production":
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a random value of at least 32 characters.")
    if not PAYSTACK_SECRET_KEY or PAYMENT_PROVIDER != "paystack":
        raise ImproperlyConfigured(
            "Production requires PAYSTACK_SECRET_KEY and PAYMENT_PROVIDER=paystack; mock checkout is local-only."
        )

    # Serve fingerprinted static assets from Django without a separate web server.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
