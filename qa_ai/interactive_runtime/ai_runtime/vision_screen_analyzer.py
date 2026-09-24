"""
vision_screen_analyzer.py - Analyze screenshots or ScreenState to infer UI structure.

If no vision model is configured → returns CapabilityGap, not fake results.
Supports local Ollama (qwen2.5vl) if configured.
Falls back to ScreenState/accessibility tree if vision unavailable.
No app-specific hardcoding.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.schemas import (
    CapabilityGap,
    CapabilityStatus,
    ScreenState,
    UIElement,
    VisionAnalysis,
    VisionAnalysisConfig,
)

logger = logging.getLogger(__name__)


class VisionScreenAnalyzer:
    """
    Analyze screenshots / ScreenState to infer UI structure.

    Priority:
      1. If vision model configured and available → use it
      2. Fall back to ScreenState elements + visible_text
      3. If screen state also missing → return CapabilityGap
    """

    def __init__(self, config: Optional[VisionAnalysisConfig] = None):
        self._config = config or VisionAnalysisConfig()
        self._provider_available: Optional[bool] = None

    def analyze(
        self,
        screen: Optional[ScreenState] = None,
        screenshot_path: Optional[str] = None,
        previous_screenshot_path: Optional[str] = None,
    ) -> VisionAnalysis:
        """
        Analyze current screen state and/or screenshot.

        Returns VisionAnalysis. If no model and no screen state → capability_gap is set.
        """
        screen_id = screen.screen_id if screen else ""

        # Try vision model first if enabled
        if self._config.enabled and self._is_provider_available():
            return self._analyze_with_vision_model(
                screen_id, screen, screenshot_path, previous_screenshot_path
            )

        # Fall back to accessibility tree / screen state
        if screen and (screen.elements or screen.visible_text):
            return self._analyze_from_screen_state(screen)

        # Nothing available
        gap = CapabilityGap(
            capability="vision_screen_analysis",
            status=CapabilityStatus.UNAVAILABLE,
            reason="No vision model configured and no ScreenState available.",
            workaround="Configure vision_analysis.provider in ai_runtime config or ensure ScreenState is populated.",
            todo="Configure local Ollama with qwen2.5vl or another multimodal model.",
        )
        return VisionAnalysis(
            screen_id=screen_id,
            possible_screen_purpose="unknown",
            uncertainty_score=1.0,
            provider_used="none",
            capability_gap=gap,
        )

    def _analyze_from_screen_state(self, screen: ScreenState) -> VisionAnalysis:
        """Derive VisionAnalysis from existing ScreenState without a vision model."""
        buttons = [e.label for e in screen.buttons if e.label]
        inputs = [e.label or e.placeholder or e.element_type for e in screen.inputs if e.visible]
        menus = [e.label for e in screen.elements if e.element_type in ("tab", "menu") and e.label]

        clickable_regions = [
            {"label": e.label, "type": e.element_type, "selector": e.selector}
            for e in screen.elements
            if e.visible and e.enabled and e.element_type in ("button", "link", "tab", "menu")
        ]

        purpose = self._infer_purpose_from_text(screen.title, screen.visible_text)
        uncertainty = 0.3 if (buttons or inputs) else 0.7

        return VisionAnalysis(
            screen_id=screen.screen_id,
            possible_screen_purpose=purpose,
            inferred_clickable_regions=clickable_regions,
            inferred_buttons=buttons,
            inferred_inputs=inputs,
            inferred_menus=menus,
            uncertainty_score=uncertainty,
            provider_used="accessibility_tree",
            capability_gap=None,
        )

    def _analyze_with_vision_model(
        self,
        screen_id: str,
        screen: Optional[ScreenState],
        screenshot_path: Optional[str],
        previous_screenshot_path: Optional[str],
    ) -> VisionAnalysis:
        """
        Attempt analysis via configured vision model (e.g., Ollama qwen2.5vl).
        Falls back to accessibility tree on any failure.
        """
        try:
            raw = self._call_ollama_vision(screenshot_path)
            if raw:
                return self._parse_vision_output(screen_id, raw, screen)
        except Exception as exc:
            logger.warning("Vision model call failed, falling back to screen state: %s", exc)

        if screen:
            return self._analyze_from_screen_state(screen)

        gap = CapabilityGap(
            capability="vision_screen_analysis",
            status=CapabilityStatus.PARTIAL,
            reason=f"Vision model {self._config.model} failed and no ScreenState available.",
            workaround="Ensure Ollama is running and screenshot path is valid.",
            todo=f"Start Ollama with: ollama pull {self._config.model}",
        )
        return VisionAnalysis(
            screen_id=screen_id,
            possible_screen_purpose="unknown",
            uncertainty_score=0.9,
            provider_used=f"failed:{self._config.model}",
            capability_gap=gap,
        )

    def _call_ollama_vision(self, screenshot_path: Optional[str]) -> Optional[str]:
        """Call vision model via TaskRouter. Returns raw text response or None."""
        if not screenshot_path:
            return None
        img_path = Path(screenshot_path)
        if not img_path.exists():
            logger.warning("Screenshot not found for vision analysis: %s", screenshot_path)
            return None

        try:
            from qa_ai.ai.task_router import ModelTask, get_task_router
            router = get_task_router()
            prompt = (
                "Analyze this UI screenshot. List: "
                "1) Clickable buttons (label, position). "
                "2) Input fields (label/placeholder). "
                "3) Navigation elements. "
                "4) Screen purpose (1 sentence). "
                "5) Visible menus/tabs. "
                "Be concise. JSON format preferred."
            )
            result = router.call(
                ModelTask.VISION_SCREEN_ANALYSIS,
                prompt,
                images=[screenshot_path],
            )
            if result.ok:
                return result.output_text
            logger.debug("Vision TaskRouter gap: %s", result.capability_gap)
        except Exception as exc:
            logger.debug("Vision TaskRouter unavailable, using legacy path: %s", exc)
            return self._call_ollama_vision_legacy(screenshot_path)
        return None

    def _call_ollama_vision_legacy(self, screenshot_path: str) -> Optional[str]:
        """Legacy direct Ollama vision call — only used if TaskRouter unavailable."""
        try:
            import base64
            import json
            import urllib.request
            img_path = Path(screenshot_path)
            with open(img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            payload = json.dumps({
                "model": self._config.model,
                "prompt": (
                    "Analyze this UI screenshot. List buttons, inputs, nav, purpose. JSON preferred."
                ),
                "images": [img_b64],
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data.get("response", "")
        except Exception as exc:
            logger.debug("Legacy Ollama vision call failed: %s", exc)
            return None

    def _parse_vision_output(
        self,
        screen_id: str,
        raw: str,
        screen: Optional[ScreenState],
    ) -> VisionAnalysis:
        """Parse Ollama text response into VisionAnalysis."""
        buttons: List[str] = []
        inputs: List[str] = []
        menus: List[str] = []
        purpose = "unknown"

        lines = raw.splitlines()
        for line in lines:
            ll = line.lower()
            if "button" in ll and ":" in line:
                buttons.append(line.split(":", 1)[-1].strip()[:80])
            elif "input" in ll or "field" in ll:
                inputs.append(line.split(":", 1)[-1].strip()[:80])
            elif "menu" in ll or "tab" in ll or "nav" in ll:
                menus.append(line.split(":", 1)[-1].strip()[:80])
            elif "purpose" in ll or "screen" in ll:
                purpose = line.split(":", 1)[-1].strip()[:120]

        # Supplement with screen state if available
        if screen and self._config.fallback_to_accessibility_tree:
            acc_analysis = self._analyze_from_screen_state(screen)
            buttons = list(dict.fromkeys(buttons + acc_analysis.inferred_buttons))
            inputs = list(dict.fromkeys(inputs + acc_analysis.inferred_inputs))
            menus = list(dict.fromkeys(menus + acc_analysis.inferred_menus))

        return VisionAnalysis(
            screen_id=screen_id,
            possible_screen_purpose=purpose,
            inferred_buttons=buttons[:20],
            inferred_inputs=inputs[:15],
            inferred_menus=menus[:10],
            inferred_clickable_regions=[{"label": b, "type": "button"} for b in buttons[:20]],
            uncertainty_score=0.4,
            provider_used=f"ollama:{self._config.model}",
            raw_analysis=raw[:1000],
        )

    def _is_provider_available(self) -> bool:
        if self._provider_available is not None:
            return self._provider_available
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            self._provider_available = True
        except Exception:
            self._provider_available = False
        return self._provider_available

    @staticmethod
    def _infer_purpose_from_text(title: str, visible_text: List[str]) -> str:
        all_text = f"{title} {' '.join(visible_text[:10])}".lower()
        if any(w in all_text for w in ("login", "sign in", "password", "username")):
            return "login_screen"
        if any(w in all_text for w in ("dashboard", "overview", "summary", "home")):
            return "dashboard"
        if any(w in all_text for w in ("settings", "preferences", "config")):
            return "settings_screen"
        if any(w in all_text for w in ("list", "table", "records", "items")):
            return "list_view"
        if any(w in all_text for w in ("form", "create", "new", "add")):
            return "form_screen"
        if any(w in all_text for w in ("report", "analytics", "chart", "graph")):
            return "analytics_screen"
        return title or "unknown"
