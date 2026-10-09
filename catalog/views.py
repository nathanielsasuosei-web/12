from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from orders.models import Order

from .models import Beat, Video


def home(request):
    beats = Beat.objects.filter(is_published=True)[:6]
    videos = Video.objects.filter(is_published=True)[:3]
    return render(request, "catalog/home.html", {"beats": beats, "videos": videos})


def beat_list(request):
    beats = Beat.objects.filter(is_published=True)
    query = request.GET.get("q", "").strip()
    genre = request.GET.get("genre", "").strip()
    if query:
        beats = beats.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if genre:
        beats = beats.filter(genre__iexact=genre)
    genres = (
        Beat.objects.filter(is_published=True)
        .exclude(genre="")
        .values_list("genre", flat=True)
        .distinct()
        .order_by("genre")
    )
    page = Paginator(beats, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "catalog/beat_list.html",
        {"page": page, "query": query, "genre": genre, "genres": genres},
    )


def beat_detail(request, slug):
    beat = get_object_or_404(Beat, slug=slug, is_published=True)
    already_bought = False
    if request.user.is_authenticated:
        already_bought = Order.objects.filter(user=request.user, beat=beat, status=Order.Status.PAID).exists()
    return render(request, "catalog/beat_detail.html", {"beat": beat, "already_bought": already_bought})


def video_list(request):
    page = Paginator(Video.objects.filter(is_published=True), 12).get_page(request.GET.get("page"))
    return render(request, "catalog/video_list.html", {"page": page})


def video_detail(request, slug):
    video = get_object_or_404(Video, slug=slug, is_published=True)
    return render(request, "catalog/video_detail.html", {"video": video})
