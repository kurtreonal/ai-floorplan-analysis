# Implementation Architecture

> **Authority and status**
>
> `docs/FUNCTIONAL_SPEC.md` owns ticket scope and acceptance criteria;
> `AGENTS.md` owns repository-wide implementation rules. This document records
> the architecture actually implemented through L1, including E3A, J1A, and J3A, and labels
> downstream concepts as planned or proposed. The approved target AI migration
> is governed by `docs/LOCAL_VLM_MIGRATION_PLAN.md`; it does not retroactively
> make the local VLM an implemented capability.

## 1. Current implementation boundary

### Implemented

- A1–A4: repository, environment, React/Vite, and FastAPI foundations
- B1–B5: SQLAlchemy/PyMySQL connectivity and the first five prototype tables
- C1–C6: OAuth/OIDC, signed sessions, current-user restoration, role checks,
  frontend sign-in, and logout
- D1–D4: project create/list/detail APIs and project dashboard UI
- E1–E3: upload validation, original storage, and upload API
- E3A: project-floor list/create API required by upload
- E4: project-floor selection/creation and upload UI
- F1: persisted processing-job model and sixth prototype table
- F2: owning-Designer start-processing API with durable queued jobs
- F3: ownership-aware, read-only processing-job status API
- F4: Designer processing controls and sequential, abortable status polling for
  current-session upload cards
- G1: isolated one-page PDF-to-PNG conversion with safe derived storage and job
  failure-state persistence
- G2: Pillow-based orientation, RGB conversion, transparency compositing, and
  bounded no-upscale normalization for raster and G1 inputs
- G3: isolated OpenCV grayscale, denoising, blur, and threshold preprocessing
- H1: deterministic probabilistic-Hough wall-line candidate detection
- H2: immutable explicit-scale conversion from pixels to canonical meters
- H3: transactional persistence and read-only retrieval of wall geometry
- I1: validated local YOLO model loading with dynamic metadata and a bounded,
  thread-safe process cache
- I2: isolated, validated in-memory symbol inference over copied G3 binary data
- I3: immutable in-memory confidence classification with configured threshold
- I4: processing-job-versioned persistence and retrieval of original symbol AI
  provenance
- J1: ownership-aware read-only detection-results API with explicit symbol-job
  version selection and current H3 wall retrieval
- J1A: ownership-aware read-only serving of the existing G2 normalized RGB PNG
  as the aligned blueprint reference
- J2: protected React-Konva detection review with separate blueprint, current
  wall, selected-job symbol, and selection layers plus accessible DOM inspection
- J3: append-only, owning-Designer confirmation/rejection decisions with
  immutable machine detection provenance and persisted latest-review display
- J3A: database-backed approved symbol legend records and authenticated,
  active-only read-only retrieval
- J4: append-only owner-scoped Designer classification corrections with
  immutable original AI provenance and latest-authoritative retrieval
- J5: owner-scoped, retry-idempotent manual symbol placement using trusted J1A
  image dimensions, separate J1 retrieval, and a source-pixel K1 handoff
- K1: strict canonical geometry schema v1 plus pure H2-wall and J5-symbol
  adapters shared with a renderer-independent JavaScript normalizer
- K2: append-only canonical layout snapshots with per-floor version allocation,
  validated reconstruction, ordered history, and transactional current selection
- K3: owning-Designer current-layout retrieval and snapshot creation plus
  read-only Admin access, using the strict K1 request and K2 persistence contracts
- K4: protected read-only canonical layout route, strict current-layout client,
  responsive source-pixel Konva stage, six stable layers, accessible local
  visibility controls, and provenance-safe optional J1A blueprint display
- K5: detected/manual canonical symbol selection, Designer-only drag and
  accessible meter editing, immutable draft/save/cancel state, strict K3 POST
  use, uncertain-save reconciliation, and append-only K2 snapshot adoption
- L1: protected, lazy-loaded Three.js/React Three Fiber empty viewer with a
  demand-rendered neutral scene, direct OrbitControls lifecycle, orbit/pan/zoom,
  deterministic reset, and viewer-local loading/WebGL/error isolation
- PRE0: maintained migration documentation and private-artifact ignore baseline
- PRE1: ownership-aware persisted floor-plan discovery with safe metadata,
  deterministic floor/plan ordering, and optional project-floor filtering
- PRE2: ownership-aware bounded processing-job history discovery with safe
  error text, server timestamps, and deterministic newest-first ordering
- PRE3: reload-safe project workspace reconciliation, recovered active polling,
  persisted completed-review links, and inspection-only Admin job state
- PRE4: private immutable original SHA-256 manifests and one-based source-page
  identity, with atomic upload persistence and verified legacy backfill
