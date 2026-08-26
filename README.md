# VED Electrical Services

AI-driven floor plan analysis, 2D/3D visualization, electrical routing, material quantification, and cost estimation system for VED Electrical Services.

## Development Status

**Implemented and verified through E4, including the E3A project-floor prerequisite.**

The repository currently includes:

- repository and environment foundations;
- a React/Vite JavaScript frontend and FastAPI backend;
- SQLAlchemy/PyMySQL connectivity and the five-table MySQL prototype schema;
- OAuth 2.0/OpenID Connect authentication with signed local sessions;
- database-authoritative `ADMIN` and `DESIGNER` roles;
- project create, list, and detail APIs plus the project dashboard;
- project-floor list/create APIs;
- JPEG, PNG, and PDF validation;
- collision-safe original-file storage and compensating cleanup;
- the floor-plan upload API and project-workspace upload UI.

Implementation must continue incrementally through the tickets in
`docs/FUNCTIONAL_SPEC.md`; completing E4 does not imply that the downstream AI,
geometry, routing, estimation, or reporting pipeline exists.

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

Tickets A1–A4, B1–B5, C1–C6, D1–D4, E1–E4, and the E3A
project-floor prerequisite are implemented. F1 and all later functional tickets
remain unimplemented.

The next ticket must be chosen explicitly. Do not silently add a floor-plan
listing API or begin processing jobs as part of unrelated work.

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
- Processing jobs and processing-status APIs are not implemented.
- No OpenCV or YOLO processing pipeline is implemented.
- Canonical geometry and the Konva 2D/Three.js 3D editors are not implemented.
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
