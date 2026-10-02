# VED Electrical Services — Functional Specification & Codex Project Guide

> **Purpose of this file:**
> Defines project structure, system responsibilities, development boundaries, data flow, and implementation order for Codex before any major coding begins.
>
> Codex should treat this document as primary implementation guide unless newer project specification explicitly replaces section.

---

# 1. Project Overview

## Project Name

**VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation**

## Project Type

Web-based electrical planning, floor-plan analysis, visualization, routing, and estimation system.

## Primary Goal

system accepts residential or commercial floor plans and assists Electrical Designers by:

- Uploading floor plans in JPEG, PNG, or PDF format.
- Processing floor plans using Computer Vision.
- Detecting architectural boundaries.
- Detecting electrical symbols.
- Producing editable 2D layouts.
- Reconstructing layout into interactive 3D environment.
- Calculating electrical wire and conduit routes.
- Calculating material quantities.
- Generating cost estimates.
- Producing PDF reports.
- Saving project history.
- Allowing administrators to maintain symbols and material prices.

original thesis architecture specifies React.js, OpenCV, YOLOv8, Konva.js,
Three.js, A* pathfinding, SQL/MySQL, and Python backend. The implementation
uses **FastAPI instead of Flask**. YOLO was implemented in I1-I4, but the
approved target direction is now local multimodal floor-plan interpretation as
defined below and in `docs/LOCAL_VLM_MIGRATION_PLAN.md`.

## Current Prototype Implementation Decisions

### September 9, 2026 priority amendment: next-day development demo

active near-term milestone is unannotated single-floor upload producing
real room/wall and symbol proposals, explicit review/metric approval, saved
canonical geometry, and aligned Konva 2D plus basic Three/R3F 3D by target
date September 10, 2026 (Asia/Singapore). The detailed DEMO-0 through DEMO-4
scope, acceptance rules and bounded dependency exception are maintained in
`docs/LOCAL_VLM_MIGRATION_PLAN.md`; section 0 of
`docs/CODEX_U_VLM_MIGRATION_PROMPT.md` is current execution handoff.

demo targets >=50% room recall and >=50% symbol recall separately on
reviewed development pages, with false positives and precision reported. It
requires actual detection and real 2D/3D integration, not 0.50 confidence
setting or static annotated sample. Wiring, routing, fine-tuning and sealed
production evaluation are deferred for this milestone. U3's original blocked
corpus decisions remain unresolved; this exception neither passes U3 nor
authorizes unreviewed training or production promotion. Reuse existing
stack and safety/data contracts. Explicitly bring forward only minimum
L2-L5 floor/wall/symbol rendering and synchronization needed for demo.
Existing U/L completion checklists remain unchanged until fully verified.

For current prototype/development phase:

- **MySQL remains required database.**
- primary Windows local-development workflow uses **MySQL started from XAMPP**.
- FastAPI connects directly to MySQL through **SQLAlchemy ORM + PyMySQL**. Apache and PHP are not backend dependencies.
- `phpMyAdmin` may be used as optional local administration tool for creating or inspecting development database.
- primary development database name is `ved_electrical`.
- Database schema creation during prototype uses SQLAlchemy metadata (for example, `Base.metadata.create_all()`).
- **No Alembic or schema-migration workflow is required during current prototype phase.** Development schema reset/recreation is allowed while data model is still being tested.
- Authentication uses **OAuth 2.0 + OpenID Connect (OIDC)** with configurable external identity provider.
- Local application passwords are not stored or verified by VED.
- MySQL stores local application user record and VED authorization role (`ADMIN` or `DESIGNER`) after external identity verification.

XAMPP is local-development convenience, not production architecture requirement. A later deployment may use another MySQL host without changing application's SQLAlchemy domain model.

## Target Local AI Decision

planned production interpreter is locally hosted open-weight
**vision-language model (VLM)**. Calling it local LLM does not make a
text-only language model suitable for scans: selected base model must accept
images and support grounded structured output. Private floor plans, prompts,
outputs, reference material, training examples, and model adapters remain on
VED-controlled storage and compute.

Must accept normal scanned floor plan without requiring user
to draw training boxes. This is inference requirement. It does not mean that
unannotated scans provide supervised coordinate or class truth. The migration
therefore combines zero/few-shot local interpretation, pseudo-label generation,
Designer correction, independent VED approval, and optional offline
LoRA/QLoRA fine-tuning. Production requests never update model weights
automatically.

local model produces versioned `FloorPlanInterpretationCandidate`, not K1
canonical geometry. Strict application-owned validation and deterministic
adapter stand between model output and Designer review/K1/K2 path. No raw
model output may directly create Konva state, Three.js state, wiring quantities,
routes, estimates, or reports.

existing I1-I4 YOLO implementation is retained as legacy comparison and
rollback path until U14 explicitly approves retirement. Documentation of the
target state must not be interpreted as completed dependency, model, worker,
API, or database migration.

## Current Implementation Status

application roadmap is implemented through L1, including E3A
project-floor prerequisite introduced between E3 and E4. PRE0-PRE12 are also
complete.

current verified prototype contract contains twenty-three SQLAlchemy/MySQL tables
and 34 OpenAPI operations. J5 adds `manual_symbols` after J4's append-only
`detection_class_corrections` table and the empty-safe J3A `symbol_legends`
catalog. K1 changes neither count; K2 adds `layout_versions` while leaving the
API count unchanged; K3 adds exactly two layout operations and no table; PRE4
adds `floor_plan_sources` and `floor_plan_pages`; PRE5 adds
`processing_artifacts`; PRE6 adds `floor_elevation_settings` and
`page_scale_settings` plus three analysis-setting operations; PRE7 adds
`symbol_legend_history` plus three Admin legend operations. PRE8 adds
`layout_save_requests` and leaves operation count unchanged. PRE9 adds
`processing_job_attempts`, `processing_job_cancellations`, and one cancellation
operation. PRE10 adds `dataset_approver_assignments` and four authority
operations without adding global role or review decision. K4, K5, and
L1 otherwise leave both counts unchanged. PRE1 and PRE2 each
add one GET operation and no table.

Completed ticket areas:

```text
A1–A4
B1–B5
C1–C6
D1–D4
E1–E4
E3A — Project Floor API
F1 — Create Processing Jobs Table
F2 — Create Start Processing Endpoint
F3 — Create Processing Status Endpoint
F4 — Build Processing Status UI
G1 — Implement PDF-to-Image Conversion
G2 — Implement Image Normalization
G3 — Implement OpenCV Preprocessing Pipeline
H1 — Implement Wall-Line Detection Prototype
H2 — Normalize Wall Coordinates
H3 — Persist Wall Geometry
I1 — Implement YOLO Model Loader
I2 — Implement Symbol Inference Service
I3 — Implement Confidence Filtering
I4 — Persist Detected Symbols
J1 — Create Detection Results API
J1A — Create Detection Review Image API
J2 — Build Detection Review Canvas
J3 — Confirm or Reject Detection
J3A — Approved Symbol Legend Foundation
J4 — Correct Symbol Classification
J5 — Add Missing Symbol Manually
K1 — Define Canonical Geometry Schema
K2 — Create Layout Snapshot/Version Model
K3 — Create 2D Layout API
K4 — Build Konva Layer Architecture
K5 — Implement Symbol Move/Edit in 2D
L1 — Initialize Three.js / React Three Fiber Viewer
PRE0 — Publish Documentation and Privacy Baseline
PRE1 — Add Ownership-Aware Floor-Plan Discovery API
PRE2 — Add Processing-Job History Discovery API
PRE3 — Reconcile Project Workspace After Reload
PRE4 — Persist Immutable Floor-Plan Source/Page Identity
PRE5 — Register Derived Processing Artifacts
PRE6 — Add Reviewed Scale and Elevation Inputs
PRE7 — Implement Approved Symbol-Legend Administration
PRE8 — Add Conditional and Idempotent Layout Saving
PRE9 — Add Processing Execution Controls
PRE10 — Add Dataset-Approver Authority
PRE11 — Freeze Canonical-Geometry Compatibility Decision
PRE12 — Publish Passing Pre-VLM Readiness Gate
```

implemented application includes authentication and signed sessions,
database-authoritative roles, project and project-floor workflows, upload
validation and original storage, upload API, project upload UI, and
persisted processing-job records, owning-Designer endpoint that creates a
durable queued job, ownership-aware read-only status endpoint, and a
current-session Designer processing UI, backend-only PDF-to-PNG conversion
service, Pillow-based image normalization, OpenCV preprocessing, wall candidate
detection/normalization/persistence, configured YOLO loading, isolated symbol
inference, in-memory confidence classification, and processing-job-versioned
machine detection persistence, plus read-only detection-result retrieval and
authenticated serving of aligned G2 normalized review image, and the
read-only React-Konva review canvas, append-only owning-Designer confirmation
or rejection decisions, and database-backed active-only approved symbol
legend catalog, append-only owning-Designer classification correction, and
owner-scoped idempotent manual placement using trusted review-image dimensions.
L1 provides protected, lazy-loaded empty 3D viewer with orbit, pan, zoom,
deterministic reset, and local failure isolation. It does not fetch or render
K1/K2/K3 geometry. K5 provides canonical symbol repositioning, not general
geometry editing. In particular, there is no worker, external queue, automatic
OpenCV/YOLO pipeline, canonical 3D reconstruction, routing, estimation, or
report implementation. PRE9 provides execution-control records and primitives,
not worker or automatic pipeline. There is also no local VLM runtime, reviewed
VLM gold set, adapter, or VLM orchestration. PRE0-PRE12 foundations and U1
requirements baseline pass. U2 implements only strict advisory candidate
schema; see `docs/FLOOR_PLAN_INTERPRETATION_CANDIDATE_V1.md`.
L2-L5 were explicitly authorized and implemented on 2026-09-19; see Epic L's
checkpoints below. Earlier milestone descriptions here are historical; current
U implementation and pending acceptance gates are in `U_VLM_PROGRESS.md`.

`GET /api/projects/{project_id}/floor-plans` now returns authorized persisted
safe metadata with optional project-scoped floor filter. E4 still uses
current-session upload state before PRE3; PRE3 now consumes persistent
discovery and bounded processing-job history provided by PRE2.

---

# 2. Important Development Rule

**Do not implement application as collection of disconnected pages.**

All modules must operate around shared project model.

main project pipeline is:

```text
Project
   ↓
Floor Plan Upload
   ↓
Image Processing
   ↓
Local Multimodal Interpretation
   ↓
Validated Structure, Symbol, Scale, and Observed-Wiring Candidates
   ↓
User Verification / Correction
   ↓
2D Layout
   ↓
3D Reconstruction
   ↓
Electrical Routing
   ↓
Material Quantification
   ↓
Cost Estimation
   ↓
Report Generation
```

same project data must remain synchronized across 2D editor, 3D viewer, routing engine, estimates, and reports.

---

# 3. Actors

## Electrical Designer / User

Electrical Designer is main project user.

Primary capabilities:

- Login.
- Create projects.
- Upload floor plans.
- Start floor-plan analysis.
- Review AI detections.
- Correct incorrectly detected symbols.
- Add missing symbols.
- Delete incorrect symbols.
- Modify electrical layout.
- View 2D layouts.
- View 3D layouts.
- View electrical routing.
- Manually adjust wiring/conduits where supported.
- Generate material quantities.
- Generate cost estimates.
- Export reports.

source document specifies that users must be able to manually edit design when outlet, switch, or other component needs to be changed.

## Admin / Project Engineer

Primary capabilities:

- Manage users.
- Manage electrical symbol legends.
- Manage material records.
- Update material prices.
- Review projects.
- Review estimates.
- View generated reports.
- Review system activity.
- Maintain reference symbol datasets.

source architecture assigns management of symbols and material pricing to Admin.

---

# 4. Technology Stack

## Frontend

```text
React
JavaScript
Vite
React Router
Axios or TanStack Query
Konva.js / React-Konva
Three.js / React Three Fiber
React Hook Form
Zod
```

### Frontend Responsibilities

React handles:

- Authentication UI.
- Dashboard.
- Project management.
- Floor-plan upload.
- Processing status.
- AI detection review.
- 2D editing.
- 3D visualization.
- Wiring visualization.
- Material tables.
- Cost estimates.
- Report viewing.
- Admin interfaces.

---

# 5. Backend

## Main Backend

```text
Python
FastAPI
Uvicorn
Pydantic
SQLAlchemy
PyMySQL
OAuth 2.0 / OpenID Connect (OIDC)
```

FastAPI replaces Flask backend described in original theoretical framework.

backend handles business logic and must not place business rules inside API route files.

Recommended separation:

```text
API Router
   ↓
Service
   ↓
Repository
   ↓
Database
```

AI processing should follow:

```text
API Router
   ↓
Processing Service
   ↓
AI / CV Pipeline
   ↓
Result Formatter
   ↓
Repository
   ↓
Database
```

---

# 6. AI and Computer Vision Stack

```text
Python
OpenCV
Local open-weight multimodal VLM selected by U6
Transformers
PEFT / TRL for LoRA or QLoRA adapter training
Local OCR/document parsing
Optional specialist grounding model selected by evaluation
NumPy
Pillow
PDF-to-image processing library
```

currently implemented baseline uses OpenCV wall extraction and YOLO symbol
recognition. New production work targets local VLM pipeline. No model family
is approved merely by appearing in plan: U1 establishes hardware/privacy
constraints and U6 measures feasible Qwen3-VL/Qwen2.5-VL candidates plus
optional Florence-2 or PaddleOCR/PaddleOCR-VL helpers against reviewed U5
development validation, never sealed U14 final test set. The model, runtime, revision, license, hash, prompt,
adapter, and decoding configuration must be recorded.

## Processing Pipeline

```text
Original Floor Plan
        ↓
Input Validation
        ↓
PDF → Image Conversion if required
        ↓
Image Normalization
        ↓
Page Classification and Quality Assessment
        ↓
Whole-Page Overview, Legend Region, and Overlapping Tiles
        ↓
Local OCR and Deterministic Line/Geometry Evidence
        ↓
Local Multimodal Interpretation
        ↓
Strict Candidate-JSON Validation
        ↓
Cross-Tile De-duplication and Evidence Fusion
        ↓
Persisted Advisory Machine Result
        ↓
Designer Review / Correction / Approval
        ↓
Deterministic K1 Coordinate and Identity Adaptation
        ↓
Append-Only K2 Canonical Geometry Snapshot
```

existing G1-G3, H1-H3, and I1-I4 modules may be used as legacy comparison
or specialist evidence while migration is evaluated. A VLM must not be limited
to downscaled page when small glyphs require native-resolution overlapping
tiles. Whole-page context is still required so tile candidates can be related
to title block, legend, scale, floor, rooms, panels, and circuits.

---

# 7. AI Detection Scope

interpreter should recognize only symbols approved for VED Electrical
Services and should also propose architectural structure, scale evidence,
rooms, panels, and wiring visibly present on source sheet.

Source-defined examples include:

```text
Power outlets
Wall switches
Lighting fixtures
Data connection ports
```

source states that automatic recognition is intended for standardized symbols used by VED Electrical Services rather than arbitrary architectural symbols from other firms.

Do not silently expand classes beyond active approved legend catalog. The
drawing-specific approved legend is primary. PEC Part 1 (2017) and Part 2
(2020) references may support private retrieval pack only when their exact
edition/part/page provenance and VED approval are recorded; they are not an
automatic substitute for drawing legend or professional review.

Observed wiring is copied evidence from uploaded sheet. Generated wiring is
later A* routing result. Store their provenance and status separately. If a
sheet contains no visible wiring, candidate must contain no observed routes
rather than inventing circuit.

---

# 8. Confidence Handling

implemented I3 YOLO baseline uses:

```text
Confidence threshold = 0.50
```

Detections below threshold should not automatically become confirmed electrical components.

That numeric threshold is not automatically transferable to VLM. Token
probability and model-written confidence text are not treated as calibrated
object-detection confidence. VLM candidates instead retain evidence references,
ambiguity/warnings, model provenance, deterministic validation results, and
Designer review status. A release-specific confidence or calibration policy may
be adopted only after U5/U6 measurements.

Recommended detection states:

```text
detected
confirmed
needs_review
corrected
manually_added
deleted
```

[Inference] Keeping original detection rather than immediately deleting rejected predictions would make accuracy testing and audit tracking easier.

---

# 9. 2D Layout System

## Technology

```text
Konva.js
or
React-Konva
```

source architecture specifies Konva.js as interactive 2D canvas technology.

## Layer Structure

Recommended canvas layers:

```text
Layer 1 — Original Blueprint
Layer 2 — Detected Walls
Layer 3 — Room Boundaries
Layer 4 — Electrical Symbols
Layer 5 — Wiring
Layer 6 — Conduits
Layer 7 — Selection / Editing UI
```

original floor plan should remain unchanged.

source explicitly states that uploaded blueprint is used as reference and should not be modified by system.

---

# 10. Shared Geometry Model

This is one of most important architectural requirements.

2D and 3D editors must **not maintain unrelated versions of building geometry**.

Use one normalized project coordinate system.

Example:

```json
{
  "project_id": 15,
  "coordinate_system": {
    "unit": "meter",
    "pixels_per_meter": 100
  },
  "walls": [],
  "rooms": [],
  "symbols": [],
  "routes": []
}
```

[Inference] Konva coordinates can be derived from this model for 2D rendering while Three.js coordinates can be derived from same model for 3D rendering.

Target mapping:

```text
Canonical Geometry
       │
       ├────→ Konva 2D
       │
       ├────→ Three.js 3D
       │
       ├────→ Routing Engine
       │
       └────→ Material Calculation
```

---

# 11. 3D Visualization

## Technology

```text
Three.js
React Three Fiber
WebGL
```

Three.js is part of source-defined architecture for reconstructing detected 2D floor plans into interactive 3D views.

## 3D Scene

scene should support:

```text
Floor
Walls
Doors
Windows
Rooms
Electrical panel
Outlets
Switches
Lighting fixtures
Data ports
Wiring
Conduits
```

## Camera

Required interactions:

```text
Orbit
Pan
Zoom
Reset View
Top View
Perspective View
```

---