- PRE5: durable derived-artifact manifests with exact job/source-page identity,
  bounded kinds, safe relative paths, content metadata, and trusted J1A lookup

### Planned

PRE6-PRE12 now define the remaining non-model foundation gate. After PRE12 passes, U1-U14
define the migration from the implemented YOLO-only symbol path to local
multimodal floor-plan interpretation. L2 and later roadmap tickets also remain
unimplemented, including canonical 3D geometry, routing, quantities, estimates,
reports, administration, and audit logging.

## 2. Implemented application layers

```text
React + JavaScript/JSX
        ↓ credentialed HTTP/JSON or multipart
FastAPI router
        ↓
Service layer
        ↓
Repository layer
        ↓
SQLAlchemy 2.x
        ↓
PyMySQL
        ↓
MySQL-compatible database
```

FastAPI routers handle request validation, authentication dependencies, HTTP
status mapping, and response schemas. Services own domain workflow. Repositories
own SQLAlchemy persistence queries. Upload validation and filesystem storage are
separate from route logic.

The preferred Windows development database is MySQL-compatible and managed by
XAMPP. FastAPI connects directly through PyMySQL; phpMyAdmin is optional and
Apache/PHP are not application dependencies.

## 3. Technology state

### Frontend

Implemented frontend technology is React with JavaScript/JSX and Vite. Current
tests use Vitest, Testing Library, and jsdom. The project does not use
TypeScript.

Konva/React-Konva, `three@0.185.1`, and `@react-three/fiber@9.7.0` are installed.
React Router, Axios/TanStack Query, and React Hook Form/Zod remain permitted by
the target architecture but are introduced only when their owning tickets need
them. The current project workflow uses a small hash route and Fetch-based API
modules. L1 lazy-loads its 3D route so Three/R3F remain outside the initial
application chunk.

### Backend

- Python and FastAPI/Uvicorn
- Pydantic and Pydantic Settings
- SQLAlchemy 2.x and PyMySQL
- Authlib and signed Starlette sessions
- Pillow and pypdf for upload validation
- `pypdfium2` with bundled PDFium for G1 PDF page rendering
- `ultralytics-opencv-headless==8.4.131` for lazy I1 model loading; the resolved
  environment uses `torch==2.13.0`, `torchvision==0.28.0`, and the existing
  `opencv-python-headless==4.14.0.94`
- Python `unittest` for the current backend suite

Prototype schema creation uses an explicit development-only
`Base.metadata.create_all()` command. Alembic and production migration tooling
remain deferred.

### AI/CV

G1 PDF-to-image conversion, G2 image normalization, G3 preprocessing, H1 wall
detection, H2 coordinate conversion, and H3 wall persistence are directly
callable backend services. I1 lazily loads a readable local `.pt` model from
`YOLO_MODEL_PATH`, using `models/yolo/electrical-symbols.pt` as the example
relative path. No trained model is stored in the repository. Loads are cached by
canonical path, and class metadata comes dynamically from `model.names`.
Invalid or missing models produce a controlled sanitized loader error without
breaking FastAPI startup. I2 consumes only G3's validated two-dimensional
`uint8` binary threshold array, gives YOLO a separate contiguous three-channel
copy, and converts one prediction result into immutable processed-pixel class,
confidence, bounding-box, and center records. It uses `conf=0.0` to defer the
application threshold to I3 and reports when the 300-result bound is reached.
Empty inference succeeds. A successful job wrapper leaves the job processing;
failure stores only the safe I2 message. No worker invokes the pipeline, and I2
adds no detection persistence, API, artifacts, UI, or automatic orchestration.

I3 consumes that immutable I2 result without invoking YOLO. It uses the existing
configured threshold, default `0.50`, classifies equality and higher confidence
as `detected`, and classifies lower confidence as `needs_review`. It preserves
all original prediction objects and result metadata in order. I3 itself has no
database or processing-job side effects and does not perform Designer
confirmation.

I4 validates the complete I3 result before mutation, locks the parent floor
plan, and atomically replaces only the selected processing job's detection rows.
Other jobs remain preserved as earlier machine-result versions. Retrieval is
ordered and relationship-isolated and does not execute I1-I3. Successful I4
persistence leaves job and floor-plan state unchanged.

J1 adds a read-only service/repository flow. It authorizes an exact
`floor_plan_analysis` job by joining processing job, floor plan, project floor,
and project without relationship lazy loading or row locks. Designers are
filtered by database-owned project ownership; Admins may read any matching
context. Symbols are selected only for the required query job, while walls are
the current H3 floor-plan set and expose their own processing-job provenance.
The route executes no AI/CV stage and performs no commit, flush, or state change.

