"""Saved settings: a bad settings.json must never stop the app from starting."""

import json

import pytest

from converterw import config
from converterw.youtube import Options


def test_missing_file_gives_defaults(isolated_settings):
    assert not isolated_settings.exists()
    assert config.load() == config.defaults()


@pytest.mark.parametrize("content", ["{not json", "", "[1, 2, 3]", "null", '"text"'])
def test_corrupt_file_gives_defaults(isolated_settings, content):
    isolated_settings.write_text(content, encoding="utf-8")
    assert config.load() == config.defaults()


def test_values_of_the_wrong_type_are_ignored(isolated_settings):
    isolated_settings.write_text(json.dumps({
        "quality": 1080,
        "embed_thumbnail": "yes",
        "concurrent_fragments": "8",
        "container": "mkv",
        "something_from_a_newer_version": True,
    }), encoding="utf-8")

    settings = config.load()
    defaults = config.defaults()
    assert settings["quality"] == defaults["quality"]
    assert settings["embed_thumbnail"] == defaults["embed_thumbnail"]
    assert settings["concurrent_fragments"] == defaults["concurrent_fragments"]
    assert settings["container"] == "mkv"
    assert "something_from_a_newer_version" not in settings


def test_save_then_load_round_trips():
    settings = config.defaults()
    settings.update(quality="720p", audio_format="flac", show_log=True, concurrent_fragments=8)
    config.save(settings)
    assert config.load() == settings


def test_unwritable_location_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "missing-dir" / "settings.json")
    config.save(config.defaults())


def test_to_options_keeps_only_download_options():
    settings = config.defaults()
    settings.update(audio_format="opus", output_dir="/somewhere")
    options = config.to_options(settings)

    assert isinstance(options, Options)
    assert options.audio_format == "opus"
    assert not hasattr(options, "output_dir")


def test_every_option_has_a_default_setting():
    defaults = config.defaults()
    for name in Options.__dataclass_fields__:
        assert name in defaults
