"""The self-updating yt-dlp engine: versions, staging, swapping and downloads."""

import io
import sys
import zipfile

import pytest

from converterw import engine
from converterw.engine import parse_version


@pytest.fixture
def engine_root(tmp_path, monkeypatch):
    root = tmp_path / "engine"
    monkeypatch.setattr(engine, "engine_dir", lambda: root)
    return root


def make_package(where, version):
    """Lay out the bare minimum _is_valid() looks for."""
    package = where / "yt_dlp"
    (package / "extractor").mkdir(parents=True)
    (package / "YoutubeDL.py").write_text("", encoding="utf-8")
    (package / "version.py").write_text(f"__version__ = '{version}'\n", encoding="utf-8")
    return where


# ------------------------------------------------------------------ versions

@pytest.mark.parametrize("text, parsed", [
    ("2026.08.19", (2026, 8, 19)),
    ("2026.08.19.232843", (2026, 8, 19, 232843)),
    ("1.2rc1", (1, 2)),
    ("", (0,)),
    (None, (0,)),
])
def test_parse_version(text, parsed):
    assert parse_version(text) == parsed


def test_versions_compare_as_numbers_not_strings():
    # As strings "2026.10.01" < "2026.9.30"; as dates it is the other way round.
    assert parse_version("2026.10.01") > parse_version("2026.9.30")
    assert parse_version("2026.08.19.232843") > parse_version("2026.08.19")


# ------------------------------------------------------------------- staging

def test_staged_update_is_promoted_at_startup(engine_root):
    make_package(engine_root / "active", "2026.08.01")
    make_package(engine_root / "staged", "2026.09.01")

    engine._promote_staged()

    assert engine.installed_version() == "2026.09.01"
    assert not (engine_root / "staged").exists()
    assert not (engine_root / "retired").exists()


def test_broken_staged_update_is_discarded(engine_root):
    make_package(engine_root / "active", "2026.08.01")
    (engine_root / "staged" / "yt_dlp").mkdir(parents=True)  # no files at all

    engine._promote_staged()

    assert engine.installed_version() == "2026.08.01"
    assert not (engine_root / "staged").exists()


def test_newer_downloaded_engine_takes_over(engine_root, monkeypatch):
    make_package(engine_root / "active", "2026.09.01")
    monkeypatch.setattr(engine, "bundled_version", lambda: "2026.08.19")
    monkeypatch.setattr(sys, "path", list(sys.path))

    assert engine.activate() == "2026.09.01"
    assert sys.path[0] == str(engine_root / "active")


def test_older_downloaded_engine_is_left_alone(engine_root, monkeypatch):
    # e.g. a fresh .exe that bundles a newer yt-dlp than the user's old update.
    make_package(engine_root / "active", "2026.07.01")
    monkeypatch.setattr(engine, "bundled_version", lambda: "2026.08.19")
    monkeypatch.setattr(sys, "path", list(sys.path))
    before = list(sys.path)

    assert engine.activate() == "2026.08.19"
    assert sys.path == before


def test_reset_removes_the_downloaded_engine(engine_root):
    make_package(engine_root / "active", "2026.09.01")
    engine.reset()
    assert not engine_root.exists()
    assert engine.installed_version() is None


# ------------------------------------------------------------------ download

class FakeResponse(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def make_wheel(version, extra=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr("yt_dlp/YoutubeDL.py", "")
        wheel.writestr("yt_dlp/extractor/__init__.py", "")
        wheel.writestr("yt_dlp/version.py", f"__version__ = '{version}'\n")
        wheel.writestr(f"yt_dlp-{version}.dist-info/METADATA", "")
        for name in extra:
            wheel.writestr(name, "")
    return buffer.getvalue()


@pytest.fixture
def serve_wheel(monkeypatch):
    def install(payload):
        monkeypatch.setattr(engine, "_wheel_url", lambda version, timeout=10: "https://example/whl")
        monkeypatch.setattr(engine.urllib.request, "urlopen",
                            lambda request, timeout=None: FakeResponse(payload))
    return install


def test_download_update_stages_the_new_engine(engine_root, serve_wheel):
    serve_wheel(make_wheel("2026.09.01"))
    progress = []

    assert engine.download_update(version="2026.09.01", progress=progress.append) == "2026.09.01"

    staged = engine_root / "staged"
    assert engine._read_version(staged) == "2026.09.01"
    assert not list(staged.glob("*.dist-info"))
    assert progress[-1] == 1.0


def test_download_update_never_writes_outside_the_package(engine_root, serve_wheel):
    serve_wheel(make_wheel("2026.09.01", extra=["yt_dlp/../../escaped.py"]))
    engine.download_update(version="2026.09.01")

    assert not list(engine_root.parent.rglob("escaped.py"))


def test_incomplete_download_is_not_staged(engine_root, serve_wheel):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr("yt_dlp/version.py", "__version__ = '2026.09.01'\n")
    serve_wheel(buffer.getvalue())

    with pytest.raises(RuntimeError, match="incomplete"):
        engine.download_update(version="2026.09.01")
    assert not (engine_root / "staged").exists()


def test_latest_version_is_none_when_offline(monkeypatch):
    def offline(request, timeout=None):
        raise OSError("no network")

    monkeypatch.setattr(engine.urllib.request, "urlopen", offline)
    assert engine.latest_version() is None
    assert engine.update_available() == (None, False)
