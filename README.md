# Raster Illustration Vectorizer Skill

A Codex skill for semi-automatic conversion of raster scientific illustrations, hand-drawn explanatory diagrams, map-like figures, and disaster-chain schematics into structured SVG.

This V1 is intentionally conservative. It prioritizes reproducibility, inspectable intermediate files, and manual checkpoints over fully automatic object recognition.

## What V1 does

1. Analyze the input image: dimensions, background, approximate color complexity, edge density, and likely text-like regions.
2. Optionally enhance low-resolution inputs using deterministic scaling and sharpening. AI/super-resolution outputs should be treated as enhancement only, not as ground truth.
3. Segment the image into coarse visual elements using connected components, edge masks, and color/area heuristics.
4. Save element crops into an `assets/` directory and record layout metadata in `analysis/layout.json`.
5. Trace element crops with `vtracer` by default, using Illustrator-like low/medium/high presets.
6. Optimize generated SVGs with `svgo` when available.
7. Reassemble traced elements into a final SVG using the original coordinate system and z-order metadata.
8. Generate preview and QA artifacts when a renderer such as Inkscape is available.

## Default V1 parameters

```yaml
segmentation_level: medium
smoothing_level: medium
noise_filter_level: medium
trace_mode: spline
```

Parameter intent:

| Parameter | Low | Medium | High |
|---|---|---|---|
| `segmentation_level` | coarse structures only | main icons, lines, and shapes | smaller individual objects |
| `smoothing_level` | preserve hand-drawn irregularity | moderate smoothing | cleaner, more regular paths |
| `noise_filter_level` | retain fine details | remove small speckles | aggressive cleanup; may lose detail |

## Repository layout

```text
.agents/skills/raster-illustration-vectorizer/
├─ SKILL.md
├─ scripts/
│  ├─ analyze_image.py
│  ├─ preprocess_image.py
│  ├─ segment_elements.py
│  ├─ trace_elements.py
│  ├─ assemble_svg.py
│  ├─ qa_compare.py
│  └─ run_pipeline.py
├─ references/
│  ├─ parameter_presets.md
│  ├─ workflow.md
│  └─ qa_rules.md
└─ examples/
   └─ README.md
```

## Dependencies

Python dependencies:

```bash
python -m pip install -r requirements.txt
```

External command-line tools:

```bash
# macOS examples
brew install imagemagick inkscape
cargo install vtracer
npm install -g svgo
```

On Windows or Linux, install equivalent packages for ImageMagick, Inkscape, `vtracer`, and `svgo`.

## Quick start

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  input.png \
  --workdir work \
  --profile medium
```

Equivalent explicit parameters:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  input.png \
  --workdir work \
  --segmentation-level medium \
  --smoothing-level medium \
  --noise-filter-level medium \
  --trace-mode spline
```

Expected outputs:

```text
work/
├─ analysis/
│  ├─ image_report.json
│  ├─ layout.json
│  └─ qa_report.json
├─ assets/
│  ├─ icons/
│  ├─ lines/
│  ├─ shapes/
│  └─ compounds/
├─ vectors/
├─ preview/
│  ├─ assembled_preview.png
│  └─ diff_overlay.png
└─ output/
   └─ final.svg
```

## Important limitations

V1 does not perform reliable semantic object naming. It creates conservative element IDs such as `icon_001`, `shape_002`, or `line_003`. Rename elements manually in `analysis/layout.json` if semantic names such as `house_01`, `tree_01`, or `river_01` are required.

V1 detects likely text-like regions only to exclude or flag them. It does not OCR text and should not infer text content.

Automatic vectorization can over-fragment hand-drawn textures, rain lines, stones, and shading. Always inspect `preview/diff_overlay.png` and `analysis/qa_report.json` before using `output/final.svg` as a final publication asset.
