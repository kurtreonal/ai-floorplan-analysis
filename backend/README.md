# VED Electrical Services API

This directory contains the FastAPI backend implemented through K3; the
repository's frontend is implemented through L1. The backend
provides application liveness, OAuth/OIDC authentication with signed local
sessions, database-authoritative role authorization, project APIs,
project-floor APIs, original floor-plan upload validation and storage, and
persisted processing-job records, the owning-Designer start-processing endpoint,
and an ownership-aware processing-status endpoint. A backend-only PDF-to-PNG
image normalization, OpenCV preprocessing, wall detection/normalization/
persistence, configured YOLO model loading, and isolated symbol inference are
also implemented, together with confidence filtering, versioned symbol
persistence, read-only detection-result retrieval, authenticated serving of
the existing normalized review image, append-only Designer confirmation or
rejection decisions, an active-only approved symbol legend API, and append-only
Designer classification correction, and owner-scoped manual symbol placement.
K1 adds a pure canonical geometry v1 contract and adapters. K2 adds the
thirteenth prototype table and a backend-only transactional service for
append-only canonical layout snapshots, history retrieval, and current-version
selection. K3 exposes current-layout retrieval and owning-Designer snapshot
creation through two layout operations. K4 consumes only the existing `GET`
operation and makes no backend or schema change. K5 consumes the existing K3
GET and POST operations to reposition canonical symbols and adds no backend
operation, table, or schema field. L1 adds only a protected, empty frontend 3D
viewer and likewise makes no backend, API, schema, storage, or environment
change. The API remains at 21 operations. Workers, canonical 3D rendering,
non-symbol geometry editing, routing, estimation, and reporting are not implemented.

## Requirements

- Python 3.13.7
- MySQL-compatible development server (XAMPP is the preferred Windows workflow)
- The dependencies pinned in `requirements.txt`

PDF rendering uses `pypdfium2==5.13.0`, installed from its Windows wheel with
bundled PDFium. It requires no Poppler, Ghostscript, Java, or separate rendering
executable. The package is available under Apache-2.0/BSD-3-Clause licensing.

The current automated backend suite uses Python `unittest`. Pytest is not an
installed project dependency.

## Setup

From `backend/` on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The application optionally reads the ignored repository-root `.env`. Process
environment variables take precedence. Copy public key names from
`.env.example`, replace placeholders locally, and never commit credentials.

## Database and prototype schema

FastAPI connects directly to the configured MySQL-compatible server through
SQLAlchemy and PyMySQL. It does not connect through phpMyAdmin; Apache and PHP
are not backend dependencies.

1. Start the existing XAMPP MySQL service.
2. Create the development database manually if it does not exist.
3. Configure `DATABASE_URL` in the ignored root `.env` with the
   `mysql+pymysql` driver.
4. Verify connectivity from `backend/`:

   ```powershell
   .\.venv\Scripts\python.exe -c "from app.core.database import verify_database_connection; verify_database_connection(); print('Database connection verified.')"
   ```

The connection is lazy: importing FastAPI and calling `/health` do not test
database readiness.

The explicit development-only schema command is:

```powershell
.\.venv\Scripts\python.exe -m app.core.schema
```

It imports registered models and calls `Base.metadata.create_all()` to create
missing tables. It does not run during startup and is not a migration system.
The current prototype has these thirteen application tables:

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

Alembic and production schema migrations remain deferred. Never run schema
initialization as an automatic repair step against an unexpected database.

Seed the required local roles deliberately in development:

```powershell
.\.venv\Scripts\python.exe -m app.core.seed
```

The idempotent seed ensures `ADMIN` and `DESIGNER` exist; it does not seed
users.

## Authentication, sessions, and authorization

`GET /api/auth/login` starts a provider-configurable OAuth 2.0/OIDC flow. The
callback validates state and relies on Authlib for OIDC identity-token
validation. A verified provider plus subject resolves a local user. New users
receive `DESIGNER`; provider claims never grant local `ADMIN` authority.

