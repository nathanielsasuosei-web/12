import logging

from django.conf import settings
from django.urls import reverse

from core.mail import send_email

from .models import Order

logger = logging.getLogger(__name__)


def send_download_email(order):
    """Send the buyer their receipt and download link. Safe to call again to resend."""
    beat = order.beat
    download_url = settings.SITE_URL + order.download_url()
    send_email(
        subject=f"Your beat is ready: {beat.title}",
        template="emails/purchase_download.txt",
        context={
            "order": order,
            "beat": beat,
            "download_url": download_url,
            "max_downloads": settings.MAX_DOWNLOADS_PER_ORDER,
            "site_name": settings.SITE_NAME,
            "orders_url": settings.SITE_URL + reverse("orders:my_orders"),
        },
        to=order.user.email,
    )


def send_sale_email(order):
    if not settings.PRODUCER_EMAIL:
        return
    send_email(
        subject=f"New sale: {order.beat.title} (GHS {order.amount_ghs})",
        template="emails/sale_to_producer.txt",
        context={"order": order, "admin_url": settings.SITE_URL + "/admin/orders/order/"},
        to=settings.PRODUCER_EMAIL,
    )


def send_purchase_emails(order_pk):
    order = Order.objects.select_related("beat", "user").get(pk=order_pk)
    try:
        send_download_email(order)
        send_sale_email(order)
    except Exception:
        logger.exception("Purchase emails failed for order %s", order.reference)