J3 adds a Designer-only mutation flow from the existing detection route through
a review service and repository. It locks the exact owner-scoped detected-symbol
row, reads the latest sequence, treats identical decisions idempotently, and
appends reversals. `detection_reviews` has no mutable timestamp or delete
cascade. J1 obtains all latest reviews with one deterministic bulk query and
keeps its machine status unchanged. I4 explicitly rejects replacement of a job
version once any of its detections has review history.

J1A reuses that authorization context and resolves only the deterministic G2
`normalized/floor-plan-<id>/job-<id>/image.png` artifact beneath the processed
root. It validates containment, symlink safety, PNG content, RGB mode, byte
size, and G2 dimensions before returning private, non-cacheable bytes. It does
not generate missing images or mutate original files or database state.

J3A adds a separate read-only legend flow. `symbol_legends` stores unique
nonnegative model class IDs and unique normalized names with a deliberate
case-sensitive MySQL collation. Designers and Admins can retrieve active rows
ordered by class ID then row ID. The catalog may be empty, and no production
VED classes are inferred from detections or seeded without approved source
data. P3 still owns future Admin catalog management.

J4 adds a separate Designer-only mutation flow. The service locks the exact
owner-scoped detection, resolves the latest effective class, locks the requested
active legend, and appends an immutable old/new snapshot only for a real change.
Selecting the current class is idempotent; selecting the original class restores
it as authoritative without deleting history. J1 retrieves latest corrections
with one separate deterministic bulk query. J3 review decisions remain
independent, and I4 refuses same-job replacement when either review or
classification-correction history exists.

Ultralytics is available under AGPL-3.0 and a separate Enterprise license.
Commercial or production deployment requires a licensing review.

### Pre-migration foundation gate

U1 does not start directly from the current L1 implementation. PRE0-PRE12 in
`docs/PRE_VLM_FOUNDATION_PLAN.md` first close non-model gaps demonstrated by the
repository:

```text
reload-safe floor-plan and job discovery
        ↓
immutable source/page identity and artifact provenance
        ↓
approved elevation and scale inputs
        ↓
operational legend administration and dataset-approver authority
        ↓
conditional/idempotent layout saves
        ↓
engine-neutral claim/lease/cancel/recovery controls
        ↓
canonical v1 compatibility decision for future page/opening/panel/route data
        ↓
PRE12 readiness report
```

These foundations do not run inference, train a model, or remove YOLO. They
make the existing project/upload/review/canonical boundaries durable enough for
the U-series to extend them without rediscovering missing identity, recovery,
authorization, or concurrency contracts midway through migration.

### Target local multimodal architecture

The production target is a locally hosted open-weight **vision-language model
(VLM)**, not a text-only LLM. Model choice is intentionally not frozen until U1
records the actual CPU, RAM, GPU, VRAM, operating-system, privacy, and latency
constraints and U6 runs the same frozen evaluation set against feasible
candidates. The initial bake-off includes Qwen3-VL 4B/8B and a Qwen2.5-VL
fallback, with Florence-2 and PaddleOCR/PaddleOCR-VL eligible as specialist
grounding or OCR helpers rather than assumed sources of truth.

```text
Immutable uploaded PDF/image + SHA-256
        ↓
Validated page rendering and normalization
        ↓
Whole-page overview + legend crop + overlapping high-resolution tiles
        ↓
Local OCR + deterministic line/geometry evidence
        ↓
Isolated local VLM process with an approved legend/reference pack
        ↓
FloorPlanInterpretationCandidate JSON
        ↓
Strict schema, bounds, identity, topology, and provenance validation
        ↓
Cross-tile de-duplication and deterministic evidence fusion
        ↓
Persisted advisory machine interpretation
        ↓
VED Designer review/correction and independent release approval
        ↓
Deterministic adapter into validated K1 canonical geometry
        ↓
K2 version snapshot → Konva 2D / Three.js 3D / routing / quantities
```

`FloorPlanInterpretationCandidate` is an intermediate, versioned contract. It
must carry source/page/model/prompt/adapter provenance; page classification and
quality warnings; scale evidence; OCR regions; wall and room candidates;
symbol/panel candidates; observed wiring candidates; and explicit ambiguity.
It is not K1 geometry. The model never writes SQLAlchemy entities, Konva nodes,
Three.js meshes, routes, quantities, or estimates directly. Application-owned
validators and adapters own all identity and coordinate transformations.

The model must treat the drawing-specific approved legend as primary class
evidence. PEC 2017 and PEC 2020 references may support a local retrieval pack,
but their edition, part, page, copyright, and VED approval provenance must be
recorded. The model must not infer that a glyph is approved merely because it
resembles an example in a private reference scan.

#### Annotation-free user workflow versus model training

Ordinary users may submit previously unseen scans without drawing boxes or
polygons. That is an inference requirement, not evidence that raw scans alone
are adequate supervised training data. The private learning workflow has four
separate levels:

