"""How Options turn into what yt-dlp is asked to do."""

import math

import pytest
import yt_dlp

from converterw import youtube
from converterw.youtube import Options, build_options, parse_timecode, wants_playlist

VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SHORT_LINK = "https://youtu.be/dQw4w9WgXcQ"
VIDEO_IN_MIX = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ&start_radio=1"
PLAYLIST = "https://www.youtube.com/playlist?list=PL590L5WQmH8fJ54F369BLDSqIwcs-TCfs"


# ------------------------------------------------------------------ timecodes

@pytest.mark.parametrize("text, seconds", [
    ("75", 75),
    ("1:15", 75),
    ("01:02:03", 3723),
    ("1:15.5", 75.5),
    ("  1:15  ", 75),
    ("0", 0),
])
def test_parse_timecode_accepts_common_forms(text, seconds):
    assert parse_timecode(text) == seconds


@pytest.mark.parametrize("text", ["", "   ", None])
def test_parse_timecode_blank_means_unset(text):
    assert parse_timecode(text) is None


@pytest.mark.parametrize("text", ["abc", "1:2:3:4", "-5", "1:", ":30", "1,5", "1:3o"])
def test_parse_timecode_rejects_garbage(text):
    with pytest.raises(ValueError, match="is not a time"):
        parse_timecode(text)


# ----------------------------------------------------------------------- trim

def test_trim_left_over_but_switched_off_is_ignored():
    # The bug fixed in af92511: old start/end values must do nothing once
    # the checkbox is unticked.
    options = Options(trim_enabled=False, trim_start="5:00", trim_end="6:00")
    assert youtube._trim_range(options) is None
    assert "download_ranges" not in build_options(VIDEO, "out", options)


def test_trim_enabled_but_empty_downloads_everything():
    assert youtube._trim_range(Options(trim_enabled=True)) is None


def test_trim_open_ended_ranges():
    start_only = Options(trim_enabled=True, trim_start="1:30")
    end_only = Options(trim_enabled=True, trim_end="0:45")
    assert youtube._trim_range(start_only) == (90, math.inf)
    assert youtube._trim_range(end_only) == (0.0, 45)


@pytest.mark.parametrize("start, end", [("2:00", "1:00"), ("1:00", "1:00")])
def test_trim_end_must_come_after_start(start, end):
    options = Options(trim_enabled=True, trim_start=start, trim_end=end)
    with pytest.raises(ValueError, match="later than the start"):
        youtube._trim_range(options)


def test_trim_is_passed_to_yt_dlp_as_a_download_range():
    options = Options(trim_enabled=True, trim_start="0:30", trim_end="1:45")
    ydl_opts = build_options(VIDEO, "out", options)

    sections = list(ydl_opts["download_ranges"]({}, None))
    assert sections == [{"start_time": 30, "end_time": 105}]
    assert ydl_opts["force_keyframes_at_cuts"] is True


# ------------------------------------------------------------------ playlists

def test_url_classification():
    assert youtube.is_playlist_only(PLAYLIST)
    assert not youtube.is_playlist_only(VIDEO_IN_MIX)
    assert youtube.is_video_url(VIDEO)
    assert youtube.is_video_url(SHORT_LINK)
    assert youtube.is_video_in_playlist(VIDEO_IN_MIX)
    assert youtube.is_video_in_playlist(SHORT_LINK + "?list=PLabc")
    assert not youtube.is_video_in_playlist(VIDEO)


def test_playlist_link_means_the_playlist():
    assert wants_playlist(PLAYLIST, Options())


def test_video_link_carrying_a_mix_means_just_the_video():
    # The other regression fixed in af92511.
    assert not wants_playlist(VIDEO_IN_MIX, Options())
    assert build_options(VIDEO_IN_MIX, "out", Options())["noplaylist"] is True


def test_download_playlist_opts_into_the_carried_list():
    options = Options(download_playlist=True)
    assert wants_playlist(VIDEO_IN_MIX, options)
    assert not wants_playlist(VIDEO, options)


def test_no_playlist_overrides_everything():
    options = Options(no_playlist=True, download_playlist=True)
    assert not wants_playlist(PLAYLIST, options)
    assert not wants_playlist(VIDEO_IN_MIX, options)


def test_playlist_gets_its_own_folder_unless_flat(tmp_path):
    nested = build_options(PLAYLIST, str(tmp_path), Options())
    flat = build_options(PLAYLIST, str(tmp_path), Options(playlist_subfolder=False))
    single = build_options(VIDEO, str(tmp_path), Options())

    assert "%(playlist_title)s" in nested["outtmpl"]["default"]
    assert "%(playlist_title)s" not in flat["outtmpl"]["default"]
    assert "%(playlist_title)s" not in single["outtmpl"]["default"]