The signed, HttpOnly application session stores only the local user ID.
`GET /api/auth/me` reloads the user and current role from MySQL. Logout clears
only the local VED session. Provider tokens, authorization codes, client
secrets, and provider subjects are not returned by `/api/auth/me` or stored in
the session.

Authorization behavior:

- `DESIGNER` can create projects, create floors for owned projects, upload floor
  plans to owned project floors, and start processing for owned floor plans.
- `DESIGNER` project access is owner-scoped; cross-owner access returns `404`
  to conceal resource existence.
- `ADMIN` can list and inspect all projects and list their floors.
- `ADMIN` cannot create projects, create floors, upload floor plans, or start
  floor-plan processing through the current API.
- Missing authentication returns `401`; an authenticated unsupported role
  returns `403`.

Credentialed CORS accepts only explicitly configured origins. Wildcard origins
are rejected while credentials are enabled.

## Implemented API

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

The API has 21 OpenAPI operations through L1; K4, K5, and L1 add no backend operation.
`GET /api/symbol-legends`
permits authenticated Designers and Admins, returns active records ordered by
model class ID then row ID, and returns `[]` when the catalog is empty. No
official VED class values are committed or seeded; P3 remains responsible for
future Admin management of the catalog.

`GET /api/projects/{project_id}/floor-plans` does not exist. The E4 frontend
shows successful uploads returned during the current page session, but upload
history cannot repopulate after reload. Persistent history requires a separate
approved ticket.

## Floor-plan validation and original storage

The upload API accepts JPEG/JPG, PNG, and PDF multipart uploads with a positive
`project_floor_id`. Before storage it verifies:

- extension and declared MIME type;
- MIME/extension agreement and content signature;
- configurable maximum size;
- image integrity and dimensions, including decompression-bomb protection;
- PDF integrity, encryption status, and at least one accessible page.

The endpoint currently reads at most the configured size plus one byte into
memory, so uploads are validated and stored in-memory rather than streamed to
the final file.

Original bytes are stored under `<UPLOAD_DIR>/originals` with collision-safe
generated names. User path components are removed, existing originals are not
overwritten, and `floor_plans.storage_path` contains a relative POSIX reference
such as `originals/<generated-name>.png`, not an absolute filesystem path.

The E2 storage service owns the database commit/rollback boundary. If record
persistence fails, it rolls back and removes the newly written file as a
compensating cleanup action. Later processing must write separate derived files
and must never modify the stored original.

## Processing-job records

F1 adds `processing_jobs` as a persisted child of `floor_plans`. Its database
fields are `id`, `floor_plan_id`, `type`, `status`, `progress`,
`error_message`, `created_at`, and `updated_at`. The Python model exposes the
database `type` column as `job_type`.

Allowed statuses are `queued`, `processing`, `completed`, `failed`, and
`cancelled`. The named `ck_processing_jobs_status` constraint enforces that
set, while `ck_processing_jobs_progress` enforces progress from 0 through 100.
Status defaults to `queued`, progress defaults to `0`, and `floor_plan_id` is an
indexed required foreign key to `floor_plans.id`.

F2 exposes:

```http
POST /api/floor-plans/{floor_plan_id}/process
```

An owning Designer receives `202 Accepted` with `job_id` and status `queued`.
The server controls the `floor_plan_analysis` job type. Admin and unsupported
roles receive `403`; inaccessible and nonexistent floor plans share a sanitized
`404`. A `queued` or `processing` job produces `409`, while `completed`,
`failed`, or `cancelled` jobs permit a new attempt.

The service locks the authorized `floor_plans` row with `SELECT ... FOR UPDATE`
before checking for an active job. The database job row is currently the
durable queue. Failure-state persistence stores only the stable message
`Floor-plan processing could not be started.`

F3 exposes:

```http
GET /api/processing-jobs/{job_id}
```

Owning Designers may read jobs beneath their projects, while Admins may read any
job. Missing and cross-owner jobs share the same sanitized `404`; unauthenticated
requests receive `401`, and unsupported roles receive `403`. The response is
limited to `job_id`, `type`, `status`, `progress`, and nullable
`error_message`. Failed jobs expose a stable generic message instead of stored
database errors. Polling uses relationship-free read queries without row locks
and does not modify job, floor-plan, or original-file state.

