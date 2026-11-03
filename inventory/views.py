import csv
import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AdjustmentForm,
    ComplaintForm,
    ComplaintUpdateForm,
    ContactForm,
    ItemForm,
    NewRegistrationForm,
    ProfileForm,
    ProjectLoginForm,
    RegistrationForm,
    ReturnForm,
    ReviewForm,
    StockRequestForm,
    UserAccessForm,
)
from .models import (
    Activity,
    Complaint,
    ContactMessage,
    Item,
    LoginAttempt,
    Notification,
    Profile,
    StockMovement,
    StockRequest,
)
from .notifications import notify
from .permissions import role_for, roles_required
from .services import adjust_stock, return_stock, review_request

User = get_user_model()


class WorkspaceLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    authentication_form = ProjectLoginForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if settings.SHOW_DEMO_ACCOUNTS and settings.DEMO_PASSWORD:
            descriptions = {
                "admin": "Manage equipment, users, requests and complaints.",
                "faculty": "Request equipment, report issues and track progress.",
                "technician": "Handle assigned repairs and record equipment returns.",
            }
            accounts = []
            for role, description in descriptions.items():
                account = User.objects.filter(
                    username=f"demo.{role}",
                    email=f"{role}@lidms.example",
                    is_active=True,
                    profile__role=role,
                ).first()
                if account:
                    accounts.append(
                        {
                            "role": role,
                            "label": "Administrator" if role == "admin" else role.title(),
                            "email": account.email,
                            "description": description,
                        }
                    )
            if accounts:
                context.update(demo_accounts=accounts, demo_password=settings.DEMO_PASSWORD)
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        # Keep the intentionally published demo details out of shared page caches.
        response["Cache-Control"] = "no-store"
        return response

    def form_valid(self, form):
        attempt = self._attempt()
        if attempt.failures >= 8:
            form.add_error(None, "Too many attempts. Please try again in 15 minutes.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        attempt.delete()
        return super().form_valid(form)

    def form_invalid(self, form):
        attempt = self._attempt()
        LoginAttempt.objects.filter(pk=attempt.pk).update(failures=F("failures") + 1)
        if attempt.failures >= 8:
            form.add_error(None, "Too many attempts. Please try again in 15 minutes.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().form_invalid(form)

    def _attempt(self):
        # Do not trust a client-controlled forwarded IP header for throttling.
        identity = f"{self.request.META.get('REMOTE_ADDR', '')}:{self.request.POST.get('username', '').strip().lower()}"
        key = hashlib.sha256(identity.encode()).hexdigest()
        attempt, _ = LoginAttempt.objects.get_or_create(
            key=key, defaults={"started_at": timezone.now()}
        )
        if attempt.started_at < timezone.now() - timedelta(minutes=15):
            attempt.failures = 0
            attempt.started_at = timezone.now()
            attempt.save(update_fields=["failures", "started_at"])
        return attempt


def home(request):
    return render(request, "home.html", {"title": "Lab management"})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            Profile.objects.create(
                user=user,
                department=form.cleaned_data["department"],
                phone=form.cleaned_data["phone"],
            )
        messages.success(
            request,
            "Account requested. An administrator must approve access before you can sign in.",
        )
        return redirect("login")
    return render(request, "registration/register.html", {"form": form})


def scoped_requests(user):
    queryset = StockRequest.objects.select_related(
        "requester", "requester__profile", "item", "reviewed_by"
    )
    return queryset if role_for(user) == "admin" else queryset.filter(requester=user)


@roles_required("admin")
def new_registration(request):
    form = NewRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Profile.objects.create(
                user=user,
                role=form.cleaned_data["role"],
                department=form.cleaned_data["department"],
                phone=form.cleaned_data["phone"],
            )
            Activity.objects.create(
                actor=request.user, message=f"Registered account for {user.email}."
            )
            notify(
                user,
                "Your LIDMS account is ready. Your lab workspace is available.",
                "account",
                actor=request.user,
            )
        messages.success(
            request, "Registration completed. The user can log in with their email and password."
        )
        return redirect("users")
    return render(
        request,
        "form.html",
        {
            "title": "New Registration",
            "section": "registration",
            "form": form,
            "back_url": "users",
            "submit_label": "Register",
        },
    )


@login_required
def stock_manager(request):
    return render(request, "stock_manager.html", {"title": "Stock Manager", "section": "inventory"})


def faq(request):
    return render(
        request,
        "faq.html",
        {
            "title": "FAQs",
            "section": "faq",
            "layout_template": "base.html" if request.user.is_authenticated else "public_base.html",
        },
    )


def contact(request):
    initial = (
        {"name": request.user.get_full_name(), "email": request.user.email}
        if request.user.is_authenticated
        else {}
    )
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your message has been recorded for the lab administrator.")
        return redirect("contact")
    return render(
        request,
        "contact.html",
        {
            "title": "Contact Us",
            "section": "contact",
            "form": form,
            "inquiries": ContactMessage.objects.all()[:20]
            if role_for(request.user) == "admin"
            else [],
            "layout_template": "base.html" if request.user.is_authenticated else "public_base.html",
        },
    )


def scoped_complaints(user):
    queryset = Complaint.objects.select_related(
        "reporter", "reporter__profile", "assigned_to", "item"
    )
    role = role_for(user)
    if role == "admin":
        return queryset
    if role == "technician":
        return queryset.filter(Q(assigned_to=user) | Q(reporter=user))
    return queryset.filter(reporter=user)


def page(request, queryset):
    return Paginator(queryset, 15).get_page(request.GET.get("page"))


def scoped_loans(user, include_returned=False):
    queryset = (
        StockRequest.objects.filter(status="approved", item__isnull=False)
        .select_related("item", "requester", "requester__profile")
        .annotate(units_out=F("quantity") - F("quantity_returned"))
    )
    if role_for(user) not in ("admin", "technician"):
        queryset = queryset.filter(requester=user)
    return queryset if include_returned else queryset.filter(units_out__gt=0)


@login_required
def dashboard(request):
    role = role_for(request.user)
    label = {"admin": "Admin", "faculty": "Faculty", "technician": "Technician"}[role]
    requests = scoped_requests(request.user)
    complaints = scoped_complaints(request.user)
    items = Item.objects.filter(is_active=True)
    low_stock = items.filter(quantity__lte=F("reorder_level"))
    pending = requests.filter(status="pending")
    loans = scoped_loans(request.user)
    units_out = loans.aggregate(total=Sum("units_out"))["total"] or 0
    open_issues = complaints.exclude(status="resolved")
    inactive_users = (
        User.objects.filter(is_active=False).select_related("profile").order_by("date_joined")
        if role == "admin"
        else User.objects.none()
    )
    if role == "admin":
        metric_specs = [
            (
                "Pending requests",
                pending.count(),
                "requests",
                "?status=pending",
                "Requests ready for your decision",
            ),
            (
                "Open complaints",
                open_issues.count(),
                "complaints",
                "?status=active",
                "Maintenance needing attention",
            ),
            (
                "Low-stock items",
                low_stock.count(),
                "inventory",
                "?stock=low",
                "At or below the reorder level",
            ),
            (
                "Inactive accounts",
                inactive_users.count(),
                "users",
                "?access=inactive",
                "Review registration and access",
            ),
        ]
        intro = "Keep registrations, equipment and lab maintenance moving."
        queue_title = "Requests awaiting your decision"
    elif role == "technician":
        assigned = complaints.filter(assigned_to=request.user).exclude(status="resolved")
        metric_specs = [
            (
                "Assigned jobs",
                assigned.count(),
                "complaints",
                "?queue=assigned",
                "Your open maintenance work",
            ),
            (
                "High-priority jobs",
                assigned.filter(priority="high").count(),
                "complaints",
                "?queue=assigned&priority=high",
                "Assigned issues to handle first",
            ),
            (
                "Low-stock items",
                low_stock.count(),
                "inventory",
                "?stock=low",
                "Equipment that needs replenishment",
            ),
            ("Units issued", units_out, "loans", "", "Equipment awaiting return"),
        ]
        intro = "Your maintenance queue, stock alerts and equipment returns."
        queue_title = "Your stock requests"
    else:
        metric_specs = [
            (
                "My pending requests",
                pending.count(),
                "requests",
                "?status=pending",
                "Waiting for administrator review",
            ),
            (
                "My open complaints",
                open_issues.count(),
                "complaints",
                "?status=active",
                "Track the issues you reported",
            ),
            ("My borrowed units", units_out, "loans", "", "Equipment currently issued to you"),
            ("Equipment types", items.count(), "inventory", "", "Browse the lab inventory"),
        ]
        intro = "Request equipment, follow your complaints and track your lab work."
        queue_title = "Your recent stock requests"
    metrics = [
        {"label": title, "value": count, "url": reverse(route) + query, "hint": hint}
        for title, count, route, query, hint in metric_specs
    ]
    priority_order = Case(
        When(priority="high", then=Value(0)),
        When(priority="medium", then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )
    maintenance = (
        open_issues.filter(assigned_to=request.user) if role == "technician" else open_issues
    )
    maintenance = maintenance.order_by(priority_order, "created_at")
    activity = Activity.objects.select_related("actor")
    if role != "admin":
        activity = activity.filter(actor=request.user)
    progress_complaints = (
        complaints.filter(assigned_to=request.user) if role == "technician" else complaints
    )
    status_counts = dict(
        progress_complaints.values("status")
        .annotate(total=Count("pk"))
        .values_list("status", "total")
    )
    total_complaints = sum(status_counts.values())
    breakdown = [
        {
            "label": label,
            "status": status,
            "count": status_counts.get(status, 0),
            "percent": round(status_counts.get(status, 0) * 100 / total_complaints)
            if total_complaints
            else 0,
        }
        for status, label in Complaint.Status.choices
    ]
    return render(
        request,
        "dashboard.html",
        {
            "title": f"{label} Dashboard",
            "section": "dashboard",
            "intro": intro,
            "metrics": metrics,
            "queue_title": queue_title,
            "request_queue": (pending.order_by("created_at") if role == "admin" else requests)[:5],
            "maintenance_queue": maintenance[:4],
            "low_stock": low_stock.order_by("quantity", "name")[:4],
            "inactive_users": inactive_users[:3],
            "activities": activity[:5],
            "breakdown": breakdown,
            "complaint_total": total_complaints,
            "open_units": units_out,
        },
    )


@login_required
def inventory(request):
    items = (
        Item.objects.all()
        if role_for(request.user) in ("admin", "technician")
        else Item.objects.filter(is_active=True)
    )
    query = request.GET.get("q", "").strip()[:150]
    if query:
        items = items.filter(
            Q(name__icontains=query)
            | Q(asset_code__icontains=query)
            | Q(laboratory__icontains=query)
        )
    if request.GET.get("stock") == "low":
        items = items.filter(is_active=True, quantity__lte=F("reorder_level"))
    return render(
        request,
        "inventory.html",
        {
            "title": "Show Stock Details",
            "section": "inventory",
            "page_obj": page(request, items),
            "query": query,
        },
    )


@roles_required("admin", "technician")
def item_edit(request, pk=None):
    item = get_object_or_404(Item, pk=pk) if pk else None
    form = ItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save()
            Activity.objects.create(
                actor=request.user, message=f"Updated inventory record {item.asset_code}."
            )
        messages.success(
            request, "Equipment saved. Use Adjust stock to record received or removed units."
        )
        return redirect("inventory")
    return render(
        request,
        "form.html",
        {
            "title": "Edit equipment" if pk else "Add equipment",
            "section": "inventory",
            "form": form,
            "back_url": "inventory",
        },
    )


@roles_required("admin", "technician")
def stock_adjust(request, pk):
    item = get_object_or_404(Item, pk=pk, is_active=True)
    form = AdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            adjust_stock(item_id=item.pk, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Stock updated and movement recorded.")
            return redirect("inventory")
    return render(
        request,
        "form.html",
        {
            "title": f"Adjust stock · {item.name}",
            "subtitle": f"Available: {item.quantity} units",
            "section": "inventory",
            "form": form,
            "back_url": "inventory",
        },
    )


@login_required
def stock_requests(request):
    queryset = scoped_requests(request.user)
    status = request.GET.get("status", "")
    if status in StockRequest.Status.values:
        queryset = queryset.filter(status=status)
    return render(
        request,
        "requests.html",
        {
            "title": "New Stock Requests",
            "section": "requests",
            "page_obj": page(request, queryset),
            "statuses": StockRequest.Status.choices,
        },
    )


@login_required
def request_create(request, item_id=None):
    selected_item = get_object_or_404(Item, pk=item_id, is_active=True) if item_id else None
    form = StockRequestForm(request.POST or None, user=request.user, selected_item=selected_item)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            stock_request = form.save(commit=False)
            stock_request.requester = request.user
            stock_request.save()
            Activity.objects.create(
                actor=request.user, message=f"Submitted stock request #{stock_request.pk}."
            )
        messages.success(request, "Request submitted for administrator approval.")
        return redirect("requests")
    return render(
        request,
        "form.html",
        {
            "title": "Post Stock Request",
            "section": "post_request",
            "form": form,
            "back_url": "requests",
            "submit_label": "Post",
            "detail": f"Request available {selected_item.name}. Stock is issued after administrator approval."
            if selected_item
            else "Request new lab equipment and describe why it is needed.",
        },
    )


@roles_required("admin")
def request_review(request, pk):
    stock_request = get_object_or_404(
        StockRequest.objects.select_related("item", "requester"), pk=pk
    )

    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            review_request(request_id=pk, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Request reviewed successfully.")
            return redirect("requests")
    return render(
        request,
        "form.html",
        {
            "title": f"Review request #{pk}",
            "subtitle": f"{stock_request.requester.get_full_name() or stock_request.requester.username} · {stock_request.equipment_label} · {stock_request.quantity} units",
            "detail": stock_request.purpose,
            "form": form,
            "section": "requests",
            "back_url": "requests",
        },
    )


@login_required
def request_detail(request, pk):
    queryset = scoped_requests(request.user)
    if role_for(request.user) == "technician":
        queryset = StockRequest.objects.select_related(
            "item", "requester", "requester__profile", "reviewed_by"
        ).filter(Q(requester=request.user) | Q(status="approved", item__isnull=False))
    stock_request = get_object_or_404(queryset, pk=pk)
    return render(
        request,
        "request_detail.html",
        {
            "title": f"Stock Request #{pk}",
            "section": "requests",
            "stock_request": stock_request,
            "movements": stock_request.movements.select_related("actor"),
        },
    )


@login_required
def loans(request):
    queryset = scoped_loans(request.user, include_returned=request.GET.get("history") == "1")
    query = request.GET.get("q", "").strip()[:150]
    if query:
        queryset = queryset.filter(
            Q(item__name__icontains=query)
            | Q(requester__first_name__icontains=query)
            | Q(requester__last_name__icontains=query)
            | Q(item__asset_code__icontains=query)
        )
    return render(
        request,
        "loans.html",
        {
            "title": "Issued Equipment",
            "section": "inventory",
            "page_obj": page(request, queryset),
            "query": query,
        },
    )


@roles_required("admin", "technician")
def equipment_return(request, pk):
    stock_request = get_object_or_404(scoped_loans(request.user, include_returned=True), pk=pk)
    if not stock_request.outstanding_quantity:
        messages.info(request, "All issued units for this request have already been returned.")
        return redirect("request_detail", pk=pk)
    form = ReturnForm(request.POST or None)
    form.fields["quantity"].max_value = stock_request.outstanding_quantity
    if request.method == "POST" and form.is_valid():
        try:
            return_stock(request_id=pk, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Return recorded and stock balance updated.")
            return redirect("request_detail", pk=pk)
    return render(
        request,
        "form.html",
        {
            "title": "Record Equipment Return",
            "section": "inventory",
            "form": form,
            "subtitle": f"{stock_request.equipment_label} · {stock_request.outstanding_quantity} units outstanding",
            "back_url": "loans",
            "submit_label": "Record return",
        },
    )


@login_required
def notifications(request):
    queryset = request.user.notifications.all()
    if request.GET.get("unread") == "1":
        queryset = queryset.filter(is_read=False)
    return render(
        request,
        "notifications.html",
        {"title": "Your Updates", "page_obj": page(request, queryset), "section": "updates"},
    )


@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect("notifications")


@login_required
@require_POST
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications")


@login_required
def complaints(request):
    queryset = scoped_complaints(request.user)
    if request.GET.get("queue") == "assigned":
        queryset = queryset.filter(assigned_to=request.user).exclude(status="resolved")
    if request.GET.get("priority") in Complaint.Priority.values:
        queryset = queryset.filter(priority=request.GET["priority"])
    status = request.GET.get("status", "")
    if status == "active":
        queryset = queryset.exclude(status="resolved")
    elif status in Complaint.Status.values:
        queryset = queryset.filter(status=status)
    return render(
        request,
        "complaints.html",
        {
            "title": "Complaint Details",
            "section": "complaints",
            "page_obj": page(request, queryset),
            "statuses": Complaint.Status.choices,
        },
    )


@login_required
def complaint_create(request):
    form = ComplaintForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            complaint = form.save(commit=False)
            complaint.reporter = request.user
            complaint.save()
            Activity.objects.create(
                actor=request.user, message=f"Reported complaint #{complaint.pk}."
            )
        messages.success(request, "Complaint recorded. You can track its status here.")
        return redirect("complaints")
    return render(
        request,
        "form.html",
        {
            "title": "Post Complaint",
            "submit_label": "Post",
            "form_variant": "project-form",
            "section": "complaints",
            "form": form,
            "back_url": "complaints",
        },
    )


@login_required
def complaint_detail(request, pk):
    complaint = get_object_or_404(scoped_complaints(request.user), pk=pk)
    previous_assignment = complaint.assigned_to_id
    previous_status = complaint.status
    role = role_for(request.user)
    can_update = role == "admin" or (
        role == "technician" and complaint.assigned_to_id == request.user.pk
    )
    if request.method == "POST" and not can_update:
        raise PermissionDenied
    form = (
        ComplaintUpdateForm(request.POST or None, instance=complaint, is_admin=role == "admin")
        if can_update
        else None
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            if complaint.assigned_to_id and complaint.assigned_to_id != previous_assignment:
                notify(
                    complaint.assigned_to,
                    f"Complaint #{complaint.pk} was assigned to you: {complaint.subject}",
                    "complaint",
                    complaint.pk,
                    actor=request.user,
                )
            if (
                complaint.status != previous_status
                or complaint.assigned_to_id != previous_assignment
            ):
                notify(
                    complaint.reporter,
                    f"Your complaint #{complaint.pk} was updated: {complaint.get_status_display()}.",
                    "complaint",
                    complaint.pk,
                    actor=request.user,
                )
            Activity.objects.create(
                actor=request.user,
                message=f"Updated complaint #{complaint.pk} to {complaint.get_status_display()}.",
            )
        messages.success(request, "Complaint updated.")
        return redirect("complaint_detail", pk=pk)
    return render(
        request,
        "complaint_detail.html",
        {
            "title": f"Complaint #{pk}",
            "section": "complaints",
            "complaint": complaint,
            "form": form,
        },
    )


@roles_required("admin")
def users(request):
    queryset = User.objects.select_related("profile").order_by("-date_joined")
    if request.GET.get("access") == "inactive":
        queryset = queryset.filter(is_active=False)
    query = request.GET.get("q", "").strip()[:150]
    if query:
        queryset = queryset.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
        )
    return render(
        request,
        "users.html",
        {
            "title": "User Details",
            "section": "users",
            "page_obj": page(request, queryset),
            "query": query,
        },
    )


@roles_required("admin")
def user_access(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile, _ = Profile.objects.get_or_create(user=user)
    form = UserAccessForm(
        request.POST or None, initial={"role": role_for(user), "is_active": user.is_active}
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if user.pk == request.user.pk and (not data["is_active"] or data["role"] != "admin"):
            form.add_error(None, "You cannot remove your own administrator access.")
        elif user.is_superuser and (not data["is_active"] or data["role"] != "admin"):
            form.add_error(None, "Superuser access must be changed through Django administration.")
        else:
            with transaction.atomic():
                profile.role = data["role"]
                profile.save()
                user.is_active = data["is_active"]
                user.save(update_fields=["is_active"])
                Activity.objects.create(
                    actor=request.user, message=f"Updated access for {user.username}."
                )
                notify(
                    user,
                    f"Your account access was updated: {profile.get_role_display()}, {'active' if user.is_active else 'inactive'}.",
                    "account",
                    actor=request.user,
                )
            messages.success(request, "Account access updated.")
            return redirect("users")
    return render(
        request,
        "form.html",
        {
            "title": f"Account access · {user.username}",
            "section": "users",
            "form": form,
            "back_url": "users",
        },
    )


@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            request.user.first_name = form.cleaned_data["first_name"]
            request.user.last_name = form.cleaned_data["last_name"]
            request.user.save(update_fields=["first_name", "last_name"])
        messages.success(request, "Profile saved.")
        return redirect("profile")
    return render(request, "profile.html", {"title": "Profile", "section": "profile", "form": form})


def csv_cell(value):
    value = str(value if value is not None else "")
    # Spreadsheet applications can execute formula-looking cells from CSV files.
    return (
        "'" + value
        if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))
        else value
    )


@login_required
def reports(request):
    items = Item.objects.filter(is_active=True)
    requests = scoped_requests(request.user)
    complaints = scoped_complaints(request.user)
    kind = request.GET.get("export")
    if kind in ("inventory", "requests", "complaints"):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="lidms-{kind}.csv"'
        writer = csv.writer(response)
        if kind == "inventory":
            writer.writerow(
                ["Code", "Equipment", "Category", "Laboratory", "Available", "Reorder level"]
            )
            rows = items.values_list(
                "asset_code", "name", "category", "laboratory", "quantity", "reorder_level"
            )
        elif kind == "requests":
            writer.writerow(["ID", "Requester", "Equipment", "Quantity", "Status", "Created"])
            rows = (
                (
                    row.pk,
                    row.requester.get_full_name() or row.requester.username,
                    row.equipment_label,
                    row.quantity,
                    row.status,
                    row.created_at,
                )
                for row in requests.iterator()
            )
        else:
            writer.writerow(["ID", "Subject", "Laboratory", "Priority", "Status", "Reported"])
            rows = complaints.values_list(
                "pk", "subject", "laboratory", "priority", "status", "created_at"
            )
        for row in rows:
            writer.writerow([csv_cell(cell) for cell in row])
        return response
    report_view = request.GET.get("view")
    if report_view == "stock":
        return render(
            request,
            "stock_report.html",
            {"title": "Show Stock’s Report", "section": "reports", "items": items},
        )
    if report_view == "complaints":
        return render(
            request,
            "complaint_report.html",
            {"title": "Show Complaint’s Report", "section": "reports", "records": complaints},
        )
    return render(
        request,
        "reports.html",
        {
            "title": "Reports",
            "section": "reports",
            "item_count": items.count(),
            "request_count": requests.count(),
            "complaint_count": complaints.count(),
            "movements": StockMovement.objects.select_related("item", "actor")[:12]
            if role_for(request.user) in ("admin", "technician")
            else [],
        },
    )
