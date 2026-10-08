"""Payment gateway integration (Paystack: mobile money + bank channels)."""
import hashlib
import hmac
import logging
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"
REQUEST_TIMEOUT = 20


class PaymentError(Exception):
    pass


@dataclass
class VerifyResult:
    status: str
    amount: int  # in the lowest currency unit (pesewas / kobo / cents)
    currency: str
    channel: str


def to_subunits(amount):
    return int((Decimal(amount) * 100).to_integral_value())


def _headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _json(response):
    try:
        return response.json()
    except ValueError:
        return {}


def initialize_payment(order, email, callback_url):
    """Create a payment session for the order and return the URL to send the buyer to."""
    if settings.PAYMENT_PROVIDER == "mock":
        return reverse("mock_checkout", args=[order.payment_reference])

    if settings.PAYMENT_PROVIDER != "paystack":
        raise PaymentError(f"Unknown PAYMENT_PROVIDER: {settings.PAYMENT_PROVIDER}")
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaymentError("PAYSTACK_SECRET_KEY is not configured.")

    payload = {
        "email": email,
        "amount": to_subunits(order.amount),
        "currency": order.currency,
        "reference": order.payment_reference,
        "callback_url": callback_url,
        "channels": settings.PAYMENT_CHANNELS,
        "metadata": {"order_id": order.pk, "beat": order.beat.title},
    }
    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            json=payload,
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PaymentError("Could not reach the payment provider. Please try again.") from exc

    body = _json(response)
    if response.status_code != 200 or not body.get("status"):
        logger.error("Paystack initialize failed: %s %s", response.status_code, body)
        raise PaymentError(body.get("message") or "Payment could not be started.")
    return body["data"]["authorization_url"]


def verify_with_provider(reference):
    """Ask Paystack for the authoritative status of a transaction."""
    try:
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PaymentError("Could not verify the payment right now.") from exc

    body = _json(response)
    if response.status_code != 200 or not body.get("status"):
        raise PaymentError(body.get("message") or "Payment verification failed.")
    data = body["data"]
    return VerifyResult(
        status=data.get("status", ""),
        amount=int(data.get("amount", 0)),
        currency=data.get("currency", ""),
        channel=data.get("channel", "") or "",
    )


def verify_webhook_signature(body, signature):
    """Paystack signs webhook payloads with HMAC-SHA512 using the secret key."""
    if not settings.PAYSTACK_SECRET_KEY or not signature:
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
