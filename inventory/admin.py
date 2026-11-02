from django.contrib import admin

from .models import Activity, Complaint, ContactMessage, Item, Profile, StockMovement, StockRequest


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "department"]
    list_filter = ["role"]


@admin.register(Item, StockRequest, Complaint, ContactMessage, StockMovement, Activity)
class AuditAdmin(admin.ModelAdmin):
    """Workflow writes go through the application so they cannot bypass stock/audit rules."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
