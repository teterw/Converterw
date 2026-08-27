"""Remembers the user's last choices between runs."""

import json
from dataclasses import asdict, fields

from core.paths import app_data_dir
from core.youtube import DEFAULT_DOWNLOAD_DIR, Options

SETTINGS_FILE = app_data_dir() / "settings.json"

_EXTRA_DEFAULTS = {
    "output_dir": DEFAULT_DOWNLOAD_DIR,
    "appearance": "System",
    "auto_update_engine": True,
    "show_log": False,
}


def defaults():
    settings = asdict(Options())
    settings.update(_EXTRA_DEFAULTS)
    return settings


def load():
    """Read saved settings, falling back to defaults for anything missing or
    corrupt so a bad file can never stop the app from starting."""
    settings = defaults()
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings

    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in settings and isinstance(value, type(settings[key])):
                settings[key] = value
    return settings


def save(settings):
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass  # Settings are a convenience; never fail a download over them.


def to_options(settings) -> Options:
    """Pull just the download options out of the settings dict."""
    names = {f.name for f in fields(Options)}
    return Options(**{k: v for k, v in settings.items() if k in names})
