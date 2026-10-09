from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Beat, Video
from .utils import youtube_video_id


def make_beat(title="Red Night", **kwargs):
    defaults = {
        "price_ghs": Decimal("150.00"),
        "preview_audio": SimpleUploadedFile("preview.mp3", b"ID3 preview bytes"),
        "full_audio": SimpleUploadedFile("full.wav", b"RIFF full bytes"),
        "is_published": True,
        "genre": "Drill",
        "bpm": 140,
    }
    defaults.update(kwargs)
    return Beat.objects.create(title=title, **defaults)


@override_settings(MEDIA_ROOT="/tmp/beatstore-test-media", PRIVATE_MEDIA_ROOT="/tmp/beatstore-test-private")
class CatalogPagesTests(TestCase):
    def test_home_renders_hero_and_latest_beats(self):
        make_beat("Visible Beat")
        response = self.client.get(reverse("catalog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hero-canvas")
        self.assertContains(response, "Visible Beat")

    def test_unpublished_beat_is_hidden(self):
        beat = make_beat("Secret Draft", is_published=False)
        self.assertEqual(self.client.get(beat.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("catalog:beat_list")), "Secret Draft")

    def test_beat_list_filters_by_genre(self):
        make_beat("Drill One", genre="Drill")
        make_beat("Amapiano One", genre="Amapiano")
        response = self.client.get(reverse("catalog:beat_list"), {"genre": "Amapiano"})
        self.assertContains(response, "Amapiano One")
        self.assertNotContains(response, "Drill One")

    def test_beat_detail_shows_preview_and_buy_prompt_for_guests(self):
        beat = make_beat("Preview Me")
        response = self.client.get(beat.get_absolute_url())
        self.assertContains(response, "<audio")
        self.assertContains(response, "Sign in to buy")
        self.assertNotContains(response, beat.full_audio.name)

    def test_duplicate_titles_get_unique_slugs(self):
        first = make_beat("Same Name")
        second = make_beat("Same Name")
        self.assertEqual(first.slug, "same-name")
        self.assertEqual(second.slug, "same-name-2")

    def test_video_detail_embeds_youtube_without_arbitrary_urls(self):
        video = Video.objects.create(
            title="Studio Session", youtube_url="https://youtu.be/dQw4w9WgXcQ", is_published=True
        )
        response = self.client.get(video.get_absolute_url())
        self.assertContains(response, "youtube-nocookie.com/embed/dQw4w9WgXcQ")


@override_settings(MEDIA_ROOT="/tmp/beatstore-test-media", PRIVATE_MEDIA_ROOT="/tmp/beatstore-test-private")
class YouTubeParsingTests(TestCase):
    def test_accepts_common_shapes(self):
        self.assertEqual(youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_rejects_other_hosts_and_bad_ids(self):
        self.assertIsNone(youtube_video_id("https://evil.example.com/watch?v=dQw4w9WgXcQ"))
        self.assertIsNone(youtube_video_id("https://www.youtube.com/watch?v=short"))
        self.assertIsNone(youtube_video_id(""))

    def test_video_needs_a_source(self):
        video = Video(title="No source")
        with self.assertRaises(ValidationError):
            video.clean()

    def test_video_rejects_invalid_youtube_link(self):
        video = Video(title="Bad link", youtube_url="https://example.com/video")
        with self.assertRaises(ValidationError):
            video.clean()


@override_settings(MEDIA_ROOT="/tmp/beatstore-test-media", PRIVATE_MEDIA_ROOT="/tmp/beatstore-test-private")
class ProducerUploadTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.producer = get_user_model().objects.create_superuser(
            username="producer@example.com", email="producer@example.com", password="Studio-Pass-2026!"
        )
        self.client.force_login(self.producer)

    def beat_data(self, **overrides):
        data = {
            "title": "Uploaded Beat",
            "description": "Fresh from the studio",
            "genre": "Drill",
            "bpm": 140,
            "musical_key": "A minor",
            "price_ghs": "120.00",
            "preview_audio": SimpleUploadedFile("preview.mp3", b"ID3 preview"),
            "full_audio": SimpleUploadedFile("full.wav", b"RIFF full"),
            "is_published": "on",
        }
        data.update(overrides)
        return data

    def test_producer_can_upload_a_beat_in_admin(self):
        response = self.client.post(reverse("admin:catalog_beat_add"), self.beat_data())
        self.assertRedirects(response, reverse("admin:catalog_beat_changelist"))
        beat = Beat.objects.get()
        self.assertEqual(beat.slug, "uploaded-beat")
        self.assertTrue(beat.is_published)
        self.assertTrue(beat.full_audio.name.startswith("full/"))
        self.assertTrue(beat.preview_audio.name.startswith("previews/"))

    def test_admin_rejects_wrong_file_types(self):
        response = self.client.post(
            reverse("admin:catalog_beat_add"),
            self.beat_data(full_audio=SimpleUploadedFile("virus.exe", b"MZ")),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Beat.objects.exists())

    def test_video_needs_a_link_or_file(self):
        response = self.client.post(
            reverse("admin:catalog_video_add"),
            {"title": "Empty video", "description": "", "youtube_url": "", "is_published": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Video.objects.exists())
