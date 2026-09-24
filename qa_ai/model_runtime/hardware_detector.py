"""
hardware_detector.py - Detect host hardware capabilities for adaptive model routing.

Uses psutil if available; falls back to platform/os/sys.
Never fails — returns conservative profile on any error.
No shell. No subprocess. No eval. No sensitive data returned.

Security:
- Only RAM, platform, arch, and GPU framework availability are returned.
- No process names, no user info, no network interfaces exposed.
- No shell commands.
"""
from __future__ import annotations

import logging
import platform
import sys
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_PROFILE_LOW     = "low_ram_8gb"
_PROFILE_MID     = "mac_m4_16gb"
_PROFILE_PRO     = "pro_32gb"
_PROFILE_WS      = "workstation_64gb"
_PROFILE_REMOTE  = "remote_gpu"
_PROFILE_UNKNOWN = "mac_m4_16gb"   # conservative fallback


@dataclass
class HardwareProfile:
    platform: str               # "macos" | "linux" | "windows" | "unknown"
    architecture: str           # "arm64" | "x86_64" | "unknown"
    total_ram_gb: float
    available_ram_gb: float     # 0.0 if unknown
    apple_silicon: bool
    cuda_available: bool
    metal_available: bool
    gpu_label: str              # e.g. "Apple M4 Pro GPU" | "NVIDIA A100" | "unknown"
    inside_container: bool
    recommended_profile: str
    detection_confidence: str   # "high" | "medium" | "low"
    warnings: List[str] = field(default_factory=list)


def detect_hardware() -> HardwareProfile:
    """
    Detect current machine hardware.

    Returns HardwareProfile. Never raises — errors captured as warnings.
    Conservative fallback profile if detection fails.
    """
    warnings: List[str] = []
    platform_str = _detect_platform()
    arch = _detect_arch()
    total_ram, avail_ram, ram_warning = _detect_ram()
    if ram_warning:
        warnings.append(ram_warning)

    apple_si  = _is_apple_silicon(platform_str, arch)
    cuda      = _detect_cuda()
    metal     = _detect_metal(platform_str, apple_si)
    gpu_label = _detect_gpu_label(platform_str, arch, cuda, metal)
    container = _detect_container()

    profile, conf = _recommend_profile(
        total_ram, apple_si, cuda, metal, container
    )

    if total_ram < 6.0:
        warnings.append(
            "Very low RAM detected (< 6 GB). "
            "Most AI tasks will be disabled. Only phi4-mini or smaller recommended."
        )
    elif total_ram < 10.0:
        warnings.append(
            "Low RAM (< 10 GB). Heavy models disabled. "
            "Vision AI may be unavailable. Prefer deterministic verification."
        )
    elif total_ram < 14.0:
        warnings.append(
            "RAM in conservative range (10–14 GB). "
            "Sequential model calls only. Avoid concurrent heavy tasks."
        )

    if container:
        warnings.append(
            "Running inside a container. "
            "GPU pass-through and Metal are unlikely to be available."
        )

    return HardwareProfile(
        platform=platform_str,
        architecture=arch,
        total_ram_gb=total_ram,
        available_ram_gb=avail_ram,
        apple_silicon=apple_si,
        cuda_available=cuda,
        metal_available=metal,
        gpu_label=gpu_label,
        inside_container=container,
        recommended_profile=profile,
        detection_confidence=conf,
        warnings=warnings,
    )


# ── Internals ─────────────────────────────────────────────────────────────────

def _detect_platform() -> str:
    try:
        s = platform.system().lower()
        if s == "darwin":
            return "macos"
        if s == "linux":
            return "linux"
        if s == "windows":
            return "windows"
        return "unknown"
    except Exception:
        return "unknown"


def _detect_arch() -> str:
    try:
        m = platform.machine().lower()
        if m in ("arm64", "aarch64"):
            return "arm64"
        if m in ("x86_64", "amd64"):
            return "x86_64"
        return m or "unknown"
    except Exception:
        return "unknown"


