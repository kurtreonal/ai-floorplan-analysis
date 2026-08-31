# VED Electrical Services

AI-driven floor plan analysis, 2D/3D visualization, electrical routing, material quantification, and cost estimation system for VED Electrical Services.

## Development Status

**Implemented through K3, including the E3A, J1A, and J3A prerequisites.**

The current backend surface contains 21 OpenAPI operations.

The repository currently includes:

- repository and environment foundations;
- a React/Vite JavaScript frontend and FastAPI backend;
- SQLAlchemy/PyMySQL connectivity and the thirteen-table MySQL prototype schema;
- OAuth 2.0/OpenID Connect authentication with signed local sessions;
- database-authoritative `ADMIN` and `DESIGNER` roles;
- project create, list, and detail APIs plus the project dashboard;
- project-floor list/create APIs;
- JPEG, PNG, and PDF validation;
- collision-safe original-file storage and compensating cleanup;
- the floor-plan upload API and project-workspace upload UI;
- persisted processing-job records with constrained status and progress fields;
- an owning-Designer start-processing API that creates a durable queued job;
- a read-only processing-status API for owning Designers and Admins; and
- a Designer processing-status UI with sequential, abortable polling and safe
  terminal-state retry paths for uploads returned during the current session;
- a backend-only PDF-to-PNG conversion service using bundled PDFium through
  `pypdfium2`, with safe job-failure persistence and separate derived storage;
- a Pillow-based image-normalization service for uploaded JPEG/PNG images and
  G1-rendered pages, producing metadata-free RGB PNG input for later G3 work;
- isolated OpenCV preprocessing and deterministic wall-line detection;
- explicit pixel-to-meter wall-coordinate normalization;
- atomic persistence and read-only retrieval of detected or verified wall
  geometry with floor-plan and processing-job provenance; and
- isolated YOLO model loading plus validated in-memory symbol inference from G3
  binary images; and
- immutable confidence classification and processing-job-versioned detected
  symbol persistence; and
- an ownership-aware, read-only detection-results API with explicit symbol-job
  version selection and current persisted wall geometry; and
- an authenticated, read-only review-image API that serves the existing G2
  normalized RGB PNG aligned with wall and symbol pixel coordinates; and
- a protected, read-only React-Konva detection-review canvas with separate
  blueprint, wall, symbol, and selection layers plus accessible inspection; and
- append-only, owner-scoped Designer confirmation/rejection decisions with
  immutable machine provenance, persisted latest-review retrieval, and a
  distinct visible rejected state; and
- a database-backed, active-only approved symbol legend catalog exposed through
  an authenticated read-only API. No production VED classes are guessed or
  seeded, so an unpopulated catalog validly returns an empty array; and
- append-only, owner-scoped Designer classification corrections selected from
  that approved catalog, with original AI provenance retained and the latest
  corrected class returned as authoritative for review; and
- owner-scoped, idempotent placement of missing symbols from the approved
  catalog on the normalized review image, with separate manual provenance,
  J1 retrieval, and a source-pixel authoritative-symbol handoff; and
- a versioned, renderer-independent canonical geometry contract with strict
  Python and JavaScript validation, pure H2-wall/J5-symbol adapters, explicit
  floor elevation, and one shared cross-runtime fixture; and
- append-only canonical layout snapshots with per-floor sequential versions,
  one nullable current marker, reconstruction validation, and transactional
  current-version switching; and
- an ownership-aware layout API that returns the current canonical snapshot and
  lets an owning Designer save a complete validated K1 document as the next K2
  version without modifying the original floor-plan file.

Implementation must continue incrementally through the tickets in
`docs/FUNCTIONAL_SPEC.md`; completing K3 does not imply that an editable layout,
3D, routing, estimation, or reporting exists.

Do **not** ask Codex to build the entire system in one prompt.

---

## Required Tech Stack

### Frontend

- JavaScript / JSX
- React
- Vite
- React Router
- Axios and/or TanStack Query
- Konva.js / React-Konva
- Three.js / React Three Fiber
- React Hook Form
- Zod

