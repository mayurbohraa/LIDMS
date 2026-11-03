from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Preserve the original email login while retaining CLI/demo username support."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            # Two matches are enough to reject ambiguous email addresses.
            matches = list(
                get_user_model()
                .objects.filter(email__iexact=username.strip())
                .values_list("username", flat=True)[:2]
            )
            if len(matches) != 1:
                return None
            username = matches[0]
        return super().authenticate(request, username=username, password=password, **kwargs)
