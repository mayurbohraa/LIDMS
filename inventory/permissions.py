from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Profile


def role_for(user):
    if not user.is_authenticated:
        return ""
    if user.is_superuser:
        return Profile.Role.ADMIN
    try:
        return user.profile.role
    except Profile.DoesNotExist:
        return Profile.Role.FACULTY


def roles_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if role_for(request.user) not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
