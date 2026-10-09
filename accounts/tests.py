from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(SITE_URL="https://beats.example.com")
class AccountTests(TestCase):
    def test_signup_creates_account_logs_in_and_sends_welcome(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Kofi",
                "email": "Kofi@Example.com",
                "password1": "Blue-River-2026!",
                "password2": "Blue-River-2026!",
            },
        )
        self.assertRedirects(response, reverse("orders:my_orders"), fetch_redirect_response=False)
        user = User.objects.get()
        self.assertEqual(user.email, "kofi@example.com")
        self.assertEqual(user.username, "kofi@example.com")
        self.assertEqual(mail.outbox[0].to, ["kofi@example.com"])
        self.assertIn("Welcome", mail.outbox[0].subject)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(username="a@example.com", email="a@example.com", password="x-Long-pass-123")
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "A",
                "email": "A@example.com",
                "password1": "Blue-River-2026!",
                "password2": "Blue-River-2026!",
            },
        )
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_mismatched_passwords_rejected(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {"first_name": "B", "email": "b@example.com", "password1": "Blue-River-2026!", "password2": "other"},
        )
        self.assertContains(response, "do not match")
        self.assertFalse(User.objects.exists())

    def test_sign_in_with_email(self):
        User.objects.create_user(username="c@example.com", email="c@example.com", password="Blue-River-2026!")
        response = self.client.post(
            reverse("accounts:login"), {"username": "c@example.com", "password": "Blue-River-2026!"}
        )
        self.assertRedirects(response, reverse("orders:my_orders"), fetch_redirect_response=False)
