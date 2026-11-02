#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env-file")
    options, arguments = parser.parse_known_args()
    if options.env_file:
        if not Path(options.env_file).is_file():
            raise SystemExit("The specified environment file does not exist.")
        # An explicit target file keeps hosted database maintenance separate from local work.
        load_dotenv(options.env_file, override=True)
    else:
        load_dotenv(".env.local")
        load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lidms.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], *arguments])