> This project uses **JavaScript, not TypeScript**.

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- PyMySQL
- MySQL

The prototype creates missing tables explicitly through SQLAlchemy metadata.
Alembic and production schema migrations remain deferred unless the project
architecture is explicitly changed.

### AI / Computer Vision

- OpenCV
- Ultralytics YOLO
- NumPy
- Pillow
- PDF-to-image processing

---

## Documentation Map

Codex and contributors should use the documentation in this order:

| File | Purpose | How Codex should use it |
|---|---|---|
| `AGENTS.md` | Repository-wide coding and agent rules | Read automatically / first. These rules control how work is performed. |
| `docs/FUNCTIONAL_SPEC.md` | Functional requirements, modules, tickets, acceptance criteria, development order | Primary implementation plan. Use the relevant ticket/section for the current task. |
| `docs/ARCHITECTURE.md` | FastAPI architecture, workflow, technology choices, APIs, database and AI design | Use when a ticket needs architectural context. |
| `docs/THESIS_SOURCE.md` | Markdown conversion of the original thesis/source manuscript | Reference-only source for project scope and academic requirements. Do not treat old Flask references as implementation instructions. |

### Documentation Priority

When implementation details differ between documents, use this priority:

```text
1. Current user instruction / active ticket
2. AGENTS.md
3. docs/FUNCTIONAL_SPEC.md
4. docs/ARCHITECTURE.md
5. docs/THESIS_SOURCE.md
```

`docs/THESIS_SOURCE.md` is retained as the academic source and may contain earlier architecture terminology such as Flask. The current implementation uses FastAPI.

---

## Core System Flow

```text
Login
  ↓
Create/Open Project
  ↓
Upload Floor Plan
  ↓
Validate and Preserve Original File
  ↓
OpenCV Preprocessing
  ↓
Wall / Boundary Detection
  ↓
YOLO Electrical Symbol Detection
  ↓
Designer Review and Correction
  ↓
Canonical Geometry
  ├──→ Konva 2D Editor
  ├──→ Three.js 3D Viewer
  ├──→ A* Spatial Routing
  └──→ Material Quantification
              ↓
        Cost Estimation
              ↓
          PDF Report
```

The verified canonical geometry is the shared source of truth for 2D, 3D, routing, material quantities, estimates, and reports.

---

## How to Work With Codex

Development should be ticket-based.

For each ticket:

1. Read `AGENTS.md`.
2. Read the relevant section/ticket in `docs/FUNCTIONAL_SPEC.md`.
3. Read only the relevant parts of `docs/ARCHITECTURE.md` when needed.
4. Inspect the existing repository before changing files.
5. Implement only the current ticket.
6. Run the required verification/tests.
7. Report each acceptance criterion as `PASS`, `FAIL`, `BLOCKED`, or `NOT TESTED`.
8. Do not continue into the next ticket automatically.
9. Review the diff before committing.
10. Commit the completed ticket before starting the next one.

Example Codex request:

```text
Implement TICKET A1 from docs/FUNCTIONAL_SPEC.md.

First read AGENTS.md and the relevant ticket.
Inspect the repository before making changes.

Implement only A1.
Do not begin A2 or later tickets.

Run the required verification and report:
- files changed
- commands/tests run
- each acceptance criterion as PASS/FAIL/BLOCKED/NOT TESTED
- known limitations
```

For larger or risky tickets, first ask Codex for an inspection-only plan before authorizing implementation.

---

## Current Roadmap Position

Tickets A1–A4, B1–B5, C1–C6, D1–D4, E1–E4, the E3A project-floor
prerequisite, F1–F4, G1–G3, H1–H3, I1–I4, J1, and the J1A review-image
prerequisite, J2, J3, the J3A approved-symbol-legend prerequisite, J4, J5, and
K1, K2, and K3 are implemented. K4 and all later tickets remain unimplemented.

The next ticket must be chosen explicitly. Do not silently add a floor-plan
listing API or processing-worker behavior as part of unrelated work.

---

## Inputs Needed by Later Tickets

Before the corresponding implementation stages, the project will also need real project assets/data such as:

- Approved VED electrical symbol legend/classes
- Annotated YOLO training/validation dataset
- Trained YOLO model weights
- Representative floor-plan test files
- Official material catalog and company pricing data
- Validated electrical routing/domain rules
- UI/Figma references if the frontend must match a specific approved design

These should be introduced when their tickets require them rather than blocking the repository-foundation work.

---

## Repository Structure Target

The application directories established by Ticket A1 are:

| Directory | Responsibility |
|---|---|
| `frontend/` | React and Vite frontend application code. |
| `backend/` | FastAPI backend application code. |
| `storage/` | Runtime uploads and generated artifacts; contents are not committed. |
| `docs/` | Functional, architecture, and project documentation. |
| `models/` | Local AI model artifacts and related resources. |
| `scripts/` | Development and operational helper scripts. |

The active frontend is located in `frontend/`, and the active backend is located
in `backend/`.

```text
ved-electrical-services/
├── AGENTS.md
├── README.md
├── docs/
│   ├── FUNCTIONAL_SPEC.md
│   ├── ARCHITECTURE.md
│   └── THESIS_SOURCE.md
├── frontend/
├── backend/
├── models/
├── storage/
├── scripts/
├── docker/
├── .env.example
├── .gitignore
└── docker-compose.yml
```

The folders that do not exist yet should be created by the appropriate development ticket instead of being pre-filled with unrelated implementation code.

---

## Important Boundaries

- Frontend uses JavaScript/JSX, not TypeScript.
- Backend uses FastAPI, not Flask.
- Original uploaded floor plans must remain unchanged.
- AI detections require Designer review before becoming authoritative project geometry.
- 2D and 3D must share the same canonical geometry.
- Electrical routing rules must be explicit and validated instead of guessed.
- Material prices come from the database.
- Historical estimates should preserve the price snapshot used when they were generated.
- Generated layouts and estimates are planning outputs and still require appropriate professional validation.

---

## Current Limitations

- `GET /api/projects/{project_id}/floor-plans` is not implemented. E4 can show
  successful upload responses during the current page session, but uploads do
  not repopulate after reload.
- Current-session upload cards can start processing and poll the job-status
  endpoint, but no worker, external queue, cancellation workflow, or automatic
  job creation exists. Without a worker, queued jobs do not advance
  automatically. Persisted results can be reviewed through the J2/J3 UI when a
  completed job and its normalized review image already exist.
- G1 can convert one selected PDF page to a separate PNG when called directly by
  backend code, but F2 does not invoke it automatically. Page numbers are
  one-based, page 1 is the default, and the default resolution is 150 DPI.
- G2 can normalize uploaded JPEG/PNG images or a validated G1 page when called
  directly. It applies EXIF orientation, composites transparency onto white,
  converts to RGB PNG, never upscales, and limits the longest edge to 4096
  pixels. No worker invokes it automatically and no processed-image metadata is
  persisted yet.
- G3 can run grayscale, median denoising, optional Gaussian blur, and Otsu or
  fixed binary thresholding on a validated G2 normalized PNG. Debug images are
  optional and isolated beneath `storage/processed/preprocessed`; no worker
  invokes G3 automatically. G3 does not perform wall detection or YOLO inference.
- H1 can detect unverified straight wall-line candidates from G3's in-memory
  binary image using Canny edges and a probabilistic Hough transform. Results
  use top-left-origin pixel coordinates and deterministic IDs, but are not
  persisted, scaled, merged into walls, or rendered in the UI.
- H2 can convert those raw candidates into meters when a caller explicitly
  supplies `pixels_per_meter`. Raw pixels remain attached for overlay alignment;
  the scale is never inferred from PDF DPI. These remain machine candidates,
  not automatically verified project geometry.
- H3 can atomically replace and later retrieve the current detected wall set for
  a floor plan without rerunning OpenCV. It rejects truncated geometry and will
  not overwrite verified walls. H3 adds no HTTP API, review UI, status-transition
  workflow, worker integration, room geometry, or complete K1 project geometry.
