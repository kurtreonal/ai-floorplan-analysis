# Implementation Architecture

> **Authority and status**
>
> `docs/FUNCTIONAL_SPEC.md` owns ticket scope and acceptance criteria;
> `AGENTS.md` owns repository-wide implementation rules. This document records
> the architecture actually implemented through I4, including E3A, and labels
> downstream concepts as planned or proposed.

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

### Planned

J1 and later roadmap tickets remain unimplemented, including workers,
detection API/review UI, complete K1 geometry, Konva
2D, Three.js 3D, routing, quantities, estimates, reports, administration, and
audit logging.

### Proposed but not approved

A project floor-plan listing API has been identified as useful, but this route
does not exist:

```http
GET /api/projects/{project_id}/floor-plans
```

Adding it requires a separate approved ticket. E4 currently displays successful
upload responses only for the active page session.

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

React Router, Axios/TanStack Query, React Hook Form/Zod, Konva, and Three.js are
required or permitted by the target architecture but are introduced only when
their owning tickets need them. The current project workflow uses a small hash
route and Fetch-based API modules.

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

Ultralytics is available under AGPL-3.0 and a separate Enterprise license.
Commercial or production deployment requires a licensing review.

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

The live and SQLAlchemy model table set through I4 is exactly:

```text
roles
users
projects
project_floors
floor_plans
processing_jobs
walls
detected_symbols
```

Relationships:

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

POST /api/projects/{project_id}/floor-plans

POST /api/floor-plans/{floor_plan_id}/process
GET  /api/processing-jobs/{job_id}
```

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
rooms, symbols, or full K1 project geometry.

## 10. Testing strategy and verified baseline

- Backend: Python `unittest`, including FastAPI TestClient and live
  MySQL-backed transactional tests
- Frontend: Vitest, Testing Library, and jsdom
- Static checks: frontend ESLint/build, Python compileall/pip check, environment
  template validation, OpenAPI/metadata inspection, and Git diff checks

The verified baseline through I4 is:

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
I4 focused backend:     13 tests
Full backend:          468 tests
F4 API client:           21 tests
F4 component:            35 tests
Full frontend:          103 tests
```

The current Starlette TestClient/httpx combination emits a deprecation warning;
it does not currently hide test failures. The backend suite runs with pytest
while retaining its existing `unittest`-style test classes.

## 11. Planned downstream architecture

The target data flow remains:

```text
Original floor plan
        ↓
Durable queued processing job with planned worker and AI/CV pipeline
        ↓
Planned Designer review
        ↓
Planned verified canonical geometry
        ├── planned Konva 2D
        ├── planned Three.js 3D
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
  exists; the detection API and review workflow remain unimplemented
- No detection review or canonical geometry
- No 2D/3D editor implementation
- No routing or multi-floor route calculation
- No material pricing, estimates, reports, or audit logs
- Production Vercel deployment remains frontend-only without a separately
  deployed HTTPS FastAPI backend

The next roadmap ticket is J1 detection results API. A persistent
floor-plan listing API remains a separate proposed ticket and is not implied by
I4.
