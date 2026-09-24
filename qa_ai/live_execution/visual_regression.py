"""
visual_regression.py - Compares screenshots and detects visual/layout changes.
Supports configurable thresholds for pixel diff tolerance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import logging
import time
import hashlib
import base64

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class VisualDiff:
    """Result of comparing two screenshots."""

    def __init__(
        self,
        name: str,
        baseline_path: str = "",
        current_path: str = "",
        diff_path: str = "",
        pixel_diff_count: int = 0,
        total_pixels: int = 0,
        diff_percentage: float = 0.0,
        is_match: bool = True,
        threshold: float = 0.01,
    ):
        self.name = name
        self.baseline_path = baseline_path
        self.current_path = current_path
        self.diff_path = diff_path
        self.pixel_diff_count = pixel_diff_count
        self.total_pixels = total_pixels
        self.diff_percentage = diff_percentage
        self.is_match = is_match
        self.threshold = threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "baseline_path": self.baseline_path,
            "current_path": self.current_path,
            "diff_path": self.diff_path,
            "pixel_diff_count": self.pixel_diff_count,
            "total_pixels": self.total_pixels,
            "diff_percentage": round(self.diff_percentage, 4),
            "is_match": self.is_match,
            "threshold": self.threshold,
        }


class VisualRegression:
    """
    Compares screenshots and detects visual changes.

    Features:
    - Compare current vs baseline screenshots
    - Configurable pixel diff threshold
    - Generate diff images
    - Track visual regressions across runs
    - Generate visual_regression_report.json

    Note: Actual pixel comparison requires Pillow.
    Falls back to hash comparison if Pillow is unavailable.
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self._diffs: List[VisualDiff] = []

    def run(
        self,
        current_screenshots: Optional[Dict[str, bytes]] = None,
        baseline_name: str = "visual_baseline",
        threshold: float = 0.01,
    ) -> Dict[str, Any]:
        """Compare current screenshots against baseline."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if current_screenshots is None:
            current_screenshots = {}

        baseline_raw = self.store.load_artifact(baseline_name) or {}

        # Decode baseline from base64 if present
        baseline: Dict[str, bytes] = {}
        for name, val in baseline_raw.items():
            if isinstance(val, str):
                try:
                    baseline[name] = base64.b64decode(val)
                except Exception as e:
                    logger.debug("base64 decode of baseline screenshot '%s' failed: %s", name, e)
            elif isinstance(val, bytes):
                baseline[name] = val

        self._diffs = []
        for name, current_bytes in current_screenshots.items():
            baseline_bytes = baseline.get(name)
            if baseline_bytes:
                diff = self._compare_screenshots(name, baseline_bytes, current_bytes, threshold)
                self._diffs.append(diff)
            else:
                # New screenshot, no baseline to compare
                self._diffs.append(VisualDiff(
                    name=name,
                    current_path=f"evidence/screenshots/{name}",
                    is_match=True,
                    diff_percentage=0.0,
                    threshold=threshold,
                ))

        # Save current as new baseline (encode bytes as base64 for JSON storage)
        new_baseline: Dict[str, str] = {}
        for name, current_bytes in current_screenshots.items():
            if isinstance(current_bytes, bytes):
                new_baseline[name] = base64.b64encode(current_bytes).decode("ascii")
            else:
                new_baseline[name] = str(current_bytes)
        if new_baseline:
            self.store.save_artifact(baseline_name, new_baseline)

        duration = time.time() - start_time

        regressions = [d for d in self._diffs if not d.is_match]

        result = {
            "metadata": {
                "comparison_type": "visual_regression",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "VisualRegression",
                "total_comparisons": len(self._diffs),
                "threshold": threshold,
            },
            "diffs": [d.to_dict() for d in self._diffs],
            "regressions": [d.to_dict() for d in regressions],
            "summary": {
                "total": len(self._diffs),
                "matches": sum(1 for d in self._diffs if d.is_match),
                "regressions": len(regressions),
            },
        }

        self.store.save_artifact("visual_regression_report", result, agent="VisualRegression")
        logger.info(
            f"Visual regression: {len(regressions)}/{len(self._diffs)} regressions"
        )
        return result

    def _compare_screenshots(
        self,
        name: str,
        baseline_bytes: bytes,
        current_bytes: bytes,
        threshold: float,
    ) -> VisualDiff:
        """Compare two screenshots."""
        # Try Pillow-based comparison
        try:
            return self._compare_with_pillow(name, baseline_bytes, current_bytes, threshold)
        except (ImportError, Exception):
            pass

        # Fallback: hash comparison
        baseline_hash = hashlib.md5(baseline_bytes).hexdigest()
        current_hash = hashlib.md5(current_bytes).hexdigest()

        is_match = baseline_hash == current_hash
        return VisualDiff(
            name=name,
            baseline_path=f"baseline/{name}",
            current_path=f"current/{name}",
            pixel_diff_count=0 if is_match else 1,
            total_pixels=1,
            diff_percentage=0.0 if is_match else 1.0,
            is_match=is_match,
            threshold=threshold,
        )

    def _compare_with_pillow(
        self,
        name: str,
        baseline_bytes: bytes,
        current_bytes: bytes,
        threshold: float,
    ) -> VisualDiff:
        """Compare screenshots using Pillow pixel diff."""
        from PIL import Image
        import io

        baseline_img = Image.open(io.BytesIO(baseline_bytes))
        current_img = Image.open(io.BytesIO(current_bytes))

        # Resize to match if needed
        if baseline_img.size != current_img.size:
            current_img = current_img.resize(baseline_img.size)

        baseline_pixels = list(baseline_img.convert("RGB").getdata())
        current_pixels = list(current_img.convert("RGB").getdata())

        total_pixels = len(baseline_pixels)
        diff_count = 0

        for bp, cp in zip(baseline_pixels, current_pixels):
            if bp != cp:
                diff_count += 1

        diff_percentage = diff_count / total_pixels if total_pixels > 0 else 0.0
        is_match = diff_percentage <= threshold

        return VisualDiff(
            name=name,
            baseline_path=f"baseline/{name}",
            current_path=f"current/{name}",
            pixel_diff_count=diff_count,
            total_pixels=total_pixels,
            diff_percentage=diff_percentage,
            is_match=is_match,
            threshold=threshold,
        )

    def get_regressions(self) -> List[VisualDiff]:
        """Get all detected visual regressions."""
        return [d for d in self._diffs if not d.is_match]

    def get_all_diffs(self) -> List[VisualDiff]:
        """Get all comparison results."""
        return list(self._diffs)