# 12. 2D → 3D Reconstruction

Expected transformation:

```text
2D wall line
      ↓
3D wall segment

2D room polygon
      ↓
3D floor area

2D symbol coordinate
      ↓
3D fixture position

2D electrical route
      ↓
3D conduit/wire route
```

Each wall should have metadata such as:

```json
{
  "id": 54,
  "start": {
    "x": 2.5,
    "y": 1.2
  },
  "end": {
    "x": 5.8,
    "y": 1.2
  },
  "height": 2.7,
  "thickness": 0.15
}
```

---

# 13. Electrical Routing

source specifies A* spatial routing algorithm for determining wiring paths and calculating total wire lengths.

## Routing Inputs

```text
Electrical panel location
Device location
Walls
Rooms
Structural boundaries
Route restrictions
Elevation
Floor level
```

## Routing Output

```text
Route coordinate points
Horizontal distance
Vertical distance
Total route distance
Route type
Connected devices
Required wire type
Required conduit type
```

---

# 14. Electrical Routing Rules

electrical route should not simply draw direct Euclidean line between components.

Routes need to represent realistic building movement.

[Inference] The routing engine should support rules such as:

```text
Horizontal routing → ceiling/service routing level

Vertical movement → inside or directly along wall paths

Device drop → ceiling route down through associated wall

Device rise → wall path upward toward ceiling/service route

Cross-room routing → ceiling/service level rather than diagonal paths through open space
```

These rules should remain configurable because final electrical implementation requires professional validation.

---

# 15. Multi-Floor Routing

source identifies hidden vertical routes between floors as important problem with traditional 2D planning.

routing model therefore needs:

```text
floor_id
floor_number
elevation
vertical_connector
route_start
route_end
```

Example:

```text
Floor 1 Panel
      ↓
Vertical Riser
      ↓
Floor 2 Ceiling Route
      ↓
Wall Drop
      ↓
Outlet
```

Vertical distance must be included in material calculations.

---

# 16. Materials and Cost Estimation

source cost-estimation module receives:

```text
Detected symbol quantities
+
Calculated wiring lengths
+
Official material prices
```

and produces itemized Bill of Materials and total project estimate.

## Basic Formula

```text
Line Total = Quantity × Unit Price
```

Example:

```text
THHN Wire
Length: 135 m
Price: ₱25 / m

135 × 25 = ₱3,375
```

---

# 17. Pricing Rules

Material prices must come from database.

Do not hard-code prices inside:

```text
React components
FastAPI endpoints
AI modules
Routing modules
PDF templates
```

Use:

```text
materials
material_prices
price_history
```

[Inference] Estimates should preserve unit prices used when estimate was created so later Admin price changes do not alter historical estimates.

---

# 18. Report Output

completed project should be able to produce:

```text
Project information
Floor-plan information
Detected electrical components
Electrical component quantities
Wire lengths
Conduit lengths
Bill of Materials
Unit prices
Line totals
Overall estimated cost
2D layout reference
Optional 3D preview
Generation date
Prepared-by information
```

source system explicitly includes exportable PDF report as part of System Output.

---

# 19. Database

Required database:

```text
MySQL
```

Primary Windows local-development workflow:

```text
XAMPP Control Panel
        ↓
Start MySQL
        ↓
MySQL at configured host/port
        ↓
PyMySQL
        ↓
SQLAlchemy ORM
        ↓
FastAPI
```

Default local development assumptions may use:

```text
Host: 127.0.0.1
Port: 3306
Database: ved_electrical
```

These values must remain environment-configurable. Database credentials must never be hard-coded in application source.

FastAPI connects directly to MySQL. Apache and PHP are not required by FastAPI backend, and `phpMyAdmin` is only optional local database administration interface.

Use:

```text
SQLAlchemy ORM
PyMySQL
SQLAlchemy metadata / Base.metadata.create_all()
```

For current prototype, do not introduce Alembic or another schema-migration framework. While schema is still being tested, development database may be reset/recreated and current tables recreated from SQLAlchemy models. Production-grade schema migration/versioning is deferred until explicitly requested.

Do not perform raw SQL throughout application unless there is specific performance requirement.

---

# 20. Core Database Tables

Recommended initial schema:

```text
roles
users

projects
project_floors
floor_plans

processing_jobs
processed_images

rooms
walls
doors
windows

symbol_legends
detected_symbols
manual_corrections

layout_versions

electrical_panels
wiring_routes
route_segments

materials
material_prices
price_history

estimates
estimate_items

reports

audit_logs
```

---

# 21. Important Relationships

```text
User
 └── Projects

Project
 ├── Project Floors
 ├── Floor Plans
 ├── Layout Versions
 ├── Wiring Routes
 ├── Estimates
 └── Reports

Floor Plan
 ├── Processing Jobs
 ├── Walls
 ├── Rooms
 └── Detected Symbols

Detected Symbol
 └── Symbol Legend

Estimate
 └── Estimate Items

Estimate Item
 └── Material
```

---

# 22. Project States

Recommended project lifecycle:

```text
draft

uploaded

processing

needs_review

layout_ready

routing_ready

estimated

report_ready

archived
```

Do not use UI assumptions to determine actual project state.

Backend must remain source of truth.

---

# 23. Processing Job States

AI operations should use explicit processing states:

```text
queued
processing
completed
failed
cancelled
```

Example:

```json
{
  "job_id": 218,
  "type": "floor_plan_analysis",
  "status": "processing",
  "progress": 72
}
```

This allows React to display meaningful progress instead of blocking entire interface.

---

# 24. FastAPI Application Structure

```text
backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   │
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── projects.py
│   │       ├── floor_plans.py
│   │       ├── processing.py
│   │       ├── symbols.py
│   │       ├── layouts.py
│   │       ├── routing.py
│   │       ├── materials.py
│   │       ├── estimates.py
│   │       ├── reports.py
│   │       └── admin.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── floor_plan.py
│   │   ├── symbol.py
│   │   ├── layout.py
│   │   ├── routing.py
│   │   ├── material.py
│   │   ├── estimate.py
│   │   └── report.py
│   │
│   ├── schemas/
│   │
│   ├── repositories/
│   │
│   ├── services/
│   │   ├── project_service.py
│   │   ├── processing_service.py
│   │   ├── layout_service.py
│   │   ├── routing_service.py
│   │   ├── estimation_service.py
│   │   └── report_service.py
│   │
│   ├── ai/
│   │   ├── preprocessing/
│   │   ├── wall_detection/
│   │   ├── symbol_detection/
│   │   ├── floor_plan_interpretation/
│   │   ├── ocr/
│   │   └── local_model_gateway/
│   │
│   ├── geometry/
│   │   ├── coordinates.py
│   │   ├── walls.py
│   │   ├── rooms.py
│   │   └── transforms.py
│   │
│   ├── routing/
│   │   ├── graph.py
│   │   ├── astar.py
│   │   ├── route_rules.py
│   │   └── measurements.py
│   │
│   └── reports/
│       ├── generator.py
│       └── templates/
│
├── tests/
│
└── requirements.txt
```

---

# 25. Frontend Structure

```text
frontend/
│
├── src/
│   │
│   ├── app/
│   │
│   ├── routes/
│   │
│   ├── components/
│   │
│   ├── features/
│   │   │
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── projects/
│   │   ├── floor-plans/
│   │   ├── processing/
│   │   ├── detection-review/
│   │   ├── editor-2d/
│   │   ├── viewer-3d/
│   │   ├── routing/
│   │   ├── estimation/
│   │   ├── reports/
│   │   └── admin/
│   │
│   ├── api/
│   │
│   ├── hooks/
│   │
│   ├── stores/
│   │
│   ├── types/
│   │
│   ├── utils/
│   │
│   └── assets/
│
└── package.json
```

---

# 26. Storage Structure

Local development:

```text
storage/
│
├── uploads/
│   └── originals/
│
├── processed/
│
├── detections/
│
├── previews/
│
├── reports/
│
└── training/       # private, Git-ignored corpus/review/model-release workspace
```

Do not overwrite uploaded original.

Every generated resource should reference corresponding project and floor plan.

---

# 27. Root Repository Structure

```text
ved-electrical-services/
│
├── frontend/
├── backend/
├── models/
│   └── yolo/
│
├── storage/
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── database.md
│   ├── geometry.md
│   ├── routing.md
│   └── ai-pipeline.md
│
├── scripts/
│
├── docker/
│
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml
```

---

# 28. Core API Groups

Codex should organize FastAPI routes around resources rather than individual UI pages.

```text
/api/auth

/api/users

/api/projects

/api/projects/{project_id}/floors

/api/projects/{project_id}/floor-plans

/api/floor-plans/{id}/process

/api/processing-jobs/{id}

/api/floor-plans/{id}/detections

/api/projects/{id}/layouts

/api/projects/{id}/routes

/api/materials

/api/projects/{id}/estimates

/api/projects/{id}/reports

/api/admin
```

---

# 29. Example Floor-Plan Processing Flow

```text
POST
/api/projects/25/floor-plans

          ↓

floor_plan_id = 81

          ↓

POST
/api/floor-plans/81/process

          ↓

processing_job_id = 103

          ↓

GET
/api/processing-jobs/103

          ↓

status = completed

          ↓

GET
/api/floor-plans/81/detections?processing_job_id=103

          ↓

React loads review/editor
```

---

# 30. Authentication and Authorization

Authentication uses:

```text
OAuth 2.0
+
OpenID Connect (OIDC)
```

OAuth/OIDC provider must remain configurable until concrete provider is selected.

Target authentication flow:

```text
React Sign In
      ↓
FastAPI /api/auth/login
      ↓
Configured OAuth/OIDC Provider
      ↓
FastAPI /api/auth/callback
      ↓
Validated External Identity
      ↓
Local MySQL User Record
      ↓
VED Role Authorization
```

VED does not require or store local application password. External provider identity is mapped to local `users` record using provider identity data such as provider name and provider subject identifier.

Required local application roles:

```text
ADMIN
DESIGNER
```

[Inference] A `PROJECT_ENGINEER` role can be introduced if responsibilities need to be separated from Admin role later.

OAuth/OIDC establishes who user is. The local MySQL role determines what authenticated user may do inside VED.

Backend authorization must control protected actions. Hiding buttons in React is not sufficient authorization.

Security requirements include:

- OAuth/OIDC client secrets remain server-side.
- Provider tokens and authorization codes must not be written to normal application logs.
- OAuth state validation is required.
- OIDC nonce/identity-token validation must be applied when used by selected provider flow.
- Authentication must not rely only on frontend state.
- Secrets remain outside version control.

Example:

```text
Designer
    can create projects
    can upload plans
    can modify own projects
    can generate estimates
    can generate reports

Admin
    can manage users
    can manage symbols
    can manage material prices
    can inspect project data
    can inspect audit history
```

---

# 31. Audit Requirements

Track important system actions.

Examples:

```text
USER_LOGIN

PROJECT_CREATED

FLOOR_PLAN_UPLOADED

ANALYSIS_STARTED

ANALYSIS_COMPLETED

SYMBOL_CORRECTED

SYMBOL_ADDED

SYMBOL_REMOVED

ROUTE_RECALCULATED

PRICE_UPDATED

ESTIMATE_GENERATED

REPORT_GENERATED
```

---

# 32. Error Handling

implemented API does not yet have one globally uniform top-level error
envelope. Application-generated errors raised with FastAPI `HTTPException`
currently use:

```json
{
  "detail": {
    "error": {
      "code": "INVALID_FLOOR_PLAN",
      "message": "The uploaded floor plan does not meet processing requirements.",
      "details": {}
    }
  }
}
```

FastAPI request-validation failures use framework's standard validation
detail array. A future error-contract ticket may unify these shapes, but current
documentation and clients must reflect implemented responses.

Do not expose:

```text
SQL errors
Filesystem paths
Python stack traces
Secret values
Model filesystem locations
```

to normal users.

---

# 33. Upload Validation

Supported source formats from thesis are:

```text
JPEG
PNG
PDF
```

Validation should check:

```text
Extension
MIME type
File integrity
File size
Image dimensions
PDF page availability
```

source states that low-resolution and hand-drawn images are outside intended operating scope.

---

# 34. Development Priorities

Codex should not attempt to build entire system in one pass.

Follow this dependency order:

```text
01 — Repository Foundation

02 — Database

03 — FastAPI

04 — Authentication

05 — Project Management

06 — File Upload

07 — AI Processing Framework

08 — Symbol Detection

09 — Geometry Representation

10 — 2D Editor

11 — 3D Reconstruction

12 — Spatial Routing

13 — Material Quantification

14 — Cost Estimation

15 — Report Generation

16 — Admin Management

17 — Testing

18 — Deployment
```

---

# 35. Phase 1 — Foundation

Build:

```text
frontend/
backend/
storage/
docs/
```

Configure:

```text
React
JavaScript
Vite

FastAPI
SQLAlchemy
PyMySQL

MySQL (XAMPP for primary Windows local development)
```

Create:

```text
.env.example
.gitignore
README.md
```

Do not implement AI yet.

---

# 36. Phase 2 — Data Foundation

Implement:

```text
Users
Roles
Projects
Project Floors
Floor Plans
Materials
Pricing
```

Create and verify required MySQL development schema from SQLAlchemy models before building dependent modules. During prototype phase, schema reset/recreation is allowed instead of maintaining migration history.

---

# 37. Phase 3 — Project Workflow

Implement:

```text
Login
Dashboard
Create Project
Open Project
Upload Floor Plan
Project History
```

At this stage, uploaded plans may simply be displayed.

---

# 38. Phase 4 — AI Pipeline

Implement:

```text
Image loading
PDF conversion
Page normalization and quality assessment
High-resolution overview/legend/tile preparation
Local OCR and deterministic geometry evidence
Local multimodal interpretation
Strict candidate validation and fusion
Advisory interpretation persistence
Designer review and deterministic canonical adaptation
```

Do not connect cost estimation yet.

legacy G/H/I implementation remains available for comparison and rollback
while U1-U14 replace production interpretation path incrementally. Do not
remove it in earlier U ticket.

---

# 39. Phase 5 — Detection Review

Implement:

```text
Original blueprint
AI bounding boxes
Detected symbols
Confidence values
Confirm detection
Correct detection
Delete detection
Add missing symbol
```

user-corrected version becomes authoritative layout input.

---

# 40. Phase 6 — Geometry Engine

Convert accepted detection and structural information into normalized geometry model.

Do not make Three.js parse raw YOLO or VLM output directly.

Correct:

```text
Validated and Designer-approved interpretation
 ↓
Normalized Geometry
 ↓
Three.js
```

Avoid:

```text
Raw model candidate output
 ↓
Three.js-specific custom logic
```

---

# 41. Phase 7 — 2D Editor

Implement:

```text
Blueprint background
Walls
Symbols
Selection
Dragging
Adding
Deleting
Wiring overlays
Save
Undo / redo if included
```

---

# 42. Phase 8 — 3D Viewer

Implement:

```text
Wall extrusion
Floor geometry
Electrical device placement
Camera controls
Layer visibility
2D/3D synchronization
```

first target is accurate geometry.

Do not prioritize decorative materials, realistic lighting, or furniture before coordinate alignment works correctly.

---

# 43. Phase 9 — Spatial Routing

Implement:

```text
Routing graph
A*
Obstacles
Vertical routing
Ceiling paths
Wall drops
Route measurement
```

source objective specifically requires routing to account for vertical elevation and structural obstructions.

---

# 44. Phase 10 — Cost Engine

Inputs:

```text
Confirmed electrical components
Calculated wire length
Calculated conduit length
Material rules
Database prices
```

Output:

```text
Bill of Materials
Material quantities
Unit prices
Totals
```

---

# 45. Phase 11 — Reporting

Generate PDF containing project and estimation information.

Reports should reference specific estimate version.

Do not calculate current prices again while downloading old report.

---

# 46. Testing Requirements

Current implemented tooling:

```text
Backend:  Python unittest
          Combined pytest discovery includes canonical tests
Frontend: Vitest + Testing Library + jsdom
```

Run current backend suite from `backend/` with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pytest tests -q
```

`pytest` is not declared as direct project dependency in
`backend/requirements.txt`, although it may be present in resolved development
environment through installed tooling or transitive dependencies. The current
suite includes `unittest`-style cases and canonical pytest cases; full coverage
requires latter as well. PRE12 ran both commands and their totals overlap.
Ticket S1 below describes future explicit pytest testing
foundation and must not be read as claim about current dependency file.

thesis specifies:

- AI symbol recognition accuracy validation.
- Comparison of AI counts against manual counts.
- Unit testing.
- 3D spatial alignment validation.
- SQL-based cost calculation validation.
- ISO 25010 evaluation focusing on functional suitability, usability, and performance efficiency.

Recommended test directories:

```text
backend/tests/unit/
backend/tests/integration/
backend/tests/api/
backend/tests/ai/
backend/tests/routing/
backend/tests/estimation/

frontend/src/**/*.test.jsx
```

---

# 47. System Limitations From the Thesis

Codex must not accidentally expand functionality beyond declared project scope.

thesis currently states that:

```text
The system focuses on residential and commercial floor plans.

Automatic recognition is based on VED Electrical Services' standardized symbols.

Non-standard external symbols are outside automatic recognition.

Original uploaded blueprints must remain unchanged.

The system is a planning and estimation tool.

Generated electrical layouts still require professional review.

Low-resolution and hand-drawn plans are outside the intended detection scope.

Cost information does not automatically represent live market prices unless Admin updates the database.
```

---

# 48. Professional Validation Boundary

Must not present generated layouts as final permit-ready engineering documents.

thesis states that generated layouts and estimates must still be reviewed, validated, and signed by Licensed Professional Engineer before actual installation or official permit use.

UI wording should therefore use terminology such as:

```text
Generated Layout

Planning Layout

Estimated Material Requirement

