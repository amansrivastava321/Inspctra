"""
permission_assistant.py - Platform-specific permission detection and guidance.

Rules:
- Inspectra CANNOT grant OS permissions.
- Inspectra CAN detect, explain, open settings, and guide.
- Re-check is required after user acts — never assume permission was granted.
- All subprocess calls use list form. No shell=True.
"""
from __future__ import annotations

import logging
import platform
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


class PermissionAssistant:
    """
    Detect and guide OS permission setup.
    All guidance is platform-conditional.
    """

    def check_macos_accessibility(self) -> bool:
        """
        Check if macOS Accessibility permission is granted.
        Uses osascript — returns False on any non-macOS platform.
        """
        if platform.system() != "Darwin":
            return False
        try:
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process'],
                capture_output=True, text=True, timeout=5, shell=False,
            )
            granted = r.returncode == 0
            if not granted:
                logger.debug("macOS Accessibility: denied (osascript returncode=%d)", r.returncode)
            return granted
        except Exception as exc:
            logger.debug("macOS Accessibility check failed: %s", exc)
            return False

    def check_screencapture(self) -> bool:
        """Check screencapture CLI is available (macOS)."""
        if platform.system() != "Darwin":
            return False
        import shutil
        return bool(shutil.which("screencapture"))

    def open_macos_accessibility_settings(self) -> bool:
        """
        Attempt to open macOS Privacy & Security → Accessibility settings.

        Returns True if the open command succeeded.
        The user must still grant permission manually — Inspectra cannot do this.
        """
        if platform.system() != "Darwin":
            return False
        urls = [
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Accessibility",
        ]
        for url in urls:
            try:
                r = subprocess.run(
                    ["open", url],
                    capture_output=True, text=True, timeout=5, shell=False,
                )
                if r.returncode == 0:
                    return True
            except Exception:
                continue
        return False

    def macos_accessibility_manual_steps(self) -> List[str]:
        return [
            "Open: System Settings → Privacy & Security → Accessibility",
            "Click the '+' button or find your terminal in the list.",
            "Enable: Terminal / iTerm2 / VS Code / Cursor / Python (whichever runs Inspectra).",
            "If prompted, enter your macOS password.",
            "Restart your terminal after granting permission.",
            "Re-run: python -m qa_ai.cli runtime-doctor",
        ]

    def linux_atspi_notes(self) -> List[str]:
        return [
            "Enable AT-SPI in desktop settings:",
            "  gsettings set org.gnome.desktop.interface toolkit-accessibility true",
            "Install pyatspi:",
            "  pip install pyatspi",
            "  # or: sudo apt-get install python3-pyatspi",
            "Install xdotool for keyboard input:",
            "  sudo apt-get install xdotool",
            "Set DISPLAY if running headless:",
            "  export DISPLAY=:0",
        ]

    def windows_pywinauto_notes(self) -> List[str]:
        return [
            "Install pywinauto:",
            "  pip install pywinauto",
            "Enable UIA backend for modern Windows apps:",
            "  backend='uia' is the default in Inspectra.",
            "Run as user (not elevated) for most UIA calls.",
        ]

    def check_macos_screen_recording(self) -> bool:
        """
        Attempt to detect Screen Recording permission on macOS.
        Uses screencapture to a temp file. Returns False on non-macOS.
        Note: this is approximate — screencapture may still work even with a black image.
        """
        if platform.system() != "Darwin":
            return False
        import shutil
        import tempfile
        if not shutil.which("screencapture"):
            return False
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                r = subprocess.run(
                    ["screencapture", "-x", "-t", "png", tmp.name],
                    capture_output=True, text=True, timeout=5, shell=False,
                )
                # screencapture returns 0 even without Screen Recording in some macOS versions
                return r.returncode == 0
        except Exception:
            return False

    def open_macos_screen_recording_settings(self) -> bool:
        """Open macOS Screen Recording privacy settings."""
        if platform.system() != "Darwin":
            return False
        urls = [
            "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_ScreenCapture",
        ]
        for url in urls:
            try:
                r = subprocess.run(
                    ["open", url],
                    capture_output=True, text=True, timeout=5, shell=False,
                )
                if r.returncode == 0:
                    return True
            except Exception:
                continue
        return False

    def macos_screen_recording_manual_steps(self) -> List[str]:
        return [
            "Open: System Settings → Privacy & Security → Screen Recording",
            "Enable your terminal app or Python process.",
            "Restart terminal after granting.",
        ]

    def appium_android_setup_notes(self) -> List[str]:
        """Manual setup steps for Android/Appium testing."""
        return [
            "Install Node.js and npm: https://nodejs.org",
            "Install Appium server: npm install -g appium",
            "Install uiautomator2 driver: appium driver install uiautomator2",
            "Start Appium server: appium",
            "Connect Android device or start emulator:",
            "  - Enable USB debugging on device (Settings → Developer options)",
            "  - Or: emulator -avd <avd_name>  (Android Studio AVD Manager)",
            "Verify: adb devices  # device must appear",
            "Inspectra cannot grant Android permissions — device/emulator must be running.",
        ]

    def appium_ios_setup_notes(self) -> List[str]:
        """Manual setup steps for iOS/Appium testing."""
        return [
            "iOS testing requires macOS with Xcode installed.",
            "Install Xcode from App Store.",
            "Install Xcode command line tools: xcode-select --install",
            "Install Node.js and npm: https://nodejs.org",
            "Install Appium server: npm install -g appium",
            "Install xcuitest driver: appium driver install xcuitest",
            "Start Appium server: appium",
            "Connect iOS device or start Simulator:",
            "  - Device: Trust the Mac when prompted",
            "  - Simulator: open -a Simulator",
            "Inspectra cannot start simulators/devices automatically.",
        ]

    def appium_server_not_running_note(self, url: str = "http://localhost:4723") -> List[str]:
        """Steps to start Appium server."""
        return [
            f"Appium server not reachable at {url}",
            "Start it: appium",
            "Or: appium --port 4723 --address 127.0.0.1",
            f"Verify: curl {url}/status",
        ]

    def wait_for_user_to_grant_permission(
        self,
        permission_name: str,
        interactive: bool = True,
    ) -> None:
        """
        Pause and ask the user to manually grant a permission.
        Only blocks in interactive mode.
        """
        if not interactive:
            logger.info("Non-interactive: skipping wait for permission '%s'", permission_name)
            return
        print(f"\n[ACTION REQUIRED] Grant '{permission_name}' permission.")
        print("Press Enter after granting permission (or Ctrl+C to skip)...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("Skipped.")

    def recheck_macos_accessibility(self, interactive: bool = True) -> bool:
        """
        Wait for user to grant permission then re-check.
        Returns True only if re-check confirms permission granted.
        Do not claim permission was granted unless check passes.
        """
        self.wait_for_user_to_grant_permission("macOS Accessibility", interactive=interactive)
        granted = self.check_macos_accessibility()
        if granted:
            print("[OK] macOS Accessibility permission confirmed.")
        else:
            print("[FAIL] macOS Accessibility still not granted. Check steps above.")
        return granted
