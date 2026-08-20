# AGENTS.md

# VED Electrical Services — Codex / Agent Instructions

This file defines repository-wide instructions for AI coding agents working on the **VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation** project.

These instructions apply to the whole repository unless a deeper `AGENTS.md` file explicitly overrides a rule for a subdirectory.

---

## 1. Project Purpose

This project is a web-based electrical planning and estimation system for VED Electrical Services.

The main workflow is:

```text
User Login
    ↓
Create/Open Project
    ↓
Upload Floor Plan
    ↓
Validate Input
    ↓
Preprocess Image
    ↓
Detect Walls / Boundaries
    ↓
Detect Electrical Symbols
    ↓
User Reviews / Corrects AI Results
    ↓
Generate Shared Canonical Geometry
    ↓
Render Editable 2D Layout
    ↓
Render Synchronized 3D Layout
    ↓
Calculate Electrical Routing
    ↓
Calculate Material Quantities
    ↓
Generate Cost Estimate
    ↓
Generate PDF Report
```

The application is a **planning and estimation tool**. Do not represent automatically generated layouts as permit-ready or professionally approved electrical plans.

---

# 2. Required Technology Stack

Agents must preserve this technology stack unless the user explicitly requests a change.

## Frontend

Use:

```text
JavaScript
React
Vite
React Router
Axios and/or TanStack Query
Konva.js / React-Konva
Three.js / React Three Fiber
React Hook Form
Zod
```

### Important JavaScript Rule

This project uses **JavaScript, not TypeScript**.

Do not migrate the project to TypeScript.

Do not create:

```text
.ts files
.tsx files
tsconfig.json
TypeScript interfaces
TypeScript-only syntax
```

Use:

```text
.js
.jsx
```

for frontend source files.

When type-like validation is required, prefer runtime validation through Zod, Pydantic on the backend, documented object shapes, and clear JavaScript naming.

---

## Backend

Use:

```text
Python
FastAPI
Uvicorn
Pydantic
SQLAlchemy
Alembic
MySQL
```

FastAPI is the required backend framework.

Do not introduce Flask unless the user explicitly asks for it.

---

## AI / Computer Vision

Use:

```text
Python
OpenCV
Ultralytics YOLO
NumPy
Pillow
PDF-to-image processing
```

The AI/CV pipeline should remain separate from HTTP route logic.

---

## 2D Visualization

Use:

```text
Konva.js
React-Konva
```

The 2D editor is responsible for displaying and editing:

```text
Original blueprint reference
Walls
Room boundaries
Electrical symbols
Wiring routes
Conduits
Selections / editing controls
```

---

## 3D Visualization

Use:

```text
Three.js
React Three Fiber
WebGL
```

The 3D viewer should consume the same canonical geometry used by the 2D editor.

Do not maintain a separate, unrelated 3D geometry model.

---

# 3. Repository Architecture

Preferred root structure:

```text
ved-electrical-services/
│
├── frontend/
├── backend/
├── models/
│   └── yolo/
├── storage/
├── docs/
├── scripts/
├── docker/
├── .env.example
├── .gitignore
├── AGENTS.md
├── README.md
└── docker-compose.yml
```

Do not reorganize the repository without a specific reason and explicit task scope.

---

# 4. Frontend Structure

Preferred frontend structure:

```text
frontend/
│
├── src/
│   ├── app/
│   ├── routes/
│   ├── components/
│   ├── features/
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── projects/
│   │   ├── floor-plans/
│   │   ├── processing/
│   │   ├── detection-review/
│   │   ├── editor-2d/
│   │   ├── viewer-3d/
│   │   ├── routing/
│   │   ├── estimation/
│   │   ├── reports/
│   │   └── admin/
│   ├── api/
│   ├── hooks/
│   ├── stores/
│   ├── utils/
│   └── assets/
│
├── package.json
└── vite.config.js
```

Use JavaScript files such as:

```text
App.jsx
main.jsx
ProjectPage.jsx
api.js
projectService.js
geometryUtils.js
```

Do not convert these files to `.tsx`.

---

# 5. Backend Structure

Preferred backend structure:

