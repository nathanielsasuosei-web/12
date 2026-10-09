from django.db import models
from django.utils import timezone


class ContactMessage(models.Model):
    class Topic(models.TextChoices):
        GENERAL = "general", "General question"
        CUSTOM = "custom", "Custom beat or session"
        LICENSING = "licensing", "Licensing"
        SUPPORT = "support", "Payment or download help"

    name = models.CharField(max_length=150)
    email = models.EmailField()
    topic = models.CharField(max_length=20, choices=Topic.choices, default=Topic.GENERAL)
    message = models.TextField(max_length=3000)
    created_at = models.DateTimeField(default=timezone.now)
    is_handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.get_topic_display()})"
