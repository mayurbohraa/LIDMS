from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Activity, Item, StockMovement, StockRequest
from .notifications import notify
from .permissions import role_for


@transaction.atomic
def adjust_stock(*, item_id, delta, actor, reason):
    if role_for(actor) not in ("admin", "technician"):
        raise PermissionDenied
    item = Item.objects.select_for_update().get(pk=item_id, is_active=True)
    if not delta:
        raise ValidationError("Enter a non-zero stock adjustment.")
    # A conditional update prevents negative stock even if another request consumes it.
    updated = Item.objects.filter(pk=item.pk, quantity__gte=max(0, -delta)).update(
        quantity=F("quantity") + delta
    )
    if not updated:
        raise ValidationError("There is not enough stock for this adjustment.")
    item.refresh_from_db()
    StockMovement.objects.create(
        item=item, delta=delta, balance=item.quantity, actor=actor, reason=reason
    )
    Activity.objects.create(actor=actor, message=f"Adjusted {item.name} by {delta:+d} units.")
    return item


@transaction.atomic
def review_request(*, request_id, actor, decision, note=""):
    if role_for(actor) != "admin":
        raise PermissionDenied
    stock_request = StockRequest.objects.select_for_update().get(pk=request_id)
    if decision not in (StockRequest.Status.APPROVED, StockRequest.Status.REJECTED):
        raise ValidationError("Choose approve or reject.")
    if stock_request.status != StockRequest.Status.PENDING:
        raise ValidationError("This request has already been reviewed.")
    if decision == StockRequest.Status.APPROVED and stock_request.item_id:
        item = Item.objects.select_for_update().get(pk=stock_request.item_id)
        updated = Item.objects.filter(
            pk=item.pk, is_active=True, quantity__gte=stock_request.quantity
        ).update(quantity=F("quantity") - stock_request.quantity)
        if not updated:
            raise ValidationError("This item is archived or has insufficient available stock.")
        item.refresh_from_db()
        StockMovement.objects.create(
            item=item,
            actor=actor,
            delta=-stock_request.quantity,
            balance=item.quantity,
            stock_request=stock_request,
            reason=f"Issued for request #{stock_request.pk}",
        )
    stock_request.status = decision
    stock_request.decision_note = note
    stock_request.reviewed_by = actor
    stock_request.reviewed_at = timezone.now()
    stock_request.save(update_fields=["status", "decision_note", "reviewed_by", "reviewed_at"])
    Activity.objects.create(
        actor=actor,
        message=f"{stock_request.get_status_display()} stock request #{stock_request.pk}.",
    )
    notify(
        stock_request.requester,
        f"Your request #{stock_request.pk} for {stock_request.equipment_label} was {stock_request.get_status_display().lower()}.",
        "request",
        stock_request.pk,
        actor=actor,
    )
    return stock_request


@transaction.atomic
def return_stock(*, request_id, quantity, actor, reason, operation_id):
    if role_for(actor) not in ("admin", "technician"):
        raise PermissionDenied
    if not operation_id:
        raise ValidationError("A return reference is required. Reload the form and try again.")
    stock_request = StockRequest.objects.select_for_update().get(pk=request_id)
    previous = StockMovement.objects.filter(operation_id=operation_id).first()
    if previous:
        if (
            previous.stock_request_id == request_id
            and previous.delta == quantity
            and previous.actor_id == actor.pk
        ):
            return previous
        raise ValidationError("This return reference has already been used for another operation.")
    if stock_request.status != StockRequest.Status.APPROVED or not stock_request.item_id:
        raise ValidationError("Only issued equipment can be returned.")
    if quantity <= 0 or quantity > stock_request.outstanding_quantity:
        raise ValidationError(
            f"Return between 1 and {stock_request.outstanding_quantity} outstanding units."
        )
    item = Item.objects.select_for_update().get(pk=stock_request.item_id)
    # Archived equipment can still be received back without making it available for issue.
    Item.objects.filter(pk=item.pk).update(quantity=F("quantity") + quantity)
    StockRequest.objects.filter(pk=stock_request.pk).update(
        quantity_returned=F("quantity_returned") + quantity
    )
    item.refresh_from_db()
    movement = StockMovement.objects.create(
        item=item,
        actor=actor,
        delta=quantity,
        balance=item.quantity,
        stock_request=stock_request,
        operation_id=operation_id,
        reason=reason,
    )
    Activity.objects.create(
        actor=actor,
        message=f"Recorded {quantity} returned unit(s) for request #{stock_request.pk}.",
    )
    notify(
        stock_request.requester,
        f"{quantity} unit(s) returned for request #{stock_request.pk} were recorded by the lab.",
        "request",
        stock_request.pk,
        actor=actor,
    )
    return movement
