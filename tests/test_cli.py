"""The `converterw` command: argument mapping and exit codes."""

import io
import json

import pytest

from converterw import cli, paths
from converterw.youtube import Cancelled, Downloader

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def parse(*argv):
    return cli.options_from_args(cli.build_parser().parse_args([URL, *argv]))


# ------------------------------------------------------------------- options

def test_defaults():
    options = parse()
    assert options.mode == "video"
    assert options.quality == "Best available"
    assert options.container == "mp4"
    assert options.trim_enabled is False
    assert options.cookies_browser == "None"


@pytest.mark.parametrize("flag, label", [("4k", "4K (2160p)"), ("2160p", "4K (2160p)"),
                                         ("1080p", "1080p"), ("best", "Best available")])
def test_quality_names(flag, label):
    assert parse("-q", flag).quality == label


def test_audio_options():
    options = parse("--audio", "-a", "flac", "-b", "320")
    assert options.mode == "audio"
    assert options.audio_format == "flac"
    assert options.audio_bitrate == "320 kbps"


def test_either_end_of_a_range_turns_trimming_on():
    assert parse("--start", "1:30").trim_enabled
    assert parse("--end", "2:15").trim_enabled
    both = parse("--start", "1:30", "--end", "2:15")
    assert (both.trim_start, both.trim_end) == ("1:30", "2:15")


def test_extras_and_playlist_flags():
    options = parse("--subs", "en,es", "--sponsorblock", "--no-thumbnail", "--no-metadata",
                    "--items", "1-5", "--flat", "--skip-existing", "--playlist",
                    "--cookies-from-browser", "firefox", "-j", "0")
    assert options.embed_subtitles and options.subtitle_languages == "en,es"
    assert options.remove_sponsors
    assert not options.embed_thumbnail and not options.embed_metadata
    assert options.playlist_items == "1-5"
    assert not options.playlist_subfolder
    assert options.skip_existing and options.download_playlist
    assert options.cookies_browser == "firefox"
    assert options.concurrent_fragments == 1


def test_gui_settings_never_leak_into_the_command_line(isolated_settings):
    # A trim range or cookie choice left behind in the GUI must not silently
    # apply to a terminal download - the CLI says exactly what it does.
    isolated_settings.write_text(json.dumps({
        "trim_enabled": True, "trim_start": "5:00", "trim_end": "6:00",
        "cookies_browser": "chrome", "remove_sponsors": True,
        "download_playlist": True, "playlist_items": "3-4",
    }), encoding="utf-8")

    options = parse()
    assert options.trim_enabled is False
    assert options.cookies_browser == "None"
    assert options.remove_sponsors is False
    assert options.download_playlist is False
    assert options.playlist_items == ""


def test_unknown_choice_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.build_parser().parse_args([URL, "-q", "8k"])
    assert exit_info.value.code == 2


# ---------------------------------------------------------------- exit codes

URL2 = "https://youtu.be/9bZkp7q19f0"
URL3 = "https://youtu.be/kJQP7kiw5Fk"


def saved(*files):
    return {"completed": len(files), "errors": [], "files": list(files)}


@pytest.fixture
def fake_run(monkeypatch, tmp_path):
    """Run `converterw` with each link's download outcome chosen up front.

    The real batch loop runs; only the single download behind it is faked.
    The returned runner's .calls lists the links that were downloaded.
    """
    monkeypatch.setattr(cli, "_install_sigint_handler", lambda downloader: None)
    monkeypatch.setattr(cli, "has_ffmpeg", lambda: True)
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)

    def install(*outcomes):
        """One outcome per link, in order: a result dict or an exception."""
        queue = list(outcomes)
        calls = []

        class FakeDownloader(Downloader):
            def run(self, url, out_dir, options):
                calls.append(url)
                outcome = queue.pop(0)
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome

        monkeypatch.setattr(cli, "Downloader", FakeDownloader)

        def run(*argv):
            return cli.main(["-o", str(tmp_path), *argv])

        run.calls = calls
        return run

    return install


def test_success_exits_zero(fake_run, capsys):
    run = fake_run(saved("/videos/clip.mp4"))
    assert run(URL) == 0
    out = capsys.readouterr().out
    assert "Saved /videos/clip.mp4" in out
    assert "Done - 1 file saved." in out


def test_partial_playlist_reports_skipped_items(fake_run, capsys):
    run = fake_run({"completed": 3, "errors": ["a", "b"], "files": ["1", "2", "3"]})
    assert run(URL) == 0
    assert "3 files saved, 2 skipped" in capsys.readouterr().out


def test_quiet_prints_nothing_on_success(fake_run, capsys):
    run = fake_run(saved("/videos/clip.mp4"))
    assert run(URL, "--quiet") == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_failure_exits_one_and_is_logged(fake_run, capsys, tmp_path):
    run = fake_run(RuntimeError("Download failed:\n\nERROR: Private video"))
    assert run(URL) == 1
    assert "Private video" in capsys.readouterr().err
    assert "Private video" in (tmp_path / "errors.log").read_text(encoding="utf-8")


@pytest.mark.parametrize("interruption", [Cancelled(), KeyboardInterrupt()])
def test_cancel_exits_130(fake_run, interruption):
    assert fake_run(interruption)(URL) == 130


def test_no_url_shows_help_and_exits_two(capsys):
    assert cli.main([]) == 2
    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["--audio"], ["--start", "1:00"], ["--sponsorblock"]])
