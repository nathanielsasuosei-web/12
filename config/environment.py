"""Environment variables for the "12" beat store, read and checked in one place.

Each field reads the environment variable with the same name in upper case: `email_port` reads
EMAIL_PORT. A variable that is set but blank counts as unset and uses its default. The exception is
DJANGO_DEBUG, where blank means off, as it always has.

config/settings.py maps these values onto Django's settings. Invalid values never raise here,
because Vercel imports the settings while it builds the app. They are listed in
CONFIGURATION_ERRORS instead, and config/production.py reports them when the app starts and
when `manage.py check_production` runs.
"""

from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Development-only fallback. config/production.py refuses to serve with it when DEBUG is off.
DEV_SECRET_KEY = "dev-insecure-change-me-in-production"


def split_list(value):
    """Split a comma-separated setting, dropping blank items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _is_blank(value):
    return isinstance(value, str) and value.strip() == ""


class Environment(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def treat_blank_as_unset(cls, data):
        """A variable that is set but blank counts as unset, so it uses its default.

        DJANGO_DEBUG is the exception: a blank value turns debug off, as it always has, so an
        empty variable can never switch debug on by accident.
        """
        if not isinstance(data, dict):
            return data
        cleaned = {key: value for key, value in data.items() if not _is_blank(value)}
        if _is_blank(data.get("django_debug")):
            cleaned["django_debug"] = False
        return cleaned

    # Set by Vercel during builds and at run time.
    vercel: bool = False
    vercel_env: str = ""
    vercel_url: str = ""
    vercel_branch_url: str = ""
    vercel_project_production_url: str = ""

    site_name: str = "12"
    site_url: str = "http://localhost:8000"

    django_secret_key: str = DEV_SECRET_KEY
    # Unset means on everywhere except Vercel. settings.py works out that default.
    django_debug: bool | None = None
    django_allowed_hosts: str = "localhost,127.0.0.1,0.0.0.0,.e2b.app"
    django_csrf_trusted_origins: str = "https://*.e2b.app,http://localhost:8000"
    django_secure_ssl_redirect: bool = True
    django_hsts_seconds: int = 3600

    database_url: str = ""
    db_conn_max_age: int = 600
    sqlite_path: str = ""
    media_root: str = ""

    # The console backend is the default: emails are printed to the server log.
    email_backend: str = "django.core.mail.backends.console.EmailBackend"
    email_host: str = "localhost"
    email_port: int = 587
    email_host_user: str = ""
    email_host_password: str = ""
    email_use_tls: bool = True
    default_from_email: str = "12 Beats <noreply@example.com>"
    producer_email: str = ""
    email_attach_max_bytes: int = 15 * 1024 * 1024

    paystack_secret_key: str = ""
    # Unset means "paystack" when a Paystack key is set, and "mock" otherwise. settings.py works that out.
    payment_provider: str | None = None
    payment_currency: str = "GHS"
    payment_channels: str = "mobile_money,bank"

    @property
    def is_vercel_deploy(self) -> bool:
        return self.vercel and self.vercel_env.strip().lower() != "development"

    @property
    def vercel_hosts(self) -> list[str]:
        """The hosts Vercel assigns to preview and production builds, without the scheme."""
        hosts = []
        for value in (self.vercel_url, self.vercel_branch_url, self.vercel_project_production_url):
            host = value.strip()
            for scheme in ("https://", "http://"):
                if host.startswith(scheme):
                    host = host[len(scheme):]
            host = host.rstrip("/")
            if host and host not in hosts:
                hosts.append(host)
        return hosts


def load_environment():
    """Return (environment, errors). This never raises, so importing the settings cannot fail."""
    try:
        return Environment(), []
    except ValidationError as error:
        problems = error.errors()
        errors = [f"{item['loc'][0].upper()}: {item['msg']}" for item in problems]
        # Replace only the invalid values with their defaults. Everything else still comes from the environment.
        overrides = {
            item["loc"][0]: Environment.model_fields[item["loc"][0]].get_default(call_default_factory=True)
            for item in problems
        }
        return Environment(**overrides), errors
