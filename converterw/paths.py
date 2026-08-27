import os
import sys
from pathlib import Path

from converterw.version import APP_NAME


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


def error_log() -> Path:
    return app_data_dir() / "errors.log"


def log_error(message, context=""):
    """Append a failure to the error log so it can be reported after the fact.

    The GUI shows an error in a dialog that is gone as soon as it is dismissed,
    which leaves nothing to go on when someone says "it failed".
    """
    from datetime import datetime

    try:
        with open(error_log(), "a", encoding="utf-8") as handle:
            handle.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            if context:
                handle.write(f"{context}\n")
            handle.write(f"{message}\n")
    except OSError:
        pass  # Never let logging a failure cause another one.


def bundled_dir() -> Path:
    """Where PyInstaller extracts bundled files at runtime, or the source tree otherwise."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parent.parent