- I1 can lazily load and cache a configured local `.pt` detection model through
  `YOLO_MODEL_PATH`. Relative paths resolve from the repository root; the
  default example is `models/yolo/electrical-symbols.pt`. The repository does
  not include trained model weights, and a missing or invalid model produces a
  controlled, sanitized loader error rather than preventing application startup.
  Classes come from trained-model metadata; none are hard-coded.
- I2 consumes `PreprocessedImage.thresholded`, validates its binary pixel
  contract, and passes a separate contiguous three-channel copy to YOLO with
  `conf=0.0` and `max_det=300`. Immutable predictions retain processed-image
  pixel coordinates, dynamic class ID/name, original confidence, bounding box,
  and derived center. Empty inference is successful, and reaching the cap is
  explicit. Success leaves a processing job unchanged; failure stores only
  `Floor-plan symbol inference failed.` I2 adds no confidence filtering,
  detection persistence, route, worker, UI, or automatic pipeline; I3 owns the
  separate confidence classification described below.
- I3 classifies every immutable I2 prediction with the configured application
  confidence threshold, which defaults to `0.50`. Confidence equal to the
  threshold becomes `detected`; lower confidence becomes `needs_review` and is
  retained. Prediction order, exact confidence, class/geometry data, image
  dimensions, and detection-limit metadata remain unchanged. I3 is in-memory
  only and adds no job transition, API, worker, or review UI.
- I4 persists complete classified machine results in `detected_symbols`, keyed
  by processing job as an analysis version. Same-job reruns replace atomically,
  newer jobs preserve older versions, and empty results clear only their own
  job. Original class, confidence, pixel geometry, threshold, order, image, and
  detection-limit provenance remain retrievable without rerunning I1-I3. I4
  does not itself add a correction workflow, job completion, worker, or review UI.
- J1 exposes stored results through
  `GET /api/floor-plans/{floor_plan_id}/detections?processing_job_id={job_id}`.
  Owning Designers and Admins may read the exact requested symbol-job version;
  walls remain H3's current floor-plan wall set and retain their own job
  provenance. Empty stored results return empty arrays. J1 performs no AI rerun,
  filesystem write, state mutation, or Designer review action.
- J1A serves the existing G2 normalized blueprint reference through
  `GET /api/floor-plans/{floor_plan_id}/review-image?processing_job_id={job_id}`.
  It validates the authorized job and RGB PNG without generating or changing a
  file.
- J2 uses `konva` and `react-konva` to display that blueprint with current H3
  walls and the explicit J1 symbol-job version. It supports read-only selection,
  status/confidence inspection, an accessible DOM table, responsive shared
  scaling, safe retries, and request/object-URL cleanup.
- J3 adds `PUT /api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review`
  with the required `processing_job_id` query. Owning Designers can append
  `confirmed` or `deleted` decisions; identical repeats are idempotent and
  reversals append a new sequence. J1 returns only the latest review while the
  original machine status, class, confidence, geometry, and timestamps remain
  unchanged. Reviewed same-job I4 results cannot be replaced.
- J3A adds the tenth prototype table, `symbol_legends`, and authenticated
  `GET /api/symbol-legends` access for Designers and Admins. Only active rows
  are returned in deterministic class order. The repository contains no
  approved production VED class values, so the live catalog may remain empty;
  P3 still owns future Admin catalog management.
- J4 adds the eleventh prototype table, `detection_class_corrections`, and a
  Designer-only classification PUT endpoint. Corrections append old/new class
  snapshots, preserve the original AI class, and are independent from J3
  confirmation/rejection. J1 returns the latest correction and authoritative
  class. Selecting the current class is idempotent; returning to the original
  class removes no history and makes the original authoritative again.
  Correction history also blocks same-job I4 replacement. The review UI loads
  active legend values and safely disables correction when the catalog is empty.
  J5 extends same-job replacement protection when manual symbols exist.