```text
backend/
│
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── projects.py
│   │       ├── floor_plans.py
│   │       ├── processing.py
│   │       ├── symbols.py
│   │       ├── layouts.py
│   │       ├── routing.py
│   │       ├── materials.py
│   │       ├── estimates.py
│   │       ├── reports.py
│   │       └── admin.py
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── ai/
│   │   ├── preprocessing/
│   │   ├── wall_detection/
│   │   ├── symbol_detection/
│   │   └── model_loader.py
│   ├── geometry/
│   │   ├── coordinates.py
│   │   ├── walls.py
│   │   ├── rooms.py
│   │   └── transforms.py
│   ├── routing/
│   │   ├── graph.py
│   │   ├── astar.py
│   │   ├── route_rules.py
│   │   └── measurements.py
│   └── reports/
│       ├── generator.py
│       └── templates/
├── alembic/
├── tests/
└── requirements.txt
```

---

# 6. Backend Layering Rules

Keep FastAPI route files thin.

Preferred flow:

```text
FastAPI Router
     ↓
Service Layer
     ↓
Repository Layer
     ↓
SQLAlchemy
     ↓
MySQL
```

Routes should primarily handle:

```text
Authentication dependencies
Request validation
Calling services
Returning responses
HTTP status codes
```

Routes should not contain large blocks of:

```text
SQL queries
Image processing
YOLO inference
A* pathfinding
Cost calculations
PDF generation
```

Move those responsibilities into dedicated modules.

---

# 7. Canonical Geometry Is the Core Data Contract

The 2D editor, 3D viewer, routing engine, and material estimator must use one shared geometry model.

Conceptual flow:

```text
AI Detection
     ↓
User Verification
     ↓
Canonical Geometry
     ├──→ Konva 2D
     ├──→ Three.js 3D
     ├──→ Routing Engine
     └──→ Material Calculation
```

Do not create independent geometry data for each module.

Example shape:

```json
{
  "project_id": 15,
  "floor_id": 2,
  "coordinate_system": {
    "unit": "meter",
    "pixels_per_meter": 100
  },
  "walls": [],
  "rooms": [],
  "symbols": [],
  "routes": []
}
```

The exact schema may evolve through migrations and documented API changes, but all dependent modules must stay synchronized.

---

# 8. Original Floor Plan Rule

Never overwrite or destructively edit the original uploaded floor plan.

Store original files separately from:

```text
Processed images
Thresholded images
Detection previews
AI result JSON
2D layout snapshots
3D metadata
Reports
```

Preferred storage structure:

```text
storage/
├── uploads/
│   └── originals/
├── processed/
├── detections/
├── previews/
└── reports/
```

---

# 9. Supported Upload Formats

The project supports:

```text
JPEG
JPG
PNG
PDF
```

Validate:

```text
File extension
MIME type
File integrity
File size
Image dimensions
PDF page availability
```

Do not rely on file extension alone.

The original file must remain unchanged after validation and processing.

---

# 10. AI Processing Pipeline

Keep the processing pipeline modular.

Preferred sequence:

```text
Input Validation
    ↓
PDF-to-Image Conversion when needed
    ↓
Image Normalization
    ↓
Grayscale Conversion
    ↓
Noise Reduction
    ↓
Gaussian Blur
    ↓
Thresholding
    ↓
Wall / Boundary Detection
    ↓
YOLO Symbol Detection
    ↓
Confidence Filtering
    ↓
Coordinate Normalization
    ↓
Persist Results
```

Do not put the full pipeline in a single FastAPI endpoint function.

---

# 11. Symbol Detection Rules

Initial electrical symbol categories should come from the approved VED symbol dataset.

Examples include:

```text
Power outlets
Wall switches
Lighting fixtures
Data connection ports
```

Do not invent new AI classes in application code when they are not represented by the trained model or approved symbol legend.

The default symbol-confidence threshold is:

```text
0.50
```

Keep the threshold configurable.

Low-confidence detections should remain reviewable instead of silently being accepted.

Useful states include:

```text
detected
confirmed
needs_review
corrected
manually_added
deleted
```

Preserve the original AI class and confidence when a user corrects a detection so accuracy evaluation remains possible.

