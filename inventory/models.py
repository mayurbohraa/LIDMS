from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        FACULTY = "faculty", "Faculty"
        TECHNICIAN = "technician", "Technician"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=Role, default=Role.FACULTY)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Item(models.Model):
    name = models.CharField(max_length=150)
    asset_code = models.CharField(max_length=40, unique=True)
    category = models.CharField(max_length=80)
    laboratory = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=0), name="item_nonnegative_quantity")
        ]

    @property
    def low_stock(self):
        return self.quantity <= self.reorder_level

    def __str__(self):
        return f"{self.name} · {self.asset_code}"


class StockRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_requests"
    )
    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="requests", null=True, blank=True
    )
    equipment_needed = models.CharField(max_length=150, blank=True)
    quantity = models.PositiveIntegerField()
    quantity_returned = models.PositiveIntegerField(default=0)
    purpose = models.TextField(max_length=2000)
    status = models.CharField(max_length=15, choices=Status, default=Status.PENDING)
    decision_note = models.CharField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def equipment_label(self):
        return self.equipment_needed or (self.item.name if self.item_id else "Equipment request")

    @property
    def outstanding_quantity(self):
        return (
            self.quantity - self.quantity_returned
            if self.status == self.Status.APPROVED and self.item_id
            else 0
        )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="request_positive_quantity"),
            models.CheckConstraint(
                condition=Q(quantity_returned__lte=models.F("quantity")),
                name="request_returns_within_issue",
            ),
        ]


class Complaint(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="complaints"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT, null=True, blank=True)
    subject = models.CharField(max_length=150)
    complaint_type = models.CharField(
        max_length=20,
        choices=[("hardware", "Hardware"), ("software", "Software")],
        default="hardware",
    )
    laboratory = models.CharField(max_length=100)
    description = models.TextField(max_length=4000)
    priority = models.CharField(max_length=10, choices=Priority, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status, default=Status.OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_complaints",
    )
    resolution = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class StockMovement(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    delta = models.IntegerField()
    balance = models.PositiveIntegerField()
    reason = models.CharField(max_length=500)
    stock_request = models.ForeignKey(
        StockRequest, on_delete=models.PROTECT, null=True, blank=True, related_name="movements"
    )
    operation_id = models.UUIDField(unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["stock_request"],
                condition=Q(stock_request__isnull=False, delta__lt=0),
                name="one_issue_per_request",
            )
        ]


class Activity(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LoginAttempt(models.Model):
    """Shared database state keeps login throttling effective across function instances."""

    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField()


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    message = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=300)
    resource = models.CharField(
        max_length=20,
        choices=[("request", "Stock request"), ("complaint", "Complaint"), ("account", "Account")],
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    @property
    def target_url(self):
        if self.resource == "request" and self.object_id:
            return reverse("request_detail", args=[self.object_id])
        if self.resource == "complaint" and self.object_id:
            return reverse("complaint_detail", args=[self.object_id])
        return reverse("profile")
