import subprocess
import os
import re
import sys
from pathlib import Path

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

PROGRESS_REGEX = re.compile(
    r"\[download\]\s+(\d+\.\d+)%\s+of\s+([\d\.]+)(MiB|GiB).*?"
    r"at\s+([\d\.]+)(KiB|MiB|GiB)/s\s+ETA\s+([\d:]+)"
)


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


def _download(url, out_dir, mode, progress_callback):
    if not url:
        raise ValueError("URL is empty")

    os.makedirs(out_dir, exist_ok=True)

    # Decide output path
    if is_playlist_only(url):
        output_template = f"{out_dir}/%(playlist_title)s/%(title)s.%(ext)s"
    else:
        output_template = f"{out_dir}/%(title)s.%(ext)s"

    cmd = [
        "yt-dlp",
        "--newline",
        "-o", output_template,
        url
    ]

    # Force single-video behavior
    if is_video_in_playlist(url) and not is_playlist_only(url):
        cmd.append("--no-playlist")

    if mode == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    else:
        cmd += ["-f", "bv*+ba/best", "--merge-output-format", "mp4"]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=creationflags
    )

    for line in process.stdout:
        match = PROGRESS_REGEX.search(line)
        if match and progress_callback:
            progress_callback({
                "percent": float(match.group(1)) / 100,
                "size": f"{match.group(2)} {match.group(3)}",
                "speed": f"{match.group(4)} {match.group(5)}/s",
                "eta": match.group(6)
            })

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("Download failed")
