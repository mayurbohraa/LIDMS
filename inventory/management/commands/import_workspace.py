import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from inventory.data_transfer import restore_workspace


class Command(BaseCommand):
    help = "Import a workspace into an empty Neon/PostgreSQL database after migrations."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError(
                "This command requires the Neon/PostgreSQL target, not local SQLite."
            )
        counts = restore_workspace(options["path"])
        self.stdout.write(
            self.style.SUCCESS("Workspace imported; record counts and stock balances verified.")
        )
        self.stdout.write(json.dumps(counts, indent=2))
