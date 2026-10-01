"""Downloader: retries, partial playlists, batches, cancelling and early refusals.

yt-dlp is replaced with a scripted fake, so these run offline and fast.
"""

import pytest
import yt_dlp

from converterw import youtube
from converterw.youtube import NO_FFMPEG_NOTE, BatchResult, Cancelled, Downloader, Options

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
FORBIDDEN = "ERROR: unable to download video data: HTTP Error 403: Forbidden"


class FakeRun:
    """What one scripted ydl.download() call can do to the Downloader."""

    def __init__(self, opts, url):
        self.opts = opts
        self.url = url

    def progress(self, **status):
        self.opts["progress_hooks"][0](status)

    def finished(self, video_id, filename="clip.mp4"):
        self.progress(status="finished", info_dict={"id": video_id}, filename=filename)

    def saved(self, path):
        for hook in self.opts["post_hooks"]:
            hook(path)

    def error(self, message):
        self.opts["logger"].error(message)


@pytest.fixture
def fake_ydl(monkeypatch):
    """Swap yt_dlp.YoutubeDL for a fake that plays one scripted step per attempt.

    Each step is a function (run: FakeRun) -> return code, standing in for one
    whole ydl.download() call. Returns the list of runs, one per attempt.
    """
    runs = []

    def install(*steps):
        class FakeYoutubeDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def download(self, urls):
                run = FakeRun(self.opts, urls[0])
                runs.append(run)
                return steps[len(runs) - 1](run)

        monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
        return runs

    return install


def ok(run):
    run.finished("abc")
    run.saved("/downloads/clip.mp4")
    return 0


def forbidden(run):
    run.error(FORBIDDEN)
    return 1


def fails_with(message):
    def step(run):
        run.error(message)
        return 1
    return step


def players(run):
    return (run.opts.get("extractor_args") or {}).get("youtube", {}).get("player_client")


# ------------------------------------------------------------------ outcomes

def test_success_on_the_first_try(fake_ydl, tmp_path):
    runs = fake_ydl(ok)
    result = Downloader().run(URL, str(tmp_path), Options())

    assert result == {"completed": 1, "errors": [], "files": ["/downloads/clip.mp4"]}
    assert len(runs) == 1
    assert players(runs[0]) is None


def test_403_falls_back_to_another_player_client(fake_ydl, tmp_path):
    runs = fake_ydl(forbidden, ok)
    logs = []
    result = Downloader(log_callback=logs.append).run(URL, str(tmp_path), Options())

    assert result["completed"] == 1
    assert [players(run) for run in runs] == [None, ["tv", "web_safari"]]
    assert any("403" in line for line in logs)


def test_403_from_every_client_points_at_the_engine_update(fake_ydl, tmp_path):
    runs = fake_ydl(forbidden, forbidden, forbidden)

    with pytest.raises(RuntimeError, match="Update engine now"):
        Downloader().run(URL, str(tmp_path), Options())
    assert len(runs) == len(youtube._CLIENT_FALLBACKS)


def test_other_failures_are_not_retried(fake_ydl, tmp_path):
    runs = fake_ydl(fails_with("ERROR: [youtube] dQw4w9WgXcQ: Private video"), ok)

    with pytest.raises(RuntimeError, match="Private video"):
        Downloader().run(URL, str(tmp_path), Options())
    assert len(runs) == 1


def test_an_aborting_download_error_counts_as_a_failure(fake_ydl, tmp_path):
    def raises(run):
        raise yt_dlp.utils.DownloadError("ERROR: Unsupported URL")

    fake_ydl(raises)
    with pytest.raises(RuntimeError, match="Unsupported URL"):
        Downloader().run(URL, str(tmp_path), Options())


def test_playlist_with_some_unavailable_videos_still_succeeds(fake_ydl, tmp_path):
    def partial(run):
        run.finished("one")
        run.saved("/downloads/01 - one.mp4")
        run.error("ERROR: [youtube] two: Video unavailable")
        run.finished("three")
        run.saved("/downloads/03 - three.mp4")
        return 1

    runs = fake_ydl(partial)
    result = Downloader().run(URL, str(tmp_path), Options())

    assert result["completed"] == 2
    assert result["errors"] == ["ERROR: [youtube] two: Video unavailable"]
    assert result["files"] == ["/downloads/01 - one.mp4", "/downloads/03 - three.mp4"]
    assert len(runs) == 1


