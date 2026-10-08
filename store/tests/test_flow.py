import hashlib
import hmac
import json
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import DatabaseError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from store import payments
from store.models import Beat, ContactMessage, Order, Video

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp(prefix="12-test-media-")


@override_settings(
    DEBUG=True,
    MEDIA_ROOT=TMP_MEDIA,
    PAYMENT_PROVIDER="mock",
    PAYSTACK_SECRET_KEY="",
    SITE_URL="http://testserver",
    PRODUCER_EMAIL="producer@example.com",
    PAYMENT_CURRENCY="GHS",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class BaseFlowTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.beat = Beat.objects.create(
            title="Night Drive",
            price=Decimal("50.00"),
            audio_file=SimpleUploadedFile("night.mp3", b"ID3fakeaudio", content_type="audio/mpeg"),
            bpm=140,
            musical_key="Am",
        )
        self.buyer = User.objects.create_user("artist", "artist@example.com", "pass12345!")


class CatalogueTests(BaseFlowTest):
    def test_home_and_lists_render(self):
        self.assertContains(self.client.get(reverse("home")), "Hear it.")
        self.assertContains(self.client.get(reverse("beat_list")), "Night Drive")
        self.assertContains(self.client.get(self.beat.get_absolute_url()), "Night Drive")
        self.assertEqual(self.client.get(reverse("video_list")).status_code, 200)

    def test_unpublished_beat_is_hidden(self):
        self.beat.is_published = False
        self.beat.save()
        self.assertEqual(self.client.get(self.beat.get_absolute_url()).status_code, 404)

    def test_video_embed_urls(self):
        v = Video(title="a", video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(v.embed_url, "https://www.youtube.com/embed/dQw4w9WgXcQ")
        v.video_url = "https://vimeo.com/123456"
        self.assertEqual(v.embed_url, "https://player.vimeo.com/video/123456")


class ContactTests(BaseFlowTest):
    def test_contact_page_renders(self):
        self.assertContains(self.client.get(reverse("contact")), "Talk to the producer")

    def test_contact_form_prefills_for_logged_in_artist(self):
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse("contact"))
        self.assertContains(resp, "artist@example.com")

    def test_contact_message_is_saved_and_emailed_to_producer_and_sender(self):
        resp = self.client.post(reverse("contact"), {
            "name": "Kwame",
            "email": "kwame@example.com",
            "subject": "Custom beat",
            "message": "I need a 140 BPM afrobeat instrumental.",
        })
        self.assertRedirects(resp, reverse("contact"))
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.name, "Kwame")
        self.assertFalse(msg.is_read)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["producer@example.com"])
        self.assertIn("kwame@example.com", mail.outbox[0].body)
        self.assertEqual(mail.outbox[1].to, ["kwame@example.com"])

    def test_contact_form_rejects_empty_message(self):
        resp = self.client.post(reverse("contact"), {
            "name": "Kwame",
            "email": "kwame@example.com",
            "subject": "Hi",
            "message": "",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)


class PreviewTests(BaseFlowTest):
    def test_detail_shows_preview_player_when_set(self):
        self.beat.preview_file = SimpleUploadedFile("night-preview.mp3", b"ID3preview", content_type="audio/mpeg")
        self.beat.save()
        self.assertContains(self.client.get(self.beat.get_absolute_url()), "<audio")

    def test_detail_hides_preview_player_when_missing(self):
        self.assertNotContains(self.client.get(self.beat.get_absolute_url()), "<audio")


class DeploymentReadinessTests(TestCase):
    def test_healthcheck_returns_ok_when_database_is_available(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_healthcheck_reports_database_outage(self):
        with mock.patch("store.views.connection.cursor", side_effect=DatabaseError("offline")):
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_mock_checkout_is_disabled_when_debug_is_off(self):
        with override_settings(DEBUG=False, PAYMENT_PROVIDER="mock"):
            response = self.client.get(reverse("mock_checkout", args=["not-a-real-reference"]))
        self.assertEqual(response.status_code, 404)


class SignupAndAccessTests(BaseFlowTest):
    def test_signup_creates_account_and_logs_in(self):
        resp = self.client.post(reverse("signup"), {
            "username": "newartist",
            "email": "NEW@example.com",
            "password1": "Sup3r-secret-pw",
            "password2": "Sup3r-secret-pw",
        })
        self.assertRedirects(resp, reverse("dashboard"))
        user = User.objects.get(username="newartist")
        self.assertEqual(user.email, "new@example.com")

    def test_duplicate_email_rejected(self):
        resp = self.client.post(reverse("signup"), {
            "username": "other",
            "email": "ARTIST@example.com",
            "password1": "Sup3r-secret-pw",
            "password2": "Sup3r-secret-pw",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already exists")

    def test_checkout_requires_login(self):
        resp = self.client.post(reverse("checkout", args=[self.beat.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])
        self.assertEqual(Order.objects.count(), 0)


class MockPaymentFlowTests(BaseFlowTest):
    def test_full_purchase_sends_receipt_with_beat_and_notifies_producer(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse("checkout", args=[self.beat.pk]))
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.amount, Decimal("50.00"))
        self.assertRedirects(resp, reverse("mock_checkout", args=[order.payment_reference]), fetch_redirect_response=False)

        resp = self.client.post(reverse("mock_checkout", args=[order.payment_reference]), {"channel": "mobile_money"})
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.channel, "mobile_money")
        self.assertIsNotNone(order.paid_at)

        self.assertEqual(len(mail.outbox), 2)
        buyer_mail = mail.outbox[0]
        self.assertEqual(buyer_mail.to, ["artist@example.com"])
        self.assertIn(order.get_download_url(), buyer_mail.body)
        self.assertTrue(buyer_mail.attachments[0][0].startswith("night") and buyer_mail.attachments[0][0].endswith(".mp3"))
        self.assertEqual(mail.outbox[1].to, ["producer@example.com"])

    def test_paid_order_is_fulfilled_only_once(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse("checkout", args=[self.beat.pk]))
        order = Order.objects.get()
        url = reverse("mock_checkout", args=[order.payment_reference])
        self.client.post(url, {"channel": "bank"})
        self.client.post(url, {"channel": "bank"})
        self.assertEqual(len(mail.outbox), 2)  # buyer + producer, not duplicated

    def test_download_blocked_until_paid_then_works(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price)
        self.assertEqual(self.client.get(order.get_download_url()).status_code, 404)
        self.client.post(reverse("mock_checkout", args=[order.payment_reference]), {"channel": "bank"})
        resp = self.client.get(order.get_download_url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attachment", resp["Content-Disposition"])
        order.refresh_from_db()
        self.assertEqual(order.download_count, 1)

    def test_dashboard_lists_purchases(self):
        self.client.force_login(self.buyer)
        Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price)
        self.assertContains(self.client.get(reverse("dashboard")), "Night Drive")

    def test_mock_checkout_rejects_unknown_channel(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price)
        resp = self.client.post(reverse("mock_checkout", args=[order.payment_reference]), {"channel": "crypto"})
        self.assertEqual(resp.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)


@override_settings(
    MEDIA_ROOT=TMP_MEDIA,
    PAYMENT_PROVIDER="paystack",
    PAYSTACK_SECRET_KEY="sk_test_123",
    SITE_URL="http://testserver",
    PAYMENT_CURRENCY="GHS",
    PAYMENT_CHANNELS=["mobile_money", "bank"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PaystackTests(BaseFlowTest):
    def _response(self, status, body):
        m = mock.Mock(status_code=status)
        m.json.return_value = body
        return m

    def test_checkout_initializes_paystack_and_redirects(self):
        self.client.force_login(self.buyer)
        init = self._response(200, {"status": True, "data": {"authorization_url": "https://checkout.paystack.com/abc"}})
        with mock.patch("store.payments.requests.post", return_value=init) as post:
            resp = self.client.post(reverse("checkout", args=[self.beat.pk]))
        self.assertEqual(resp["Location"], "https://checkout.paystack.com/abc")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["amount"], 5000)  # pesewas
        self.assertEqual(payload["currency"], "GHS")
        self.assertEqual(payload["channels"], ["mobile_money", "bank"])
        self.assertEqual(payload["callback_url"], "http://testserver/payments/return/")

    def test_failed_initialize_marks_order_failed(self):
        self.client.force_login(self.buyer)
        bad = self._response(400, {"status": False, "message": "Invalid key"})
        with mock.patch("store.payments.requests.post", return_value=bad):
            resp = self.client.post(reverse("checkout", args=[self.beat.pk]), follow=True)
        self.assertEqual(Order.objects.get().status, Order.Status.FAILED)
        self.assertContains(resp, "Invalid key")

    def test_return_verifies_with_provider_and_fulfils(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price, currency="GHS")
        verify = self._response(200, {"status": True, "data": {
            "status": "success", "amount": 5000, "currency": "GHS", "channel": "mobile_money"}})
        with mock.patch("store.payments.requests.get", return_value=verify):
            resp = self.client.get(reverse("payment_return"), {"reference": order.payment_reference})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.channel, "mobile_money")
        self.assertContains(resp, "Payment successful")
        self.assertEqual(len(mail.outbox), 2)

    def test_amount_mismatch_is_not_fulfilled(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price, currency="GHS")
        verify = self._response(200, {"status": True, "data": {
            "status": "success", "amount": 100, "currency": "GHS", "channel": "bank"}})
        with mock.patch("store.payments.requests.get", return_value=verify):
            self.client.get(reverse("payment_return"), {"reference": order.payment_reference})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def _sign(self, body):
        return hmac.new(b"sk_test_123", body, hashlib.sha512).hexdigest()

    def test_webhook_rejects_bad_signature(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price, currency="GHS")
        body = json.dumps({"event": "charge.success", "data": {"reference": order.payment_reference}}).encode()
        resp = self.client.post(reverse("payment_webhook"), body, content_type="application/json",
                                HTTP_X_PAYSTACK_SIGNATURE="forged")
        self.assertEqual(resp.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_webhook_with_valid_signature_fulfils(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price, currency="GHS")
        body = json.dumps({"event": "charge.success", "data": {"reference": order.payment_reference}}).encode()
        verify = self._response(200, {"status": True, "data": {
            "status": "success", "amount": 5000, "currency": "GHS", "channel": "bank"}})
        with mock.patch("store.payments.requests.get", return_value=verify):
            resp = self.client.post(reverse("payment_webhook"), body, content_type="application/json",
                                    HTTP_X_PAYSTACK_SIGNATURE=self._sign(body))
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_mock_checkout_disabled_in_paystack_mode(self):
        order = Order.objects.create(user=self.buyer, beat=self.beat, amount=self.beat.price, currency="GHS")
        resp = self.client.post(reverse("mock_checkout", args=[order.payment_reference]), {"channel": "bank"})
        self.assertEqual(resp.status_code, 404)

    def test_to_subunits(self):
        self.assertEqual(payments.to_subunits(Decimal("12.34")), 1234)
