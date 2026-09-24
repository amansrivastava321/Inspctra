"""Abstract base class for all UI automation drivers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from qa_ai.interactive_runtime.schemas import (
    DriverCapabilities,
    ScreenState,
    WindowInfo,
)


class UniversalUIDriver(ABC):
    """Protocol every platform driver must satisfy.

    Implementors must never fake support — if a capability is unavailable on
    the current OS or without the required tool, they must return False / None
    and set the appropriate DriverStatus in capabilities().
    """

    @classmethod
    @abstractmethod
    def supports(cls, app_type: str) -> bool:
        """Return True if this driver can handle the given app_type on the current platform."""

    @abstractmethod
    def capabilities(self) -> DriverCapabilities:
        """Return what this driver can actually do right now."""

    @abstractmethod
    def find_app_window(self, app_name: str) -> Optional[WindowInfo]:
        """Find the main window of the running app. Return None if not found."""

    @abstractmethod
    def observe_screen(self) -> ScreenState:
        """Return current screen state (visible elements, text, error indicators)."""

    @abstractmethod
    def get_accessibility_tree(self) -> dict:
        """Return raw accessibility tree as a dict. Empty dict if unavailable."""

    @abstractmethod
    def click_element(self, label: str, element_type: str = "button") -> bool:
        """Click a UI element by accessibility label. Return False if not found."""

    @abstractmethod
    def click_coordinates(self, x: int, y: int) -> bool:
        """Click at absolute screen coordinates. Return False if unsupported."""

    @abstractmethod
    def type_text(self, text: str, element_label: Optional[str] = None) -> bool:
        """Type text, optionally focused on the element with the given label."""

    @abstractmethod
    def press_key(self, key: str) -> bool:
        """Press a named key (e.g. 'Return', 'Tab', 'Escape')."""

    @abstractmethod
    def wait_for_text(self, text: str, timeout: float = 5.0) -> bool:
        """Poll until the given text appears on screen or timeout elapses."""

    @abstractmethod
    def wait_for_element(self, label: str, timeout: float = 5.0) -> bool:
        """Poll until the element with the given label appears or timeout elapses."""

    @abstractmethod
    def take_screenshot(self, path: str) -> bool:
        """Capture current screen to file at path. Return False if unsupported."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by this driver."""