- J5 adds the twelfth prototype table, `manual_symbols`, plus owning-Designer
  `POST /api/floor-plans/{floor_plan_id}/manual-symbols`. Placement requires an
  active approved legend and uses the exact existing J1A RGB PNG dimensions as
  source-pixel authority. Retry UUIDs make identical requests idempotent;
  conflicting reuse returns `409`. J1 returns manual records in a separate
  `manual_symbols` array. Confirmed detections with J4 authoritative classes
  and all manual records feed a renderer-independent source-pixel handoff for
  K1. No production classes are seeded, so an empty catalog disables placement.
- K1 defines canonical schema version 1 for one project floor, with shared
  walls, rooms, authoritative symbols, routes, coordinate metadata, and an
  explicit non-inferred floor elevation. It adds pure backend/frontend adapters
  but no API, database column, renderer, or persistence. See `docs/geometry.md`.
- K2 adds the thirteenth prototype table, `layout_versions`. Its backend-only
  service stores complete K1 documents as append-only JSON snapshots, assigns
  positive sequential versions while locking the project-floor row, and keeps
  exactly one current snapshot per floor through `TRUE`/`NULL` markers. History
  and prior geometry remain intact when the current marker changes. K2 adds no
  HTTP operation, editor, renderer, or change to original floor-plan files.
- K3 exposes the current snapshot at
  `GET /api/projects/{project_id}/floors/{project_floor_id}/layouts` to the
  owning Designer or an Admin. The matching `POST` accepts exactly one complete
  K1 canonical document from the owning Designer and creates the next K2
  snapshot. The API exposes no history or current-version-selection operation.
- `ultralytics-opencv-headless` is distributed under AGPL-3.0 with a separate
  Enterprise license option. Licensing must be reviewed before commercial or
  production deployment.
- Editable Konva 2D/Three.js 3D editors are not implemented.
  `project_floors` does not persist elevation; each K2 snapshot
  retains the explicit elevation inside its complete canonical document.
- Electrical routing, material quantification, cost estimation, and PDF reports
  are not implemented.
- The current Vercel deployment is frontend-only unless a separately hosted
  HTTPS FastAPI backend is configured.

---

## Production Deployment Checklist

The current Vercel project deploys the static React frontend only. A production
authentication flow also requires a separately deployed HTTPS FastAPI backend;
never point a public frontend build at `localhost`.

Before deploying:

- Use a dedicated production environment and database. Do not reuse local XAMPP credentials.
- Set `APP_ENV=production` and `APP_DEBUG=false` explicitly on the backend host.
- Generate unique production values for `OAUTH_CLIENT_SECRET` and `SESSION_SECRET`; never prefix secrets with `VITE_`.
- Keep `VITE_AUTH_ENABLED=false` for a frontend-only Vercel deployment. Set it to `true` only when a public HTTPS FastAPI backend is ready.
- When production authentication is enabled, set `VITE_API_BASE_URL` in Vercel to the public HTTPS FastAPI origin before building the frontend.
- Set `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` to the exact public frontend origin; never use `*` with credentialed requests.
- Register the exact production `/api/auth/callback` HTTPS URL with the OAuth/OIDC provider.
- Keep database, OAuth, and session secrets only in the deployment platforms' encrypted environment settings.
- Run `python scripts/validate_env.py`, backend tests, frontend lint, and the frontend production build.
- Confirm `/health`, login, callback, `/api/auth/me`, role authorization, logout, and post-logout `401` behavior on the deployed origins.
- Inspect the built frontend bundle for `localhost`, private URLs, source maps, and secret names before release.
- Confirm HTTPS, HSTS, credentialed CORS, secure cookies, logging redaction, and rollback procedures.

Repository protection:

- Enable GitHub secret scanning and push protection under **Settings → Security → Code security and analysis**.
- Protect `main` under **Settings → Branches**. Require pull requests, at least one approval, dismissal of stale approvals, conversation resolution, and the `Environment validation` and `Secret scan` status checks.
- Enable the tracked pre-commit hook once per clone with `powershell -File scripts/install_git_hooks.ps1`.
- Treat automated scanning as defense in depth. Rotate any exposed credential immediately, even if it is later removed from Git history.

Local OAuth development remains enabled through the ignored `frontend/.env.local`:

```env
VITE_AUTH_ENABLED=true
VITE_API_BASE_URL=http://localhost:8000
```
