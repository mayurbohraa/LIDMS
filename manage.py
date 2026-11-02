#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env-file")
    parser.add_argument("--direct-db", action="store_true")
    options, arguments = parser.parse_known_args()
    if options.env_file:
        if not Path(options.env_file).is_file():
            raise SystemExit("The specified environment file does not exist.")
        os.environ["LIDMS_ENV_FILE"] = str(Path(options.env_file).resolve())
    if options.direct_db:
        os.environ["LIDMS_USE_DIRECT_DB"] = "1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lidms.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], *arguments])
