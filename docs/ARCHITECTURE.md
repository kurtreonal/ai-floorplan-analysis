# Implementation Architecture

> **Authority and status**
>
> `docs/FUNCTIONAL_SPEC.md` owns ticket scope and acceptance criteria;
> `AGENTS.md` owns repository-wide implementation rules. This document records
> the architecture actually implemented through G1, including E3A, and labels
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

### Planned

G2 and later roadmap tickets remain unimplemented, including workers,
OpenCV/YOLO processing, detection review, canonical geometry, Konva
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
- Python `unittest` for the current backend suite

Prototype schema creation uses an explicit development-only
`Base.metadata.create_all()` command. Alembic and production migration tooling
remain deferred.

### AI/CV

G1 PDF-to-image conversion is implemented as a directly callable backend
service. OpenCV, NumPy, Ultralytics YOLO, normalization, model loading, wall
detection, and symbol inference remain planned. Processing-job persistence and
the F2/F3 job APIs exist, but no worker invokes G1. A queued job therefore does
not mean analysis is executing.

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

The live and SQLAlchemy model table set through F2 remains exactly:

```text
roles
users
projects
project_floors
floor_plans
processing_jobs
```

Relationships:

```text
roles 1 ── * users
users 1 ── * projects
projects 1 ── * project_floors
project_floors 1 ── * floor_plans
floor_plans 1 ── * processing_jobs
```

- `users` maps provider plus subject to a local role and contains no password.
- `projects.owner_id` identifies the authoritative Designer owner.
- `project_floors` supports multiple ordered floors per project.
- `floor_plans` stores upload metadata and a relative storage reference.
- `processing_jobs` stores a job type, constrained lifecycle status, bounded
  progress, a safe nullable error message, and timestamps for one floor plan.

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

## 10. Testing strategy and verified baseline

- Backend: Python `unittest`, including FastAPI TestClient and live
  MySQL-backed transactional tests
- Frontend: Vitest, Testing Library, and jsdom
- Static checks: frontend ESLint/build, Python compileall/pip check, environment
  template validation, OpenAPI/metadata inspection, and Git diff checks

The verified baseline through G1 is:

```text
F3 focused backend:    11 tests
F2 focused regression: 15 tests
F1 focused regression: 17 tests
G1 focused backend:     38 tests
Full backend:          238 tests
F4 API client:           21 tests
F4 component:            35 tests
Full frontend:          103 tests
```

The current Starlette TestClient/httpx combination emits a deprecation warning;
it does not currently hide test failures. Pytest belongs to a future testing
foundation ticket and is not installed for the current suite.

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
- G1 is callable by backend code but is not automatically invoked by F2; G2
  normalization remains unimplemented
- No OpenCV/YOLO pipeline
- No detection review or canonical geometry
- No 2D/3D editor implementation
- No routing or multi-floor route calculation
- No material pricing, estimates, reports, or audit logs
- Production Vercel deployment remains frontend-only without a separately
  deployed HTTPS FastAPI backend

The next roadmap dependency is G2 image normalization. A persistent floor-plan
listing API remains a separate proposed ticket and is not implied by G1.
