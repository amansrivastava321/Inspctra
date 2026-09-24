"""
capability_registry.py - Environment intelligence for the Autonomous QA Platform.
Detects available tools, SDKs, devices, and runtimes.
Answers: What can I test right now? What is missing? What can I auto-provision?
"""

from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import shutil
import os
import platform as sys_platform
import json
import logging

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class CapabilityStatus(Enum):
    """Status of a detected capability."""
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    VERSION_MISMATCH = "version_mismatch"
    NEEDS_SETUP = "needs_setup"
    ERROR = "error"
    UNKNOWN = "unknown"


class ProvisionStrategy(Enum):
    """How a missing capability can be provisioned."""
    AUTO = "auto"               # Can be installed automatically
    GUIDED = "guided"           # Needs user to follow instructions
    MANUAL = "manual"           # Requires manual installation
    CREDENTIAL = "credential"   # Needs credentials or API keys
    DEVICE = "device"           # Needs physical device connection
    NOT_PROVISIONABLE = "not_provisionable"


@dataclass
class Capability:
    """A single detected tool, SDK, or device capability."""
    name: str
    category: str                      # "sdk", "tool", "device", "runtime", "service"
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    version: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None
    provision_strategy: ProvisionStrategy = ProvisionStrategy.NOT_PROVISIONABLE
    provision_command: Optional[str] = None
    provision_instructions: Optional[str] = None
    required_by: List[str] = field(default_factory=list)  # Which agents need this
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        return self.status == CapabilityStatus.AVAILABLE
    
    @property
    def can_provision(self) -> bool:
        return self.provision_strategy != ProvisionStrategy.NOT_PROVISIONABLE
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status.value,
            "version": self.version,
            "path": self.path,
            "error_message": self.error_message,
            "provision_strategy": self.provision_strategy.value,
            "provision_command": self.provision_command,
            "provision_instructions": self.provision_instructions,
            "required_by": self.required_by,
            "is_available": self.is_available,
            "can_provision": self.can_provision,
            "metadata": self.metadata,
        }


@dataclass
class DeviceInfo:
    """A connected or available test device."""
    device_id: str
    device_name: str
    device_type: str                   # "emulator", "simulator", "physical"
    platform: str                      # "android", "ios", "web"
    os_version: str = ""
    screen_resolution: str = ""
    is_online: bool = False
    is_authorized: bool = False        # For iOS: trusted device
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "platform": self.platform,
            "os_version": self.os_version,
            "screen_resolution": self.screen_resolution,
            "is_online": self.is_online,
            "is_authorized": self.is_authorized,
            "metadata": self.metadata,
        }


