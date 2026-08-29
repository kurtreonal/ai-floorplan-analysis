# VED Electrical Services — Functional Specification & Codex Project Guide

> **Purpose of this file:**
> This document defines the project structure, system responsibilities, development boundaries, data flow, and implementation order for Codex before any major coding begins.
>
> Codex should treat this document as the primary implementation guide unless a newer project specification explicitly replaces a section.

---

# 1. Project Overview

## Project Name

**VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation**

## Project Type

Web-based electrical planning, floor-plan analysis, visualization, routing, and estimation system.

## Primary Goal

The system accepts residential or commercial floor plans and assists Electrical Designers by:

- Uploading floor plans in JPEG, PNG, or PDF format.
- Processing floor plans using Computer Vision.
- Detecting architectural boundaries.
- Detecting electrical symbols.
- Producing editable 2D layouts.
- Reconstructing the layout into an interactive 3D environment.
- Calculating electrical wire and conduit routes.
- Calculating material quantities.
- Generating cost estimates.
- Producing PDF reports.
- Saving project history.
- Allowing administrators to maintain symbols and material prices.

The original thesis architecture specifies React.js, OpenCV, YOLOv8, Konva.js, Three.js, A* pathfinding, SQL/MySQL, and a Python backend. The implementation will use **FastAPI instead of Flask**.

## Current Prototype Implementation Decisions

For the current prototype/development phase:

- **MySQL remains the required database.**
- The primary Windows local-development workflow uses **MySQL started from XAMPP**.
- FastAPI connects directly to MySQL through **SQLAlchemy ORM + PyMySQL**. Apache and PHP are not backend dependencies.
- `phpMyAdmin` may be used as an optional local administration tool for creating or inspecting the development database.
- The primary development database name is `ved_electrical`.
- Database schema creation during the prototype uses SQLAlchemy metadata (for example, `Base.metadata.create_all()`).
- **No Alembic or schema-migration workflow is required during the current prototype phase.** Development schema reset/recreation is allowed while the data model is still being tested.
- Authentication uses **OAuth 2.0 + OpenID Connect (OIDC)** with a configurable external identity provider.
- Local application passwords are not stored or verified by VED.
- MySQL stores the local application user record and VED authorization role (`ADMIN` or `DESIGNER`) after external identity verification.

XAMPP is a local-development convenience, not a production architecture requirement. A later deployment may use another MySQL host without changing the application's SQLAlchemy domain model.

## Current Implementation Status

The repository is implemented through J1, including the E3A project-floor
prerequisite introduced between E3 and E4.

Completed ticket areas:

```text
A1–A4
B1–B5
C1–C6
D1–D4
E1–E4
E3A — Project Floor API
F1 — Create Processing Jobs Table
F2 — Create Start Processing Endpoint
F3 — Create Processing Status Endpoint
F4 — Build Processing Status UI
G1 — Implement PDF-to-Image Conversion
G2 — Implement Image Normalization
G3 — Implement OpenCV Preprocessing Pipeline
H1 — Implement Wall-Line Detection Prototype
H2 — Normalize Wall Coordinates
H3 — Persist Wall Geometry
I1 — Implement YOLO Model Loader
I2 — Implement Symbol Inference Service
I3 — Implement Confidence Filtering
I4 — Persist Detected Symbols
J1 — Create Detection Results API
```

The implemented application includes authentication and signed sessions,
database-authoritative roles, project and project-floor workflows, upload
validation and original storage, the upload API, the project upload UI, and
persisted processing-job records, an owning-Designer endpoint that creates a
durable queued job, an ownership-aware read-only status endpoint, and a
current-session Designer processing UI, a backend-only PDF-to-PNG conversion
service, Pillow-based image normalization, OpenCV preprocessing, wall candidate
detection/normalization/persistence, configured YOLO loading, isolated symbol
inference, in-memory confidence classification, and processing-job-versioned
machine detection persistence, plus read-only detection-result retrieval. J2
and later tickets remain unimplemented. In
particular, there is no worker, external queue, automatic OpenCV/YOLO pipeline,
detection review canvas or mutation workflow,
canonical geometry,
2D/3D editor, routing, estimation, or report implementation.

`GET /api/projects/{project_id}/floor-plans` is not implemented. E4 displays
successful uploads returned during the current page session; records cannot
repopulate after reload until a separate floor-plan listing ticket is approved
and implemented.

---

# 2. Important Development Rule

**Do not implement the application as a collection of disconnected pages.**

All modules must operate around a shared project model.

The main project pipeline is:

```text
Project
   ↓
Floor Plan Upload
   ↓
Image Processing
   ↓
Wall / Boundary Detection
   ↓
Electrical Symbol Detection
   ↓
User Verification / Correction
   ↓
2D Layout
   ↓
3D Reconstruction
   ↓
Electrical Routing
   ↓
Material Quantification
   ↓
Cost Estimation
   ↓
Report Generation
```

The same project data must remain synchronized across the 2D editor, 3D viewer, routing engine, estimates, and reports.

---

# 3. Actors

## Electrical Designer / User

The Electrical Designer is the main project user.

Primary capabilities:

- Login.
- Create projects.
- Upload floor plans.
- Start floor-plan analysis.
- Review AI detections.
- Correct incorrectly detected symbols.
- Add missing symbols.
- Delete incorrect symbols.
- Modify the electrical layout.
- View 2D layouts.
- View 3D layouts.
- View electrical routing.
- Manually adjust wiring/conduits where supported.
- Generate material quantities.
- Generate cost estimates.
- Export reports.

The source document specifies that users must be able to manually edit the design when an outlet, switch, or other component needs to be changed.

## Admin / Project Engineer

Primary capabilities:

- Manage users.
- Manage electrical symbol legends.
- Manage material records.
- Update material prices.
- Review projects.
- Review estimates.
- View generated reports.
- Review system activity.
- Maintain reference symbol datasets.

The source architecture assigns management of symbols and material pricing to the Admin.

---

# 4. Technology Stack

## Frontend

```text
React
JavaScript
Vite
React Router
Axios or TanStack Query
Konva.js / React-Konva
Three.js / React Three Fiber
React Hook Form
Zod
```

### Frontend Responsibilities

React handles:

- Authentication UI.
- Dashboard.
- Project management.
- Floor-plan upload.
- Processing status.
- AI detection review.
- 2D editing.
- 3D visualization.
- Wiring visualization.
- Material tables.
- Cost estimates.
- Report viewing.
- Admin interfaces.

---

# 5. Backend

## Main Backend

```text
Python
FastAPI
Uvicorn
Pydantic
SQLAlchemy
PyMySQL
OAuth 2.0 / OpenID Connect (OIDC)
```

FastAPI replaces the Flask backend described in the original theoretical framework.

The backend is responsible for business logic and must not place business rules inside API route files.

Recommended separation:

```text
API Router
   ↓
Service
   ↓
Repository
   ↓
Database
```

AI processing should follow:

```text
API Router
   ↓
Processing Service
   ↓
AI / CV Pipeline
   ↓
Result Formatter
   ↓
Repository
   ↓
Database
```

---

# 6. AI and Computer Vision Stack

```text
Python
OpenCV
Ultralytics YOLO
NumPy
Pillow
PDF-to-image processing library
```

The source system uses image preprocessing followed by wall extraction and YOLO-based symbol recognition.

## Processing Pipeline

```text
Original Floor Plan
        ↓
Input Validation
        ↓
PDF → Image Conversion if required
        ↓
Image Normalization
        ↓
Grayscale
        ↓
Noise Reduction
        ↓
Gaussian Blur
        ↓
Thresholding
        ↓
Architectural Boundary Detection
        ↓
Wall Detection
        ↓
YOLO Symbol Detection
        ↓
Confidence Filtering
        ↓
Coordinate Normalization
        ↓
Structured JSON
```

---

# 7. AI Detection Scope

The initial model should recognize symbols used by VED Electrical Services.

Source-defined examples include:

```text
Power outlets
Wall switches
Lighting fixtures
Data connection ports
```

The source states that automatic recognition is intended for the standardized symbols used by VED Electrical Services rather than arbitrary architectural symbols from other firms.

Do not silently expand the detection classes beyond the approved dataset.

---

# 8. Confidence Handling

The source architecture uses:

```text
Confidence threshold = 0.50
```

Detections below the threshold should not automatically become confirmed electrical components.

Recommended detection states:

```text
detected
confirmed
needs_review
corrected
manually_added
deleted
```

[Inference] Keeping the original detection rather than immediately deleting rejected predictions would make accuracy testing and audit tracking easier.

---

# 9. 2D Layout System

## Technology

```text
Konva.js
or
React-Konva
```

The source architecture specifies Konva.js as the interactive 2D canvas technology.

## Layer Structure

Recommended canvas layers:

```text
Layer 1 — Original Blueprint
Layer 2 — Detected Walls
Layer 3 — Room Boundaries
Layer 4 — Electrical Symbols
Layer 5 — Wiring
Layer 6 — Conduits
Layer 7 — Selection / Editing UI
```

The original floor plan should remain unchanged.

The source explicitly states that the uploaded blueprint is used as a reference and should not be modified by the system.

---

# 10. Shared Geometry Model

This is one of the most important architectural requirements.

The 2D and 3D editors must **not maintain unrelated versions of the building geometry**.

Use one normalized project coordinate system.

Example:

```json
{
  "project_id": 15,
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

[Inference] Konva coordinates can be derived from this model for 2D rendering while Three.js coordinates can be derived from the same model for 3D rendering.

Target mapping:

```text
Canonical Geometry
       │
       ├────→ Konva 2D
       │
       ├────→ Three.js 3D
       │
       ├────→ Routing Engine
       │
       └────→ Material Calculation
```

---

# 11. 3D Visualization

## Technology

```text
Three.js
React Three Fiber
WebGL
```

Three.js is part of the source-defined architecture for reconstructing detected 2D floor plans into interactive 3D views.

## 3D Scene

The scene should support:

```text
Floor
Walls
Doors
Windows
Rooms
Electrical panel
Outlets
Switches
Lighting fixtures
Data ports
Wiring
Conduits
```

## Camera

Required interactions:

```text
Orbit
Pan
Zoom
Reset View
Top View
Perspective View
```

---

# 12. 2D → 3D Reconstruction

Expected transformation:

```text
2D wall line
      ↓
3D wall segment

2D room polygon
      ↓
3D floor area

2D symbol coordinate
      ↓
3D fixture position

2D electrical route
      ↓
3D conduit/wire route
```

Each wall should have metadata such as:

```json
{
  "id": 54,
  "start": {
    "x": 2.5,
    "y": 1.2
  },
  "end": {
    "x": 5.8,
    "y": 1.2
  },
  "height": 2.7,
  "thickness": 0.15
}
```

---

# 13. Electrical Routing

The source specifies an A* spatial routing algorithm for determining wiring paths and calculating total wire lengths.

## Routing Inputs

```text
Electrical panel location
Device location
Walls
Rooms
Structural boundaries
Route restrictions
Elevation
Floor level
```

## Routing Output

```text
Route coordinate points
Horizontal distance
Vertical distance
Total route distance
Route type
Connected devices
Required wire type
Required conduit type
```

---

# 14. Electrical Routing Rules

The electrical route should not simply draw a direct Euclidean line between components.

Routes need to represent realistic building movement.

[Inference] The routing engine should support rules such as:

```text
Horizontal routing → ceiling/service routing level

Vertical movement → inside or directly along wall paths

Device drop → ceiling route down through associated wall

Device rise → wall path upward toward ceiling/service route

Cross-room routing → ceiling/service level rather than diagonal paths through open space
```

These rules should remain configurable because final electrical implementation requires professional validation.

---

# 15. Multi-Floor Routing

The source identifies hidden vertical routes between floors as an important problem with traditional 2D planning.

The routing model therefore needs:

```text
floor_id
floor_number
elevation
vertical_connector
route_start
route_end
```

Example:

```text
Floor 1 Panel
      ↓
Vertical Riser
      ↓
Floor 2 Ceiling Route
      ↓
Wall Drop
      ↓
Outlet
```

Vertical distance must be included in material calculations.

---

# 16. Materials and Cost Estimation

The source cost-estimation module receives:

```text
Detected symbol quantities
+
Calculated wiring lengths
+
Official material prices
```

and produces an itemized Bill of Materials and total project estimate.

## Basic Formula

```text
Line Total = Quantity × Unit Price
```

Example:

```text
THHN Wire
Length: 135 m
Price: ₱25 / m

