from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .backends import EmailOrUsernameBackend
from .models import (
    Activity,
    Complaint,
    ContactMessage,
    Item,
    Notification,
    Profile,
    StockMovement,
    StockRequest,
)
from .services import adjust_stock, return_stock, review_request
from .views import scoped_complaints, scoped_requests

User = get_user_model()
PASSWORD = "Local-tests-only-73!WmQ"


@override_settings(DEBUG=True, ON_VERCEL=False)
class DemoSeedTests(TestCase):
    @override_settings(DEBUG=False, DEMO_MODE=False)
    def test_hosted_seed_requires_both_explicit_safeguards(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", allow_hosted_demo=True, stdout=StringIO())
        with override_settings(DEMO_MODE=True), self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())

    @override_settings(DEBUG=False, DEMO_MODE=True)
    def test_explicit_hosted_demo_can_seed_without_debug(self):
        with patch.dict("os.environ", {"LIDMS_DEMO_PASSWORD": PASSWORD}):
            call_command("seed_demo", allow_hosted_demo=True, stdout=StringIO())
        self.assertEqual(Item.objects.count(), 12)

    def seed(self):
        with patch.dict("os.environ", {"LIDMS_DEMO_PASSWORD": PASSWORD}):
            call_command("seed_demo", stdout=StringIO())

    def test_connected_samples_balance_and_reruns_preserve_visitor_changes(self):
        self.seed()
        self.assertEqual(Item.objects.count(), 12)
        self.assertEqual(User.objects.count(), 6)
        self.assertTrue(User.objects.filter(is_active=False).exists())
        self.assertTrue(Item.objects.filter(quantity=0, is_active=True).exists())
        self.assertTrue(Item.objects.filter(is_active=False).exists())
        self.assertEqual(
            set(StockRequest.objects.values_list("status", flat=True)),
            {"pending", "approved", "rejected"},
        )
        self.assertEqual(
            set(Complaint.objects.values_list("status", flat=True)),
            {"open", "in_progress", "resolved"},
        )
        self.assertTrue(StockRequest.objects.filter(quantity_returned__gt=0).exists())
        self.assertTrue(StockRequest.objects.filter(status="approved", item=None).exists())
        self.assertFalse(Complaint.objects.filter(status="resolved", resolution="").exists())
        for item in Item.objects.all():
            self.assertEqual(
                item.quantity, item.movements.aggregate(total=Sum("delta"))["total"] or 0
            )
        for role in ("admin", "faculty", "technician"):
            inbox = Notification.objects.filter(recipient__username=f"demo.{role}")
            self.assertTrue(inbox.filter(is_read=False).exists())
            self.assertTrue(inbox.filter(is_read=True).exists())

        admin = User.objects.get(username="demo.admin")
        admin.set_password("Visitor-changed-password-724!")
        admin.save()
        request = StockRequest.objects.filter(status="pending", item__isnull=False).first()
        review_request(request_id=request.pk, actor=admin, decision="approved")
        notice = Notification.objects.filter(is_read=False).first()
        notice.is_read = True
        notice.save()
        models = (
            User,
            Profile,
            Item,
            StockRequest,
            Complaint,
            StockMovement,
            Activity,
            Notification,
            ContactMessage,
        )
        counts = {model: model.objects.count() for model in models}
        quantities = dict(Item.objects.values_list("pk", "quantity"))
        self.seed()
        self.assertEqual(counts, {model: model.objects.count() for model in models})
        self.assertEqual(quantities, dict(Item.objects.values_list("pk", "quantity")))
        notice.refresh_from_db()
        request.refresh_from_db()
        admin.refresh_from_db()
        self.assertTrue(notice.is_read)
        self.assertEqual(request.status, "approved")
        self.assertTrue(admin.check_password("Visitor-changed-password-724!"))


