from .models import Notification


def notify(recipient, message, resource, object_id=None, actor=None):
    if actor is not None and recipient.pk == actor.pk:
        return
    Notification.objects.create(
        recipient=recipient, message=message[:300], resource=resource, object_id=object_id
    )
