"""Order fulfilment. Every path that marks an order as paid goes through fulfill_order()."""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import emails, payments
from .models import Order

logger = logging.getLogger(__name__)


def fulfill_order(order_id, channel=""):
    """Mark an order PAID exactly once and send the emails. Returns (order, newly_paid)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("beat", "user").get(pk=order_id)
        if order.is_paid:
            return order, False
        order.status = Order.Status.PAID
        order.channel = (channel or "")[:30]
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "channel", "paid_at"])

    emails.send_purchase_emails(order)
    return order, True


def confirm_payment(reference):
    """Check a transaction with the provider and fulfil the order if it succeeded.

    Returns the Order (or None if the reference is unknown). Raises PaymentError on provider problems.
    """
    order = Order.objects.select_related("beat", "user").filter(payment_reference=reference).first()
    if order is None:
        return None
    if order.is_paid or settings.PAYMENT_PROVIDER == "mock":
        return order

    result = payments.verify_with_provider(reference)
    if result.status == "success":
        if result.amount != payments.to_subunits(order.amount) or result.currency != order.currency:
            logger.error(
                "Payment mismatch for %s: got %s %s, expected %s %s",
                reference, result.amount, result.currency,
                payments.to_subunits(order.amount), order.currency,
            )
            raise payments.PaymentError("The amount paid does not match this order.")
        order, _ = fulfill_order(order.pk, result.channel)
    elif result.status in ("failed", "abandoned") and order.status == Order.Status.PENDING:
        Order.objects.filter(pk=order.pk, status=Order.Status.PENDING).update(status=Order.Status.FAILED)
        order.refresh_from_db()
    return order
