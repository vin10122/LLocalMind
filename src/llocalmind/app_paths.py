"""User-owned files live outside the replaceable application directory."""

import os
from pathlib import Path


def data_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "LLocalMind"


def user_data_dir() -> Path:
    """Settings and conversations; never an installer destination."""
    return data_root() / "data"


def models_dir() -> Path:
    """Default external model directory; users can select another location."""
    return data_root() / "models"


def updates_dir() -> Path:
    return data_root() / "updates"
