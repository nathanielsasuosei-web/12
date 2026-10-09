import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from catalog.models import Beat

from .models import Order
from .payments import PaymentError, PaystackProvider
from .services import begin_checkout, confirm_with_provider, create_pending_order, mark_paid

logger = logging.getLogger(__name__)


@login_required
@require_POST
def start_order(request, slug):
    beat = get_object_or_404(Beat, slug=slug, is_published=True)
    existing = Order.objects.filter(user=request.user, beat=beat, status=Order.Status.PAID).first()
    if existing:
        messages.info(request, "You already own this beat. Your download is below.")
        return redirect(existing)
    order = create_pending_order(request.user, beat)
    try:
        url = begin_checkout(order)
    except PaymentError as exc:
        order.status = Order.Status.FAILED
        order.save(update_fields=["status"])
        messages.error(request, str(exc))
        return redirect(beat)
    return redirect(url)


@login_required
@require_POST
def pay_order(request, reference):
    order = get_object_or_404(Order, reference=reference, user=request.user)
    if order.is_paid:
        return redirect(order)
    try:
        url = begin_checkout(order)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect(order)
    return redirect(url)


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).select_related("beat")
    return render(request, "orders/my_orders.html", {"orders": orders})


@login_required
def order_detail(request, reference):
    order = get_object_or_404(Order.objects.select_related("beat"), reference=reference, user=request.user)
    return render(request, "orders/order_detail.html", {"order": order})


@require_GET
def paystack_callback(request):
    """Buyer returns here from Paystack. Payment is confirmed with Paystack, never trusted from the URL."""
    reference = request.GET.get("reference") or request.GET.get("trxref") or ""
    order = get_object_or_404(Order.objects.select_related("beat", "user"), reference=reference)
    if not order.is_paid and order.provider == "paystack":
        try:
            confirm_with_provider(order)
        except PaymentError as exc:
            messages.info(request, f"{exc} If you were charged, your download will be emailed to you.")
    order.refresh_from_db()
    if request.user.is_authenticated and order.user_id == request.user.id:
        return redirect(order)
    return render(request, "orders/payment_received.html", {"order": order})


@csrf_exempt
def paystack_webhook(request):
    """Paystack server-to-server notification. Signed with HMAC-SHA512 using the secret key."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    secret = settings.PAYSTACK_SECRET_KEY
    signature = request.headers.get("x-paystack-signature", "")
    if not secret or not PaystackProvider.signature_is_valid(request.body, signature, secret):
        return HttpResponse("invalid signature", status=400)
    try:
        event = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse("invalid body", status=400)

    if event.get("event") == "charge.success":
        data = event.get("data") or {}
        order = Order.objects.filter(reference=data.get("reference", "")).first()
        if order is None:
            logger.warning("Webhook for unknown reference %r", data.get("reference"))
        else:
            try:
                mark_paid(
                    order,
                    channel=data.get("channel", ""),
                    transaction_id=data.get("id", ""),
                    amount_pesewas=data.get("amount"),
                    currency=data.get("currency", "GHS"),
                )
            except PaymentError:
                logger.error("Webhook payment rejected for order %s", order.reference)
    return HttpResponse("ok")


@login_required
def mock_checkout(request, reference):
    """Development-only checkout page. Returns 404 whenever DEBUG is off."""
    if not settings.DEBUG or settings.PAYMENT_PROVIDER != "mock":
        raise Http404
    order = get_object_or_404(Order.objects.select_related("beat"), reference=reference, user=request.user)
    if request.method == "POST":
        if not order.is_paid:
            mark_paid(order, channel="mock", transaction_id=f"mock-{order.reference}")
        return redirect(order)
    return render(request, "orders/mock_checkout.html", {"order": order})


def download(request, token):
    """Send the full beat to a buyer who holds a valid, paid download token."""
    order = get_object_or_404(Order.objects.select_related("beat"), download_token=token, status=Order.Status.PAID)
    limit = settings.MAX_DOWNLOADS_PER_ORDER
    # Atomic check-and-increment so two simultaneous requests cannot exceed the limit.
    allowed = Order.objects.filter(pk=order.pk, download_count__lt=limit).update(download_count=F("download_count") + 1)
    if not allowed:
        return render(request, "orders/download_limit.html", {"order": order, "limit": limit}, status=403)
    beat_file = order.beat.full_audio
    if not beat_file:
        raise Http404
    try:
        handle = beat_file.open("rb")
    except FileNotFoundError:
        logger.error("Missing full file for beat %s", order.beat_id)
        raise Http404
    return FileResponse(handle, as_attachment=True, filename=os.path.basename(beat_file.name))