1. immutable raw, unannotated corpus;
2. model-generated pseudo-labels and deterministic evidence;
3. Designer-corrected and VED-approved gold records;
4. a project-separated frozen test set never used for training or class design.

Only levels 3 and approved non-test examples may enter supervised LoRA/QLoRA
training. Production requests never change weights automatically. Each adapter
release is offline, reproducible, versioned, hashed, evaluated, approved, and
reversible.

#### Observed and generated wiring

Wiring visibly present in the upload is `observed` drawing evidence. It retains
pixel/metric geometry, page and crop provenance, connected-symbol/panel
candidates, ambiguity, and review state. A later A* result is `generated` and
must retain routing-rule/version provenance. These collections must never be
silently merged. When no wiring is visibly supported, the correct observed
result is an empty collection; the VLM must not design missing circuits.

#### Runtime trust boundary

The model server runs on VED-controlled hardware, binds locally by default, has
no hosted-inference fallback, and receives only bounded pages/tiles for an
authorized job. Model artifacts are pinned by name, revision, license, and
hash. Grammar- or JSON-schema-constrained decoding reduces malformed output but
does not replace Pydantic validation. The gateway enforces input limits,
timeouts, cancellation, bounded concurrency, sanitized errors, health checks,
and resource accounting. Training runs in a separate environment from FastAPI
serving.

#### Migration and rollback

The local VLM first runs offline, then in shadow mode where its output is not
authoritative. Release promotion requires the U5 metric contract, zero private
data egress, strict-schema and coordinate safety gates, Designer review, and a
documented rollback. The I1-I4 YOLO path is removed only by a separately
approved U14 decision after the new release meets its gates; until then it is a
comparison and rollback implementation.

## 4. Authentication and session architecture

```text
OAuth/OIDC provider
        ↓ validated state and OIDC identity
FastAPI callback
        ↓ provider + subject lookup
Local users row
        ↓ role relationship
Local ADMIN or DESIGNER authorization
        ↓
Signed HttpOnly session containing local user_id only
```

The OAuth/OIDC provider is environment-configurable. The login route creates
state and nonce values. The callback validates state and uses Authlib's OIDC
validation before accepting the provider subject. Provider tokens and
authorization codes are not stored in MySQL or the application session.

New verified identities receive the local `DESIGNER` role. Existing local roles
are preserved, and provider claims cannot grant `ADMIN`. `/api/auth/me` reloads
the user and role from MySQL for each request, so the database remains
authoritative.

Session cookies are signed and HttpOnly, use `SameSite=Lax`, and are secure
outside development. Logout clears only the local VED session. Credentialed
CORS accepts explicit configured origins and rejects wildcard origins.

## 5. Authorization behavior

| Action | DESIGNER | ADMIN |
|---|---|---|
| List projects | Owned projects | All projects |
| Read project detail | Owned project | Any project |
| Create project | Allowed | Denied |
| List project floors | Owned project | Any project |
| Create project floor | Owned project | Denied |
| Upload floor plan | Owned project/floor | Denied |
| Start floor-plan processing | Owned floor plan | Denied |

Missing authentication returns `401`. Authenticated unsupported roles return
`403`. Designer access to another owner's project returns `404` to conceal the
resource. Project ownership and role values are derived server-side rather than
trusted from client input or provider claims.

## 6. Implemented database schema

The live and SQLAlchemy model table set remains exactly the same through K5:

```text
roles
users
projects
project_floors
floor_plans
processing_jobs
walls
detected_symbols
detection_reviews
symbol_legends
detection_class_corrections
manual_symbols
layout_versions
```

Relationships:

J5 also associates each `manual_symbols` row with one floor plan, processing
job, creator user, and approved symbol legend. These relationships have no
destructive delete cascade.

```text
roles 1 ── * users
users 1 ── * projects
projects 1 ── * project_floors
project_floors 1 ── * floor_plans
floor_plans 1 ── * processing_jobs
floor_plans 1 ── * walls
processing_jobs 1 ── * walls
floor_plans 1 ── * detected_symbols
processing_jobs 1 ── * detected_symbols
detected_symbols 1 ── * detection_class_corrections
users 1 ── * detection_class_corrections
symbol_legends 1 ── * detection_class_corrections (old/new nullable references)
projects 1 ── * layout_versions
project_floors 1 ── * layout_versions
floor_plans 1 ── * layout_versions
```

- `users` maps provider plus subject to a local role and contains no password.
- `projects.owner_id` identifies the authoritative Designer owner.
- `project_floors` supports multiple ordered floors per project.
- `floor_plans` stores upload metadata and a relative storage reference.
- `processing_jobs` stores a job type, constrained lifecycle status, bounded
  progress, a safe nullable error message, and timestamps for one floor plan.
