import logging
import secrets

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .emails import send_purchase_emails
from .models import Order
from .payments import PaymentError, get_provider

logger = logging.getLogger(__name__)


def create_pending_order(user, beat):
    return Order.objects.create(user=user, beat=beat, amount_ghs=beat.price_ghs)


def begin_checkout(order):
    """Start a payment with the active provider and return the URL to send the buyer to."""
    provider = get_provider()
    callback = settings.SITE_URL + reverse("orders:paystack_callback")
    url = provider.start_checkout(order, email=order.user.email, callback_url=callback)
    changed = []
    if order.provider != provider.name:
        order.provider = provider.name
        changed.append("provider")
    if order.status == Order.Status.FAILED:
        # A retry puts the order back to awaiting payment.
        order.status = Order.Status.PENDING
        changed.append("status")
    if changed:
        order.save(update_fields=changed)
    return url


def mark_paid(order, *, channel="", transaction_id="", amount_pesewas=None, currency="GHS"):
    """Mark an order as paid exactly once and create its download token.

    Returns True when this call paid the order, False when it was already paid.
    Raises PaymentError when the paid amount or currency does not match the order.
    """
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status == Order.Status.PAID:
            return False
        if amount_pesewas is not None and int(amount_pesewas) != locked.amount_pesewas:
            logger.error(
                "Amount mismatch on order %s: paid %s, expected %s",
                locked.reference,
                amount_pesewas,
                locked.amount_pesewas,
            )
            raise PaymentError("The amount paid does not match this order.")
        if currency and currency.upper() != "GHS":
            raise PaymentError("The payment currency does not match this order.")
        locked.status = Order.Status.PAID
        locked.paid_at = timezone.now()
        locked.channel = channel or locked.channel
        locked.provider_transaction_id = str(transaction_id or "")[:64]
        locked.download_token = secrets.token_urlsafe(32)
        locked.save()
        transaction.on_commit(lambda: send_purchase_emails(locked.pk))
    order.refresh_from_db()
    return True


def confirm_with_provider(order):
    """Check a pending order with Paystack. Returns True when it is now paid."""
    if order.is_paid:
        return True
    provider = get_provider()
    if provider.name != "paystack":
        return False
    data = provider.verify(order.reference)
    if data.get("status") != "success":
        return False
    mark_paid(
        order,
        channel=data.get("channel", ""),
        transaction_id=data.get("id", ""),
        amount_pesewas=data.get("amount"),
        currency=data.get("currency", "GHS"),
    )
    return True