Estimated Project Cost
```

rather than representing outputs as professionally approved construction documents.

---

# 49. Coding Rules for Codex

When implementing this repository:

1. Inspect existing files before creating replacements.
2. Preserve working functionality unless requested task explicitly changes it.
3. Do not duplicate business logic between frontend and backend.
4. Keep FastAPI routers thin.
5. Put business logic in services.
6. Put persistence logic in repositories.
7. Keep AI processing isolated from HTTP route code.
8. Keep routing algorithms isolated from UI rendering.
9. Use typed Pydantic schemas for API input/output.
10. Use JavaScript types for frontend domain models.
11. Do not hard-code database IDs.
12. Do not hard-code material prices.
13. Do not hard-code filesystem paths.
14. Use environment variables for configuration.
15. Do not overwrite original floor-plan uploads.
16. Keep 2D and 3D geometry synchronized through shared geometry model.
17. Run relevant tests after modifying module.
18. Do not refactor unrelated modules during focused tasks.

---

# 50. Environment Variables

Example:

```env
APP_ENV=development

API_HOST=0.0.0.0
API_PORT=8000

# XAMPP-friendly local MySQL example.
# Replace change_me only in the ignored local .env file.
DATABASE_URL=mysql+pymysql://root:change_me@127.0.0.1:3306/ved_electrical

# OAuth 2.0 / OpenID Connect
OAUTH_PROVIDER=configure_me
OAUTH_CLIENT_ID=change_me
OAUTH_CLIENT_SECRET=change_me
OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/callback
OAUTH_DISCOVERY_URL=change_me
OAUTH_SCOPES=openid profile email

# Application session/state protection
SESSION_SECRET=change_me

UPLOAD_DIR=storage/uploads
PROCESSED_DIR=storage/processed
REPORT_DIR=storage/reports

YOLO_MODEL_PATH=models/yolo/electrical-symbols.pt

# Planned local-VLM values. Add them to .env.example only in the implementing
# ticket, after U6 selects and pins a runtime/model.
LOCAL_VLM_MODEL_PATH=models/vlm/base-model
LOCAL_VLM_ADAPTER_PATH=models/vlm/adapters/ved-approved
LOCAL_VLM_RUNTIME_URL=http://127.0.0.1:8081
LOCAL_VLM_ALLOW_NETWORK=false

FRONTEND_URL=http://localhost:5173
```

Real credentials must not be committed.

---

# 51. Definition of Done

feature is not considered complete only because it renders in browser.

module is complete when applicable requirements are satisfied:

```text
UI implemented

API implemented

Validation implemented

Authorization implemented

Database/schema change implemented

Database persistence implemented

Loading state implemented

Error state implemented

Relevant tests implemented

No unrelated regressions found

Project documentation updated
```

---

# 52. MVP Definition

minimum viable system should allow this complete workflow:

```text
User logs in
        ↓
Creates project
        ↓
Uploads floor plan
        ↓
System processes floor plan
        ↓
AI detects electrical symbols
        ↓
User reviews/corrects detections
        ↓
System builds editable 2D representation
        ↓
System generates synchronized 3D layout
        ↓
System calculates wiring routes
        ↓
System calculates material quantities
        ↓
Database pricing is applied
        ↓
System generates cost estimate
        ↓
System generates PDF report
```

If this complete pipeline does not work from beginning to end, system should still be considered under development even if individual pages appear finished.

---

# 53. Codex Start-Up Checklist

Before making major implementation change, Codex should determine:

```text
What module am I changing?

What existing files own this responsibility?

What API does it depend on?

What database entities does it depend on?

Does it affect the shared geometry model?

Does it affect both 2D and 3D?

Does it affect routing?

Does it affect estimates?

Does the MySQL development schema need to change?

What tests need to pass?
```

Then inspect relevant repository files before editing.

---

# 54. Architecture Summary

```text
                       ┌───────────────────────┐
                       │         USER          │
                       │ Electrical Designer   │
                       └───────────┬───────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────┐
│                  REACT FRONTEND                      │
│                                                      │
│ Dashboard │ Projects │ Konva 2D │ Three.js 3D        │
│ Routing │ Estimation │ Reports │ Admin UI            │
└─────────────────────────┬────────────────────────────┘
                          │
                    REST / JSON
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│                    FASTAPI                           │
│                                                      │
│ Auth │ Projects │ Processing │ Layout │ Routing      │
│ Materials │ Estimates │ Reports │ Administration     │
└─────────────┬───────────────────────┬────────────────┘
              │                       │
              ▼                       ▼
┌────────────────────────┐   ┌─────────────────────────┐
│      AI / CV ENGINE    │   │     MYSQL DATABASE      │
│                        │   │                         │
│ Page/Tiles/OCR         │   │ Users                   │
│ Local Multimodal VLM   │   │ Projects                │
│ Schema Validation      │   │ Layouts                 │
│ Evidence Fusion        │   │ Symbols                 │
└─────────────┬──────────┘   │ Routes                  │
              │              │ Materials               │
              ▼              │ Estimates               │
        Geometry Model       │ Reports                 │
              │              └─────────────────────────┘
       ┌──────┴──────┐
       │             │
       ▼             ▼
    Konva 2D     Three.js 3D
       │             │
       └──────┬──────┘
              │
              ▼
      Spatial Routing
              │
              ▼
     Material Quantity
              │
              ▼
      Cost Estimation
              │
              ▼
        PDF Report
```

---

# 55. Final Development Principle

core architecture should remain:

```text
Floor Plan
   ↓
AI Interpretation
   ↓
Verified Geometry
   ↓
2D + 3D Visualization
   ↓
Spatial Routing
   ↓
Material Quantification
   ↓
Cost Estimation
   ↓
