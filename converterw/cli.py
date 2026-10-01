"""Command-line interface for Converterw.

Installed as `converterw`, so it behaves like any other terminal tool:

    converterw https://youtu.be/VIDEO -q 1080p
    converterw https://youtu.be/VIDEO --audio -a mp3 -b 320
    converterw URL1 URL2 URL3
"""

import argparse
import os
import sys

from converterw import config, engine
from converterw.paths import log_error
from converterw.version import APP_NAME, __version__
from converterw.youtube import (
    AUDIO_FORMATS,
    COOKIE_BROWSERS,
    DEFAULT_DOWNLOAD_DIR,
    NO_FFMPEG_NOTE,
    VIDEO_CONTAINERS,
    Downloader,
    Options,
    brief_error,
    format_duration,
    has_ffmpeg,
    probe,
    split_links,
)

# The GUI shows friendly labels; the CLI takes short ones people would type.
QUALITY_CHOICES = {
    "best": "Best available",
    "2160p": "4K (2160p)",
    "4k": "4K (2160p)",
    "1440p": "1440p",
    "1080p": "1080p",
    "720p": "720p",
    "480p": "480p",
    "360p": "360p",
    "240p": "240p",
}
BITRATE_CHOICES = {
    "best": "Best available",
    "320": "320 kbps",
    "256": "256 kbps",
    "192": "192 kbps",
    "128": "128 kbps",
    "96": "96 kbps",
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="converterw",
        description=f"{APP_NAME} - download YouTube videos and audio from the terminal.",
        epilog=(
            "examples:\n"
            "  converterw https://youtu.be/VIDEO\n"
            "  converterw https://youtu.be/VIDEO -q 1080p -c mkv\n"
            "  converterw https://youtu.be/VIDEO --audio -a mp3 -b 320\n"
            "  converterw https://youtu.be/VIDEO --start 1:30 --end 2:15\n"
            "  converterw PLAYLIST_URL --items 1-5 -o ~/Music\n"
            "  converterw URL1 URL2 URL3 --audio\n"
            "  converterw --batch-file links.txt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("urls", nargs="*", metavar="URL",
                        help="YouTube video or playlist links - as many as you like")
    parser.add_argument("-o", "--output", metavar="DIR", default=None,
                        help=f"where to save (default: {DEFAULT_DOWNLOAD_DIR})")
    parser.add_argument("--batch-file", metavar="FILE",
                        help="also read links from FILE, one per line ('-' reads them "
                             "from stdin); lines starting with # are skipped")

    what = parser.add_argument_group("what to download")
    what.add_argument("--audio", action="store_true", help="extract audio instead of video")
    what.add_argument("-q", "--quality", choices=sorted(QUALITY_CHOICES), default="best",
                      metavar="Q", help="video quality: %(choices)s")
    what.add_argument("-c", "--container", choices=VIDEO_CONTAINERS, default="mp4",
                      metavar="EXT", help="video container: %(choices)s")
    what.add_argument("-a", "--audio-format", choices=AUDIO_FORMATS, default="mp3",
                      metavar="FMT", help="audio format: %(choices)s")
    what.add_argument("-b", "--bitrate", choices=sorted(BITRATE_CHOICES), default="best",
                      metavar="KBPS", help="audio bitrate: %(choices)s")

    part = parser.add_argument_group("download only part of a video")
    part.add_argument("--start", metavar="TIME", default="",
                      help="start at mm:ss, hh:mm:ss or seconds")
    part.add_argument("--end", metavar="TIME", default="",
                      help="stop at mm:ss, hh:mm:ss or seconds")

    extras = parser.add_argument_group("extras")
    extras.add_argument("--no-thumbnail", action="store_true", help="do not embed cover art")
    extras.add_argument("--no-metadata", action="store_true", help="do not embed tags or chapters")
    extras.add_argument("--subs", metavar="LANGS", default="",
                        help="embed subtitles, e.g. --subs en,es")
    extras.add_argument("--sponsorblock", action="store_true",
                        help="cut sponsor segments out (SponsorBlock)")
    extras.add_argument("--cookies-from-browser", choices=COOKIE_BROWSERS[1:], metavar="BROWSER",
                        help="use cookies from a browser for age-restricted videos")

    playlist = parser.add_argument_group("playlists")
    playlist.add_argument("--playlist", action="store_true",
                          help="also take the list a video link carries (a mix, usually)")
    playlist.add_argument("--no-playlist", action="store_true",
                          help="download one video only, even from a playlist link")
    playlist.add_argument("--items", metavar="RANGE", default="",
                          help="which entries to take, e.g. 1-5,8")
    playlist.add_argument("--flat", action="store_true",
                          help="do not put the playlist in its own folder")
    playlist.add_argument("--skip-existing", action="store_true",
                          help="skip anything already downloaded to this folder")

    other = parser.add_argument_group("other")
    other.add_argument("--info", action="store_true", help="show video details and exit")
    other.add_argument("-j", "--jobs", type=int, default=4, metavar="N",
                       help="parallel download fragments (default: 4)")
    other.add_argument("--quiet", action="store_true", help="only print errors")
    other.add_argument("--verbose", action="store_true", help="print yt-dlp's own output")
    other.add_argument("--update-engine", action="store_true",
                       help="download the newest yt-dlp and exit")
    other.add_argument("--reset-engine", action="store_true",
                       help="throw away the downloaded yt-dlp and exit")
    other.add_argument("--version", action="version",
                       version=f"{APP_NAME} {__version__} (yt-dlp {engine.current_version()})")
    return parser


def options_from_args(args) -> Options:
    saved = config.load()
    options = config.to_options(saved)

    options.mode = "audio" if args.audio else "video"
    options.quality = QUALITY_CHOICES[args.quality]
    options.container = args.container
    options.audio_format = args.audio_format
    options.audio_bitrate = BITRATE_CHOICES[args.bitrate]

    options.embed_thumbnail = not args.no_thumbnail
    options.embed_metadata = not args.no_metadata
    options.embed_subtitles = bool(args.subs)
    options.subtitle_languages = args.subs or "en"
    options.remove_sponsors = args.sponsorblock

    options.download_playlist = args.playlist
    options.no_playlist = args.no_playlist
    options.playlist_items = args.items
    options.playlist_subfolder = not args.flat
    options.skip_existing = args.skip_existing

    options.trim_enabled = bool(args.start or args.end)
    options.trim_start = args.start
    options.trim_end = args.end

    options.cookies_browser = args.cookies_from_browser or "None"
    options.concurrent_fragments = max(1, args.jobs)
    return options


class ProgressPrinter:
    """One rewriting status line, but only when stderr is a real terminal."""

    def __init__(self, quiet=False):
        self.quiet = quiet
        self.tty = sys.stderr.isatty()
        self._width = 0

    def __call__(self, data):
        if self.quiet:
            return
        if data["status"] == "processing":
            line = f"  converting {data['filename']}"
        else:
            line = (f"  {int(data['percent'] * 100):3d}%  {data['size']:>9}  "
                    f"{data['speed']:>11}  ETA {data['eta']}")
        if self.tty:
            self._width = max(self._width, len(line))
            sys.stderr.write("\r" + line.ljust(self._width))
            sys.stderr.flush()
        elif data["status"] == "processing":
            print(line.strip(), file=sys.stderr)

    def done(self):
        if self.tty and self._width and not self.quiet:
            sys.stderr.write("\r" + " " * self._width + "\r")
            sys.stderr.flush()


def _run_engine_update():
    print("Checking for a newer yt-dlp...")
    latest = engine.latest_version()
    if not latest:
        print("Could not reach PyPI.", file=sys.stderr)
        return 1
    if engine.parse_version(latest) <= engine.parse_version(engine.current_version()):
        print(f"Already up to date (yt-dlp {engine.current_version()}).")
        return 0
    staged = engine.download_update(version=latest)
    print(f"Downloaded yt-dlp {staged}; it will be used from the next run.")
    return 0


def read_batch_file(path):
    """Links from a file, one or more per line. Blank lines and lines starting
    with # are skipped, as in yt-dlp's own batch files."""
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(os.path.expanduser(path), encoding="utf-8-sig") as handle:
            text = handle.read()

    links = []
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            links.extend(split_links(line))
    return links


def _print_info(urls):
    """Details of each link; exits 1 if any of them could not be read."""
    failed = False
    for index, url in enumerate(urls):
        if len(urls) > 1:
            if index:
                print()
            print(f"[{index + 1}/{len(urls)}] {url}")
        try:
            info = probe(url)
        except Exception as error:
            print(f"error: {str(error).splitlines()[0]}", file=sys.stderr)
            failed = True
            continue
        if info["is_playlist"]:
            print(f"Playlist: {info['title']}")
            print(f"Videos:   {info['count']}")
            print(f"Total:    {format_duration(info['duration'])}")
        else:
            print(f"Title:    {info['title']}")
            print(f"Channel:  {info['uploader']}")
            print(f"Duration: {format_duration(info['duration'])}")
    return 1 if failed else 0


def _install_sigint_handler(downloader):
    """Ctrl-C should stop the download tidily rather than dump a traceback."""
    import signal

    def handler(_signum, _frame):
        downloader.cancel()

    try:
        signal.signal(signal.SIGINT, handler)
    except (ValueError, OSError):
        pass  # Not on the main thread; KeyboardInterrupt handling still applies.


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.update_engine:
        return _run_engine_update()
    if args.reset_engine:
        engine.reset()
        print("Engine reset; the bundled yt-dlp will be used from the next run.")
        return 0

    urls = list(args.urls)
    if args.batch_file:
        try:
            urls += read_batch_file(args.batch_file)
        except OSError as error:
            print(f"error: could not read {args.batch_file}: {error.strerror or error}",
                  file=sys.stderr)
            return 1
        if not urls:
            print(f"error: no links found in {args.batch_file}", file=sys.stderr)
            return 1
    urls = list(dict.fromkeys(urls))  # the same link twice would only download twice

    if not urls:
        parser.print_help()
        return 2

    if args.info:
        return _print_info(urls)

    out_dir = os.path.expanduser(args.output or DEFAULT_DOWNLOAD_DIR)
    options = options_from_args(args)

    if not has_ffmpeg():
        needs_ffmpeg = args.audio or options.trim_enabled or args.sponsorblock
        if needs_ffmpeg:
            print("error: ffmpeg was not found on your PATH, and it is required for this "
                  "download.", file=sys.stderr)
            print("       Install it with your package manager, e.g. "
                  "'sudo apt install ffmpeg'.", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"warning: {NO_FFMPEG_NOTE}", file=sys.stderr)

    progress = ProgressPrinter(quiet=args.quiet)
    log = (lambda message: print(message, file=sys.stderr)) if args.verbose else None
    downloader = Downloader(progress_callback=progress, log_callback=log)
    _install_sigint_handler(downloader)

    # Output is flushed as it goes, so it stays in order around stderr when
    # both are piped into the same log.
    what = "audio" if args.audio else "video"
    if not args.quiet:
        print(f"Downloading {what} to {out_dir}", flush=True)

    def on_start(index, url):
        if len(urls) > 1 and not args.quiet:
            progress.done()
            print(f"[{index + 1}/{len(urls)}] {url}", flush=True)

    try:
        batch = downloader.run_all(urls, out_dir, options, on_start=on_start)
    except KeyboardInterrupt:
        batch = None
    progress.done()

    if batch is None or batch.cancelled:
        finished = len(batch.done) if batch else 0
        if len(urls) > 1 and finished:
            print(f"Cancelled after {finished} of {len(urls)} links.", file=sys.stderr)
        else:
            print("Cancelled.", file=sys.stderr)
        return 130

    if not args.quiet:
        for path in batch.files:
            print(f"Saved {path}")
        sys.stdout.flush()

    for url, message in batch.failed:
        log_error(message, context=f"{what} download: {url}")
        if len(urls) == 1:
            print(f"error: {message}", file=sys.stderr)
        else:
            print(f"error: {url}\n       {brief_error(message)}", file=sys.stderr)

    if not args.quiet and batch.done:
        print(batch.summary(len(urls)))
    return 1 if batch.failed else 0


def entry_point():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    entry_point()