F3 does not provide a worker, external queue, automatic upload hook,
cancellation endpoint, or AI/CV behavior. F4's frontend can start and poll jobs
for uploads returned during the current page session, but it adds no backend
operation and cannot advance job lifecycle state. Job lifecycle changes do not
modify the original upload or `floor_plans.processing_status`.

## PDF-to-image conversion

G1 adds `app.services.pdf_conversion`, a callable backend service that is
independent from FastAPI and HTTP. Each call renders exactly one PDF page to an
RGB PNG. Page numbers are one-based, default to page `1`, and may select another
page explicitly through an internal call. The default resolution is 150 DPI;
validated internal callers and tests may request another DPI.

Derived pages are stored without overwriting beneath:

```text
<PROCESSED_DIR>/pdf-pages/floor-plan-<floor_plan_id>/job-<processing_job_id>/page-<page_number padded to four digits>.png
```

The service returns a portable forward-slash reference plus the rendered page
metadata. It does not store that derived reference in a new database table. The
configured processed directory must remain outside `<UPLOAD_DIR>/originals`, and
source resolution accepts only a persisted relative PDF reference beneath that
originals directory. Original PDF bytes and floor-plan metadata remain unchanged.

Before conversion, the higher-level callable commits the job as `processing`.
Success leaves the broader analysis job in `processing`, because G1 is only one
stage and does not imply complete analysis. A conversion failure commits only
`Floor-plan PDF conversion failed.` and marks the job `failed`; renderer details,
paths, stack traces, and SQL are not persisted or exposed.

No worker invokes G1 automatically, and F2 remains a job-creation endpoint only.
G2 consumes either G1 output or uploaded raster input through a separate callable;
OpenCV, AI inference, and schema expansion remain unimplemented.

## Image normalization

G2 adds `app.services.image_normalization`. Its low-level boundary uses only
filesystem paths and scalar values; its higher-level boundary validates an
existing floor plan and processing job. It accepts uploaded JPEG/PNG originals
or a strictly validated G1 `ConvertedPdfPage`/portable reference. G2 loads G1
output but never invokes G1 automatically.

Normalization fully decodes JPEG/PNG data, treats decompression-bomb conditions
as safe failures, applies only declared EXIF orientation, composites transparent
pixels onto white, converts supported modes to RGB, and strips source EXIF and
unrelated metadata. Images are never upscaled. An oriented image whose longest
edge exceeds 4096 pixels is resized proportionally with Pillow LANCZOS.

Normalized output is written exclusively without overwriting to:

```text
<PROCESSED_DIR>/normalized/floor-plan-<floor_plan_id>/job-<processing_job_id>/image.png
```

The returned `NormalizedImage` records encoded, orientation-corrected, and final
dimensions plus orientation/resizing flags and output size. No
`processed_images` table or existing database column stores this result yet.
Original uploads and G1-rendered pages remain unchanged.

A queued job becomes `processing`; an already-processing job remains so. G2
preserves progress and leaves the job `processing` after success. Failure stores
only `Floor-plan image normalization failed.` and never persists Pillow errors,
paths, SQL, or stack traces. No API or worker invokes G2.

## OpenCV preprocessing

G3 adds `app.ai.preprocessing`, separate from FastAPI routes and the G2 service.
It uses `opencv-python-headless==4.14.0.94` and `numpy==2.5.2`; no GUI, CUDA,
Java, or system OpenCV dependency is required. Only the headless OpenCV wheel is
installed.

The exact stage order is:

```text
Normalized RGB PNG
    -> grayscale
    -> median noise reduction
    -> optional Gaussian blur
    -> binary threshold
```

`PreprocessingParameters` is a frozen, validated parameter contract. Defaults
are a median kernel of 3, Gaussian enabled with kernel 3 and sigma 0.0, Otsu
thresholding, fixed-threshold fallback value 127, no inversion, and no debug
output. Kernels must be odd integers from 3 through 31. Threshold mode may be
`otsu` or `fixed`; fixed values range from 0 through 255. Otsu records the
threshold selected from the image, while fixed mode records the configured
value. Inversion is opt-in.

