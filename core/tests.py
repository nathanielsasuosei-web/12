from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.production import production_problems, validate_production_settings
from config.settings import DEV_SECRET_KEY

GOOD = dict(
    DEBUG=False,
    SECRET_KEY="x" * 60,
    ALLOWED_HOSTS=["beats.example.com"],
    SITE_URL="https://beats.example.com",
    PAYMENT_PROVIDER="paystack",
    PAYSTACK_SECRET_KEY="sk_live_123",
    PRODUCER_EMAIL="producer@example.com",
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
)


class ProductionSafetyTests(SimpleTestCase):
    def settings_with(self, **overrides):
        values = dict(GOOD)
        values.update(overrides)
        return type("S", (), values)

    def test_fully_configured_production_passes(self):
        self.assertEqual(production_problems(self.settings_with()), [])

    def test_debug_mode_skips_checks(self):
        self.assertEqual(production_problems(self.settings_with(DEBUG=True, SECRET_KEY=DEV_SECRET_KEY)), [])

    def test_dev_secret_key_is_refused(self):
        problems = production_problems(self.settings_with(SECRET_KEY=DEV_SECRET_KEY))
        self.assertTrue(any("SECRET_KEY" in p for p in problems))

    def test_mock_payments_and_missing_keys_are_refused(self):
        problems = production_problems(
            self.settings_with(PAYMENT_PROVIDER="mock", PAYSTACK_SECRET_KEY="", PRODUCER_EMAIL="")
        )
        text = " ".join(problems)
        self.assertIn("PAYMENT_PROVIDER", text)
        self.assertIn("PAYSTACK_SECRET_KEY", text)
        self.assertIn("PRODUCER_EMAIL", text)

    def test_http_site_url_and_console_email_are_refused(self):
        problems = production_problems(
            self.settings_with(
                SITE_URL="http://beats.example.com", EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
            )
        )
        self.assertTrue(any("https://" in p for p in problems))
        self.assertTrue(any("SMTP" in p for p in problems))

    def test_validate_raises_with_every_problem(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_production_settings(self.settings_with(SECRET_KEY="short", PAYMENT_PROVIDER="mock"))
        self.assertIn("SECRET_KEY", str(ctx.exception))
        self.assertIn("PAYMENT_PROVIDER", str(ctx.exception))
