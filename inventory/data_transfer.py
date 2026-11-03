"""One-time workspace transfer; deliberately excludes sessions and login attempts."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.apps import apps
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections, transaction
from django.db.models import Sum
from django.utils import timezone

MODEL_LABELS = (
    "auth.group",
    "auth.user",
    "inventory.profile",
    "inventory.item",
    "inventory.stockrequest",
    "inventory.complaint",
    "inventory.stockmovement",
    "inventory.activity",
    "inventory.contactmessage",
    "inventory.notification",
)


def workspace_models():
    return [apps.get_model(label) for label in MODEL_LABELS]


def digest(objects):
    content = json.dumps(objects, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def check_balances(using="default"):
    items = (
        apps.get_model("inventory.Item")
        .objects.using(using)
        .annotate(ledger_total=Sum("movements__delta"))
    )
    for item in items:
        if item.quantity != (item.ledger_total or 0):
            raise CommandError(
                f"Stock history does not match available quantity: {item.asset_code}."
            )
    requests = (
        apps.get_model("inventory.StockRequest").objects.using(using).prefetch_related("movements")
    )
    for request in requests.filter(item__isnull=False, status="approved"):
        movements = [movement.delta for movement in request.movements.all()]
        if (
            sum(n for n in movements if n < 0) != -request.quantity
            or sum(n for n in movements if n > 0) != request.quantity_returned
        ):
            raise CommandError(f"Issue/return history does not match request #{request.pk}.")


def export_workspace(path, using="default"):
    path = Path(path)
    if path.exists():
        raise CommandError("Export file already exists. Choose another output filename.")
    with transaction.atomic(using=using):
        check_balances(using)
        rows = []
        counts = {}
        for model in workspace_models():
            # Natural foreign keys otherwise fetch the same account once per record.
            natural_relations = [
                field.name
                for field in model._meta.fields
                if field.many_to_one and hasattr(field.remote_field.model, "natural_key")
            ]
            objects = model.objects.using(using).order_by("pk")
            if natural_relations:
                objects = objects.select_related(*natural_relations)
            serialized = json.loads(
                serializers.serialize("json", objects, use_natural_foreign_keys=True)
            )
            rows.extend(serialized)
            counts[model._meta.label_lower] = len(serialized)
        payload = {
            "format": "lidms-workspace-v1",
            "exported_at": timezone.now().isoformat(),
            "counts": counts,
            "sha256": digest(rows),
            "objects": rows,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return counts


def read_export(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        objects = payload["objects"]
        if payload["format"] != "lidms-workspace-v1" or payload["sha256"] != digest(objects):
            raise ValueError
        counts = dict.fromkeys(MODEL_LABELS, 0)
        seen = set()
        for row in objects:
            key = (row["model"], row["pk"])
            if row["model"] not in counts or not row["pk"] or key in seen:
                raise ValueError
            seen.add(key)
            counts[row["model"]] += 1
        if counts != payload["counts"] or not counts["auth.user"]:
            raise ValueError
        return payload
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise CommandError(
            "Invalid or damaged workspace export; no records were imported."
        ) from error


def restore_workspace(path, using="default"):
    payload = read_export(path)
    models = workspace_models()
    with transaction.atomic(using=using):
        connection = connections[using]
        if connection.vendor == "postgresql":
            # Hold writers while checking emptiness and restoring preserved record IDs.
            tables = ", ".join(connection.ops.quote_name(model._meta.db_table) for model in models)
            with connection.cursor() as cursor:
                cursor.execute(f"LOCK TABLE {tables} IN EXCLUSIVE MODE")
        if any(model.objects.using(using).exists() for model in models):
            raise CommandError(
                "Target already contains workspace records. Import refused; nothing was overwritten."
            )
        with TemporaryDirectory(prefix="lidms-transfer-") as temporary:
            fixture = Path(temporary) / "workspace.json"
            fixture.write_text(json.dumps(payload["objects"]), encoding="utf-8")
            # Django restores relationships and resets PostgreSQL ID sequences here.
            call_command("loaddata", str(fixture), database=using, verbosity=0)
        actual = {model._meta.label_lower: model.objects.using(using).count() for model in models}
        if actual != payload["counts"]:
            raise CommandError("Imported counts do not match. The import was rolled back.")
        check_balances(using)
    return actual