The filesystem boundary accepts only a matching G2 `NormalizedImage` or exact
portable reference at:

```text
normalized/floor-plan-<id>/job-<id>/image.png
```

It validates IDs, PNG content, three-channel `uint8` data, dimensions, absolute
path agreement, and confinement beneath `PROCESSED_DIR`. The G2 image is read
without modification. Debug output is disabled by default. When enabled, each
single-channel stage is created exclusively beneath:

```text
<PROCESSED_DIR>/preprocessed/floor-plan-<id>/job-<id>/
```

The directory contains `grayscale.png`, `denoised.png`, optional `blurred.png`,
and `thresholded.png`. Existing artifacts are never overwritten, and a failed
multi-file write removes newly created G3 files.

The optional job wrapper requires an already-`processing`
`floor_plan_analysis` job. Success preserves status and progress because later
detection has not run. Failure stores only `Floor-plan preprocessing failed.`
and marks the job failed. No API, worker, or automatic F2/G2 invocation exists.
G3 deliberately excludes morphology, edges, contours, Hough transforms, wall
detection, YOLO, and geometry work. H1 is the next roadmap ticket.

## Wall-line detection prototype

H1 adds `app.ai.wall_detection`, an in-memory detector that consumes only G3's
`PreprocessedImage.thresholded` array. The prototype method is:

```text
G3 binary image
    -> Canny edge detection
    -> probabilistic Hough transform
    -> endpoint canonicalization
    -> exact-duplicate removal
    -> deterministic sorting and IDs
```

`WallDetectionParameters` is frozen and strictly validated. Prototype defaults
are Canny thresholds 50 and 200 with aperture 3; Hough rho 1.0 pixel, theta 1.0
degree, vote threshold 50, minimum line length 50 pixels, maximum gap 10 pixels,
and at most 2000 candidates. These values are evaluation defaults, not
electrical or architectural engineering conclusions.

Candidates use raw image coordinates: unit `pixel`, origin `top_left`, positive
x to the right, and positive y downward. Each segment's topmost endpoint comes
first, with the leftmost endpoint breaking a tie. Angles are normalized into
`[0, 180)`, public lengths and angles are rounded to six decimal places, and
coordinates are ordinary Python integers within the image bounds.

Exact canonical duplicates are removed without merging nearby or collinear
segments. Candidates sort by start y, start x, end y, and end x before receiving
one-based IDs. When unique results exceed `maximum_candidates`, only the first
deterministically sorted candidates are returned and `truncated` is true. Empty,
all-white, all-black, and no-line input validly return an empty tuple with
`truncated` false.

H1 candidates are unverified image-space suggestions, not confirmed walls. The
detector reads and writes no files, draws no previews, mutates no processing
state, and requires no FastAPI, SQLAlchemy, MySQL, API, schema, worker, or UI.
It does not infer wall thickness, pair or merge lines, convert scale, create
rooms, or persist geometry.

## Wall-coordinate normalization

H2 adds the pure `app.geometry` layer. It validates a complete H1 result and
converts each raw pixel endpoint with an explicit caller-supplied scale:

```text
meters_per_pixel = 1 / pixels_per_meter
metric_coordinate = pixel_coordinate / pixels_per_meter
```

There is no default scale. `pixels_per_meter` must be an ordinary positive,
finite integer or float for every conversion. The value `100` in examples is
illustrative only and is not measured project data. PDF rendering DPI is not an
architectural scale and is never used to infer one; a floor-plan calibration
workflow remains unimplemented.

The shared planar coordinate model uses meters, the normalized image's top-left
origin, x increasing right, and y increasing down. This preserves exact image
overlay alignment. Raw H1 endpoints, lengths, angles, candidate IDs, order, and
the source truncation flag remain attached unchanged. Metric endpoints are
converted from pixels, and metric length is derived from those endpoints.
Internal immutable objects keep full floating-point values; serialized metric
coordinates and lengths round to nine decimal places and normalize negative
zero. Output remains deterministic and JSON-serializable.

Illustrative serialized candidate at 100 pixels per meter:

```json
{
  "coordinate_system": {
    "unit": "meter",
    "origin": "image_top_left",
    "x_direction": "right",
    "y_direction": "down",
    "pixels_per_meter": 100.0,
    "image_width_pixels": 640,
    "image_height_pixels": 480,
    "width_meters": 6.4,
    "height_meters": 4.8
  },
  "source_truncated": false,
  "walls": [{
    "candidate_id": 1,
    "raw_pixels": {
      "start": {"x": 20, "y": 35},
      "end": {"x": 220, "y": 35},
      "length_pixels": 200.0,
      "angle_degrees": 0.0
    },
    "canonical": {
      "start": {"x": 0.2, "y": 0.35},
      "end": {"x": 2.2, "y": 0.35},
      "length_meters": 2.0,
      "angle_degrees": 0.0
    }
  }]
}
```

Future Konva and Three.js adapters must consume this same coordinate source. The
conceptual Three.js mapping is canonical x to Three.js x, canonical y to
Three.js z, and floor elevation to Three.js y; H2 implements no renderer or
adapter. H2 candidates remain unverified machine suggestions. It adds no OpenCV
execution, API, filesystem I/O, database table, persistence, scale inference,
wall merging/snapping/thickness, room geometry, worker, or job-state behavior.
K1 now supplies the complete cross-domain canonical document schema; see
`../docs/geometry.md`. K2 persists complete validated documents, and K3 exposes
the current document and new snapshot creation through the protected layout API.

## Layout snapshot persistence

K2 adds `layout_versions` as the thirteenth prototype table. Each append-only
row references a project, project floor, and source floor plan and stores a
complete schema-v1 canonical JSON document, a positive per-floor sequential
version, a nullable current marker, and a server timestamp. Saving locks the
project-floor row, validates document identity, clears the prior `TRUE` marker
to `NULL`, and inserts the new current snapshot in one transaction. Database
constraints enforce unique floor/version pairs and at most one current row per
floor. Selecting an older version changes only current markers; snapshot JSON
and creation timestamps remain unchanged.

The repository/service boundary supports save, exact-version reconstruction,
current-version reconstruction, ordered metadata history, and current-version
selection. Stored documents are reconstructed through the K1 validator, and
database or document failures expose only sanitized service errors. K2 itself
adds no HTTP operation and performs no floor-plan or derived-file writes.

K3 adds `GET` and `POST`
`/api/projects/{project_id}/floors/{project_floor_id}/layouts`. The owning
Designer may read and create snapshots; Admins may read but not save. `POST`
requires one complete strict K1 document, verifies its path and persisted-floor
identity, and delegates append-only creation to K2. Missing, inaccessible, or
cross-context resources share `LAYOUT_NOT_FOUND`; invalid semantic geometry is
`INVALID_LAYOUT_GEOMETRY`; storage failures use sanitized retrieval/save `503`
errors. K3 exposes neither history nor current-version selection and never
writes an original or derived floor-plan file.

K4 adds a frontend-only, read-only Konva consumer of the current-layout `GET`.
It does not call layout `POST`, add an API route, change any table, or modify
stored geometry. Aligned-blueprint display is allowed only for one unambiguous
wall/symbol processing-job provenance value whose decoded image dimensions
exactly match the canonical coordinate system; otherwise the frontend keeps a
neutral blueprint layer and reports the limitation safely.

K5 adds no backend production behavior. Its frontend keeps symbol movement in
the complete K1 `geometry.symbols[*].position` meter field, posts the complete
document through the existing K3 operation, and adopts the returned K2 current
snapshot. Every successful save therefore creates a new append-only layout
version. K3 has no expected-version, ETag, conditional-write, or idempotency-key
contract; frontend reconciliation after an uncertain response reduces duplicate
retries but does not provide atomic concurrent-edit protection.

## Wall-geometry persistence

H3 adds the `walls` table and the backend-only wall persistence service. Each
row stores exact `Decimal` values for the explicit pixels-per-meter scale, raw
pixel endpoints and length, canonical meter endpoints and length, and the
normalized angle. Required indexed foreign keys retain both floor-plan and
processing-job provenance. The floor association remains
`Wall -> FloorPlan -> ProjectFloor`; `walls` does not duplicate a project-floor
identifier.

