import subprocess
import os
import re
from pathlib import Path

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

PROGRESS_REGEX = re.compile(
    r"\[download\]\s+(\d+\.\d+)%\s+of\s+([\d\.]+)(MiB|GiB).*?at\s+([\d\.]+)(KiB|MiB|GiB)/s\s+ETA\s+([\d:]+)"
)


def download_mp3(url, out_dir, progress_callback=None):
    _download(url, out_dir, "mp3", progress_callback)


def download_mp4(url, out_dir, progress_callback=None):
    _download(url, out_dir, "mp4", progress_callback)


def _download(url, out_dir, mode, progress_callback):
    if not url:
        raise ValueError("URL is empty")

    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "--newline",
        "-o", f"{out_dir}/%(title)s.%(ext)s",
        url
    ]

    if mode == "mp3":
        cmd += ["-x", "--audio-format", "mp3"]
    else:
        cmd += ["-f", "bv*+ba/best", "--merge-output-format", "mp4"]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    for line in process.stdout:
        match = PROGRESS_REGEX.search(line)
        if match and progress_callback:
            percent = float(match.group(1))
            size = f"{match.group(2)} {match.group(3)}"
            speed = f"{match.group(4)} {match.group(5)}/s"
            eta = match.group(6)

            progress_callback({
                "percent": percent / 100,
                "size": size,
                "speed": speed,
                "eta": eta
            })

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("Download failed")
