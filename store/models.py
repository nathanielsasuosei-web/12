import re
import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse


def _default_currency():
    return settings.PAYMENT_CURRENCY


def _new_reference():
    return f"12-{uuid.uuid4().hex[:20]}"


class Beat(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    audio_file = models.FileField(
        upload_to="beats/",
        validators=[FileExtensionValidator(["mp3", "wav", "aiff", "aif", "flac", "m4a", "zip"])],
    )
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    bpm = models.PositiveIntegerField(blank=True, null=True)
    musical_key = models.CharField(max_length=10, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("beat_detail", args=[self.pk])


class Video(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_file = models.FileField(
        upload_to="videos/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["mp4", "webm", "mov"])],
    )
    video_url = models.URLField(blank=True, help_text="Optional YouTube or Vimeo link.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        url = self.video_url or ""
        match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{11})", url)
        if match:
            return f"https://www.youtube.com/embed/{match.group(1)}"
        match = re.search(r"vimeo\.com/(\d+)", url)
        if match:
            return f"https://player.vimeo.com/video/{match.group(1)}"
        return ""


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    beat = models.ForeignKey(Beat, on_delete=models.PROTECT, related_name="orders")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default=_default_currency)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_reference = models.CharField(max_length=64, unique=True, default=_new_reference)
    channel = models.CharField(max_length=30, blank=True, help_text="e.g. mobile_money or bank")
    download_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    download_count = models.PositiveIntegerField(default=0)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} - {self.user} - {self.beat}"

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    def get_download_url(self):
        return reverse("download", args=[self.download_token])