---

# 12. Detection Review Rules

AI results are suggestions until verified by the Electrical Designer.

The UI must support:

```text
Confirm detection
Reject/delete detection
Correct classification
Move detected symbol
Add missing symbol
```

The user-corrected project geometry becomes the authoritative source for later:

```text
2D rendering
3D rendering
Routing
Material quantities
Cost estimates
Reports
```

Do not calculate final quantities directly from unverified raw YOLO output when verified layout data exists.

---

# 13. Konva 2D Rules

Use separate layers where practical:

```text
Layer 1 — Original blueprint
Layer 2 — Walls
Layer 3 — Room boundaries
Layer 4 — Electrical symbols
Layer 5 — Wiring
Layer 6 — Conduits
Layer 7 — Selection/editing UI
```

Do not permanently bake overlays into the uploaded blueprint image.

Persist model coordinates, not only temporary Konva node state.

When the user moves a symbol:

```text
Konva interaction
    ↓
Canonical geometry update
    ↓
Backend persistence
    ↓
3D viewer consumes updated geometry
```

---

# 14. Three.js Rules

The first priority is geometric accuracy.

Do not prioritize:

```text
Decorative furniture
Complex materials
Photorealistic lighting
Unnecessary post-processing
Visual effects
```

before these work correctly:

```text
Floor scale
Wall coordinates
Wall height
Wall thickness
Door/window positioning
Electrical symbol placement
2D/3D synchronization
Routing visualization
```

Required camera capabilities:

```text
Orbit
Pan
Zoom
Reset view
Top view
Perspective view
```

---

# 15. 2D-to-3D Mapping Rules

Conceptual mappings:

```text
2D wall line
    ↓
3D wall mesh

2D room polygon
    ↓
3D floor area

2D symbol coordinate
    ↓
3D device placement

2D / canonical route points
    ↓
3D conduit/wire path
```

Do not make Three.js parse raw YOLO results directly.

Correct:

```text
YOLO
  ↓
Detection normalization
  ↓
Verified canonical geometry
  ↓
Three.js
```

Avoid:

```text
YOLO
  ↓
Three.js-specific detection logic
```

---

# 16. Electrical Routing Rules

Use A* or the project's selected spatial pathfinding implementation for automated routes.

Routing must not simply draw a direct diagonal line between the panel and a device.

Routing inputs may include:

```text
Electrical panel position
Device position
Walls
Room boundaries
Obstacles
Floor
Elevation
Vertical connectors
Routing rules
```

Routing outputs should include:

```text
Ordered route points
Route segments
Horizontal length
Vertical length
Total length
Floor references
Segment type
Connected components
```

---

# 17. Ceiling and Wall Routing Behavior

Follow the project routing concept:

```text
Horizontal movement
    → route at ceiling/service level where applicable

Vertical movement
    → route up/down along or inside the relevant wall

Device drop
    → ceiling/service route then vertical wall drop

Device rise
    → wall rise toward ceiling/service level

Cross-room movement
    → use ceiling/service-level paths rather than arbitrary diagonal lines
```

Do not invent electrical engineering rules that are not defined by the project.

If a routing rule is ambiguous, isolate it as configuration or clearly mark it for professional validation rather than guessing.

---

# 18. Multi-Floor Routing

Support explicit vertical connections between floors.

Use concepts such as:

```text
floor_id
floor_number
elevation
vertical_connector
riser
route_start
route_end
```

Vertical movement must contribute to measured wire/conduit length.

Never create an impossible shortcut through floors when no valid vertical connector exists.

---

# 19. Material and Pricing Rules

Material prices must come from the database.

Never hard-code official prices in:

```text
React components
JavaScript constants
FastAPI routes
AI modules
Routing code
PDF templates
```

Recommended data areas:

```text
materials
material_prices
price_history
```

When generating an estimate, capture the unit price used at that moment.

Later Admin price changes must not silently modify previously generated estimate totals.

---

# 20. Cost Calculation Rules

Core formula:

```text
line_total = quantity × captured_unit_price
```

Estimate inputs should come from:

```text
Verified symbol quantities
Calculated wire lengths
Calculated conduit lengths
Material mapping rules
Stored material prices
```

