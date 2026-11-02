from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from inventory import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.WorkspaceLoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change.html", success_url="/profile/"
        ),
        name="password_change",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("registration/new/", views.new_registration, name="new_registration"),
    path("stockmanager/", views.stock_manager, name="stock_manager"),
    path("inventory/", views.inventory, name="inventory"),
    path("inventory/new/", views.item_edit, name="item_create"),
    path("inventory/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("inventory/<int:pk>/adjust/", views.stock_adjust, name="stock_adjust"),
    path("inventory/<int:item_id>/request/", views.request_create, name="item_request"),
    path("issued/", views.loans, name="loans"),
    path("issued/<int:pk>/return/", views.equipment_return, name="equipment_return"),
    path("requests/", views.stock_requests, name="requests"),
    path("requests/new/", views.request_create, name="request_create"),
    path("requests/<int:pk>/review/", views.request_review, name="request_review"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("updates/", views.notifications, name="notifications"),
    path("updates/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("updates/read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("complaints/", views.complaints, name="complaints"),
    path("complaints/new/", views.complaint_create, name="complaint_create"),
    path("complaints/<int:pk>/", views.complaint_detail, name="complaint_detail"),
    path("people/", views.users, name="users"),
    path("people/<int:pk>/access/", views.user_access, name="user_access"),
    path("profile/", views.profile, name="profile"),
    path("reports/", views.reports, name="reports"),
    path("faq/", views.faq, name="faq"),
    path("contact/", views.contact, name="contact"),
    path("help/", views.faq, name="help"),
    path("admin/", admin.site.urls),
    # Keep the original role dashboard bookmarks useful after consolidation.
    path("myadmin/", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("faculty/", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("technician/", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
]

# Preserve legacy navigation URLs while all roles share the permission-aware workspace.
legacy_routes = {
    "newregister": "new_registration",
    "stockmanager": "stock_manager",
    "shwstkdetl": "inventory",
    "newstkdetl": "requests",
    "userdetails": "users",
    "postcomplaint": "complaint_create",
    "poststkreq": "request_create",
    "reports": "reports",
    "shwstkreport": "reports",
    "shwcomplaintreport": "reports",
    "faq": "faq",
    "contactus": "contact",
    "profile": "profile",
}
for role_prefix in ("myadmin", "faculty", "technician"):
    for old_route, destination in legacy_routes.items():
        urlpatterns.append(
            path(
                f"{role_prefix}/{old_route}/",
                RedirectView.as_view(pattern_name=destination, permanent=False),
            )
        )
