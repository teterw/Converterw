import subprocess
import os
from pathlib import Path

# Default to the Downloads folder
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

def download_mp3(url, out_dir=DEFAULT_DOWNLOAD_DIR):
    if not url:
        raise ValueError("URL is empty")

    os.makedirs(out_dir, exist_ok=True)

    subprocess.run([
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", f"{out_dir}/%(title)s.%(ext)s",
        url
    ], check=True)

def download_mp4(url, out_dir=DEFAULT_DOWNLOAD_DIR):
    if not url:
        raise ValueError("URL is empty")

    os.makedirs(out_dir, exist_ok=True)

    subprocess.run([
        "yt-dlp",
        "-f", "bv*+ba/best",
        "--merge-output-format", "mp4",
        "-o", f"{out_dir}/%(title)s.%(ext)s",
        url
    ], check=True)
