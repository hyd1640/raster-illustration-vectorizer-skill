#!/usr/bin/env python3
"""Trace segmented raster elements to SVG using vtracer.

The script fails clearly if vtracer is not installed. It does not silently embed
raster images into SVG because that would produce a misleading non-vector result.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List


VTRACER_PRESETS = {
    "low": {
        "filter_speckle": "2",
        "color_precision": "7",
        "layer_difference": "12",
        "length_threshold": "3.5",
        "max_iterations": "8",
        "splice_threshold": "35",
        "path_precision": "3",
    },
    "medium": {
        "filter_speckle": "6",
        "color_precision": "6",
        "layer_difference": "16",
        "length_threshold": "4.5",
        "max_iterations": "10",
        "splice_threshold": "45",
        "path_precision": "3",
    },
    "high": {
        "filter_speckle": "12",
        "color_precision": "5",
        "layer_difference": "24",
        "length_threshold": "6.5",
        "max_iterations": "12",
        "splice_threshold": "60",
        "path_precision": "2",
    },
}

MODE_MAP = {
    "spline": "spline",
    "polygon": "polygon",
    # V1 line-art still uses vtracer mode syntax after upstream preprocessing.
    "line-art": "spline",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run(cmd: List[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(cmd)
            + "\nSTDOUT:\n"
            + proc.stdout
            + "\nSTDERR:\n"
            + proc.stderr
        )


def trace_one(input_png: Path, output_svg: Path, trace_mode: str, smoothing_level: str, noise_filter_level: str) -> None:
    vtracer = shutil.which("vtracer")
    if not vtracer:
        raise RuntimeError(
            "vtracer is not installed or not on PATH. Install it first, for example: cargo install vtracer"
        )

    preset = VTRACER_PRESETS[noise_filter_level]
    mode = MODE_MAP[trace_mode]
    ensure_dir(output_svg.parent)

    cmd = [
        vtracer,
        "--input",
        str(input_png),
        "--output",
        str(output_svg),
        "--colormode",
        "color",
        "--hierarchical",
        "stacked",
        "--mode",
        mode,
        "--filter_speckle",
        preset["filter_speckle"],
        "--color_precision",
        preset["color_precision"],
        "--layer_difference",
        preset["layer_difference"],
        "--length_threshold",
        preset["length_threshold"],
        "--max_iterations",
        preset["max_iterations"],
        "--splice_threshold",
        preset["splice_threshold"],
        "--path_precision",
        preset["path_precision"],
    ]

    # Higher smoothing should produce fewer, smoother paths.
    if smoothing_level == "high":
        cmd[cmd.index("--length_threshold") + 1] = "7.5"
        cmd[cmd.index("--splice_threshold") + 1] = "65"
    elif smoothing_level == "low":
        cmd[cmd.index("--length_threshold") + 1] = "3.0"
        cmd[cmd.index("--splice_threshold") + 1] = "30"

    run(cmd)

    svgo = shutil.which("svgo")
    if svgo:
        tmp = output_svg.with_suffix(".svgo.svg")
        run([svgo, "-i", str(output_svg), "-o", str(tmp)])
        tmp.replace(output_svg)


def trace_all(layout_path: Path, assets_dir: Path, vectors_dir: Path, trace_mode: str, smoothing_level: str, noise_filter_level: str) -> Dict[str, Any]:
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    ensure_dir(vectors_dir)
    traced = 0

    for element in layout.get("elements", []):
        asset_rel = element["asset"]
        input_png = assets_dir / asset_rel
        vector_rel = str(Path(asset_rel).with_suffix(".svg"))
        output_svg = vectors_dir / vector_rel
        element_mode = element.get("trace_mode", trace_mode) or trace_mode
        element_mode = trace_mode if element_mode not in MODE_MAP else element_mode
        trace_one(input_png, output_svg, element_mode, smoothing_level, noise_filter_level)
        element["vector"] = vector_rel
        element["trace_mode"] = element_mode
        traced += 1

    layout["trace"] = {
        "trace_mode": trace_mode,
        "smoothing_level": smoothing_level,
        "noise_filter_level": noise_filter_level,
        "traced_count": traced,
        "optimizer": "svgo" if shutil.which("svgo") else None,
    }
    layout_path.write_text(json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8")
    return layout


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace segmented elements to SVG.")
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--vectors-dir", type=Path, required=True)
    parser.add_argument("--trace-mode", choices=["spline", "polygon", "line-art"], default="spline")
    parser.add_argument("--smoothing-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--noise-filter-level", choices=["low", "medium", "high"], default="medium")
    args = parser.parse_args()

    layout = trace_all(
        args.layout,
        args.assets_dir,
        args.vectors_dir,
        args.trace_mode,
        args.smoothing_level,
        args.noise_filter_level,
    )
    print(json.dumps({"traced_count": layout.get("trace", {}).get("traced_count")}, indent=2))


if __name__ == "__main__":
    main()
