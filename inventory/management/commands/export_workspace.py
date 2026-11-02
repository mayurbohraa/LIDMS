import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from inventory.data_transfer import export_workspace


class Command(BaseCommand):
    help = "Export the current SQLite workspace for its initial Neon transfer."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("Use --env-file .env.local to export the original SQLite workspace.")
        counts = export_workspace(options["output"])
        self.stdout.write(
            self.style.SUCCESS("Workspace exported. Keep this private file out of Git.")
        )
        self.stdout.write(json.dumps(counts, indent=2))
