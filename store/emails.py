import logging
import mimetypes
import os

from django.conf import settings
from django.core.mail import EmailMessage, send_mail

logger = logging.getLogger(__name__)


def _absolute(path):
    return f"{settings.SITE_URL}{path}"


def send_purchase_emails(order):
    """Send the buyer their receipt + beat, and notify the producer. Failures are logged, not raised."""
    _send_buyer_email(order)
    _notify_producer(order)


def _send_buyer_email(order):
    beat = order.beat
    download_url = _absolute(order.get_download_url())
    body = (
        f"Hi {order.user.username},\n\n"
        f"Thank you for your purchase! Your payment was received.\n\n"
        f"Order:    #{order.pk}\n"
        f"Beat:     {beat.title}\n"
        f"Amount:   {order.amount} {order.currency}\n"
        f"Paid via: {order.channel or 'Paystack'}\n\n"
        f"Download your beat here (link stays valid for your order):\n{download_url}\n\n"
        f"Your account dashboard: {_absolute('/dashboard/')}\n\n"
        f"Thanks for supporting {settings.SITE_NAME}!\n"
    )
    message = EmailMessage(
        subject=f"Your beat is ready: {beat.title} (Order #{order.pk})",
        body=body,
        to=[order.user.email],
    )

    audio = beat.audio_file
    try:
        if audio and audio.size <= settings.EMAIL_ATTACH_MAX_BYTES:
            name = os.path.basename(audio.name)
            mimetype = mimetypes.guess_type(name)[0] or "application/octet-stream"
            with audio.open("rb") as handle:
                message.attach(name, handle.read(), mimetype)
    except OSError:
        logger.exception("Could not attach beat file for order %s", order.pk)

    try:
        message.send()
    except Exception:
        logger.exception("Failed to send purchase email for order %s", order.pk)


def _notify_producer(order):
    if not settings.PRODUCER_EMAIL:
        return
    try:
        send_mail(
            subject=f"New sale: {order.beat.title} (Order #{order.pk})",
            message=(
                f"{order.user.username} ({order.user.email}) bought '{order.beat.title}' "
                f"for {order.amount} {order.currency} via {order.channel or 'Paystack'}.\n\n"
                f"Admin: {_absolute('/admin/store/order/')}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.PRODUCER_EMAIL],
        )
    except Exception:
        logger.exception("Failed to notify producer for order %s", order.pk)


def send_contact_emails(contact_message):
    """Forward an artist's message to the producer and confirm receipt to the sender."""
    if settings.PRODUCER_EMAIL:
        try:
            EmailMessage(
                subject=f"New message: {contact_message.subject}",
                body=(
                    f"From: {contact_message.name} <{contact_message.email}>\n\n"
                    f"{contact_message.message}\n\n"
                    f"Reply directly to {contact_message.email}.\n"
                    f"Admin: {_absolute('/admin/store/contactmessage/')}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.PRODUCER_EMAIL],
                reply_to=[contact_message.email],
            ).send()
        except Exception:
            logger.exception("Failed to forward contact message %s", contact_message.pk)
    try:
        send_mail(
            subject=f"We got your message: {contact_message.subject}",
            message=(
                f"Hi {contact_message.name},\n\n"
                f"Thanks for reaching out to {settings.SITE_NAME}! "
                f"The producer will reply to this email address shortly.\n\n"
                f"Your message:\n{contact_message.message}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[contact_message.email],
        )
    except Exception:
        logger.exception("Failed to confirm contact message %s", contact_message.pk)