- `detected_symbols` snapshots original I1/I2 output plus I3 classification and
  uses processing jobs as immutable machine-result version identifiers. A
  unique job/prediction index retains source order without duplicating project
  or project-floor identifiers.
- `walls` stores the current detected or later-verified wall geometry with raw
  pixel values, canonical meter values, scale, and processing provenance.
- `detection_reviews` stores immutable Designer confirmation/rejection events.
- `symbol_legends` stores the active/inactive approved class catalog. No
  production legend records are seeded by J3A.
- `detection_class_corrections` stores append-only old/new class snapshots and
  reviewer provenance; it has no mutable timestamp or delete cascade.
- `manual_symbols` stores immutable active-legend snapshots, creator and review
  context provenance, retry UUIDs, trusted review-image dimensions, and bounded
  source-pixel centers; it has no mutable timestamp or delete cascade.
- `layout_versions` stores complete K1 schema-v1 JSON documents as append-only
  snapshots. Positive versions are sequential per floor, `TRUE` marks the one
  current row while historical rows use `NULL`, and foreign keys have no
  destructive delete cascade.

Processing-job status is restricted by `ck_processing_jobs_status` to `queued`,
`processing`, `completed`, `failed`, or `cancelled`. Progress is restricted by
`ck_processing_jobs_progress` to the inclusive range 0–100. The defaults are
`queued` and `0`. F2 uses each job row as the durable queue entry and does not
change a floor plan's upload status.

The required seeded role names are `ADMIN` and `DESIGNER`. Schema initialization
and role seeding are explicit development commands and do not run at FastAPI
startup.

## 7. Implemented API surface

```http
GET  /health

GET  /api/auth/login
GET  /api/auth/callback
GET  /api/auth/me
POST /api/auth/logout

GET  /api/projects
POST /api/projects
GET  /api/projects/{project_id}

GET  /api/projects/{project_id}/floors
POST /api/projects/{project_id}/floors

GET  /api/projects/{project_id}/floor-plans?project_floor_id={optional_floor_id}
POST /api/projects/{project_id}/floor-plans

GET  /api/projects/{project_id}/floors/{project_floor_id}/layouts
POST /api/projects/{project_id}/floors/{project_floor_id}/layouts

POST /api/floor-plans/{floor_plan_id}/process
GET  /api/processing-jobs/{job_id}
GET  /api/floor-plans/{floor_plan_id}/detections?processing_job_id={job_id}
GET  /api/floor-plans/{floor_plan_id}/review-image?processing_job_id={job_id}
PUT  /api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review?processing_job_id={job_id}
GET  /api/symbol-legends
PUT  /api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/classification?processing_job_id={job_id}
POST /api/floor-plans/{floor_plan_id}/manual-symbols?processing_job_id={job_id}
```

The API contains 23 OpenAPI operations through PRE2. Floor-plan discovery
returns safe persisted metadata to the owning Designer or an Admin, supports a
positive project-scoped optional floor filter, and orders by floor sort order,
floor ID, then floor-plan ID without reading files or exposing storage paths.
Processing-job history discovery returns only the authorized floor plan's
`floor_plan_analysis` jobs, orders by creation time and job ID newest first,
exposes sanitized status/error/timestamp metadata, and uses a validated default
limit of 50 with a maximum of 100. It neither executes nor mutates jobs.
Detection retrieval requires a
positive `processing_job_id`; it returns HTTP 200 with empty arrays for an
authorized matching context that has no stored walls or symbols. Machine and
manual symbols are returned in separate arrays. Symbols are
job-versioned, whereas walls remain the current floor-plan wall set.

The layout `GET` returns only the current complete K2 snapshot. It permits the
owning Designer and Admins. The matching `POST` is owning-Designer-only, accepts
the exact complete K1 document, verifies path and persisted-floor identity, and
creates a new append-only current K2 version. K3 exposes no history or
current-version-selection API and performs no floor-plan file writes.

All business responses use Pydantic response schemas. Project-floor listing is
ordered by `sort_order` then ID. The upload endpoint requires a positive
`project_floor_id` multipart field and an uploaded file.
The processing endpoint requires an owning Designer, returns `202` with a
durable queued job ID, locks the authorized parent floor-plan row before its
active-job check, and returns `409` for an existing queued or processing job.
Terminal jobs permit a new attempt.
The status endpoint permits owning Designers and all Admins, selects only public
job fields without relationship loading or row locks, and maps any failed job to
a stable generic public error message. Missing and cross-owner jobs use the same
sanitized `404` response.

Application-generated errors use FastAPI `HTTPException` and therefore appear
under `detail`:

```json
{
  "detail": {
    "error": {
      "code": "PROJECT_NOT_FOUND",
      "message": "The requested project was not found.",
      "details": {}
    }
  }
}
```

