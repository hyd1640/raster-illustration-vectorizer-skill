---
name: raster-illustration-vectorizer
description: Semi-automatically convert raster scientific illustrations, hand-drawn diagrams, disaster-chain schematics, and map-like figures into structured, editable SVG using preprocessing, element segmentation, vtracer tracing, SVG optimization, layout reassembly, and QA checks.
---

# Raster Illustration Vectorizer

Use this skill when the user wants to convert a raster image such as PNG, JPG, or TIFF into a clean SVG while preserving the original visual structure, layout, and hand-drawn style as much as practical.

This skill is designed for V1 semi-automatic operation. It should produce inspectable intermediate artifacts and ask for human review when segmentation, tracing, or layout fidelity is uncertain.

## Core objective

Convert a raster figure into a structured SVG scene. Prioritize:

1. Element completeness.
2. Spatial fidelity.
3. Layer and occlusion consistency.
4. Visual style consistency.
5. SVG editability.

Do not optimize only for visual similarity if the result becomes an uneditable mass of fragmented paths.

## Non-goals

- Do not OCR text.
- Do not infer or rewrite text content.
- Do not claim AI upscaling is lossless.
- Do not treat hallucinated super-resolution details as ground truth.
- Do not collapse all objects into one unstructured SVG if element-level reassembly is feasible.

## Default V1 parameters

Use these unless the user specifies otherwise:

```yaml
segmentation_level: medium
smoothing_level: medium
noise_filter_level: medium
trace_mode: spline
```

The low/medium/high settings follow the intent of Adobe Illustrator Image Trace controls, but are simplified for reproducible scripting.

| Parameter | Low | Medium | High |
|---|---|---|---|
| `segmentation_level` | coarse structures only | main icons, lines, and shapes | smaller individual objects |
| `smoothing_level` | preserve hand-drawn irregularity | moderate smoothing | cleaner, more regular paths |
| `noise_filter_level` | retain fine details | remove small speckles | aggressive cleanup; may lose detail |

## Standard workflow

Run the pipeline from the repository root:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  <input-image> \
  --workdir work \
  --profile medium
```

Or specify controls explicitly:

```bash
python .agents/skills/raster-illustration-vectorizer/scripts/run_pipeline.py \
  <input-image> \
  --workdir work \
  --segmentation-level medium \
  --smoothing-level medium \
  --noise-filter-level medium \
  --trace-mode spline
```

## Workflow steps

### 1. Input analysis

Run `analyze_image.py` to inspect:

- width and height;
- approximate background color;
- approximate color count;
- edge density;
- low-resolution warning;
- likely text-like regions to exclude or flag.

Output:

```text
work/analysis/image_report.json
```

### 2. Optional enhancement

Run `preprocess_image.py` to perform deterministic scaling, denoising, sharpening, and background normalization.

Use 2x or 4x enhancement only when the input is too small for stable edge tracing. Treat enhancement as auxiliary; retain the original input for QA comparison.

### 3. Element segmentation

Run `segment_elements.py` to produce:

- cropped raster assets;
- per-element masks where available;
- a layout manifest with bounding boxes, estimated type, and z-order.

Asset classes:

- `icons`: discrete small elements such as houses, trees, clouds, stones, or symbols;
- `lines`: rain strokes, outlines, road edges, frame lines;
- `shapes`: larger filled regions such as landslide mass, water area, dust, terrain, or background regions;
- `compounds`: complex multi-part structures such as roads, bridges, or buildings grouped with nearby strokes.

Do not over-trust semantic names in V1. Use generic stable IDs unless the user manually provides names.

### 4. Element-level tracing

Run `trace_elements.py` to convert cropped elements to SVG using `vtracer` by default.

Prefer `spline` mode for hand-drawn and colored illustrations. Use alternative modes only when the user chooses a different tradeoff:

- `spline`: smoother curves, good for hand-drawn illustrations;
- `polygon`: simpler geometry, useful for regular structures;
- `line-art`: stricter treatment of line drawings after thresholding.

### 5. SVG optimization

Use `svgo` if available. Optimization should remove redundant data while preserving structure and editability.

Avoid excessive optimization that merges unrelated elements or destroys useful groups.

### 6. Reassembly

Run `assemble_svg.py` to restore the original coordinate system:

- preserve `bbox` placement;
- preserve estimated `z_index`;
- keep element group IDs;
- keep element classes.

Output:

```text
work/output/final.svg
```

### 7. QA comparison

Run `qa_compare.py` to generate:

- assembled preview PNG when Inkscape or another renderer is available;
- diff overlay;
- QA report.

Output:

```text
work/preview/assembled_preview.png
work/preview/diff_overlay.png
work/analysis/qa_report.json
```

## Especially avoid

1. Excessive path fragmentation.
2. Broken or jagged strokes.
3. Boundary drift and shape distortion.
4. Incorrect layer order.
5. Position or scale drift during reassembly.
6. Color drift and white-edge contamination.
7. Inconsistent stroke width and style.
8. Over-smoothing that destroys hand-drawn character.
9. Vectorizing hallucinated AI-upscaling artifacts.
10. Exporting final SVG without preview and QA inspection.

## Failure and review policy

Flag the result as requiring manual review when:

- many small objects are missing;
- path count is extremely high;
- preview rendering fails;
- large areas are visually displaced;
- layer order appears incorrect;
- the QA report cannot compare final SVG against the source image;
- `vtracer` is unavailable and no acceptable vector fallback exists.

If the output is uncertain, provide the intermediate assets and metadata rather than pretending the SVG is final.
