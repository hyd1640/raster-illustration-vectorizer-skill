#!/usr/bin/env python3
"""Analyze a raster illustration before vectorization.

This script intentionally does not OCR text. It only flags likely text-like
regions as small, dense, high-contrast connected components so downstream steps
can exclude or review them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def rgb_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def estimate_background(arr: np.ndarray) -> List[int]:
    """Estimate background from image border median."""
    h, w, _ = arr.shape
    border = np.concatenate(
        [
            arr[0: max(1, h // 40), :, :].reshape(-1, 3),
            arr[max(0, h - h // 40): h, :, :].reshape(-1, 3),
            arr[:, 0: max(1, w // 40), :].reshape(-1, 3),
            arr[:, max(0, w - w // 40): w, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return np.median(border, axis=0).round().astype(int).tolist()


def approximate_color_count(arr: np.ndarray, sample_limit: int = 100_000) -> int:
    flat = arr.reshape(-1, 3)
    if flat.shape[0] > sample_limit:
        idx = np.linspace(0, flat.shape[0] - 1, sample_limit).astype(int)
        flat = flat[idx]
    # Quantize to 5 bits/channel for a stable approximate count.
    quantized = (flat // 8).astype(np.uint8)
    return int(np.unique(quantized, axis=0).shape[0])


def edge_density(arr: np.ndarray) -> float:
    gray = np.asarray(Image.fromarray(arr).convert("L"))
    if cv2 is None:
        gx, gy = np.gradient(gray.astype(float))
        mag = np.hypot(gx, gy)
        return float((mag > 24).mean())
    edges = cv2.Canny(gray, 60, 160)
    return float((edges > 0).mean())


def likely_text_regions(arr: np.ndarray) -> List[Dict[str, Any]]:
    """Flag dense small high-contrast regions. This is not OCR."""
    if cv2 is None:
        return []

    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    # Emphasize dark strokes against light background.
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        9,
    )
    num, labels, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    regions: List[Dict[str, Any]] = []
    h, w = gray.shape
    img_area = h * w
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if area < 8 or area > img_area * 0.01:
            continue
        aspect = bw / max(1, bh)
        fill = area / max(1, bw * bh)
        # Text-like components are often compact, stroke-dense, and small.
        if 0.15 <= aspect <= 8 and fill >= 0.08 and bh <= h * 0.08 and bw <= w * 0.25:
            regions.append(
                {
                    "bbox": [int(x), int(y), int(bw), int(bh)],
                    "area": int(area),
                    "confidence": "low",
                    "note": "Likely text-like small high-contrast region; not OCR.",
                }
            )
    return regions[:200]


def analyze(input_path: Path) -> Dict[str, Any]:
    image = rgb_image(input_path)
    arr = np.asarray(image)
    width, height = image.size
    bg = estimate_background(arr)
    colors = approximate_color_count(arr)
    ed = edge_density(arr)
    min_dim = min(width, height)

    return {
        "input_path": str(input_path),
        "width": width,
        "height": height,
        "min_dimension": min_dim,
        "background_rgb_estimate": bg,
        "approx_color_count_5bit": colors,
        "edge_density": round(ed, 6),
        "low_resolution_warning": bool(min_dim < 1200),
        "recommended_scale": 2 if min_dim < 1200 else 1,
        "likely_text_regions": likely_text_regions(arr),
        "notes": [
            "Text-like regions are only flagged; no OCR is performed.",
            "Approximate color count is quantized and intended for preset selection, not color science.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a raster image before vectorization.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="Output JSON report path.")
    args = parser.parse_args()

    ensure_dir(args.out.parent)
    report = analyze(args.input)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
