import os

import pytest

from Audio_Transcription.transcription_logic import (
    AUDIO_FORMATS,
    WHISPER_MODELS,
    find_audio_files,
    is_model_installed,
    legacy_model_files,
)

SPEECH = os.path.join(os.path.dirname(__file__), "fixtures", "speech_sample.mp3")


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


def test_transcription_does_not_import_torch():
    """faster-whisper runs on CTranslate2; torch must not be pulled in here."""
    import subprocess
    import sys
    code = ("import sys; import Audio_Transcription.transcription_logic, faster_whisper; "
            "sys.exit(1 if 'torch' in sys.modules else 0)")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert subprocess.run([sys.executable, "-c", code], cwd=root).returncode == 0


def test_models_are_pinned_ctranslate2_repos():
    for name, info in WHISPER_MODELS.items():
        assert info["repo_id"] == f"Systran/faster-whisper-{name}"
        assert len(info["revision"]) == 40


def test_partial_download_is_not_installed(tmp_path):
    (tmp_path / "tiny.part").mkdir()
    (tmp_path / "tiny.part" / "model.bin").write_bytes(b"x")
    (tmp_path / "tiny").mkdir()
    (tmp_path / "tiny" / "config.json").write_text("{}")  # model.bin missing
    assert not is_model_installed("tiny", str(tmp_path))


def test_legacy_pt_checkpoints_are_found(tmp_path):
    (tmp_path / "tiny.pt").write_bytes(b"x")
    (tmp_path / "base").mkdir()
    assert legacy_model_files(str(tmp_path)) == [str(tmp_path / "tiny.pt")]


# Container -> (codec, sample rate) used to transcode the fixture for the decode test.
_TRANSCODE = {
    ".mp3": None, ".mpga": None, ".mpeg": None,  # same MPEG audio stream, new extension
    ".wav": ("pcm_s16le", 16000),
    ".flac": ("flac", 16000),
    ".ogg": ("opus", 48000),
    ".webm": ("opus", 48000),
    ".m4a": ("aac", 16000),
    ".mp4": ("aac", 16000),
}


def _transcode(src, dst, codec, rate):
    import av
    fmt = {".m4a": "mp4", ".mp4": "mp4", ".webm": "webm", ".ogg": "ogg"}.get(os.path.splitext(dst)[1])
    options = {}
    if codec == "opus":
        # Release builds use an LGPL FFmpeg with only native codecs, where the
        # Opus encoder is "experimental"; PyPI wheels also have libopus.
        if "libopus" in av.codecs_available:
            codec = "libopus"
        else:
            options = {"strict": "experimental"}
    with av.open(src) as inp, av.open(dst, "w", format=fmt) as out:
        stream = out.add_stream(codec, rate=rate, options=options)
        stream.layout = "mono"
        resampler = av.AudioResampler(format=stream.codec_context.format, layout="mono", rate=rate)
        for frame in inp.decode(audio=0):
            for f in resampler.resample(frame):
                for packet in stream.encode(f):
                    out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)


@pytest.mark.parametrize("ext", AUDIO_FORMATS)
def test_every_audio_format_decodes(ext, tmp_path):
    """Every extension the page accepts must decode in-process (no ffmpeg binary)."""
    import shutil
    from faster_whisper.audio import decode_audio
    assert ext in _TRANSCODE, f"add a transcode recipe for {ext}"
    dst = str(tmp_path / f"sample{ext}")
    recipe = _TRANSCODE[ext]
    if recipe is None:
        shutil.copyfile(SPEECH, dst)
    else:
        _transcode(SPEECH, dst, *recipe)
    audio = decode_audio(dst, sampling_rate=16000)
    seconds = len(audio) / 16000
    assert 8.0 < seconds < 10.0, f"{ext}: decoded {seconds:.2f}s"


@pytest.mark.parametrize("name", ["video_sample.mp4", "video_sample.mpeg"])
def test_audio_is_found_in_files_with_video(name):
    """Recorded interviews are often video files.  Release builds use an FFmpeg
    without video decoders; the demuxer must still identify the video stream
    as video (not mislabel it as audio) and the audio must decode."""
    from faster_whisper.audio import decode_audio
    audio = decode_audio(os.path.join(os.path.dirname(SPEECH), name), sampling_rate=16000)
    assert 2.5 < len(audio) / 16000 < 3.5


@pytest.mark.skipif(not os.environ.get("MDMT_NETWORK_TESTS"), reason="downloads a model; set MDMT_NETWORK_TESTS=1")
def test_transcribe_fixture_with_tiny_model(tmp_path):
    from Audio_Transcription.transcription_logic import load_model, transcribe_file
    model = load_model("tiny", str(tmp_path / "models"))
    result = transcribe_file(model, SPEECH, str(tmp_path / "out.txt"))
    assert result["status"] == "success", result.get("message")
    assert "magazine" in result["text"].lower()
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == result["text"]
