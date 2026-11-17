"""Load API keys from the project's git-ignored .env into the environment (no extra dependency)."""
import os
from pathlib import Path

_ENV = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    if not _ENV.exists():
        return
    for line in _ENV.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
