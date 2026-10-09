from django.contrib import admin

from .models import Beat, Video


@admin.register(Beat)
class BeatAdmin(admin.ModelAdmin):
    list_display = ("title", "genre", "bpm", "musical_key", "price_ghs", "is_published", "created_at")
    list_editable = ("is_published",)
    list_filter = ("is_published", "genre")
    search_fields = ("title", "genre", "description")
    readonly_fields = ("slug", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "description", "is_published")}),
        ("Details", {"fields": ("genre", "bpm", "musical_key", "price_ghs")}),
        ("Files", {"fields": ("cover_image", "preview_audio", "full_audio")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "created_at")
    list_editable = ("is_published",)
    list_filter = ("is_published",)
    search_fields = ("title", "description")
    readonly_fields = ("slug", "created_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "description", "is_published")}),
        ("Video", {"fields": ("youtube_url", "video_file", "thumbnail")}),
        ("Dates", {"fields": ("created_at",)}),
    )
