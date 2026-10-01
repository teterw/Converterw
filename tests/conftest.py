"""Shared test setup.

The app data folder is pointed at a throwaway directory *before* anything
imports converterw: youtube.py activates the self-updating engine at import
time and config.py resolves the settings path at import time, so otherwise
the tests would read and write the real %LOCALAPPDATA%\\Converterw of
whoever runs them.
"""

import atexit
import os
import shutil
import sys
import tempfile

_DATA_ROOT = tempfile.mkdtemp(prefix="converterw-tests-")
atexit.register(shutil.rmtree, _DATA_ROOT, ignore_errors=True)

os.environ["LOCALAPPDATA"] = _DATA_ROOT
os.environ["XDG_DATA_HOME"] = _DATA_ROOT
if sys.platform == "darwin":
    os.environ["HOME"] = _DATA_ROOT

import pytest  # noqa: E402

from converterw import config, youtube  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Every test starts from an empty settings file of its own."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)
    return settings_file


@pytest.fixture(autouse=True)
def ffmpeg_installed(monkeypatch):
    """Pretend ffmpeg is installed, so results don't depend on the machine.

    Tests about life without ffmpeg patch has_ffmpeg back to False.
    """
    monkeypatch.setattr(youtube, "has_ffmpeg", lambda: True)


@pytest.fixture
def no_ffmpeg(monkeypatch):
    monkeypatch.setattr(youtube, "has_ffmpeg", lambda: False)
