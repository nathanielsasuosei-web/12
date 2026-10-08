"""Fail the build if the production configuration is incomplete (see config/production.py)."""
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from config.production import check_production_config


class Command(BaseCommand):
    help = (
        "Exit with an error if production settings are missing or unsafe. "
        "vercel.json runs this as the Vercel build command."
    )
    # This command runs its own checks, so Django's system checks are not needed first.
    requires_system_checks = []

    def handle(self, *args, **options):
        try:
            check_production_config()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write("Production configuration check passed.")
