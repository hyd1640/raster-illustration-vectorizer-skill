#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2 replacement for legacy trace_elements.py.

This removes V1 layout-based tracing and replaces it with a symbol-centric
vectorization workflow:

- faithful-trace (vtracer)
- symbol-redraw (deterministic fallback)

No scene assembly is performed in V2.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image


VTRACER_PRESETS = {
    "low": {"filter_speckle":"2","color_precision":"7","layer_difference":"12","length_threshold":"3.0","max_iterations":"8","splice_threshold":"30","path_precision":"3"},
    "medium": {"filter_speckle":"4","color_precision":"7","layer_difference":"16","length_threshold":"4.0","max_iterations":"10","splice_threshold":"40","path_precision":"3"},
    "high": {"filter_speckle":"8","color_precision":"6","layer_difference":"24","length_threshold":"5.5","max_iterations":"12","splice_threshold":"55","path_precision":"2"},
}


def run(cmd: List[str]):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)


def trace_vtracer(png: Path, svg: Path, profile: str):
    vtracer = shutil.which("vtracer")
    if not vtracer:
        raise RuntimeError("vtracer missing")

    pr = VTRACER_PRESETS[profile]
    cmd = [vtracer,"--input",str(png),"--output",str(svg),"--colormode","color","--hierarchical","stacked","--mode","spline"]

    for k,v in pr.items():
        cmd += [f"--{k}",v]

    run(cmd)


def trace_redraw(png: Path, svg: Path, max_colors:int=7):
    im = Image.open(png).convert("RGBA")
    arr = np.array(im)
    mask = arr[:,:,3] > 0
    rgb = arr[:,:,:3]

    pixels = rgb[mask].reshape(-1,3).astype(np.float32)
    if len(pixels)==0:
        return

    k = min(max_colors, max(2, len(np.unique(pixels//32))))
    _,_,centers = cv2.kmeans(pixels,k,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,0.8),3,cv2.KMEANS_PP_CENTERS)

    full = rgb.reshape(-1,3).astype(np.float32)
    d = ((full[:,None,:]-centers[None,:,:])**2).sum(2)
    labels = np.argmin(d,axis=1).reshape(mask.shape)

    h,w = mask.shape
    paths=[]

    for i,c in enumerate(centers):
        cm = ((labels==i)&mask).astype(np.uint8)*255
        cm = cv2.morphologyEx(cm,cv2.MORPH_CLOSE,np.ones((2,2),np.uint8))
        cnts,_ = cv2.findContours(cm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        col = "#%02x%02x%02x" % tuple(map(int,c))

        for c0 in cnts:
            if cv2.contourArea(c0) < 10:
                continue
            eps = 0.01 * cv2.arcLength(c0, True)
            c1 = cv2.approxPolyDP(c0, eps, True)
            pts = c1.reshape(-1,2)
            if len(pts) < 3:
                continue
            d = "M " + " L ".join([f"{x},{y}" for x,y in pts]) + " Z"
            paths.append(f'<path fill="{col}" d="{d}"/>')

    svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{"".join(paths)}</svg>')


def trace_one(png: Path, svg: Path, mode: str, profile: str):
    svg.parent.mkdir(parents=True, exist_ok=True)
    if mode == "faithful-trace":
        trace_vtracer(png, svg, profile)
    else:
        trace_redraw(png, svg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--assets-dir", required=True)
    ap.add_argument("--vectors-dir", required=True)
    ap.add_argument("--trace-mode", default="spline")
    ap.add_argument("--smoothing-level", default="medium")
    ap.add_argument("--noise-filter-level", default="medium")
    args = ap.parse_args()

    layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    assets = Path(args.assets_dir)
    vectors = Path(args.vectors_dir)
    vectors.mkdir(parents=True, exist_ok=True)

    count = 0
    for e in layout.get("elements", []):
        asset = assets / e["asset"]
        out = vectors / (Path(e["asset"]).with_suffix(".svg"))
        trace_one(asset, out, "faithful-trace", args.smoothing_level)
        count += 1

    print(json.dumps({"traced": count}))


if __name__ == "__main__":
    main()