135 × 25 = ₱3,375
```

---

# 17. Pricing Rules

Material prices must come from the database.

Do not hard-code prices inside:

```text
React components
FastAPI endpoints
AI modules
Routing modules
PDF templates
```

Use:

```text
materials
material_prices
price_history
```

[Inference] Estimates should preserve the unit prices used when the estimate was created so later Admin price changes do not alter historical estimates.

---

# 18. Report Output

A completed project should be able to produce:

```text
Project information
Floor-plan information
Detected electrical components
Electrical component quantities
Wire lengths
Conduit lengths
Bill of Materials
Unit prices
Line totals
Overall estimated cost
2D layout reference
Optional 3D preview
Generation date
Prepared-by information
```

The source system explicitly includes an exportable PDF report as part of the System Output.

---

# 19. Database

Required database:

```text
MySQL
```

Primary Windows local-development workflow:

```text
XAMPP Control Panel
        ↓
Start MySQL
        ↓
MySQL at configured host/port
        ↓
PyMySQL
        ↓
SQLAlchemy ORM
        ↓
FastAPI
```

Default local development assumptions may use:

```text
Host: 127.0.0.1
Port: 3306
Database: ved_electrical
```

These values must remain environment-configurable. Database credentials must never be hard-coded in application source.

FastAPI connects directly to MySQL. Apache and PHP are not required by the FastAPI backend, and `phpMyAdmin` is only an optional local database administration interface.

Use:

```text
SQLAlchemy ORM
PyMySQL
SQLAlchemy metadata / Base.metadata.create_all()
```

For the current prototype, do not introduce Alembic or another schema-migration framework. While the schema is still being tested, the development database may be reset/recreated and the current tables recreated from SQLAlchemy models. Production-grade schema migration/versioning is deferred until explicitly requested.

Do not perform raw SQL throughout the application unless there is a specific performance requirement.

---

# 20. Core Database Tables

Recommended initial schema:

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

---

# 21. Important Relationships

```text
User
 └── Projects

Project
 ├── Project Floors
 ├── Floor Plans
 ├── Layout Versions
 ├── Wiring Routes
 ├── Estimates
 └── Reports

Floor Plan
 ├── Processing Jobs
 ├── Walls
 ├── Rooms
 └── Detected Symbols

Detected Symbol
 └── Symbol Legend

Estimate
 └── Estimate Items

Estimate Item
 └── Material
```

---

# 22. Project States

Recommended project lifecycle:

```text
draft

uploaded

processing

needs_review

layout_ready

routing_ready

estimated

report_ready

archived
```

Do not use UI assumptions to determine the actual project state.

The backend must remain the source of truth.

---

# 23. Processing Job States

AI operations should use explicit processing states:

```text
queued
processing
completed
failed
cancelled
```

Example:

```json
{
  "job_id": 218,
  "type": "floor_plan_analysis",
  "status": "processing",
  "progress": 72
}
```

This allows React to display meaningful progress instead of blocking the entire interface.

---

# 24. FastAPI Application Structure

```text
backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   │
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
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── floor_plan.py
│   │   ├── symbol.py
│   │   ├── layout.py
│   │   ├── routing.py
│   │   ├── material.py
│   │   ├── estimate.py
│   │   └── report.py
│   │
│   ├── schemas/
│   │
│   ├── repositories/
│   │
│   ├── services/
│   │   ├── project_service.py
│   │   ├── processing_service.py
│   │   ├── layout_service.py
│   │   ├── routing_service.py
│   │   ├── estimation_service.py
│   │   └── report_service.py
│   │
│   ├── ai/
│   │   ├── preprocessing/
│   │   ├── wall_detection/
│   │   ├── symbol_detection/
│   │   └── model_loader.py
│   │
│   ├── geometry/
│   │   ├── coordinates.py
│   │   ├── walls.py
│   │   ├── rooms.py
│   │   └── transforms.py
│   │
│   ├── routing/
│   │   ├── graph.py
│   │   ├── astar.py
│   │   ├── route_rules.py
│   │   └── measurements.py
│   │
│   └── reports/
│       ├── generator.py
│       └── templates/
│
├── tests/
│
└── requirements.txt
```

---

# 25. Frontend Structure

```text
frontend/
│
├── src/
│   │
│   ├── app/
│   │
│   ├── routes/
│   │
│   ├── components/
│   │
│   ├── features/
│   │   │
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
│   │
│   ├── api/
│   │
│   ├── hooks/
│   │
│   ├── stores/
│   │
│   ├── types/
│   │
│   ├── utils/
│   │
│   └── assets/
│
└── package.json
```

---

# 26. Storage Structure

Local development:

```text
storage/
│
├── uploads/
│   └── originals/
│
├── processed/
│
├── detections/
│
├── previews/
│
└── reports/
```

Do not overwrite the uploaded original.

Every generated resource should reference the corresponding project and floor plan.

---

# 27. Root Repository Structure

```text
ved-electrical-services/
│
├── frontend/
├── backend/
├── models/
│   └── yolo/
│
├── storage/
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── database.md
│   ├── geometry.md
│   ├── routing.md
│   └── ai-pipeline.md
│
├── scripts/
│
├── docker/
│
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml
```

---

# 28. Core API Groups

Codex should organize FastAPI routes around resources rather than individual UI pages.

```text
/api/auth

/api/users

/api/projects

/api/projects/{project_id}/floors

/api/projects/{project_id}/floor-plans

/api/floor-plans/{id}/process

/api/processing-jobs/{id}

/api/floor-plans/{id}/detections

/api/projects/{id}/layouts

/api/projects/{id}/routes

/api/materials

/api/projects/{id}/estimates

/api/projects/{id}/reports

/api/admin
```

---

# 29. Example Floor-Plan Processing Flow

```text
POST
/api/projects/25/floor-plans

          ↓

floor_plan_id = 81

          ↓

POST
/api/floor-plans/81/process

          ↓

processing_job_id = 103

          ↓

GET
/api/processing-jobs/103

          ↓

status = completed

          ↓

GET
/api/floor-plans/81/detections?processing_job_id=103

          ↓

React loads review/editor
```

---

# 30. Authentication and Authorization

Authentication uses:

```text
OAuth 2.0
+
OpenID Connect (OIDC)
```

The OAuth/OIDC provider must remain configurable until a concrete provider is selected.

Target authentication flow:

```text
React Sign In
      ↓
FastAPI /api/auth/login
      ↓
Configured OAuth/OIDC Provider
      ↓
FastAPI /api/auth/callback
      ↓
Validated External Identity
      ↓
Local MySQL User Record
      ↓
VED Role Authorization
```

VED does not require or store a local application password. External provider identity is mapped to a local `users` record using provider identity data such as provider name and provider subject identifier.

Required local application roles:

```text
ADMIN
DESIGNER
```

[Inference] A `PROJECT_ENGINEER` role can be introduced if responsibilities need to be separated from the Admin role later.

OAuth/OIDC establishes who the user is. The local MySQL role determines what the authenticated user may do inside VED.

Backend authorization must control protected actions. Hiding buttons in React is not sufficient authorization.

Security requirements include:

- OAuth/OIDC client secrets remain server-side.
- Provider tokens and authorization codes must not be written to normal application logs.
- OAuth state validation is required.
- OIDC nonce/identity-token validation must be applied when used by the selected provider flow.
- Authentication must not rely only on frontend state.
- Secrets remain outside version control.

Example:

```text
Designer
    can create projects
    can upload plans
    can modify own projects
    can generate estimates
    can generate reports

Admin
    can manage users
    can manage symbols
    can manage material prices
    can inspect project data
    can inspect audit history
```

---

# 31. Audit Requirements

Track important system actions.

Examples:

```text
USER_LOGIN

PROJECT_CREATED

FLOOR_PLAN_UPLOADED

ANALYSIS_STARTED

ANALYSIS_COMPLETED

SYMBOL_CORRECTED

SYMBOL_ADDED

SYMBOL_REMOVED

ROUTE_RECALCULATED

PRICE_UPDATED

ESTIMATE_GENERATED

REPORT_GENERATED
```

---

# 32. Error Handling

The implemented API does not yet have one globally uniform top-level error
envelope. Application-generated errors raised with FastAPI `HTTPException`
currently use:

```json
{
  "detail": {
    "error": {
      "code": "INVALID_FLOOR_PLAN",
      "message": "The uploaded floor plan does not meet processing requirements.",
      "details": {}
    }
  }
}
```

FastAPI request-validation failures use the framework's standard validation
detail array. A future error-contract ticket may unify these shapes, but current
documentation and clients must reflect the implemented responses.

Do not expose:

```text
SQL errors
Filesystem paths
Python stack traces
Secret values
Model filesystem locations
```

to normal users.

---

# 33. Upload Validation

Supported source formats from the thesis are:

```text
JPEG
PNG
PDF
```

Validation should check:

```text
Extension
MIME type
File integrity
File size
Image dimensions
PDF page availability
```

The source states that low-resolution and hand-drawn images are outside the intended operating scope.

---

# 34. Development Priorities

Codex should not attempt to build the entire system in one pass.

Follow this dependency order:

```text
01 — Repository Foundation

02 — Database

03 — FastAPI

04 — Authentication

05 — Project Management

06 — File Upload

07 — AI Processing Framework

08 — Symbol Detection

09 — Geometry Representation

10 — 2D Editor

11 — 3D Reconstruction

12 — Spatial Routing

13 — Material Quantification

14 — Cost Estimation

15 — Report Generation

16 — Admin Management

17 — Testing

18 — Deployment
```

---

# 35. Phase 1 — Foundation

Build:

```text
frontend/
backend/
storage/
docs/
```

Configure:

```text
React
JavaScript
Vite

FastAPI
SQLAlchemy
PyMySQL

MySQL (XAMPP for primary Windows local development)
```

Create:

```text
.env.example
.gitignore
README.md
```

Do not implement AI yet.

---

# 36. Phase 2 — Data Foundation

Implement:

```text
Users
Roles
Projects
Project Floors
Floor Plans
Materials
Pricing
```

Create and verify the required MySQL development schema from SQLAlchemy models before building dependent modules. During the prototype phase, schema reset/recreation is allowed instead of maintaining migration history.

---

# 37. Phase 3 — Project Workflow

Implement:

```text
Login
Dashboard
Create Project
Open Project
Upload Floor Plan
Project History
```

At this stage, uploaded plans may simply be displayed.

---

# 38. Phase 4 — AI Pipeline

Implement:

```text
Image loading
PDF conversion
Preprocessing
Wall detection
YOLO inference
Detection persistence
Confidence filtering
```

Do not connect cost estimation yet.

---

# 39. Phase 5 — Detection Review

Implement:

```text
Original blueprint
AI bounding boxes
Detected symbols
Confidence values
Confirm detection
Correct detection
Delete detection
Add missing symbol
```

The user-corrected version becomes the authoritative layout input.

---

# 40. Phase 6 — Geometry Engine

Convert accepted detection and structural information into a normalized geometry model.

Do not make Three.js parse raw YOLO output directly.

Correct:

```text
YOLO
 ↓
Normalized Geometry
 ↓
Three.js
```

Avoid:

```text
YOLO
 ↓
Three.js-specific custom logic
```

---

# 41. Phase 7 — 2D Editor

Implement:

```text
Blueprint background
Walls
Symbols
Selection
Dragging
Adding
Deleting
Wiring overlays
Save
Undo / redo if included
```

---

# 42. Phase 8 — 3D Viewer

Implement:

```text
Wall extrusion
Floor geometry
Electrical device placement
Camera controls
Layer visibility
2D/3D synchronization
```

The first target is accurate geometry.

Do not prioritize decorative materials, realistic lighting, or furniture before coordinate alignment works correctly.

---

# 43. Phase 9 — Spatial Routing

Implement:

```text
Routing graph
A*
Obstacles
Vertical routing
Ceiling paths
Wall drops
Route measurement
```

The source objective specifically requires routing to account for vertical elevation and structural obstructions.

---

# 44. Phase 10 — Cost Engine

Inputs:

```text
Confirmed electrical components
Calculated wire length
Calculated conduit length
Material rules
Database prices
```

Output:

```text
Bill of Materials
Material quantities
Unit prices
Totals
```

---

# 45. Phase 11 — Reporting

Generate a PDF containing project and estimation information.

Reports should reference a specific estimate version.

Do not calculate current prices again while downloading an old report.

---

# 46. Testing Requirements

Current implemented tooling:

```text
Backend:  Python unittest
Frontend: Vitest + Testing Library + jsdom
```

Run the current backend suite from `backend/` with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`pytest` is not declared as a direct project dependency in
`backend/requirements.txt`, although it may be present in a resolved development
environment through installed tooling or transitive dependencies. The current
suite remains `unittest`-style, and the documented canonical command uses
`unittest`. Ticket S1 below describes a future explicit pytest testing
foundation and must not be read as a claim about the current dependency file.

The thesis specifies:

- AI symbol recognition accuracy validation.
- Comparison of AI counts against manual counts.
- Unit testing.
- 3D spatial alignment validation.
- SQL-based cost calculation validation.
- ISO 25010 evaluation focusing on functional suitability, usability, and performance efficiency.

Recommended test directories:

```text
backend/tests/unit/
backend/tests/integration/
backend/tests/api/
backend/tests/ai/
backend/tests/routing/
backend/tests/estimation/

