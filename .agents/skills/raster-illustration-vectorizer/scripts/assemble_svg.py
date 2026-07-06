#!/usr/bin/env python3
"""Assemble per-element SVGs into a single scene SVG.

This uses layout asset_bbox origin coordinates to place each traced element
back into the original canvas coordinate system.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict


def extract_svg_inner(svg_text: str) -> str:
    # naive extraction of inner SVG content
    match = re.search(r"<svg[^>]*>(.*)</svg>", svg_text, re.S)
    if not match:
        return svg_text
    return match.group(1)


def build(layout: Dict[str, Any], vectors_dir: Path, output_path: Path) -> None:
    canvas = layout["canvas"]
    width = canvas["width"]
    height = canvas["height"]

    elements = layout.get("elements", [])

    layers = []

    for e in elements:
        vec_path = vectors_dir / e["vector"]
        if not vec_path.exists():
            continue

        svg = vec_path.read_text(encoding="utf-8")
        inner = extract_svg_inner(svg)

        x, y, w, h = e.get("asset_bbox", e.get("bbox"))

        group = f'<g transform="translate({x},{y})">{inner}</g>'
        layers.append((e["z_index"], group))

    layers.sort(key=lambda x: x[0])

    content = "\n".join([l[1] for l in layers])

    final_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{content}
</svg>
'''

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--vectors-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    layout = json.loads(args.layout.read_text(encoding="utf-8"))
    build(layout, args.vectors_dir, args.out)


if __name__ == "__main__":
    main()
