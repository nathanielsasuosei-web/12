"""Create demo content: producer login, sample beats with covers + previews, and a video."""
import math
import struct
import wave
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand

from store.models import Beat, Video

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None


BEATS = [
    {"title": "Lagos Nights", "price": "75.00", "bpm": 102, "musical_key": "Fm", "freq": 220.0,
     "description": "Afrobeats groove with log drums, shakers, and a late-night guitar loop."},
    {"title": "Red Thunder", "price": "60.00", "bpm": 140, "musical_key": "Am", "freq": 277.0,
     "description": "Dark trap banger. Booming 808s, crisp hats, and an anthem lead."},
    {"title": "Golden Hour", "price": "50.00", "bpm": 92, "musical_key": "C", "freq": 261.6,
     "description": "Soulful hip-hop sample flip with warm keys and dusty drums."},
]


def make_tone(path, freq, seconds=8, sample_rate=22050):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for i in range(int(seconds * sample_rate)):
        t = i / sample_rate
        envelope = min(1.0, t * 4) * min(1.0, (seconds - t) * 2)
        sample = math.sin(2 * math.pi * freq * t) * 0.5 * envelope
        sample += math.sin(2 * math.pi * freq * 2 * t) * 0.2 * envelope
        frames += struct.pack("<h", int(sample * 32767))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))


def make_cover(path, title):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (600, 600), (13, 5, 7))
    draw = ImageDraw.Draw(img)
    for y in range(600):
        ratio = y / 600
        draw.line([(0, y), (600, y)],
                  fill=(int(143 + ratio * 112), int(0 + ratio * 20), int(16 + ratio * 30)))
    for i, bar in enumerate([180, 260, 340, 300, 220, 150, 200, 320, 260, 190]):
        x = 40 + i * 52
        draw.rectangle([x, 480 - bar, x + 36, 480], fill=(255, 210, 63) if i % 3 == 0 else (255, 30, 44))
    draw.text((40, 500), title[:22], fill=(255, 255, 255))
    img.save(path, "JPEG", quality=85)


class Command(BaseCommand):
    help = "Seed demo beats, covers, previews, and a video."

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(username="producer").exists():
            User.objects.create_superuser("producer", "producer@example.com", "producer123")
            self.stdout.write("Created producer login: producer / producer123")
        else:
            self.stdout.write("Producer user already exists.")

        media = Path(settings.MEDIA_ROOT)
        for beat_data in BEATS:
            if Beat.objects.filter(title=beat_data["title"]).exists():
                self.stdout.write(f"Beat already exists: {beat_data['title']}")
                continue
            beat = Beat(
                title=beat_data["title"],
                description=beat_data["description"],
                price=beat_data["price"],
                bpm=beat_data["bpm"],
                musical_key=beat_data["musical_key"],
            )
            slug = beat_data["title"].lower().replace(" ", "-")
            full_path = media / "beats" / f"{slug}-full.wav"
            preview_path = media / "previews" / f"{slug}-preview.wav"
            make_tone(full_path, beat_data["freq"], seconds=12)
            make_tone(preview_path, beat_data["freq"], seconds=8)
            with open(full_path, "rb") as fh:
                beat.audio_file.save(full_path.name, File(fh), save=False)
            with open(preview_path, "rb") as fh:
                beat.preview_file.save(preview_path.name, File(fh), save=False)
            if Image is not None:
                cover_path = media / "covers" / f"{slug}.jpg"
                make_cover(cover_path, beat_data["title"])
                with open(cover_path, "rb") as fh:
                    beat.cover_image.save(cover_path.name, File(fh), save=False)
            beat.save()
            self.stdout.write(f"Created beat: {beat.title}")

        if not Video.objects.filter(title="Studio Session — Red Thunder").exists():
            Video.objects.create(
                title="Studio Session — Red Thunder",
                description="Behind the scenes: building the beat from scratch.",
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            )
            self.stdout.write("Created demo video.")

        self.stdout.write(self.style.SUCCESS("Demo content ready."))
