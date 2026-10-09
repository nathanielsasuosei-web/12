import logging

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from core.mail import send_email

from .forms import ContactForm

logger = logging.getLogger(__name__)


def contact(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {"name": request.user.first_name, "email": request.user.email}
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save()
            try:
                # Producer receives the message by email and can reply straight from the inbox.
                if settings.PRODUCER_EMAIL:
                    send_email(
                        subject=f"[{message.get_topic_display()}] Message from {message.name}",
                        template="emails/contact_to_producer.txt",
                        context={"message": message},
                        to=settings.PRODUCER_EMAIL,
                        reply_to=message.email,
                        raise_errors=True,
                    )
                send_email(
                    subject=f"We received your message, {message.name}",
                    template="emails/contact_confirmation.txt",
                    context={"message": message, "site_name": settings.SITE_NAME},
                    to=message.email,
                    raise_errors=True,
                )
            except Exception:
                logger.exception("Contact form email failed for message %s", message.pk)
                messages.error(
                    request, "Your message was saved, but the email could not be sent. Please try again later."
                )
                return render(request, "contact/contact.html", {"form": form})
            return redirect("contact:thanks")
    else:
        form = ContactForm(initial=initial)
    return render(request, "contact/contact.html", {"form": form})


def thanks(request):
    return render(request, "contact/thanks.html")