def test_jobs_needing_ffmpeg_fail_fast_without_it(fake_run, monkeypatch, capsys, argv):
    run = fake_run(saved("clip.mp4"))
    monkeypatch.setattr(cli, "has_ffmpeg", lambda: False)
    assert run(URL, *argv) == 1
    assert "ffmpeg" in capsys.readouterr().err
    assert run.calls == []


def test_plain_video_without_ffmpeg_only_warns(fake_run, monkeypatch, capsys):
    run = fake_run(saved("clip.mp4"))
    monkeypatch.setattr(cli, "has_ffmpeg", lambda: False)
    assert run(URL) == 0
    assert "warning: ffmpeg was not found" in capsys.readouterr().err


# ------------------------------------------------------------- several links

def test_several_links_download_in_turn(fake_run, capsys):
    run = fake_run(saved("/v/one.mp4"), saved("/v/two.mp4"))
    assert run(URL, URL2) == 0
    assert run.calls == [URL, URL2]

    out = capsys.readouterr().out
    assert f"[1/2] {URL}" in out and f"[2/2] {URL2}" in out
    assert "Saved /v/one.mp4" in out and "Saved /v/two.mp4" in out
    assert "Done - 2 links, 2 files saved." in out


def test_a_failed_link_is_reported_and_the_rest_still_run(fake_run, capsys, tmp_path):
    run = fake_run(saved("/v/one.mp4"),
                   RuntimeError("Download failed:\n\nERROR: [youtube] x: Private video"),
                   saved("/v/three.mp4"))
    assert run(URL, URL2, URL3) == 1
    assert run.calls == [URL, URL2, URL3]

    captured = capsys.readouterr()
    assert f"error: {URL2}" in captured.err
    assert "ERROR: [youtube] x: Private video" in captured.err
    assert "Done - 2 of 3 links, 2 files saved. 1 link failed." in captured.out
    assert URL2 in (tmp_path / "errors.log").read_text(encoding="utf-8")


def test_cancel_stops_the_remaining_links(fake_run, capsys):
    run = fake_run(saved("/v/one.mp4"), Cancelled(), saved("/v/three.mp4"))
    assert run(URL, URL2, URL3) == 130
    assert run.calls == [URL, URL2]
    assert "Cancelled after 1 of 3 links." in capsys.readouterr().err


def test_repeated_links_download_once(fake_run):
    run = fake_run(saved("a"), saved("b"))
    assert run(URL, URL2, URL) == 0
    assert run.calls == [URL, URL2]


def test_batch_file(fake_run, tmp_path):
    links = tmp_path / "links.txt"
    links.write_text(f"# my list\n\n{URL2}\n  {URL3}  \n{URL}\n", encoding="utf-8")
    run = fake_run(saved("a"), saved("b"), saved("c"))

    assert run(URL, "--batch-file", str(links)) == 0
    assert run.calls == [URL, URL2, URL3]


def test_batch_file_from_stdin(fake_run, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{URL}\n{URL2}\n"))
    run = fake_run(saved("a"), saved("b"))

    assert run("--batch-file", "-") == 0
    assert run.calls == [URL, URL2]


def test_missing_batch_file(fake_run, capsys, tmp_path):
    run = fake_run()
    assert run("--batch-file", str(tmp_path / "nope.txt")) == 1
    assert "could not read" in capsys.readouterr().err


def test_batch_file_with_no_links(fake_run, capsys, tmp_path):
    links = tmp_path / "links.txt"
    links.write_text("# nothing here yet\n\n", encoding="utf-8")
    assert fake_run()("--batch-file", str(links)) == 1
    assert "no links found" in capsys.readouterr().err


# ---------------------------------------------------------------------- info

def test_info_prints_details_without_downloading(monkeypatch, capsys):
    monkeypatch.setattr(cli, "probe", lambda url: {
        "is_playlist": False, "title": "Never Gonna Give You Up",
        "uploader": "Rick Astley", "count": 1, "duration": 213,
    })
    assert cli.main([URL, "--info"]) == 0
    out = capsys.readouterr().out
    assert "Never Gonna Give You Up" in out and "03:33" in out


def test_info_failure_exits_one(monkeypatch, capsys):
    def fails(url):
        raise RuntimeError("ERROR: Unsupported URL\nmore detail")

    monkeypatch.setattr(cli, "probe", fails)
    assert cli.main([URL, "--info"]) == 1
    assert capsys.readouterr().err.strip() == "error: ERROR: Unsupported URL"


def test_info_for_several_links_carries_on_past_a_bad_one(monkeypatch, capsys):
    def probe(url):
        if url == URL:
            raise RuntimeError("ERROR: Private video")
        return {"is_playlist": False, "title": "Gangnam Style", "uploader": "PSY",
                "count": 1, "duration": 253}

    monkeypatch.setattr(cli, "probe", probe)
    assert cli.main([URL, URL2, "--info"]) == 1
    captured = capsys.readouterr()
    assert "[2/2]" in captured.out and "Gangnam Style" in captured.out
    assert "Private video" in captured.err


# ------------------------------------------------------------------- the GUI

def test_gui_module_imports():
    # Catches a broken import or syntax error in the GUI without opening a window.
    try:
        import customtkinter  # noqa: F401
    except Exception as error:  # not installed, or no Tk on this machine
        pytest.skip(f"customtkinter unavailable: {error}")

    from converterw.gui import app

    assert callable(app.run_app)
