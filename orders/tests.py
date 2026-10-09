import json
import tempfile
from decimal import Decimal
from unittest import mock

import requests
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Beat

from .models import Order
from .payments import PaystackProvider, get_provider
from .services import mark_paid

TMP = tempfile.mkdtemp(prefix="beatstore-orders-")
PAYSTACK_SETTINGS = dict(
    PAYMENT_PROVIDER="paystack",
    PAYSTACK_SECRET_KEY="sk_test_secret_for_tests",
    PAYSTACK_CHANNELS=["mobile_money", "bank"],
    SITE_URL="https://beats.example.com",
    PRODUCER_EMAIL="producer@example.com",
    MEDIA_ROOT=TMP + "/media",
    PRIVATE_MEDIA_ROOT=TMP + "/private",
    DEBUG=False,
)
SECRET = PAYSTACK_SETTINGS["PAYSTACK_SECRET_KEY"]


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def sign(body: bytes) -> str:
    import hashlib
    import hmac

    return hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()


@override_settings(MEDIA_ROOT=TMP + "/media", PRIVATE_MEDIA_ROOT=TMP + "/private")
class OrderTestBase(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.buyer = User.objects.create_user(
            username="artist@example.com", email="artist@example.com", password="StrongPass!234", first_name="Ama"
        )
        self.other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="StrongPass!234"
        )
        self.beat = Beat.objects.create(
            title="Gold Rush",
            price_ghs=Decimal("250.00"),
            preview_audio=SimpleUploadedFile("p.mp3", b"preview"),
            full_audio=SimpleUploadedFile("f.wav", b"FULL-WAV-CONTENT"),
            is_published=True,
        )

    def order_for(self, user=None, status=Order.Status.PENDING):
        return Order.objects.create(
            user=user or self.buyer, beat=self.beat, amount_ghs=self.beat.price_ghs, status=status
        )


@override_settings(**PAYSTACK_SETTINGS)
class PaystackCheckoutTests(OrderTestBase):
    def test_guest_cannot_start_checkout(self):
        response = self.client.post(reverse("orders:start", args=[self.beat.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(Order.objects.count(), 0)

    def test_start_creates_order_and_redirects_to_paystack(self):
        self.client.force_login(self.buyer)
        fake = FakeResponse(200, {"status": True, "data": {"authorization_url": "https://checkout.paystack.com/abc"}})
        with mock.patch("orders.payments.requests.post", return_value=fake) as post:
            response = self.client.post(reverse("orders:start", args=[self.beat.slug]))
        self.assertRedirects(response, "https://checkout.paystack.com/abc", fetch_redirect_response=False)
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.provider, "paystack")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["amount"], 25000)
        self.assertEqual(payload["currency"], "GHS")
        self.assertEqual(payload["reference"], order.reference)
        self.assertEqual(payload["channels"], ["mobile_money", "bank"])
        self.assertEqual(payload["callback_url"], "https://beats.example.com/orders/paystack/callback/")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer " + SECRET)

    def test_paystack_error_marks_order_failed_and_returns_to_beat(self):
        self.client.force_login(self.buyer)
        with mock.patch(
            "orders.payments.requests.post", return_value=FakeResponse(400, {"status": False, "message": "bad"})
        ):
            response = self.client.post(reverse("orders:start", args=[self.beat.slug]), follow=True)
        self.assertEqual(Order.objects.get().status, Order.Status.FAILED)
        self.assertRedirects(response, self.beat.get_absolute_url())
        self.assertContains(response, "could not start this payment")

    def test_network_error_is_reported_without_crashing(self):
        self.client.force_login(self.buyer)
        with mock.patch("orders.payments.requests.post", side_effect=requests.ConnectionError("down")):
            response = self.client.post(reverse("orders:start", args=[self.beat.slug]), follow=True)
        self.assertContains(response, "could not reach the payment provider")

    def test_already_owned_beat_is_not_sold_twice(self):
        self.order_for(status=Order.Status.PAID)
        self.client.force_login(self.buyer)
        with mock.patch("orders.payments.requests.post") as post:
            self.client.post(reverse("orders:start", args=[self.beat.slug]))
        post.assert_not_called()
        self.assertEqual(Order.objects.count(), 1)

    def _webhook(self, payload, signature=None):
        body = json.dumps(payload).encode()
        return self.client.post(
            reverse("orders:paystack_webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature if signature is not None else sign(body),
        )

    def test_webhook_with_bad_signature_is_rejected(self):
        order = self.order_for()
        payload = {
            "event": "charge.success",
            "data": {"reference": order.reference, "amount": 25000, "currency": "GHS"},
        }
        response = self._webhook(payload, signature="forged")
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    def test_signed_charge_success_pays_order_and_emails_buyer_and_producer(self):
        order = self.order_for()
        payload = {
            "event": "charge.success",
            "data": {
                "id": 99,
                "reference": order.reference,
                "amount": 25000,
                "currency": "GHS",
                "channel": "mobile_money",
            },
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = self._webhook(payload)
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.channel, "mobile_money")
        self.assertTrue(order.download_token)
        recipients = sorted(address for message in mail.outbox for address in message.to)
        self.assertEqual(recipients, ["artist@example.com", "producer@example.com"])
        buyer_mail = next(m for m in mail.outbox if m.to == ["artist@example.com"])
        self.assertIn(f"/orders/download/{order.download_token}/", buyer_mail.body)

    def test_amount_mismatch_is_not_marked_paid(self):
        order = self.order_for()
        payload = {"event": "charge.success", "data": {"reference": order.reference, "amount": 100, "currency": "GHS"}}
        response = self._webhook(payload)
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertFalse(order.is_paid)
        self.assertEqual(mail.outbox, [])

    def test_repeated_webhooks_send_emails_once(self):
        order = self.order_for()
        payload = {
            "event": "charge.success",
            "data": {"reference": order.reference, "amount": 25000, "currency": "GHS"},
        }
        with self.captureOnCommitCallbacks(execute=True):
            self._webhook(payload)
            self._webhook(payload)
        self.assertEqual(len(mail.outbox), 2)

    def test_callback_confirms_with_paystack_before_marking_paid(self):
        order = self.order_for()
        order.provider = "paystack"  # set when checkout starts
        order.save(update_fields=["provider"])
        verified = {"status": "success", "amount": 25000, "currency": "GHS", "channel": "bank", "id": 7}
        self.client.force_login(self.buyer)
        with mock.patch(
            "orders.payments.requests.get", return_value=FakeResponse(200, {"status": True, "data": verified})
        ) as get:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.get(reverse("orders:paystack_callback"), {"reference": order.reference})
        self.assertRedirects(response, order.get_absolute_url())
        self.assertIn(f"/transaction/verify/{order.reference}", get.call_args.args[0])
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.channel, "bank")

    def test_callback_does_not_pay_when_paystack_says_failed(self):
        order = self.order_for()
        order.provider = "paystack"
        order.save(update_fields=["provider"])
        failed = {"status": "failed", "amount": 25000, "currency": "GHS"}
        with mock.patch(
            "orders.payments.requests.get", return_value=FakeResponse(200, {"status": True, "data": failed})
        ):
            self.client.get(reverse("orders:paystack_callback"), {"reference": order.reference})
        order.refresh_from_db()
        self.assertFalse(order.is_paid)

    def test_callback_for_guest_shows_receipt_page(self):
        order = self.order_for()
        with mock.patch(
            "orders.payments.requests.get",
            return_value=FakeResponse(200, {"status": True, "data": {"status": "pending"}}),
        ):
            response = self.client.get(reverse("orders:paystack_callback"), {"reference": order.reference})
        self.assertTemplateUsed(response, "orders/payment_received.html")

    def test_other_users_cannot_see_an_order(self):
        order = self.order_for()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)