Report
```

**AI detection should assist designer, while verified project geometry becomes authoritative source for later routing, visualization, material computation, and reports.**

Uploaded drawings may be unannotated from user's perspective. Training and
release evidence may not be: pseudo-labels require VED review, frozen test data
must stay out of training, and every promoted adapter must be reproducible and
reversible. A model must return empty/ambiguous evidence rather than fabricate
walls, symbols, scale, rooms, or observed wiring.

This separation is important because project explicitly supports manual correction of automatically generated layouts and uses those layouts as planning and estimation tool rather than as automatically approved engineering plan.

---

# 56. Codex Ticket Execution Rules

Codex should implement this project through **small, isolated tickets** instead of attempting large features in one pass.

Each ticket should:

1. Have one primary responsibility.
2. Touch smallest reasonable set of files.
3. Define explicit inputs and outputs.
4. List dependencies on earlier tickets.
5. Include acceptance criteria that can be checked manually or through tests.
6. Avoid unrelated refactors.
7. Preserve existing working functionality.
8. Include or update tests where practical.
9. Update documentation when ticket changes API, schema, environment variable, or shared data contract.
10. Report and publish completed ticket before continuing only within explicitly authorized sequence; otherwise stop.

## Ticket Completion Format

For every completed ticket, Codex should report:

```text
Ticket:
Status:
Files changed:
Database/schema changes:
API changes:
Tests added/updated:
Manual verification performed:
Known limitations:
Next dependency:
```

ticket is not complete until its acceptance criteria are satisfied.

---

# 57. Isolated Development Ticket Breakdown

Completed ticket descriptions below record what each ticket introduced at that
time. PRE1-PRE12 supersede older limitations around discovery, reload, artifact
manifests, metric inputs, catalog administration, save concurrency, execution
controls and reviewer authority. Current behavior is summarized above and in
PRE section; do not rebuild those foundations inside U tickets.

## Epic A — Repository Foundation

### TICKET A1 — Create Root Repository Structure

**Goal:** Create initial project directories without implementing application features.

**Dependencies:** None.

**Scope:**

```text
frontend/
backend/
storage/
docs/
models/
scripts/
```

**Acceptance Criteria:**

- [ ] All required root directories exist.
- [ ] No application feature code is added yet.
- [ ] `.gitignore` exists and excludes environment files, Python cache files, Node modules, uploaded files, generated reports, and local model artifacts where appropriate.
- [ ] `README.md` identifies frontend and backend directories.
- [ ] Existing files are not deleted or replaced without documented reason.

---

### TICKET A2 — Create Environment Configuration Template

**Goal:** Define environment variables required by application.

**Dependencies:** A1.

**Acceptance Criteria:**

- [ ] `.env.example` exists.
- [ ] It contains database, API, frontend URL, upload directory, processed directory, report directory, OAuth/OIDC, session, and YOLO model settings.
- [ ] No real password, secret, API key, or private connection string is committed.
- [ ] Backend configuration reads values from environment variables rather than hard-coded paths.
- [ ] Missing variables that are mandatory for active feature produce clear configuration/startup error.

---

### TICKET A3 — Initialize React + JavaScript + Vite Frontend

**Goal:** Create minimal runnable frontend.

**Dependencies:** A1.

**Acceptance Criteria:**

- [ ] React runs locally through Vite.
- [ ] JavaScript compilation succeeds.
- [ ] application has simple placeholder landing screen.
- [ ] No 2D, 3D, AI, or estimation logic is implemented yet.
- [ ] `npm run build` completes successfully.

---

### TICKET A4 — Initialize FastAPI Backend

**Goal:** Create minimal FastAPI application.

**Dependencies:** A1, A2.

**Acceptance Criteria:**

- [ ] FastAPI starts successfully through Uvicorn.
- [ ] `GET /health` returns HTTP 200.
- [ ] Health response follows documented JSON structure.
- [ ] API routes are separated from `main.py`.
- [ ] No business logic is placed in `main.py`.
- [ ] Backend dependencies are documented.

---

## Epic B — Database Foundation

### TICKET B1 — Configure SQLAlchemy MySQL Connection

**Goal:** Connect FastAPI to MySQL through SQLAlchemy and PyMySQL, using XAMPP-managed MySQL as primary Windows local-development workflow.

**Dependencies:** A2, A4.

**Acceptance Criteria:**

- [ ] Database URL comes from environment configuration.
- [ ] Application can connect to configured MySQL database.
- [ ] documented primary Windows local workflow can connect to MySQL started from XAMPP.
- [ ] SQLAlchemy engine/session management is isolated in backend core/database layer.
- [ ] PyMySQL is used as MySQL DBAPI driver unless later ticket explicitly changes it.
- [ ] failed connection produces clear application error without exposing credentials.
- [ ] No database credentials are hard-coded.
- [ ] Apache and PHP are not required by FastAPI database connection.
- [ ] No Alembic or migration framework is introduced in this ticket.

---

### TICKET B2 — Initialize Development Database Schema

**Goal:** Create current MySQL development schema from SQLAlchemy ORM models without introducing migration tooling.

**Dependencies:** B1.

**Acceptance Criteria:**

- [ ] MySQL remains configured database.
- [ ] Schema definitions come from SQLAlchemy models.
- [ ] controlled development initialization command/function can create missing tables using SQLAlchemy metadata.
- [ ] Running initialization against empty `ved_electrical` development database creates current required tables.
- [ ] Database credentials continue to come from environment configuration.
- [ ] No Alembic dependency, migration directory, or migration command is introduced.
- [ ] Development schema reset/recreation behavior is documented for prototype phase.
- [ ] No production schema-migration guarantee is claimed during this prototype phase.

---

### TICKET B3 — Create OAuth Users and Roles Tables

**Goal:** Implement local authorization schema used after OAuth/OIDC identity verification.

**Dependencies:** B2.

**Acceptance Criteria:**

- [ ] `roles` table exists.
- [ ] `users` table exists.
- [ ] user does not require local password or password-hash field.
- [ ] user model can store OAuth/OIDC provider identifier and provider subject/user identifier.
- [ ] Provider + provider subject uniquely identify external identity.
- [ ] Email and display name can be stored when supplied by configured identity provider.
- [ ] Optional avatar/profile image URL can be stored without making it mandatory.
- [ ] User references valid local VED role.
- [ ] Initial roles include `ADMIN` and `DESIGNER`.
- [ ] schema can be created successfully in MySQL development database through current SQLAlchemy schema initialization workflow.

---

### TICKET B4 — Create Projects Table

**Goal:** Persist project metadata.

**Dependencies:** B3.

**Acceptance Criteria:**

- [ ] `projects` table exists.
- [ ] Each project references its owner/creator.
- [ ] Project name, status, timestamps, and optional client/location metadata are supported.
- [ ] Project status uses documented set of allowed states.
- [ ] SQLAlchemy project model and constraints can be created successfully in MySQL development schema.

---

### TICKET B5 — Create Project Floors and Floor Plans Tables

**Goal:** Support multiple floors and uploaded source plans.

**Dependencies:** B4.

**Acceptance Criteria:**

- [ ] `project_floors` table exists.
- [ ] `floor_plans` table exists.
- [ ] project can have multiple floors.
- [ ] floor can reference one or more uploaded floor-plan records if versioning is required.
- [ ] Original filename, stored filename/path, MIME type, file size, and processing status are stored.
- [ ] Original uploads are not overwritten.

---

## Epic C — Authentication and Authorization

### TICKET C1 — Configure OAuth/OIDC Authentication

**Goal:** Establish provider-configurable OAuth 2.0 / OpenID Connect authentication configuration for FastAPI.

**Dependencies:** B3.

**Acceptance Criteria:**

- [ ] OAuth/OIDC configuration comes from environment variables.
- [ ] Client ID is not hard-coded.
- [ ] Client secret is not hard-coded.
- [ ] Redirect URI is configurable.
- [ ] Provider/discovery configuration is configurable.
- [ ] Required OAuth/OIDC settings fail clearly when authentication feature starts without them.
- [ ] Provider tokens and authorization codes are not logged.
- [ ] No local password authentication or password-hashing utility is introduced.

---

### TICKET C2 — Implement OAuth Login and Callback

**Goal:** Authenticate users through configured OAuth/OIDC provider and resolve verified identity to local MySQL user.

**Dependencies:** C1.

**Acceptance Criteria:**

- [ ] `GET /api/auth/login` starts OAuth/OIDC authorization flow.
- [ ] `GET /api/auth/callback` handles configured provider callback.
- [ ] OAuth state is validated before accepting callback.
- [ ] OIDC identity validation is applied when required by selected provider flow.
- [ ] Invalid or failed authorization returns controlled authentication error.
- [ ] Successful authentication resolves external provider identity to local MySQL user record.
- [ ] New valid external identities can create/link local VED user according to documented rule.
- [ ] No local password is requested or stored.
- [ ] OAuth client secrets are never returned to frontend.
- [ ] Raw provider tokens and authorization codes are not logged.
- [ ] Login activity can be audited later without changing endpoint contract.

---

### TICKET C3 — Implement Current User Endpoint

**Goal:** Allow frontend to restore authenticated VED application session.

**Dependencies:** C2.

**Acceptance Criteria:**

- [ ] `GET /api/auth/me` exists.
- [ ] Valid authentication returns current local user ID, name/display name, email when available, and VED role.
- [ ] Missing or invalid authentication returns HTTP 401.
- [ ] Protected route dependency is reusable by other routes.
- [ ] Provider tokens are not returned by `/api/auth/me`.

---

### TICKET C4 — Implement Role-Based Authorization

**Goal:** Restrict Admin and Designer actions using local MySQL role after OAuth/OIDC authentication.

**Dependencies:** C3.

**Acceptance Criteria:**

- [ ] Reusable backend role-check dependency exists.
- [ ] Admin-only sample route rejects Designer accounts.
- [ ] Designer-accessible routes remain accessible to authorized Designers.
- [ ] OAuth/OIDC provider identity does not directly grant VED Admin privileges.
- [ ] Authorization does not rely only on hiding frontend controls.
- [ ] Authorization behavior has automated tests.

---

### TICKET C5 — Build Frontend OAuth Sign-In Screen

**Goal:** Connect React authentication UI to FastAPI OAuth/OIDC flow.

**Dependencies:** A3, C2, C3.

**Acceptance Criteria:**

- [ ] Login screen provides provider-neutral Sign In action.
- [ ] Sign In starts backend OAuth/OIDC flow instead of collecting local password.
- [ ] Successful authentication returns user to application.
- [ ] OAuth/OIDC errors display readable error state.
- [ ] Authentication state can be restored using `/api/auth/me`.
- [ ] Protected frontend routes redirect unauthenticated users.
- [ ] OAuth client secrets and raw provider tokens are not exposed in browser logs.

---

### TICKET C6 — Implement Logout

**Goal:** End local authenticated VED application session.

**Dependencies:** C2, C3.

**Acceptance Criteria:**

- [ ] Logout endpoint/action exists.
- [ ] local authenticated application session is invalidated.
- [ ] `/api/auth/me` returns unauthenticated after logout.
- [ ] Frontend returns to unauthenticated state.
- [ ] Logout does not modify unrelated external provider account data.

---

## Epic D — Project Management

### TICKET D1 — Create Project API

**Goal:** Allow authenticated Designers to create projects.

**Dependencies:** B4, C4.

**Acceptance Criteria:**

- [ ] `POST /api/projects` exists.
- [ ] Project owner comes from authenticated user, not user ID supplied blindly by client.
- [ ] Required fields are validated.
- [ ] Created project is persisted.
- [ ] Response uses typed Pydantic schema.
- [ ] Unauthorized creation is rejected.

---

### TICKET D2 — List User Projects API

**Goal:** Return projects accessible to authenticated user.

**Dependencies:** D1.

**Acceptance Criteria:**

- [ ] `GET /api/projects` exists.
- [ ] Designer sees only projects they are authorized to view.
- [ ] Admin behavior is explicitly defined.
- [ ] Results include project status and updated timestamp.
- [ ] Empty project lists return empty array instead of error.

---

### TICKET D3 — Project Detail API

**Goal:** Load one project workspace.

**Dependencies:** D2.

**Acceptance Criteria:**

- [ ] `GET /api/projects/{project_id}` exists.
- [ ] Unauthorized project access returns 403 or 404 according to chosen policy.
- [ ] Project metadata is returned.
- [ ] Response does not load unrelated large AI or geometry payloads unnecessarily.
- [ ] Invalid IDs are handled cleanly.

---

### TICKET D4 — Project Dashboard UI

**Goal:** Display and open projects from React.

**Dependencies:** D2, D3.

**Acceptance Criteria:**

- [ ] Dashboard lists available projects.
- [ ] User can create project.
- [ ] User can open project.
- [ ] Empty, loading, and error states are visible.
- [ ] Project status displayed in UI comes from backend.

---

## Epic E — Floor Plan Upload

### TICKET E1 — Implement Upload Validation Service

**Goal:** Validate JPEG, PNG, and PDF inputs before storage.

**Dependencies:** B5.

**Acceptance Criteria:**

- [ ] JPEG is supported.
- [ ] PNG is supported.
- [ ] PDF is supported.
- [ ] Unsupported file types are rejected.
- [ ] MIME type and extension are checked.
- [ ] Maximum file size is configurable.
- [ ] Corrupt images/PDFs return clear validation error.
- [ ] Validation service is testable without HTTP request.

---

### TICKET E2 — Implement Floor Plan Storage Service

**Goal:** Save original uploads safely.

**Dependencies:** E1, A2.

**Acceptance Criteria:**

- [ ] Original file is saved under configured upload directory.
- [ ] Stored filenames avoid collisions.
- [ ] User-supplied filenames cannot escape upload directory.
- [ ] Original files are never modified by later processing.
- [ ] Database stores metadata and resulting storage reference.
- [ ] Failed storage does not leave inconsistent successful database record.

---

### TICKET E3 — Create Floor Plan Upload API

**Goal:** Upload plan into specific project/floor.

**Dependencies:** E2, D3.

**Acceptance Criteria:**

- [ ] `POST /api/projects/{project_id}/floor-plans` exists.
- [ ] Upload requires project authorization.
- [ ] Valid file creates `floor_plans` record.
- [ ] Invalid file returns clear 4xx response.
- [ ] Response includes floor plan ID and processing status.
- [ ] Existing original uploads remain unchanged.

---

### TICKET E3A — Project Floor API

**Goal:** List and create project floors required by upload workflow.

**Dependencies:** B5, C4, D3, E3.

**Acceptance Criteria:**

- [ ] `GET /api/projects/{project_id}/floors` exists.
- [ ] `POST /api/projects/{project_id}/floors` exists.
- [ ] Designer can list and create floors only for owned project.
- [ ] Cross-owner Designer access returns `404`.
- [ ] Admin can list project floors but cannot create them.
- [ ] accessible project with no floors returns empty array.
- [ ] Requests and responses use typed Pydantic schemas.
- [ ] Floor listing order is deterministic by `sort_order`, then ID.
- [ ] ticket introduces no database schema change.

---

### TICKET E4 — Build Floor Plan Upload UI

**Goal:** Allow users to upload floor plans from project workspace.

**Dependencies:** E3, E3A.

**Acceptance Criteria:**

- [ ] JPEG, PNG, and PDF are selectable.
- [ ] Unsupported files are blocked or clearly rejected.
- [ ] Upload progress/loading state is visible.
- [ ] Successful upload appears in project workspace.
- [ ] Backend validation errors are shown to user.
- [ ] Uploading does not automatically modify original source image.

---

## Epic F — AI Processing Jobs

### TICKET F1 — Create Processing Jobs Table

**Goal:** Track long-running analysis operations.

**Dependencies:** B5.

**Implementation status:** Complete. F1 persists job records only; F2 owns
start-processing behavior.

Implemented database contract:

- `processing_jobs.floor_plan_id` is indexed required foreign key to
  `floor_plans.id`.
- database column `type` is exposed as Python attribute `job_type` and
  remains open to future job types.
- `status` defaults to `queued` and is constrained by
  `ck_processing_jobs_status`.
- `progress` defaults to `0` and is constrained to 0–100 inclusive by
  `ck_processing_jobs_progress`.
- `error_message` is nullable; `created_at` and `updated_at` are
  server-generated.
- `FloorPlan.processing_jobs` and `ProcessingJob.floor_plan` form the
  bidirectional relationship.

No processing API, automatic upload hook, background worker, queue, or AI/CV
operation is part of F1.

**Acceptance Criteria:**

- [ ] `processing_jobs` table exists.
- [ ] Job stores type, status, progress, timestamps, and error message.
- [ ] Allowed states include `queued`, `processing`, `completed`, `failed`, and `cancelled`.
- [ ] Job references relevant floor plan.
- [ ] processing-jobs model can be created successfully in current MySQL development schema.

---

### TICKET F2 — Create Start Processing Endpoint

**Goal:** Start analysis without blocking initial request.

**Dependencies:** F1, E3.

**Implementation status:** Complete. F2 creates and commits queued
`floor_plan_analysis` job, then returns immediately without running analysis.

Implemented behavior:

- `POST /api/floor-plans/{floor_plan_id}/process` accepts no request body and
  returns `202` with typed `job_id` and `queued` status.
- Only owning Designer may start processing. Admin and unsupported roles
  receive `403`; missing, inaccessible, and cross-owner records use sanitized
  responses without disclosing ownership.
- authorized floor-plan row is locked with `SELECT ... FOR UPDATE` before
  checking active jobs. Existing `queued` or `processing` jobs return `409`;
  terminal jobs permit another attempt.
- processing-job row is durable queue entry. No worker or AI operation
  runs during F2.
- Failure-state persistence stores stable safe message and does not modify the
  original upload or `floor_plans.processing_status`.
- Database creation failures roll back and return sanitized `503`.

F2 does not add F3's status endpoint, worker, external queue, automatic
upload hook, cancellation behavior, or floor-plan listing endpoint.

**Acceptance Criteria:**

- [ ] `POST /api/floor-plans/{id}/process` exists.
- [ ] It checks floor-plan authorization.
- [ ] processing job is created.
- [ ] Response returns job ID.
- [ ] second accidental request does not silently create uncontrolled duplicate processing.
- [ ] Job failure is persisted.

---

### TICKET F3 — Create Processing Status Endpoint

**Goal:** Allow frontend to track job progress.

**Dependencies:** F2.

**Implementation status:** Complete. F3 adds read-only status endpoint without
starting worker or mutating processing state.

Implemented behavior:

- `GET /api/processing-jobs/{job_id}` returns only `job_id`, `type`, `status`,
  `progress`, and nullable `error_message`.
- Designers may read jobs belonging to their own projects; Admins may read any
  job. Missing and cross-owner jobs share sanitized `404`.
- Unauthenticated requests receive `401`; unsupported roles receive `403`.
- Failed jobs return stable generic error message. Raw stored errors, paths,
  SQL text, secrets, and stack traces are never returned.
- Repository reads select only public job fields, prohibit relationship lazy
  loading, acquire no row lock, and perform no writes.

F3 does not add processing UI, worker, external queue, cancellation behavior,
automatic upload hook, AI/CV behavior, or floor-plan listing endpoint.

**Acceptance Criteria:**

- [ ] `GET /api/processing-jobs/{id}` exists.
- [ ] Response includes status and progress.
- [ ] Failed jobs include safe error message.
- [ ] Internal stack traces and filesystem paths are not returned.
- [ ] Unauthorized job access is rejected.

---

### TICKET F4 — Build Processing Status UI

**Goal:** Show AI processing progress in React.

**Dependencies:** F3.

**Implementation status:** Complete. F4 adds frontend controls for starting and
monitoring jobs associated with upload responses retained in current page
session. It adds no backend or OpenAPI operation.

Implemented behavior:

- Designer upload cards can start one F2 request at time. Admins receive no
  processing controls.
- valid F2 active-job conflict is adopted using only its positive integer job
  ID; malformed conflicts require explicit new attempt.
- Queued and processing jobs show exact F3 progress. Polling uses a
  sequential, abortable two-second timeout and never overlaps status requests.
- Polling stops on terminal states, unmount, session expiry, authorization or
  lookup failures, and temporary errors. Temporary failures preserve job
  ID and offer explicit status retry instead of retrying indefinitely.
- Completed jobs state that analysis review is later feature. Failed and
  cancelled jobs offer new F2 attempt; failed output uses only F3's sanitized
  nullable error message or generic fallback.

F4 does not add persistent upload discovery, local storage, worker, external
queue, cancellation endpoint, AI/CV processing, or result/review behavior.
Because no floor-plan listing endpoint exists, controls do not repopulate after
reload.

**Acceptance Criteria:**

- [ ] UI can start processing.
- [ ] UI displays queued/processing/completed/failed states.
- [ ] Completed processing triggers next workflow state.
- [ ] Failed processing offers clear retry path.
- [ ] page does not freeze while analysis is running.

---

## Epic G — Image Preprocessing

### TICKET G1 — Implement PDF-to-Image Conversion

**Goal:** Convert supported PDF pages into processable raster images.

**Dependencies:** F2.

**Implementation status:** Complete. G1 adds isolated backend service using
`pypdfium2==5.13.0` with bundled PDFium. It is callable without FastAPI, HTTP, or
database connection at its low-level boundary.

Implemented behavior:

- Each call converts exactly one page to RGB PNG. Page numbers are one-based,
  default to page 1, and reject zero, negative, or out-of-range values.
- Rendering defaults to 150 DPI. Validated internal callers may supply another
  DPI; neither page nor DPI selection is exposed through HTTP in G1.
- Output uses
  `pdf-pages/floor-plan-<id>/job-<id>/page-<NNNN>.png` beneath
  `PROCESSED_DIR`, and returned reference uses forward slashes.
- Persisted source references must remain relative and resolve beneath
  `<UPLOAD_DIR>/originals`. The source must be regular PDF with
  `application/pdf` metadata. Traversal, absolute paths, symlink escapes, and
  raster inputs are rejected.
- Rendering enforces pre-allocation pixel limit, honors effective page
  rotation, encodes in memory, and writes exclusively without silently
  overwriting existing derived page. Partial output is removed where safe.
- higher-level callable commits job as `processing` before conversion.
  Success leaves broader job `processing`; it does not mark analysis
  complete or alter `floor_plans.processing_status`.
- Conversion failure commits `failed` with only
  `Floor-plan PDF conversion failed.` Raw renderer errors, paths, SQL, and stack
  traces are not persisted. Persistence failure is reported separately and
  safely.
- Original PDF bytes and floor-plan metadata remain unchanged. The derived path
  is returned to later orchestration and is not stored in new table.

G1 is not automatically invoked by F2 because no worker exists. It adds no API,
schema, normalization, OpenCV, AI inference, or raster-input processing. G2 is
implemented as separate downstream callable.

**Acceptance Criteria:**

- [ ] PDF conversion is isolated in service/module.
- [ ] Output image path is separate from original PDF.
- [ ] Original PDF remains unchanged.
- [ ] Conversion errors mark processing job as failed.
- [ ] Page selection behavior is documented.
- [ ] Unit/integration test covers at least one valid PDF.

---

### TICKET G2 — Implement Image Normalization

**Goal:** Normalize image orientation and processing dimensions.

**Dependencies:** G1 for PDFs; E3 for image inputs.

**Implementation status:** Complete. G2 adds Pillow-only backend service with
filesystem/scalar low-level boundary and database-aware processing-job
wrapper. No FastAPI route or worker invokes it.

Implemented behavior:

- Uploaded JPEG/PNG originals are resolved beneath `<UPLOAD_DIR>/originals`.
  PDF input requires matching G1 `ConvertedPdfPage` or strictly validated
  portable reference beneath same floor-plan/job directory.
- Content is fully decoded and must match its MIME type and extension. Traversal,
  absolute paths, missing files, directories, symlink escapes, corrupt/truncated
  content, and decompression-bomb dimensions fail safely.
- EXIF orientation is applied without portrait/landscape guessing. Transparency
  is composited onto white, supported modes are converted to RGB, and source
  EXIF/unrelated metadata is removed from derived PNG.
- Images are never upscaled. The longest oriented edge is reduced to 4096 pixels
  only when necessary, preserving aspect ratio with LANCZOS resampling.
- `NormalizedImage` records encoded, oriented, and final dimensions plus
  orientation/resizing flags, MIME types, IDs, reference, and byte size.
- Output is created exclusively at
  `normalized/floor-plan-<id>/job-<id>/image.png` beneath `PROCESSED_DIR`.
  Existing results are not overwritten and partial writes are removed safely.
- Queued and already-processing jobs are accepted. Progress remains unchanged;
  success leaves broader job `processing`. Failure persists only
  `Floor-plan image normalization failed.`
- Floor-plan metadata, original uploads, and G1 pages remain unchanged. No
  `processed_images` table, new column, sidecar, API, worker, OpenCV behavior, or
  automatic F2/G1/G2 orchestration is added.

G3 is implemented separately and consumes only G2 normalized output.

**Acceptance Criteria:**

- [ ] JPEG and PNG inputs can be loaded.
- [ ] PDF-converted images can be loaded.
- [ ] Image dimensions are recorded.
- [ ] Processing does not replace original.
- [ ] Normalized output is written to processed storage directory.
- [ ] Invalid image input fails gracefully.

---

### TICKET G3 — Implement OpenCV Preprocessing Pipeline

**Goal:** Produce processed images for wall and symbol detection.

**Dependencies:** G2.

**Implementation status:** Complete. G3 adds isolated
`app.ai.preprocessing` package using `opencv-python-headless==4.14.0.94` and
`numpy==2.5.2`. It has no FastAPI route and is not invoked automatically by F2
or G2 because no worker exists.

Implemented behavior:

- pure array boundary consumes three-channel normalized RGB `uint8` data and
  returns typed stage arrays without HTTP, filesystem, or database requirements.
- Stage order is grayscale, median noise reduction, optional Gaussian blur,
  then binary thresholding. Dimensions and `uint8` dtype are preserved; the
  final image contains only 0 and 255.
- Otsu thresholding is default and records selected threshold. Fixed
  threshold mode uses explicit 0-through-255 value. Binary inversion is
  disabled unless configured.
- Frozen `PreprocessingParameters` defaults to median kernel 3, Gaussian enabled
  with kernel 3 and sigma 0.0, Otsu mode, fixed value 127, no inversion, and no
  debug writes. Kernels are validated odd integers from 3 through 31; Boolean
  numeric values, non-finite sigma, unknown modes, and unknown fields fail safely.
- filesystem boundary accepts only matching G2 `NormalizedImage` or exact
  `normalized/floor-plan-<id>/job-<id>/image.png` reference beneath
  `PROCESSED_DIR`. IDs, absolute/portable path agreement, symlink confinement,
  PNG format, three-channel content, and dimensions are validated. G2 bytes are
  never modified.
- Optional debug artifacts are exclusive single-channel PNGs beneath
  `preprocessed/floor-plan-<id>/job-<id>/`: `grayscale.png`, `denoised.png`,
  optional `blurred.png`, and `thresholded.png`. Existing files are not
  overwritten and partial writes receive compensating cleanup.
- optional database wrapper requires matching already-`processing`
  `floor_plan_analysis` job. Success preserves status and progress; failure
  persists only `Floor-plan preprocessing failed.`
- G3 adds no schema, manifest, processed-image row, worker, API, morphology,
  Canny, Hough, contour, wall-detection, YOLO, or geometry behavior. H1 is next.

**Acceptance Criteria:**

- [ ] Grayscale conversion is implemented.
- [ ] Noise reduction is implemented.
- [ ] Gaussian blur is implemented where configured.
- [ ] Thresholding is implemented.
- [ ] Processing parameters are centralized/configurable.
- [ ] Output can be saved for debugging/evaluation.
- [ ] Unit tests verify expected output type and dimensions.

---

## Epic H — Structural Geometry Detection

### TICKET H1 — Implement Wall-Line Detection Prototype

**Goal:** Detect candidate wall lines from processed floor plan.

**Dependencies:** G3.

**Implementation status:** Complete. H1 adds isolated in-memory candidate
detector using Canny edge detection followed by OpenCV's probabilistic Hough
transform. It consumes only G3's thresholded array and does not reopen or write
any image file.

Implemented behavior:

- `WallDetectionParameters` centralizes strictly validated prototype defaults:
  Canny 50/200 with aperture 3; Hough rho 1.0, theta 1.0 degree, vote threshold
  50, minimum length 50, maximum gap 10, and maximum 2000 candidates.
- Input is either G3 `PreprocessedImage` or isolated two-dimensional binary
  `uint8` array. Dimensions must be positive and no edge may exceed 4096 pixels.
  G3 width/height must match thresholded array, and input bytes are not
  mutated.
- Candidate coordinates are ordinary Python integers in raw pixel space with a
  top-left origin, x increasing right, and y increasing down. The topmost
  endpoint is first; leftmost endpoint breaks horizontal ties.
- Angles are normalized to `[0, 180)`, and public angle and pixel-length values
  are rounded to six decimal places.
- Exact canonical duplicates are removed. Nearby or collinear segments are not
  merged. Candidates sort by start y, start x, end y, then end x before one-based
  IDs are assigned, producing stable JSON-serializable output.
- Unique results above configured maximum are deterministically capped and
  return `truncated=true`. Empty, all-white, all-black, and no-line inputs return
  empty candidate tuple and `truncated=false` without error.
- Candidates are raw, unverified wall suggestions. H1 does not add persistence,
  walls tables, previews, scale conversion, thickness/pairing, rooms, APIs,
  workers, job-state changes, frontend overlays, YOLO, or symbol detection.

H2 coordinate normalization is next roadmap ticket.

**Acceptance Criteria:**

- [ ] Hough Line Transform or selected OpenCV method is isolated in wall-detection module.
- [ ] Detection returns coordinates rather than drawing directly into UI.
- [ ] Output uses documented coordinate structure.
- [ ] Empty/noisy detection results are handled without crashing.
- [ ] sample test image produces deterministic output format.

---

### TICKET H2 — Normalize Wall Coordinates

**Goal:** Convert image-space wall coordinates into canonical geometry representation.

**Dependencies:** H1.

**Implementation status:** Complete. H2 adds pure, immutable `app.geometry`
contract that validates H1 output and converts its raw image-space candidates
into shared metric plane. It executes no OpenCV and has no API, filesystem,
database, worker, model, job-state, or frontend dependency.

Implemented behavior:

- Every conversion requires explicit positive finite `pixels_per_meter`.
  There is no default. Booleans, zero, negatives, strings, NaN, infinity, and
  missing values fail through sanitized error contract.
- Physical scale is never inferred from PDF rendering DPI. The specification's
  `100 pixels_per_meter` example is illustrative, not calibrated project data.
- Canonical coordinates use meters, normalized image's top-left origin,
  x increasing right, and y increasing down, preserving image overlay alignment.
- H1 candidate IDs and deterministic order, raw integer endpoints, raw lengths,
  raw angles, and source truncation are preserved exactly. Empty H1 results
  remain valid empty geometry.
- Canonical endpoints use `pixel_coordinate / pixels_per_meter`; metric length
  is derived from canonical endpoints rather than trusting raw length.
- Internal immutable values retain full floating-point precision. Serialized
  metric coordinates and lengths round to nine decimal places, normalize
  negative zero, remain numeric, and contain only ordinary Python/JSON values.
- Complete H1 metadata, dimensions, IDs, candidate order, endpoint bounds,
  length, and angle contracts are validated before conversion. No NumPy scalar
  value escapes into geometry result.
- H2 does not merge, snap, extend, filter, or deduplicate H1 candidates again.
  It does not implement wall thickness, rooms, persistence, or scale detection.
- Future Konva and Three.js adapters must consume same canonical coordinates.
  Conceptually canonical x maps to Three.js x, canonical y to Three.js z, and
  floor elevation to Three.js y; no adapter or renderer is implemented in H2.

H2 output remains unverified machine-candidate geometry. H3 persists that
contract, while K1 still owns complete cross-domain project geometry schema.

**Acceptance Criteria:**

- [ ] Raw pixel coordinates are preserved where needed.
- [ ] Canonical coordinates use one documented unit/scale model.
- [ ] Conversion is implemented in geometry layer rather than UI code.
- [ ] Konva and Three.js do not define separate wall geometries.
- [ ] Coordinate conversion has unit tests.

---

### TICKET H3 — Persist Wall Geometry

**Goal:** Save detected/verified walls.

**Dependencies:** H2.

**Implementation status:** Complete. H3 adds seventh prototype table,
`walls`, plus repository and service boundaries for transactional detected-wall
replacement and read-only retrieval. It does not connect H1/H2 to worker or
HTTP route.

Implemented behavior:

- Every wall retains indexed floor-plan and processing-job foreign keys. Its
  project-floor association is reached through `Wall -> FloorPlan ->
  ProjectFloor`; no redundant project-floor key is stored.
- Raw pixel endpoints/length, canonical meter endpoints/length, explicit
  pixels-per-meter scale, candidate ID, angle, status, and timestamps are stored.
  Fixed-scale `Decimal` columns preserve persistence boundary.
- Status is constrained to `detected` or `verified`. H3 machine persistence
  writes only `detected`; it does not add verification transition or editor.
- Persistence requires exact, complete, nontruncated H2 geometry and matching
  `floor_plan_analysis` job whose status remains `processing`.
- Replacement locks floor-plan row, protects verified walls, deletes the
  current detected set, inserts complete replacement, and commits once.
  Identical reruns do not accumulate duplicates, newer jobs replace older
  detected rows, fewer candidates remove stale rows, and empty geometry clears
  detected set.
- Any database read, delete, insertion, flush, or commit failure rolls back the
  replacement and surfaces only stable sanitized error. Job progress/status,
  floor-plan processing status, and stored image files are not changed.
- Retrieval returns immutable candidate-ordered tuple with exact internal
  `Decimal` values and optional JSON-compatible serializer. It loads no
  relationships and executes neither OpenCV nor H2 conversion.
- H3 adds no HTTP wall API, review UI, manual editing, room/door/window/symbol
  persistence, worker, layout versioning, I1 behavior, or complete K1 geometry.

**Acceptance Criteria:**

- [ ] Walls are associated with correct floor plan/floor.
- [ ] Start and end coordinates are stored.
- [ ] Geometry can be retrieved later without rerunning OpenCV.
- [ ] Reprocessing behavior is defined so duplicate wall sets are not silently accumulated.
- [ ] Persistence tests pass.

---

## Epic I — Implemented Legacy YOLO Symbol Detection

I1-I4 are completed implementation history and remain migration comparison
and rollback path. They are not target production architecture after U14.

### TICKET I1 — Implement YOLO Model Loader

**Goal:** Load configured trained electrical-symbol model.

**Dependencies:** A2.

**Implementation status:** Complete. I1 adds isolated lazy loader for a
configured local `.pt` model. `YOLO_MODEL_PATH` is only model-location
setting; relative values resolve from repository root and maintained
example is `models/yolo/electrical-symbols.pt`. No trained model is committed to
repository.

Implemented behavior:

- Local path, extension, file type, existence, and readability are validated
  before official `YOLO(model_path)` constructor is called, preventing model
  shorthand from triggering automatic download.
- Absolute local paths are supported, while URLs, directories, malformed paths,
  unsupported extensions, and missing files fail with stable sanitized errors.
- Class names are normalized dynamically from list- or dictionary-shaped
  `model.names` metadata. No electrical class names are assumed in code.
- Successful loads use bounded, thread-safe process-local cache by canonical
  path. Concurrent first callers load once, failures remain retryable, and tests
  can explicitly reset cache or inject fake model factory.
- Importing FastAPI does not load model. Missing or invalid weights therefore
  cause controlled loader/processing error only when loader is called,
  rather than application-wide startup crash.
- I1 invokes no prediction or preprocessing, persists no detections, changes no
  processing jobs, and adds no API or worker integration. I2 remains future
  inference ticket.
- `ultralytics-opencv-headless==8.4.131` uses AGPL-3.0 or separately obtained
  Enterprise license. Commercial or production use requires licensing review.

**Acceptance Criteria:**

- [ ] Model path comes from configuration.
- [ ] Missing model produces clear startup or processing error.
- [ ] Model loading is not repeated unnecessarily for every detected object.
- [ ] Model loader is isolated from API route files.
- [ ] Application does not assume classes not present in trained model.

---

### TICKET I2 — Implement Symbol Inference Service

**Goal:** Run YOLO on processed floor plan.

**Dependencies:** I1, G3.

**Implementation status:** Complete. I2 is isolated in-memory inference
boundary and processing-job failure wrapper. It adds no route, worker,
automatic orchestration, output image, schema table, or detected-symbol
persistence.

Implemented behavior:

- primary boundary accepts only valid G3 `PreprocessedImage` and consumes
  `thresholded`. The source must be nonempty two-dimensional `uint8` array,
  match declared dimensions, contain only 0/255, and remain within the
  existing 4096-pixel limit.
- YOLO receives separate contiguous three-channel binary copy, so prediction
  cannot mutate or share writable memory with G3 output. It receives no path,
  URL, camera identifier, or save destination.
- Prediction arguments are exactly `conf=0.0`, `max_det=300`, `verbose=False`,
  `save=False`, and `stream=False`. The zero confidence floor deliberately
  leaves threshold ownership to I3 and preserves detections below 0.50.
- Exactly one single-image detection result is required. Tensor-like and NumPy
  output is converted into immutable, ordered `SymbolPrediction` records with
  dynamically resolved class ID/name, original finite confidence, validated
  `x_min/y_min/x_max/y_max`, and derived center. Coordinates use processed
  pixels with top-left origin, positive X right, and positive Y down.
- Empty boxes are successful. Exactly 300 detections set
  `detection_limit_reached=True`; malformed or excess output fails instead of
  being clipped or silently accepted.
- job wrapper requires matching positive floor-plan/job association, job
  type `floor_plan_analysis`, and status `processing`. Success leaves status,
  progress, and error unchanged. Model loading, prediction, or result conversion
  failure marks job failed with only `Floor-plan symbol inference failed.`;
  persistence failure rolls back and surfaces sanitized error.
- I2 performs no I3 confidence classification/filtering and no I4 database
  persistence. I3 remains separate stage implemented below.

**Acceptance Criteria:**

- [ ] Inference accepts processed image.
- [ ] Output includes class, confidence, bounding box, and center coordinates.
- [ ] Raw inference output is converted to stable internal schema.
- [ ] Empty detection results are valid.
- [ ] AI inference errors mark job appropriately.

---

### TICKET I3 — Implement Confidence Filtering

**Goal:** Apply source-defined confidence threshold.

**Dependencies:** I2.

**Implementation status:** Complete. I3 classifies every validated I2
prediction using application confidence threshold. It is immutable,
in-memory transformation and neither invokes YOLO nor mutates processing job.

Implemented behavior:

- configuration-aware boundary reads existing
  `Settings.yolo_confidence_threshold`, whose default is exactly `0.50`, and
  supports injected settings for isolated tests. The pure boundary accepts an
  explicit finite numeric threshold from `0.0` through `1.0`; Boolean, textual,
  non-finite, and out-of-range values fail with sanitized error.
- Confidence equal to or greater than threshold receives `detected`.
  Confidence below threshold receives `needs_review`; it is never dropped
  or treated as confirmed.
- Each immutable classified record contains original `SymbolPrediction`
  object unchanged. Model order, exact confidence, dynamic class metadata,
  bounding box, center, image dimensions, maximum-detection value, and
  detection-limit flag are preserved.
- Empty I2 results are valid. Malformed I2 containers, predictions, confidence,
  geometry, and inconsistent detection-limit metadata fail safely.
- I3 adds no table, detected-symbol persistence, API, worker, orchestration, job
  transition, Designer confirmation/correction, or frontend behavior. I4 is the
  next ticket.

**Acceptance Criteria:**

- [ ] Default threshold is `0.50`.
- [ ] Threshold is configurable.
- [ ] Predictions above/at threshold and below threshold are distinguishable.
- [ ] Low-confidence predictions are not silently treated as confirmed.
- [ ] Original confidence value is preserved.

---

### TICKET I4 — Persist Detected Symbols

**Goal:** Save detection results independently from later manual edits.

**Dependencies:** I3.

**Implementation status:** Complete. I4 adds eighth prototype table,
`detected_symbols`, with backend-only transactional persistence and immutable
retrieval. It adds no route, worker, job completion, Designer review action,
symbol-legend integration, or canonical geometry.

Implemented behavior:

- Each row stores floor-plan and processing-job foreign keys, one-based source
  prediction index, I3 machine status/threshold, original I1/I2 class and
  confidence, processed-image dimensions, original bounding box and center,
  detection maximum/cap provenance, and timestamps. Original fields are
  explicit snapshots for later auditable correction work.
- Only `detected` and `needs_review` are accepted, and status must agree with the
  stored original confidence and threshold. Complete input validation rejects
  malformed, nonfinite, out-of-bounds, inconsistent, oversized, or mutable I3
  results before database mutation.
- Processing jobs are machine-result versions. Same-job persistence locks the
  floor plan and atomically replaces only that job's rows. A newer job preserves
  older versions. Empty results clear only selected job. A named unique
  constraint prevents duplicate job/prediction indexes.
- After J3, same-job replacement is rejected before deletion when any existing
  detection has review history. Unreviewed same-job and different-job versions
  preserve I4's original behavior.
- Persistence requires matching `floor_plan_analysis` job in `processing` and
  commits once. Any read, deletion, insertion, flush, or commit failure rolls
  back entire replacement and exposes only sanitized error.
- Retrieval requires floor-plan and processing-job identity, orders by
  prediction index then row ID, returns immutable JSON-compatible records, and
  executes no model loading, inference, confidence classification, OpenCV, or
  filesystem operation.
- Successful persistence leaves processing-job status/progress/error and
  floor-plan processing status unchanged. J1 is next normal ticket.

**Acceptance Criteria:**

- [ ] Each detection references correct floor plan.
- [ ] Symbol class is stored.
- [ ] Confidence is stored.
- [ ] Bounding box and center position are stored.
- [ ] Detection status is stored.
- [ ] Reprocessing behavior is versioned or clearly replaces previous machine result.
- [ ] User corrections do not erase original AI result without trace.

---

## Epic J — Detection Review

### TICKET J1 — Create Detection Results API

**Goal:** Return structural and symbol results for review.

**Dependencies:** H3, I4.

**Implementation status:** Complete. J1 adds ownership-aware, read-only API
for persisted H3/I4 results without rerunning AI/CV or changing database state.

Implemented behavior:

- `GET /api/floor-plans/{floor_plan_id}/detections` requires positive
  `processing_job_id` query parameter identifying exact
  `floor_plan_analysis` symbol-result version.
- Owning Designers may read their own project results; Admins may read any
  matching floor-plan/job context. Missing, mismatched, wrong-type, and
  cross-owner contexts share same sanitized `404`.
- Symbols come only from requested job and remain ordered by prediction
  index then row ID. Empty versions return empty array and never fall back to
  older job.
- Walls remain H3's current floor-plan wall set, ordered by candidate then row
  ID. Each wall includes its own processing-job provenance because wall and
  symbol job versions may differ.
- Explicit nested Pydantic schemas expose raw-pixel and canonical-meter walls,
  original symbol class/confidence, I3 threshold/status, pixel geometry, image
  dimensions, detection-cap metadata, and timestamps.
- Each symbol includes nullable latest-review decision, sequence, and timestamp
  loaded with one deterministic bulk query. Its I3 machine status is unchanged.
- Valid contexts with no stored records return HTTP 200 with empty arrays.
  Database failures return sanitized `503`; FastAPI validation retains its
  standard response shape.
- Repository reads use scoped joins, `load_only`, `raiseload("*")`, deterministic
  ordering, no row locks, and no writes. J1 performs no commit, AI inference,
  confidence filtering, persistence, filesystem access, or state transition.
- J1 itself adds no schema, dependency, configuration, worker, frontend, review
  mutation, or canonical geometry. J1A and J2 provide review image/canvas;
  J3 extends only response with persisted latest decision.

**Acceptance Criteria:**

- [ ] `GET /api/floor-plans/{id}/detections` exists.
- [ ] Response returns walls and symbols in documented schema.
- [ ] Symbol confidence values are included.
- [ ] Low-confidence status is included.
- [ ] Unauthorized access is rejected.

---

### TICKET J1A — Create Detection Review Image API

**Goal:** Securely serve existing normalized blueprint reference required
for pixel-aligned detection review.

**Dependencies:** G2, J1.

**Implementation status:** Complete. J1A adds
`GET /api/floor-plans/{floor_plan_id}/review-image` with required positive
`processing_job_id`. Owning Designers and Admins can retrieve only existing
G2 RGB PNG for exact `floor_plan_analysis` floor-plan/job context.

endpoint validates deterministic containment beneath `PROCESSED_DIR`,
symlink safety, PNG content, RGB mode, bounded bytes, and G2 dimensions. It
returns private, non-cacheable `image/png` bytes and never invokes G1/G2/G3,
creates artifact, exposes path, changes original, or writes database
state.

**Acceptance Criteria:**

- [x] Authorized users can retrieve exact existing normalized RGB PNG.
- [x] Missing, inaccessible, mismatched, and unsafe resources fail safely.
- [x] Private cache and content-sniffing headers are present.
- [x] No file generation, original mutation, or database write occurs.

---

### TICKET J2 — Build Detection Review Canvas

**Goal:** Display AI results over original plan.

**Dependencies:** J1, J1A.

**Implementation status:** Complete. J2 adds strict detection JSON and
review-image clients, protected positive-safe-integer hash route, completed
job review link, and dedicated read-only React-Konva feature. The canvas uses
four layers for normalized blueprint, current walls, selected-job symbols,
and selection highlighting. All overlays share one responsive source-pixel
scale and never mutate backend coordinates.

page handles loading, empty, capped, missing, authorization, temporary,
session-expired, malformed-data, retry, abort, and object-URL cleanup states.
accessible DOM table and details panel expose original class/confidence,
threshold, status, geometry, detection ID, order, and job provenance. J2 adds no
editing or persistence action. Current-session upload cards expose completed
jobs; direct review URLs remain valid when identifiers are known.

**Acceptance Criteria:**

- [x] Normalized blueprint displays as non-destructive background/reference.
- [x] Detected walls are visually overlaid.
- [x] Detected electrical symbols are visually overlaid.
- [x] Confidence/status can be inspected.
- [x] Canvas uses J1/J1A backend data rather than hard-coded sample components.

---

### TICKET J3 — Confirm or Reject Detection

**Goal:** Allow Designer to review individual AI detections.

**Dependencies:** J2.

**Implementation status:** Complete. J3 adds ninth prototype table,
`detection_reviews`, and owning-Designer review mutation while retaining the
complete I4 machine result unchanged.

Implemented behavior:

- `PUT /api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review`
  requires exact positive `processing_job_id` and strict body containing
  only `confirmed` or `deleted`.
- Reviewer identity and ownership come from authenticated local database
  user. Admins and unsupported roles receive `403`; missing, mismatched, and
  cross-owner resources share non-disclosing `404`.
- Review events are append-only. The first decision uses sequence one, an
  identical repeat creates no event, and reversal appends next sequence.
  selected detection is row-locked during sequence allocation.
- J1 returns only latest review in nullable nested object through one bulk
  query. It does not lock or mutate retrieval state.
- `detected_symbols.status`, original class/confidence/threshold, pixel geometry,
  prediction/job provenance, and timestamps remain immutable during review.
- I4 rejects same-job replacement once any detection in that version has review
  history. Unreviewed and different-job replacement behavior is preserved.
- J2's canvas now labels machine status separately from pending/confirmed/deleted
  Designer decisions. Confirm/reject actions are disabled in flight, announce
  success/errors accessibly, preserve selection, and keep rejected detections
  visible in muted presentation.
- J3 adds no J4 classification correction, J5 manual placement, dragging,
  resizing, canonical geometry, worker, dependency, or model class.

**Acceptance Criteria:**

- [x] User can confirm detection.
- [x] User can mark detection as incorrect/deleted.
- [x] Changes persist after page reload.
- [x] Original AI result remains auditable.
- [x] User cannot modify another user's project without authorization.

---

### TICKET J3A — Approved Symbol Legend Foundation

**Goal:** Provide stable approved symbol-class source required by J4 without
inventing or seeding production VED classes.

**Dependencies:** J3.

**Implementation status:** Complete. J3A adds `symbol_legends` as tenth
prototype table and exposes authenticated, read-only active legend retrieval.

Implemented behavior:

- `GET /api/symbol-legends` permits authenticated Designers and Admins.
- Active records are ordered by model class ID then database ID; inactive rows
  are excluded and empty catalog returns HTTP 200 with `[]`.
- Class IDs and normalized names are unique. Names use deliberate
  case-sensitive `utf8mb4_bin` MySQL collation.
- Retrieval performs no model loading, inference, filesystem access, database
  mutation, flush, commit, or row lock.
- No approved production VED values were supplied, so J3A seeds none. PRE7
  implements P3's Admin API; P4 owns future management UI.

**Acceptance Criteria:**

- [x] `symbol_legends` is registered and creatable through SQLAlchemy metadata.
- [x] Active approved classes have typed read-only API.
- [x] Designer and Admin retrieval authorization is enforced.
- [x] Empty-catalog behavior is explicit and safe.
- [x] No guessed production symbol class is committed or seeded.

---

### TICKET J4 — Correct Symbol Classification

**Goal:** Change incorrectly classified detected symbol.

**Dependencies:** J3, J3A.

**Implementation status:** Complete. J4 adds eleventh prototype table,
`detection_class_corrections`, Designer-only classification mutation, latest
authoritative-class retrieval, and approved-catalog controls in J2/J3
review UI.

Implemented behavior:

- strict PUT route requires exact positive floor-plan, processing-job,
  detection, and `symbol_legend_id` values. Ownership and reviewer identity are
  derived from authenticated local database user.
- Only active database legend may be selected. Missing/inactive choices
  return sanitized `409`; Admins and unsupported roles receive `403`; missing,
  mismatched, and cross-owner detection contexts share `404`.
- Each real correction appends immutable positive sequence with old/new
  class ID/name snapshots and nullable legend references. Identical selection
  is idempotent. Returning to original AI class restores its authority
  without deleting prior correction history.
- J1 returns immutable `original_class`, latest `authoritative_class`, and a
  nullable latest correction summary loaded through one separate bulk query.
- J3 confirmation/rejection remains independent: correction does not change a
  review decision, and review does not change classification history.
- I4 same-job replacement is rejected when review or correction history exists,
  including attempted empty replacement. Other job versions remain isolated.
- frontend loads active legend catalog, presents loading/error/empty
  states, disables no-op and duplicate saves, preserves selection and geometry,
  keeps rejected results visible, and announces safe outcomes accessibly.
- J4 adds no production legend seed, Admin catalog mutation, J5 manual symbol,
  dragging, canonical geometry, worker orchestration, model run, or new
  dependency. PRE7 later implements Admin legend management without changing J4.

**Acceptance Criteria:**

- [x] User can choose valid symbol class from approved legend library.
- [x] Corrected class persists.
- [x] Correction records old and new values.
- [x] corrected value becomes authoritative review value for later layout work.
- [x] Original AI class remains available for accuracy evaluation.

---

### TICKET J5 — Add Missing Symbol Manually

**Goal:** Add components model did not detect.

**Dependencies:** J2.

**Implementation status:** Complete. J5 adds twelfth prototype table,
`manual_symbols`, and owner-scoped Designer POST endpoint. Manual placement
uses active approved legend and stores its immutable class snapshot,
authenticated creator provenance, `manually_added` status, and source-pixel
center validated against exact existing J1A normalized RGB PNG. A
client-generated UUID makes retries idempotent, while conflicting reuse is
rejected. J1 returns manual records separately from AI detections, and I4
protects job version containing manual symbols from replacement. A tested
renderer-independent handoff combines confirmed detections using their J4
authoritative classes with manual symbols for K1. The approved catalog remains
empty until VED supplies production class data; UI disables placement in
that state. J5 does not implement K1 canonical geometry, 3D, routing,
quantities, estimates, or reports.

**Acceptance Criteria:**

- [x] User can choose valid symbol class.
- [x] User can place symbol on 2D plan.
- [x] Manual symbol is marked as manually added.
- [x] Symbol persists after reload.
- [x] Manual symbols enter authoritative K1 handoff for later 3D, routing,
  and quantity work. Actual downstream modules remain unimplemented and were
  not executed by J5.

---

## Epic K — Canonical Geometry and 2D Layout

### TICKET K1 — Define Canonical Geometry Schema

**Goal:** Establish shared domain model used by 2D, 3D, routing, and estimation.

**Dependencies:** H2, J5.

**Implementation status:** Complete. K1 defines immutable schema version 1 for
one project floor and its source-plan coordinate plane. Pure backend and
frontend validators agree through one shared JSON fixture. H2 canonical walls
and ordered J5 authoritative symbols map into document; rooms and minimal
elevated route points are representable. Floor elevation is supplied explicitly
and is not inferred or stored in `project_floors`. See `docs/geometry.md`.
K1 adds no API operation or table, layout snapshot, editor, renderer, routing
algorithm, quantity, estimate, or report implementation. K2 supplies the
snapshot persistence described in these ticket.

**Acceptance Criteria:**

- [x] Schema defines coordinate system and unit.
- [x] Walls are represented.
- [x] Rooms can be represented.
- [x] Symbols are represented.
- [x] Routes can be represented.
- [x] Floor/elevation association is represented.
- [x] Schema is documented in `docs/geometry.md`.
- [x] Frontend and backend agree on field names/types.

---

### TICKET K2 — Create Layout Snapshot/Version Model

**Goal:** Preserve verified layout state.

**Dependencies:** K1.

**Implementation status:** Complete. K2 adds thirteenth prototype table,
`layout_versions`, and backend-only repository/service boundary. Each row
stores one complete validated K1 schema-v1 document with project, floor, and
source-plan references, positive per-floor sequential version, server
timestamp, and nullable `TRUE`/`NULL` current marker. Saving locks the
project-floor row and atomically preserves history while making new version
current. An older version may later become current without changing its stored
geometry or timestamp. Database constraints enforce unique floor/version and
one current row per floor. Reconstruction rejects corrupt or mismatched stored
JSON. K2 adds no HTTP operation, original-file mutation, editor, renderer,
routing, estimate, or report behavior. K3 exposes this service without changing
those persistence guarantees.

**Acceptance Criteria:**

- [x] Layout version references project/floor.
- [x] Version number or timestamp is stored.
- [x] Verified walls and symbols can be reconstructed from version.
- [x] Saving new layout does not silently destroy previous version if versioning is enabled.
- [x] One version can be marked current/authoritative.

---

### TICKET K3 — Create 2D Layout API

**Goal:** Load and save authoritative 2D layout.

**Dependencies:** K2.

**Implementation status:** Complete. K3 adds exactly `GET` and `POST`
`/api/projects/{project_id}/floors/{project_floor_id}/layouts`. `GET` returns
current complete K2 snapshot to owning Designer or Admin. `POST`
accepts exact complete strict K1 canonical document from owning
Designer, validates its path and persisted-floor identity, and creates next
append-only K2 version. Missing, inaccessible, and cross-context resources use
same non-disclosing `LAYOUT_NOT_FOUND` response. Semantic geometry failures
use `INVALID_LAYOUT_GEOMETRY`, and persistence failures are sanitized. No
history/current-selection API, editor, renderer, schema change, or floor-plan
file mutation is introduced. K4 consumes this current-layout `GET` without
changing K3 contract.

**Acceptance Criteria:**

- [x] `GET /api/projects/{id}/layouts` or documented equivalent returns current layout data.
- [x] Save/update endpoint validates geometry.
- [x] Backend remains source of truth.
- [x] Invalid coordinates produce validation error.
- [x] Saving 2D layout does not modify original blueprint file.

---

### TICKET K4 — Build Konva Layer Architecture

**Goal:** Implement stable 2D rendering layers.

**Dependencies:** K3.

**Implementation status:** Complete. K4 adds protected current-layout hash
route and project-floor navigation, strict credentialed K3 `GET` client, and
responsive read-only React-Konva source plane derived exclusively from the
deeply frozen K1 document. Blueprint, walls, rooms, symbols, wiring/conduit
previews, and empty selection/editing UI are six separate always-mounted
layers in that exact order. Accessible checkboxes change only each layer's
`visible` presentation property and never modify canonical arrays or call K3
`POST`.

existing J1A image is requested only when all non-null canonical wall and
symbol provenance resolves to exactly one positive safe processing-job ID. The
decoded image must exactly match canonical pixel dimensions. Missing or
mixed provenance, fetch/decode failure, or dimension mismatch retains neutral
blueprint layer and accessible warning. Guaranteed aligned-image display for
source-less/mixed snapshots requires later explicit blueprint-source contract;
K4 does not change K1-K3 or database to solve that limitation.

**Acceptance Criteria:**

- [x] Blueprint is on its own layer.
- [x] Walls are on their own layer.
- [x] Symbols are on their own layer.
- [x] Wiring/conduit layer exists even if routing is not implemented yet.
- [x] Selection/editing UI is separated from project geometry.
- [x] Toggling one layer does not delete its data.

---

### TICKET K5 — Implement Symbol Move/Edit in 2D

**Goal:** Allow verified symbols to be repositioned.

**Dependencies:** K4.

**Implementation status:** Complete. K5 makes confirmed detected and manually
added canonical symbols selectable on six-layer Konva canvas and in an
accessible inspector. Owning Designers may drag or enter bounded X/Y meter
coordinates; Admins remain inspection-only. Edits update immutable complete
K1 draft and explicit save posts that document through existing K3 route,
creating new append-only K2 version whose server response becomes current
local state. Cancel restores last server snapshot without POST. Walls,
rooms, routes, scale, floor identity/elevation, symbol class/status/provenance,
deletion, resize/rotation, undo/redo, 3D, and routing remain outside K5.

PRE8 adds expected-version and UUIDv4 envelope to K3 save. The server
locks and compares authoritative current floor version, rejects stale saves
with sanitized `409`, and uses `layout_save_requests` to return original
result for identical retry without another K2 version. Conflicting UUID
reuse is `409`; K5 retains same UUID across uncertain reconciliation and
retry.

**Acceptance Criteria:**

- [x] User can select symbol.
- [x] User can move symbol.
- [x] Updated canonical coordinate is saved.
- [x] Reload shows saved position.
- [x] Position is not stored only in Konva-specific state.
- [x] Later 3D rendering can consume same coordinate.

---

## Epic L — 3D Reconstruction

### TICKET L1 — Initialize Three.js / React Three Fiber Viewer

**Goal:** Create empty interactive 3D scene.

**Dependencies:** A3.

**Implementation status:** Complete. L1 adds protected hash route
`#/app/projects/{project_id}/floors/{project_floor_id}/viewer-3d`, exposed from
Designer and Admin floor controls even when no upload or layout snapshot exists.
lazily loaded JavaScript viewer uses `three@0.185.1` and
`@react-three/fiber@9.7.0`, perspective camera, neutral grid/axes helpers,
demand rendering, and direct Three.js OrbitControls with local cleanup and
saveState/reset behavior. It makes no floor-plan, detection, processing-job, or
layout request. The helpers are not project geometry. Top/perspective switching
and all canonical floor, wall, opening, symbol, and route rendering remain later
work.

