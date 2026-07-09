---
name: raster-illustration-vectorizer
description: V2-only workflow for converting raster scientific-illustration elements into a reusable SVG symbol library. Use a generated or user-provided symbol sheet, extract per-symbol PNG assets, vectorize each asset in faithful-trace or symbol-redraw mode, and stop before final manual figure composition.
---

# Raster Illustration Vectorizer V2

Use this skill when the user wants to build a reusable SVG symbol library from raster scientific illustrations, disaster-chain schematics, hand-drawn diagrams, or map-like figure elements.

This skill is now **V2-only**. It does **not** attempt to automatically reassemble a final scene. The final composition should be done manually by the user in a vector editor, GIS/cartographic tool, slide editor, or publication layout workflow.

## Core objective

Convert raster element assets into a reviewed SVG symbol library:

```text
source illustration analysis
→ symbol sheet generation or user-provided symbol sheet
→ per-symbol PNG extraction
→ SVG symbol vectorization
→ manifest output
→ user/manual scene composition
```

The output should be inspectable and editable. Do not claim a symbol is publication-ready unless the user has reviewed it.

## Non-goals

- Do not automatically assemble the final scene.
- Do not OCR text.
- Do not infer or rewrite text labels.
- Do not treat automatic symbol extraction as semantic truth.
- Do not claim deterministic `symbol-redraw` is equivalent to manual vector redraw.
- Do not embed raster images into SVG and call them vector output.

## V2 phases

### 1. Symbol sheet preparation

The user may provide a generated or manually prepared symbol sheet containing clean standalone icons and texture snippets. The sheet should separate visual elements such as:

- trigger factors: clouds, rain strokes;
- environmental context: mountains/slopes, rivers, roads, bridges, vegetation;
- disaster processes: landslide body, debris-flow texture, cracks, rocks, dust;
- exposed assets: houses, guardrails, infrastructure;
- auxiliary marks: stones, soil clumps, contour lines, surface texture, flow arrows.

### 2. Symbol asset extraction

Use `extract_symbol_assets.py` to split a symbol sheet into per-symbol PNG assets:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/extract_symbol_assets.py \
  symbol_sheet.png \
  --out-dir work_v2/assets/symbol_candidates
```

The automatic extractor uses background estimation, foreground masks, divider detection, text/header suppression, and connected components. It does not OCR labels and should be treated as a candidate extractor.

For stable production, prefer an explicit layout schema:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/extract_symbol_assets.py \
  symbol_sheet.png \
  --layout-schema symbol_sheet_schema.json \
  --out-dir work_v2/assets/symbol_candidates
```

### 3. SVG symbol vectorization

Use `vectorize_symbols.py` to convert each PNG symbol into an SVG symbol candidate:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/vectorize_symbols.py \
  work_v2/assets/symbol_candidates \
  --out-dir work_v2/output/symbol_library \
  --mode faithful-trace \
  --trace-profile low
```

### 4. Pipeline entry point

Use `run_pipeline.py` when the user wants extraction and vectorization in one call:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  --symbol-sheet symbol_sheet.png \
  --workdir work_v2 \
  --mode faithful-trace \
  --trace-profile low
```

Or skip extraction if per-symbol PNG files already exist:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  --assets-dir assets/symbol_png \
  --workdir work_v2 \
  --mode faithful-trace \
  --trace-profile low
```

## Two supported modes

### `faithful-trace`

Recommended default. Uses `vtracer` with symbol-friendly settings:

```text
--colormode color
--hierarchical stacked
--mode spline
--filter_speckle 2
--color_precision 7
--layer_difference 12
--length_threshold 3.0
--max_iterations 8
--splice_threshold 30
--path_precision 3
```

This mode is intended to preserve the appearance of already-clean icons and hand-drawn strokes. Use `trace-profile: low` by default for clean symbol PNGs. Higher profiles mean stronger cleanup and fewer paths, not necessarily higher fidelity.

### `symbol-redraw`

Experimental deterministic fallback. It performs:

```text
background removal
→ content crop
→ foreground masking
→ adaptive palette reduction
→ contour extraction
→ simplified SVG path output
```

This mode is not a generative model. It can be useful for quick prototypes but can convert strokes into filled contour shapes and may reduce visual fidelity. Mark outputs as requiring review.

## Expected outputs

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

`vector_symbol_manifest.json` is the primary handoff artifact. It should be used to review, rename, and map symbols to semantic classes.

## Recommended manifest extensions

Downstream projects should enrich the manifest with fields such as:

```json
{
  "symbol_id": "tree_broadleaf_001",
  "semantic_class": "tree_or_vegetation",
  "role": "vegetation_context",
  "state": "normal",
  "reuse_allowed": true,
  "style_token": "hand_drawn_clean_dark_blue_outline",
  "preferred_scale_range": [0.5, 1.5]
}
```

## Review policy

Flag output as requiring manual review when:

- automatic extraction merges unrelated icons;
- captions or section headings remain in symbol crops;
- foreground/background removal deletes pale fills;
- SVG path count is excessive;
- hand-drawn outlines are broken, jagged, or over-smoothed;
- `vtracer` is unavailable and `symbol-redraw` fallback is used;
- the user plans to use symbols in a publication figure.

## Final composition policy

Do not run automatic scene reassembly as part of the default workflow. The skill should stop after the SVG symbol library and manifest. Manual composition is the intended next step.
