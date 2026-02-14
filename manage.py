#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""


# Adds newer version of sqlite for ChromaDB
import pysqlite3
import sys
sys.modules["sqlite3"] = pysqlite3

import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ragtalk.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