L1 verification covers 40 focused route/navigation/viewer regressions. Current
PRE11 verification covers 280 frontend tests across 30 files, 627
`unittest`-discovery tests, 667 combined pytest tests plus 504 subtests, and a
separate 40-test canonical-geometry pytest suite.

**Acceptance Criteria:**

- [x] 3D scene loads without floor-plan data.
- [x] Orbit works.
- [x] Pan works.
- [x] Zoom works.
- [x] Reset view works.
- [x] Viewer failure does not crash unrelated dashboard pages.

---

### TICKET L2 — Render Floor from Canonical Geometry

**Goal:** Generate floor plane from project geometry.

**Dependencies:** K1, L1.

**Acceptance Criteria:**

- [x] Floor dimensions come from canonical geometry.
- [x] Scene does not use hard-coded demo dimensions.
- [x] Scale matches documented coordinate system.
- [x] Floor alignment can be compared against 2D plan.

L2 checkpoint (2026-09-19): metric source-plane dimensions and room surfaces
reuse demo canonical renderer. Shape projection is isolated and tested;
viewer links to saved 2D layout and identifies image extent versus
room boundaries. K1 reads accept U11's additive extension metadata without
rendering unvalidated extension entities. No API/schema/database changes.

---

### TICKET L3 — Extrude Walls from 2D Geometry