frontend/src/**/*.test.jsx
```

---

# 47. System Limitations From the Thesis

Codex must not accidentally expand functionality beyond the declared project scope.

The thesis currently states that:

```text
The system focuses on residential and commercial floor plans.

Automatic recognition is based on VED Electrical Services' standardized symbols.

Non-standard external symbols are outside automatic recognition.

Original uploaded blueprints must remain unchanged.

The system is a planning and estimation tool.

Generated electrical layouts still require professional review.

Low-resolution and hand-drawn plans are outside the intended detection scope.

Cost information does not automatically represent live market prices unless Admin updates the database.
```

---

# 48. Professional Validation Boundary

The system must not present generated layouts as final permit-ready engineering documents.

The thesis states that generated layouts and estimates must still be reviewed, validated, and signed by a Licensed Professional Engineer before actual installation or official permit use.

UI wording should therefore use terminology such as:

```text
Generated Layout

Planning Layout

Estimated Material Requirement

Estimated Project Cost
```

rather than representing outputs as professionally approved construction documents.

---

# 49. Coding Rules for Codex

When implementing this repository:

1. Inspect existing files before creating replacements.
2. Preserve working functionality unless the requested task explicitly changes it.
3. Do not duplicate business logic between frontend and backend.
4. Keep FastAPI routers thin.
5. Put business logic in services.
6. Put persistence logic in repositories.
7. Keep AI processing isolated from HTTP route code.
8. Keep routing algorithms isolated from UI rendering.
9. Use typed Pydantic schemas for API input/output.
10. Use JavaScript types for frontend domain models.
11. Do not hard-code database IDs.
12. Do not hard-code material prices.
13. Do not hard-code filesystem paths.
14. Use environment variables for configuration.
15. Do not overwrite original floor-plan uploads.
16. Keep 2D and 3D geometry synchronized through the shared geometry model.
17. Run relevant tests after modifying a module.
18. Do not refactor unrelated modules during focused tasks.

---

# 50. Environment Variables

Example:

```env
APP_ENV=development

API_HOST=0.0.0.0
API_PORT=8000

# XAMPP-friendly local MySQL example.
# Replace change_me only in the ignored local .env file.
DATABASE_URL=mysql+pymysql://root:change_me@127.0.0.1:3306/ved_electrical

# OAuth 2.0 / OpenID Connect
OAUTH_PROVIDER=configure_me
OAUTH_CLIENT_ID=change_me
OAUTH_CLIENT_SECRET=change_me
OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/callback
OAUTH_DISCOVERY_URL=change_me
OAUTH_SCOPES=openid profile email

# Application session/state protection
SESSION_SECRET=change_me

UPLOAD_DIR=storage/uploads
PROCESSED_DIR=storage/processed
REPORT_DIR=storage/reports

YOLO_MODEL_PATH=models/yolo/electrical-symbols.pt

FRONTEND_URL=http://localhost:5173
```

Real credentials must not be committed.

---

# 51. Definition of Done

A feature is not considered complete only because it renders in the browser.

A module is complete when applicable requirements are satisfied:

```text
UI implemented

API implemented

Validation implemented

Authorization implemented

Database/schema change implemented

Database persistence implemented

Loading state implemented

Error state implemented

Relevant tests implemented

No unrelated regressions found

Project documentation updated
```

---

# 52. MVP Definition

The minimum viable system should allow this complete workflow:

```text
User logs in
        ↓
Creates project
        ↓
Uploads floor plan
        ↓
System processes floor plan
        ↓
AI detects electrical symbols
        ↓
User reviews/corrects detections
        ↓
System builds editable 2D representation
        ↓
System generates synchronized 3D layout
        ↓
System calculates wiring routes
        ↓
System calculates material quantities
        ↓
Database pricing is applied
        ↓
System generates cost estimate
        ↓
System generates PDF report
```

If this complete pipeline does not work from beginning to end, the system should still be considered under development even if individual pages appear finished.

---

# 53. Codex Start-Up Checklist

Before making a major implementation change, Codex should determine:

```text
What module am I changing?

What existing files own this responsibility?

What API does it depend on?

What database entities does it depend on?

Does it affect the shared geometry model?

Does it affect both 2D and 3D?

Does it affect routing?

Does it affect estimates?

Does the MySQL development schema need to change?

What tests need to pass?
```

Then inspect the relevant repository files before editing.

---

# 54. Architecture Summary

```text
                       ┌───────────────────────┐
                       │         USER          │
                       │ Electrical Designer   │
                       └───────────┬───────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────┐
│                  REACT FRONTEND                      │
│                                                      │
│ Dashboard │ Projects │ Konva 2D │ Three.js 3D        │
│ Routing │ Estimation │ Reports │ Admin UI            │
└─────────────────────────┬────────────────────────────┘
                          │
                    REST / JSON
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│                    FASTAPI                           │
│                                                      │
│ Auth │ Projects │ Processing │ Layout │ Routing      │
│ Materials │ Estimates │ Reports │ Administration     │
└─────────────┬───────────────────────┬────────────────┘
              │                       │
              ▼                       ▼
┌────────────────────────┐   ┌─────────────────────────┐
│      AI / CV ENGINE    │   │     MYSQL DATABASE      │
│                        │   │                         │
│ OpenCV                 │   │ Users                   │
│ Wall Detection         │   │ Projects                │
│ YOLO                   │   │ Layouts                 │
│ Symbol Detection       │   │ Symbols                 │
└─────────────┬──────────┘   │ Routes                  │
              │              │ Materials               │
              ▼              │ Estimates               │
        Geometry Model       │ Reports                 │
              │              └─────────────────────────┘
       ┌──────┴──────┐
       │             │
       ▼             ▼
    Konva 2D     Three.js 3D
       │             │
       └──────┬──────┘
              │
              ▼
      Spatial Routing
              │
              ▼
     Material Quantity
              │
              ▼
      Cost Estimation
              │
              ▼
        PDF Report
```

---

# 55. Final Development Principle

The core architecture should remain:

```text
Floor Plan
   ↓
AI Interpretation
   ↓
Verified Geometry
   ↓
2D + 3D Visualization
   ↓
Spatial Routing
   ↓
Material Quantification
   ↓
Cost Estimation
   ↓
