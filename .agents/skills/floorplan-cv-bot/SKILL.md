---
name: floorplan-cv-bot
description: >-
  Runbook and architectural guide for the AI/CV floor plan processing pipeline, local
  multimodal vision-language model (VLM) inference, multi-resolution tile generation,
  candidate envelope validation, and durable human review in VED Electrical Services.
  Use when developing, testing, or debugging image preprocessing, wall/symbol detection,
  local model gateway execution, coordinate fusion, and dataset approval.
---

# Floor Plan Computer Vision & Local VLM Pipeline

This skill defines the technical workflow, validation requirements, and implementation patterns for the AI floor-plan interpretation pipeline in VED Electrical Services.

---

## 1. Modular Processing Sequence

The AI/CV pipeline must remain strictly modular and separate from HTTP route logic:

```text
Input Validation (MIME, PDF check, file size)
    ↓
PDF-to-Image / Image Normalization (300 DPI, orientation)
    ↓
Page Quality Assessment (skew, contrast, noise, resolution)
    ↓
Multi-Resolution Preparation (Overview + overlapping detail tiles)
    ↓
Deterministic Line & OCR Evidence Extraction
    ↓
Isolated Local VLM Gateway Execution (Loopback only, offline egress guard)
    ↓
Strict Candidate Envelope Validation (U2 Pydantic schema)
    ↓
Cross-Tile Coordinate & Class Fusion (Spatial NMS, adjacent symbol protection)
    ↓
Designer Review & Correction (Append-only revisions, U9)
    ↓
Canonical Geometry Adaptation (K1 schema)
    ↓
Persist Versioned Layout & Artifacts
```

---

## 2. Multi-Resolution Page Preparation (`U7`)

1. **Isotropic Scaling**: Always maintain aspect ratio when resizing or generating tiles (`scale_x === scale_y`). Anisotropic distortion corrupts symbol geometries and distance measurements.
2. **Tile Generation**: Divide high-resolution blueprint pages into overlapping tiles (e.g., 1024x1024 px with 128 px overlap) to capture small electrical glyphs without downsampling loss.
3. **Affine Transforms**: Track invertible affine transformation matrices (`local_to_source_coords`, `source_to_local_coords`) so detections from local tiles map back to exact page source pixels.

---

## 3. Local Model Gateway Isolation (`U8`)

1. **Strict Loopback Security**: The gateway connects only to local runtimes on `127.0.0.1` or `localhost`. Network egress is blocked (`allow_network=False`).
2. **Resource Budgeting**: Wrap model inference with `ResourceTracker` to monitor latency, peak RAM, and VRAM. Reject queries exceeding memory or timeout budgets.
3. **Data Protection & Sanitization**: Redact bearer tokens, private filesystem paths, and internal hostnames from all log entries and client-facing error responses.

---

## 4. Candidate Contract Enforcement (`U2`)

All machine outputs must be wrapped in the immutable `FloorPlanInterpretationCandidate` envelope:
- **`provenance`**: 32-hex `candidate_run_id`, source SHA256, page dimensions, model release ID, prompt version, aware UTC timestamp.
- **`payload`**: Strict coordinates in source pixels. Every symbol has an integer `class_id` and bounding box/center.
- **Validation**: Reject non-finite numbers, negative coordinates, or extra undocumented keys (`extra="forbid"`).

---

## 5. Cross-Tile Fusion & Deduplication

When merging candidate observations from overlapping tiles:
- **Spatial Clustering**: Cluster symbol candidates within a radius (e.g., 20 pixels).
- **Adjacent True Symbol Protection**: Never merge distinct symbols that have different approved symbol legend IDs or are distinct endpoints of separate circuits.
- **Confidence Fusion**: Combine observations using weighted centroid positions and highest class consensus.

---

## 6. Durable Pseudo-Labeling & Human Correction (`U9`)

- **Append-Only History**: Every review correction creates an incremented revision (`revision_number = latest + 1`). Prior revisions and raw model outputs are never deleted or rewritten in-place.
- **Dataset Approval vs. Project Review**: A Designer's approval of a project layout does NOT grant training dataset permission. Supervised training exports require explicit sign-off by an active `VED_AI_DATASET_APPROVER` (PRE10), with strict author self-approval rejection.
- **Exclusion of Incomplete Pages**: Partially reviewed floor plans or unresolved ambiguous items are strictly excluded from gold datasets and training manifests.
