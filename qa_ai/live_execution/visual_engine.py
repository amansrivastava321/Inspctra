"""
visual_engine.py - Safe offline visual regression testing engine.

Uses pre-installed Pillow to perform pixel-by-pixel comparisons,
highlight differences in red, and calculate mismatch ratio.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from PIL import Image, ImageChops

logger = logging.getLogger(__name__)

# Decompression bomb mitigation: max 16 megapixels
MAX_PIXELS = 16_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

# Physical constraints
MAX_DIMENSION = 4000
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class VisualEngine:
    """
    Local image comparator for visual regression testing.
    """

    @staticmethod
    def compare_images(
        baseline_path: str | Path,
        current_path: str | Path,
        diff_out_path: str | Path,
        color_tolerance: int = 15,
    ) -> float:
        """
        Compare two images. Highlights differences in a red-tinted transparent overlay.
        Returns the ratio of mismatched pixels (float between 0.0 and 1.0).

        If dimensions mismatch, the current image is resized to match the baseline image.
        """
        b_path = Path(baseline_path)
        c_path = Path(current_path)
        d_path = Path(diff_out_path)

        # 1. Enforce file size check
        if b_path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError(f"Baseline image file size exceeds limit: {b_path.name}")
        if c_path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError(f"Current image file size exceeds limit: {c_path.name}")

        # 2. Open images
        img1 = Image.open(b_path).convert("RGB")
        img2 = Image.open(c_path).convert("RGB")

        # 3. Dimension limit checks
        if img1.width > MAX_DIMENSION or img1.height > MAX_DIMENSION:
            raise ValueError(f"Baseline image dimensions exceed limit: {img1.size}")
        if img2.width > MAX_DIMENSION or img2.height > MAX_DIMENSION:
            raise ValueError(f"Current image dimensions exceed limit: {img2.size}")

        # 4. Handle dimension mismatch
        if img1.size != img2.size:
            logger.warning(
                "VisualEngine: dimension mismatch (baseline: %s, current: %s). Resizing current to match baseline.",
                img1.size,
                img2.size,
            )
            img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)

        # 5. Pixel comparison and diff highlighting
        pixels1 = img1.load()
        pixels2 = img2.load()
        width, height = img1.size
        mismatched = 0

        # Create diff overlay (transparent by default, red where mismatched)
        diff_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        diff_pixels = diff_img.load()

        for y in range(height):
            for x in range(width):
                r1, g1, b1 = pixels1[x, y]
                r2, g2, b2 = pixels2[x, y]
                # Euclidean distance in RGB color space
                dist = ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5
                if dist > color_tolerance:
                    mismatched += 1
                    diff_pixels[x, y] = (255, 0, 0, 255)  # Bright red for mismatch
                else:
                    diff_pixels[x, y] = (0, 0, 0, 0)

        total_pixels = width * height
        mismatch_ratio = mismatched / total_pixels

        # 6. Save diff output file if there are mismatches
        d_path.parent.mkdir(parents=True, exist_ok=True)
        if mismatched > 0:
            diff_img.save(d_path)
        else:
            # Save a blank transparent image to satisfy path expectation
            diff_img.save(d_path)

        return mismatch_ratio