def test_separate_video_and_audio_streams_count_as_one_file(fake_ydl, tmp_path):
    def merged(run):
        run.finished("abc", "clip.f137.mp4")
        run.finished("abc", "clip.f140.m4a")
        run.saved("/downloads/clip.mp4")
        return 0

    fake_ydl(merged)
    result = Downloader().run(URL, str(tmp_path), Options())
    assert result["completed"] == 1
    assert result["files"] == ["/downloads/clip.mp4"]


# ------------------------------------------------------------- several links

def test_batch_downloads_every_link_in_order(fake_ydl, tmp_path):
    def saves(name):
        def step(run):
            run.finished(name)
            run.saved(f"/downloads/{name}.mp4")
            return 0
        return step

    runs = fake_ydl(saves("a"), saves("b"), saves("c"))
    started = []
    batch = Downloader().run_all(["u1", "u2", "u3"], str(tmp_path), Options(),
                                 on_start=lambda index, url: started.append((index, url)))

    assert [run.url for run in runs] == ["u1", "u2", "u3"]
    assert started == [(0, "u1"), (1, "u2"), (2, "u3")]
    assert [url for url, _result in batch.done] == ["u1", "u2", "u3"]
    assert batch.files == ["/downloads/a.mp4", "/downloads/b.mp4", "/downloads/c.mp4"]
    assert batch.completed == 3
    assert not batch.failed and not batch.cancelled


def test_one_bad_link_does_not_stop_the_batch(fake_ydl, tmp_path):
    runs = fake_ydl(ok, fails_with("ERROR: [youtube] x: Private video"), ok)
    batch = Downloader().run_all(["u1", "u2", "u3"], str(tmp_path), Options())

    assert len(runs) == 3
    assert [url for url, _result in batch.done] == ["u1", "u3"]
    assert len(batch.failed) == 1
    url, message = batch.failed[0]
    assert url == "u2" and "Private video" in message


def test_refused_link_is_a_failure_not_a_crash(fake_ydl, tmp_path):
    fake_ydl(ok)
    batch = Downloader().run_all(["", "u2"], str(tmp_path), Options())
    assert batch.failed == [("", "URL is empty")]
    assert [url for url, _result in batch.done] == ["u2"]


def test_cancel_stops_the_rest_of_the_batch(fake_ydl, tmp_path):
    downloader = Downloader()

    def user_cancels(run):
        downloader.cancel()
        run.progress(status="downloading", downloaded_bytes=10, total_bytes=100)
        return 0

    runs = fake_ydl(ok, user_cancels, ok)
    batch = downloader.run_all(["u1", "u2", "u3"], str(tmp_path), Options())

    assert batch.cancelled
    assert [url for url, _result in batch.done] == ["u1"]
    assert len(runs) == 2


def test_batch_totals_add_up():
    batch = BatchResult(done=[
        ("u1", {"completed": 1, "errors": [], "files": ["a.mp4"]}),
        ("u2", {"completed": 2, "errors": ["gone"], "files": ["b.mp4", "c.mp4"]}),
    ])
    assert batch.completed == 3
    assert batch.skipped == 1
    assert batch.files == ["a.mp4", "b.mp4", "c.mp4"]


# ---------------------------------------------------------------- cancelling

def test_cancel_during_a_download_stops_it(fake_ydl, tmp_path):
    downloader = Downloader()

    def user_cancels(run):
        downloader.cancel()
        run.progress(status="downloading", downloaded_bytes=10, total_bytes=100)
        return 0

    runs = fake_ydl(user_cancels, ok)
    with pytest.raises(Cancelled):
        downloader.run(URL, str(tmp_path), Options())
    assert len(runs) == 1


def test_cancel_is_yt_dlps_own_cancellation():
    # Any other exception type is swallowed per video by yt-dlp, and the run
    # would just carry on to the next playlist item.
    assert issubclass(Cancelled, yt_dlp.utils.DownloadCancelled)


# ------------------------------------------------------------------ progress

def test_progress_is_reported_in_display_units(fake_ydl, tmp_path):
    def downloading(run):
        run.progress(status="downloading", downloaded_bytes=512 * 1024,
                     total_bytes=1024 * 1024, speed=2048, eta=65,
                     filename="/some/dir/clip.mp4")
        run.finished("abc")
        return 0

    fake_ydl(downloading)
    updates = []
    Downloader(progress_callback=updates.append).run(URL, str(tmp_path), Options())

    assert updates[0] == {
        "percent": 0.5,
        "size": "1.0MiB",
        "speed": "2.0KiB/s",
        "eta": "01:05",
        "filename": "clip.mp4",
        "status": "downloading",
    }
    assert updates[-1]["status"] == "processing"
    assert updates[-1]["percent"] == 1.0


