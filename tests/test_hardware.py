"""Tests for RAG hardware detection module."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from RAG.hardware import HardwareInfo, detect_hardware, recommend_model


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
    def test_low_memory_recommends_0_8b(self):
        assert recommend_model(available_mb=1500) == "0.8B"

    def test_medium_memory_recommends_2b(self):
        assert recommend_model(available_mb=3000) == "2B"

    def test_high_memory_recommends_4b(self):
        assert recommend_model(available_mb=5000) == "4B"

    def test_boundary_2gb_recommends_2b(self):
        assert recommend_model(available_mb=2048) == "2B"

    def test_boundary_4gb_recommends_4b(self):
        assert recommend_model(available_mb=4096) == "4B"

    def test_very_low_memory_recommends_0_8b(self):
        assert recommend_model(available_mb=500) == "0.8B"


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
        mock_ram.return_value = 3000
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
        # Low VRAM: use RAM for model recommendation, CPU for inference
        assert info.n_gpu_layers == 0
        assert info.recommended_model == "4B"

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
        assert info.recommended_model == "0.8B"
        assert info.n_gpu_layers == 0


class TestNoConsoleWindows:
    """The windowed Windows build must not flash a console for each probe."""

    @patch("RAG.hardware.subprocess.run")
    def test_gpu_probes_pass_no_window_flags_on_windows(self, mock_run, monkeypatch):
        import sys
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

