import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .data_transfer import digest, export_workspace, restore_workspace, workspace_models
from .models import Item, Notification, StockRequest


@override_settings(DEBUG=True, ON_VERCEL=False)
class WorkspaceTransferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with patch.dict("os.environ", {"LIDMS_DEMO_PASSWORD": "Transfer-test-password-829!"}):
            call_command("seed_demo", stdout=StringIO())

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "workspace.json"

    def empty_workspace(self):
        for model in reversed(workspace_models()):
            model.objects.all().delete()

    def test_round_trip_preserves_hashes_relations_balances_and_read_states(self):
        counts = export_workspace(self.path)
        user = get_user_model().objects.get(username="demo.faculty")
        expected = (
            user.pk,
            user.password,
            list(
                Notification.objects.order_by("pk").values_list(
                    "pk", "recipient_id", "is_read", "object_id"
                )
            ),
            list(StockRequest.objects.order_by("pk").values_list("pk", "quantity_returned")),
        )
        self.empty_workspace()
        self.assertEqual(restore_workspace(self.path), counts)
        user = get_user_model().objects.get(username="demo.faculty")
        actual = (
            user.pk,
            user.password,
            list(
                Notification.objects.order_by("pk").values_list(
                    "pk", "recipient_id", "is_read", "object_id"
                )
            ),
            list(StockRequest.objects.order_by("pk").values_list("pk", "quantity_returned")),
        )
        self.assertEqual(actual, expected)
        self.assertTrue(user.check_password("Transfer-test-password-829!"))

    def test_existing_target_is_never_overwritten(self):
        counts = export_workspace(self.path)
        with self.assertRaisesMessage(CommandError, "already contains"):
            restore_workspace(self.path)
        self.assertEqual(Item.objects.count(), counts["inventory.item"])

    def test_damaged_export_is_rejected_before_loading(self):
        export_workspace(self.path)
        payload = json.loads(self.path.read_text())
        payload["sha256"] = "damaged"
        self.path.write_text(json.dumps(payload))
        with self.assertRaisesMessage(CommandError, "damaged"):
            restore_workspace(self.path)

    def test_invalid_stock_rolls_back_the_whole_restore(self):
        export_workspace(self.path)
        payload = json.loads(self.path.read_text())
        item = next(row for row in payload["objects"] if row["model"] == "inventory.item")
        item["fields"]["quantity"] += 100
        payload["sha256"] = digest(payload["objects"])
        self.path.write_text(json.dumps(payload))
        self.empty_workspace()
        with self.assertRaisesMessage(CommandError, "Stock history"):
            restore_workspace(self.path)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Item.objects.exists())

    def test_import_command_refuses_the_local_sqlite_target(self):
        export_workspace(self.path)
        with self.assertRaisesMessage(CommandError, "PostgreSQL target"):
            call_command("import_workspace", str(self.path), stdout=StringIO())