def test_unknown_size_does_not_divide_by_zero(fake_ydl, tmp_path):
    def no_size(run):
        run.progress(status="downloading", downloaded_bytes=1000)
        return 0

    fake_ydl(no_size)
    updates = []
    Downloader(progress_callback=updates.append).run(URL, str(tmp_path), Options())
    assert updates[0]["percent"] == 0.0
    assert updates[0]["size"] == "?"


# --------------------------------------------------------------- no ffmpeg

def test_video_without_ffmpeg_downloads_a_single_ready_made_file(fake_ydl, no_ffmpeg, tmp_path):
    runs = fake_ydl(ok)
    logs = []
    Downloader(log_callback=logs.append).run(URL, str(tmp_path), Options(quality="1080p"))

    opts = runs[0].opts
    # Nothing that would need merging, converting or embedding afterwards -
    # otherwise yt-dlp leaves a silent video next to a separate audio file.
    assert "+" not in opts["format"]
    assert opts["postprocessors"] == []
    assert "writethumbnail" not in opts
    assert NO_FFMPEG_NOTE in logs
    # The android client is the one that still serves a combined format.
    assert players(runs[0]) == ["default", "android"]
    assert not any("Retrying" in line for line in logs)


def test_without_ffmpeg_a_video_with_no_combined_format_says_why(fake_ydl, no_ffmpeg, tmp_path):
    no_format = "ERROR: [youtube] x: Requested format is not available. Use --list-formats"
    runs = fake_ydl(fails_with(no_format))

    with pytest.raises(RuntimeError, match="joining them needs ffmpeg"):
        Downloader().run(URL, str(tmp_path), Options())
    assert len(runs) == 1


def test_with_ffmpeg_the_default_clients_are_used(fake_ydl, tmp_path):
    runs = fake_ydl(ok)
    Downloader().run(URL, str(tmp_path), Options())
    assert players(runs[0]) is None


@pytest.mark.parametrize("options", [
    Options(mode="audio"),
    Options(trim_enabled=True, trim_start="0:10"),
    Options(remove_sponsors=True),
], ids=["audio", "trim", "sponsorblock"])
def test_ffmpeg_jobs_are_refused_without_ffmpeg(fake_ydl, monkeypatch, no_ffmpeg, options, tmp_path):
    runs = fake_ydl(ok)
    monkeypatch.setattr(youtube, "probe", lambda url: {"is_playlist": False, "duration": 600})

    with pytest.raises(RuntimeError, match="ffmpeg is required"):
        Downloader().run(URL, str(tmp_path), options)
    assert runs == []


# ----------------------------------------------------- refusing up front

def test_trim_past_the_end_of_the_video_is_refused(fake_ydl, monkeypatch, tmp_path):
    runs = fake_ydl(ok)
    monkeypatch.setattr(youtube, "probe", lambda url: {"is_playlist": False, "duration": 180})
    options = Options(trim_enabled=True, trim_start="5:00")

    with pytest.raises(ValueError, match=r"only 03:00 long.*starts at 05:00"):
        Downloader().run(URL, str(tmp_path), options)
    assert runs == []


def test_trim_check_gives_way_when_the_video_cannot_be_probed(fake_ydl, monkeypatch, tmp_path):
    def offline(url):
        raise OSError("network down")

    runs = fake_ydl(ok)
    monkeypatch.setattr(youtube, "probe", offline)
    options = Options(trim_enabled=True, trim_start="5:00")

    Downloader().run(URL, str(tmp_path), options)
    assert len(runs) == 1


@pytest.mark.parametrize("url, out_dir, message", [
    ("", "out", "URL is empty"),
    (URL, "", "No output folder"),
])
def test_missing_input_is_refused(url, out_dir, message):
    with pytest.raises(ValueError, match=message):
        Downloader().run(url, out_dir, Options())


def test_output_folder_is_created(fake_ydl, tmp_path):
    fake_ydl(ok)
    target = tmp_path / "new" / "folder"
    Downloader().run(URL, str(target), Options())
    assert target.is_dir()
