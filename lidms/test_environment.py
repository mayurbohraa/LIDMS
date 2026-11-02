import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .environment import load_environment


class EnvironmentTests(SimpleTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / ".env.local").write_text("DJANGO_DEBUG=true\nDATABASE_URL=\n")
        (self.root / ".env.neon").write_text(
            "DJANGO_DEBUG=false\nDATABASE_URL=postgresql://sample/shared\n"
            "DATABASE_URL_UNPOOLED=postgresql://sample/direct\n"
        )

    def test_localhost_shares_only_the_neon_connection(self):
        with patch.dict(os.environ, {}, clear=True):
            load_environment(self.root)
            self.assertEqual(os.environ["DATABASE_URL"], "postgresql://sample/shared")
            self.assertEqual(os.environ["DJANGO_DEBUG"], "true")

    def test_blank_neon_file_keeps_sqlite_before_connection(self):
        (self.root / ".env.neon").write_text("DATABASE_URL=\n")
        with patch.dict(os.environ, {}, clear=True):
            load_environment(self.root)
            self.assertFalse(os.environ.get("DATABASE_URL"))

    def test_incomplete_shared_connection_cannot_silently_start_sqlite(self):
        (self.root / ".env.neon").write_text("DATABASE_URL_UNPOOLED=postgresql://sample/direct\n")
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ImproperlyConfigured):
            load_environment(self.root)

    def test_hosting_uses_only_injected_environment(self):
        with patch.dict(os.environ, {"VERCEL": "1", "DATABASE_URL": "hosted"}, clear=True):
            load_environment(self.root)
            self.assertEqual(os.environ["DATABASE_URL"], "hosted")
            self.assertNotIn("DJANGO_DEBUG", os.environ)

    def test_explicit_sqlite_file_does_not_pick_up_neon(self):
        with patch.dict(os.environ, {"LIDMS_ENV_FILE": str(self.root / ".env.local")}, clear=True):
            load_environment(self.root)
            self.assertFalse(os.environ.get("DATABASE_URL"))

    def test_direct_maintenance_uses_unpooled_connection(self):
        with patch.dict(os.environ, {"LIDMS_USE_DIRECT_DB": "1"}, clear=True):
            load_environment(self.root)
            self.assertEqual(os.environ["DATABASE_URL"], "postgresql://sample/direct")

    def test_missing_direct_connection_is_rejected(self):
        with patch.dict(os.environ, {"VERCEL": "1", "LIDMS_USE_DIRECT_DB": "1"}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                load_environment(self.root)

    def test_missing_explicit_file_is_rejected(self):
        with patch.dict(os.environ, {"LIDMS_ENV_FILE": str(self.root / "absent")}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                load_environment(self.root)
