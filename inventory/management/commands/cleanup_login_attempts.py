from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import LoginAttempt


class Command(BaseCommand):
    help = "Remove expired login-throttle records. Safe to run periodically."

    def handle(self, *args, **options):
        count, _ = LoginAttempt.objects.filter(
            started_at__lt=timezone.now() - timedelta(days=1)
        ).delete()
        self.stdout.write(f"Removed {count} expired login-attempt records.")