Framework request-validation errors use FastAPI's standard validation-detail
array. A globally uniform top-level error envelope has not been implemented.

## 8. Project and upload frontend workflow

```text
Restore signed session with /api/auth/me
        ↓
Load Designer-owned or Admin-visible projects
        ↓
Create/open a project
        ↓
Load project floors
        ├── Designer may create a floor
        └── Admin has read-only floor visibility
        ↓
Designer selects a floor and uploads JPEG/PNG/PDF
        ↓
Display returned upload metadata for this page session
        ↓
Designer starts a durable processing job
        ↓
Poll public job status sequentially until a terminal state
```

The dashboard and project detail views include loading, empty, error, retry,
submission, and authorization-appropriate states. Backend responses remain
authoritative for project status, upload metadata, and job progress. Processing
controls appear only on Designer upload cards returned during the current page
session; Admins retain read-only floor visibility. Polling uses one abortable
request at a time and schedules the next request only after the prior response.
It stops for terminal states, authentication/authorization failures, unmounts,
and non-retryable lookup errors. Temporary monitoring failures preserve the job
ID and require an explicit status retry. Completed status does not imply that
AI results or the later detection-review workflow exist.

## 9. Validation and original storage pipeline

```text
Authenticated Designer request
        ↓
Owned project check
        ↓
Floor belongs to project check
        ↓
Read configured maximum + 1 byte into memory
        ↓
Extension + MIME + signature validation
        ↓
Image/PDF integrity and dimensions/pages validation
        ↓
Write exact bytes to <UPLOAD_DIR>/originals/<generated name>
        ↓
Persist relative originals/<generated name> reference
        ↓
Commit, or rollback and remove the new file
```

Supported inputs are JPEG/JPG, PNG, and PDF. Encrypted or empty PDFs, corrupt
files, disguised content, invalid image dimensions, decompression bombs, and
oversized files are rejected. Client filename path components cannot select the
destination path. Existing originals are never overwritten or modified.

The current endpoint holds the bounded upload in memory; streaming storage is
not implemented. G1 resolves only persisted PDF references confined beneath
`<UPLOAD_DIR>/originals`, preserves their bytes, and writes exactly one selected
page to a collision-safe RGB PNG beneath:

```text
<PROCESSED_DIR>/pdf-pages/floor-plan-<id>/job-<id>/page-<NNNN>.png
```

Page selection is one-based and defaults to page 1. Rendering defaults to 150
DPI. The output reference is returned by the service and is not stored in a new
table. Successful conversion leaves the broader job `processing`; a conversion
failure persists only the safe failed-state message. G1 is not connected to F2
automatically because no worker exists.

G2 accepts either an uploaded JPEG/PNG resolved beneath originals or a validated
G1 page for the same floor plan and job. Its separate output contract is:

```text
<PROCESSED_DIR>/normalized/floor-plan-<id>/job-<id>/image.png
```

The typed result records encoded source, oriented, and normalized dimensions.
No `processed_images` table or sidecar manifest exists. Success leaves the job
`processing` with unchanged progress; failure persists only the stable safe
normalization message. Uploaded originals and G1 pages are never modified.

G3 consumes only that normalized G2 PNG through the isolated
`app.ai.preprocessing` package. The pure array pipeline is:

```text
RGB uint8 -> grayscale -> median filter -> optional Gaussian blur
          -> Otsu or fixed binary threshold
```

The implementation uses the server-oriented `opencv-python-headless==4.14.0.94`
wheel with `numpy==2.5.2`, without OpenCV GUI or system-library dependencies.
Central frozen parameters default to 3x3 median filtering, enabled 3x3 Gaussian
blur with automatic sigma, Otsu threshold selection, no inversion, and no debug
writes. Fixed thresholding and inversion are explicit alternatives.

The filesystem boundary accepts only
`normalized/floor-plan-<id>/job-<id>/image.png` beneath `PROCESSED_DIR`, verifies
the matching G2 IDs and dimensions, and decodes a three-channel PNG from bounded
bytes. It never changes the G2 file. Optional evaluation artifacts use portable
references beneath
`preprocessed/floor-plan-<id>/job-<id>/` and are exclusive, single-channel
`uint8` PNGs. Partial artifact creation receives compensating cleanup.

The database-aware wrapper requires the matching analysis job to already be
`processing`; success changes neither status nor progress, while failure stores
only `Floor-plan preprocessing failed.` No FastAPI route or worker invokes G3,
and no schema or manifest persists its output. G3 ends at binary thresholding;
wall detection begins separately in H1.

H1 implements that first detection step in `app.ai.wall_detection` without
changing G3 or reopening any derived file:

```text
PreprocessedImage.thresholded
    -> Canny
    -> HoughLinesP
    -> canonical pixel endpoints
    -> exact deduplication
    -> deterministic candidate tuple
```