Machine output is inserted only with status `detected`; the model also accepts
`verified` for later review work. Replacement locks the target floor plan,
validates that its `floor_plan_analysis` job is still `processing`, rejects
truncated or malformed H2 geometry, and protects any verified wall set. If no
verified rows exist, it deletes the prior detected set and inserts the complete
new set in one transaction. Repeating a result therefore replaces rather than
duplicates it, a newer job replaces older detected rows, and valid empty
geometry clears the detected set. Any database failure rolls back the whole
replacement.

Read-only retrieval returns immutable records ordered by candidate ID and row
ID, retaining `Decimal` values internally without executing OpenCV or H2
conversion. Successful persistence deliberately leaves both the processing job
and floor-plan processing status unchanged because later analysis stages remain
incomplete. H3 adds no route, HTTP wall API, review UI, confirmation/editing
service, worker connection, room/symbol persistence, or complete K1 geometry.

## YOLO model loading

I1 adds an isolated, lazy model loader under `app/ai/symbol_detection`. It reads
only `YOLO_MODEL_PATH`, resolves relative values from the repository root,
requires a readable local `.pt` file, and loads it through the official
`YOLO(model_path)` API. The example configuration points to
`models/yolo/electrical-symbols.pt`, but no trained model is included in this
repository.

Successful loads are held in a bounded, thread-safe process-local cache keyed by
canonical path. Class names are discovered from `model.names`; application code
does not assume a fixed electrical class set. Missing, invalid, or unloadable
models produce stable sanitized loader errors and do not crash FastAPI import.
I1 itself does not run inference, filter confidence, persist detections, update
jobs, or connect to a worker or HTTP route. I2 uses the loaded model only through
the isolated inference boundary below.

## Symbol inference

I2 accepts only a valid G3 `PreprocessedImage` and consumes its two-dimensional
binary `thresholded` array. It passes YOLO a separate contiguous three-channel
copy, never a file path or shared writable G3 memory. Prediction explicitly uses
`conf=0.0`, `max_det=300`, `verbose=False`, `save=False`, and `stream=False`.
The zero confidence floor preserves all finite model confidences for I3 instead
of applying `YOLO_CONFIDENCE_THRESHOLD` prematurely.

Validated immutable output remains in processed-image pixels with a top-left
origin and contains image dimensions, dynamic class ID/name, original
confidence, `x_min/y_min/x_max/y_max`, and a derived center. Empty detections are
successful. Exactly 300 results set `detection_limit_reached` so the cap is not
silent. A successful processing-job wrapper leaves status, progress, and error
unchanged; model or inference failure stores only
`Floor-plan symbol inference failed.`

I2 creates no detection rows or artifacts and adds no API, worker, drawing,
confidence classification, or automatic F2 orchestration. I3 owns the separate
classification boundary below.

## Symbol confidence classification

I3 applies the existing `YOLO_CONFIDENCE_THRESHOLD` application setting to a
validated I2 result without rerunning inference. The default is exactly `0.50`.
Each prediction at or above the selected threshold is wrapped with status
`detected`; each lower-confidence prediction is wrapped with `needs_review`.
Low-confidence predictions are preserved rather than discarded.

The result is immutable and retains every original `SymbolPrediction` object in
model order, including exact confidence, dynamic class metadata, bounding box,
and center. Image dimensions, the maximum-detection value, and the detection-cap
flag are copied unchanged. The pure boundary accepts an explicit threshold; a
configuration-aware boundary supports injected settings for tests.

I3 performs no database write, job transition, API operation, worker action, or
Designer confirmation. I4 owns the separate persistence boundary below.

## Detected-symbol persistence

I4 adds the eighth prototype table, `detected_symbols`, and backend-only
repository/service boundaries. Each row snapshots the original dynamic model
class, unrounded Python confidence, I3 threshold/status, processed-pixel box and
center, image dimensions, tuple order, detection maximum/cap flag, floor plan,
and processing-job provenance. No symbol-legend foreign key exists yet.