def _detect_ram() -> tuple[float, float, Optional[str]]:
    """Return (total_gb, available_gb, warning_or_None)."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        total = round(vm.total / (1024 ** 3), 1)
        avail = round(vm.available / (1024 ** 3), 1)
        return total, avail, None
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("psutil RAM detection failed: %s", exc)

    # Fallback: /proc/meminfo on Linux
    try:
        import os
        if os.path.exists("/proc/meminfo"):
            total_kb, avail_kb = 0, 0
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        avail_kb = int(line.split()[1])
            if total_kb > 0:
                return round(total_kb / (1024 ** 2), 1), round(avail_kb / (1024 ** 2), 1), None
    except Exception:
        pass

    # macOS sysctl fallback
    try:
        import subprocess
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            mem_bytes = int(result.stdout.strip())
            return round(mem_bytes / (1024 ** 3), 1), 0.0, None
    except Exception:
        pass

    return 0.0, 0.0, "RAM detection failed — conservative profile applied."


def _is_apple_silicon(platform_str: str, arch: str) -> bool:
    return platform_str == "macos" and arch == "arm64"


def _detect_cuda() -> bool:
    try:
        import importlib
        if importlib.util.find_spec("torch") is not None:
            import torch  # type: ignore
            return bool(torch.cuda.is_available())
    except Exception:
        pass
    # Check CUDA env var as secondary signal
    import os
    return bool(os.environ.get("CUDA_VISIBLE_DEVICES"))


def _detect_metal(platform_str: str, apple_silicon: bool) -> bool:
    if platform_str != "macos":
        return False
    try:
        import importlib
        if importlib.util.find_spec("torch") is not None:
            import torch  # type: ignore
            return bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    except Exception:
        pass
    # Apple Silicon Macs always have Metal available
    return apple_silicon


def _detect_gpu_label(platform_str: str, arch: str, cuda: bool, metal: bool) -> str:
    if metal and arch == "arm64":
        try:
            model = platform.node()
            chip = _get_apple_chip_label()
            return f"Apple Silicon GPU ({chip})"
        except Exception:
            return "Apple Silicon GPU"
    if cuda:
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                return torch.cuda.get_device_name(0)
        except Exception:
            return "NVIDIA GPU (CUDA)"
        return "NVIDIA GPU (CUDA)"
    return "unknown"


def _get_apple_chip_label() -> str:
    """Try to read Apple Silicon chip model."""
    try:
        import subprocess
        r = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        # Fallback: hw.model
        r2 = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            capture_output=True, text=True, timeout=2,
        )
        if r2.returncode == 0 and r2.stdout.strip():
            return r2.stdout.strip()
    except Exception:
        pass
    return "Apple Silicon"


def _detect_container() -> bool:
    import os
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup") as f:
            content = f.read()
            if "docker" in content or "kubepods" in content or "lxc" in content:
                return True
    except Exception:
        pass
    return False


def _recommend_profile(
    total_ram: float,
    apple_si: bool,
    cuda: bool,
    metal: bool,
    container: bool,
) -> tuple[str, str]:
    """Return (profile_id, confidence)."""
    if total_ram == 0.0:
        return _PROFILE_MID, "low"   # unknown RAM → conservative mid

    # Remote GPU: CUDA available and RAM >= 16 GB
    if cuda and total_ram >= 16.0 and not apple_si:
        return _PROFILE_REMOTE, "high"

    if total_ram >= 48.0:
        return _PROFILE_WS, "high"
    if total_ram >= 24.0:
        return _PROFILE_PRO, "high"
    if total_ram >= 12.0:
        return _PROFILE_MID, "high"
    if total_ram >= 6.0:
        return _PROFILE_LOW, "high"

    # Very low — still use low_ram_8gb (it'll disable most models)
    return _PROFILE_LOW, "medium"
