"""Load private local settings, optionally sharing Neon's database with Vercel."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values, load_dotenv


def load_environment(base_dir):
    explicit = os.getenv("LIDMS_ENV_FILE")
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ImproperlyConfigured("The specified environment file does not exist.")
        load_dotenv(path, override=True)
    elif os.getenv("VERCEL") != "1":
        inherited_database = os.getenv("DATABASE_URL")
        load_dotenv(base_dir / ".env.local")
        load_dotenv(base_dir / ".env")
        # Only share database connections, never hosted debug/cookie settings.
        if not inherited_database:
            shared = dotenv_values(base_dir / ".env.neon")
            if (
                shared.get("DATABASE_URL_UNPOOLED")
                and not shared.get("DATABASE_URL")
                and os.getenv("LIDMS_USE_DIRECT_DB") != "1"
            ):
                raise ImproperlyConfigured(
                    "Add the pooled DATABASE_URL to .env.neon before starting the shared app."
                )
            for key in ("DATABASE_URL", "DATABASE_URL_UNPOOLED"):
                if shared.get(key):
                    os.environ[key] = shared[key]
    if os.getenv("LIDMS_USE_DIRECT_DB") == "1":
        direct = os.getenv("DATABASE_URL_UNPOOLED", "")
        if not direct:
            raise ImproperlyConfigured("Set DATABASE_URL_UNPOOLED before using --direct-db.")
        os.environ["DATABASE_URL"] = direct
