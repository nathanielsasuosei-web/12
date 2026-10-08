import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from config.production import check_production_config, production_config_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
STRONG_SECRET = "a" * 48

PRODUCTION = {
    "DEBUG": False,
    "IS_VERCEL_DEPLOY": False,
    "DATABASE_URL": "postgres://beats:secret@db:5432/beats",
    "SECRET_KEY": STRONG_SECRET,
    "PAYMENT_PROVIDER": "paystack",
    "PAYSTACK_SECRET_KEY": "sk_live_example",
}
PRODUCTION_ENV = {
    "DATABASE_URL": PRODUCTION["DATABASE_URL"],
    "DJANGO_SECRET_KEY": STRONG_SECRET,
    "PAYSTACK_SECRET_KEY": PRODUCTION["PAYSTACK_SECRET_KEY"],
}


class ProductionConfigTests(SimpleTestCase):
    def test_development_needs_no_production_settings(self):
        with override_settings(
            DEBUG=True, IS_VERCEL_DEPLOY=False, PAYMENT_PROVIDER="mock", PAYSTACK_SECRET_KEY=""
        ):
            self.assertEqual(production_config_errors(), [])

    def test_complete_production_configuration_passes(self):
        with override_settings(**PRODUCTION):
            self.assertEqual(production_config_errors(), [])
            check_production_config()

    def test_vercel_production_requires_database_url(self):
        with override_settings(**{**PRODUCTION, "IS_VERCEL_DEPLOY": True, "DATABASE_URL": ""}):
            self.assertEqual(
                production_config_errors(),
                ["Vercel deployments require DATABASE_URL; SQLite storage is not persistent."],
            )

    def test_vercel_rejects_debug(self):
        with override_settings(**{**PRODUCTION, "IS_VERCEL_DEPLOY": True, "DEBUG": True}):
            self.assertEqual(production_config_errors(), ["Vercel deployments must set DJANGO_DEBUG=0."])

    def test_every_missing_setting_is_reported_together(self):
        overrides = {
            **PRODUCTION,
            "IS_VERCEL_DEPLOY": True,
            "DATABASE_URL": "",
            "SECRET_KEY": settings.DEV_SECRET_KEY,
            "PAYSTACK_SECRET_KEY": "",
        }
        with override_settings(**overrides):
            with self.assertRaises(ImproperlyConfigured) as raised:
                check_production_config()
        message = str(raised.exception)
        self.assertIn("DATABASE_URL", message)
        self.assertIn("DJANGO_SECRET_KEY", message)
        self.assertIn("PAYSTACK_SECRET_KEY", message)

    def test_check_production_command_passes_when_complete(self):
        out = StringIO()
        with override_settings(**PRODUCTION):
            call_command("check_production", stdout=out)
        self.assertIn("passed", out.getvalue())

    def test_check_production_command_fails_when_incomplete(self):
        with override_settings(**{**PRODUCTION, "PAYSTACK_SECRET_KEY": ""}):
            with self.assertRaisesMessage(CommandError, "PAYSTACK_SECRET_KEY"):
                call_command("check_production")


class VercelBuildTests(SimpleTestCase):
    """Vercel imports the settings during its build, but the app must still refuse to serve without
    production configuration.

    Each check runs in a subprocess with a minimal environment that mirrors a Vercel build
    (VERCEL=1), so the results do not depend on the variables of the machine running the tests.
    """

    def run_python(self, *args, **extra_env):
        env = {"PATH": os.environ.get("PATH", ""), "VERCEL": "1", "VERCEL_ENV": "production", **extra_env}
        return subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_settings_import_does_not_need_production_secrets(self):
        result = self.run_python("-c", "import config.settings")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wsgi_app_refuses_to_start_without_production_secrets(self):
        result = self.run_python("-c", "import config.wsgi")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL", result.stderr)

    def test_wsgi_app_starts_with_production_secrets(self):
        result = self.run_python("-c", "import config.wsgi", **PRODUCTION_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_command_fails_without_production_secrets(self):
        result = self.run_python("manage.py", "check_production")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL", result.stderr)

    def test_build_command_passes_with_production_secrets(self):
        result = self.run_python("manage.py", "check_production", **PRODUCTION_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
