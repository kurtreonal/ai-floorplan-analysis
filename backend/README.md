# VED Electrical Services API

This directory contains the FastAPI backend implemented through G1. It
provides application liveness, OAuth/OIDC authentication with signed local
sessions, database-authoritative role authorization, project APIs,
project-floor APIs, original floor-plan upload validation and storage, and
persisted processing-job records, the owning-Designer start-processing endpoint,
and an ownership-aware processing-status endpoint. A backend-only PDF-to-PNG
service is also implemented. Workers, OpenCV/YOLO processing, canonical geometry,
routing, estimation, and reporting are not implemented.

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
G2 normalization, raster-image handling, OpenCV, AI inference, and schema
expansion remain unimplemented.

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
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
```

The current expected totals are 38 focused G1 tests, 11 focused F3 tests,
15 focused F2 regression tests, 17 focused F1 regression tests, and 238 full
backend tests. The existing
Starlette TestClient/httpx deprecation warning does not by itself indicate a
test failure.
