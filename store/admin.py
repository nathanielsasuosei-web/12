from django.contrib import admin

from .models import Beat, ContactMessage, Order, Video


@admin.register(Beat)
class BeatAdmin(admin.ModelAdmin):
    list_display = ("title", "price", "bpm", "musical_key", "is_published", "created_at")
    list_editable = ("price", "is_published")
    list_filter = ("is_published", "created_at")
    search_fields = ("title", "musical_key", "description")
    fieldsets = (
        (None, {"fields": ("title", "description", "price", "bpm", "musical_key", "is_published")}),
        ("Files", {"fields": ("audio_file", "preview_file", "cover_image")}),
    )


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "video_url", "created_at")
    search_fields = ("title", "description")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Purchases are read-only here: they are created and updated by the payment flow."""

    list_display = ("id", "user", "beat", "amount", "currency", "status", "channel", "paid_at", "created_at")
    list_filter = ("status", "channel", "currency", "created_at")
    search_fields = ("user__username", "user__email", "beat__title", "payment_reference")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in Order._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """Messages artists send through the contact page (also delivered by email)."""

    list_display = ("subject", "name", "email", "is_read", "created_at")
    list_editable = ("is_read",)
    list_filter = ("is_read", "created_at")
    search_fields = ("subject", "name", "email", "message")
    readonly_fields = ("name", "email", "subject", "message", "created_at")

    def has_add_permission(self, request):
        return False
