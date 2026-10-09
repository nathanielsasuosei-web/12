import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateFileStorage(FileSystemStorage):
    """Storage for paid beat files. It lives outside MEDIA_ROOT, so the web server never serves it.

    The path is read from settings on each use, not when the model loads, so
    overriding PRIVATE_MEDIA_ROOT in tests or deployments takes effect.
    """

    @property
    def base_location(self):
        return os.fspath(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None
