"""Keeps yt-dlp up to date at runtime.

YouTube changes how it serves streams every few weeks. When that happens, any
yt-dlp older than the change starts failing with "HTTP Error 403: Forbidden".
Because the app ships as a frozen .exe, the bundled yt-dlp can never fix itself
and every release rots within a month or two.

yt-dlp is pure Python, so the fix is to keep an updated copy in the user's
app-data directory and put it ahead of the bundled one on sys.path:

    <app data>/engine/active/yt_dlp/   <- used if newer than the bundled copy
    <app data>/engine/staged/yt_dlp/   <- downloaded update, promoted at startup

Updates are staged rather than written over the running copy, so an update can
never corrupt the yt-dlp that the current session already imported.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from core.paths import app_data_dir

PYPI_PROJECT_URL = "https://pypi.org/pypi/yt-dlp/json"
_USER_AGENT = "Converterw (+https://github.com/teterw/Converterw)"
_VERSION_RE = re.compile(r"""^__version__\s*=\s*['"]([^'"]+)['"]""", re.MULTILINE)


def engine_dir() -> Path:
    return app_data_dir() / "engine"


def _active_dir() -> Path:
    return engine_dir() / "active"


def _staged_dir() -> Path:
    return engine_dir() / "staged"


def parse_version(text):
    """'2026.08.19' -> (2026, 8, 19). Unparseable input sorts oldest."""
    if not text:
        return (0,)
    parts = []
    for chunk in str(text).split("."):
        match = re.match(r"\d+", chunk)
        parts.append(int(match.group()) if match else 0)
    return tuple(parts) or (0,)


def _read_version(package_dir: Path):
    """Read yt-dlp's version straight from its source, without importing it."""
    version_file = package_dir / "yt_dlp" / "version.py"
    try:
        match = _VERSION_RE.search(version_file.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return match.group(1) if match else None


def _is_valid(package_dir: Path) -> bool:
    """A usable copy has the entry points we rely on and a readable version."""
    root = package_dir / "yt_dlp"
    return (
        (root / "YoutubeDL.py").is_file()
        and (root / "extractor").is_dir()
        and _read_version(package_dir) is not None
    )


def bundled_version():
    """Version of the yt-dlp that shipped inside the app (or is pip-installed)."""
    try:
        from importlib.metadata import version

        return version("yt-dlp")
    except Exception:
        return None


def installed_version():
    """Version of the downloaded engine currently in place, if any."""
    return _read_version(_active_dir())


def _promote_staged():
    """Move a previously downloaded update into place.

    Called only at startup, so the files being replaced are guaranteed not to
    have been imported yet by this process.
    """
    staged = _staged_dir()
    if not _is_valid(staged):
        shutil.rmtree(staged, ignore_errors=True)
        return

    active = _active_dir()
    retired = engine_dir() / "retired"
    shutil.rmtree(retired, ignore_errors=True)
    try:
        if active.exists():
            active.rename(retired)
        staged.rename(active)
    except OSError:
        # A half-finished swap must not leave a broken engine behind.
        if not _is_valid(active) and _is_valid(retired):
            shutil.rmtree(active, ignore_errors=True)
            retired.rename(active)
        return
    finally:
        shutil.rmtree(retired, ignore_errors=True)


def activate():
    """Pick the newest available yt-dlp and make `import yt_dlp` resolve to it.

    Must be called before anything imports yt_dlp. Returns the version string
    that will be used.
    """
    try:
        _promote_staged()
    except Exception:
        pass

    active = _active_dir()
    try:
        if _is_valid(active) and parse_version(_read_version(active)) > parse_version(
            bundled_version()
        ):
            sys.path.insert(0, str(active))
            return _read_version(active)
    except Exception:
        pass
    return bundled_version()


def latest_version(timeout=10):
    """Ask PyPI for the newest published yt-dlp. Returns None if offline."""
    try:
        request = urllib.request.Request(PYPI_PROJECT_URL, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)["info"]["version"]
    except Exception:
        return None


def current_version():
    """Version of the yt-dlp actually loaded for this session."""
    try:
        import yt_dlp

        return yt_dlp.version.__version__
    except Exception:
        return installed_version() or bundled_version()


def update_available(timeout=10):
    """(latest, True) when a newer yt-dlp than the one in use is published."""
    latest = latest_version(timeout=timeout)
    if not latest:
        return None, False
    return latest, parse_version(latest) > parse_version(current_version())


def _wheel_url(version, timeout=10):
    url = f"https://pypi.org/pypi/yt-dlp/{version}/json"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    for entry in payload.get("urls", []):
        filename = entry.get("filename", "")
        if entry.get("packagetype") == "bdist_wheel" and filename.endswith("-py3-none-any.whl"):
            return entry["url"]
    raise RuntimeError(f"No pure-Python wheel published for yt-dlp {version}")


def download_update(version=None, progress=None, timeout=30):
    """Download a yt-dlp release and stage it for the next launch.

    Returns the staged version string. The wheel is a plain zip of pure Python,
    so unpacking the `yt_dlp` package out of it is all that is needed.
    """
    version = version or latest_version(timeout=timeout)
    if not version:
        raise RuntimeError("Could not reach PyPI to check for updates.")

    url = _wheel_url(version, timeout=timeout)
    engine_dir().mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="converterw-engine-") as work_dir:
        work = Path(work_dir)
        wheel_path = work / "yt_dlp.whl"

        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(wheel_path, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done / total if total else 0.0)

        unpacked = work / "unpacked"
        with zipfile.ZipFile(wheel_path) as wheel:
            members = [n for n in wheel.namelist() if n.startswith("yt_dlp/") and ".." not in n]
            wheel.extractall(unpacked, members=members)

        if not _is_valid(unpacked):
            raise RuntimeError(f"Downloaded yt-dlp {version} looks incomplete; update aborted.")

        staged = _staged_dir()
        shutil.rmtree(staged, ignore_errors=True)
        shutil.move(str(unpacked), str(staged))

    return version


def reset():
    """Throw away the downloaded engine and fall back to the bundled yt-dlp."""
    shutil.rmtree(engine_dir(), ignore_errors=True)


def restart_app():
    """Relaunch the app so a staged engine update takes effect."""
    import subprocess

    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        command = [sys.executable, str(Path(__file__).resolve().parent.parent / "main.py")]
    subprocess.Popen(command, close_fds=True, cwd=os.getcwd())
