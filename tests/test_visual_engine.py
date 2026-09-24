"""
test_visual_engine.py - Unit tests for the VisualEngine.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator
import pytest
from PIL import Image

from qa_ai.live_execution.visual_engine import VisualEngine


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_solid_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> None:
    img = Image.new("RGB", size, color)
    img.save(path)


def test_perfect_match(temp_dir: Path) -> None:
    b_path = temp_dir / "baseline.png"
    c_path = temp_dir / "current.png"
    d_path = temp_dir / "diff.png"

    create_solid_image(b_path, (255, 255, 255))
    create_solid_image(c_path, (255, 255, 255))

    ratio = VisualEngine.compare_images(b_path, c_path, d_path)
    assert ratio == 0.0


def test_mismatch_ratio(temp_dir: Path) -> None:
    b_path = temp_dir / "baseline.png"
    c_path = temp_dir / "current.png"
    d_path = temp_dir / "diff.png"

    # Baseline is white
    create_solid_image(b_path, (255, 255, 255))

    # Current has different color (red)
    create_solid_image(c_path, (255, 0, 0))

    ratio = VisualEngine.compare_images(b_path, c_path, d_path)
    assert ratio == 1.0
    assert d_path.is_file()


def test_dimension_mismatch_resizing(temp_dir: Path) -> None:
    b_path = temp_dir / "baseline.png"
    c_path = temp_dir / "current.png"
    d_path = temp_dir / "diff.png"

    create_solid_image(b_path, (255, 255, 255), size=(100, 100))
    create_solid_image(c_path, (255, 255, 255), size=(200, 200))

    # Resizing should make them match, resulting in 0.0 ratio
    ratio = VisualEngine.compare_images(b_path, c_path, d_path)
    assert ratio == 0.0


def test_size_bounds_checking(temp_dir: Path) -> None:
    b_path = temp_dir / "baseline.png"
    c_path = temp_dir / "current.png"
    d_path = temp_dir / "diff.png"

    create_solid_image(b_path, (255, 255, 255), size=(5000, 100))  # Exceeds max 4000 limit
    create_solid_image(c_path, (255, 255, 255), size=(100, 100))

    with pytest.raises(ValueError) as exc:
        VisualEngine.compare_images(b_path, c_path, d_path)
    assert "dimensions exceed limit" in str(exc.value)
