"""Tests for RAG hardware detection module."""
from unittest.mock import patch, MagicMock
import pytest

import RAG.hardware
from RAG.hardware import HardwareInfo, detect_hardware, recommend_model

_REAL_PROBE = RAG.hardware._llama_gpu_offload


class TestHardwareInfo:
    def test_dataclass_fields(self):
        info = HardwareInfo(
            gpu_available=True,
            gpu_type="nvidia",
            vram_mb=8192,
            ram_mb=16384,
            recommended_model="4B",
            n_gpu_layers=-1,
        )
        assert info.gpu_available is True
        assert info.gpu_type == "nvidia"
        assert info.vram_mb == 8192
        assert info.ram_mb == 16384
        assert info.recommended_model == "4B"
        assert info.n_gpu_layers == -1


class TestRecommendModel:
    # On a CPU, 4B takes about a minute per answer for a small gain over 2B
    # (eval/ runs), so 4B is recommended only where it runs on a GPU.
    def test_no_usable_gpu_recommends_2b(self):
        assert recommend_model(gpu_mb=0) == "2B"

    def test_small_gpu_recommends_2b(self):
        assert recommend_model(gpu_mb=3072) == "2B"

    def test_gpu_with_4gb_recommends_4b(self):
        assert recommend_model(gpu_mb=4096) == "4B"


@pytest.fixture(autouse=True)
def offload_supported(monkeypatch):
    """Most tests assume a llama.cpp build that can use the GPU (as on macOS)."""
    monkeypatch.setattr("RAG.hardware._llama_gpu_offload", lambda: True)


class TestDetectHardware:
    @patch("RAG.hardware._detect_nvidia_gpu")
    @patch("RAG.hardware._get_system_ram_mb")
    def test_nvidia_gpu_detected(self, mock_ram, mock_nvidia):
        mock_nvidia.return_value = ("nvidia", 8192)
        mock_ram.return_value = 16384
        info = detect_hardware()
        assert info.gpu_available is True
        assert info.gpu_type == "nvidia"
        assert info.vram_mb == 8192
        assert info.n_gpu_layers == -1
        assert info.recommended_model == "4B"

    @patch("RAG.hardware._detect_nvidia_gpu")
    @patch("RAG.hardware._detect_amd_gpu")
    @patch("RAG.hardware._detect_metal")
    @patch("RAG.hardware._get_system_ram_mb")
    def test_no_gpu_falls_back_to_ram(self, mock_ram, mock_metal, mock_amd, mock_nvidia):
        mock_nvidia.return_value = None
        mock_amd.return_value = None
        mock_metal.return_value = None
        mock_ram.return_value = 16000          # plenty of RAM, but no GPU: still 2B
        info = detect_hardware()
        assert info.gpu_available is False
        assert info.gpu_type == "none"
        assert info.vram_mb == 0
        assert info.n_gpu_layers == 0
        assert info.recommended_model == "2B"

    @patch("RAG.hardware._detect_nvidia_gpu")
    @patch("RAG.hardware._get_system_ram_mb")
    def test_low_vram_gpu_uses_cpu(self, mock_ram, mock_nvidia):
        mock_nvidia.return_value = ("nvidia", 512)
        mock_ram.return_value = 8000
        info = detect_hardware()
        assert info.gpu_available is True
        assert info.vram_mb == 512
        # Too little VRAM: run on the CPU, so 2B
        assert info.n_gpu_layers == 0
        assert info.recommended_model == "2B"

    @patch("RAG.hardware._detect_nvidia_gpu")
    @patch("RAG.hardware._detect_amd_gpu")
    @patch("RAG.hardware._detect_metal")
    @patch("RAG.hardware._get_system_ram_mb")
    def test_all_detection_fails_returns_safe_defaults(self, mock_ram, mock_metal, mock_amd, mock_nvidia):
        mock_nvidia.return_value = None
        mock_amd.return_value = None
        mock_metal.return_value = None
        mock_ram.side_effect = Exception("detection failed")
        info = detect_hardware()
        assert info.gpu_available is False
        assert info.recommended_model == "2B"
        assert info.n_gpu_layers == 0


class TestAppleSilicon:
    @patch("RAG.hardware._detect_nvidia_gpu", return_value=None)
    @patch("RAG.hardware._detect_amd_gpu", return_value=None)
    @patch("RAG.hardware._detect_metal", return_value=("metal", 8192))
    @patch("RAG.hardware._get_system_ram_mb", return_value=8192)
    def test_an_8gb_mac_runs_4b_on_metal(self, *_mocks):
        info = detect_hardware()
        assert info.n_gpu_layers == -1 and info.recommended_model == "4B"


class TestNoConsoleWindows:
    """The windowed Windows build must not flash a console for each probe."""

    @patch("RAG.hardware.subprocess.run")
    def test_gpu_probes_pass_no_window_flags_on_windows(self, mock_run, monkeypatch):
        import RAG.hardware as hw
        from common import proc
        monkeypatch.setattr(proc.sys, "platform", "win32")
        monkeypatch.setattr(proc.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        hw._detect_nvidia_gpu()
        hw._detect_amd_gpu()
        assert mock_run.call_count == 2
        for call in mock_run.call_args_list:
            assert call.kwargs.get("creationflags") == 0x08000000

    def test_no_flags_elsewhere(self, monkeypatch):
        from common import proc
        monkeypatch.setattr(proc.sys, "platform", "linux")
        assert proc.no_window_kwargs() == {}



class TestCpuOnlyBuild:
    """The Windows and Linux builds ship llama.cpp's CPU backend only."""

    @patch("RAG.hardware._detect_nvidia_gpu", return_value=("nvidia", 12288))
    @patch("RAG.hardware._get_system_ram_mb", return_value=32768)
    def test_an_unusable_gpu_is_reported_but_not_used(self, *_mocks):
        with patch.object(RAG.hardware, "_llama_gpu_offload", return_value=False):
            info = detect_hardware()
            assert info.gpu_available and not info.gpu_used
            assert info.n_gpu_layers == 0 and info.recommended_model == "2B"
            assert "runs chat models on the CPU" in info.describe()

    @patch("RAG.hardware._detect_nvidia_gpu", return_value=("nvidia", 8192))
    @patch("RAG.hardware._get_system_ram_mb", return_value=16384)
    def test_a_usable_gpu_is_described_plainly(self, *_mocks):
        info = detect_hardware()
        assert info.gpu_used and "not used" not in info.describe() and "NVIDIA" in info.describe()

    def test_offload_probe_never_raises(self, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "llama_cpp", None)      # import fails
        assert _REAL_PROBE() is False
