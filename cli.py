import argparse
import subprocess
import os

def youtube_to_mp3(url, out):
    subprocess.run([
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "-o", f"{out}/%(title)s.%(ext)s",
        url
    ], check=True)

def youtube_to_mp4(url, out):
    subprocess.run([
        "yt-dlp",
        "-f", "bv*+ba/best",
        "--merge-output-format", "mp4",
        "-o", f"{out}/%(title)s.%(ext)s",
        url
    ], check=True)

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["yt"])
parser.add_argument("--mp3", action="store_true")
parser.add_argument("--mp4", action="store_true")
parser.add_argument("url")
parser.add_argument("--out", default="downloads")

args = parser.parse_args()
os.makedirs(args.out, exist_ok=True)

if args.mp3:
    youtube_to_mp3(args.url, args.out)
elif args.mp4:
    youtube_to_mp4(args.url, args.out)
else:
    print("Choose --mp3 or --mp4")