**Goal:** Generate 3D wall meshes from canonical wall data.

**Dependencies:** H3, L2.

**Acceptance Criteria:**

- [x] Every rendered wall comes from stored wall geometry.
- [x] Wall start/end positions align with 2D coordinates.
- [x] Wall height is configurable or stored.
- [x] Wall thickness is configurable or stored.
- [x] Walls are not manually recreated separately in Three.js.

L3 checkpoint (2026-09-19): only verified, nonzero walls are extruded using
stored metric height/thickness. Missing dimensions on rendered wall block
metric rendering; unverified/zero-length walls are omitted with visible count.
Horizontal, vertical and reversed diagonal mesh endpoints are tested against
canonical coordinates at negative floor elevation. No schema or data changes.

---

### TICKET L4 — Render Electrical Symbols in 3D

**Goal:** Place verified electrical components in 3D scene.

**Dependencies:** J5, L3.

**Acceptance Criteria:**

- [x] Verified symbols appear in 3D.
- [x] Deleted/rejected symbols do not appear.
- [x] Manually added symbols appear.
- [x] Symbol position derives from canonical geometry.
- [x] Moving symbol in 2D changes its 3D position after synchronization/reload.

L4 checkpoint (2026-09-19): confirmed/manual canonical symbols retain class,
identity and review status in scene and its readable inventory. Strict K1
validation rejects unreviewed/deleted/rejected symbols; removed records render
no marker. Positions remain floor-plan markers at floor elevation, with no
invented mounting heights or device specifications. Coordinate/status tests
cover changed saved positions, manual symbols and invalid review states.

---

### TICKET L5 — Add 2D/3D View Synchronization

**Goal:** Keep both visualizations based on one project model.

**Dependencies:** K5, L4.

**Acceptance Criteria:**

- [x] 2D and 3D consume same authoritative geometry data.
- [x] Editing object does not create second unrelated 3D-only record.
- [x] Reloading both views shows same saved project state.
- [x] Coordinate transform logic is isolated and tested.

L5 checkpoint (2026-09-19): both views load same versioned K1 endpoint.
Explicit 3D reload replaces scene, fences old floor requests and clears
stale geometry on failure. The 2D link requires saved/discarded edits.
Focused viewer/editor/API tests: 69 PASS. No new persistence/API/table.
Full frontend regression: 347 tests across 39 files PASS; lint/build/diff PASS.
Build retains existing >500 kB chunk warning. Backend regression was not
rerun for frontend-only changes; frontend and backend health HTTP checks PASS.
U11 extended snapshots are displayed as base geometry and kept read-only in
K1 editor to avoid losing extension data; edit them through interpretation
review. Openings/panels/observed-route rendering is outside L2-L5 criteria.
Browser visual acceptance remains manual; automated scene/UI tests use fixtures.

---

## Epic M — Spatial Routing

### TICKET M1 — Define Routing Data Model

Implementation checkpoint: `app/routing/contracts.py` defines explicit panel
placement, canonical target identity, floor/version references, aligned metric
offsets, service elevation, bounded obstacles and explicit risers. Generated
routes contain ordered points and typed segments with separate horizontal and
vertical meters. No automatic mounting heights, allowances or engineering
approval are inferred. Contract tests: 2 PASS (2026-09-19).

**Goal:** Define panels, route points, route segments, and route types.

**Dependencies:** K1.

**Acceptance Criteria:**

- [x] Electrical panel can be represented.
- [x] Route contains ordered points/segments.
- [x] Horizontal and vertical distance can be represented separately.
- [x] Floor/elevation is supported.
- [x] Route type can distinguish ceiling/service-level and wall-embedded movement.
- [x] Model is documented.

---

### TICKET M2 — Build Navigable Routing Graph

Implementation checkpoint: bounded orthogonal graph in `app/routing/graph.py`,
exact endpoint anchors, deterministic adjacency, conservative wall bounds and
closed-segment obstacle checks. Missing wall review and resource limits fail
closed. Cumulative routing tests: 5 PASS (2026-09-19).

**Goal:** Convert building geometry into A*-compatible graph.

**Dependencies:** M1, H3.

**Acceptance Criteria:**

- [x] Graph generation is independent of Three.js.
- [x] Walls/obstacles restrict invalid paths.
- [x] Electrical panel and target devices can be mapped to graph nodes.
- [x] Graph generation has deterministic tests for small sample layout.

---

### TICKET M3 — Implement Basic A* Routing

Implementation checkpoint: deterministic A*, known shortest-path and obstacle
detour tests, controlled `NO_ROUTE` without fallback shortcuts. Cumulative
routing tests: 7 PASS (2026-09-19).

**Goal:** Compute valid path from panel to target device.

**Dependencies:** M2.

**Acceptance Criteria:**

- [x] A* returns ordered route.
- [x] Route avoids configured structural obstacles.
- [x] No-path cases return controlled error/result.
- [x] Algorithm has unit tests using known graphs.
- [x] Route result is independent of visual rendering.

---

### TICKET M4 — Add Ceiling-Level Horizontal Routing Rule

Engine checkpoint: configured absolute service elevation, typed horizontal
segments, exact saved target matching and backend distances. Cumulative routing
tests: 8 PASS. Display/manual acceptance is pending M7 integration.

**Goal:** Apply project-specific routing rule for cross-room/horizontal movement.

**Dependencies:** M3.

**Acceptance Criteria:**

- [x] Horizontal routing uses configured ceiling/service elevation where required.
- [x] Route metadata identifies ceiling-level segments.
- [x] Cross-room routes do not use arbitrary diagonal lines through open space when rule-based routing applies.
- [x] Behavior is configurable/documented.
- [ ] Sample routing case can be manually verified in 3D.

---

### TICKET M5 — Add Wall Vertical Drop/Rise Rule

Engine checkpoint: explicit wall attachment, height/position checks, typed
rise/drop segments and vertical distance totals. User obstacles apply along
vertical segments. Cumulative tests: 10 PASS; display awaits M7.

**Goal:** Route from ceiling/service level to wall-mounted devices.

**Dependencies:** M4.

**Acceptance Criteria:**

- [x] Vertical drop/rise segments are represented explicitly.
- [x] Vertical segment follows associated wall path where applicable.
- [x] Vertical distance contributes to total wire/conduit length.
- [x] Route is visible correctly in 3D.
- [x] Route output contains segment type/elevation metadata.

