from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .storage import PrivateFileStorage
from .utils import unique_slug_for, youtube_video_id


class Beat(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    genre = models.CharField(max_length=60, blank=True)
    bpm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(40), MaxValueValidator(300)],
    )
    musical_key = models.CharField(max_length=20, blank=True, help_text="For example: C# minor")
    price_ghs = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00"))],
        help_text="Price in Ghana cedis (GHS).",
    )
    cover_image = models.ImageField(
        upload_to="covers/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    preview_audio = models.FileField(
        upload_to="previews/",
        validators=[FileExtensionValidator(["mp3"])],
        help_text="Public MP3 preview that visitors can play.",
    )
    full_audio = models.FileField(
        upload_to="full/",
        storage=PrivateFileStorage(),
        validators=[FileExtensionValidator(["wav", "mp3", "flac", "zip"])],
        help_text="Full-quality file. Only buyers can download it. Stored privately.",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug_for(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:beat_detail", args=[self.slug])

    @property
    def price_pesewas(self):
        return int(self.price_ghs * 100)


class Video(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    youtube_url = models.URLField(
        blank=True,
        help_text="Paste a YouTube link. Leave empty if you upload a file instead.",
    )
    video_file = models.FileField(
        upload_to="videos/",
        blank=True,
        validators=[FileExtensionValidator(["mp4", "webm", "mov"])],
        help_text="Upload a video file. Leave empty if you use a YouTube link.",
    )
    thumbnail = models.ImageField(
        upload_to="thumbnails/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if not self.youtube_url and not self.video_file:
            raise ValidationError("Add a YouTube link or upload a video file.")
        if self.youtube_url and not youtube_video_id(self.youtube_url):
            raise ValidationError({"youtube_url": "Enter a valid YouTube video link."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug_for(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:video_detail", args=[self.slug])

    @property
    def youtube_id(self):
        return youtube_video_id(self.youtube_url)