The coordinate space is raw pixels with a top-left origin, x increasing right,
and y increasing down. Endpoint order is topmost first and then leftmost for a
tie. Candidate order is start y, start x, end y, end x; one-based IDs are
assigned only after sorting. Length and normalized `[0, 180)` angle values are
rounded to six decimal places. Exact segments are deduplicated, but H1 does not
merge or pair nearby/collinear detections.

Central prototype defaults are Canny 50/200 with aperture 3 and probabilistic
Hough rho 1.0, theta 1.0 degree, 50 votes, 50-pixel minimum length, 10-pixel
maximum gap, and a 2000-candidate limit. Deterministic overflow truncation is
reported explicitly. Empty detections are successful empty results.

These candidates remain unverified image-space suggestions. H1 has no file I/O,
preview drawing, persistence, API, worker, job-state mutation, scale conversion,
wall thickness/pairing, room construction, frontend overlay, or YOLO behavior.

H2 adds `app.geometry` as the first shared, renderer-independent metric geometry
boundary. It consumes H1's typed result without executing OpenCV and requires an
explicit positive finite `pixels_per_meter` for every conversion. No default or
scale inference exists, and PDF DPI is never treated as architectural scale.
The `100 pixels_per_meter` specification sample is illustrative only.

The canonical wall-candidate plane is:

```text
unit: meter
origin: normalized image top-left
x direction: right
y direction: down
```

Each candidate preserves its H1 ID, order, raw endpoints, raw length, raw angle,
and truncation provenance. Canonical endpoints divide pixel coordinates by the
explicit scale; metric length is derived from those endpoints. Immutable
objects retain full floating-point precision, while JSON-ready metric values
round to nine decimal places and normalize negative zero.

Future adapters branch from this one coordinate model: canonical x maps to
Three.js x, canonical y maps to Three.js z, and floor elevation maps to Three.js
y. This is documentation only; H2 contains neither Konva nor Three.js state.
H2 outputs remain machine candidates rather than verified authoritative walls.
It adds no persistence, database schema, project/floor association, API, worker,
scale calibration, merging, snapping, thickness, rooms, or renderer.

H3 persists that H2 contract without rerunning OpenCV. `walls.floor_plan_id`
and `walls.processing_job_id` are indexed foreign keys; the floor chain remains
`Wall -> FloorPlan -> ProjectFloor`. Numeric geometry crosses the persistence
boundary as fixed-scale `Decimal` values. Machine writes always use `detected`,
while the database contract also supports `verified` for later review work.

Replacement locks the floor-plan row with `SELECT ... FOR UPDATE`, validates a
matching `floor_plan_analysis` job in `processing`, rejects truncated geometry,
and refuses to overwrite verified rows. Otherwise it deletes the prior detected
set and inserts the complete replacement with one commit. Empty geometry is a
valid empty replacement, and any failure rolls back deletion and insertion.
Read-only retrieval is ordered, immutable, relationship-isolated, and performs
no OpenCV or H2 conversion. H3 adds no API, review transition, editing, worker,
rooms or symbols. K1 composes H2 walls and J5 authoritative symbols into the
document described by `geometry.md` without changing H2 persistence.

## 10. Testing strategy and verified baseline

- Backend: Python `unittest`, including FastAPI TestClient and live
  MySQL-backed transactional tests
- Frontend: Vitest, Testing Library, and jsdom
- Static checks: frontend ESLint/build, Python compileall/pip check, environment
  template validation, OpenAPI/metadata inspection, and Git diff checks

The verified backend surface remains unchanged through K5; K5 adds one focused
K3 persistence/reload regression while using the existing operations. K4 adds focused
frontend API, route, navigation, coordinate, canvas, layer-toggle, page, and
accessibility coverage:

```text
F3 focused backend:    11 tests
F2 focused regression: 15 tests
F1 focused regression: 17 tests
G1 focused backend:     38 tests
G2 focused backend:     38 tests
G3 focused backend:     37 tests
H1 focused backend:     32 tests
H2 focused backend:     30 tests
H3 focused backend:     21 tests
I1 focused backend:     21 tests
I2 focused backend:     25 tests
I3 focused backend:     13 tests
I4 focused backend:     15 tests
J1 focused backend:     15 tests
J1A focused backend:    10 tests
J3 focused backend:      9 tests
J3A focused backend:     9 tests
J4 focused backend:     11 tests
J5 focused backend:      8 tests
J5 backend regressions: 90 tests
K1 focused backend:     39 tests
K1 required regressions: 85 tests + 63 subtests
K2 focused backend:     17 tests + 27 subtests
K3 focused backend:     13 tests + 26 subtests
Backend unittest:      590 tests + 479 subtests
Canonical pytest:       39 tests
Backend aggregate:     629 top-level tests + 479 subtests
F4 API client:           21 tests
F4 component:            35 tests
J3 focused frontend:    25 tests
J4 focused frontend:    18 tests
J5 focused frontend:    49 tests
K1 focused frontend:    21 tests
K1 J2/J5 regressions:   43 tests
K4 focused frontend:    19 tests + 4 route/navigation regressions
L1 focused/regression:  40 tests
Full frontend:          264 tests
```

