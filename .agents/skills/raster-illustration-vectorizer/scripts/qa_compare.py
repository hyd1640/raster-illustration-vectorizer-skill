#!/usr/bin/env python3
"""QA comparison between original raster and assembled SVG output."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def render_svg(svg_path: Path, out_png: Path) -> None:
    cmd = ["inkscape", str(svg_path), "--export-type=png", f"--export-filename={out_png}"]
    subprocess.run(cmd, check=True)


def image_diff(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    m = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    a = a[:m[0], :m[1]]
    b = b[:m[0], :m[1]]
    return float(np.mean(np.abs(a - b)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    tmp_png = args.out.with_suffix(".png")

    render_svg(args.svg, tmp_png)

    orig = np.asarray(Image.open(args.input).convert("RGB"))
    recon = np.asarray(Image.open(tmp_png).convert("RGB"))

    diff = image_diff(orig, recon)

    report = {
        "diff_score_mean_abs_error": diff,
        "note": "Lower is better; 0 means perfect pixel match (rare for vectorization)."
    }

    args.out.write_text(str(report), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
