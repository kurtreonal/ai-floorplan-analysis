# VED Electrical Services

AI-driven floor plan analysis, 2D/3D visualization, electrical routing, material quantification, and cost estimation system for VED Electrical Services.

## Development Status

**Pre-development / repository foundation**

The project documentation is prepared. Implementation should proceed incrementally through the tickets defined in `docs/FUNCTIONAL_SPEC.md`.

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
- Alembic
- MySQL

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

## Initial Development Order

Start with the repository and development foundation:

```text
A1 Repository Foundation
  ↓
A2 Environment Configuration
  ↓
A3 React + JavaScript + Vite
  ↓
A4 FastAPI Foundation
```

Then continue through the database, authentication, projects, uploads, processing jobs, OpenCV, YOLO, detection review, canonical geometry, 2D, 3D, routing, estimation, reporting, and testing tickets defined in `docs/FUNCTIONAL_SPEC.md`.

---

## Inputs That Are Not Required for Ticket A1 but Will Be Needed Later

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
