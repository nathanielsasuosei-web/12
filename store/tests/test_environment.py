import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from config.environment import load_environment
from config.production import production_config_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
STRONG_SECRET = "a" * 48
PRODUCTION_ENV = {
    "DATABASE_URL": "postgres://beats:secret@db:5432/beats",
    "DJANGO_SECRET_KEY": STRONG_SECRET,
    "PAYSTACK_SECRET_KEY": "sk_live_example",
}


def load(**variables):
    """Load the environment from exactly these variables, ignoring the machine running the tests."""
    with mock.patch.dict(os.environ, variables, clear=True):
        return load_environment()


class EnvironmentTests(SimpleTestCase):
    def test_unset_variables_use_defaults(self):
        environment, errors = load()
        self.assertEqual(errors, [])
        self.assertEqual(environment.email_port, 587)
        self.assertIsNone(environment.django_debug)
        self.assertEqual(environment.payment_channels, "mobile_money,bank")

    def test_blank_variables_count_as_unset(self):
        environment, errors = load(EMAIL_PORT="", PAYMENT_PROVIDER="  ", DATABASE_URL="")
        self.assertEqual(errors, [])
        self.assertEqual(environment.email_port, 587)
        self.assertIsNone(environment.payment_provider)

    def test_blank_debug_turns_debug_off(self):
        # Like before, an empty DJANGO_DEBUG must not switch debug on outside Vercel.
        for blank in ("", "   "):
            environment, errors = load(DJANGO_DEBUG=blank)
            self.assertEqual(errors, [])
            self.assertIs(environment.django_debug, False)

    def test_invalid_number_is_named_and_other_values_still_load(self):
        environment, errors = load(EMAIL_PORT="abc", DATABASE_URL="postgres://beats@db/beats")
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("EMAIL_PORT:"), errors)
        self.assertEqual(environment.email_port, 587)
        self.assertEqual(environment.database_url, "postgres://beats@db/beats")

    def test_invalid_boolean_is_named(self):
        _, errors = load(DJANGO_DEBUG="maybe")
        self.assertTrue(errors[0].startswith("DJANGO_DEBUG:"), errors)

    def test_error_messages_do_not_repeat_the_value(self):
        _, errors = load(EMAIL_PORT="not-a-port-secret-123")
        self.assertNotIn("secret-123", " ".join(errors))

    def test_vercel_hosts_drop_the_scheme_and_slash(self):
        environment, _ = load(
            VERCEL_URL="https://beats-abc.vercel.app/",
            VERCEL_BRANCH_URL="beats-git-main.vercel.app",
        )
        self.assertEqual(environment.vercel_hosts, ["beats-abc.vercel.app", "beats-git-main.vercel.app"])

    def test_configuration_errors_block_production(self):
        error = "EMAIL_PORT: Input should be a valid integer, unable to parse string as an integer"
        with override_settings(
            DEBUG=False,
            IS_VERCEL_DEPLOY=False,
            DATABASE_URL="postgres://beats@db/beats",
            SECRET_KEY=STRONG_SECRET,
            PAYMENT_PROVIDER="paystack",
            PAYSTACK_SECRET_KEY="sk_live_example",
            CONFIGURATION_ERRORS=[error],
        ):
            self.assertEqual(production_config_errors(), [error])


class VercelBuildWithEnvironmentTests(SimpleTestCase):
    """Run the Vercel build steps in a subprocess, with a minimal environment that mirrors Vercel."""

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

    def test_blank_numeric_variables_do_not_break_the_settings_import(self):
        result = self.run_python("-c", "import config.settings", EMAIL_PORT="", DB_CONN_MAX_AGE="", **PRODUCTION_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_check_passes_with_blank_optional_variables(self):
        result = self.run_python("manage.py", "check_production", EMAIL_PORT="", **PRODUCTION_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_check_names_an_invalid_variable_without_a_traceback(self):
        result = self.run_python("manage.py", "check_production", EMAIL_PORT="abc", **PRODUCTION_ENV)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EMAIL_PORT", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