Processing jobs are machine-result versions. Repeating an unreviewed job validates the
complete result, locks its floor plan, deletes only that job's rows, inserts the
complete replacement, and commits once. A newer job preserves older job rows;
a valid empty result clears only its own version. Retrieval requires both floor
plan and job, returns immutable records ordered by one-based prediction index,
and does not rerun model loading, inference, or classification.

Once a job version has an associated J3 review event, J4 class correction, or
J5 manual symbol, I4 rejects
same-job replacement with a sanitized persistence error. This prevents the
append-only review history from being erased. Other processing-job versions
remain independently persistable.

Success leaves floor-plan and processing-job state unchanged. Failures roll back
the whole replacement and expose only stable sanitized errors. I4 adds no API,
worker or job completion.
J1 exposes the persisted results through the read-only endpoint documented
below. J1A provides the aligned blueprint reference consumed by the J2
frontend; J3 adds the review-decision boundary documented below.

## Approved symbol legend foundation

J3A adds `symbol_legends` as the tenth prototype table. Each row has a unique
nonnegative model/dataset `class_id`, a unique normalized name using the
case-sensitive `utf8mb4_bin` collation, an active flag, and timestamps. The
active/class/ID index supports deterministic read-only retrieval. J3A adds no
Admin mutation endpoint, production seed, model loading, inference, or
classification correction. An empty catalog is valid until approved VED class
data is supplied.

## Detection classification corrections API

```http
PUT /api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/classification?processing_job_id={job_id}
Content-Type: application/json

{"symbol_legend_id": 12}
```

J4 adds `detection_class_corrections` as the eleventh prototype table. Only the
owning Designer may choose an active class returned by the approved legend
catalog. Each real change appends a positive sequence with immutable old/new
class ID and name snapshots plus their nullable legend references. Repeating
the authoritative class is idempotent. Choosing the original AI class makes it
authoritative again without deleting prior correction events.

The original class, confidence, geometry, machine status, and timestamps in
`detected_symbols` never change. J3 confirmation/rejection state is separate
and survives corrections. J1 bulk-loads the latest correction independently
from the latest review and returns both `original_class` and
`authoritative_class` plus a nullable correction summary. Missing, mismatched,
and cross-owner detections use a non-disclosing `404`; unavailable/inactive
legend choices use `409`; storage failures use a sanitized `503`.

## Manual symbol placement API

J5 adds `manual_symbols` as the twelfth prototype table and
`POST /api/floor-plans/{floor_plan_id}/manual-symbols?processing_job_id={job_id}`.
Only the owning Designer may place an active approved legend. The strict body
contains a client UUID, legend ID, and source-pixel center; class, status,
creator, and image dimensions are server-authoritative. The exact existing J1A
RGB PNG supplies trusted dimensions and is never generated or modified during
placement. Identical UUID retries return the existing record with HTTP 200;
new rows return 201 and conflicting reuse returns 409.

