from .permissions import role_for


def workspace(request):
    role = role_for(request.user)
    name = request.user.get_full_name().strip() if request.user.is_authenticated else ""
    name = name or request.user.get_username()
    initials = "".join(part[0] for part in name.split()[:2]).upper()
    return {
        "workspace_role": role,
        "account_name": name,
        "account_initials": initials,
        "account_role": "Administrator" if role == "admin" else role.title(),
        "can_manage_stock": role in ("admin", "technician"),
        "is_administrator": role == "admin",
        "unread_notifications": request.user.notifications.filter(is_read=False).count()
        if request.user.is_authenticated
        else 0,
    }
