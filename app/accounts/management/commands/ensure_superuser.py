"""
Idempotent superuser creation for container startup.

Reads credentials from env vars and creates the superuser only if one
with that email doesn't already exist.

Usage:
    python manage.py ensure_superuser

Env vars:
    DJANGO_SUPERUSER_EMAIL    (required)
    DJANGO_SUPERUSER_PASSWORD (required)
    DJANGO_SUPERUSER_USERNAME (optional, defaults to "admin")
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from env vars if one doesn't already exist."

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin").strip()

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD not set — skipping."
            ))
            return

        User = get_user_model()

        if User.objects.filter(email=email).exists() or User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f"Superuser {email} already exists — skipping."
            ))
            return

        User.objects.create_superuser(email=email, name=username, password=password)

        self.stdout.write(self.style.SUCCESS(
            f"Superuser created: {email} (username={username})"
        ))
