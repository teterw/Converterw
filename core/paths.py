import os
import sys
from pathlib import Path

from core.version import APP_NAME


def app_data_dir() -> Path:
    """Per-user writable directory for settings and the updatable yt-dlp engine."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_dir() -> Path:
    """Where PyInstaller extracts bundled files at runtime, or the source tree otherwise."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parent.parent
