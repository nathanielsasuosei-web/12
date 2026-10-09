import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def unique_slug_for(instance, value, max_length=200):
    """Return a slug for value that does not clash with other rows of the same model."""
    from django.utils.text import slugify

    base = slugify(value)[:max_length] or "item"
    slug = base
    model = type(instance)
    counter = 2
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        suffix = f"-{counter}"
        slug = f"{base[: max_length - len(suffix)]}{suffix}"
        counter += 1
    return slug


def youtube_video_id(url):
    """Extract an 11-character YouTube video id from common URL shapes, or return None."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    candidate = None
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
                candidate = parts[1]
    if candidate and _YOUTUBE_ID.match(candidate):
        return candidate
    return None
