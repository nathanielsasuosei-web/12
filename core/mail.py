import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_email(subject, template, context, to, reply_to=None, raise_errors=False):
    """Render a plain-text template and send it. Returns True when the mail was accepted."""
    body = render_to_string(template, context)
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to] if isinstance(to, str) else list(to),
        reply_to=[reply_to] if reply_to else None,
    )
    try:
        message.send()
    except Exception:
        logger.exception("Could not send email %r to %s", subject, to)
        if raise_errors:
            raise
        return False
    return True
