#!/usr/bin/env python3
"""Segment a raster illustration into inspectable element crops.

V1 uses conservative connected-component segmentation. It does not attempt
reliable semantic recognition. The output element names are stable generic IDs
that can be manually edited in analysis/layout.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("segment_elements.py requires opencv-python") from exc


SEGMENTATION_PRESETS = {
    "low": {"min_area_ratio": 0.00055, "kernel": 9, "dilate_iterations": 2, "margin": 10},
    "medium": {"min_area_ratio": 0.00018, "kernel": 5, "dilate_iterations": 1, "margin": 8},
    "high": {"min_area_ratio": 0.00005, "kernel": 3, "dilate_iterations": 0, "margin": 6},
}

TYPE_DIRS = {
    "icon": "icons",
    "line": "lines",
    "shape": "shapes",
    "compound": "compounds",
}

TYPE_Z_BASE = {
    "shape": 10_000,
    "compound": 20_000,
    "icon": 30_000,
    "line": 40_000,
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def estimate_background(arr: np.ndarray) -> np.ndarray:
    h, w, _ = arr.shape
    border = np.concatenate(
        [arr[: max(1, h // 40), :, :].reshape(-1, 3), arr[-max(1, h // 40):, :, :].reshape(-1, 3), arr[:, : max(1, w // 40), :].reshape(-1, 3), arr[:, -max(1, w // 40):, :].reshape(-1, 3)],
        axis=0,
    )
    return np.median(border, axis=0)


def load_text_regions(report_path: Path | None) -> List[Tuple[int, int, int, int]]:
    if report_path is None or not report_path.exists():
        return []
    data = json.loads(report_path.read_text(encoding="utf-8"))
    out = []
    for region in data.get("likely_text_regions", []):
        bbox = region.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            out.append(tuple(int(v) for v in bbox))
    return out


def build_foreground_mask(arr: np.ndarray, level: str, text_regions: List[Tuple[int, int, int, int]], exclude_text: bool) -> np.ndarray:
    bg = estimate_background(arr)
    dist = np.linalg.norm(arr.astype(np.float32) - bg.astype(np.float32), axis=2)
    fg = (dist > 18).astype(np.uint8) * 255

    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    preset = SEGMENTATION_PRESETS[level]
    kernel_size = int(preset["kernel"])
    kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
    mask = cv2.bitwise_or(fg, edges)

    if preset["dilate_iterations"]:
        mask = cv2.dilate(mask, kernel, iterations=int(preset["dilate_iterations"]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    if exclude_text:
        for x, y, w, h in text_regions:
            pad = 2
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(mask.shape[1], x + w + pad)
            y1 = min(mask.shape[0], y + h + pad)
            mask[y0:y1, x0:x1] = 0

    return mask


def classify_component(x: int, y: int, w: int, h: int, area: int, canvas_w: int, canvas_h: int) -> str:
    rel_area = area / max(1, canvas_w * canvas_h)
    aspect = w / max(1, h)
    rel_w = w / max(1, canvas_w)
    rel_h = h / max(1, canvas_h)

    if rel_area > 0.08 or rel_w > 0.55 or rel_h > 0.55:
        return "shape"
    if aspect > 4.5 or aspect < 0.22:
        return "line"
    if rel_area > 0.025 or rel_w > 0.28 or rel_h > 0.28:
        return "compound"
    return "icon"


def crop_with_alpha(arr: np.ndarray, labels: np.ndarray, component_id: int, bbox: Tuple[int, int, int, int], margin: int) -> Image.Image:
    x, y, w, h = bbox
    h_img, w_img = labels.shape
    x0 = max(0, x - margin)
    y0 = max(0, y - margin)
    x1 = min(w_img, x + w + margin)
    y1 = min(h_img, y + h + margin)

    crop_rgb = arr[y0:y1, x0:x1, :]
    crop_alpha = (labels[y0:y1, x0:x1] == component_id).astype(np.uint8) * 255
    rgba = np.dstack([crop_rgb, crop_alpha])
    return Image.fromarray(rgba, mode="RGBA")


def segment(input_path: Path, assets_dir: Path, layout_path: Path, report_path: Path | None, level: str, exclude_text: bool) -> Dict[str, Any]:
    image = Image.open(input_path).convert("RGB")
    arr = np.asarray(image)
    canvas_w, canvas_h = image.size
    ensure_dir(assets_dir)
    for subdir in TYPE_DIRS.values():
        ensure_dir(assets_dir / subdir)

    text_regions = load_text_regions(report_path)
    mask = build_foreground_mask(arr, level, text_regions, exclude_text)

    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    preset = SEGMENTATION_PRESETS[level]
    min_area = max(8, int(canvas_w * canvas_h * float(preset["min_area_ratio"])))
    margin = int(preset["margin"])

    elements: List[Dict[str, Any]] = []
    counters = {"icon": 0, "line": 0, "shape": 0, "compound": 0}

    for component_id in range(1, num):
        x, y, w, h, area = [int(v) for v in stats[component_id]]
        if area < min_area:
            continue
        if w <= 2 or h <= 2:
            continue

        element_type = classify_component(x, y, w, h, area, canvas_w, canvas_h)
        counters[element_type] += 1
        element_id = f"{element_type}_{counters[element_type]:03d}"
        type_dir = TYPE_DIRS[element_type]
        asset_rel = f"{type_dir}/{element_id}.png"
        asset_path = assets_dir / asset_rel

        crop = crop_with_alpha(arr, labels, component_id, (x, y, w, h), margin)
        crop.save(asset_path)

        elements.append(
            {
                "id": element_id,
                "name": element_id,
                "type": element_type,
                "bbox": [x, y, w, h],
                "asset": asset_rel,
                "z_index": TYPE_Z_BASE[element_type] + y,
                "trace_method": "vtracer",
                "trace_mode": "spline",
                "source_confidence": "medium" if level != "high" else "low",
                "notes": "Generic V1 element ID. Rename manually if semantic naming is required.",
            }
        )

    elements.sort(key=lambda e: e["z_index"])
    layout = {
        "source_image": str(input_path),
        "canvas": {"width": canvas_w, "height": canvas_h},
        "segmentation_level": level,
        "text_regions_excluded": exclude_text,
        "element_count": len(elements),
        "elements": elements,
    }

    ensure_dir(layout_path.parent)
    layout_path.write_text(json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8")

    mask_path = layout_path.parent / "segmentation_mask.png"
    Image.fromarray(mask).save(mask_path)
    return layout


def main() -> None:
    parser = argparse.ArgumentParser(description="Segment a raster illustration into element assets.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--image-report", type=Path)
    parser.add_argument("--segmentation-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--exclude-text-regions", action="store_true")
    args = parser.parse_args()

    layout = segment(
        args.input,
        args.assets_dir,
        args.layout,
        args.image_report,
        args.segmentation_level,
        args.exclude_text_regions,
    )
    print(json.dumps({"element_count": layout["element_count"], "layout": str(args.layout)}, indent=2))


if __name__ == "__main__":
    main()
