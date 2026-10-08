import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.db.models import F, Q
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import payments, services
from .forms import SignUpForm
from .models import Beat, Order, Video

logger = logging.getLogger(__name__)

MOCK_CHANNELS = {"mobile_money": "Mobile Money", "bank": "Bank Account"}


@require_GET
def healthz(request):
    """Readiness check for the web process and its database connection."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def _absolute(path):
    return f"{settings.SITE_URL}{path}"


def home(request):
    context = {
        "beats": Beat.objects.filter(is_published=True)[:3],
        "videos": Video.objects.all()[:3],
    }
    return render(request, "store/home.html", context)


def beat_list(request):
    query = request.GET.get("q", "").strip()
    beats = Beat.objects.filter(is_published=True)
    if query:
        beats = beats.filter(Q(title__icontains=query) | Q(musical_key__icontains=query))
    return render(request, "store/beat_list.html", {"beats": beats, "query": query})


def beat_detail(request, pk):
    beat = get_object_or_404(Beat, pk=pk, is_published=True)
    return render(request, "store/beat_detail.html", {"beat": beat})


def video_list(request):
    return render(request, "store/video_list.html", {"videos": Video.objects.all()})


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account is ready.")
            return redirect("dashboard")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard(request):
    orders = Order.objects.filter(user=request.user).select_related("beat")
    return render(request, "store/dashboard.html", {"orders": orders})


@login_required
@require_POST
def checkout(request, pk):
    beat = get_object_or_404(Beat, pk=pk, is_published=True)
    if not request.user.email:
        messages.error(request, "Please add an email address to your account before buying.")
        return redirect("beat_detail", pk=beat.pk)

    order = Order.objects.create(user=request.user, beat=beat, amount=beat.price, currency=settings.PAYMENT_CURRENCY)
    try:
        checkout_url = payments.initialize_payment(
            order,
            email=request.user.email,
            callback_url=_absolute(reverse("payment_return")),
        )
    except payments.PaymentError as exc:
        logger.error("Could not start payment for order %s: %s", order.pk, exc)
        order.status = Order.Status.FAILED
        order.save(update_fields=["status"])
        messages.error(request, f"Payment could not be started: {exc}")
        return redirect("beat_detail", pk=beat.pk)

    return redirect(checkout_url)


@require_GET
def payment_return(request):
    """Where the gateway sends the buyer after paying. The payment is always re-verified server-side."""
    reference = request.GET.get("reference") or request.GET.get("trxref")
    if not reference:
        raise Http404
    order = Order.objects.select_related("beat").filter(payment_reference=reference).first()
    if order is None:
        raise Http404
    error = ""
    try:
        order = services.confirm_payment(reference) or order
    except payments.PaymentError as exc:
        error = str(exc)
    return render(request, "store/payment_status.html", {"order": order, "error": error})


@csrf_exempt
@require_POST
def payment_webhook(request):
    if settings.PAYMENT_PROVIDER != "paystack":
        raise Http404
    signature = request.headers.get("x-paystack-signature", "")
    if not payments.verify_webhook_signature(request.body, signature):
        return HttpResponseForbidden("Invalid signature")
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest("Invalid JSON")

    if event.get("event") == "charge.success":
        reference = (event.get("data") or {}).get("reference")
        if reference:
            try:
                services.confirm_payment(reference)
            except payments.PaymentError:
                logger.exception("Webhook could not confirm %s", reference)
                return HttpResponse(status=500)
    return HttpResponse(status=200)


def mock_checkout(request, reference):
    """Local stand-in for the gateway's payment page; never enable it in production."""
    if not settings.DEBUG or settings.PAYMENT_PROVIDER != "mock":
        raise Http404
    order = get_object_or_404(Order.objects.select_related("beat", "user"), payment_reference=reference)

    if request.method == "POST" and order.status == Order.Status.PENDING:
        channel = request.POST.get("channel", "")
        if channel not in MOCK_CHANNELS:
            return HttpResponseBadRequest("Unknown channel")
        services.fulfill_order(order.pk, channel)
        return redirect(f"{reverse('payment_return')}?reference={order.payment_reference}")

    return render(
        request,
        "store/mock_checkout.html",
        {"order": order, "channels": MOCK_CHANNELS},
    )


def download(request, token):
    """Download link sent by email. Only works for paid orders."""
    order = get_object_or_404(Order.objects.select_related("beat"), download_token=token, status=Order.Status.PAID)
    Order.objects.filter(pk=order.pk).update(download_count=F("download_count") + 1)
    audio = order.beat.audio_file
    return FileResponse(
        audio.open("rb"),
        as_attachment=True,
        filename=os.path.basename(audio.name),
    )