def test_playlist_items_are_trimmed_and_passed_through():
    ydl_opts = build_options(PLAYLIST, "out", Options(playlist_items=" 1-5,8 "))
    assert ydl_opts["playlist_items"] == "1-5,8"
    assert "playlist_items" not in build_options(PLAYLIST, "out", Options())


# --------------------------------------------------------------------- format

@pytest.mark.parametrize("quality", youtube.VIDEO_QUALITY_LABELS)
@pytest.mark.parametrize("container", youtube.VIDEO_CONTAINERS)
def test_every_format_selector_is_valid_and_has_a_catch_all(quality, container):
    selector = youtube._format_selector(Options(quality=quality, container=container))

    # yt-dlp's own parser raises SyntaxError on a malformed spec.
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.build_format_selector(selector)

    # Whatever the quality, the chain must end in "anything at all", so an
    # exact request never becomes "requested format is not available".
    assert selector.endswith("bv*+ba/b")


def test_mp4_prefers_natively_compatible_streams():
    assert youtube._format_selector(Options(container="mp4")).startswith("bv*[ext=mp4]+ba[ext=m4a]")
    assert "[ext=mp4]" not in youtube._format_selector(Options(container="mkv"))


def test_quality_caps_height():
    selector = youtube._format_selector(Options(quality="1080p"))
    assert "[height<=1080]" in selector
    assert "[height<=" not in youtube._format_selector(Options(quality="Best available"))


def test_audio_takes_the_best_audio_stream():
    assert youtube._format_selector(Options(mode="audio")) == "bestaudio/best"


# ------------------------------------------------------------ postprocessors

def _keys(options):
    return [pp["key"] for pp in youtube._postprocessors(options)]