Do not base cost estimation on visual Three.js mesh lengths when canonical route geometry is available.

Backend calculation is authoritative.

Frontend totals should display backend results rather than maintain a separate hidden calculation implementation.

---

# 21. Database Rules

Use:

```text
MySQL
SQLAlchemy
Alembic
```

Do not scatter raw SQL throughout the application.

Prefer:

```text
SQLAlchemy models
Repository methods
Service-layer business logic
Alembic migrations
```

Create migrations for schema changes.

Do not manually alter a development database and leave the migration history out of sync.

---

# 22. Core Database Areas

The project may contain tables similar to:

```text
roles
users

projects
project_floors
floor_plans

processing_jobs
processed_images

rooms
walls
doors
windows

symbol_legends
detected_symbols
manual_corrections

layout_versions

electrical_panels
wiring_routes
route_segments

materials
material_prices
price_history

estimates
estimate_items

reports

audit_logs
```

Do not create redundant tables that duplicate an existing domain concept without first inspecting the existing schema.

---

# 23. Authentication and Authorization

Required roles:

```text
ADMIN
DESIGNER
```

Authorization must be enforced by FastAPI.

Frontend hiding is only a UI convenience and is not sufficient security.

Examples:

```text
DESIGNER
- create projects
- upload floor plans
- edit authorized project layouts
- generate routes
- generate estimates
- generate reports

ADMIN
- manage users
- manage symbol legends
- manage materials
- update material prices
- inspect administrative records
```

Do not trust user IDs, project owner IDs, or role names supplied by the frontend without server-side validation.

---

# 24. API Design Rules

Prefer resource-oriented APIs.

Examples:

```text
/api/auth
/api/users
/api/projects
/api/projects/{project_id}/floors
/api/projects/{project_id}/floor-plans
/api/floor-plans/{floor_plan_id}/process
/api/processing-jobs/{job_id}
/api/floor-plans/{floor_plan_id}/detections
/api/projects/{project_id}/layouts
/api/projects/{project_id}/routes
/api/materials
/api/projects/{project_id}/estimates
/api/projects/{project_id}/reports
/api/admin
```

Use Pydantic request and response schemas.

Do not return raw SQLAlchemy models directly if a defined response schema exists.

---

# 25. Processing Job Rules

Long-running AI work should use explicit job states.

Use:

```text
queued
processing
completed
failed
cancelled
```

A processing request should not keep a normal HTTP request open for the full AI pipeline if the work is long-running.

The frontend should be able to check job progress/status.

Do not pretend progress is exact if the backend cannot actually measure it.

---

# 26. Error Response Rules

Use consistent API error structures where possible.

Example:

```json
{
  "error": {
    "code": "INVALID_FLOOR_PLAN",
    "message": "The uploaded floor plan does not meet processing requirements.",
    "details": {}
  }
}
```

Do not expose:

```text
Database credentials
JWT secrets
Python stack traces
Private filesystem paths
Model filesystem internals
SQL errors containing sensitive data
```

to normal frontend users.

---

# 27. Environment Configuration

Configuration should come from environment variables.

Expected variables may include:

```env
APP_ENV=development

API_HOST=0.0.0.0
API_PORT=8000

DATABASE_URL=mysql+pymysql://user:password@localhost:3306/ved_electrical

JWT_SECRET=
JWT_ALGORITHM=HS256

UPLOAD_DIR=storage/uploads
PROCESSED_DIR=storage/processed
REPORT_DIR=storage/reports

YOLO_MODEL_PATH=models/yolo/electrical-symbols.pt

FRONTEND_URL=http://localhost:5173
```

Never commit real credentials.

Keep `.env.example` safe for public version control.

---

# 28. JavaScript Coding Rules

Because this project uses JavaScript instead of TypeScript:

Use clear object shapes and consistent naming.

Prefer:

```javascript
export function normalizeWall(wall) {
  return {
    id: wall.id,
    start: {
      x: Number(wall.start.x),
      y: Number(wall.start.y),
    },
    end: {
      x: Number(wall.end.x),
      y: Number(wall.end.y),
    },
  };
}
```

