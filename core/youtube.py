import os
import sys
from pathlib import Path

import yt_dlp

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

_FFMPEG_EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


def _bundled_dir():
    """Where PyInstaller extracts bundled files at runtime, or the source tree otherwise."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ffmpeg_location():
    """Prefer the ffmpeg shipped with the app; fall back to letting yt-dlp search PATH."""
    for candidate_dir in (_bundled_dir(), os.path.join(_bundled_dir(), "vendor", "ffmpeg")):
        candidate = os.path.join(candidate_dir, _FFMPEG_EXE)
        if os.path.isfile(candidate):
            return candidate
    return None


def is_playlist_only(url: str) -> bool:
    return "youtube.com/playlist" in url and "list=" in url


def is_video_url(url: str) -> bool:
    return "watch?v=" in url or "youtu.be/" in url


def is_video_in_playlist(url: str) -> bool:
    return is_video_url(url) and "list=" in url


def download_mp3(url, out_dir, progress_callback=None):
    _download(url, out_dir, mode="mp3", progress_callback=progress_callback)


def download_mp4(url, out_dir, progress_callback=None):
    _download(url, out_dir, mode="mp4", progress_callback=progress_callback)


def _format_bytes(n):
    if not n:
        return "0B"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TiB"


def _format_eta(seconds):
    if seconds is None:
        return "--:--"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _make_progress_hook(progress_callback):
    def hook(d):
        if not progress_callback or d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded = d.get("downloaded_bytes") or 0
        speed = d.get("speed") or 0
        progress_callback({
            "percent": (downloaded / total) if total else 0.0,
            "size": _format_bytes(total) if total else "?",
            "speed": f"{_format_bytes(speed)}/s" if speed else "?",
            "eta": _format_eta(d.get("eta")),
        })
    return hook


def _download(url, out_dir, mode, progress_callback):
    if not url:
        raise ValueError("URL is empty")

    os.makedirs(out_dir, exist_ok=True)

    if is_playlist_only(url):
        output_template = f"{out_dir}/%(playlist_title)s/%(title)s.%(ext)s"
    else:
        output_template = f"{out_dir}/%(title)s.%(ext)s"

    ydl_opts = {
        "outtmpl": output_template,
        "noplaylist": is_video_in_playlist(url) and not is_playlist_only(url),
        "progress_hooks": [_make_progress_hook(progress_callback)],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    ffmpeg_location = _ffmpeg_location()
    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location

    if mode == "mp3":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }]
    else:
        ydl_opts["format"] = "bv*+ba/best"
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"Download failed:\n{e}")
