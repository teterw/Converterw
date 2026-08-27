import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from converterw import engine
from converterw.paths import bundled_dir

# Must happen before yt_dlp is imported so a downloaded engine can take over
# from the (possibly stale) bundled copy.
engine.activate()

import yt_dlp  # noqa: E402

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

_FFMPEG_EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

# Ordered best-first; the label is what the GUI shows.
VIDEO_QUALITIES = [
    ("Best available", None),
    ("4K (2160p)", 2160),
    ("1440p", 1440),
    ("1080p", 1080),
    ("720p", 720),
    ("480p", 480),
    ("360p", 360),
    ("240p", 240),
]
VIDEO_QUALITY_LABELS = [label for label, _ in VIDEO_QUALITIES]
_QUALITY_HEIGHTS = dict(VIDEO_QUALITIES)

VIDEO_CONTAINERS = ["mp4", "mkv", "webm"]
AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav"]
AUDIO_BITRATES = ["Best available", "320 kbps", "256 kbps", "192 kbps", "128 kbps", "96 kbps"]
COOKIE_BROWSERS = ["None", "chrome", "edge", "firefox", "brave", "opera", "vivaldi"]

# Tried in order when a download comes back 403. YouTube periodically locks
# individual player clients out; another client usually still serves the media.
_CLIENT_FALLBACKS = [
    None,
    ["tv", "web_safari"],
    ["ios", "android"],
]

SPONSORBLOCK_CATEGORIES = ["sponsor", "selfpromo", "interaction", "intro", "outro", "preview"]


class Cancelled(yt_dlp.utils.DownloadCancelled):
    """Raised out of the progress hook when the user cancels a download.

    Subclasses yt-dlp's own cancellation error: any other exception type is
    swallowed per-video and the run simply continues to the next playlist item.
    """


@dataclass
class Options:
    """Everything the UI can choose about a download."""

    mode: str = "video"  # "video" or "audio"
    quality: str = "Best available"
    container: str = "mp4"
    audio_format: str = "mp3"
    audio_bitrate: str = "Best available"
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_subtitles: bool = False
    subtitle_languages: str = "en"
    remove_sponsors: bool = False
    # Off by default: a copied YouTube link usually carries a mix in "&list=",
    # and grabbing that whole mix is never what was wanted.
    download_playlist: bool = False
    # Hard override: never pull in a list, not even from a playlist link.
    no_playlist: bool = False
    playlist_items: str = ""
    playlist_subfolder: bool = True
    skip_existing: bool = False
    trim_enabled: bool = False
    trim_start: str = ""
    trim_end: str = ""
    cookies_browser: str = "None"
    concurrent_fragments: int = 4


def _ffmpeg_location():
    """Prefer the ffmpeg shipped with the app; fall back to letting yt-dlp search PATH."""
    for candidate_dir in (bundled_dir(), bundled_dir() / "vendor" / "ffmpeg"):
        if (candidate_dir / _FFMPEG_EXE).is_file():
            return str(candidate_dir)
    return None


def _put_ffmpeg_on_path():
    """Also expose the bundled ffmpeg through PATH.

    Most of yt-dlp honours the ffmpeg_location option, but the downloader used
    for partial downloads looks ffmpeg up on PATH only - without this, trimming
    fails with "ffmpeg is not installed" even though it is right there.
    """
    location = _ffmpeg_location()
    if not location:
        return
    path = os.environ.get("PATH", "")
    if location not in path.split(os.pathsep):
        os.environ["PATH"] = location + os.pathsep + path


_put_ffmpeg_on_path()


def has_ffmpeg() -> bool:
    if _ffmpeg_location():
        return True
    from shutil import which

    return which("ffmpeg") is not None


def is_playlist_only(url: str) -> bool:
    return "youtube.com/playlist" in url and "list=" in url


def is_video_url(url: str) -> bool:
    return "watch?v=" in url or "youtu.be/" in url


def is_video_in_playlist(url: str) -> bool:
    return is_video_url(url) and "list=" in url


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


def format_duration(seconds):
    if not seconds:
        return "?"
    return _format_eta(seconds)