Avoid introducing TypeScript syntax such as:

```typescript
interface Wall {}
type Project = {}
const value: string = ""
function foo(input: Wall): Project {}
```

Use runtime validation where needed.

Examples:

```text
Zod on frontend boundaries
Pydantic on backend boundaries
Explicit guards in JavaScript utilities
```

Do not add JSDoc type complexity merely to imitate TypeScript unless it clearly improves an existing JavaScript module.

---

# 29. React Rules

Use functional components.

Prefer hooks for local behavior.

Do not place all project state in one giant component.

Split features by responsibility.

Good boundaries include:

```text
Project workspace
Upload panel
Processing status
Detection review
2D editor
3D viewer
Routing controls
Estimate panel
Report panel
```

Keep API calls in dedicated API/service modules instead of scattering `fetch`/Axios calls throughout visual components.

---

# 30. State Management Rules

Use the simplest existing state strategy that satisfies the feature.

Prefer server-state tools for API-backed data when already installed.

Do not introduce a new global state library without checking the repository first.

Canonical project data persisted by FastAPI/MySQL remains authoritative.

Frontend state may be optimistic or temporary, but it must synchronize with the backend for saved project changes.

---

# 31. Testing Rules

Inspect the existing test setup before introducing a new framework.

For backend, prefer:

```text
pytest
FastAPI test client / HTTPX where already used
```

Frontend tests should follow the existing repository setup.

If no frontend test framework exists and a ticket explicitly requires adding one, keep the choice minimal and document it.

Important test areas include:

```text
Authentication
Authorization
Upload validation
Image preprocessing
Coordinate transformations
AI output normalization
2D-to-3D alignment
A* routing
Horizontal route length
Vertical route length
Multi-floor route length
Material quantities
Estimate calculations
Historical price snapshots
Report generation
```

Do not claim a test passed unless it was actually run.

---

# 32. Ticket-Based Development Rule

Large features must be split into small, isolated tasks.

Do not implement:

```text
Upload
AI
2D
3D
Routing
Costing
Reports
```

all in one change.

A ticket should normally have:

```text
One primary responsibility
Clear dependencies
Explicit files/modules involved
Acceptance criteria
Relevant tests
A defined stopping point
```

When the requested task is complete, stop.

Do not continue into the next roadmap phase unless the user explicitly asks.

---

# 33. Acceptance Criteria Rule

Before editing, identify the task's acceptance criteria.

After editing, report each applicable criterion as:

```text
PASS
FAIL
NOT TESTED
BLOCKED
```

Never mark `PASS` based only on visual inspection when the criterion requires a build, test, API call, migration, or calculation.

---

# 34. Required Agent Workflow

For every coding task:

## Step 1 — Inspect

Inspect existing relevant files first.

Determine:

```text
What feature owns the behavior?
What files already implement it?
What API/data contract exists?
What database tables exist?
What tests already exist?
What could break if this changes?
```

## Step 2 — Plan

State or internally establish the smallest implementation plan.

Do not rewrite unrelated modules.

## Step 3 — Implement

Make the smallest coherent change that satisfies the ticket.

## Step 4 — Verify

Run relevant commands.

Examples:

```text
Frontend build
Frontend tests
Backend tests
FastAPI endpoint checks
Alembic migration checks
Linting if configured
```

## Step 5 — Report

Summarize:

```text
Files changed
What changed
Tests run
Acceptance criteria status
Known limitations
```

---

# 35. Do Not Perform Unrelated Refactors

When fixing one feature:

Do not:

```text
Rename unrelated files
Rewrite the folder structure
Change API route naming globally
Change database naming conventions
Replace installed libraries
Migrate JavaScript to TypeScript
Replace FastAPI
Replace MySQL
Change 2D/3D libraries
```

unless required by the task.

Preserve working features.

---

# 36. Dependency Rules

Before adding a dependency:

1. Check whether an installed package already solves the need.
2. Confirm the dependency belongs to the required tech stack.
3. Avoid adding large overlapping libraries.
4. Keep frontend dependencies in `frontend/package.json`.
5. Keep Python dependencies in the backend dependency file used by the project.
6. Document new required environment/system dependencies.