J1 returns manual records in a separate `manual_symbols` array. Persisted class
snapshots survive later legend changes. A renderer-independent service hands
confirmed detections (using J4's authoritative class) plus all manual symbols
to K1 in source pixels, excluding pending and deleted detections. K1 canonical
geometry converts those centers with H2 scale while preserving authoritative
class and source provenance. K2/K3 canonical persistence and current-layout API
access are implemented; actual 3D, routing, and quantity work remain
unimplemented.

## Detection results API

```http
GET /api/floor-plans/{floor_plan_id}/detections?processing_job_id={job_id}
```

The positive `processing_job_id` query parameter is required. Symbols come only
from that exact `floor_plan_analysis` job version; an empty requested version
returns `"symbols": []` and `"manual_symbols": []` and never falls back to older rows. Walls are H3's
current floor-plan wall set rather than a version selected by the query, and
each wall includes its own `processing_job_id` so differing provenance remains
visible.

Owning Designers may retrieve their projects, while Admins may retrieve any
project. Missing, mismatched, wrong-type, and cross-owner floor-plan/job
contexts share a sanitized `404`. Valid contexts with no stored results return
HTTP 200 with empty arrays. Database failures return a sanitized `503`.

The response contains nested raw-pixel and canonical-meter wall geometry plus
the original and authoritative symbol classes, confidence, I3 threshold/status, processed-pixel box
and center, image dimensions, detection-cap metadata, timestamps, and a nullable
latest `review` containing decision, sequence, and review timestamp, plus a
nullable latest `correction` containing old/new snapshots and correction time. The route
does not expose storage/model paths, rerun OpenCV or YOLO, classify confidence,
write files, or mutate floor-plan, job, wall, or symbol state.

## Detection review decisions API

```http
PUT /api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review?processing_job_id={job_id}
Content-Type: application/json

{"decision":"confirmed"}
```

Only the owning Designer may submit `confirmed` or `deleted`; Admins and other
roles receive `403`, while missing, mismatched, and cross-owner resources share
a non-disclosing `404`. Repeating the current decision returns it without a new
event. Reversing a decision appends the next positive sequence. The selected
detection is locked while sequence numbers are allocated and the transaction is
committed atomically. Failures roll back and return a sanitized `503`.

`detection_reviews` is the ninth prototype table. Its events are immutable and
reference both the original detected symbol and authenticated reviewer. Review
actions never overwrite `detected_symbols.status` or any original class,
confidence, threshold, geometry, timestamp, job, floor-plan, or file state.

## Detection review image API

```http
GET /api/floor-plans/{floor_plan_id}/review-image?processing_job_id={job_id}
```

J1A serves only the existing G2 normalized RGB PNG beneath `PROCESSED_DIR` for
an authorized exact floor-plan/job context. It validates containment, symlink
safety, PNG content, RGB mode, byte size, and G2 dimensions. Responses use
`image/png`, `Cache-Control: private, no-store`, and
`X-Content-Type-Options: nosniff`. It never runs G1/G2/G3, generates a missing
artifact, exposes a path, changes the original, or mutates database state.

`ultralytics-opencv-headless==8.4.131` is offered under AGPL-3.0, with a separate
Enterprise license available. Complete a licensing review before commercial or
production use.

## Error responses

Application-generated errors currently use FastAPI `HTTPException`, which
produces this response shape:

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

FastAPI request-validation failures use the framework's standard validation
detail array. The API therefore does not yet have one globally uniform top-level
error envelope.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`GET /health` returns:

```json
{
  "status": "ok",
  "service": "VED Electrical Services API"
}
```

Interactive OpenAPI documentation is available at `/docs` while the local
server is running.

## Verification

Run from `backend/` with the configured MySQL service and seeded roles
available:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_layout_versions -v
.\.venv\Scripts\python.exe -m unittest tests.test_layouts_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_detection_results_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_detection_reviews_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_detection_classifications_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_symbol_persistence -v
.\.venv\Scripts\python.exe -m unittest tests.test_processing_jobs -v
.\.venv\Scripts\python.exe -m unittest tests.test_processing_jobs_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_processing_job_status_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_pdf_conversion -v
.\.venv\Scripts\python.exe -m unittest tests.test_image_normalization -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
```

The current expected totals include 11 focused J4 classification-correction
tests, 9 focused J3A symbol-legend tests, 10 focused J1A tests, 15 focused J1
tests, 9 focused J3 tests, 15 focused I4 tests,
13 focused I3 tests, 25 focused I2 tests, 21 focused I1 tests, 21 focused H3
tests, 30 focused H2 tests, 32 focused H1 tests, 37 focused G3 tests, 38
focused G2 tests, 38 focused G1 tests, 11 focused F3 tests, 15 focused F2
regression tests, 17 focused F1 regression tests, 39 focused K1 tests, 17
focused K2 tests plus 27 subtests, 13 focused K3 tests plus 26 subtests, and
563 tests in the full `unittest` discovery run plus 479 subtests through L1.
The separate canonical-geometry pytest suite contains 39 tests, for 602
aggregate top-level backend tests; 602 is not a single discovery-run count. The required
H2/H3/J1/J4/J5 K1 regression batch
contains 85 tests plus 63 subtests.
The existing
Starlette TestClient/httpx deprecation warning does not by itself indicate a
test failure.