Report
```

**AI detection should assist the designer, while the verified project geometry becomes the authoritative source for later routing, visualization, material computation, and reports.**

This separation is important because the project explicitly supports manual correction of automatically generated layouts and uses those layouts as a planning and estimation tool rather than as an automatically approved engineering plan.

---

# 56. Codex Ticket Execution Rules

Codex should implement this project through **small, isolated tickets** instead of attempting large features in one pass.

Each ticket should:

1. Have one primary responsibility.
2. Touch the smallest reasonable set of files.
3. Define explicit inputs and outputs.
4. List dependencies on earlier tickets.
5. Include acceptance criteria that can be checked manually or through tests.
6. Avoid unrelated refactors.
7. Preserve existing working functionality.
8. Include or update tests where practical.
9. Update documentation when the ticket changes an API, schema, environment variable, or shared data contract.
10. Stop when the ticket scope is complete instead of continuing into the next feature automatically.

## Ticket Completion Format

For every completed ticket, Codex should report:

```text
Ticket:
Status:
Files changed:
Database/schema changes:
API changes:
Tests added/updated:
Manual verification performed:
Known limitations:
Next dependency:
```

A ticket is not complete until its acceptance criteria are satisfied.

---

# 57. Isolated Development Ticket Breakdown

## Epic A — Repository Foundation

### TICKET A1 — Create Root Repository Structure

**Goal:** Create the initial project directories without implementing application features.

**Dependencies:** None.

**Scope:**

```text
frontend/
backend/
storage/
docs/
models/
scripts/
```

**Acceptance Criteria:**

- [ ] All required root directories exist.
- [ ] No application feature code is added yet.
- [ ] `.gitignore` exists and excludes environment files, Python cache files, Node modules, uploaded files, generated reports, and local model artifacts where appropriate.
- [ ] `README.md` identifies the frontend and backend directories.
- [ ] Existing files are not deleted or replaced without a documented reason.

---

### TICKET A2 — Create Environment Configuration Template

**Goal:** Define environment variables required by the application.

**Dependencies:** A1.

**Acceptance Criteria:**

- [ ] `.env.example` exists.
- [ ] It contains database, API, frontend URL, upload directory, processed directory, report directory, OAuth/OIDC, session, and YOLO model settings.
- [ ] No real password, secret, API key, or private connection string is committed.
- [ ] Backend configuration reads values from environment variables rather than hard-coded paths.
- [ ] Missing variables that are mandatory for an active feature produce a clear configuration/startup error.

---

### TICKET A3 — Initialize React + JavaScript + Vite Frontend

**Goal:** Create a minimal runnable frontend.

**Dependencies:** A1.

**Acceptance Criteria:**

- [ ] React runs locally through Vite.
- [ ] JavaScript compilation succeeds.
- [ ] The application has a simple placeholder landing screen.
- [ ] No 2D, 3D, AI, or estimation logic is implemented yet.
- [ ] `npm run build` completes successfully.

---

### TICKET A4 — Initialize FastAPI Backend

**Goal:** Create a minimal FastAPI application.

**Dependencies:** A1, A2.

**Acceptance Criteria:**

- [ ] FastAPI starts successfully through Uvicorn.
- [ ] `GET /health` returns HTTP 200.
- [ ] Health response follows a documented JSON structure.
- [ ] API routes are separated from `main.py`.
- [ ] No business logic is placed in `main.py`.
- [ ] Backend dependencies are documented.

---

## Epic B — Database Foundation

### TICKET B1 — Configure SQLAlchemy MySQL Connection

**Goal:** Connect FastAPI to MySQL through SQLAlchemy and PyMySQL, using XAMPP-managed MySQL as the primary Windows local-development workflow.

**Dependencies:** A2, A4.

**Acceptance Criteria:**

- [ ] Database URL comes from environment configuration.
- [ ] Application can connect to the configured MySQL database.
- [ ] The documented primary Windows local workflow can connect to MySQL started from XAMPP.
- [ ] SQLAlchemy engine/session management is isolated in the backend core/database layer.
- [ ] PyMySQL is used as the MySQL DBAPI driver unless a later ticket explicitly changes it.
- [ ] A failed connection produces a clear application error without exposing credentials.
- [ ] No database credentials are hard-coded.
- [ ] Apache and PHP are not required by the FastAPI database connection.
- [ ] No Alembic or migration framework is introduced in this ticket.

---

### TICKET B2 — Initialize Development Database Schema

**Goal:** Create the current MySQL development schema from SQLAlchemy ORM models without introducing migration tooling.

**Dependencies:** B1.

**Acceptance Criteria:**

- [ ] MySQL remains the configured database.
- [ ] Schema definitions come from SQLAlchemy models.
- [ ] A controlled development initialization command/function can create missing tables using SQLAlchemy metadata.
- [ ] Running initialization against an empty `ved_electrical` development database creates the current required tables.
- [ ] Database credentials continue to come from environment configuration.
- [ ] No Alembic dependency, migration directory, or migration command is introduced.
- [ ] Development schema reset/recreation behavior is documented for the prototype phase.
- [ ] No production schema-migration guarantee is claimed during this prototype phase.

---

### TICKET B3 — Create OAuth Users and Roles Tables

**Goal:** Implement the local authorization schema used after OAuth/OIDC identity verification.

**Dependencies:** B2.

**Acceptance Criteria:**

- [ ] `roles` table exists.
- [ ] `users` table exists.
- [ ] A user does not require a local password or password-hash field.
- [ ] The user model can store an OAuth/OIDC provider identifier and provider subject/user identifier.
- [ ] Provider + provider subject uniquely identify an external identity.
- [ ] Email and display name can be stored when supplied by the configured identity provider.
- [ ] Optional avatar/profile image URL can be stored without making it mandatory.
- [ ] User references a valid local VED role.
- [ ] Initial roles include `ADMIN` and `DESIGNER`.
- [ ] The schema can be created successfully in the MySQL development database through the current SQLAlchemy schema initialization workflow.

---

### TICKET B4 — Create Projects Table

**Goal:** Persist project metadata.

**Dependencies:** B3.

**Acceptance Criteria:**

- [ ] `projects` table exists.
- [ ] Each project references its owner/creator.
- [ ] Project name, status, timestamps, and optional client/location metadata are supported.
- [ ] Project status uses a documented set of allowed states.
- [ ] The SQLAlchemy project model and constraints can be created successfully in the MySQL development schema.

---

### TICKET B5 — Create Project Floors and Floor Plans Tables

**Goal:** Support multiple floors and uploaded source plans.

**Dependencies:** B4.

**Acceptance Criteria:**

- [ ] `project_floors` table exists.
- [ ] `floor_plans` table exists.
- [ ] A project can have multiple floors.
- [ ] A floor can reference one or more uploaded floor-plan records if versioning is required.
- [ ] Original filename, stored filename/path, MIME type, file size, and processing status are stored.
- [ ] Original uploads are not overwritten.

---

## Epic C — Authentication and Authorization

### TICKET C1 — Configure OAuth/OIDC Authentication

**Goal:** Establish provider-configurable OAuth 2.0 / OpenID Connect authentication configuration for FastAPI.

**Dependencies:** B3.

**Acceptance Criteria:**

- [ ] OAuth/OIDC configuration comes from environment variables.
- [ ] Client ID is not hard-coded.
- [ ] Client secret is not hard-coded.
- [ ] Redirect URI is configurable.
- [ ] Provider/discovery configuration is configurable.
- [ ] Required OAuth/OIDC settings fail clearly when the authentication feature starts without them.
- [ ] Provider tokens and authorization codes are not logged.
- [ ] No local password authentication or password-hashing utility is introduced.

---

### TICKET C2 — Implement OAuth Login and Callback

**Goal:** Authenticate users through the configured OAuth/OIDC provider and resolve the verified identity to a local MySQL user.

**Dependencies:** C1.

**Acceptance Criteria:**

- [ ] `GET /api/auth/login` starts the OAuth/OIDC authorization flow.
- [ ] `GET /api/auth/callback` handles the configured provider callback.
- [ ] OAuth state is validated before accepting the callback.
- [ ] OIDC identity validation is applied when required by the selected provider flow.
- [ ] Invalid or failed authorization returns a controlled authentication error.
- [ ] Successful authentication resolves the external provider identity to a local MySQL user record.
- [ ] New valid external identities can create/link a local VED user according to a documented rule.
- [ ] No local password is requested or stored.
- [ ] OAuth client secrets are never returned to the frontend.
- [ ] Raw provider tokens and authorization codes are not logged.
- [ ] Login activity can be audited later without changing the endpoint contract.

---

### TICKET C3 — Implement Current User Endpoint

**Goal:** Allow the frontend to restore the authenticated VED application session.

**Dependencies:** C2.

**Acceptance Criteria:**

- [ ] `GET /api/auth/me` exists.
- [ ] Valid authentication returns current local user ID, name/display name, email when available, and VED role.
- [ ] Missing or invalid authentication returns HTTP 401.
- [ ] Protected route dependency is reusable by other routes.
- [ ] Provider tokens are not returned by `/api/auth/me`.

---

### TICKET C4 — Implement Role-Based Authorization

**Goal:** Restrict Admin and Designer actions using the local MySQL role after OAuth/OIDC authentication.

**Dependencies:** C3.

**Acceptance Criteria:**

- [ ] Reusable backend role-check dependency exists.
- [ ] Admin-only sample route rejects Designer accounts.
- [ ] Designer-accessible routes remain accessible to authorized Designers.
- [ ] OAuth/OIDC provider identity does not directly grant VED Admin privileges.
- [ ] Authorization does not rely only on hiding frontend controls.
- [ ] Authorization behavior has automated tests.

---

### TICKET C5 — Build Frontend OAuth Sign-In Screen

**Goal:** Connect React authentication UI to the FastAPI OAuth/OIDC flow.

**Dependencies:** A3, C2, C3.

**Acceptance Criteria:**

- [ ] Login screen provides a provider-neutral Sign In action.
- [ ] Sign In starts the backend OAuth/OIDC flow instead of collecting a local password.
- [ ] Successful authentication returns the user to the application.
- [ ] OAuth/OIDC errors display a readable error state.
- [ ] Authentication state can be restored using `/api/auth/me`.
- [ ] Protected frontend routes redirect unauthenticated users.
- [ ] OAuth client secrets and raw provider tokens are not exposed in browser logs.

---

### TICKET C6 — Implement Logout

**Goal:** End the local authenticated VED application session.

**Dependencies:** C2, C3.

**Acceptance Criteria:**

- [ ] Logout endpoint/action exists.
- [ ] The local authenticated application session is invalidated.
- [ ] `/api/auth/me` returns unauthenticated after logout.
- [ ] Frontend returns to the unauthenticated state.
- [ ] Logout does not modify unrelated external provider account data.

---

## Epic D — Project Management

### TICKET D1 — Create Project API

**Goal:** Allow authenticated Designers to create projects.

**Dependencies:** B4, C4.

**Acceptance Criteria:**

- [ ] `POST /api/projects` exists.
- [ ] Project owner comes from the authenticated user, not a user ID supplied blindly by the client.
- [ ] Required fields are validated.
- [ ] Created project is persisted.
- [ ] Response uses a typed Pydantic schema.
- [ ] Unauthorized creation is rejected.

---

### TICKET D2 — List User Projects API

**Goal:** Return projects accessible to the authenticated user.

**Dependencies:** D1.

**Acceptance Criteria:**

- [ ] `GET /api/projects` exists.
- [ ] Designer sees only projects they are authorized to view.
- [ ] Admin behavior is explicitly defined.
- [ ] Results include project status and updated timestamp.
- [ ] Empty project lists return an empty array instead of an error.

---

### TICKET D3 — Project Detail API

**Goal:** Load one project workspace.

**Dependencies:** D2.

**Acceptance Criteria:**

- [ ] `GET /api/projects/{project_id}` exists.
- [ ] Unauthorized project access returns 403 or 404 according to the chosen policy.
- [ ] Project metadata is returned.
- [ ] Response does not load unrelated large AI or geometry payloads unnecessarily.
- [ ] Invalid IDs are handled cleanly.

---

### TICKET D4 — Project Dashboard UI

**Goal:** Display and open projects from React.

**Dependencies:** D2, D3.

**Acceptance Criteria:**

- [ ] Dashboard lists available projects.
- [ ] User can create a project.
- [ ] User can open a project.
- [ ] Empty, loading, and error states are visible.
- [ ] Project status displayed in the UI comes from the backend.

---

## Epic E — Floor Plan Upload

### TICKET E1 — Implement Upload Validation Service

**Goal:** Validate JPEG, PNG, and PDF inputs before storage.

**Dependencies:** B5.

**Acceptance Criteria:**

- [ ] JPEG is supported.
- [ ] PNG is supported.
- [ ] PDF is supported.
- [ ] Unsupported file types are rejected.
- [ ] MIME type and extension are checked.
- [ ] Maximum file size is configurable.
- [ ] Corrupt images/PDFs return a clear validation error.
- [ ] Validation service is testable without an HTTP request.

---

### TICKET E2 — Implement Floor Plan Storage Service

**Goal:** Save original uploads safely.

**Dependencies:** E1, A2.

**Acceptance Criteria:**

- [ ] Original file is saved under the configured upload directory.
- [ ] Stored filenames avoid collisions.
- [ ] User-supplied filenames cannot escape the upload directory.
- [ ] Original files are never modified by later processing.
- [ ] Database stores metadata and the resulting storage reference.
- [ ] Failed storage does not leave an inconsistent successful database record.

---

### TICKET E3 — Create Floor Plan Upload API

**Goal:** Upload a plan into a specific project/floor.

**Dependencies:** E2, D3.

**Acceptance Criteria:**

- [ ] `POST /api/projects/{project_id}/floor-plans` exists.
- [ ] Upload requires project authorization.
- [ ] Valid file creates a `floor_plans` record.
- [ ] Invalid file returns a clear 4xx response.
- [ ] Response includes floor plan ID and processing status.
- [ ] Existing original uploads remain unchanged.

---

### TICKET E3A — Project Floor API

**Goal:** List and create the project floors required by the upload workflow.

**Dependencies:** B5, C4, D3, E3.

**Acceptance Criteria:**

- [ ] `GET /api/projects/{project_id}/floors` exists.
- [ ] `POST /api/projects/{project_id}/floors` exists.
- [ ] A Designer can list and create floors only for an owned project.
- [ ] Cross-owner Designer access returns `404`.
- [ ] An Admin can list project floors but cannot create them.
- [ ] An accessible project with no floors returns an empty array.
- [ ] Requests and responses use typed Pydantic schemas.
- [ ] Floor listing order is deterministic by `sort_order`, then ID.
- [ ] The ticket introduces no database schema change.

---

### TICKET E4 — Build Floor Plan Upload UI

**Goal:** Allow users to upload floor plans from the project workspace.

**Dependencies:** E3, E3A.

**Acceptance Criteria:**

- [ ] JPEG, PNG, and PDF are selectable.
- [ ] Unsupported files are blocked or clearly rejected.
- [ ] Upload progress/loading state is visible.
- [ ] Successful upload appears in the project workspace.
- [ ] Backend validation errors are shown to the user.
- [ ] Uploading does not automatically modify the original source image.

---

## Epic F — AI Processing Jobs

### TICKET F1 — Create Processing Jobs Table

**Goal:** Track long-running analysis operations.

**Dependencies:** B5.

**Implementation status:** Complete. F1 persists job records only; F2 owns
start-processing behavior.

Implemented database contract:

- `processing_jobs.floor_plan_id` is an indexed required foreign key to
  `floor_plans.id`.
- The database column `type` is exposed as the Python attribute `job_type` and
  remains open to future job types.
- `status` defaults to `queued` and is constrained by
  `ck_processing_jobs_status`.
- `progress` defaults to `0` and is constrained to 0–100 inclusive by
  `ck_processing_jobs_progress`.
- `error_message` is nullable; `created_at` and `updated_at` are
  server-generated.
- `FloorPlan.processing_jobs` and `ProcessingJob.floor_plan` form the
  bidirectional relationship.

No processing API, automatic upload hook, background worker, queue, or AI/CV
operation is part of F1.

**Acceptance Criteria:**

- [ ] `processing_jobs` table exists.
- [ ] Job stores type, status, progress, timestamps, and error message.
- [ ] Allowed states include `queued`, `processing`, `completed`, `failed`, and `cancelled`.
- [ ] Job references the relevant floor plan.
- [ ] The processing-jobs model can be created successfully in the current MySQL development schema.

---

### TICKET F2 — Create Start Processing Endpoint

**Goal:** Start analysis without blocking the initial request.

**Dependencies:** F1, E3.

**Implementation status:** Complete. F2 creates and commits a queued
`floor_plan_analysis` job, then returns immediately without running analysis.

Implemented behavior:

- `POST /api/floor-plans/{floor_plan_id}/process` accepts no request body and
  returns `202` with a typed `job_id` and `queued` status.
- Only the owning Designer may start processing. Admin and unsupported roles
  receive `403`; missing, inaccessible, and cross-owner records use sanitized
  responses without disclosing ownership.
- The authorized floor-plan row is locked with `SELECT ... FOR UPDATE` before
  checking active jobs. Existing `queued` or `processing` jobs return `409`;
  terminal jobs permit another attempt.
- The processing-job row is the durable queue entry. No worker or AI operation
  runs during F2.
- Failure-state persistence stores a stable safe message and does not modify the
  original upload or `floor_plans.processing_status`.
- Database creation failures roll back and return a sanitized `503`.

F2 does not add F3's status endpoint, a worker, an external queue, an automatic
upload hook, cancellation behavior, or a floor-plan listing endpoint.

**Acceptance Criteria:**

- [ ] `POST /api/floor-plans/{id}/process` exists.
- [ ] It checks floor-plan authorization.
- [ ] A processing job is created.
- [ ] Response returns a job ID.
- [ ] A second accidental request does not silently create uncontrolled duplicate processing.
- [ ] Job failure is persisted.

---

### TICKET F3 — Create Processing Status Endpoint

**Goal:** Allow the frontend to track job progress.

**Dependencies:** F2.

**Implementation status:** Complete. F3 adds a read-only status endpoint without
starting a worker or mutating processing state.

Implemented behavior:

- `GET /api/processing-jobs/{job_id}` returns only `job_id`, `type`, `status`,
  `progress`, and nullable `error_message`.
- Designers may read jobs belonging to their own projects; Admins may read any
  job. Missing and cross-owner jobs share a sanitized `404`.
- Unauthenticated requests receive `401`; unsupported roles receive `403`.
- Failed jobs return a stable generic error message. Raw stored errors, paths,
  SQL text, secrets, and stack traces are never returned.
- Repository reads select only public job fields, prohibit relationship lazy
  loading, acquire no row lock, and perform no writes.

F3 does not add a processing UI, worker, external queue, cancellation behavior,
automatic upload hook, AI/CV behavior, or floor-plan listing endpoint.

**Acceptance Criteria:**

- [ ] `GET /api/processing-jobs/{id}` exists.
- [ ] Response includes status and progress.
- [ ] Failed jobs include a safe error message.
- [ ] Internal stack traces and filesystem paths are not returned.
- [ ] Unauthorized job access is rejected.

---

### TICKET F4 — Build Processing Status UI

**Goal:** Show AI processing progress in React.

**Dependencies:** F3.

**Implementation status:** Complete. F4 adds frontend controls for starting and
monitoring jobs associated with upload responses retained in the current page
session. It adds no backend or OpenAPI operation.

Implemented behavior:

- Designer upload cards can start one F2 request at a time. Admins receive no
  processing controls.
- A valid F2 active-job conflict is adopted using only its positive integer job
  ID; malformed conflicts require an explicit new attempt.
- Queued and processing jobs show the exact F3 progress. Polling uses a
  sequential, abortable two-second timeout and never overlaps status requests.
- Polling stops on terminal states, unmount, session expiry, authorization or
  lookup failures, and temporary errors. Temporary failures preserve the job
  ID and offer an explicit status retry instead of retrying indefinitely.
- Completed jobs state that analysis review is a later feature. Failed and
  cancelled jobs offer a new F2 attempt; failed output uses only F3's sanitized
  nullable error message or a generic fallback.

F4 does not add persistent upload discovery, local storage, a worker, external
queue, cancellation endpoint, AI/CV processing, or result/review behavior.
Because no floor-plan listing endpoint exists, controls do not repopulate after
reload.

**Acceptance Criteria:**

- [ ] UI can start processing.
- [ ] UI displays queued/processing/completed/failed states.
- [ ] Completed processing triggers the next workflow state.
- [ ] Failed processing offers a clear retry path.
- [ ] The page does not freeze while analysis is running.

---

## Epic G — Image Preprocessing

### TICKET G1 — Implement PDF-to-Image Conversion

**Goal:** Convert supported PDF pages into processable raster images.

**Dependencies:** F2.

**Implementation status:** Complete. G1 adds an isolated backend service using
`pypdfium2==5.13.0` with bundled PDFium. It is callable without FastAPI, HTTP, or
a database connection at its low-level boundary.

Implemented behavior:

- Each call converts exactly one page to an RGB PNG. Page numbers are one-based,
  default to page 1, and reject zero, negative, or out-of-range values.
- Rendering defaults to 150 DPI. Validated internal callers may supply another
  DPI; neither page nor DPI selection is exposed through HTTP in G1.
- Output uses
  `pdf-pages/floor-plan-<id>/job-<id>/page-<NNNN>.png` beneath
  `PROCESSED_DIR`, and the returned reference uses forward slashes.
- Persisted source references must remain relative and resolve beneath
  `<UPLOAD_DIR>/originals`. The source must be a regular PDF with
  `application/pdf` metadata. Traversal, absolute paths, symlink escapes, and
  raster inputs are rejected.
- Rendering enforces a pre-allocation pixel limit, honors effective page
  rotation, encodes in memory, and writes exclusively without silently
  overwriting an existing derived page. Partial output is removed where safe.
- The higher-level callable commits the job as `processing` before conversion.
  Success leaves the broader job `processing`; it does not mark analysis
  complete or alter `floor_plans.processing_status`.
- Conversion failure commits `failed` with only
  `Floor-plan PDF conversion failed.` Raw renderer errors, paths, SQL, and stack
  traces are not persisted. Persistence failure is reported separately and
  safely.
- Original PDF bytes and floor-plan metadata remain unchanged. The derived path
  is returned to later orchestration and is not stored in a new table.

G1 is not automatically invoked by F2 because no worker exists. It adds no API,
schema, normalization, OpenCV, AI inference, or raster-input processing. G2 is
implemented as a separate downstream callable.

**Acceptance Criteria:**

- [ ] PDF conversion is isolated in a service/module.
- [ ] Output image path is separate from the original PDF.
- [ ] Original PDF remains unchanged.
- [ ] Conversion errors mark the processing job as failed.
- [ ] Page selection behavior is documented.
- [ ] Unit/integration test covers at least one valid PDF.

---

### TICKET G2 — Implement Image Normalization

**Goal:** Normalize image orientation and processing dimensions.

**Dependencies:** G1 for PDFs; E3 for image inputs.

**Implementation status:** Complete. G2 adds a Pillow-only backend service with
a filesystem/scalar low-level boundary and a database-aware processing-job
wrapper. No FastAPI route or worker invokes it.

Implemented behavior:

- Uploaded JPEG/PNG originals are resolved beneath `<UPLOAD_DIR>/originals`.
  PDF input requires a matching G1 `ConvertedPdfPage` or strictly validated
  portable reference beneath the same floor-plan/job directory.
- Content is fully decoded and must match its MIME type and extension. Traversal,
  absolute paths, missing files, directories, symlink escapes, corrupt/truncated
  content, and decompression-bomb dimensions fail safely.
- EXIF orientation is applied without portrait/landscape guessing. Transparency
  is composited onto white, supported modes are converted to RGB, and source
  EXIF/unrelated metadata is removed from the derived PNG.
- Images are never upscaled. The longest oriented edge is reduced to 4096 pixels
  only when necessary, preserving aspect ratio with LANCZOS resampling.
- `NormalizedImage` records encoded, oriented, and final dimensions plus
  orientation/resizing flags, MIME types, IDs, reference, and byte size.
- Output is created exclusively at
  `normalized/floor-plan-<id>/job-<id>/image.png` beneath `PROCESSED_DIR`.
  Existing results are not overwritten and partial writes are removed safely.
- Queued and already-processing jobs are accepted. Progress remains unchanged;
  success leaves the broader job `processing`. Failure persists only
  `Floor-plan image normalization failed.`
- Floor-plan metadata, original uploads, and G1 pages remain unchanged. No
  `processed_images` table, new column, sidecar, API, worker, OpenCV behavior, or
  automatic F2/G1/G2 orchestration is added.

G3 is implemented separately and consumes only G2 normalized output.

**Acceptance Criteria:**

- [ ] JPEG and PNG inputs can be loaded.
- [ ] PDF-converted images can be loaded.
- [ ] Image dimensions are recorded.
- [ ] Processing does not replace the original.
- [ ] Normalized output is written to the processed storage directory.
- [ ] Invalid image input fails gracefully.

---

### TICKET G3 — Implement OpenCV Preprocessing Pipeline

**Goal:** Produce processed images for wall and symbol detection.

**Dependencies:** G2.

**Implementation status:** Complete. G3 adds the isolated
`app.ai.preprocessing` package using `opencv-python-headless==4.14.0.94` and
`numpy==2.5.2`. It has no FastAPI route and is not invoked automatically by F2
or G2 because no worker exists.

Implemented behavior:

- A pure array boundary consumes three-channel normalized RGB `uint8` data and
  returns typed stage arrays without HTTP, filesystem, or database requirements.
- Stage order is grayscale, median noise reduction, optional Gaussian blur,
  then binary thresholding. Dimensions and `uint8` dtype are preserved; the
  final image contains only 0 and 255.
- Otsu thresholding is the default and records the selected threshold. Fixed
  threshold mode uses an explicit 0-through-255 value. Binary inversion is
  disabled unless configured.
- Frozen `PreprocessingParameters` defaults to median kernel 3, Gaussian enabled
  with kernel 3 and sigma 0.0, Otsu mode, fixed value 127, no inversion, and no
  debug writes. Kernels are validated odd integers from 3 through 31; Boolean
  numeric values, non-finite sigma, unknown modes, and unknown fields fail safely.
- The filesystem boundary accepts only a matching G2 `NormalizedImage` or exact
  `normalized/floor-plan-<id>/job-<id>/image.png` reference beneath
  `PROCESSED_DIR`. IDs, absolute/portable path agreement, symlink confinement,
  PNG format, three-channel content, and dimensions are validated. G2 bytes are
  never modified.
- Optional debug artifacts are exclusive single-channel PNGs beneath
  `preprocessed/floor-plan-<id>/job-<id>/`: `grayscale.png`, `denoised.png`,
  optional `blurred.png`, and `thresholded.png`. Existing files are not
  overwritten and partial writes receive compensating cleanup.
- The optional database wrapper requires a matching already-`processing`
  `floor_plan_analysis` job. Success preserves status and progress; failure
  persists only `Floor-plan preprocessing failed.`
- G3 adds no schema, manifest, processed-image row, worker, API, morphology,
  Canny, Hough, contour, wall-detection, YOLO, or geometry behavior. H1 is next.

**Acceptance Criteria:**

- [ ] Grayscale conversion is implemented.
- [ ] Noise reduction is implemented.
- [ ] Gaussian blur is implemented where configured.
- [ ] Thresholding is implemented.
- [ ] Processing parameters are centralized/configurable.
- [ ] Output can be saved for debugging/evaluation.
- [ ] Unit tests verify expected output type and dimensions.

---

## Epic H — Structural Geometry Detection

### TICKET H1 — Implement Wall-Line Detection Prototype

**Goal:** Detect candidate wall lines from the processed floor plan.

**Dependencies:** G3.

**Implementation status:** Complete. H1 adds an isolated in-memory candidate
detector using Canny edge detection followed by OpenCV's probabilistic Hough
transform. It consumes only G3's thresholded array and does not reopen or write
any image file.

Implemented behavior:

- `WallDetectionParameters` centralizes strictly validated prototype defaults:
  Canny 50/200 with aperture 3; Hough rho 1.0, theta 1.0 degree, vote threshold
  50, minimum length 50, maximum gap 10, and maximum 2000 candidates.
- Input is either a G3 `PreprocessedImage` or an isolated two-dimensional binary
  `uint8` array. Dimensions must be positive and no edge may exceed 4096 pixels.
  G3 width/height must match the thresholded array, and input bytes are not
  mutated.
- Candidate coordinates are ordinary Python integers in raw pixel space with a
  top-left origin, x increasing right, and y increasing down. The topmost
  endpoint is first; the leftmost endpoint breaks horizontal ties.
- Angles are normalized to `[0, 180)`, and public angle and pixel-length values
  are rounded to six decimal places.
- Exact canonical duplicates are removed. Nearby or collinear segments are not
  merged. Candidates sort by start y, start x, end y, then end x before one-based
  IDs are assigned, producing stable JSON-serializable output.
- Unique results above the configured maximum are deterministically capped and
  return `truncated=true`. Empty, all-white, all-black, and no-line inputs return
  an empty candidate tuple and `truncated=false` without error.
- Candidates are raw, unverified wall suggestions. H1 does not add persistence,
  walls tables, previews, scale conversion, thickness/pairing, rooms, APIs,
  workers, job-state changes, frontend overlays, YOLO, or symbol detection.

H2 coordinate normalization is the next roadmap ticket.

**Acceptance Criteria:**

- [ ] Hough Line Transform or the selected OpenCV method is isolated in a wall-detection module.
- [ ] Detection returns coordinates rather than drawing directly into the UI.
- [ ] Output uses a documented coordinate structure.
- [ ] Empty/noisy detection results are handled without crashing.
- [ ] A sample test image produces a deterministic output format.

---

### TICKET H2 — Normalize Wall Coordinates

**Goal:** Convert image-space wall coordinates into the canonical geometry representation.

**Dependencies:** H1.

**Implementation status:** Complete. H2 adds a pure, immutable `app.geometry`
contract that validates H1 output and converts its raw image-space candidates
into a shared metric plane. It executes no OpenCV and has no API, filesystem,
database, worker, model, job-state, or frontend dependency.

Implemented behavior:

- Every conversion requires an explicit positive finite `pixels_per_meter`.
  There is no default. Booleans, zero, negatives, strings, NaN, infinity, and
  missing values fail through a sanitized error contract.
- Physical scale is never inferred from PDF rendering DPI. The specification's
  `100 pixels_per_meter` example is illustrative, not calibrated project data.
- Canonical coordinates use meters, the normalized image's top-left origin,
  x increasing right, and y increasing down, preserving image overlay alignment.
- H1 candidate IDs and deterministic order, raw integer endpoints, raw lengths,
  raw angles, and source truncation are preserved exactly. Empty H1 results
  remain valid empty geometry.
- Canonical endpoints use `pixel_coordinate / pixels_per_meter`; metric length
  is derived from the canonical endpoints rather than trusting raw length.
- Internal immutable values retain full floating-point precision. Serialized
  metric coordinates and lengths round to nine decimal places, normalize
  negative zero, remain numeric, and contain only ordinary Python/JSON values.
- Complete H1 metadata, dimensions, IDs, candidate order, endpoint bounds,
  length, and angle contracts are validated before conversion. No NumPy scalar
  value escapes into the geometry result.
- H2 does not merge, snap, extend, filter, or deduplicate H1 candidates again.
  It does not implement wall thickness, rooms, persistence, or scale detection.
- Future Konva and Three.js adapters must consume the same canonical coordinates.
  Conceptually canonical x maps to Three.js x, canonical y to Three.js z, and
  floor elevation to Three.js y; no adapter or renderer is implemented in H2.

H2 output remains unverified machine-candidate geometry. H3 persists that
contract, while K1 still owns the complete cross-domain project geometry schema.

**Acceptance Criteria:**

- [ ] Raw pixel coordinates are preserved where needed.
- [ ] Canonical coordinates use one documented unit/scale model.
- [ ] Conversion is implemented in the geometry layer rather than UI code.
- [ ] Konva and Three.js do not define separate wall geometries.
- [ ] Coordinate conversion has unit tests.

---

### TICKET H3 — Persist Wall Geometry

**Goal:** Save detected/verified walls.

**Dependencies:** H2.

**Implementation status:** Complete. H3 adds the seventh prototype table,
`walls`, plus repository and service boundaries for transactional detected-wall
replacement and read-only retrieval. It does not connect H1/H2 to a worker or
HTTP route.

Implemented behavior:

- Every wall retains indexed floor-plan and processing-job foreign keys. Its
  project-floor association is reached through `Wall -> FloorPlan ->
  ProjectFloor`; no redundant project-floor key is stored.
- Raw pixel endpoints/length, canonical meter endpoints/length, the explicit
  pixels-per-meter scale, candidate ID, angle, status, and timestamps are stored.
  Fixed-scale `Decimal` columns preserve the persistence boundary.
- Status is constrained to `detected` or `verified`. H3 machine persistence
  writes only `detected`; it does not add a verification transition or editor.
- Persistence requires exact, complete, nontruncated H2 geometry and a matching
  `floor_plan_analysis` job whose status remains `processing`.
- Replacement locks the floor-plan row, protects verified walls, deletes the
  current detected set, inserts the complete replacement, and commits once.
  Identical reruns do not accumulate duplicates, newer jobs replace older
  detected rows, fewer candidates remove stale rows, and empty geometry clears
  the detected set.
- Any database read, delete, insertion, flush, or commit failure rolls back the
  replacement and surfaces only a stable sanitized error. Job progress/status,
  floor-plan processing status, and stored image files are not changed.
- Retrieval returns an immutable candidate-ordered tuple with exact internal
  `Decimal` values and an optional JSON-compatible serializer. It loads no
  relationships and executes neither OpenCV nor H2 conversion.
- H3 adds no HTTP wall API, review UI, manual editing, room/door/window/symbol
  persistence, worker, layout versioning, I1 behavior, or complete K1 geometry.

**Acceptance Criteria:**

- [ ] Walls are associated with the correct floor plan/floor.
- [ ] Start and end coordinates are stored.
- [ ] Geometry can be retrieved later without rerunning OpenCV.
- [ ] Reprocessing behavior is defined so duplicate wall sets are not silently accumulated.
- [ ] Persistence tests pass.

---

## Epic I — YOLO Symbol Detection

### TICKET I1 — Implement YOLO Model Loader

**Goal:** Load the configured trained electrical-symbol model.

**Dependencies:** A2.

**Implementation status:** Complete. I1 adds an isolated lazy loader for a
configured local `.pt` model. `YOLO_MODEL_PATH` is the only model-location
setting; relative values resolve from the repository root and the maintained
example is `models/yolo/electrical-symbols.pt`. No trained model is committed to
the repository.

Implemented behavior:

- Local path, extension, file type, existence, and readability are validated
  before the official `YOLO(model_path)` constructor is called, preventing model
  shorthand from triggering an automatic download.
- Absolute local paths are supported, while URLs, directories, malformed paths,
  unsupported extensions, and missing files fail with stable sanitized errors.
- Class names are normalized dynamically from list- or dictionary-shaped
  `model.names` metadata. No electrical class names are assumed in code.
- Successful loads use a bounded, thread-safe process-local cache by canonical
  path. Concurrent first callers load once, failures remain retryable, and tests
  can explicitly reset the cache or inject a fake model factory.
- Importing FastAPI does not load a model. Missing or invalid weights therefore
  cause a controlled loader/processing error only when the loader is called,
  rather than an application-wide startup crash.
- I1 invokes no prediction or preprocessing, persists no detections, changes no
  processing jobs, and adds no API or worker integration. I2 remains the future
  inference ticket.
- `ultralytics-opencv-headless==8.4.131` uses AGPL-3.0 or a separately obtained
  Enterprise license. Commercial or production use requires licensing review.

**Acceptance Criteria:**

- [ ] Model path comes from configuration.
- [ ] Missing model produces a clear startup or processing error.
- [ ] Model loading is not repeated unnecessarily for every detected object.
- [ ] Model loader is isolated from API route files.
- [ ] Application does not assume classes not present in the trained model.

---

### TICKET I2 — Implement Symbol Inference Service

**Goal:** Run YOLO on a processed floor plan.

**Dependencies:** I1, G3.

**Implementation status:** Complete. I2 is an isolated in-memory inference
boundary and processing-job failure wrapper. It adds no route, worker,
automatic orchestration, output image, schema table, or detected-symbol
persistence.

Implemented behavior:

- The primary boundary accepts only a valid G3 `PreprocessedImage` and consumes
  `thresholded`. The source must be a nonempty two-dimensional `uint8` array,
  match the declared dimensions, contain only 0/255, and remain within the
  existing 4096-pixel limit.
- YOLO receives a separate contiguous three-channel binary copy, so prediction
  cannot mutate or share writable memory with G3 output. It receives no path,
  URL, camera identifier, or save destination.
- Prediction arguments are exactly `conf=0.0`, `max_det=300`, `verbose=False`,
  `save=False`, and `stream=False`. The zero confidence floor deliberately
  leaves threshold ownership to I3 and preserves detections below 0.50.
- Exactly one single-image detection result is required. Tensor-like and NumPy
  output is converted into immutable, ordered `SymbolPrediction` records with
  dynamically resolved class ID/name, original finite confidence, validated
  `x_min/y_min/x_max/y_max`, and a derived center. Coordinates use processed
  pixels with a top-left origin, positive X right, and positive Y down.
- Empty boxes are successful. Exactly 300 detections set
  `detection_limit_reached=True`; malformed or excess output fails instead of
  being clipped or silently accepted.
- The job wrapper requires a matching positive floor-plan/job association, job
  type `floor_plan_analysis`, and status `processing`. Success leaves status,
  progress, and error unchanged. Model loading, prediction, or result conversion
  failure marks the job failed with only `Floor-plan symbol inference failed.`;
  persistence failure rolls back and surfaces a sanitized error.
- I2 performs no I3 confidence classification/filtering and no I4 database
  persistence. I3 remains the separate stage implemented below.

**Acceptance Criteria:**

- [ ] Inference accepts a processed image.
- [ ] Output includes class, confidence, bounding box, and center coordinates.
- [ ] Raw inference output is converted to a stable internal schema.
- [ ] Empty detection results are valid.
- [ ] AI inference errors mark the job appropriately.

---

### TICKET I3 — Implement Confidence Filtering

**Goal:** Apply the source-defined confidence threshold.

**Dependencies:** I2.

**Implementation status:** Complete. I3 classifies every validated I2
prediction using the application confidence threshold. It is an immutable,
in-memory transformation and neither invokes YOLO nor mutates a processing job.

Implemented behavior:

- The configuration-aware boundary reads the existing
  `Settings.yolo_confidence_threshold`, whose default is exactly `0.50`, and
  supports injected settings for isolated tests. The pure boundary accepts an
  explicit finite numeric threshold from `0.0` through `1.0`; Boolean, textual,
  non-finite, and out-of-range values fail with a sanitized error.
- Confidence equal to or greater than the threshold receives `detected`.
  Confidence below the threshold receives `needs_review`; it is never dropped
  or treated as confirmed.
- Each immutable classified record contains the original `SymbolPrediction`
  object unchanged. Model order, exact confidence, dynamic class metadata,
  bounding box, center, image dimensions, maximum-detection value, and
  detection-limit flag are preserved.
- Empty I2 results are valid. Malformed I2 containers, predictions, confidence,
  geometry, and inconsistent detection-limit metadata fail safely.
- I3 adds no table, detected-symbol persistence, API, worker, orchestration, job
  transition, Designer confirmation/correction, or frontend behavior. I4 is the
  next ticket.

**Acceptance Criteria:**

- [ ] Default threshold is `0.50`.
- [ ] Threshold is configurable.
- [ ] Predictions above/at threshold and below threshold are distinguishable.
- [ ] Low-confidence predictions are not silently treated as confirmed.
- [ ] Original confidence value is preserved.

---

### TICKET I4 — Persist Detected Symbols

**Goal:** Save detection results independently from later manual edits.

**Dependencies:** I3.

**Implementation status:** Complete. I4 adds the eighth prototype table,
`detected_symbols`, with backend-only transactional persistence and immutable
retrieval. It adds no route, worker, job completion, Designer review action,
symbol-legend integration, or canonical geometry.

Implemented behavior:

- Each row stores floor-plan and processing-job foreign keys, a one-based source
  prediction index, I3 machine status/threshold, original I1/I2 class and
  confidence, processed-image dimensions, original bounding box and center,
  detection maximum/cap provenance, and timestamps. Original fields are
  explicit snapshots for later auditable correction work.
- Only `detected` and `needs_review` are accepted, and status must agree with the
  stored original confidence and threshold. Complete input validation rejects
  malformed, nonfinite, out-of-bounds, inconsistent, oversized, or mutable I3
  results before database mutation.
- Processing jobs are machine-result versions. Same-job persistence locks the
  floor plan and atomically replaces only that job's rows. A newer job preserves
  older versions. Empty results clear only the selected job. A named unique
  constraint prevents duplicate job/prediction indexes.
- Persistence requires a matching `floor_plan_analysis` job in `processing` and
  commits once. Any read, deletion, insertion, flush, or commit failure rolls
  back the entire replacement and exposes only a sanitized error.
- Retrieval requires floor-plan and processing-job identity, orders by
  prediction index then row ID, returns immutable JSON-compatible records, and
  executes no model loading, inference, confidence classification, OpenCV, or
  filesystem operation.
- Successful persistence leaves processing-job status/progress/error and
  floor-plan processing status unchanged. J1 is the next normal ticket.

**Acceptance Criteria:**

- [ ] Each detection references the correct floor plan.
- [ ] Symbol class is stored.
- [ ] Confidence is stored.
- [ ] Bounding box and center position are stored.
- [ ] Detection status is stored.
- [ ] Reprocessing behavior is versioned or clearly replaces the previous machine result.
- [ ] User corrections do not erase the original AI result without trace.

---

## Epic J — Detection Review

### TICKET J1 — Create Detection Results API

**Goal:** Return structural and symbol results for review.

**Dependencies:** H3, I4.

**Implementation status:** Complete. J1 adds an ownership-aware, read-only API
for persisted H3/I4 results without rerunning AI/CV or changing database state.

Implemented behavior:

- `GET /api/floor-plans/{floor_plan_id}/detections` requires a positive
  `processing_job_id` query parameter identifying the exact
  `floor_plan_analysis` symbol-result version.
- Owning Designers may read their own project results; Admins may read any
  matching floor-plan/job context. Missing, mismatched, wrong-type, and
  cross-owner contexts share the same sanitized `404`.
- Symbols come only from the requested job and remain ordered by prediction
  index then row ID. Empty versions return an empty array and never fall back to
  an older job.
- Walls remain H3's current floor-plan wall set, ordered by candidate then row
  ID. Each wall includes its own processing-job provenance because the wall and
  symbol job versions may differ.
- Explicit nested Pydantic schemas expose raw-pixel and canonical-meter walls,
  original symbol class/confidence, I3 threshold/status, pixel geometry, image
  dimensions, detection-cap metadata, and timestamps.
- Valid contexts with no stored records return HTTP 200 with empty arrays.
  Database failures return a sanitized `503`; FastAPI validation retains its
  standard response shape.
- Repository reads use scoped joins, `load_only`, `raiseload("*")`, deterministic
  ordering, no row locks, and no writes. J1 performs no commit, AI inference,
  confidence filtering, persistence, filesystem access, or state transition.
- J1 adds no schema, dependency, configuration, worker, frontend, review
  mutation, or canonical geometry. J2 remains next.

**Acceptance Criteria:**

- [ ] `GET /api/floor-plans/{id}/detections` exists.
- [ ] Response returns walls and symbols in a documented schema.
- [ ] Symbol confidence values are included.
- [ ] Low-confidence status is included.
- [ ] Unauthorized access is rejected.

---

### TICKET J2 — Build Detection Review Canvas

**Goal:** Display AI results over the original plan.

**Dependencies:** J1.

**Acceptance Criteria:**

- [ ] Original blueprint displays as a non-destructive background/reference.
- [ ] Detected walls are visually overlaid.
- [ ] Detected electrical symbols are visually overlaid.
- [ ] Confidence/status can be inspected.
- [ ] Canvas uses data from the backend rather than hard-coded sample components.

---

### TICKET J3 — Confirm or Reject Detection

**Goal:** Allow the Designer to review individual AI detections.

**Dependencies:** J2.

**Acceptance Criteria:**

- [ ] User can confirm a detection.
- [ ] User can mark a detection as incorrect/deleted.
- [ ] Changes persist after page reload.
- [ ] Original AI result remains auditable.
- [ ] User cannot modify another user's project without authorization.

---

### TICKET J4 — Correct Symbol Classification

**Goal:** Change an incorrectly classified detected symbol.

**Dependencies:** J3.

**Acceptance Criteria:**

- [ ] User can choose a valid symbol class from the approved legend library.
- [ ] Corrected class persists.
- [ ] Correction records old and new values.
- [ ] The corrected value becomes the authoritative layout value.
- [ ] Original AI class remains available for accuracy evaluation.

---

### TICKET J5 — Add Missing Symbol Manually

**Goal:** Add components the model did not detect.

**Dependencies:** J2.

**Acceptance Criteria:**

- [ ] User can choose a valid symbol class.
- [ ] User can place the symbol on the 2D plan.
- [ ] Manual symbol is marked as manually added.
- [ ] Symbol persists after reload.
- [ ] Manually added symbols participate in later 3D, routing, and quantity calculations.

---

## Epic K — Canonical Geometry and 2D Layout

### TICKET K1 — Define Canonical Geometry Schema

**Goal:** Establish the shared domain model used by 2D, 3D, routing, and estimation.

**Dependencies:** H2, J5.

**Acceptance Criteria:**

- [ ] Schema defines coordinate system and unit.
- [ ] Walls are represented.
- [ ] Rooms can be represented.
- [ ] Symbols are represented.
- [ ] Routes can be represented.
- [ ] Floor/elevation association is represented.
- [ ] Schema is documented in `docs/geometry.md`.
- [ ] Frontend and backend agree on field names/types.

---

### TICKET K2 — Create Layout Snapshot/Version Model

**Goal:** Preserve verified layout state.

**Dependencies:** K1.

**Acceptance Criteria:**

- [ ] Layout version references a project/floor.
- [ ] Version number or timestamp is stored.
- [ ] Verified walls and symbols can be reconstructed from the version.
- [ ] Saving a new layout does not silently destroy the previous version if versioning is enabled.
- [ ] One version can be marked current/authoritative.

---

### TICKET K3 — Create 2D Layout API

**Goal:** Load and save the authoritative 2D layout.

**Dependencies:** K2.

**Acceptance Criteria:**

- [ ] `GET /api/projects/{id}/layouts` or documented equivalent returns current layout data.
- [ ] Save/update endpoint validates geometry.
- [ ] Backend remains source of truth.
- [ ] Invalid coordinates produce a validation error.
- [ ] Saving the 2D layout does not modify the original blueprint file.

---

### TICKET K4 — Build Konva Layer Architecture

**Goal:** Implement stable 2D rendering layers.

**Dependencies:** K3.

**Acceptance Criteria:**

- [ ] Blueprint is on its own layer.
- [ ] Walls are on their own layer.
- [ ] Symbols are on their own layer.
- [ ] Wiring/conduit layer exists even if routing is not implemented yet.
- [ ] Selection/editing UI is separated from project geometry.
- [ ] Toggling one layer does not delete its data.

---

### TICKET K5 — Implement Symbol Move/Edit in 2D

**Goal:** Allow verified symbols to be repositioned.

**Dependencies:** K4.

**Acceptance Criteria:**

- [ ] User can select a symbol.
- [ ] User can move a symbol.
- [ ] Updated canonical coordinate is saved.
- [ ] Reload shows the saved position.
- [ ] Position is not stored only in Konva-specific state.
- [ ] Later 3D rendering can consume the same coordinate.

---

## Epic L — 3D Reconstruction

### TICKET L1 — Initialize Three.js / React Three Fiber Viewer

**Goal:** Create an empty interactive 3D scene.

**Dependencies:** A3.

**Acceptance Criteria:**

- [ ] 3D scene loads without floor-plan data.
- [ ] Orbit works.
- [ ] Pan works.
- [ ] Zoom works.
- [ ] Reset view works.
- [ ] Viewer failure does not crash unrelated dashboard pages.

---

### TICKET L2 — Render Floor from Canonical Geometry

**Goal:** Generate the floor plane from project geometry.

**Dependencies:** K1, L1.

**Acceptance Criteria:**

- [ ] Floor dimensions come from canonical geometry.
- [ ] Scene does not use hard-coded demo dimensions.
- [ ] Scale matches the documented coordinate system.
- [ ] Floor alignment can be compared against the 2D plan.

---

### TICKET L3 — Extrude Walls from 2D Geometry

**Goal:** Generate 3D wall meshes from canonical wall data.

**Dependencies:** H3, L2.

**Acceptance Criteria:**

- [ ] Every rendered wall comes from stored wall geometry.
- [ ] Wall start/end positions align with 2D coordinates.
- [ ] Wall height is configurable or stored.
- [ ] Wall thickness is configurable or stored.
- [ ] Walls are not manually recreated separately in Three.js.

---

### TICKET L4 — Render Electrical Symbols in 3D

**Goal:** Place verified electrical components in the 3D scene.

**Dependencies:** J5, L3.

**Acceptance Criteria:**

- [ ] Verified symbols appear in 3D.
- [ ] Deleted/rejected symbols do not appear.
- [ ] Manually added symbols appear.
- [ ] Symbol position derives from canonical geometry.
- [ ] Moving a symbol in 2D changes its 3D position after synchronization/reload.

---

### TICKET L5 — Add 2D/3D View Synchronization

**Goal:** Keep both visualizations based on one project model.

**Dependencies:** K5, L4.

**Acceptance Criteria:**

- [ ] 2D and 3D consume the same authoritative geometry data.
- [ ] Editing an object does not create a second unrelated 3D-only record.
- [ ] Reloading both views shows the same saved project state.
- [ ] Coordinate transform logic is isolated and tested.

---

## Epic M — Spatial Routing

### TICKET M1 — Define Routing Data Model

**Goal:** Define panels, route points, route segments, and route types.

**Dependencies:** K1.

**Acceptance Criteria:**

- [ ] Electrical panel can be represented.
- [ ] Route contains ordered points/segments.
- [ ] Horizontal and vertical distance can be represented separately.
- [ ] Floor/elevation is supported.
- [ ] Route type can distinguish ceiling/service-level and wall-embedded movement.
- [ ] Model is documented.

---

### TICKET M2 — Build Navigable Routing Graph

**Goal:** Convert building geometry into an A*-compatible graph.

**Dependencies:** M1, H3.

**Acceptance Criteria:**

- [ ] Graph generation is independent of Three.js.
- [ ] Walls/obstacles restrict invalid paths.
- [ ] Electrical panel and target devices can be mapped to graph nodes.
- [ ] Graph generation has deterministic tests for a small sample layout.

---

### TICKET M3 — Implement Basic A* Routing

**Goal:** Compute a valid path from panel to a target device.

**Dependencies:** M2.

**Acceptance Criteria:**

- [ ] A* returns an ordered route.
- [ ] Route avoids configured structural obstacles.
- [ ] No-path cases return a controlled error/result.
- [ ] Algorithm has unit tests using known graphs.
- [ ] Route result is independent of visual rendering.

---

### TICKET M4 — Add Ceiling-Level Horizontal Routing Rule

**Goal:** Apply the project-specific routing rule for cross-room/horizontal movement.

**Dependencies:** M3.

**Acceptance Criteria:**

- [ ] Horizontal routing uses configured ceiling/service elevation where required.
- [ ] Route metadata identifies ceiling-level segments.
- [ ] Cross-room routes do not use arbitrary diagonal lines through open space when rule-based routing applies.
- [ ] Behavior is configurable/documented.
- [ ] Sample routing case can be manually verified in 3D.

---

### TICKET M5 — Add Wall Vertical Drop/Rise Rule

**Goal:** Route from ceiling/service level to wall-mounted devices.

**Dependencies:** M4.

**Acceptance Criteria:**

- [ ] Vertical drop/rise segments are represented explicitly.
- [ ] Vertical segment follows the associated wall path where applicable.
- [ ] Vertical distance contributes to total wire/conduit length.
- [ ] Route is visible correctly in 3D.
- [ ] Route output contains segment type/elevation metadata.

---

### TICKET M6 — Add Multi-Floor Vertical Routing

**Goal:** Support risers or vertical connectors between floors.

**Dependencies:** M5, B5.

**Acceptance Criteria:**

- [ ] Route can reference multiple floors.
- [ ] Vertical connector/riser is explicitly represented.
- [ ] Elevation difference contributes to total length.
- [ ] Floor transition is visible in route data.
- [ ] Missing vertical connector produces a controlled no-route result rather than an impossible shortcut.

---

### TICKET M7 — Persist and Display Routes

**Goal:** Save routing results and show them in 2D/3D.

**Dependencies:** M6, L5.

**Acceptance Criteria:**

- [ ] Routes are stored in the database.
- [ ] Route segments reload without recomputation.
- [ ] 2D shows route overlay.
- [ ] 3D shows horizontal and vertical route segments.
- [ ] Route length displayed in the UI matches backend calculation.
- [ ] Route recalculation creates a clear updated state/version.

---

## Epic N — Material Quantification

### TICKET N1 — Create Material Catalog Schema

**Goal:** Store company materials independently from estimates.

**Dependencies:** B2.

**Acceptance Criteria:**

- [ ] `materials` table exists.
- [ ] Material code/name is supported.
- [ ] Unit is supported.
- [ ] Category is supported.
- [ ] Active/inactive state is supported.
- [ ] Prices are not hard-coded in frontend or routing code.

---

### TICKET N2 — Create Material Pricing and History Schema

**Goal:** Track current and historical material prices.

**Dependencies:** N1.

**Acceptance Criteria:**

- [ ] Material price can be updated.
- [ ] Previous price remains available in price history.
- [ ] Effective date/time is stored.
- [ ] Updating a price does not rewrite existing estimate item prices.
- [ ] Admin identity can be associated with the change.

---

### TICKET N3 — Implement Component Quantity Calculation

**Goal:** Count verified electrical symbols by type.

**Dependencies:** J5, K2.

**Acceptance Criteria:**

- [ ] Confirmed symbols are counted.
- [ ] Corrected symbols use corrected classification.
- [ ] Manually added symbols are counted.
- [ ] Deleted/rejected symbols are excluded.
- [ ] Quantity results are reproducible from the authoritative layout.

---

### TICKET N4 — Implement Wire and Conduit Length Calculation

**Goal:** Convert route geometry into material lengths.

**Dependencies:** M7.

**Acceptance Criteria:**

- [ ] Horizontal route distance is included.
- [ ] Vertical route distance is included.
- [ ] Multi-floor/riser distance is included.
- [ ] Units are consistent.
- [ ] Calculation is performed in backend domain/service code.
- [ ] Test case with known route coordinates returns expected length.

---

## Epic O — Cost Estimation

### TICKET O1 — Create Estimate and Estimate Items Schema

**Goal:** Persist estimate snapshots.

**Dependencies:** N1, N2.

**Acceptance Criteria:**

- [ ] `estimates` table exists.
- [ ] `estimate_items` table exists.
- [ ] Estimate references the project.
- [ ] Each item stores quantity, unit, captured unit price, and line total.
- [ ] Historical estimates are not silently changed by later price updates.
- [ ] The estimate models and constraints can be created successfully in the current MySQL development schema.

---

### TICKET O2 — Implement Estimate Generation Service

**Goal:** Generate a Bill of Materials from authoritative project data.

**Dependencies:** N3, N4, O1.

**Acceptance Criteria:**

- [ ] Service uses verified component quantities.
- [ ] Service uses calculated route lengths.
- [ ] Service reads prices from the database.
- [ ] Line total equals quantity × captured unit price.
- [ ] Grand total equals the sum of item totals plus only explicitly configured additions.
- [ ] Missing required price produces a clear validation/result state.

---

### TICKET O3 — Create Estimate API

**Goal:** Expose estimate generation and retrieval.

**Dependencies:** O2.

**Acceptance Criteria:**

- [ ] Generate estimate endpoint exists.
- [ ] Get estimate endpoint exists.
- [ ] Unauthorized access is rejected.
- [ ] Response contains itemized quantities, unit prices, line totals, and total.
- [ ] Reopening an old estimate returns its stored price snapshot.

---

### TICKET O4 — Build Estimate UI

**Goal:** Present the Bill of Materials and cost summary.

**Dependencies:** O3.

**Acceptance Criteria:**

- [ ] Material rows display quantity, unit, unit price, and line total.
- [ ] Total matches backend response.
- [ ] UI does not recalculate hidden alternative prices.
- [ ] Missing-price warnings are visible.
- [ ] User can distinguish estimate version/date.

---

## Epic P — Admin Management

### TICKET P1 — Material Catalog Admin API

**Goal:** Allow Admin to manage materials.

**Dependencies:** C4, N1.

**Acceptance Criteria:**

- [ ] Admin can list materials.
- [ ] Admin can add a material.
- [ ] Admin can edit allowed fields.
- [ ] Designer cannot change material catalog.
- [ ] Validation prevents invalid units/prices where applicable.

---

### TICKET P2 — Material Price Update API

**Goal:** Allow Admin to update official company prices.

**Dependencies:** P1, N2.

**Acceptance Criteria:**

- [ ] Only Admin can update prices.
- [ ] Price history is created.
- [ ] Current material price updates correctly.
- [ ] Existing estimates remain unchanged.
- [ ] Price update action is audit-ready.

---

### TICKET P3 — Symbol Legend Admin API

**Goal:** Manage approved symbol classes/reference information.

**Dependencies:** C4, I4.

**Acceptance Criteria:**

- [ ] Admin can list symbol legends.
- [ ] Admin can activate/deactivate supported legend records.
- [ ] Designer cannot modify the legend library.
- [ ] Existing detections remain referentially valid when a legend is deactivated.
- [ ] Model class mapping behavior is documented.

---

### TICKET P4 — Build Admin Management UI

**Goal:** Provide interfaces for material and symbol maintenance.

**Dependencies:** P1, P2, P3.

**Acceptance Criteria:**

- [ ] Admin sees material management.
- [ ] Admin can update a material price.
- [ ] Admin sees symbol legend management.
- [ ] Designer does not receive Admin controls.
- [ ] Backend still rejects unauthorized direct API attempts.

---

## Epic Q — PDF Reporting

### TICKET Q1 — Define Report Data Contract

**Goal:** Freeze what data a generated report uses.

**Dependencies:** O3, K2.

**Acceptance Criteria:**

- [ ] Contract includes project metadata.
- [ ] Contract includes layout/detection summary.
- [ ] Contract includes route lengths.
- [ ] Contract includes Bill of Materials.
- [ ] Contract includes estimate totals.
- [ ] Contract references a specific estimate version.
- [ ] Report generation does not depend on current prices changing afterward.

---

### TICKET Q2 — Implement PDF Report Generator

**Goal:** Generate a project estimation PDF from stored data.

**Dependencies:** Q1.

**Acceptance Criteria:**

- [ ] PDF is generated successfully from a completed estimate.
- [ ] Project information is displayed.
- [ ] Material quantities are displayed.
- [ ] Unit prices and totals are displayed.
- [ ] Report identifies generation date and prepared-by user.
- [ ] Output uses planning/estimation language rather than representing the report as an automatically approved engineering document.
- [ ] Generated PDF is stored outside the original upload directory.

---

### TICKET Q3 — Create Report API

**Goal:** Generate and retrieve reports.

**Dependencies:** Q2.

**Acceptance Criteria:**

- [ ] Generate report endpoint exists.
- [ ] Report metadata is persisted.
- [ ] Download/retrieval endpoint exists.
- [ ] Authorization is enforced.
- [ ] Re-downloading a report does not recalculate the estimate using newer prices.

---

### TICKET Q4 — Build Report UI

**Goal:** Allow users to generate and access reports.

**Dependencies:** Q3.

**Acceptance Criteria:**

- [ ] User can generate a report from an eligible project/estimate.
- [ ] Report generation status is visible.
- [ ] User can download/open the generated PDF.
- [ ] Previous generated reports can be identified by date/version.
- [ ] Report errors are shown clearly.

---

## Epic R — Audit Logging

### TICKET R1 — Create Audit Log Schema and Service

**Goal:** Record important user/system actions.

**Dependencies:** B3.

**Acceptance Criteria:**

- [ ] `audit_logs` table exists.
- [ ] Log records user, action, entity type, entity ID, timestamp, and safe details.
- [ ] Audit service is reusable across modules.
- [ ] Sensitive credentials/secrets are never written into audit details.

---

### TICKET R2 — Log Core Workflow Actions

**Goal:** Add audit events to important features.

**Dependencies:** R1 and relevant completed feature tickets.

**Acceptance Criteria:**

- [ ] Login can be logged.
- [ ] Project creation is logged.
- [ ] Floor plan upload is logged.
- [ ] AI analysis start/completion/failure can be logged.
- [ ] Symbol corrections/additions/removals are logged.
- [ ] Route recalculation is logged.
- [ ] Material price update is logged.
- [ ] Estimate generation is logged.
- [ ] Report generation is logged.

---

### TICKET R3 — Admin Audit Log Viewer

**Goal:** Allow Admin to inspect audit history.

**Dependencies:** R2, C4.

**Acceptance Criteria:**

- [ ] Admin can retrieve audit records.
- [ ] Designer cannot access unrestricted audit history.
- [ ] Basic filtering by action/user/date is supported or clearly deferred.
- [ ] Audit details do not expose secrets or raw stack traces.

---

## Epic S — Testing and Validation

### TICKET S1 — Backend Unit Test Foundation

**Goal:** Configure isolated backend testing.

**Dependencies:** A4.

**Acceptance Criteria:**

- [ ] `pytest` test suite runs.
- [ ] Test configuration is separated from production configuration.
- [ ] At least one service-level unit test exists.
- [ ] Test failures return a non-zero process status.
- [ ] Testing command is documented.

---

### TICKET S2 — API Integration Test Foundation

**Goal:** Verify FastAPI endpoint behavior.

**Dependencies:** S1, C2.

**Acceptance Criteria:**

- [ ] Test client can call FastAPI routes.
- [ ] Authentication success case is tested.
- [ ] Authentication failure case is tested.
- [ ] Protected route behavior is tested.
- [ ] Tests do not require manually clicking the UI.

---

### TICKET S3 — AI Detection Evaluation Dataset Runner

**Goal:** Compare AI detections against manually verified ground truth.

**Dependencies:** I3, I4.

**Acceptance Criteria:**

- [ ] Evaluation accepts a defined test dataset.
- [ ] AI count can be compared against manual count.
- [ ] Per-class results can be produced.
- [ ] Confidence threshold used in evaluation is recorded.
- [ ] Evaluation results can be exported or documented for thesis analysis.

---

### TICKET S4 — 2D-to-3D Alignment Tests

**Goal:** Verify geometry transformations.

**Dependencies:** L5.

**Acceptance Criteria:**

- [ ] Known 2D wall coordinate maps to expected 3D position.
- [ ] Known symbol coordinate maps to expected 3D position.
- [ ] Scale conversion is tested.
- [ ] Coordinate transform tests run without requiring manual 3D interaction.

---

### TICKET S5 — Routing Length Tests

**Goal:** Verify horizontal and vertical route measurements.

**Dependencies:** M6.

**Acceptance Criteria:**

- [ ] Horizontal length test exists.
- [ ] Vertical drop/rise test exists.
- [ ] Multi-floor vertical test exists.
- [ ] Total route length matches expected values within documented tolerance.
- [ ] No-path behavior is tested.

---

### TICKET S6 — Cost Calculation Tests

**Goal:** Verify estimate accuracy.

**Dependencies:** O2.

**Acceptance Criteria:**

- [ ] Quantity × unit price is tested.
- [ ] Multiple line items are tested.
- [ ] Grand total is tested.
- [ ] Historical estimate price snapshot behavior is tested.
- [ ] Missing-price behavior is tested.

---

## Epic T — Deployment and Documentation

### TICKET T1 — Development Setup Documentation

**Goal:** Make the repository reproducible for another developer.

**Dependencies:** Core foundation complete.

**Acceptance Criteria:**

- [ ] Required Node.js version is documented.
- [ ] Required Python version is documented.
- [ ] XAMPP-based MySQL local-development setup is documented, including starting MySQL and creating/inspecting `ved_electrical` (`phpMyAdmin` may be used optionally).
- [ ] Frontend install/run commands are documented.
- [ ] Backend install/run commands are documented.
- [ ] SQLAlchemy development schema initialization/reset procedure is documented.
- [ ] Environment setup is documented.
- [ ] No undocumented manual secret is required to start local development.

---

### TICKET T2 — Docker Development Setup

**Goal:** Provide optional reproducible containerized local services.

**Dependencies:** B1, A3, A4.

**Acceptance Criteria:**

- [ ] `docker-compose.yml` is valid.
- [ ] Required database service starts.
- [ ] Backend can connect to the containerized database.
- [ ] Persistent database volume is configured.
- [ ] Environment variables are not hard-coded with production secrets.

---

### TICKET T3 — Production Deployment Checklist

**Goal:** Document deployment requirements without silently assuming a hosting provider.

**Dependencies:** MVP features complete.

**Acceptance Criteria:**

- [ ] Frontend deployment requirements are documented.
- [ ] FastAPI deployment requirements are documented.
- [ ] MySQL database requirements are documented.
- [ ] Persistent file/object storage requirements are documented.
- [ ] Environment/secrets management is documented.
- [ ] HTTPS and CORS requirements are documented.
- [ ] Backup requirements for database and generated project files are documented.

---

# 58. Recommended Ticket Execution Order

Codex should normally follow this order:

```text
A1 → A2 → A3 → A4