def test_audio_postprocessor_order():
    assert _keys(Options(mode="audio")) == ["FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]


def test_sponsorblock_runs_before_anything_else():
    keys = _keys(Options(remove_sponsors=True))
    assert keys[:2] == ["SponsorBlock", "ModifyChapters"]


def test_subtitles_are_embedded_before_tags_and_only_for_video():
    assert _keys(Options(embed_subtitles=True)) == ["FFmpegEmbedSubtitle", "FFmpegMetadata", "EmbedThumbnail"]
    assert "FFmpegEmbedSubtitle" not in _keys(Options(mode="audio", embed_subtitles=True))


def test_embedding_can_be_switched_off():
    assert _keys(Options(embed_thumbnail=False, embed_metadata=False)) == []


@pytest.mark.parametrize("label, quality", [
    ("Best available", "0"),
    ("320 kbps", "320"),
    ("96 kbps", "96"),
])
def test_bitrate_label_becomes_a_yt_dlp_quality(label, quality):
    extract = youtube._postprocessors(Options(mode="audio", audio_bitrate=label))[0]
    assert extract["preferredquality"] == quality


@pytest.mark.parametrize("options", [
    Options(),
    Options(mode="audio", audio_format="flac", audio_bitrate="320 kbps"),
    Options(remove_sponsors=True, embed_subtitles=True, subtitle_languages="en,es"),
    Options(container="mkv", quality="720p", embed_thumbnail=False, embed_metadata=False),
    Options(trim_enabled=True, trim_start="1:00", skip_existing=True),
], ids=["defaults", "audio", "everything-on", "everything-off", "trim+archive"])
def test_yt_dlp_accepts_the_options_we_build(options, tmp_path):
    # Constructing YoutubeDL instantiates every postprocessor, so a misspelt
    # key or argument fails here - offline - instead of mid-download.
    with yt_dlp.YoutubeDL(build_options(VIDEO, str(tmp_path), options)):
        pass


# ----------------------------------------------------------------- the rest

def test_subtitle_languages_are_cleaned_up():
    ydl_opts = build_options(VIDEO, "out", Options(embed_subtitles=True, subtitle_languages=" en , es ,"))
    assert ydl_opts["subtitleslangs"] == ["en", "es"]

    blank = build_options(VIDEO, "out", Options(embed_subtitles=True, subtitle_languages=" , "))
    assert blank["subtitleslangs"] == ["en"]


def test_audio_mode_never_asks_for_subtitles():
    ydl_opts = build_options(VIDEO, "out", Options(mode="audio", embed_subtitles=True))
    assert "writesubtitles" not in ydl_opts


def test_cookies_only_when_a_browser_is_chosen():
    assert "cookiesfrombrowser" not in build_options(VIDEO, "out", Options(cookies_browser="None"))
    chosen = build_options(VIDEO, "out", Options(cookies_browser="firefox"))
    assert chosen["cookiesfrombrowser"] == ("firefox",)


def test_skip_existing_keeps_its_archive_in_the_output_folder(tmp_path):
    ydl_opts = build_options(VIDEO, str(tmp_path), Options(skip_existing=True))
    assert ydl_opts["download_archive"] == str(tmp_path / ".converterw-archive.txt")


def test_container_only_applies_to_video():
    assert build_options(VIDEO, "out", Options(container="mkv"))["merge_output_format"] == "mkv"
    assert "merge_output_format" not in build_options(VIDEO, "out", Options(mode="audio"))


def test_fragment_count_is_at_least_one():
    ydl_opts = build_options(VIDEO, "out", Options(concurrent_fragments=0))
    assert ydl_opts["concurrent_fragment_downloads"] == 1


@pytest.mark.parametrize("value, text", [
    (0, "0B"),
    (None, "0B"),
    (512, "512.0B"),
    (1536, "1.5KiB"),
    (5 * 1024 ** 3, "5.0GiB"),
])
def test_format_bytes(value, text):
    assert youtube._format_bytes(value) == text


@pytest.mark.parametrize("seconds, text", [
    (None, "--:--"),
    (5, "00:05"),
    (65.9, "01:05"),
    (3723, "01:02:03"),
])
def test_format_eta(seconds, text):
    assert youtube._format_eta(seconds) == text


def test_format_duration_of_nothing_is_unknown():
    assert youtube.format_duration(0) == "?"
    assert youtube.format_duration(None) == "?"
    assert youtube.format_duration(213) == "03:33"


# ---------------------------------------------------------------- no ffmpeg

@pytest.mark.parametrize("quality", youtube.VIDEO_QUALITY_LABELS)
def test_without_ffmpeg_only_ready_made_formats_are_picked(quality):
    selector = youtube._format_selector(Options(quality=quality), ffmpeg=False)

    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.build_format_selector(selector)
    assert "+" not in selector  # "+" asks for streams to be merged by ffmpeg
    assert selector.endswith("/b")


def test_without_ffmpeg_nothing_is_embedded(tmp_path):
    options = Options(embed_subtitles=True, container="mkv")
    ydl_opts = build_options(VIDEO, str(tmp_path), options, ffmpeg=False)

    assert ydl_opts["postprocessors"] == []
    assert "writethumbnail" not in ydl_opts
    assert "merge_output_format" not in ydl_opts
    # Subtitles can't be embedded, but are still saved beside the video.
    assert ydl_opts["writesubtitles"] is True
    with yt_dlp.YoutubeDL(ydl_opts):
        pass


def test_ffmpeg_is_looked_for_when_not_stated(monkeypatch):
    monkeypatch.setattr(youtube, "has_ffmpeg", lambda: False)
    assert build_options(VIDEO, "out", Options())["postprocessors"] == []


# -------------------------------------------------------------------- links

@pytest.mark.parametrize("text, links", [
    (VIDEO, [VIDEO]),
    (f"{VIDEO}\n{SHORT_LINK}\n", [VIDEO, SHORT_LINK]),
    (f"  {VIDEO}   {PLAYLIST}  ", [VIDEO, PLAYLIST]),
    (f"{VIDEO},{SHORT_LINK}", [VIDEO, SHORT_LINK]),
    (f"{VIDEO}\n{VIDEO}\n{SHORT_LINK}", [VIDEO, SHORT_LINK]),
    (f"check this out: {SHORT_LINK}.", [SHORT_LINK]),
    (f"({SHORT_LINK})", [SHORT_LINK]),
    ("youtu.be/dQw4w9WgXcQ", ["youtu.be/dQw4w9WgXcQ"]),
    ("www.youtube.com/watch?v=dQw4w9WgXcQ", ["www.youtube.com/watch?v=dQw4w9WgXcQ"]),
    ("https://vimeo.com/76979871", ["https://vimeo.com/76979871"]),
], ids=["one", "lines", "spaces", "commas", "repeats", "prose", "brackets",
        "no-scheme", "www", "other-site"])
def test_split_links(text, links):
    assert youtube.split_links(text) == links


def test_text_without_links_is_passed_through_for_yt_dlp_to_judge():
    assert youtube.split_links("  dQw4w9WgXcQ ") == ["dQw4w9WgXcQ"]


@pytest.mark.parametrize("text", ["", "   \n ", None])
def test_no_text_no_links(text):
    assert youtube.split_links(text) == []


@pytest.mark.parametrize("message, brief", [
    ("Download failed:\n\nERROR: [youtube] x: Private video\nERROR: other",
     "ERROR: [youtube] x: Private video"),
    ("This video is only 03:00 long, but...\n\nChange the start", "This video is only 03:00 long, but..."),
    ("", "Unknown error"),
])
def test_brief_error(message, brief):
    assert youtube.brief_error(message) == brief
