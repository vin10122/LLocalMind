"""User-owned files live outside the replaceable application directory."""

import os
import sys
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


def child_environment():
    """Let external engines find the VC runtime bundled with the frozen app."""
    env=os.environ.copy()
    if getattr(sys,'frozen',False) and getattr(sys,'_MEIPASS',None):
        env['PATH']=str(sys._MEIPASS)+os.pathsep+env.get('PATH','')
    return env
