import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from catalog.models import Beat


def new_reference():
    return "BS-" + uuid.uuid4().hex[:24].upper()


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"

    reference = models.CharField(max_length=64, unique=True, default=new_reference)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    beat = models.ForeignKey(Beat, on_delete=models.PROTECT, related_name="orders")
    amount_ghs = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=20, blank=True)
    channel = models.CharField(
        max_length=30, blank=True, help_text="How the buyer paid, for example mobile_money or bank."
    )
    provider_transaction_id = models.CharField(max_length=64, blank=True)
    download_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.beat} · {self.get_status_display()}"

    @property
    def amount_pesewas(self):
        return int((self.amount_ghs * Decimal("100")).quantize(Decimal("1")))

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    def get_absolute_url(self):
        return reverse("orders:order_detail", args=[self.reference])

    def download_url(self):
        return reverse("orders:download", args=[self.download_token]) if self.download_token else ""
