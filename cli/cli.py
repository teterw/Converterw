import argparse
import sys
import os

# Make "core" importable regardless of where this script is run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.youtube import download_mp3, download_mp4


def main():
    parser = argparse.ArgumentParser(description="YouTube → MP3/MP4 downloader")
    parser.add_argument("mode", choices=["yt"])
    parser.add_argument("url", help="YouTube URL to download")
    parser.add_argument("--mp3", action="store_true", help="Download as MP3")
    parser.add_argument("--mp4", action="store_true", help="Download as MP4")
    parser.add_argument("--out", default="downloads", help="Output folder (default: downloads)")

    args = parser.parse_args()

    if not args.mp3 and not args.mp4:
        parser.error("Choose --mp3 or --mp4")

    os.makedirs(args.out, exist_ok=True)

    def print_progress(data):
        pct = int(data["percent"] * 100)
        print(f"\r  {pct}% | {data['size']} | {data['speed']} | ETA {data['eta']}", end="", flush=True)

    try:
        if args.mp3:
            print(f"Downloading MP3 to: {args.out}")
            download_mp3(args.url, args.out, progress_callback=print_progress)
        else:
            print(f"Downloading MP4 to: {args.out}")
            download_mp4(args.url, args.out, progress_callback=print_progress)
        print("\nDone!")
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


# Usage examples:
#   python cli/cli.py yt "https://youtu.be/VIDEO_ID" --mp3
#   python cli/cli.py yt "https://youtu.be/VIDEO_ID" --mp4 --out C:\Users\you\Music
if __name__ == "__main__":
    main()