B1 → B2 → B3 → B4 → B5

C1 → C2 → C3 → C4 → C5
C6 after C2/C3 (logout)

D1 → D2 → D3 → D4

E1 → E2 → E3 → E3A → E4

F1 → F2 → F3 → F4

G1 → G2 → G3

H1 → H2 → H3

I1 → I2 → I3 → I4

J1 → J2 → J3 → J4 → J5

K1 → K2 → K3 → K4 → K5

L1 → L2 → L3 → L4 → L5

M1 → M2 → M3 → M4 → M5 → M6 → M7

N1 → N2 → N3 → N4

O1 → O2 → O3 → O4

P1 → P2 → P3 → P4

Q1 → Q2 → Q3 → Q4

R1 → R2 → R3

S1 → S2
S3 after I4
S4 after L5
S5 after M6
S6 after O2

T1 throughout development
T2 after the application foundation is stable
T3 after the MVP pipeline is complete
```

Parallel work is allowed only when two tickets do not modify the same contract or depend on unfinished behavior.

---

# 59. Acceptance Criteria Rules for Codex

Acceptance criteria must be **observable and testable**.

Avoid vague acceptance criteria such as:

```text
- Works correctly.
- Looks good.
- Is optimized.
- Handles errors.
- Is user-friendly.
```

Use verifiable statements such as:

```text
- GET /health returns HTTP 200.
- Invalid JPEG upload returns HTTP 400 or 422 with the documented error code.
- A Designer cannot call the Admin material-price update endpoint.
- Moving an outlet to x=3.0m, y=2.0m persists after page reload.
- The same outlet appears at the corresponding transformed position in the 3D view.
- A route with 5m horizontal travel and 2m vertical drop reports 7m total before configured allowance.
- Updating a material price does not change an estimate created before the update.
```

For every ticket, Codex should identify which acceptance criteria were:

```text
PASS
FAIL
NOT TESTED
BLOCKED
```

Do not mark a criterion as passed if it was not actually checked.

---

# 60. Codex Ticket Prompt Template

Use the following format when assigning a ticket to Codex:

```text
TICKET ID:
TICKET TITLE:

OBJECTIVE:
Implement only the scope described in this ticket.

DEPENDENCIES:
List completed tickets required before starting.

FILES TO INSPECT FIRST:
List known relevant files/directories. Codex must inspect them before editing.

SCOPE:
List the exact functionality to implement.

OUT OF SCOPE:
List related features that must not be implemented in this ticket.

ACCEPTANCE CRITERIA:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

REQUIRED TESTS:
List automated/manual tests that must be performed.

CONSTRAINTS:
- Preserve existing working features.
- Do not refactor unrelated modules.
- Do not change shared API/data contracts unless this ticket explicitly requires it.
- Do not invent missing electrical engineering rules.
- Keep original floor-plan uploads unchanged.
- Keep canonical geometry as the shared source for 2D, 3D, routing, and estimation.

EXPECTED COMPLETION REPORT:
Ticket:
Status:
Files changed:
Database/schema changes:
API changes:
Tests added/updated:
Acceptance criteria results:
Known limitations:
Next dependency:
```

---

# 61. Definition of a Good Codex Ticket

A ticket is appropriately sized when:

- Codex can describe its responsibility in one sentence.
- It has one primary output.
- Its acceptance criteria can be verified independently.
- Failure does not require debugging several unrelated modules at once.
- It does not combine database schema, AI training, 2D rendering, 3D rendering, routing, costing, and reports in one request.
- It can normally be reviewed in one focused code-review pass.

If a ticket contains several independent outputs, split it again before implementation.