---

### TICKET M6 — Add Multi-Floor Vertical Routing

Engine checkpoint: explicitly aligned per-floor graphs join only through named
risers. Floor transitions and connector identity persist in generated segment
data; obstacle checks cover vertical span. Missing/blocked risers produce
NO_ROUTE. Cumulative routing tests: 12 PASS (2026-09-19).

**Goal:** Support risers or vertical connectors between floors.

**Dependencies:** M5, B5.

**Acceptance Criteria:**

- [x] Route can reference multiple floors.
- [x] Vertical connector/riser is explicitly represented.
- [x] Elevation difference contributes to total length.
- [x] Floor transition is visible in route data.
- [x] Missing vertical connector produces controlled no-route result rather than impossible shortcut.

---

### TICKET M7 — Persist and Display Routes

Implementation checkpoint (2026-09-19): generated route versions are stored in
`generated_route_versions`, pinned to existing canonical layout IDs. Designer
POST and authorized GET `/api/projects/{project_id}/routes` use service/repository
boundaries. Floor locks recheck source versions before persistence. Recalculation
appends version; stale results are identified and not drawn as current.
Konva and Three.js project same stored segments; UI totals come from Python.
3D workspace offers single-floor generation controls; multi-floor and
additional obstacle configuration are supported through typed API.

M1-M7 implementation criteria PASS by contract, engine, persistence, access and
projection tests; manual 3D visual acceptance NOT TESTED. Focused backend final:
114 PASS + 61 subtests. Full backend run: 938 PASS, 4 FAIL, 4 skipped; all four
failures were outdated API/table inventories, corrected and passed in final
focused run. Full frontend: 348 PASS; two routing tests PASS after final test/
projection additions; lint/build PASS. No claim of clean rerun of entire
backend suite. Existing dependency deprecations and large frontend chunk warning
remain. API operations: 39; tables: 28. Local route table initialized additively;
original uploads and existing rows preserved. No N-series work started.

**Goal:** Save routing results and show them in 2D/3D.

**Dependencies:** M6, L5.

**Acceptance Criteria:**

- [x] Routes are stored in database.
- [x] Route segments reload without recomputation.
- [x] 2D shows route overlay.
- [x] 3D shows horizontal and vertical route segments.
- [x] Route length displayed in UI matches backend calculation.
- [x] Route recalculation creates clear updated state/version.

---

## Epic N — Material Quantification

### TICKET N1 — Create Material Catalog Schema

**Goal:** Store company materials independently from estimates.

**Dependencies:** B2.

**Acceptance Criteria:**

- [x] `materials` table exists.
- [x] Material code/name is supported.
- [x] Unit is supported.
- [x] Category is supported.
- [x] Active/inactive state is supported.
- [x] Prices are not hard-coded in frontend or routing code.

N1: Added an independent catalog model with a unique code, bounded required
name/unit/category, active state, and timestamps. Isolated MySQL tests verify
idempotent table creation, persistence, deactivation, and duplicate rejection.
No prices, official catalog seed values, API, or UI were added. Development
database initialization remains pending; rollback can retain the unused table.

---

### TICKET N2 — Create Material Pricing and History Schema

**Goal:** Track current and historical material prices.

**Dependencies:** N1.

**Acceptance Criteria:**

- [x] Material price can be updated.
- [x] Previous price remains available in price history.
- [x] Effective date/time is stored.
- [ ] Updating price does not rewrite existing estimate item prices.
- [x] Admin identity can be associated with change.

N2: Append-only `material_prices` revisions retain exact decimal prices,
currency, unit, effective UTC time, and the authenticated Admin identity.
Updates lock the material and append a monotonic revision; exact retries are
no-ops. Backdated changes before the latest revision and future-effective
prices are explicitly rejected. Current price and history are repository reads.
Historical-estimate verification remains pending O1; no estimate tables exist yet.
P2 owns the public price-update API. No official prices were seeded.

---

### TICKET N3 — Implement Component Quantity Calculation

**Goal:** Count verified electrical symbols by type.

**Dependencies:** J5, K2.

**Acceptance Criteria:**

- [x] Confirmed symbols are counted.
- [x] Corrected symbols use corrected classification.
- [x] Manually added symbols are counted.
- [x] Deleted/rejected symbols are excluded.
- [x] Quantity results are reproducible from authoritative layout.

N3: Backend quantities consume saved canonical symbols, not detector output.
Canonical classification already includes approved corrections. Invalid review
states and duplicate symbol identities are rejected rather than counted.
Results retain layout version, class identity, and contributing symbol IDs.

---

### TICKET N4 — Implement Wire and Conduit Length Calculation

**Goal:** Convert route geometry into material lengths.

**Dependencies:** M7.

**Acceptance Criteria:**

- [x] Horizontal route distance is included.
- [x] Vertical route distance is included.
- [x] Multi-floor/riser distance is included.
- [x] Units are consistent.
- [x] Calculation is performed in backend domain/service code.
- [x] Test case with known route coordinates returns expected length.

N4: Backend measurements recompute the latest saved generated route from its
ordered metric segments, reject stale routes and inconsistent geometry/totals,
and retain route/layout identities. Base conduit length is the geometric run;
wire length requires an explicit conductor count. No waste, termination slack,
wire sizing, fittings, or company conversion factors are inferred. This is one
saved route, not a complete building takeoff or an estimate API.

---

## Epic O — Cost Estimation

### TICKET O1 — Create Estimate and Estimate Items Schema

**Goal:** Persist estimate snapshots.

**Dependencies:** N1, N2.

**Acceptance Criteria:**

- [x] `estimates` table exists.
- [x] `estimate_items` table exists.
- [x] Estimate references project.
- [x] Each item stores quantity, unit, captured unit price, and line total.
- [x] Historical estimates are not silently changed by later price updates.
- [x] estimate models and constraints can be created successfully in current MySQL development schema.

O1: Additive estimate/header and item snapshot tables retain project version,
actor, currency, date, material labels, quantity, unit, captured price, and totals.
Exact decimal storage does not introduce a rounding or generation policy.
Isolated tests verify persistence, constraints, and preservation after price and
catalog edits. Development schema creation passed without inserting test data.
O2 owns generation, calculation policy, and source-version capture; no API or UI
is introduced in O1. Rollback may retain the unused additive tables.

---

### TICKET O2 — Implement Estimate Generation Service

**Goal:** Generate Bill of Materials from authoritative project data.

**Dependencies:** N3, N4, O1.

**Acceptance Criteria:**

- [ ] Service uses verified component quantities.
- [ ] Service uses calculated route lengths.
- [ ] Service reads prices from database.
- [ ] Line total equals quantity × captured unit price.
- [ ] Grand total equals sum of item totals plus only explicitly configured additions.
- [ ] Missing required price produces clear validation/result state.

---

### TICKET O3 — Create Estimate API

**Goal:** Expose estimate generation and retrieval.

**Dependencies:** O2.

**Acceptance Criteria:**

- [ ] Generate estimate endpoint exists.
- [ ] Get estimate endpoint exists.
- [ ] Unauthorized access is rejected.
- [ ] Response contains itemized quantities, unit prices, line totals, and total.
- [ ] Reopening old estimate returns its stored price snapshot.

---

### TICKET O4 — Build Estimate UI

**Goal:** Present Bill of Materials and cost summary.

**Dependencies:** O3.

**Acceptance Criteria:**

- [ ] Material rows display quantity, unit, unit price, and line total.
- [ ] Total matches backend response.
- [ ] UI does not recalculate hidden alternative prices.
- [ ] Missing-price warnings are visible.
- [ ] User can distinguish estimate version/date.

---

## Epic P — Admin Management

### TICKET P1 — Material Catalog Admin API

**Goal:** Allow Admin to manage materials.

**Dependencies:** C4, N1.

**Acceptance Criteria:**

- [ ] Admin can list materials.
- [ ] Admin can add material.
- [ ] Admin can edit allowed fields.
- [ ] Designer cannot change material catalog.
- [ ] Validation prevents invalid units/prices where applicable.

---

### TICKET P2 — Material Price Update API

**Goal:** Allow Admin to update official company prices.

**Dependencies:** P1, N2.

**Acceptance Criteria:**

- [ ] Only Admin can update prices.
- [ ] Price history is created.
- [ ] Current material price updates correctly.
- [ ] Existing estimates remain unchanged.
- [ ] Price update action is audit-ready.

---

### TICKET P3 — Symbol Legend Admin API

**Goal:** Manage approved symbol classes/reference information.

**Dependencies:** C4, I4.

**Implementation status:** Complete through PRE7. Admins have safe all-status
retrieval, creation, and full class/name/active-state revision. Normalized class
IDs and names remain unique and case-sensitive. Every real change appends an
actor/time and old/new snapshot to `symbol_legend_history`; no-op retries append
nothing. Deactivation performs no delete and does not rewrite dependent history.
No production class or private glyph/reference file is seeded or returned. P4
still owns future management UI.

**Acceptance Criteria:**

- [x] Admin can list symbol legends.
- [x] Admin can activate/deactivate supported legend records.
- [x] Designer cannot modify legend library.
- [x] Existing detections remain referentially valid when legend is deactivated.
- [x] Model class mapping behavior is documented.

---

### TICKET P4 — Build Admin Management UI

**Goal:** Provide interfaces for material and symbol maintenance.

**Dependencies:** P1, P2, P3.

**Acceptance Criteria:**

- [ ] Admin sees material management.
- [ ] Admin can update material price.
- [x] Admin sees symbol legend management.
- [x] Designer does not receive Admin controls.
- [x] Backend still rejects unauthorized direct API attempts.

---

## Epic Q — PDF Reporting

### TICKET Q1 — Define Report Data Contract

**Goal:** Freeze what data generated report uses.

**Dependencies:** O3, K2.

**Acceptance Criteria:**

- [ ] Contract includes project metadata.
- [ ] Contract includes layout/detection summary.
- [ ] Contract includes route lengths.
- [ ] Contract includes Bill of Materials.
- [ ] Contract includes estimate totals.
- [ ] Contract references specific estimate version.
- [ ] Report generation does not depend on current prices changing afterward.

---

### TICKET Q2 — Implement PDF Report Generator

**Goal:** Generate project estimation PDF from stored data.

**Dependencies:** Q1.

**Acceptance Criteria:**

- [ ] PDF is generated successfully from completed estimate.
- [ ] Project information is displayed.
- [ ] Material quantities are displayed.
- [ ] Unit prices and totals are displayed.
- [ ] Report identifies generation date and prepared-by user.
- [ ] Output uses planning/estimation language rather than representing report as automatically approved engineering document.
- [ ] Generated PDF is stored outside original upload directory.

---

### TICKET Q3 — Create Report API

**Goal:** Generate and retrieve reports.

**Dependencies:** Q2.

**Acceptance Criteria:**

- [ ] Generate report endpoint exists.
- [ ] Report metadata is persisted.
- [ ] Download/retrieval endpoint exists.
- [ ] Authorization is enforced.
- [ ] Re-downloading report does not recalculate estimate using newer prices.

---

### TICKET Q4 — Build Report UI

**Goal:** Allow users to generate and access reports.

**Dependencies:** Q3.

**Acceptance Criteria:**

- [ ] User can generate report from eligible project/estimate.
- [ ] Report generation status is visible.
- [ ] User can download/open generated PDF.
- [ ] Previous generated reports can be identified by date/version.
- [ ] Report errors are shown clearly.

---

## Epic R — Audit Logging

### TICKET R1 — Create Audit Log Schema and Service

**Goal:** Record important user/system actions.

**Dependencies:** B3.

**Acceptance Criteria:**

- [ ] `audit_logs` table exists.
- [ ] Log records user, action, entity type, entity ID, timestamp, and safe details.
- [ ] Audit service is reusable across modules.
- [ ] Sensitive credentials/secrets are never written into audit details.

---

### TICKET R2 — Log Core Workflow Actions

**Goal:** Add audit events to important features.

**Dependencies:** R1 and relevant completed feature tickets.

**Acceptance Criteria:**

- [ ] Login can be logged.
- [ ] Project creation is logged.
- [ ] Floor plan upload is logged.
- [ ] AI analysis start/completion/failure can be logged.
- [ ] Symbol corrections/additions/removals are logged.
- [ ] Route recalculation is logged.
- [ ] Material price update is logged.
- [ ] Estimate generation is logged.
- [ ] Report generation is logged.

---

### TICKET R3 — Admin Audit Log Viewer

**Goal:** Allow Admin to inspect audit history.

**Dependencies:** R2, C4.

**Acceptance Criteria:**

- [ ] Admin can retrieve audit records.
- [ ] Designer cannot access unrestricted audit history.
- [ ] Basic filtering by action/user/date is supported or clearly deferred.
- [ ] Audit details do not expose secrets or raw stack traces.

---

## Epic S — Testing and Validation

### TICKET S1 — Backend Unit Test Foundation

**Goal:** Configure isolated backend testing.

**Dependencies:** A4.

**Acceptance Criteria:**

- [ ] `pytest` test suite runs.
- [ ] Test configuration is separated from production configuration.
- [ ] At least one service-level unit test exists.
- [ ] Test failures return non-zero process status.
- [ ] Testing command is documented.

---

### TICKET S2 — API Integration Test Foundation

**Goal:** Verify FastAPI endpoint behavior.

**Dependencies:** S1, C2.

**Acceptance Criteria:**

- [ ] Test client can call FastAPI routes.
- [ ] Authentication success case is tested.
- [ ] Authentication failure case is tested.
- [ ] Protected route behavior is tested.
- [ ] Tests do not require manually clicking UI.

---

### TICKET S3 — AI Detection Evaluation Dataset Runner

**Goal:** Compare local multimodal interpretations and legacy YOLO baseline
against independently verified ground truth.

**Dependencies:** U5, U8, U11; I3/I4 for legacy comparison while retained.

**Acceptance Criteria:**

- [ ] Evaluation accepts defined test dataset.
- [ ] Symbol count, class, box/center, wall/room geometry, scale, and observed wiring can be compared against approved truth.
- [ ] Per-class and per-drawing-set results can be produced.
- [ ] Model, adapter, prompt, reference pack, decoding settings, and any legacy confidence threshold are recorded.
- [ ] Hallucination, malformed-schema, latency, RAM, and VRAM results are reported.
- [ ] Evaluation results can be exported or documented for thesis analysis.

---

### TICKET S4 — 2D-to-3D Alignment Tests

**Goal:** Verify geometry transformations.

**Dependencies:** L5.

**Acceptance Criteria:**

- [ ] Known 2D wall coordinate maps to expected 3D position.
- [ ] Known symbol coordinate maps to expected 3D position.
- [ ] Scale conversion is tested.
- [ ] Coordinate transform tests run without requiring manual 3D interaction.

---

### TICKET S5 — Routing Length Tests

**Goal:** Verify horizontal and vertical route measurements.

**Dependencies:** M6.

**Acceptance Criteria:**

- [ ] Horizontal length test exists.
- [ ] Vertical drop/rise test exists.
- [ ] Multi-floor vertical test exists.
- [ ] Total route length matches expected values within documented tolerance.
- [ ] No-path behavior is tested.

---

### TICKET S6 — Cost Calculation Tests

**Goal:** Verify estimate accuracy.

**Dependencies:** O2.

**Acceptance Criteria:**

- [ ] Quantity × unit price is tested.
- [ ] Multiple line items are tested.
- [ ] Grand total is tested.
- [ ] Historical estimate price snapshot behavior is tested.
- [ ] Missing-price behavior is tested.

---

## Epic T — Deployment and Documentation

### TICKET T1 — Development Setup Documentation

**Goal:** Make repository reproducible for another developer.

**Dependencies:** Core foundation complete.

**Acceptance Criteria:**

- [ ] Required Node.js version is documented.
- [ ] Required Python version is documented.
- [ ] XAMPP-based MySQL local-development setup is documented, including starting MySQL and creating/inspecting `ved_electrical` (`phpMyAdmin` may be used optionally).
- [ ] Frontend install/run commands are documented.
- [ ] Backend install/run commands are documented.
- [ ] SQLAlchemy development schema initialization/reset procedure is documented.
- [ ] Environment setup is documented.
- [ ] No undocumented manual secret is required to start local development.

---

### TICKET T2 — Docker Development Setup

**Goal:** Provide optional reproducible containerized local services.

**Dependencies:** B1, A3, A4.

**Acceptance Criteria:**

- [ ] `docker-compose.yml` is valid.
- [ ] Required database service starts.
- [ ] Backend can connect to containerized database.
- [ ] Persistent database volume is configured.
- [ ] Environment variables are not hard-coded with production secrets.

---

### TICKET T3 — Production Deployment Checklist

**Goal:** Document deployment requirements without silently assuming hosting provider.

**Dependencies:** MVP features complete.

**Acceptance Criteria:**

- [ ] Frontend deployment requirements are documented.
- [ ] FastAPI deployment requirements are documented.
- [ ] MySQL database requirements are documented.
- [ ] Persistent file/object storage requirements are documented.
- [ ] Environment/secrets management is documented.
- [ ] HTTPS and CORS requirements are documented.
- [ ] Backup requirements for database and generated project files are documented.

---

## Epic PRE — Pre-VLM Application Foundations

`docs/PRE_VLM_FOUNDATION_PLAN.md` is normative evidence, scope, acceptance,
verification, publication, and reporting plan for PRE0-PRE12. The ready-to-paste
implementation authorization is in `docs/CODEX_PRE_VLM_FOUNDATION_PROMPT.md`.
These tickets do not install or run local model and do not retire YOLO.

