#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2-only pipeline: symbol-sheet extraction → SVG symbol library.

This replaces the legacy V1 full-scene pipeline.
No analysis/segmentation/scene assembly is performed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent


def run(cmd: List[str]) -> None:
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 symbol library pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol-sheet", type=Path)
    group.add_argument("--assets-dir", type=Path)

    parser.add_argument("--workdir", type=Path, default=Path("work_v2"))
    parser.add_argument("--mode", choices=["faithful-trace", "symbol-redraw"], default="faithful-trace")
    parser.add_argument("--trace-profile", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--layout-schema", type=Path, default=None)
    parser.add_argument("--foreground-threshold", type=float, default=18.0)
    parser.add_argument("--min-area-ratio", type=float, default=0.0008)
    parser.add_argument("--max-colors", type=int, default=7)
    parser.add_argument("--fallback-symbol-redraw", action="store_true")

    args = parser.parse_args()

    assets_dir = args.assets_dir or (args.workdir / "assets" / "symbol_candidates")
    out_dir = args.workdir / "output" / "symbol_library"

    # 1. extract (optional)
    if args.symbol_sheet:
        cmd = [
            "python", str(SCRIPT_DIR / "extract_symbol_assets.py"),
            str(args.symbol_sheet),
            "--out-dir", str(assets_dir),
            "--foreground-threshold", str(args.foreground_threshold),
            "--min-area-ratio", str(args.min_area_ratio),
        ]
        if args.layout_schema:
            cmd += ["--layout-schema", str(args.layout_schema)]
        run(cmd)

    # 2. vectorize
    cmd = [
        "python", str(SCRIPT_DIR / "vectorize_symbols.py"),
        str(assets_dir),
        "--out-dir", str(out_dir),
        "--mode", args.mode,
        "--trace-profile", args.trace_profile,
        "--max-colors", str(args.max_colors),
    ]

    if args.fallback_symbol_redraw:
        cmd.append("--fallback-symbol-redraw")

    run(cmd)

    summary = {
        "workflow": "V2 symbol-only",
        "mode": args.mode,
        "assets_dir": str(assets_dir),
        "output_dir": str(out_dir),
        "auto_scene_assembly": False,
        "note": "Manual composition required after SVG symbol generation"
    }

    (args.workdir / "pipeline_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(summary)


if __name__ == "__main__":
    main()
