from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ContactMessage


@override_settings(PRODUCER_EMAIL="producer@example.com")
class ContactTests(TestCase):
    def valid_data(self, **extra):
        data = {
            "name": "Efua",
            "email": "efua@example.com",
            "topic": "custom",
            "message": "Can you make a drill beat at 140 BPM?",
            "website": "",
        }
        data.update(extra)
        return data

    def test_message_is_saved_and_emailed_to_producer_with_reply_to(self):
        response = self.client.post(reverse("contact:contact"), self.valid_data())
        self.assertRedirects(response, reverse("contact:thanks"))
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        producer_mail = next(m for m in mail.outbox if m.to == ["producer@example.com"])
        self.assertEqual(producer_mail.reply_to, ["efua@example.com"])
        self.assertIn("Can you make a drill beat", producer_mail.body)
        confirmation = next(m for m in mail.outbox if m.to == ["efua@example.com"])
        self.assertIn("received your message", confirmation.body)

    def test_honeypot_blocks_bots(self):
        response = self.client.post(reverse("contact:contact"), self.valid_data(website="http://spam.example"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_empty_message_is_rejected(self):
        response = self.client.post(reverse("contact:contact"), self.valid_data(message=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())
