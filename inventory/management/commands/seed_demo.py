"""Populate a local sample workspace without resetting users or existing workflows."""

import getpass
import os
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventory.models import (
    Activity,
    Complaint,
    ContactMessage,
    Item,
    Notification,
    Profile,
    StockRequest,
)
from inventory.services import adjust_stock, return_stock, review_request


class Command(BaseCommand):
    help = "Add connected sample data for every local demo role. Never resets existing records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-hosted-demo",
            action="store_true",
            help="Allow a non-debug demo installation explicitly marked LIDMS_DEMO_MODE=true.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if (not settings.DEBUG or settings.ON_VERCEL) and not (
            settings.DEMO_MODE and options["allow_hosted_demo"]
        ):
            raise CommandError(
                "Hosted demo seeding requires LIDMS_DEMO_MODE=true and --allow-hosted-demo. "
                "Never enable this against real college records."
            )
        password = os.getenv("LIDMS_DEMO_PASSWORD") or getpass.getpass(
            "Password for local demo accounts: "
        )
        validate_password(password)
        self.now = timezone.now()
        users = self.seed_users(password)
        items = self.seed_inventory(users)
        self.seed_requests(users, items)
        self.seed_complaints(users, items)
        self.seed_messages(users)
        self.stdout.write(
            self.style.SUCCESS(
                "Sample workspace ready: equipment, requests, returns, repairs, notifications, "
                "activity and inquiries. Existing records, passwords and read states were preserved. "
                "Log in as demo.admin, demo.faculty or demo.technician."
            )
        )

    def timestamp(self, record, days):
        # Only called for newly created samples; reruns must retain visitor changes.
        type(record).objects.filter(pk=record.pk).update(created_at=self.now - timedelta(days=days))

    def activity(self, actor, message):
        Activity.objects.get_or_create(actor=actor, message=message)

    def notification(self, recipient, message, resource, object_id=None, read=False):
        Notification.objects.get_or_create(
            recipient=recipient,
            message=message,
            resource=resource,
            object_id=object_id,
            defaults={"is_read": read},
        )

    def seed_users(self, password):
        users = {}
        examples = [
            ("admin", "Alex", "Demo", "admin", "Computer Science", True),
            ("faculty", "Jordan", "Demo", "faculty", "Computer Science", True),
            ("technician", "Taylor", "Demo", "technician", "Laboratory Services", True),
            ("faculty2", "Casey", "Sample", "faculty", "Electronics", True),
            ("technician2", "Morgan", "Sample", "technician", "Laboratory Services", True),
            ("pending", "Sam", "Sample", "faculty", "Applied Sciences", False),
        ]
        for key, first, last, role, department, active in examples:
            user, created = get_user_model().objects.get_or_create(
                username=f"demo.{key}",
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{key}@lidms.example",
                    "is_active": active,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            Profile.objects.get_or_create(
                user=user, defaults={"role": role, "department": department}
            )
            users[key] = user
        return users

    def seed_inventory(self, users):
        equipment = [
            (
                "Desktop workstation",
                "PC",
                "Computers",
                "Computer Lab A",
                32,
                5,
                "Student workstations for programming and operating system practicals.",
                True,
            ),
            (
                "Digital multimeter",
                "MM",
                "Instruments",
                "Electronics Lab",
                18,
                4,
                "Handheld meters for voltage, resistance and continuity measurements.",
                True,
            ),
            (
                "Network switch",
                "NS",
                "Networking",
                "Network Lab",
                3,
                4,
                "Managed switches for VLAN and network configuration exercises.",
                True,
            ),
            (
                "Oscilloscope",
                "OS",
                "Instruments",
                "Electronics Lab",
                8,
                2,
                "Two-channel oscilloscopes supplied with probes and power leads.",
                True,
            ),
            (
                "HDMI adapter",
                "HD",
                "Accessories",
                "Computer Lab A",
                4,
                5,
                "Display adapters for classroom demonstrations; replenishment is due.",
                True,
            ),
            (
                "Arduino starter kit",
                "AR",
                "Development kits",
                "Innovation Lab",
                12,
                3,
                "Microcontroller kits with breadboards, sensors and jumper wires.",
                True,
            ),
            (
                "Compound microscope",
                "MC",
                "Microscopy",
                "Applied Science Lab",
                10,
                2,
                "Optical microscopes for introductory slide observation.",
                True,
            ),
            (
                "Bench centrifuge",
                "CF",
                "Laboratory equipment",
                "Applied Science Lab",
                4,
                1,
                "Bench units for supervised sample preparation exercises.",
                True,
            ),
            (
                "Micropipette set",
                "MP",
                "Measurement",
                "Applied Science Lab",
                24,
                6,
                "Adjustable pipettes, supplied as calibrated sets.",
                True,
            ),
            (
                "Display monitor",
                "DM",
                "Computers",
                "Computer Lab B",
                0,
                3,
                "Replacement monitors currently out of stock; new delivery is awaited.",
                True,
            ),
            (
                "Soldering station",
                "SS",
                "Tools",
                "Innovation Lab",
                6,
                2,
                "Temperature-controlled stations for supervised circuit assembly.",
                True,
            ),
            (
                "Legacy laser printer",
                "LP",
                "Peripherals",
                "Equipment Store",
                0,
                0,
                "Retired printer retained for historical records; unavailable for issue.",
                False,
            ),
        ]
        items = {}
        for name, key, category, lab, quantity, reorder, description, active in equipment:
            item, created = Item.objects.get_or_create(
                asset_code=f"DEMO-{key}-01",
                defaults={
                    "name": name,
                    "category": category,
                    "laboratory": lab,
                    "reorder_level": reorder,
                    "description": description,
                },
            )
            if created:
                if quantity:
                    adjust_stock(
                        item_id=item.pk,
                        delta=quantity,
                        actor=users["admin"],
                        reason="Initial sample inventory for the laboratory",
                    )
                if not active:
                    item.is_active = False
                    item.save(update_fields=["is_active"])
            elif not item.description:
                # Fill only the empty descriptions in the older minimal demo set.
                item.description = description
                item.save(update_fields=["description"])
            items[key] = item
        return items

    def seed_requests(self, users, items):
        # Approvals and returns use the real services so stock, audit and inboxes agree.
        scenarios = [
            ("faculty", "AR", 3, "Local demo: embedded systems practical", "pending", 0, 1, ""),
            (
                "faculty",
                "MM",
                4,
                "Demo: circuit measurement practical",
                "approved",
                1,
                6,
                "Approved for the circuit measurement session; return all meters after use.",
            ),
            (
                "faculty",
                "OS",
                2,
                "Demo: signal analysis workshop",
                "approved",
                0,
                4,
                "Two oscilloscopes issued with probes. Keep them in the supervised lab.",
            ),
            (
                "faculty",
                "MP",
                6,
                "Demo: completed sample preparation class",
                "approved",
                6,
                10,
                "Issued for the sample preparation class. All sets have been checked back in.",
            ),
            (
                "faculty",
                "HD",
                8,
                "Demo: classroom display adapter request",
                "rejected",
                0,
                3,
                "Only four adapters are available. Submit a smaller request or wait for restocking.",
            ),
            (
                "faculty",
                None,
                2,
                "Demo: propose thermal imaging cameras",
                "pending",
                0,
                2,
                "Thermal imaging camera",
            ),
            (
                "faculty",
                None,
                1,
                "Demo: approved 3D printing proposal",
                "approved",
                0,
                8,
                "3D printer",
            ),
            (
                "faculty2",
                "MC",
                3,
                "Demo: microscopy induction session",
                "approved",
                1,
                5,
                "Approved for the microscopy induction session.",
            ),
            ("faculty2", "CF", 1, "Demo: centrifuge demonstration", "pending", 0, 1, ""),
            (
                "technician",
                "SS",
                2,
                "Demo: maintenance bench soldering stations",
                "approved",
                0,
                3,
                "Issued to the maintenance bench for scheduled repair work.",
            ),
            (
                "technician",
                "NS",
                1,
                "Demo: network practice room spare switch",
                "pending",
                0,
                0,
                "",
            ),
            (
                "faculty2",
                "DM",
                2,
                "Demo: replace classroom monitors",
                "rejected",
                0,
                2,
                "Replacement monitors are out of stock. The request can be resubmitted after delivery.",
            ),
        ]
        for key, item_key, quantity, purpose, status, returned, days, note in scenarios:
            row, created = StockRequest.objects.get_or_create(
                requester=users[key],
                purpose=purpose,
                defaults={
                    "item": items.get(item_key),
                    "quantity": quantity,
                    "equipment_needed": note if item_key is None else "",
                },
            )
            if not created:
                continue
            self.timestamp(row, days)
            self.activity(users[key], f"Submitted stock request #{row.pk}: {row.equipment_label}.")
            if status == "pending":
                self.notification(
                    users["admin"],
                    f"Request #{row.pk}: {row.equipment_label} is waiting for your review.",
                    "request",
                    row.pk,
                )
            else:
                review_request(
                    request_id=row.pk,
                    actor=users["admin"],
                    decision=status,
                    note=note
                    if item_key
                    else "Proposal approved for procurement review; no stock has been issued.",
                )
                if returned:
                    return_stock(
                        request_id=row.pk,
                        quantity=returned,
                        actor=users["technician"],
                        reason="Sample return: checked, cleaned and received in working condition.",
                        operation_id=uuid4(),
                    )
                row.refresh_from_db()
                if row.outstanding_quantity:
                    self.notification(
                        users["technician"],
                        f"Request #{row.pk}: {row.outstanding_quantity} issued unit(s) of {row.equipment_label} await return.",
                        "request",
                        row.pk,
                    )

    def seed_complaints(self, users, items):
        scenarios = [
            (
                "faculty",
                "PC",
                "Local demo: workstation will not boot",
                "hardware",
                "high",
                "open",
                "technician",
                2,
                "Workstation 12 does not start. Check the power supply before the next practical.",
                "",
            ),
            (
                "faculty",
                "NS",
                "Demo: intermittent network connection",
                "hardware",
                "high",
                "in_progress",
                "technician",
                3,
                "Ports 3 and 4 disconnect during network exercises. Replacement cables are being tested.",
                "",
            ),
            (
                "faculty",
                "PC",
                "Demo: IDE cannot open student projects",
                "software",
                "medium",
                "resolved",
                "technician",
                7,
                "The programming IDE fails to load projects on workstation 8.",
                "Reinstalled the IDE, repaired file permissions and verified a sample project with faculty.",
            ),
            (
                "faculty",
                "OS",
                "Demo: oscilloscope probe calibration",
                "hardware",
                "low",
                "resolved",
                "technician",
                6,
                "Probe compensation needs checking before the signal analysis class.",
                "Calibrated both probes against the reference signal and recorded a successful check.",
            ),
            (
                "faculty",
                "HD",
                "Demo: loose display adapter connector",
                "hardware",
                "medium",
                "open",
                None,
                1,
                "The adapter loses its display signal when the connector moves.",
                "",
            ),
            (
                "faculty2",
                "MC",
                "Demo: microscope focus knob sticks",
                "hardware",
                "medium",
                "in_progress",
                "technician2",
                4,
                "The coarse focus knob on microscope 3 is difficult to turn.",
                "",
            ),
            (
                "faculty2",
                "CF",
                "Demo: centrifuge lid warning",
                "hardware",
                "high",
                "open",
                "technician",
                1,
                "The unit reports an open lid even after the lid is secured. Keep it out of use pending inspection.",
                "",
            ),
            (
                "technician",
                "SS",
                "Demo: soldering station safety check",
                "hardware",
                "low",
                "resolved",
                "technician2",
                5,
                "Inspect the damaged mains cable before returning the station to service.",
                "Replaced the mains cable and completed the electrical safety checks.",
            ),
        ]
        for (
            key,
            item_key,
            subject,
            kind,
            priority,
            status,
            assigned,
            days,
            description,
            resolution,
        ) in scenarios:
            item = items[item_key]
            row, created = Complaint.objects.get_or_create(
                reporter=users[key],
                subject=subject,
                defaults={
                    "item": item,
                    "laboratory": item.laboratory,
                    "complaint_type": kind,
                    "priority": priority,
                    "status": status,
                    "assigned_to": users.get(assigned),
                    "description": description,
                    "resolution": resolution,
                },
            )
            if not created:
                continue
            self.timestamp(row, days)
            self.activity(users[key], f"Reported complaint #{row.pk}: {row.subject}.")
            self.notification(
                users["admin"],
                f"Complaint #{row.pk}: {row.subject} - {row.get_status_display().lower()}.",
                "complaint",
                row.pk,
                read=status == "resolved",
            )
            if row.assigned_to:
                self.notification(
                    row.assigned_to,
                    f"Assigned complaint #{row.pk}: {row.subject}.",
                    "complaint",
                    row.pk,
                    read=status == "resolved",
                )
            if status != "open":
                self.notification(
                    users[key],
                    f"Your complaint #{row.pk}: {row.subject} is {row.get_status_display().lower()}.",
                    "complaint",
                    row.pk,
                    read=status == "resolved",
                )
                self.activity(
                    users[assigned], f"Updated complaint #{row.pk} to {row.get_status_display()}."
                )

    def seed_messages(self, users):
        for user in users.values():
            if not user.is_active:
                continue
            self.notification(
                user,
                "Your sample account is ready. Review your name and department in My Profile.",
                "account",
                read=True,
            )
            self.notification(
                user,
                "Welcome to the sample lab workspace. Explore requests, repairs and equipment records using your role.",
                "account",
            )
        # The older minimal seed may already have created this assignment.
        existing = Complaint.objects.filter(
            reporter=users["faculty"], subject="Local demo: workstation will not boot"
        ).first()
        if existing and existing.assigned_to_id == users["technician"].pk:
            self.notification(
                users["technician"],
                f"Assigned complaint #{existing.pk}: {existing.subject}.",
                "complaint",
                existing.pk,
                read=existing.status == "resolved",
            )
        for name, email, message, days in [
            (
                "Casey Sample",
                "faculty2@lidms.example",
                "Sample inquiry: Can we reserve the Applied Science Lab for Friday's microscopy induction?",
                2,
            ),
            (
                "Sam Sample",
                "pending@lidms.example",
                "Sample inquiry: I have requested a faculty account. Please review access for Applied Sciences.",
                1,
            ),
        ]:
            row, created = ContactMessage.objects.get_or_create(
                email=email, message=message, defaults={"name": name}
            )
            if created:
                self.timestamp(row, days)
