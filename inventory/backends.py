from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Preserve the original email login while retaining CLI/demo username support."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            matches = get_user_model().objects.filter(email__iexact=username.strip())
            if matches.count() != 1:
                return None
            username = matches.get().username
        return super().authenticate(request, username=username, password=password, **kwargs)