@dataclass
class EnvironmentCapabilities:
    """
    Complete picture of what the system can test right now.
    Answers three questions:
    1. What can I test? (available capabilities)
    2. What is missing? (unavailable capabilities)
    3. What can I auto-provision? (provisionable capabilities)
    """
    capabilities: Dict[str, Capability] = field(default_factory=dict)
    connected_devices: List[DeviceInfo] = field(default_factory=list)
    host_os: str = field(default_factory=sys_platform.system)
    host_arch: str = field(default_factory=sys_platform.machine)
    scanned_at: str = ""
    
    @property
    def available(self) -> List[Capability]:
        return [c for c in self.capabilities.values() if c.is_available]
    
    @property
    def missing(self) -> List[Capability]:
        return [c for c in self.capabilities.values() if not c.is_available]
    
    @property
    def provisionable(self) -> List[Capability]:
        return [c for c in self.missing if c.can_provision]
    
    @property
    def blocked(self) -> List[Capability]:
        return [c for c in self.missing if not c.can_provision]
    
    def can_test_platform(self, platform: str) -> bool:
        """Check if a specific platform can be tested."""
        platform_lower = platform.lower()

        if platform_lower == "web":
            playwright = self.capabilities.get("playwright")
            return playwright is not None and playwright.is_available

        if platform_lower == "android":
            adb = self.capabilities.get("adb")
            return (
                adb is not None and adb.is_available and
                len(self.android_devices) > 0
            )

        if platform_lower == "ios":
            xcode = self.capabilities.get("xcode")
            return (
                xcode is not None and xcode.is_available and
                len(self.ios_devices) > 0
            )

        if platform_lower == "flutter":
            flutter = self.capabilities.get("flutter")
            return flutter is not None and flutter.is_available

        if platform_lower in ("backend", "api"):
            return True  # API testing doesn't need device

        return False
    
    @property
    def android_devices(self) -> List[DeviceInfo]:
        return [d for d in self.connected_devices if d.platform == "android"]
    
    @property
    def ios_devices(self) -> List[DeviceInfo]:
        return [d for d in self.connected_devices if d.platform == "ios"]
    
    @property
    def web_browsers(self) -> List[str]:
        browsers = []
        chromium = self.capabilities.get("chromium")
        if chromium and chromium.is_available:
            browsers.append("chromium")
        firefox = self.capabilities.get("firefox")
        if firefox and firefox.is_available:
            browsers.append("firefox")
        webkit = self.capabilities.get("webkit")
        if webkit and webkit.is_available:
            browsers.append("webkit")
        return browsers
    
    def summary(self) -> Dict[str, Any]:
        """Generate a human-readable summary."""
        return {
            "host": f"{self.host_os} {self.host_arch}",
            "scanned_at": self.scanned_at,
            "total_capabilities": len(self.capabilities),
            "available": len(self.available),
            "missing": len(self.missing),
            "provisionable": len(self.provisionable),
            "blocked": len(self.blocked),
            "connected_devices": len(self.connected_devices),
            "android_devices": len(self.android_devices),
            "ios_devices": len(self.ios_devices),
            "web_browsers": self.web_browsers,
            "testable_platforms": {
                "web": self.can_test_platform("web"),
                "android": self.can_test_platform("android"),
                "ios": self.can_test_platform("ios"),
                "flutter": self.can_test_platform("flutter"),
                "backend": self.can_test_platform("backend"),
            },
            "available_list": [c.name for c in self.available],
            "missing_list": [c.name for c in self.missing],
            "provisionable_list": [c.name for c in self.provisionable],
        }
    
    def to_dict(self) -> dict:
        return {
            "capabilities": {k: v.to_dict() for k, v in self.capabilities.items()},
            "connected_devices": [d.to_dict() for d in self.connected_devices],
            "host_os": self.host_os,
            "host_arch": self.host_arch,
            "scanned_at": self.scanned_at,
            "summary": self.summary(),
        }


# ─── Capability Registry ───────────────────────────────

