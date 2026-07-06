#!/usr/bin/env python3
"""End-to-end pipeline for raster illustration vectorization."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--workdir", type=Path, default=Path("work"))
    parser.add_argument("--profile", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--segmentation-level", choices=["low", "medium", "high"])
    parser.add_argument("--smoothing-level", choices=["low", "medium", "high"])
    parser.add_argument("--noise-filter-level", choices=["low", "medium", "high"])
    args = parser.parse_args()

    workdir = args.workdir

    seg = args.segmentation_level or args.profile
    smo = args.smoothing_level or args.profile
    noi = args.noise_filter_level or args.profile

    analysis = workdir / "analysis"
    assets = workdir / "assets"
    vectors = workdir / "vectors"
    output = workdir / "output"
    preview = workdir / "preview"

    report = analysis / "image_report.json"
    layout = analysis / "layout.json"

    run([
        "python",
        ".agents/skills/raster-illustration-vectorizer/scripts/analyze_image.py",
        str(args.input),
        "--out",
        str(report),
    ])

    run([
        "python",
        ".agents/skills/raster-illustration-vectorizer/scripts/segment_elements.py",
        str(args.input),
        "--assets-dir",
        str(assets),
        "--layout",
        str(layout),
        "--image-report",
        str(report),
        "--segmentation-level",
        seg,
    ])

    run([
        "python",
        ".agents/skills/raster-illustration-vectorizer/scripts/trace_elements.py",
        "--layout",
        str(layout),
        "--assets-dir",
        str(assets),
        "--vectors-dir",
        str(vectors),
        "--trace-mode",
        "spline",
        "--smoothing-level",
        smo,
        "--noise-filter-level",
        noi,
    ])

    final_svg = output / "final.svg"

    run([
        "python",
        ".agents/skills/raster-illustration-vectorizer/scripts/assemble_svg.py",
        "--layout",
        str(layout),
        "--vectors-dir",
        str(vectors),
        "--out",
        str(final_svg),
    ])

    print("Done:", final_svg)


if __name__ == "__main__":
    main()
