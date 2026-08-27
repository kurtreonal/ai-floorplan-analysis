# VED Electrical Services API

This directory contains the FastAPI backend implemented through G2. It
provides application liveness, OAuth/OIDC authentication with signed local
sessions, database-authoritative role authorization, project APIs,
project-floor APIs, original floor-plan upload validation and storage, and
persisted processing-job records, the owning-Designer start-processing endpoint,
and an ownership-aware processing-status endpoint. A backend-only PDF-to-PNG
and a backend-only image-normalization service are also implemented. Workers,
OpenCV/YOLO processing, canonical geometry, routing, estimation, and reporting
are not implemented.

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
The current prototype has these six application tables:

```text
roles
users
projects
project_floors
floor_plans
processing_jobs
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
```

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
H3 persistence remains unimplemented, and K1 still owns the complete
cross-domain canonical project geometry schema.

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
.\.venv\Scripts\python.exe -m unittest tests.test_processing_jobs -v
.\.venv\Scripts\python.exe -m unittest tests.test_processing_jobs_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_processing_job_status_api -v
.\.venv\Scripts\python.exe -m unittest tests.test_pdf_conversion -v
.\.venv\Scripts\python.exe -m unittest tests.test_image_normalization -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
```

The current expected totals are 38 focused G2 tests, 38 focused G1 tests,
11 focused F3 tests, 15 focused F2 regression tests, 17 focused F1 regression
tests, and 276 full backend tests. The existing
Starlette TestClient/httpx deprecation warning does not by itself indicate a
test failure.
