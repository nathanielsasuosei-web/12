"""Django settings for the "12" beat store.

Django needs a settings module at this path (manage.py and config/wsgi.py name it). The values come
from config/environment.py, which reads and checks the environment variables.
"""

import warnings
from pathlib import Path

import dj_database_url

# DEV_SECRET_KEY is exported for config/production.py, which refuses to serve with it.
from config.environment import DEV_SECRET_KEY, load_environment, split_list  # noqa: F401

BASE_DIR = Path(__file__).resolve().parent.parent

env, CONFIGURATION_ERRORS = load_environment()

IS_VERCEL_DEPLOY = env.is_vercel_deploy
VERCEL_HOSTS = env.vercel_hosts
VERCEL_ENVIRONMENT = env.vercel_env.strip().lower()

SITE_NAME = env.site_name
SITE_URL = env.site_url.rstrip("/")

SECRET_KEY = env.django_secret_key
DEBUG = env.django_debug if env.django_debug is not None else not IS_VERCEL_DEPLOY
ALLOWED_HOSTS = list(dict.fromkeys(split_list(env.django_allowed_hosts) + VERCEL_HOSTS))
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    split_list(env.django_csrf_trusted_origins) + [f"https://{host}" for host in VERCEL_HOSTS]
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

DATABASE_URL = env.database_url.strip()
sqlite_database = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": env.sqlite_path or str(BASE_DIR / "db.sqlite3"),
}
DATABASES = {"default": sqlite_database}
if DATABASE_URL:
    try:
        DATABASES = {
            "default": dj_database_url.parse(
                DATABASE_URL,
                conn_max_age=env.db_conn_max_age,
                conn_health_checks=True,
            )
        }
    except Exception as error:  # for example an unsupported scheme; config/production.py reports it
        CONFIGURATION_ERRORS.append(f"DATABASE_URL: {error}")

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
MEDIA_ROOT = Path(env.media_root or str(BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

# Email: console backend by default (emails print to the server log).
# Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend plus the EMAIL_* values for real delivery.
EMAIL_BACKEND = env.email_backend
EMAIL_HOST = env.email_host
EMAIL_PORT = env.email_port
EMAIL_HOST_USER = env.email_host_user
EMAIL_HOST_PASSWORD = env.email_host_password
EMAIL_USE_TLS = env.email_use_tls
DEFAULT_FROM_EMAIL = env.default_from_email
# Address that receives a "new sale" notification for every paid order.
PRODUCER_EMAIL = env.producer_email
# Beats up to this size are attached to the purchase email; larger ones are sent as a download link only.
EMAIL_ATTACH_MAX_BYTES = env.email_attach_max_bytes

# Payments. "paystack" supports mobile money and bank channels in supported African countries.
# "mock" simulates checkout locally (used automatically when no Paystack key is configured).
PAYSTACK_SECRET_KEY = env.paystack_secret_key
PAYMENT_PROVIDER = env.payment_provider or ("paystack" if PAYSTACK_SECRET_KEY else "mock")
PAYMENT_CURRENCY = env.payment_currency
PAYMENT_CHANNELS = split_list(env.payment_channels)

if CONFIGURATION_ERRORS:
    warnings.warn(
        "Invalid environment variables are ignored, and their defaults are used instead:\n- "
        + "\n- ".join(CONFIGURATION_ERRORS),
        stacklevel=1,
    )

# Production hardening (only when DEBUG is off, so local development stays plain HTTP).
# Missing production secrets are not raised here: config/production.py reports them when the app
# starts, because Vercel imports this module during its build (see config/production.py).
if not DEBUG:
    # Serve fingerprinted static assets from Django without a separate web server.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.django_secure_ssl_redirect
    SECURE_HSTS_SECONDS = env.django_hsts_seconds
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
