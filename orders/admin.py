from django.contrib import admin, messages

from .emails import send_download_email
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "beat", "amount_ghs", "status", "channel", "download_count", "paid_at")
    list_filter = ("status", "channel", "provider")
    search_fields = ("reference", "user__email", "beat__title", "provider_transaction_id")
    readonly_fields = [f.name for f in Order._meta.fields]
    actions = ["resend_download_email"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description="Resend download email to the buyer")
    def resend_download_email(self, request, queryset):
        sent = 0
        for order in queryset.filter(status=Order.Status.PAID).select_related("beat", "user"):
            send_download_email(order)
            sent += 1
        messages.success(request, f"Sent {sent} download email(s).")
