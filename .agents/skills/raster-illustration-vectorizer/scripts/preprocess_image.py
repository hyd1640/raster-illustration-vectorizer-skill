#!/usr/bin/env python3
"""Preprocess raster illustrations for more stable segmentation and tracing."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


NOISE_PRESETS = {
    "low": {"median": 0, "bilateral": False},
    "medium": {"median": 3, "bilateral": True},
    "high": {"median": 5, "bilateral": True},
}

SHARPEN_PRESETS = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.5,
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def preprocess(
    input_path: Path,
    output_path: Path,
    scale: int,
    noise_filter_level: str,
    smoothing_level: str,
    normalize_background: bool,
) -> None:
    image = Image.open(input_path).convert("RGB")

    if scale not in {1, 2, 4}:
        raise ValueError("scale must be one of: 1, 2, 4")

    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)

    arr = np.asarray(image)

    if normalize_background:
        # Convert near-white transparent-looking background remnants into white.
        mask = (arr[:, :, 0] > 245) & (arr[:, :, 1] > 245) & (arr[:, :, 2] > 245)
        arr = arr.copy()
        arr[mask] = [255, 255, 255]

    preset = NOISE_PRESETS[noise_filter_level]
    if cv2 is not None:
        if preset["median"]:
            arr = cv2.medianBlur(arr, int(preset["median"]))
        if preset["bilateral"]:
            # Bilateral filtering preserves edges better than Gaussian blur.
            sigma = 50 if noise_filter_level == "medium" else 75
            arr = cv2.bilateralFilter(arr, d=5, sigmaColor=sigma, sigmaSpace=sigma)
    else:
        if preset["median"]:
            arr = np.asarray(Image.fromarray(arr).filter(ImageFilter.MedianFilter(size=int(preset["median"]))))

    image = Image.fromarray(arr)

    # Mild sharpening after denoising. This is deterministic enhancement, not super-resolution.
    sharpen_amount = SHARPEN_PRESETS[smoothing_level]
    if sharpen_amount > 0:
        image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(80 * sharpen_amount), threshold=3))

    ensure_dir(output_path.parent)
    image.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess an image before vectorization.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scale", type=int, default=1, choices=[1, 2, 4])
    parser.add_argument("--noise-filter-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--smoothing-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--normalize-background", action="store_true")
    args = parser.parse_args()

    preprocess(
        args.input,
        args.out,
        args.scale,
        args.noise_filter_level,
        args.smoothing_level,
        args.normalize_background,
    )
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
