"""Hardware detection and model recommendation for the RAG module."""
import logging
import platform
import subprocess
from dataclasses import dataclass

import psutil

logger = logging.getLogger("rag-hardware")

# Minimum VRAM (MB) to justify GPU offloading (model + KV cache overhead)
_MIN_GPU_VRAM_MB = 1024


@dataclass
class HardwareInfo:
    """Detected hardware capabilities and model recommendation."""

    gpu_available: bool
    gpu_type: str  # "nvidia", "amd", "metal", "none"
    vram_mb: int  # 0 if no GPU
    ram_mb: int
    recommended_model: str  # "0.8B", "2B", or "4B"
    n_gpu_layers: int  # -1 (all GPU) or 0 (CPU only)


def recommend_model(available_mb: int) -> str:
    """Recommend a Qwen 3.5 model size based on available memory in MB."""
    if available_mb >= 4096:
        return "4B"
    if available_mb >= 2048:
        return "2B"
    return "0.8B"


def detect_hardware() -> HardwareInfo:
    """Detect GPU/RAM and recommend an appropriate model.

    Tries GPU detection in order: NVIDIA, AMD, Metal.
    Falls back to system RAM if no GPU is found.
    Returns safe defaults if all detection fails.
    """
    gpu_result = (
        _detect_nvidia_gpu()
        or _detect_amd_gpu()
        or _detect_metal()
    )

    try:
        ram_mb = _get_system_ram_mb()
    except Exception:
        ram_mb = 0

    if gpu_result:
        gpu_type, vram_mb = gpu_result
        use_gpu = vram_mb >= _MIN_GPU_VRAM_MB
        # Use VRAM for recommendation if GPU will be used, else RAM
        rec_memory = vram_mb if use_gpu else ram_mb
        return HardwareInfo(
            gpu_available=True,
            gpu_type=gpu_type,
            vram_mb=vram_mb,
            ram_mb=ram_mb,
            recommended_model=recommend_model(rec_memory if rec_memory > 0 else 0),
            n_gpu_layers=-1 if use_gpu else 0,
        )

    # No GPU — use RAM
    if ram_mb > 0:
        return HardwareInfo(
            gpu_available=False,
            gpu_type="none",
            vram_mb=0,
            ram_mb=ram_mb,
            recommended_model=recommend_model(ram_mb),
            n_gpu_layers=0,
        )

    # All detection failed — safe defaults
    return HardwareInfo(
        gpu_available=False,
        gpu_type="none",
        vram_mb=0,
        ram_mb=0,
        recommended_model="0.8B",
        n_gpu_layers=0,
    )


def _detect_nvidia_gpu():
    """Detect NVIDIA GPU via nvidia-smi. Returns ("nvidia", vram_mb) or None."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            vram_mb = int(result.stdout.strip().splitlines()[0].strip())
            return ("nvidia", vram_mb)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None


def _detect_amd_gpu():
    """Detect AMD GPU via rocm-smi. Returns ("amd", vram_mb) or None."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.splitlines():
                if "Total" in line:
                    # Parse total VRAM in bytes, convert to MB
                    parts = line.split()
                    for part in parts:
                        if part.isdigit():
                            vram_mb = int(part) // (1024 * 1024)
                            if vram_mb > 0:
                                return ("amd", vram_mb)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None


def _detect_metal():
    """Detect Apple Metal (macOS). Returns ("metal", system_ram_mb) or None.

    Metal shares system RAM, so we report total system memory as VRAM.
    """
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            ram_bytes = int(result.stdout.strip())
            return ("metal", ram_bytes // (1024 * 1024))
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None


def _get_system_ram_mb() -> int:
    """Get total system RAM in MB via psutil."""
    return psutil.virtual_memory().total // (1024 * 1024)