| Ticket | Goal | Required result before next ticket |
|---|---|---|
| PRE0 (complete) | Publish documentation/privacy baseline | Maintained docs and ignore rules are consistent, no private/model artifact is tracked, feature and main are published |
| PRE1 (complete) | Floor-plan discovery API | Authorized persisted plans are reload-discoverable without storage-path disclosure |
| PRE2 (complete) | Processing-job history API | Safe bounded job summaries recover job IDs/status after reload |
| PRE3 (complete) | Reload-safe project workspace | Persisted plans/jobs render and active monitoring resumes without session-only state |
| PRE4 (complete) | Immutable source/page identity | Original SHA-256 and one-based raster/PDF page records are persisted atomically |
| PRE5 (complete) | Processing-artifact manifest | Every trusted derived image has exact job/page/type/path/hash/dimension provenance |
| PRE6 (complete) | Approved elevation and scale | Explicit reviewed metric inputs are persisted without inferred defaults |
| PRE7 (complete) | Symbol-legend administration | Admin can safely manage existing catalog without guessed seed data or history loss |
| PRE8 (complete) | Conditional/idempotent layout save | Stale saves and duplicate retry versions are rejected or reconciled deterministically |
| PRE9 (complete) | Processing execution controls | Claim/lease/heartbeat/cancel/recovery primitives exist without running AI pipeline |
| PRE10 (complete) | Dataset-approver authority | Active human VED approver assignment is auditable and privacy-bounded |
| PRE11 (complete) | Canonical compatibility decision | K1 v1 history is preserved and future page/opening/panel/route provenance ownership is frozen |
| PRE12 (complete) | Readiness gate | Full functional, schema, storage, privacy, documentation, and Git evidence permits U1 |

Every PRE ticket inherits detailed acceptance criteria in pre-foundation
plan. Each uses separate feature branch and progress report. PRE12 must stop
before U1.

PRE0-PRE12 are complete. PRE1 adds read-only floor-plan discovery, PRE2 adds
bounded read-only processing-job history, and PRE3 reconciles both in the
workspace without new table or backend operation. PRE4 adds two private
source/page tables and verification-first backfill. PRE5 adds one private
derived-artifact manifest table and exact J1A provenance resolution. PRE6 adds
append-only reviewed metric settings and three safe operations. PRE7 adds the
Admin legend API and append-only change history. PRE8 adds conditional,
idempotent layout-save contract and one request-record table. PRE9 adds two
execution-control tables and one owning-Designer cancellation operation without
running worker or AI pipeline. PRE10 adds history-preserving, Admin-managed
human authority assignment and privacy-reduced current-assignment read. It
rejects Admin self-assignment and creates no review decision. PRE11 accepts
`docs/decisions/0001-canonical-geometry-compatibility.md`: K1 version 1 stays
strict and readable, evidence remains in candidate/review records, and version
2 is reserved as separately implemented additive canonical extension attached
to new version-1 snapshot. PRE12 publishes passing gate in
`docs/PRE_VLM_READINESS_REPORT.md`; U1 and U2 candidate contract are
complete, but no model/runtime work has started.

---

## Epic U — Local Multimodal Floor-Plan AI Migration

`docs/LOCAL_VLM_MIGRATION_PLAN.md` contains normative rationale, data
levels, candidate contract, metrics, privacy boundary, ticket details, and Git
publication protocol. `docs/CODEX_U_VLM_MIGRATION_PROMPT.md` consolidates the
complete U1-U14 execution instructions. One explicit authorization may cover
all fourteen tickets, each separately implemented, tested, committed, merged,
pushed, and reported. No U ticket is implemented by this documentation update.

migration plan's execution clarifications are binding scope details:
U5 provides offline bootstrap review/import path; U6 selects on development
validation, not sealed final test data; U9 persists minimum candidate/review
history before U11 extends it. U11 implements PRE11 additive extension and
PRE8-safe saving without modifying K1 v1 or dropping extension data during edits.
U13 reuses PRE9 execution fencing. Missing approved data, authority, or hardware
is real gate, not permission to substitute mock evidence. U14 ends this sequence;
L2+, generated routing, quantities, estimates, and reports remain out of scope
for that full U-only sequence. The September 9 demo amendment separately
authorizes minimum L2-L5 visualization work before full migration;
generated routing, quantities, estimates and reports are still excluded.

### TICKET U1 — Freeze Hardware, Privacy, and Runtime Requirements

**Goal:** Measure target machine and approve local-only boundary before
choosing or downloading model.

**Dependencies:** PRE12 passing readiness gate; current L1 implementation
baseline.

**Acceptance Criteria:**

- [x] CPU, RAM, GPU, VRAM, OS, driver/CUDA, disk, and supported deployment environment are measured.
- [x] Page, tile, context, latency, timeout, concurrency, and storage budgets are approved.
- [x] Local-only prohibits source upload, hosted inference, telemetry, and silent network fallback.
- [x] Model-license and permitted training/deployment policies are recorded.
- [x] No model is selected or downloaded in U1.

---

### TICKET U2 — Define Floor-Plan Interpretation Candidate Schema v1

**Goal:** Freeze advisory model-output boundary before model selection.

**Dependencies:** U1, K1.

**Acceptance Criteria:**

- [x] Strict candidate data covers source/model provenance, page metadata, scale evidence, OCR, walls, rooms, openings, symbols, panels, observed routes, ambiguity, and warnings; host identity and approval cannot be supplied by model.
- [x] Candidate geometry uses reversible source-pixel coordinates and is not K1 metric geometry.
- [x] Unknown, empty, partial, and ambiguous results are valid without invented values.
- [x] Valid, malformed, out-of-bounds, adversarial, and empty fixtures are tested.
- [x] schema contains no Konva or Three.js state.

---

### TICKET U3 — Build Private Unannotated-Corpus Intake

**Goal:** Accept VED-approved scans without requiring user annotations while
protecting originals and preventing evaluation leakage.

**Dependencies:** U1.

**Acceptance Criteria:**

- [ ] Original hashes, consent/approval, drawing-set identity, pages, sheet types, and quality are manifested.
- [ ] Train, validation, and frozen-test groups are assigned by project/drawing set before pseudo-labeling.
- [ ] Exact and near-duplicate checks prevent cross-split leakage.
- [ ] Inputs, derivatives, prompts, labels, references, and model artifacts remain private and Git-ignored.
- [ ] Original source bytes are never modified.

---

### TICKET U4 — Build Approved Local Legend and Reference Pack

**Goal:** Ground local interpretation in approved VED classes and traceable
drawing/PEC evidence.

**Dependencies:** U3, J3A.

**Implementation status:** The local immutable pack builder, strict provenance,
rights and drawing-mapping contract, historical parent hash chain, unknown-glyph
separation, sanitized CLI and authenticated Admin catalog panel are implemented.
They add no API operation, database table, model dependency or catalog mutation.
real approved pack remains pending until every active VED class has reviewed
aliases, description, glyph evidence and permitted-use metadata.

**Acceptance Criteria:**

- [ ] Each active class has stable ID, approved name, aliases, description, glyph provenance, and active state.
- [ ] Drawing-specific legends are versioned and take precedence for their drawing.
- [ ] Unknown glyphs remain unknown instead of being forced into class.
- [ ] PEC/source edition, part, page, copyright, and permitted-use metadata are recorded.
- [ ] Retrieval cannot create or activate production classes.

---

### TICKET U5 — Create Frozen Gold Set and Metric Contract

**Goal:** Establish independently reviewed truth and promotion thresholds before
prompt selection or fine-tuning.

**Dependencies:** U2-U4.

**Acceptance Criteria:**

- [ ] named VED AI Dataset Approver signs representative page records.
- [ ] set covers empty/hard-negative, dense, multi-scale, degraded supported scans, and sheets with and without visible wiring.
- [ ] Metrics cover schema validity, page type, per-class symbol precision/recall/F1/count/IoU/center error, wall/room geometry, scale, wiring presence/topology/length, hallucination, latency, RAM, and VRAM.
- [ ] Numeric promotion thresholds and allowed regressions are approved before tuning.
- [ ] Frozen test examples are inaccessible to training, model selection, and prompt-selection workflows; U5 includes independent offline gold review before U9 exists.

---

### TICKET U6 — Run Local Model and Runtime Bake-Off

**Goal:** Select reproducible base VLM/runtime using measured local evidence.

**Dependencies:** U1, U2, U5.

**Acceptance Criteria:**

- [ ] Pinned Qwen3-VL 4B/8B and feasible fallbacks/helpers are evaluated or skipped for measured reason.
- [ ] Revision, hashes, license, runtime, memory, latency, schema validity, and quality are recorded.
- [ ] Network-egress checks confirm local-only inference.
- [ ] selected candidate passes approved gates, or ticket reports that no candidate qualifies.
- [ ] Available legacy YOLO results remain visible as comparison; missing weights are reported as unavailable rather than fabricated scores.

---

### TICKET U7 — Implement Multi-Resolution Page and Context Preparation

**Goal:** Preserve small symbols and page-level relationships for selected
local model.

**Dependencies:** U2, U6, G1-G3.

**Acceptance Criteria:**

- [ ] Overview, legend, plan-region, and overlapping-tile transforms are deterministic and reversible to page pixels.
- [ ] Normalized RGB is primary; threshold, line, and OCR evidence is auxiliary.
- [ ] Tile overlap/de-duplication has boundary fixtures.
- [ ] Derived files remain isolated and originals unchanged.
- [ ] Page/tile limits fail safely before resource exhaustion.

---

### TICKET U8 — Implement Isolated Local VLM Gateway

**Goal:** Produce schema-valid candidates without cloud inference or route-level
AI business logic.

**Dependencies:** U2, U6, U7.

**Acceptance Criteria:**

- [ ] Pinned model loading is lazy, cached, health-checked, and local-only.
- [ ] Each request records prompt, reference-pack version, model/adapter version, images, and decoding settings.
- [ ] Timeout, cancellation, bounded concurrency, memory, and retry limits are explicit.
- [ ] Grammar-constrained text still passes strict Pydantic validation before use.
- [ ] User errors are sanitized while protected diagnostics retain traceability.

---

### TICKET U9 — Generate Pseudo-Labels and Capture VED Corrections

**Goal:** Turn unannotated scans into reviewable candidates and approved training
targets.

**Dependencies:** U4, U8, J2-J5.

**Acceptance Criteria:**

- [ ] Pseudo-labels retain source, model, prompt, tile, and evidence provenance.
- [ ] Review covers U2 symbols, structure, panels, scale, and observed-wiring fields.
- [ ] Accept, correct, add, reject, and ambiguous decisions are append-only and durable in minimal U9 store that U11 reuses.
- [ ] Partially reviewed pages cannot enter supervised or gold releases.
- [ ] Codex and models cannot approve their own proposals.

---

### TICKET U10 — Fine-Tune and Register VED Adapter

**Goal:** Train reproducible LoRA/QLoRA adapter from approved targets rather
than training foundation model from scratch.

**Dependencies:** U5, U6, U9.

**Acceptance Criteria:**

- [ ] Only approved training examples and permitted synthetic data are used.
- [ ] Base revision, adapter config, seed, hyperparameters, framework versions, data hashes, and checkpoints are recorded.
- [ ] Validation selects checkpoints without access to frozen test set.
- [ ] Interrupted runs resume safely without overwriting released artifacts.
- [ ] adapter remains inactive until U14 promotion.

---

### TICKET U11 — Persist Candidates and Build the K1 Adapter

**Goal:** Preserve immutable machine provenance and convert only reviewed,
approved evidence into canonical geometry.

**Dependencies:** U2, U8, U9, K1-K3.

**Acceptance Criteria:**

- [ ] Every machine run is immutable and linked to its processing job and model release.
- [ ] Raw candidate, validation warnings, evidence, and latest human decisions are retrievable.
- [ ] Metric conversion requires explicit approved scale evidence.
- [ ] Only approved structure, symbols, panels, and observed routes reach K1/K2 through ADR 0001's atomic new v1 base plus additive extension, matching Python/JavaScript validation, and PRE8-safe saves.
- [ ] Historical YOLO detections and layout snapshots remain readable.

---

### TICKET U12 — Extract Observed Wiring Without Designing Routes

**Goal:** Recover wiring/conduit visibly drawn on sheet while keeping it
separate from later generated routing.

**Dependencies:** U2, U7-U9.

**Acceptance Criteria:**

- [ ] Sheets without visible wiring return empty observed-route set.
- [ ] Visible routes retain source polylines, endpoints, evidence, and ambiguity.
- [ ] Tile fragments merge deterministically without impossible jumps.
- [ ] Corrections persist and enter K1 only after approval.
- [ ] U12 adds no A*, wire/conduit sizing, or claimed PEC-compliance rule.

---

### TICKET U13 — Orchestrate Local Interpretation Jobs

**Goal:** Connect durable processing job to local pipeline without
holding request open.

**Dependencies:** U8, U11, U12, F1-F4.

**Acceptance Criteria:**

- [ ] worker safely claims jobs and reports only measurable stages.
- [ ] Cancellation, timeout, crash, restart, and bounded retry behavior are tested.
- [ ] Idempotency prevents duplicate candidate versions.
- [ ] Original/derived-file privacy and containment protections remain enforced.
- [ ] `completed` means reviewable candidates exist, not professionally approved geometry.

---

### TICKET U14 — Shadow, Promote, Roll Back, and Retire YOLO Safely

**Goal:** Activate local VLM only after it proves safe and useful on the
approved release contract.

**Dependencies:** U5-U13.

**Acceptance Criteria:**

- [ ] new path runs in non-authoritative shadow mode; available legacy results are compared on approved inputs and missing legacy weights are disclosed. A real tested rollback is mandatory.
- [ ] Numeric quality, privacy, schema, latency, and resource gates pass with signed VED decision.
- [ ] Activation uses versioned switch and tested rollback target.
- [ ] Existing YOLO records remain readable and auditable.
- [ ] YOLO code/dependencies are removed only through later separately reviewed cleanup.
- [ ] Active model release, evaluation report, hashes, approvals, and rollback target are auditable.

---

# 58. Recommended Ticket Execution Order

Codex should normally follow this order:

```text
A1 → A2 → A3 → A4

B1 → B2 → B3 → B4 → B5

C1 → C2 → C3 → C4 → C5
C6 after C2/C3 (logout)

D1 → D2 → D3 → D4

E1 → E2 → E3 → E3A → E4

F1 → F2 → F3 → F4

G1 → G2 → G3

H1 → H2 → H3

I1 → I2 → I3 → I4

J1 → J2 → J3 → J3A → J4 → J5

K1 → K2 → K3 → K4 → K5

L1

Current pre-migration foundation priority:
PRE0 → PRE1 → PRE2 → PRE3 → PRE4 → PRE5 → PRE6 → PRE7 → PRE8 → PRE9 → PRE10 → PRE11 → PRE12

Begin only after PRE12 passes:
U1 → U2 → U3 → U4 → U5 → U6 → U7 → U8 → U9 → U10 → U11 → U12 → U13 → U14

Resume only when explicitly selected:
L2 → L3 → L4 → L5

M1 → M2 → M3 → M4 → M5 → M6 → M7

N1 → N2 → N3 → N4

O1 → O2 → O3 → O4

P1 → P2 → P3 → P4

Q1 → Q2 → Q3 → Q4

R1 → R2 → R3

S1 → S2
S3 after U11, retaining I4 comparison until U14
S4 after L5
S5 after M6
S6 after O2

T1 throughout development
T2 after the application foundation is stable
T3 after the MVP pipeline is complete
```

Parallel work is allowed only when two tickets do not modify same contract or depend on unfinished behavior.

Each PRE and U ticket uses its own feature branch, focused verification, feature
commit, published upstream, explicit non-fast-forward merge, post-merge
verification, and synchronized `main`, then reports progress. The
`CODEX_PRE_VLM_FOUNDATION_PROMPT.md` handoff explicitly authorizes PRE0-PRE12
publication when user pastes it as active task; this planning document
alone does not authorize U work, model download, or dependency installation.
Assigning `CODEX_U_VLM_MIGRATION_PROMPT.md` as active task authorizes its
U1-U14 sequence and routine publication without repeated per-ticket permission,
subject to its data, human-approval, privacy, resource, and verification gates.

---

# 59. Acceptance Criteria Rules for Codex

Acceptance criteria must be **observable and testable**.

Avoid vague acceptance criteria such as:

```text
- Works correctly.
- Looks good.
- Is optimized.
- Handles errors.
- Is user-friendly.
```

Use verifiable statements such as:

```text
- GET /health returns HTTP 200.
- Invalid JPEG upload returns HTTP 400 or 422 with the documented error code.
- A Designer cannot call the Admin material-price update endpoint.
- Moving an outlet to x=3.0m, y=2.0m persists after page reload.
- The same outlet appears at the corresponding transformed position in the 3D view.
- A route with 5m horizontal travel and 2m vertical drop reports 7m total before configured allowance.
- Updating a material price does not change an estimate created before the update.
```

For every ticket, Codex should identify which acceptance criteria were:

```text
PASS
FAIL
NOT TESTED
BLOCKED
```

Do not mark criterion as passed if it was not actually checked.

---

# 60. Codex Ticket Prompt Template

Use these format when assigning ticket to Codex:

```text
TICKET ID:
TICKET TITLE:

OBJECTIVE:
Implement only the scope described in this ticket.

DEPENDENCIES:
List completed tickets required before starting.

FILES TO INSPECT FIRST:
List known relevant files/directories. Codex must inspect them before editing.

SCOPE:
List the exact functionality to implement.

OUT OF SCOPE:
List related features that must not be implemented in this ticket.

ACCEPTANCE CRITERIA:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

REQUIRED TESTS:
List automated/manual tests that must be performed.

CONSTRAINTS:
- Preserve existing working features.
- Do not refactor unrelated modules.
- Do not change shared API/data contracts unless this ticket explicitly requires it.
- Do not invent missing electrical engineering rules.
- Keep original floor-plan uploads unchanged.
- Keep canonical geometry as the shared source for 2D, 3D, routing, and estimation.

EXPECTED COMPLETION REPORT:
Ticket:
Status:
Files changed:
Database/schema changes:
API changes:
Tests added/updated:
Acceptance criteria results:
Known limitations:
Next dependency:
```

---

# 61. Definition of a Good Codex Ticket

ticket is appropriately sized when:

- Codex can describe its responsibility in one sentence.
- It has one primary output.
- Its acceptance criteria can be verified independently.
- Failure does not require debugging several unrelated modules at once.
- It does not combine database schema, AI training, 2D rendering, 3D rendering, routing, costing, and reports in one request.
- It can normally be reviewed in one focused code-review pass.

If ticket contains several independent outputs, split it again before implementation.