@override_settings(**PAYSTACK_SETTINGS)
class DownloadTests(OrderTestBase):
    def setUp(self):
        super().setUp()
        import os

        os.makedirs(TMP + "/private/full", exist_ok=True)
        self.beat.full_audio.save("gold-rush.wav", SimpleUploadedFile("gold-rush.wav", b"FULL-WAV-CONTENT"), save=True)

    def test_unpaid_order_has_no_download(self):
        order = self.order_for()
        self.assertEqual(self.client.get(reverse("orders:download", args=["not-a-real-token"])).status_code, 404)
        self.assertFalse(order.download_token)

    @override_settings(MAX_DOWNLOADS_PER_ORDER=2)
    def test_paid_download_streams_file_and_enforces_limit(self):
        order = self.order_for()
        mark_paid(order, channel="mobile_money", transaction_id="1", amount_pesewas=25000)
        order.refresh_from_db()
        url = reverse("orders:download", args=[order.download_token])

        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(b"".join(first.streaming_content), b"FULL-WAV-CONTENT")
        self.assertIn("attachment", first["Content-Disposition"])
        self.assertEqual(self.client.get(url).status_code, 200)
        third = self.client.get(url)
        self.assertEqual(third.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.download_count, 2)

    def test_mark_paid_is_idempotent(self):
        order = self.order_for()
        self.assertTrue(mark_paid(order, amount_pesewas=25000))
        self.assertFalse(mark_paid(order, amount_pesewas=25000))


class MockCheckoutTests(OrderTestBase):
    @override_settings(
        DEBUG=True, PAYMENT_PROVIDER="mock", MEDIA_ROOT=TMP + "/media", PRIVATE_MEDIA_ROOT=TMP + "/private"
    )
    def test_mock_checkout_pays_order_in_development(self):
        self.client.force_login(self.buyer)
        response = self.client.post(reverse("orders:start", args=[self.beat.slug]))
        order = Order.objects.get()
        self.assertRedirects(
            response, reverse("orders:mock_checkout", args=[order.reference]), fetch_redirect_response=False
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("orders:mock_checkout", args=[order.reference]))
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.channel, "mock")

    @override_settings(DEBUG=False, PAYMENT_PROVIDER="paystack", PAYSTACK_SECRET_KEY=SECRET)
    def test_mock_checkout_is_hidden_when_debug_is_off(self):
        order = self.order_for()
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse("orders:mock_checkout", args=[order.reference])).status_code, 404)

    def test_mock_provider_refused_outside_debug(self):
        with override_settings(DEBUG=False, PAYMENT_PROVIDER="mock"):
            with self.assertRaises(ImproperlyConfigured):
                get_provider()


class SignatureTests(TestCase):
    def test_signature_helper(self):
        body = b'{"event":"charge.success"}'
        good = sign(body)
        self.assertTrue(PaystackProvider.signature_is_valid(body, good, SECRET))
        self.assertFalse(PaystackProvider.signature_is_valid(body + b" ", good, SECRET))
        self.assertFalse(PaystackProvider.signature_is_valid(body, "", SECRET))
