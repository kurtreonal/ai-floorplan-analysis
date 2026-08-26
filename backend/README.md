# VED Electrical Services API

This directory contains the FastAPI backend implemented through F1. It
provides application liveness, OAuth/OIDC authentication with signed local
sessions, database-authoritative role authorization, project APIs,
project-floor APIs, original floor-plan upload validation and storage, and
persisted processing-job records. Processing endpoints, workers, AI/CV,
canonical geometry, routing, estimation, and reporting are not implemented.

## Requirements

- Python 3.13.7
- MySQL-compatible development server (XAMPP is the preferred Windows workflow)
- The dependencies pinned in `requirements.txt`

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

- `DESIGNER` can create projects, create floors for owned projects, and upload
  floor plans to owned project floors.
- `DESIGNER` project access is owner-scoped; cross-owner access returns `404`
  to conceal resource existence.
- `ADMIN` can list and inspect all projects and list their floors.
- `ADMIN` cannot create projects, create floors, or upload floor plans through
  the current API.
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

F1 stores records only. It does not create a start-processing endpoint, a
job-status endpoint, a worker or queue, automatic job creation after upload, or
AI/CV behavior. Creating a job does not change `floor_plans.processing_status`.

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
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
```

The current expected totals are 17 focused F1 tests and 174 full backend tests.
The existing Starlette TestClient/httpx deprecation warning does not by itself
indicate a test failure.