Do not replace Konva with another 2D engine or Three.js with another 3D engine without explicit instruction.

---

# 37. PDF Report Rules

Reports should use stored project and estimate data.

A report should reference a specific estimate/version.

Do not regenerate historical costs using the newest material prices when downloading an old report.

Report language should identify outputs as planning/estimation results.

Do not state or imply that generated output is professionally approved unless that approval is explicitly stored and implemented as a real workflow.

---

# 38. Audit Rules

Important actions should be audit-ready.

Examples:

```text
USER_LOGIN
PROJECT_CREATED
FLOOR_PLAN_UPLOADED
ANALYSIS_STARTED
ANALYSIS_COMPLETED
ANALYSIS_FAILED
SYMBOL_CONFIRMED
SYMBOL_CORRECTED
SYMBOL_ADDED
SYMBOL_REMOVED
ROUTE_RECALCULATED
PRICE_UPDATED
ESTIMATE_GENERATED
REPORT_GENERATED
```

Do not log:

```text
Passwords
JWT secrets
Raw authentication tokens
Private environment variables
```

---

# 39. Performance Rules

Do not optimize blindly.

Prioritize correctness first in:

```text
Geometry
AI result persistence
2D/3D alignment
Routing
Measurements
Cost calculations
```

Avoid unnecessary React rerenders in large Konva/Three.js scenes.

Do not rebuild the complete 3D scene for trivial UI-only changes if the existing structure supports targeted updates.

Do not reload the YOLO model for every detected symbol.

---

# 40. Security Rules

Always validate:

```text
Authentication
Authorization
Project ownership/access
Uploaded file type
Uploaded file path
Database input
API request schema
Admin-only actions
```

Never trust the frontend for authorization.

Prevent path traversal in uploaded filenames and file-serving endpoints.

Use password hashing.

Keep secrets outside version control.

---

# 41. Development Priority

When multiple improvements are possible, prioritize in this order:

```text
1. Correct data model
2. Backend validation
3. Authentication / authorization
4. Original-file safety
5. Canonical geometry correctness
6. AI detection persistence
7. 2D accuracy
8. 3D alignment
9. Routing accuracy
10. Measurement accuracy
11. Cost-estimation accuracy
12. Report accuracy
13. UX refinement
14. Visual polish
```

Do not choose visual polish over broken geometry or calculations.

---

# 42. MVP Boundary

The MVP is complete only when the full workflow functions:

```text
Login
    ↓
Create project
    ↓
Upload plan
    ↓
Process plan
    ↓
Detect symbols
    ↓
Review/correct detections
    ↓
Save authoritative geometry
    ↓
Render 2D
    ↓
Render synchronized 3D
    ↓
Calculate routes
    ↓
Calculate material quantities
    ↓
Generate estimate
    ↓
Generate PDF report
```

Individual attractive screens do not mean the project is functionally complete.

---

# 43. When Requirements Are Ambiguous

Do not guess important domain behavior.

Especially avoid guessing:

```text
Electrical routing rules
Material conversion factors
Safety allowances
Wire sizing rules
Conduit sizing rules
Engineering compliance rules
Official company prices
AI model class mappings
```

If the repository or ticket does not define the required behavior, leave the rule configurable, document the gap, or ask for clarification.

---

# 44. Final Agent Principle

The system should follow this architecture:

```text
Floor Plan
   ↓
AI Interpretation
   ↓
Designer Verification
   ↓
Canonical Geometry
   ↓
2D + 3D Visualization
   ↓
Spatial Routing
   ↓
Material Quantification
   ↓
Cost Estimation
   ↓
PDF Report
```

The canonical verified project geometry is the shared source for downstream modules.

Do not let raw AI detections, Konva-specific state, or Three.js-specific state become competing sources of truth.

Most importantly:

```text
Use JavaScript for the frontend.
Do not migrate this project to TypeScript.
Use FastAPI for the backend.
Keep 2D and 3D synchronized through shared geometry.
Keep electrical-routing rules explicit and configurable.
Preserve original uploaded floor plans.
Keep cost calculations backend-authoritative.
Implement work as small, verifiable tickets.
```