class CapabilityRegistry:
    """
    Detects and tracks all tools, SDKs, devices, and runtimes.
    
    This is the environment intelligence layer. Before any test runs,
    the system asks: "What can I actually test right now?"
    
    Architecture:
    1. Detect all installed tools (flutter, adb, xcode, docker, etc.)
    2. Detect connected devices (Android emulators, iOS simulators, physical)
    3. Detect runtimes (Playwright browsers, Node, Python)
    4. Identify gaps (what's missing?)
    5. Classify gaps (can we auto-provision, guide the user, or is it blocked?)
    """
    
    def __init__(self):
        self.capabilities = EnvironmentCapabilities()
    
    # ─── Full Scan ─────────────────────────────────────
    
    def scan_all(self) -> EnvironmentCapabilities:
        """
        Run a complete environment scan.
        Detects everything: tools, SDKs, devices, runtimes.
        """
        from datetime import datetime, timezone
        
        logger.info("Scanning environment capabilities...")
        
        self._detect_python()
        self._detect_pip()
        self._detect_git()
        self._detect_node()
        self._detect_npm()
        self._detect_docker()
        self._detect_flutter()
        self._detect_dart()
        self._detect_android_sdk()
        self._detect_adb()
        self._detect_android_emulator()
        self._detect_xcode()
        self._detect_ios_simulator()
        self._detect_playwright()
        self._detect_java()

        # Detect connected devices
        self._detect_android_devices()
        self._detect_ios_devices()
        self._detect_flutter_devices()
        
        self.capabilities.scanned_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(
            f"Scan complete: {len(self.capabilities.available)} available, "
            f"{len(self.capabilities.missing)} missing, "
            f"{len(self.capabilities.connected_devices)} devices"
        )
        
        return self.capabilities
    
    def quick_scan(self) -> Dict[str, bool]:
        """
        Fast scan for critical capabilities only.
        Returns a simple available/not-available dict.
        """
        critical = ["flutter", "adb", "xcode", "playwright", "docker"]
        results = {}
        
        for name in critical:
            cap = self._check_command(name)
            results[name] = cap.is_available
        
        return results
    
    # ─── Individual Detectors ──────────────────────────
    
    def _detect_flutter(self):
        """Detect Flutter SDK."""
        cap = self._check_command(
            "flutter",
            version_args=["--version"],
            version_pattern=r"Flutter\s+([\d\.]+)",
        )
        cap.category = "sdk"
        cap.required_by = ["flutter_runner", "ui_explorer"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "Run: brew install flutter (macOS) or visit https://flutter.dev/docs/get-started/install"
        
        if not cap.is_available:
            # Check common install paths
            common_paths = [
                Path.home() / "flutter" / "bin" / "flutter",
                Path.home() / "development" / "flutter" / "bin" / "flutter",
                Path("/usr/local/bin/flutter"),
                Path("/opt/flutter/bin/flutter"),
            ]
            for path in common_paths:
                if path.exists():
                    cap.status = CapabilityStatus.AVAILABLE
                    cap.path = str(path)
                    cap.version = self._get_flutter_version(str(path))
                    break
        
        self.capabilities.capabilities["flutter"] = cap
    
    def _detect_android_sdk(self):
        """Detect Android SDK."""
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        
        cap = Capability(
            name="android_sdk",
            category="sdk",
            required_by=["android_runner", "ui_explorer"],
            provision_strategy=ProvisionStrategy.GUIDED,
            provision_instructions="Install Android Studio: https://developer.android.com/studio",
        )
        
        if android_home and Path(android_home).exists():
            cap.status = CapabilityStatus.AVAILABLE
            cap.path = android_home
            cap.metadata["android_home"] = android_home
        else:
            # Check common paths
            common_paths = [
                Path.home() / "Android" / "Sdk",
                Path.home() / "Library" / "Android" / "sdk",
                Path("/usr/local/android-sdk"),
            ]
            for path in common_paths:
                if path.exists():
                    cap.status = CapabilityStatus.AVAILABLE
                    cap.path = str(path)
                    cap.metadata["android_home"] = str(path)
                    break
            else:
                cap.status = CapabilityStatus.NOT_FOUND
        
        self.capabilities.capabilities["android_sdk"] = cap
    
    def _detect_adb(self):
        """Detect Android Debug Bridge."""
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        
        # Check if adb is in PATH
        adb_path = shutil.which("adb")
        
        # Check Android SDK location
        if not adb_path and android_home:
            adb_candidate = Path(android_home) / "platform-tools" / "adb"
            if adb_candidate.exists():
                adb_path = str(adb_candidate)
        
        cap = Capability(
            name="adb",
            category="tool",
            required_by=["android_runner", "ui_explorer"],
            provision_strategy=ProvisionStrategy.AUTO if sys_platform.system() == "Darwin" else ProvisionStrategy.GUIDED,
            provision_command="brew install android-platform-tools" if sys_platform.system() == "Darwin" else None,
            provision_instructions="Install Android Platform Tools: https://developer.android.com/studio/releases/platform-tools",
        )
        
        if adb_path:
            cap.status = CapabilityStatus.AVAILABLE
            cap.path = adb_path
            cap.version = self._run_command([adb_path, "version"], timeout=5)
        else:
            cap.status = CapabilityStatus.NOT_FOUND
        
        self.capabilities.capabilities["adb"] = cap
    
    def _detect_xcode(self):
        """Detect Xcode (macOS only)."""
        cap = Capability(
            name="xcode",
            category="tool",
            required_by=["ios_runner", "ui_explorer"],
            provision_strategy=ProvisionStrategy.GUIDED,
            provision_instructions="Install Xcode from the Mac App Store",
        )
        
        if sys_platform.system() != "Darwin":
            cap.status = CapabilityStatus.NOT_FOUND
            cap.error_message = "Xcode is only available on macOS"
            cap.provision_strategy = ProvisionStrategy.NOT_PROVISIONABLE
            self.capabilities.capabilities["xcode"] = cap
            return
        
        # Check xcodebuild
        xcodebuild_path = shutil.which("xcodebuild")
        if xcodebuild_path:
            cap.status = CapabilityStatus.AVAILABLE
            cap.path = xcodebuild_path
            cap.version = self._run_command(["xcodebuild", "-version"], timeout=10)
            if cap.version:
                cap.version = cap.version.split("\n")[0] if "\n" in cap.version else cap.version
        else:
            cap.status = CapabilityStatus.NOT_FOUND
        
        self.capabilities.capabilities["xcode"] = cap
    
    def _detect_ios_simulator(self):
        """Detect iOS Simulator availability."""
        cap = Capability(
            name="ios_simulator",
            category="device",
            required_by=["ios_runner"],
            provision_strategy=ProvisionStrategy.GUIDED,
            provision_instructions="Install Xcode and open Simulator.app",
        )
        
        if sys_platform.system() != "Darwin":
            cap.status = CapabilityStatus.NOT_FOUND
            cap.error_message = "iOS Simulator is only available on macOS"
            cap.provision_strategy = ProvisionStrategy.NOT_PROVISIONABLE
            self.capabilities.capabilities["ios_simulator"] = cap
            return
        
        # Check if simctl is available
        xcrun = shutil.which("xcrun")
        if xcrun:
            result = self._run_command(["xcrun", "simctl", "list", "devices", "available"], timeout=10)
            if result and "iPhone" in result:
                cap.status = CapabilityStatus.AVAILABLE
                cap.metadata["available_simulators"] = self._parse_ios_simulators(result)
            else:
                cap.status = CapabilityStatus.NEEDS_SETUP
                cap.error_message = "No iOS simulators available. Open Xcode → Settings → Components to download."
        else:
            cap.status = CapabilityStatus.NOT_FOUND
        
        self.capabilities.capabilities["ios_simulator"] = cap
    
    def _detect_docker(self):
        """Detect Docker."""
        cap = Capability(
            name="docker",
            category="tool",
            required_by=["docker_manager", "environment_orchestrator"],
            provision_strategy=ProvisionStrategy.GUIDED,
            provision_instructions="Install Docker Desktop: https://www.docker.com/products/docker-desktop",
        )
        
        docker_path = shutil.which("docker")
        if docker_path:
            cap.status = CapabilityStatus.AVAILABLE
            cap.path = docker_path
            cap.version = self._run_command(["docker", "--version"], timeout=5)
        else:
            cap.status = CapabilityStatus.NOT_FOUND
        
        self.capabilities.capabilities["docker"] = cap
    
    def _detect_playwright(self):
        """Detect Playwright and installed browsers."""
        cap = Capability(
            name="playwright",
            category="tool",
            required_by=["playwright_runner", "ui_explorer"],
            provision_strategy=ProvisionStrategy.AUTO,
            provision_command="pip install playwright && playwright install",
            provision_instructions="Run: pip install playwright && playwright install chromium",
        )
        
        try:
            import playwright
            cap.status = CapabilityStatus.AVAILABLE
            cap.version = playwright.__version__ if hasattr(playwright, "__version__") else "installed"
            
            # Detect installed browsers
            self._detect_playwright_browsers()
        except ImportError:
            cap.status = CapabilityStatus.NOT_FOUND
        
        self.capabilities.capabilities["playwright"] = cap
    
    def _detect_playwright_browsers(self):
        """Detect which Playwright browsers are installed."""
        browser_paths = {
            "chromium": [
                Path.home() / "Library" / "Caches" / "ms-playwright" / "chromium-*",
                Path.home() / ".cache" / "ms-playwright" / "chromium-*",
            ],
            "firefox": [
                Path.home() / "Library" / "Caches" / "ms-playwright" / "firefox-*",
                Path.home() / ".cache" / "ms-playwright" / "firefox-*",
            ],
            "webkit": [
                Path.home() / "Library" / "Caches" / "ms-playwright" / "webkit-*",
                Path.home() / ".cache" / "ms-playwright" / "webkit-*",
            ],
        }
        
        for browser_name, paths in browser_paths.items():
            found = False
            for pattern in paths:
                matches = list(pattern.parent.glob(pattern.name)) if pattern.parent.exists() else []
                if matches:
                    found = True
                    break
            
            cap = Capability(
                name=browser_name,
                category="runtime",
                required_by=["playwright_runner"],
                status=CapabilityStatus.AVAILABLE if found else CapabilityStatus.NOT_FOUND,
                provision_strategy=ProvisionStrategy.AUTO if not found else ProvisionStrategy.NOT_PROVISIONABLE,
                provision_command=f"playwright install {browser_name}" if not found else None,
            )
            self.capabilities.capabilities[browser_name] = cap
    
    def _detect_node(self):
        """Detect Node.js."""
        cap = self._check_command("node", version_args=["--version"])
        cap.category = "runtime"
        cap.required_by = ["node_runner"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "Install Node.js: https://nodejs.org or brew install node"
        
        if cap.version and cap.version.startswith("v"):
            cap.version = cap.version[1:]  # Remove 'v' prefix
        
        self.capabilities.capabilities["node"] = cap
    
    def _detect_python(self):
        """Detect Python."""
        cap = self._check_command("python3", version_args=["--version"])
        if not cap.is_available:
            cap = self._check_command("python", version_args=["--version"])
        
        cap.category = "runtime"
        cap.required_by = ["api_runner", "security_runner"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "Install Python: https://python.org or brew install python"
        
        if cap.version:
            cap.version = cap.version.replace("Python ", "")
        
        self.capabilities.capabilities["python"] = cap
    
    def _detect_git(self):
        """Detect Git."""
        cap = self._check_command("git", version_args=["--version"])
        cap.category = "tool"
        cap.required_by = ["rca_engine", "release_audit"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "Install Git: https://git-scm.com or brew install git"
        
        if cap.version:
            cap.version = cap.version.replace("git version ", "")
        
        self.capabilities.capabilities["git"] = cap
    
    def _detect_java(self):
        """Detect Java (required for Android SDK)."""
        cap = self._check_command("java", version_args=["-version"])
        cap.category = "runtime"
        cap.required_by = ["android_runner"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "Install Java JDK: brew install openjdk (macOS) or visit https://adoptium.net"
        
        # Java outputs version to stderr
        if not cap.is_available:
            result = self._run_command(["java", "-version"], timeout=5)
            if result:
                cap.status = CapabilityStatus.AVAILABLE
                cap.version = result.split("\n")[0] if "\n" in result else result
        
        self.capabilities.capabilities["java"] = cap

    def _detect_pip(self):
        """Detect pip package manager."""
        cap = self._check_command("pip3", version_args=["--version"])
        if not cap.is_available:
            cap = self._check_command("pip", version_args=["--version"])

        cap.category = "tool"
        cap.required_by = ["api_runner", "playwright_runner"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "pip is bundled with Python. Install Python: https://python.org"

        if cap.version:
            cap.version = cap.version.replace("pip ", "").split(" ")[0]

        self.capabilities.capabilities["pip"] = cap

    def _detect_npm(self):
        """Detect npm package manager."""
        cap = self._check_command("npm", version_args=["--version"])
        cap.category = "tool"
        cap.required_by = ["node_runner"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "npm is bundled with Node.js. Install Node: https://nodejs.org"

        self.capabilities.capabilities["npm"] = cap

    def _detect_dart(self):
        """Detect Dart SDK."""
        cap = self._check_command(
            "dart",
            version_args=["--version"],
            version_pattern=r"Dart SDK version:\s+([\d\.]+)",
        )
        cap.category = "sdk"
        cap.required_by = ["flutter_runner"]
        cap.provision_strategy = ProvisionStrategy.GUIDED
        cap.provision_instructions = "Dart is bundled with Flutter. Install Flutter: https://flutter.dev"

        if not cap.is_available:
            # Check if dart is inside flutter
            flutter = self.capabilities.capabilities.get("flutter")
            if flutter and flutter.is_available and flutter.path:
                dart_path = Path(flutter.path).parent / "dart"
                if dart_path.exists():
                    cap.status = CapabilityStatus.AVAILABLE
                    cap.path = str(dart_path)

        self.capabilities.capabilities["dart"] = cap

    def _detect_android_emulator(self):
        """Detect Android emulator availability."""
        cap = Capability(
            name="android_emulator",
            category="tool",
            required_by=["android_runner"],
            provision_strategy=ProvisionStrategy.GUIDED,
            provision_instructions="Install Android Studio and create an AVD via AVD Manager",
        )

        emulator_path = shutil.which("emulator")
        if emulator_path:
            cap.status = CapabilityStatus.AVAILABLE
            cap.path = emulator_path
            # Try listing AVDs
            result = self._run_command([emulator_path, "-list-avds"], timeout=10)
            if result:
                avds = [a.strip() for a in result.split("\n") if a.strip()]
                cap.metadata["available_avds"] = avds
                if not avds:
                    cap.status = CapabilityStatus.NEEDS_SETUP
                    cap.error_message = "emulator found but no AVDs configured"
        else:
            cap.status = CapabilityStatus.NOT_FOUND

        self.capabilities.capabilities["android_emulator"] = cap
    
    # ─── Device Detection ──────────────────────────────
    
    def _detect_android_devices(self):
        """Detect connected Android devices and emulators."""
        adb = self.capabilities.capabilities.get("adb")
        if not adb or not adb.is_available:
            return
        
        adb_path = adb.path or "adb"
        result = self._run_command([adb_path, "devices", "-l"], timeout=10)
        
        if not result:
            return
        
        for line in result.split("\n")[1:]:  # Skip header
            if not line.strip() or "List of devices" in line:
                continue
            
            parts = line.split()
            if len(parts) < 2:
                continue
            
            device_id = parts[0]
            device_status = parts[1]
            
            device_info = DeviceInfo(
                device_id=device_id,
                device_name=self._extract_device_property(line, "model"),
                device_type="emulator" if "emulator" in line.lower() else "physical",
                platform="android",
                is_online=(device_status == "device"),
            )
            
            # Get OS version
            os_ver = self._run_command(
                [adb_path, "-s", device_id, "shell", "getprop", "ro.build.version.release"],
                timeout=5
            )
            if os_ver:
                device_info.os_version = os_ver.strip()
            
            self.capabilities.connected_devices.append(device_info)
    
    def _detect_ios_devices(self):
        """Detect available iOS simulators."""
        if sys_platform.system() != "Darwin":
            return
        
        xcrun = shutil.which("xcrun")
        if not xcrun:
            return
        
        result = self._run_command(
            ["xcrun", "simctl", "list", "devices", "available", "--json"],
            timeout=10
        )
        
        if not result:
            return
        
        try:
            data = json.loads(result)
            devices = data.get("devices", {})
            
            for runtime, device_list in devices.items():
                for device in device_list:
                    if device.get("state") == "Booted" or device.get("availability") == "(available)":
                        device_info = DeviceInfo(
                            device_id=device["udid"],
                            device_name=device["name"],
                            device_type="simulator",
                            platform="ios",
                            os_version=runtime.replace("com.apple.CoreSimulator.SimRuntime.iOS-", "").replace("-", "."),
                            is_online=(device.get("state") == "Booted"),
                            is_authorized=True,
                        )
                        self.capabilities.connected_devices.append(device_info)
        except json.JSONDecodeError:
            pass

    def _detect_flutter_devices(self):
        """Detect connected Flutter devices (flutter devices --machine)."""
        flutter = self.capabilities.capabilities.get("flutter")
        if not flutter or not flutter.is_available:
            return

        flutter_path = flutter.path or "flutter"
        result = self._run_command([flutter_path, "devices", "--machine"], timeout=15)
        if not result:
            return

        try:
            devices = json.loads(result)
            for dev in devices:
                device_id = dev.get("id", "")
                device_name = dev.get("name", "unknown")
                platform_name = dev.get("platform", "unknown")
                is_emulator = dev.get("emulator", False)

                # Skip if already detected by adb/xcrun
                already_detected = any(
                    d.device_id == device_id for d in self.capabilities.connected_devices
                )
                if already_detected:
                    continue

                device_info = DeviceInfo(
                    device_id=device_id,
                    device_name=device_name,
                    device_type="emulator" if is_emulator else "physical",
                    platform=platform_name,
                    is_online=True,
                )
                self.capabilities.connected_devices.append(device_info)
        except (json.JSONDecodeError, TypeError):
            pass
    
    # ─── Helpers ───────────────────────────────────────
    
    def _check_command(
        self,
        command: str,
        version_args: List[str] = None,
        version_pattern: str = None,
        timeout: int = 5,
    ) -> Capability:
        """Check if a command is available and get its version."""
        import re
        
        cap = Capability(name=command, category="unknown")
        
        cmd_path = shutil.which(command)
        if not cmd_path:
            cap.status = CapabilityStatus.NOT_FOUND
            return cap
        
        cap.status = CapabilityStatus.AVAILABLE
        cap.path = cmd_path
        
        if version_args:
            full_cmd = [cmd_path] + version_args
            version_output = self._run_command(full_cmd, timeout=timeout)
            
            if version_output and version_pattern:
                match = re.search(version_pattern, version_output)
                if match:
                    cap.version = match.group(1)
            elif version_output:
                cap.version = version_output.strip().split("\n")[0]
        
        return cap
    
    def _run_command(
        self,
        cmd: List[str],
        timeout: int = 10,
    ) -> Optional[str]:
        """Run a shell command and return stdout."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout or result.stderr
            return output.strip() if output else None
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return None
        except Exception as e:
            logger.debug("Unexpected error getting tool version: %s", e)
            return None
    
    def _get_flutter_version(self, flutter_path: str) -> Optional[str]:
        """Get Flutter version from a specific path."""
        result = self._run_command([flutter_path, "--version"], timeout=15)
        if result:
            import re
            match = re.search(r"Flutter\s+([\d\.]+)", result)
            if match:
                return match.group(1)
        return None
    
    def _extract_device_property(self, line: str, property_name: str) -> str:
        """Extract device property from adb devices -l output."""
        for part in line.split():
            if part.startswith(f"{property_name}:"):
                return part.split(":", 1)[1]
        return "unknown"
    
    def _parse_ios_simulators(self, output: str) -> List[str]:
        """Parse available iOS simulator names from simctl output."""
        simulators = []
        for line in output.split("\n"):
            if "(" in line and ")" in line:
                name = line.split("(")[0].strip()
                if name and name not in simulators:
                    simulators.append(name)
        return simulators


# ─── Global Instance ───────────────────────────────────

_default_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """Get or create the global capability registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = CapabilityRegistry()
    return _default_registry


def scan_environment() -> EnvironmentCapabilities:
    """Quick convenience: scan and return capabilities."""
    return get_capability_registry().scan_all()