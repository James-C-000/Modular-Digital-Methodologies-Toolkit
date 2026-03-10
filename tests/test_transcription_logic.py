import os
import pytest
from Audio_Transcription.transcription_logic import (
    AUDIO_FORMATS,
    find_audio_files,
)


def test_audio_formats_is_tuple():
    assert isinstance(AUDIO_FORMATS, tuple)
    assert ".mp3" in AUDIO_FORMATS
    assert ".wav" in AUDIO_FORMATS


def test_find_audio_files(tmp_path):
    (tmp_path / "song.mp3").write_text("fake")
    (tmp_path / "clip.wav").write_text("fake")
    (tmp_path / "readme.txt").write_text("not audio")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "talk.m4a").write_text("fake")

    files = find_audio_files(str(tmp_path))
    assert len(files) == 3
    assert all(
        f.endswith(AUDIO_FORMATS) for f in files
    )


def test_find_audio_files_empty(tmp_path):
    files = find_audio_files(str(tmp_path))
    assert files == []