The current Starlette TestClient/httpx combination emits a deprecation warning;
it does not currently hide test failures. The backend suite runs with pytest
while retaining its existing `unittest`-style test classes.

## 11. Planned downstream architecture

The target data flow remains:

```text
Original floor plan
        ↓
Durable queued processing job with planned local VLM worker pipeline
        ↓
Validated candidate interpretation and persisted Designer review
        ↓
Persisted K2 canonical layout snapshots
        ├── implemented Konva 2D symbol editor
        ├── implemented empty Three.js foundation; canonical rendering planned
        ├── planned electrical routing
        └── planned quantities and estimates
                    ↓
              planned PDF report
```

These modules are architectural commitments, not current application
capabilities. Verified canonical geometry must eventually become the shared
source for 2D, 3D, routing, quantities, estimates, and reports. Raw AI output,
Konva state, and Three.js scene state must not become competing sources of
truth.

## 12. Current limitations and next decision

- No persistent floor-plan listing/retrieval API
- Start-processing creates a durable queued database row and status polling is
  read-only, but no worker, external queue, cancellation endpoint, or automatic
  upload hook exists
- G1 through H3 are callable by backend code but are not automatically
  orchestrated from F2; persistent processed-image metadata remains unimplemented
- I1-I4 can load configured local YOLO weights, run isolated inference,
  classify confidence, and persist versioned machine output, but
  the repository has no trained model and no automatic OpenCV/YOLO pipeline
  exists
- No local VLM runtime, model gateway, candidate schema, reviewed gold set,
  adapter, or VLM worker exists yet. Unannotated source scans and provisional
  boxes are not approved training truth.
- J1/J1A/J2 retrieve and display stored walls, an explicitly selected symbol-job
  version, and its aligned normalized blueprint reference; J3 persists
  confirmation/rejection decisions without changing machine provenance
- Detection review supports J4 approved-catalog classification correction and
  J5 manual symbol creation; K1 geometry can be persisted through K2 and loaded
  or saved as the current snapshot through the protected K3 API
- J3A exposes an empty-safe approved legend catalog, but no approved production
  VED class values or Admin catalog-management operations have been supplied
- K5 renders an immutable draft of the current K3 snapshot in K4's six
  always-mounted Konva layers. Symbols can be selected and repositioned by an
  owning Designer; visibility remains presentation-only. Walls, rooms, routes,
  scale, identity, elevation, class/status, deletion, and resizing are read-only.
- K4 reuses the J1A review image only when wall/symbol provenance resolves to
  exactly one safe processing job and decoded dimensions match the canonical
  source plane. Missing/mixed provenance remains an explicit limitation until
  a later blueprint-source contract is approved.
- Canonical symbol positions are editable in 2D; other canonical geometry is
  read-only. L1 provides an empty 3D viewer only, with no project geometry or
  editing.
- No routing or multi-floor route calculation
- No material pricing, estimates, reports, or audit logs
- Production Vercel deployment remains frontend-only without a separately
  deployed HTTPS FastAPI backend

K3 exposes K2 current-layout retrieval and snapshot creation; K5 uses those
existing operations for canonical symbol movement and append-only saving. Floor elevation
is required by the canonical contract, stored inside each complete snapshot, is not a
`project_floors` column, and is never inferred. K3 has no atomic conditional-save
or idempotency-key contract; K5's uncertain-response reconciliation does not
claim otherwise. PRE0's documentation/privacy baseline is complete and
published. PRE1 floor-plan discovery and PRE2 processing-job history are also
complete and published. The next priority ticket is PRE3; no U ticket has started. U1 depends on the PRE12
readiness gate. L2 is paused unless explicitly
selected. L1's
grid and axes are neutral orientation helpers and it makes no layout,
floor-plan, detection, or processing-job request. Canonical floor meshes,
walls, openings, symbols, synchronization, and top/perspective switching remain
future work.
The PRE3 project workspace consumes persisted floor plans and bounded job
history, deduplicates optimistic upload feedback, and resumes active polling.
PRE4 gives originals and their pages immutable identity. PRE5 adds the
`processing_artifacts` manifest and makes G1/G2 output provenance durable; J1A
now resolves the exact registered normalized image and revalidates its file,
hash, MIME, and dimensions. PRE6 is next.
