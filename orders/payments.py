"""Payment providers. Paystack handles mobile money and bank payments in Ghana.

The mock provider is a test checkout for local development. It is refused
whenever DEBUG is off.
"""

import hashlib
import hmac
import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """A payment could not be started or checked. The message is safe to show the buyer."""


class MockProvider:
    name = "mock"

    def start_checkout(self, order, email, callback_url):
        return reverse("orders:mock_checkout", args=[order.reference])


class PaystackProvider:
    name = "paystack"
    api_base = "https://api.paystack.co"

    def __init__(self, secret_key, channels, timeout=20):
        self.secret_key = secret_key
        self.channels = list(channels)
        self.timeout = timeout

    def _headers(self):
        return {"Authorization": f"Bearer {self.secret_key}", "Accept": "application/json"}

    @staticmethod
    def _json(response):
        try:
            return response.json()
        except ValueError:
            return {}

    def start_checkout(self, order, email, callback_url):
        payload = {
            "email": email,
            "amount": order.amount_pesewas,
            "currency": "GHS",
            "reference": order.reference,
            "callback_url": callback_url,
            "metadata": {"order_id": order.pk, "beat": order.beat.title},
        }
        if self.channels:
            payload["channels"] = self.channels
        try:
            response = requests.post(
                f"{self.api_base}/transaction/initialize",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Paystack initialize failed: %s", exc)
            raise PaymentError("We could not reach the payment provider. Please try again in a moment.") from exc
        data = self._json(response)
        if response.status_code >= 400 or not data.get("status"):
            logger.warning("Paystack rejected initialize (%s): %s", response.status_code, data.get("message"))
            raise PaymentError("The payment provider could not start this payment. Please try again.")
        return data["data"]["authorization_url"]

    def verify(self, reference):
        """Ask Paystack for the transaction status. Returns Paystack's data object."""
        try:
            response = requests.get(
                f"{self.api_base}/transaction/verify/{reference}",
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Paystack verify failed: %s", exc)
            raise PaymentError("We could not confirm the payment yet. It will update automatically.") from exc
        data = self._json(response)
        if response.status_code >= 400 or not data.get("status"):
            raise PaymentError("The payment provider could not find this payment.")
        return data["data"]

    @staticmethod
    def signature_is_valid(raw_body, signature, secret_key):
        expected = hmac.new(secret_key.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature or "")


def get_provider():
    name = settings.PAYMENT_PROVIDER
    if name == "mock":
        if not settings.DEBUG:
            raise ImproperlyConfigured("The mock payment provider cannot run when DEBUG is off.")
        return MockProvider()
    if name == "paystack":
        if not settings.PAYSTACK_SECRET_KEY:
            raise ImproperlyConfigured("PAYSTACK_SECRET_KEY is not set.")
        return PaystackProvider(settings.PAYSTACK_SECRET_KEY, settings.PAYSTACK_CHANNELS)
    raise ImproperlyConfigured(f"Unknown PAYMENT_PROVIDER {name!r}.")
