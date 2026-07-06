#!/usr/bin/env python3
"""Build a V2 scene graph for semantic redraw mode.

V2 不追求逐像素还原，而是先把 V1 的分割元素组织成“语义组”。
这些语义组决定哪些元素可以复用同一个 symbol，哪些元素必须保留状态差异。

Important: this script uses conservative heuristics only. It does not pretend to
fully understand the figure. For publication-level work, review and edit the
output JSON files before final assembly.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


ROLE_PROTECTED_CLASSES = {
    "river_or_water_path",
    "road_or_linear_infrastructure",
    "landslide_or_terrain_mass",
    "mountain_or_large_background",
    "bridge_or_compound_structure",
}


def slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "symbol"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def alpha_mask(arr: np.ndarray) -> np.ndarray:
    if arr.shape[-1] == 4:
        return arr[:, :, 3] > 0
    return np.ones(arr.shape[:2], dtype=bool)


def element_features(asset_path: Path, canvas: Dict[str, int], bbox: List[int]) -> Dict[str, Any]:
    image = Image.open(asset_path).convert("RGBA")
    arr = np.asarray(image)
    mask = alpha_mask(arr)
    rgb = arr[:, :, :3]
    pixels = rgb[mask]

    if pixels.size == 0:
        pixels = rgb.reshape(-1, 3)

    mean = pixels.mean(axis=0)
    std = pixels.std(axis=0)
    dark_ratio = float((pixels.mean(axis=1) < 90).mean())
    green_ratio = float(((pixels[:, 1] > pixels[:, 0] + 10) & (pixels[:, 1] > pixels[:, 2] + 5)).mean())
    blue_ratio = float(((pixels[:, 2] > pixels[:, 0] + 12) & (pixels[:, 2] > pixels[:, 1] + 5)).mean())
    red_brown_ratio = float(((pixels[:, 0] > pixels[:, 2] + 10) & (pixels[:, 1] > pixels[:, 2] - 10)).mean())

    x, y, w, h = bbox
    area = max(1, w * h)
    rel_area = area / max(1, canvas["width"] * canvas["height"])
    aspect = w / max(1, h)

    # 中文注释：边缘密度可作为“损坏/碎屑/复杂纹理”的弱信号，但不能作为语义真值。
    if cv2 is not None:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(((edges > 0) & mask).sum() / max(1, mask.sum()))
    else:
        gray = np.asarray(Image.fromarray(rgb).convert("L"), dtype=float)
        gx, gy = np.gradient(gray)
        mag = np.hypot(gx, gy)
        edge_density = float(((mag > 24) & mask).sum() / max(1, mask.sum()))

    return {
        "mean_rgb": [round(float(v), 3) for v in mean],
        "std_rgb": [round(float(v), 3) for v in std],
        "dark_ratio": round(dark_ratio, 5),
        "green_ratio": round(green_ratio, 5),
        "blue_ratio": round(blue_ratio, 5),
        "red_brown_ratio": round(red_brown_ratio, 5),
        "edge_density": round(edge_density, 5),
        "aspect": round(float(aspect), 5),
        "relative_area": round(float(rel_area), 8),
        "opaque_area": int(mask.sum()),
    }


def infer_semantics(element: Dict[str, Any], features: Dict[str, Any], canvas: Dict[str, int]) -> Dict[str, Any]:
    """Infer weak semantic hints from V1 geometry and color features.

    中文注释：这里不是可靠的视觉识别，只是给 V2 生成 scene graph 的初始建议。
    真正关键的语义元素仍建议在 JSON 中人工复核或通过 overrides 修正。
    """
    etype = element.get("type", "icon")
    x, y, w, h = element.get("bbox", [0, 0, 1, 1])
    rel_area = features["relative_area"]
    aspect = features["aspect"]
    green = features["green_ratio"]
    blue = features["blue_ratio"]
    brown = features["red_brown_ratio"]
    edge = features["edge_density"]
    dark = features["dark_ratio"]

    semantic_class = "generic_visual_element"
    role = "context_or_decoration"
    state = "normal"
    protected = False
    reuse_allowed_hint = False

    if etype == "shape":
        protected = True
        if blue > 0.22:
            semantic_class = "river_or_water_path"
            role = "hydrological_path"
        elif rel_area > 0.12:
            semantic_class = "mountain_or_large_background"
            role = "terrain_context"
        else:
            semantic_class = "landslide_or_terrain_mass"
            role = "hazard_or_terrain_region"
    elif etype == "compound":
        protected = True
        if aspect > 3.0 or aspect < 0.34:
            semantic_class = "road_or_linear_infrastructure"
            role = "transport_or_connection_path"
        else:
            semantic_class = "bridge_or_compound_structure"
            role = "compound_infrastructure_or_key_object"
    elif etype == "line":
        if aspect > 4.0 or aspect < 0.25:
            semantic_class = "rain_or_directional_line" if y < canvas["height"] * 0.45 else "road_or_linear_infrastructure"
            role = "trigger_factor_or_connector" if y < canvas["height"] * 0.45 else "linear_structure"
            reuse_allowed_hint = semantic_class == "rain_or_directional_line"
        else:
            semantic_class = "generic_line"
            role = "outline_or_small_connector"
            reuse_allowed_hint = True
    else:
        # icon 类元素：优先识别可复用背景符号，如树、石块、云等候选。
        if green > 0.25:
            semantic_class = "tree_or_vegetation"
            role = "vegetation_context"
            reuse_allowed_hint = True
        elif blue > 0.22 and y < canvas["height"] * 0.45:
            semantic_class = "cloud_or_weather_icon"
            role = "weather_context"
            reuse_allowed_hint = True
        elif brown > 0.25 and rel_area < 0.01:
            semantic_class = "rock_or_debris"
            role = "debris_or_texture_context"
            reuse_allowed_hint = True
        elif dark > 0.12 or edge > 0.18:
            semantic_class = "facility_or_damaged_object"
            role = "exposed_asset_or_damage_marker"
            state = "damaged_candidate" if edge > 0.24 or dark > 0.22 else "normal_or_intact_candidate"
            # 房屋/设施类元素的状态可能承载灾害信息，默认不强行复用。
            reuse_allowed_hint = state == "normal_or_intact_candidate"
        else:
            semantic_class = "generic_reusable_icon"
            role = "context_symbol"
            reuse_allowed_hint = True

    return {
        "semantic_class": semantic_class,
        "role": role,
        "state": state,
        "protected": protected,
        "reuse_allowed_hint": reuse_allowed_hint,
    }


def apply_overrides(element_id: str, inferred: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(inferred)
    if element_id in overrides:
        merged.update(overrides[element_id])
        merged["override_applied"] = True
    else:
        merged["override_applied"] = False
    return merged


def group_key(semantic: Dict[str, Any], abstraction_level: str, state_strictness: str) -> Tuple[str, str, str]:
    cls = semantic["semantic_class"]
    role = semantic["role"]
    state = semantic["state"]

    if abstraction_level == "high" and cls not in ROLE_PROTECTED_CLASSES:
        # 中文注释：高抽象允许把普通背景元素合并到更粗类别，但不合并受保护主体。
        if cls in {"tree_or_vegetation", "rock_or_debris", "generic_reusable_icon"}:
            cls = "background_context_icon"
            role = "context_symbol"

    if state_strictness == "low" and not semantic.get("protected", False):
        state = "state_ignored"
    elif state_strictness == "medium" and state == "normal_or_intact_candidate":
        state = "normal"

    return cls, role, state


def choose_representative(elements: List[Dict[str, Any]]) -> str:
    if not elements:
        raise ValueError("Cannot choose representative from empty group")
    areas = np.array([e["features"]["opaque_area"] for e in elements], dtype=float)
    target = float(np.median(areas))
    idx = int(np.argmin(np.abs(areas - target)))
    return str(elements[idx]["id"])


def reuse_allowed(group: Dict[str, Any], symbol_reuse_level: str, state_strictness: str) -> bool:
    protected = any(e["semantic"].get("protected", False) for e in group["elements"])
    if protected:
        return False

    hints = [bool(e["semantic"].get("reuse_allowed_hint", False)) for e in group["elements"]]
    n = len(group["elements"])

    if symbol_reuse_level == "low":
        return n >= 3 and all(hints)
    if symbol_reuse_level == "high":
        return n >= 2 and any(hints)
    return n >= 2 and sum(hints) >= max(1, math.ceil(n * 0.6))


def build_scene_graph(
    layout_path: Path,
    assets_dir: Path,
    scene_graph_path: Path,
    semantic_groups_path: Path,
    abstraction_level: str,
    symbol_reuse_level: str,
    state_strictness: str,
    overrides_path: Path | None,
) -> Dict[str, Any]:
    layout = load_json(layout_path)
    canvas = layout["canvas"]
    overrides = load_json(overrides_path) if overrides_path and overrides_path.exists() else {}

    annotated: List[Dict[str, Any]] = []
    for element in layout.get("elements", []):
        asset_path = assets_dir / element["asset"]
        features = element_features(asset_path, canvas, element["bbox"])
        inferred = infer_semantics(element, features, canvas)
        semantic = apply_overrides(element["id"], inferred, overrides)
        annotated.append({**element, "features": features, "semantic": semantic})

    groups_raw: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for element in annotated:
        key = group_key(element["semantic"], abstraction_level, state_strictness)
        groups_raw.setdefault(key, []).append(element)

    semantic_groups: List[Dict[str, Any]] = []
    class_counter: Dict[str, int] = {}
    for (cls, role, state), elements in groups_raw.items():
        class_counter[cls] = class_counter.get(cls, 0) + 1
        symbol_id = f"{slug(cls)}_{slug(state)}_{class_counter[cls]:03d}"
        group = {
            "group_id": symbol_id,
            "semantic_class": cls,
            "role": role,
            "state": state,
            "reuse_allowed": False,
            "representative_element_id": choose_representative(elements),
            "instance_ids": [e["id"] for e in elements],
            "elements": elements,
        }
        group["reuse_allowed"] = reuse_allowed(group, symbol_reuse_level, state_strictness)
        semantic_groups.append(group)

    semantic_groups.sort(key=lambda g: (g["semantic_class"], g["state"], g["group_id"]))

    # 压缩 scene_graph 中的 element 内容，避免语义文件过大。
    compact_groups = []
    for group in semantic_groups:
        compact_groups.append(
            {
                "group_id": group["group_id"],
                "semantic_class": group["semantic_class"],
                "role": group["role"],
                "state": group["state"],
                "reuse_allowed": group["reuse_allowed"],
                "representative_element_id": group["representative_element_id"],
                "instance_ids": group["instance_ids"],
            }
        )

    scene_graph = {
        "source_layout": str(layout_path),
        "mode": "semantic-redraw",
        "parameters": {
            "semantic_abstraction_level": abstraction_level,
            "symbol_reuse_level": symbol_reuse_level,
            "state_preservation_strictness": state_strictness,
        },
        "canvas": canvas,
        "semantic_groups": compact_groups,
        "manual_review_required": True,
        "review_notes": [
            "V2 scene graph is heuristic. Review semantic_class, role, state, and reuse_allowed before final use.",
            "Do not merge objects whose visual differences carry disaster state or process information.",
            "状态差异优先级高于视觉相似性，尤其是完整房屋与损坏房屋、背景山体与滑坡主体。",
        ],
    }

    save_json(scene_graph_path, scene_graph)
    save_json(semantic_groups_path, {"semantic_groups": semantic_groups})
    return scene_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a V2 semantic scene graph from V1 layout assets.")
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--scene-graph", type=Path, required=True)
    parser.add_argument("--semantic-groups", type=Path, required=True)
    parser.add_argument("--semantic-abstraction-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--symbol-reuse-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--state-preservation-strictness", choices=["low", "medium", "high"], default="high")
    parser.add_argument("--semantic-overrides", type=Path, help="Optional JSON mapping element_id to semantic overrides.")
    args = parser.parse_args()

    scene_graph = build_scene_graph(
        args.layout,
        args.assets_dir,
        args.scene_graph,
        args.semantic_groups,
        args.semantic_abstraction_level,
        args.symbol_reuse_level,
        args.state_preservation_strictness,
        args.semantic_overrides,
    )
    print(json.dumps({"group_count": len(scene_graph["semantic_groups"]), "scene_graph": str(args.scene_graph)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