@override_settings(
    SHOW_DEMO_ACCOUNTS=True,
    DEMO_PASSWORD=PASSWORD,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
class DemoLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for role in ("admin", "faculty", "technician"):
            user = User.objects.create_user(
                username=f"demo.{role}",
                email=f"{role}@lidms.example",
                password=PASSWORD,
            )
            Profile.objects.create(user=user, role=role)

    def test_displayed_accounts_authenticate_with_the_published_details(self):
        response = self.client.get(reverse("login"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(len(response.context["demo_accounts"]), 3)
        self.assertContains(response, PASSWORD)
        for account in response.context["demo_accounts"]:
            self.assertTrue(Client().login(username=account["email"], password=PASSWORD))

    def test_disabled_or_unconfigured_demo_does_not_publish_credentials(self):
        for settings in ({"SHOW_DEMO_ACCOUNTS": False}, {"DEMO_PASSWORD": ""}):
            with self.subTest(settings=settings), override_settings(**settings):
                response = self.client.get(reverse("login"))
                self.assertNotContains(response, 'id="demo-dialog"')
                self.assertNotContains(response, PASSWORD)

    def test_inactive_and_wrong_role_accounts_are_not_advertised(self):
        User.objects.filter(username="demo.admin").update(is_active=False)
        Profile.objects.filter(user__username="demo.faculty").update(role="admin")
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, "admin@lidms.example")
        self.assertNotContains(response, "faculty@lidms.example")
        self.assertContains(response, "technician@lidms.example")


@override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)
class WorkflowTests(TestCase):
    def test_email_login_uses_bounded_lookup_and_preserves_ambiguity_rejection(self):
        backend = EmailOrUsernameBackend()
        with self.assertNumQueries(2):
            user = backend.authenticate(None, username="FACULTY@example.test", password=PASSWORD)
        self.assertEqual(user.pk, self.faculty.pk)
        User.objects.create_user(
            username="duplicate-email", email=self.faculty.email, password=PASSWORD
        )
        with self.assertNumQueries(1):
            self.assertIsNone(
                backend.authenticate(None, username=self.faculty.email, password=PASSWORD)
            )

    def test_scoped_lists_load_profile_fields_without_per_row_queries(self):
        requests = scoped_requests(self.admin)
        complaints = scoped_complaints(self.admin)
        with self.assertNumQueries(1):
            self.assertEqual([row.requester.profile.role for row in requests], ["faculty"])
        with self.assertNumQueries(1):
            self.assertEqual([row.reporter.profile.role for row in complaints], ["faculty"])

    def test_technician_progress_counts_assigned_jobs_not_all_self_reported_issues(self):
        Complaint.objects.create(
            reporter=self.technician,
            subject="Own issue awaiting assignment",
            laboratory="Lab B",
            description="Awaiting technician allocation",
            status="in_progress",
        )
        Complaint.objects.create(
            reporter=self.other,
            assigned_to=self.technician,
            subject="Completed assigned job",
            laboratory="Lab B",
            description="Repair example",
            status="resolved",
            resolution="Cable replaced and tested.",
        )
        self.client.force_login(self.technician)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["complaint_total"], 2)
        counts = {stage["status"]: stage["count"] for stage in response.context["breakdown"]}
        self.assertEqual(counts, {"open": 1, "in_progress": 0, "resolved": 1})

    def test_profile_name_updates_header_without_changing_account_access(self):
        self.client.force_login(self.faculty)
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Casey",
                "last_name": "Patel",
                "department": "Electronics",
                "phone": "9876543210",
                "role": "admin",
                "email": "changed@example.test",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.get_full_name(), "Casey Patel")
        self.assertEqual(self.faculty.profile.department, "Electronics")
        self.assertEqual(self.faculty.profile.role, "faculty")
        self.assertEqual(self.faculty.email, "faculty@example.test")
        self.assertContains(response, "Account menu for Casey Patel")
        self.assertEqual(response.context["account_initials"], "CP")

    @classmethod
    def setUpTestData(cls):
        cls.admin = cls.make_user("admin", "admin")
        cls.faculty = cls.make_user("faculty", "faculty")
        cls.other = cls.make_user("other", "faculty")
        cls.technician = cls.make_user("technician", "technician")
        cls.item = Item.objects.create(
            name="Multimeter",
            asset_code="MM-1",
            category="Instruments",
            laboratory="Lab A",
            quantity=10,
        )
        cls.stock_request = StockRequest.objects.create(
            requester=cls.faculty, item=cls.item, quantity=3, purpose="Practical session"
        )
        cls.complaint = Complaint.objects.create(
            reporter=cls.faculty,
            subject="Damaged probe",
            laboratory="Lab A",
            description="Probe needs replacement",
            assigned_to=cls.technician,
        )

    @classmethod
    def make_user(cls, username, role):
        user = User.objects.create_user(
            username=username, password=PASSWORD, email=f"{username}@example.test"
        )
        Profile.objects.create(user=user, role=role)
        return user

    def sign_in(self, user):
        self.client.force_login(user)

    def test_private_pages_require_login(self):
        for name in [
            "dashboard",
            "inventory",
            "requests",
            "complaints",
            "reports",
            "users",
            "profile",
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_every_workspace_page_renders_for_all_roles(self):
        names = [
            "dashboard",
            "inventory",
            "requests",
            "complaints",
            "reports",
            "profile",
            "request_create",
            "complaint_create",
            "password_change",
            "loans",
            "notifications",
        ]
        for user in [self.admin, self.faculty, self.technician]:
            self.sign_in(user)
            for name in names:
                with self.subTest(role=user.username, page=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.sign_in(self.admin)
        for name in ["users", "item_create"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name, pk in [
            ("stock_adjust", self.item.pk),
            ("item_edit", self.item.pk),
            ("request_review", self.stock_request.pk),
            ("user_access", self.faculty.pk),
            ("complaint_detail", self.complaint.pk),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 200)

    def test_public_pages_render(self):
        for name in ["home", "login", "register", "help"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_project_navigation_and_robot_brand_are_present(self):
        self.sign_in(self.admin)
        response = self.client.get(reverse("dashboard"))
        for label in [
            "Dashboard",
            "New Registration",
            "Stock Manager",
            "User Details",
            "Post Complaint",
            "Post Stock Request",
            "Reports",
            "FAQs",
            "Contact Us",
        ]:
            self.assertContains(response, label)
        self.assertContains(response, "Redmask/logo.png")
        for copied_content in [
            "Live status",
            "Today’s activity",
            "People &amp; access",
            "figma/logo.svg",
            "Tasks",
        ]:
            self.assertNotContains(response, copied_content)

    def test_home_restores_original_sections_without_team_names(self):
        response = self.client.get(reverse("home"))
        self.assertContains(
            response,
            "<title>LIDMS | Lab Information Digitalization and Management Systems</title>",
            html=True,
        )
        for content in [
            "Stock Management",
            "Complaints &amp; repairs",
            "Reports",
            'id="about"',
            'id="services"',
            'id="roles"',
            'id="faq"',
        ]:
            self.assertContains(response, content)
        for removed_content in ['id="contact"', 'name="email"', "Get in touch", "AITR, Indore"]:
            self.assertNotContains(response, removed_content)
        for role in ["Administrator", "Faculty", "Technician"]:
            self.assertContains(response, role)
        self.assertContains(response, "project/dashboard-admin.jpg")
        self.assertNotContains(response, "https://github.com")

    def test_original_email_login_works(self):
        response = self.client.post(
            reverse("login"), {"username": self.faculty.email.upper(), "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_administrator_can_register_user_with_original_fields(self):
        self.sign_in(self.admin)
        response = self.client.post(
            reverse("new_registration"),
            {
                "first_name": "Test",
                "last_name": "Person",
                "department": "Science",
                "role": "technician",
                "email": "registered@example.test",
                "phone": "9876543210",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("users"))
        user = User.objects.get(email="registered@example.test")
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.profile.role, "technician")
        self.assertEqual(user.profile.phone, "9876543210")

    def test_new_equipment_request_preserves_free_text_without_inventing_stock(self):
        self.sign_in(self.faculty)
        response = self.client.post(
            reverse("request_create"),
            {"equipment_needed": "A new spectrometer", "purpose": "Required for new experiments"},
        )
        self.assertRedirects(response, reverse("requests"))
        created = StockRequest.objects.latest("pk")
        self.assertIsNone(created.item)
        self.assertEqual(created.equipment_needed, "A new spectrometer")
        review_request(request_id=created.pk, actor=self.admin, decision="approved")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.assertFalse(StockMovement.objects.filter(stock_request=created).exists())

    def test_original_complaint_type_is_saved(self):
        self.sign_in(self.faculty)
        response = self.client.post(
            reverse("complaint_create"),
            {
                "subject": "Software not responding",
                "priority": "high",
                "complaint_type": "software",
                "description": "The lab application freezes.",
            },
        )
        self.assertRedirects(response, reverse("complaints"))
        self.assertEqual(Complaint.objects.latest("pk").complaint_type, "software")

    def test_contact_messages_persist_and_are_private_to_administrators(self):
        response = self.client.post(
            reverse("contact"),
            {
                "name": "Visitor",
                "email": "visitor@example.test",
                "message": "Unique private lab inquiry",
            },
        )
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.sign_in(self.faculty)
        self.assertNotContains(self.client.get(reverse("contact")), "Unique private lab inquiry")
        self.sign_in(self.admin)
        self.assertContains(self.client.get(reverse("contact")), "Unique private lab inquiry")

    def test_original_stock_manager_and_report_pages_render(self):
        self.sign_in(self.faculty)
        for url in [
            reverse("stock_manager"),
            reverse("faq"),
            reverse("contact"),
            reverse("reports") + "?view=stock",
            reverse("reports") + "?view=complaints",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_legacy_navigation_redirects_to_permission_checked_pages(self):
        self.sign_in(self.faculty)
        self.assertRedirects(self.client.get("/faculty/poststkreq/"), reverse("request_create"))
        self.assertRedirects(
            self.client.get("/myadmin/userdetails/"), reverse("users"), target_status_code=403
        )

    def test_complaint_detail_renders_without_assigned_technician(self):
        self.complaint.assigned_to = None
        self.complaint.save()
        self.sign_in(self.faculty)
        self.assertContains(
            self.client.get(reverse("complaint_detail", args=[self.complaint.pk])),
            "Awaiting assignment",
        )

    def test_registration_creates_inactive_faculty_with_hashed_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new-person",
                "first_name": "New",
                "last_name": "Person",
                "email": "new@example.test",
                "department": "Science",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "role": "admin",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="new-person")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(user.profile.role, "faculty")
        self.assertFalse(self.client.login(username=user.username, password=PASSWORD))

    def test_admin_approves_account_and_assigns_role(self):
        self.other.is_active = False
        self.other.save()
        self.sign_in(self.admin)
        response = self.client.post(
            reverse("user_access", args=[self.other.pk]), {"role": "technician", "is_active": "on"}
        )
        self.assertRedirects(response, reverse("users"))
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_active)
        self.assertEqual(self.other.profile.role, "technician")

    def test_faculty_cannot_manage_accounts_or_stock(self):
        self.sign_in(self.faculty)
        for name, args in [
            ("users", []),
            ("item_create", []),
            ("stock_adjust", [self.item.pk]),
            ("request_review", [self.stock_request.pk]),
            ("user_access", [self.other.pk]),
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.client.post(reverse(name, args=args), {}).status_code, 403)

    def test_admin_cannot_remove_own_access(self):
        self.sign_in(self.admin)
        response = self.client.post(
            reverse("user_access", args=[self.admin.pk]), {"role": "faculty"}
        )
        self.assertContains(response, "cannot remove your own")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.profile.role, "admin")

    def test_approval_deducts_stock_exactly_once(self):
        review_request(request_id=self.stock_request.pk, actor=self.admin, decision="approved")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)
        self.assertEqual(StockMovement.objects.get(stock_request=self.stock_request).delta, -3)
        with self.assertRaises(ValidationError):
            review_request(request_id=self.stock_request.pk, actor=self.admin, decision="approved")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_insufficient_stock_rolls_back_request_and_audit(self):
        self.stock_request.quantity = 50
        self.stock_request.save()
        with self.assertRaises(ValidationError):
            review_request(request_id=self.stock_request.pk, actor=self.admin, decision="approved")
        self.stock_request.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.stock_request.status, "pending")
        self.assertEqual(self.item.quantity, 10)
        self.assertFalse(StockMovement.objects.exists())
        self.assertFalse(Activity.objects.exists())

    def test_rejection_does_not_change_stock(self):
        review_request(
            request_id=self.stock_request.pk,
            actor=self.admin,
            decision="rejected",
            note="Not required",
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.assertFalse(StockMovement.objects.exists())

    def test_archived_item_cannot_be_issued(self):
        self.item.is_active = False
        self.item.save()
        with self.assertRaises(ValidationError):
            review_request(request_id=self.stock_request.pk, actor=self.admin, decision="approved")

    def test_stock_adjustment_validates_and_records_balance(self):
        adjust_stock(
            item_id=self.item.pk, actor=self.technician, delta=4, reason="Received delivery"
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 14)
        self.assertEqual(StockMovement.objects.get().balance, 14)
        for delta in [0, -100]:
            with self.assertRaises(ValidationError):
                adjust_stock(
                    item_id=self.item.pk, actor=self.technician, delta=delta, reason="Invalid"
                )
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_stock_form_creates_pending_request_and_rejects_zero(self):
        self.sign_in(self.faculty)
        payload = {"item": self.item.pk, "quantity": 0, "purpose": "Test"}
        response = self.client.post(reverse("request_create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StockRequest.objects.count(), 1)
        payload["quantity"] = 2
        payload["status"] = "approved"
        payload["requester"] = self.other.pk
        self.assertRedirects(
            self.client.post(reverse("request_create"), payload), reverse("requests")
        )
        created = StockRequest.objects.latest("pk")
        self.assertEqual(created.requester, self.faculty)
        self.assertEqual(created.status, "pending")

    def test_request_review_endpoint_handles_insufficient_stock(self):
        self.stock_request.quantity = 100
        self.stock_request.save()
        self.sign_in(self.admin)
        response = self.client.post(
            reverse("request_review", args=[self.stock_request.pk]), {"decision": "approved"}
        )
        self.assertContains(response, "insufficient")
        self.stock_request.refresh_from_db()
        self.assertEqual(self.stock_request.status, "pending")

    def test_complaint_creation_uses_authenticated_reporter(self):
        self.sign_in(self.faculty)
        response = self.client.post(
            reverse("complaint_create"),
            {
                "subject": "Broken keyboard",
                "laboratory": "Lab A",
                "priority": "high",
                "description": "Keys not responding",
                "reporter": self.other.pk,
            },
        )
        self.assertRedirects(response, reverse("complaints"))
        self.assertEqual(Complaint.objects.latest("pk").reporter, self.faculty)

    def test_complaint_visibility_and_exports_are_scoped(self):
        self.sign_in(self.other)
        self.assertNotContains(self.client.get(reverse("complaints")), "Damaged probe")
        self.assertEqual(
            self.client.get(reverse("complaint_detail", args=[self.complaint.pk])).status_code, 404
        )
        self.assertNotIn(
            b"Damaged probe", self.client.get(reverse("reports") + "?export=complaints").content
        )
        self.assertNotIn(b"MM-1", self.client.get(reverse("reports") + "?export=requests").content)
        self.sign_in(self.technician)
        self.assertContains(self.client.get(reverse("complaints")), "Damaged probe")

    def test_only_assigned_technician_can_update_and_resolution_is_required(self):
        url = reverse("complaint_detail", args=[self.complaint.pk])
        self.sign_in(self.faculty)
        self.assertEqual(
            self.client.post(url, {"status": "resolved", "resolution": "Done"}).status_code, 403
        )
        self.sign_in(self.technician)
        response = self.client.post(url, {"status": "resolved", "resolution": ""})
        self.assertContains(response, "Describe the resolution")
        self.assertRedirects(
            self.client.post(url, {"status": "resolved", "resolution": "Probe replaced"}), url
        )
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, "resolved")
        self.assertEqual(self.complaint.assigned_to, self.technician)

    def test_csv_formula_injection_is_neutralized(self):
        self.item.name = "=HYPERLINK(1)"
        self.item.save()
        self.sign_in(self.admin)
        response = self.client.get(reverse("reports") + "?export=inventory")
        self.assertIn(b"'=HYPERLINK(1)", response.content)

    def test_logout_requires_post_and_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.faculty)
        self.assertEqual(strict.get(reverse("logout")).status_code, 405)
        self.assertEqual(strict.post(reverse("logout")).status_code, 403)
        strict.get(reverse("dashboard"))
        token = strict.cookies["csrftoken"].value
        self.assertEqual(
            strict.post(reverse("logout"), {"csrfmiddlewaretoken": token}).status_code, 302
        )

    def test_throttling_blocks_even_valid_password_until_window_expires(self):
        for _ in range(8):
            self.client.post(reverse("login"), {"username": "faculty", "password": "incorrect"})
        response = self.client.post(reverse("login"), {"username": "faculty", "password": PASSWORD})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_external_redirect(self):
        response = self.client.post(
            reverse("login"),
            {"username": "faculty", "password": PASSWORD, "next": "https://attacker.example"},
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_item_edit_cannot_overwrite_quantity(self):
        self.sign_in(self.technician)
        self.client.post(
            reverse("item_edit", args=[self.item.pk]),
            {
                "name": "Multimeter",
                "asset_code": "MM-1",
                "category": "Instruments",
                "laboratory": "Lab A",
                "reorder_level": 2,
                "is_active": "on",
                "quantity": 1000,
            },
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    @override_settings(DEBUG=False)
    def test_demo_command_cannot_run_in_production(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())

    def approve_issue(self):
        return review_request(
            request_id=self.stock_request.pk, actor=self.admin, decision="approved"
        )

    def test_partial_and_complete_returns_restore_exact_stock(self):
        self.approve_issue()
        for quantity, expected in [(1, 8), (2, 10)]:
            return_stock(
                request_id=self.stock_request.pk,
                quantity=quantity,
                actor=self.technician,
                reason="Checked and working",
                operation_id=uuid4(),
            )
            self.item.refresh_from_db()
            self.assertEqual(self.item.quantity, expected)
        self.stock_request.refresh_from_db()
        self.assertEqual(self.stock_request.outstanding_quantity, 0)
        self.assertEqual(self.stock_request.movements.count(), 3)

    def test_return_retries_are_idempotent(self):
        self.approve_issue()
        operation = uuid4()
        kwargs = dict(
            request_id=self.stock_request.pk,
            quantity=1,
            actor=self.technician,
            reason="Working",
            operation_id=operation,
        )
        first = return_stock(**kwargs)
        self.assertEqual(return_stock(**kwargs).pk, first.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 8)
        self.assertEqual(StockMovement.objects.filter(operation_id=operation).count(), 1)
        with self.assertRaises(ValidationError):
            return_stock(**{**kwargs, "quantity": 2})

    def test_invalid_returns_preserve_balance(self):
        with self.assertRaises(ValidationError):
            return_stock(
                request_id=self.stock_request.pk,
                quantity=1,
                actor=self.admin,
                reason="Not issued",
                operation_id=uuid4(),
            )
        self.approve_issue()
        for amount in [0, -1, 4]:
            with self.assertRaises(ValidationError):
                return_stock(
                    request_id=self.stock_request.pk,
                    quantity=amount,
                    actor=self.admin,
                    reason="Invalid",
                    operation_id=uuid4(),
                )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)

    def test_faculty_cannot_record_returns_or_read_other_requests(self):
        self.approve_issue()
        self.sign_in(self.faculty)
        self.assertEqual(
            self.client.get(reverse("equipment_return", args=[self.stock_request.pk])).status_code,
            403,
        )
        self.sign_in(self.other)
        self.assertEqual(
            self.client.get(reverse("request_detail", args=[self.stock_request.pk])).status_code,
            404,
        )
        self.assertEqual(list(self.client.get(reverse("loans")).context["page_obj"]), [])

    def test_request_existing_equipment_ignores_spoofed_identity_and_name(self):
        self.sign_in(self.faculty)
        response = self.client.post(
            reverse("item_request", args=[self.item.pk]),
            {
                "item": self.item.pk,
                "quantity": 2,
                "equipment_needed": "Spoofed",
                "purpose": "Lab practical",
                "requester": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        record = StockRequest.objects.latest("pk")
        self.assertEqual(record.requester, self.faculty)
        self.assertEqual(record.equipment_needed, self.item.name)
        self.assertEqual(record.quantity, 2)
        response = self.client.post(
            reverse("item_request", args=[self.item.pk]), {"quantity": 2, "purpose": "Missing item"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StockRequest.objects.count(), 2)

    def test_dashboard_metrics_are_scoped_to_role(self):
        StockRequest.objects.create(
            requester=self.other,
            equipment_needed="Private equipment",
            quantity=1,
            purpose="Other member",
        )
        self.sign_in(self.faculty)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["metrics"][0]["value"], 1)
        self.assertNotContains(response, "Private equipment")
        self.sign_in(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard")).context["metrics"][0]["value"], 2)
        self.sign_in(self.technician)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["metrics"][0]["value"], 1)
        self.assertEqual(response.context["metrics"][1]["value"], 0)

    def test_request_decision_and_return_notify_borrower_only(self):
        self.approve_issue()
        self.assertEqual(Notification.objects.count(), 1)
        notice = Notification.objects.get()
        self.assertEqual(notice.recipient, self.faculty)
        self.assertEqual(notice.target_url, reverse("request_detail", args=[self.stock_request.pk]))
        return_stock(
            request_id=self.stock_request.pk,
            quantity=1,
            actor=self.technician,
            reason="Working",
            operation_id=uuid4(),
        )
        self.assertEqual(self.faculty.notifications.count(), 2)

    def test_notifications_are_private_and_reads_require_post(self):
        self.approve_issue()
        notice = Notification.objects.get()
        self.sign_in(self.other)
        self.assertNotContains(self.client.get(reverse("notifications")), notice.message)
        self.assertEqual(
            self.client.post(reverse("notification_read", args=[notice.pk])).status_code, 404
        )
        self.sign_in(self.faculty)
        self.assertEqual(
            self.client.get(reverse("notification_read", args=[notice.pk])).status_code, 405
        )
        self.client.post(reverse("notification_read", args=[notice.pk]))
        notice.refresh_from_db()
        self.assertTrue(notice.is_read)

    def test_assignment_and_resolution_notify_the_relevant_users(self):
        self.complaint.assigned_to = None
        self.complaint.save()
        self.sign_in(self.admin)
        self.client.post(
            reverse("complaint_detail", args=[self.complaint.pk]),
            {"assigned_to": self.technician.pk, "status": "in_progress", "resolution": ""},
        )
        self.assertEqual(self.technician.notifications.count(), 1)
        self.assertEqual(self.faculty.notifications.count(), 1)
        self.sign_in(self.technician)
        self.client.post(
            reverse("complaint_detail", args=[self.complaint.pk]),
            {"status": "resolved", "resolution": "Replaced probe"},
        )
        self.assertEqual(self.faculty.notifications.count(), 2)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.assigned_to, self.technician)

    def test_archived_equipment_can_be_returned(self):
        self.approve_issue()
        self.item.is_active = False
        self.item.save(update_fields=["is_active"])
        return_stock(
            request_id=self.stock_request.pk,
            quantity=3,
            actor=self.admin,
            reason="Retired after inspection",
            operation_id=uuid4(),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.assertFalse(self.item.is_active)