_TIMECODE_PART = re.compile(r"^\d+(\.\d+)?$")


def parse_timecode(text):
    """'75', '1:15', '01:02:03' or '1:15.5' -> seconds. Blank input returns None."""
    text = (text or "").strip()
    if not text:
        return None

    parts = text.split(":")
    if len(parts) > 3 or not all(_TIMECODE_PART.match(part.strip()) for part in parts):
        raise ValueError(f'"{text}" is not a time. Use mm:ss, hh:mm:ss, or seconds.')

    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def _trim_range(options: Options):
    """(start, end) in seconds for the section to keep, or None for the lot."""
    if not options.trim_enabled:
        return None

    start = parse_timecode(options.trim_start)
    end = parse_timecode(options.trim_end)
    if start is None and end is None:
        return None
    if start is not None and end is not None and end <= start:
        raise ValueError("The end time has to be later than the start time.")
    return (start or 0.0, end if end is not None else float("inf"))


def _audio_quality(label):
    """'192 kbps' -> '192'; yt-dlp reads a bare number as a kbps target."""
    digits = "".join(ch for ch in label if ch.isdigit())
    return digits or "0"  # "0" means best available to FFmpegExtractAudio


def _format_selector(options: Options) -> str:
    """Build a yt-dlp format string, always with a fallback chain so an exact
    match never turns into "requested format not available"."""
    if options.mode == "audio":
        return "bestaudio/best"

    height = _QUALITY_HEIGHTS.get(options.quality)
    limit = f"[height<={height}]" if height else ""

    chain = []
    if options.container == "mp4":
        # Prefer H.264/AAC so the result plays everywhere without re-encoding.
        chain.append(f"bv*{limit}[ext=mp4]+ba[ext=m4a]")
    chain.append(f"bv*{limit}+ba")
    chain.append(f"b{limit}")
    if height:
        # Nothing at or below the requested height: take the smallest available.
        chain.append("wv*+ba/w")
    chain.append("bv*+ba/b")
    return "/".join(chain)


def _postprocessors(options: Options):
    """Mirror the order the yt-dlp command line uses, which matters: chapters
    are rewritten before the container is built, and tags go on last."""
    pps = []

    if options.remove_sponsors:
        pps.append({
            "key": "SponsorBlock",
            "categories": set(SPONSORBLOCK_CATEGORIES),
            "when": "after_filter",
        })
        pps.append({
            "key": "ModifyChapters",
            "remove_sponsor_segments": set(SPONSORBLOCK_CATEGORIES),
        })

    if options.mode == "audio":
        pps.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": options.audio_format,
            "preferredquality": _audio_quality(options.audio_bitrate),
        })
    elif options.embed_subtitles:
        pps.append({"key": "FFmpegEmbedSubtitle"})

    if options.embed_metadata:
        pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})

    if options.embed_thumbnail:
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    return pps


def wants_playlist(url, options: Options) -> bool:
    """Whether this URL should pull in a whole list.

    A bare playlist link always means the playlist. A video link that merely
    carries "&list=" means just that one video - copying a link out of YouTube
    usually drags a mix along with it, and downloading the entire radio mix is
    never what was meant. Setting no_playlist overrules both cases.
    """
    if options.no_playlist:
        return False
    if is_playlist_only(url):
        return True
    return options.download_playlist and is_video_in_playlist(url)


