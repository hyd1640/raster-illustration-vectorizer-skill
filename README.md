# Raster Illustration Vectorizer Skill

V2-only Codex skill for converting raster scientific-illustration elements into a reusable SVG symbol library.

The workflow is intentionally not an automatic full-scene reconstruction system. It stops after producing reviewed SVG symbol candidates. Final composition is expected to be done manually in Illustrator, Inkscape, Figma, PowerPoint, ArcGIS Pro, or another vector/cartographic layout tool.

## Core V2 route

```text
raster scientific illustration
→ visual/semantic element analysis
→ generated or user-provided symbol sheet
→ extracted per-symbol PNG assets
→ SVG symbol library
→ manual figure composition by the user
```

The previous V1 route that segmented an entire source image, traced all parts, and reassembled a final scene has been removed from the main workflow.

## Two vectorization modes

### 1. `faithful-trace` default

Uses `vtracer` with conservative symbol-friendly parameters. This is the recommended mode for clean generated symbol PNGs.

Purpose:

- preserve visual appearance;
- preserve hand-drawn outlines and small details;
- avoid excessive cleanup on already-clean icons;
- create SVG symbol candidates for manual review.

Default trace profile is `low`, because for clean icon assets, aggressive speckle filtering and smoothing often damage outlines.

### 2. `symbol-redraw` experimental

Uses a deterministic local fallback:

```text
white/background removal
→ content crop
→ foreground mask
→ palette reduction
→ contour extraction
→ simplified SVG paths
```

This mode is not a generative model and is not expected to match high-quality manual redraw. It is useful for quick prototypes or environments where `vtracer` is unavailable.

## Repository layout

```text
.agents/skills/raster-illustration-vectorizer/
├─ SKILL.md
└─ scripts/
   ├─ extract_symbol_assets.py
   ├─ vectorize_symbols.py
   └─ run_pipeline.py
```

## Dependencies

Python dependencies:

```bash
python -m pip install -r requirements.txt
```

External tools for the recommended `faithful-trace` mode:

```bash
cargo install vtracer
npm install -g svgo   # optional optimizer
```

`symbol-redraw` does not require `vtracer`, but its output quality is lower and must be reviewed.

## Quick start: symbol sheet to SVG library

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  --symbol-sheet symbol_sheet.png \
  --workdir work_v2 \
  --mode faithful-trace \
  --trace-profile low
```

Expected output:

```text
work_v2/
├─ assets/
│  └─ symbol_candidates/
│     ├─ section_01/
│     ├─ section_02/
│     └─ symbol_assets_manifest.json
├─ output/
│  └─ symbol_library/
│     ├─ symbols_png_clean/
│     ├─ symbols_svg/
│     └─ vector_symbol_manifest.json
└─ pipeline_summary.json
```

## Quick start: existing per-symbol PNG directory

When you already have manually curated symbol PNG folders, skip symbol-sheet extraction:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  --assets-dir assets/symbol_png \
  --workdir work_v2 \
  --mode faithful-trace \
  --trace-profile low
```

## Explicit extraction only

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/extract_symbol_assets.py \
  symbol_sheet.png \
  --out-dir work_v2/assets/symbol_candidates
```

The extractor does not OCR labels. Automatic output should be reviewed and renamed before publication use.

For stable production, provide a layout schema with explicit bboxes:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/extract_symbol_assets.py \
  symbol_sheet.png \
  --layout-schema symbol_sheet_schema.json \
  --out-dir work_v2/assets/symbol_candidates
```

Schema example:

```json
{
  "symbols": [
    {
      "symbol_id": "tree_broadleaf_001",
      "semantic_class": "tree_or_vegetation",
      "bbox_xyxy": [38, 575, 108, 695],
      "role": "vegetation_context",
      "reuse_allowed": true
    }
  ]
}
```

## Explicit vectorization only

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/vectorize_symbols.py \
  work_v2/assets/symbol_candidates \
  --out-dir work_v2/output/symbol_library \
  --mode faithful-trace \
  --trace-profile low
```

Fallback option when `vtracer` is unavailable:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/vectorize_symbols.py \
  work_v2/assets/symbol_candidates \
  --out-dir work_v2/output/symbol_library \
  --mode faithful-trace \
  --fallback-symbol-redraw
```

## Manifest fields

`vector_symbol_manifest.json` records each output symbol:

```json
{
  "symbol_id": "section_02__tree_001",
  "semantic_folder": "section_02",
  "source_png": "...",
  "clean_png": "...",
  "svg": "...",
  "mode": "faithful-trace",
  "reuse_allowed": true,
  "review_required": true
}
```

Downstream projects may extend this with:

```json
{
  "semantic_class": "tree_or_vegetation",
  "role": "vegetation_context",
  "state": "normal",
  "style_token": "hand_drawn_clean_dark_blue_outline",
  "preferred_scale_range": [0.5, 1.5]
}
```

## Important limitations

- The skill does not perform final automatic scene assembly.
- The skill does not OCR text or infer label contents from Chinese/English captions.
- Automatic symbol-sheet extraction is heuristic and should be reviewed.
- `faithful-trace` relies on `vtracer`; without it, use `symbol-redraw` only as a prototype fallback.
- `symbol-redraw` may convert strokes into filled contours; it is not equivalent to manual SVG redraw.