def _output_template(url, out_dir, options: Options):
    if wants_playlist(url, options) and options.playlist_subfolder:
        return os.path.join(out_dir, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s")
    return os.path.join(out_dir, "%(title)s.%(ext)s")


def build_options(url, out_dir, options: Options, progress_hooks=(), logger=None):
    """Translate our Options into the dict yt-dlp expects."""
    ydl_opts = {
        # "pl_thumbnail" is disabled so a playlist's own cover art is not left
        # sitting next to the downloaded files.
        "outtmpl": {"default": _output_template(url, out_dir, options), "pl_thumbnail": ""},
        "format": _format_selector(options),
        "noplaylist": not wants_playlist(url, options),
        "progress_hooks": list(progress_hooks),
        "postprocessors": _postprocessors(options),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": "only_download",
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": max(1, options.concurrent_fragments),
        "windowsfilenames": sys.platform == "win32",
        "restrictfilenames": False,
    }

    if logger is not None:
        ydl_opts["logger"] = logger

    if options.mode == "video":
        ydl_opts["merge_output_format"] = options.container

    if options.embed_thumbnail:
        ydl_opts["writethumbnail"] = True

    if options.embed_subtitles and options.mode == "video":
        languages = [lang.strip() for lang in options.subtitle_languages.split(",") if lang.strip()]
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitleslangs"] = languages or ["en"]

    if options.playlist_items.strip():
        ydl_opts["playlist_items"] = options.playlist_items.strip()

    if options.skip_existing:
        ydl_opts["download_archive"] = os.path.join(out_dir, ".converterw-archive.txt")

    trim = _trim_range(options)
    if trim:
        # force_keyframes_at_cuts re-encodes around the cut points; without it
        # the clip starts at the previous keyframe, which can be seconds early.
        ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(None, [trim])
        ydl_opts["force_keyframes_at_cuts"] = True

    if options.cookies_browser and options.cookies_browser != "None":
        ydl_opts["cookiesfrombrowser"] = (options.cookies_browser,)

    ffmpeg_location = _ffmpeg_location()
    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location

    return ydl_opts


def probe(url, timeout=30):
    """Fetch title/uploader/duration without downloading anything."""
    if not url:
        raise ValueError("URL is empty")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "socket_timeout": timeout,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries")
    if entries is not None:
        entries = [e for e in entries if e]
        return {
            "is_playlist": True,
            "title": info.get("title") or "Playlist",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "count": len(entries),
            "duration": sum(e.get("duration") or 0 for e in entries),
        }
    return {
        "is_playlist": False,
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "count": 1,
        "duration": info.get("duration") or 0,
    }


def _is_forbidden(error) -> bool:
    text = str(error).lower()
    return "403" in text or "forbidden" in text


class _CollectingLogger:
    """yt-dlp reports per-item failures through the logger instead of raising
    when a playlist is allowed to skip bad entries, so errors are collected
    here rather than caught."""

    def __init__(self, log_callback=None):
        self.errors = []
        self.warnings = []
        self._log_callback = log_callback

    def _emit(self, message):
        if self._log_callback:
            self._log_callback(message)

    def debug(self, message):
        # yt-dlp routes both debug and plain output here; only the latter is useful.
        if not message.startswith("[debug] "):
            self._emit(message)

    def info(self, message):
        self._emit(message)

    def warning(self, message):
        self.warnings.append(message)
        self._emit(message)

    def error(self, message):
        self.errors.append(message)
        self._emit(message)


class Downloader:
    """A single download job that can report progress and be cancelled."""

    def __init__(self, progress_callback=None, log_callback=None):
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self._cancelled = False
        # Video and audio arrive as separate streams that get merged, so count
        # distinct videos rather than finished downloads.
        self._finished_ids = set()

    def cancel(self):
        self._cancelled = True

    @property
    def cancelled(self):
        return self._cancelled

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def _hook(self, d):
        if self._cancelled:
            raise Cancelled()

        status = d.get("status")
        if status == "finished":
            info = d.get("info_dict") or {}
            self._finished_ids.add(info.get("id") or d.get("filename") or len(self._finished_ids))
        if not self.progress_callback:
            return

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0
            self.progress_callback({
                "percent": (downloaded / total) if total else 0.0,
                "size": _format_bytes(total) if total else "?",
                "speed": f"{_format_bytes(speed)}/s" if speed else "?",
                "eta": _format_eta(d.get("eta")),
                "filename": os.path.basename(d.get("filename") or ""),
                "status": "downloading",
            })
        elif status == "finished":
            self.progress_callback({
                "percent": 1.0,
                "size": _format_bytes(d.get("total_bytes") or 0),
                "speed": "-",
                "eta": "00:00",
                "filename": os.path.basename(d.get("filename") or ""),
                "status": "processing",
            })

    def _check_trim_fits(self, url, trim):
        """Reject a trim window that starts past the end of the video.

        ffmpeg is asked for a section that does not exist and dies with a bare
        "exited with code 4294967274", which says nothing about the real cause -
        an old trim range left switched on from an earlier download.
        """
        try:
            info = probe(url)
        except Exception:
            return  # Can't check: let the download report the real problem.

        duration = info.get("duration")
        if info.get("is_playlist") or not duration:
            return

        start = trim[0]
        if start >= duration:
            raise ValueError(
                f"This video is only {format_duration(duration)} long, but the "
                f"selected part starts at {format_duration(start)}.\n\n"
                'Change the start and end times, or turn off "Download only part '
                'of the video".'
            )

    def run(self, url, out_dir, options: Options):
        """Download `url` into `out_dir`.

        Returns {"completed": int, "errors": [str]} - a playlist that skipped a
        few unavailable videos still counts as done. Raises RuntimeError if
        nothing downloaded, or Cancelled if the user stopped it.
        """
        if not url:
            raise ValueError("URL is empty")
        if not out_dir:
            raise ValueError("No output folder selected")

        os.makedirs(out_dir, exist_ok=True)

        trim = _trim_range(options)
        if trim:
            self._check_trim_fits(url, trim)
        if trim and not has_ffmpeg():
            raise RuntimeError(
                "ffmpeg is required to trim a video but was not found.\n"
                "Use the bundled .exe build, or install ffmpeg and put it on your PATH."
            )

        if options.mode == "audio" and not has_ffmpeg():
            raise RuntimeError(
                "ffmpeg is required to convert audio but was not found.\n"
                "Use the bundled .exe build, or install ffmpeg and put it on your PATH."
            )

        last_errors = []
        saw_forbidden = False
        for clients in _CLIENT_FALLBACKS:
            if self._cancelled:
                raise Cancelled()

            self._finished_ids.clear()
            logger = _CollectingLogger(self.log_callback)
            ydl_opts = build_options(
                url, out_dir, options, progress_hooks=[self._hook], logger=logger
            )
            if clients:
                ydl_opts["extractor_args"] = {"youtube": {"player_client": clients}}
                self._log(f"Retrying with player client: {', '.join(clients)}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    retcode = ydl.download([url])
            except Cancelled:
                raise
            except yt_dlp.utils.DownloadError as error:
                # Raised only when yt-dlp is set to abort; playlist-tolerant runs
                # report failures through the logger instead.
                retcode = 1
                logger.errors.append(str(error))

            if retcode == 0 and not logger.errors:
                return {"completed": len(self._finished_ids), "errors": []}

            last_errors = logger.errors

            # A partial playlist run is a success with warnings, not a retry case.
            if self._finished_ids:
                return {
                    "completed": len(self._finished_ids),
                    "errors": list(logger.errors),
                }

            forbidden = any(_is_forbidden(message) for message in logger.errors)
            saw_forbidden = saw_forbidden or forbidden

            # Anything other than a 403 up front is a genuine failure (private
            # video, bad URL, disk full) and another client will not help.
            if not saw_forbidden:
                raise RuntimeError("Download failed:\n\n" + "\n".join(logger.errors[:5]))

            if forbidden:
                self._log("YouTube returned 403 Forbidden - trying another player client...")
            else:
                self._log("That player client failed too - trying the next one...")

        raise RuntimeError(
            "Download failed - YouTube refused every method this version knows about.\n\n"
            "This almost always means the downloader engine is out of date. Open the "
            "Advanced tab, click 'Update engine now', then restart Converterw and try "
            "again.\n\nDetails:\n"
            + "\n".join(last_errors[:3])
        )


# Kept so older scripts importing these keep working.
def download_mp3(url, out_dir, progress_callback=None):
    Downloader(progress_callback).run(url, out_dir, Options(mode="audio"))


def download_mp4(url, out_dir, progress_callback=None):
    Downloader(progress_callback).run(url, out_dir, Options(mode="video"))
