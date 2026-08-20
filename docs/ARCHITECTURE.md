# Implementation Architecture

> **Current authority and status**
>
> This document describes the current implementation architecture. `docs/FUNCTIONAL_SPEC.md` is authoritative for ticket scope and acceptance criteria, followed by `AGENTS.md` and the implemented code. Historical thesis concepts remain only where they are explicitly labeled historical. Implemented foundations, next-ticket work, and future conceptual structures are identified separately; a table or module listed as planned does not necessarily exist yet.

## 1. Historical Thesis Context

The system is titled **“VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation.”** It addresses a manual electrical-planning workflow in which designers trace 2D blueprints, count electrical components, estimate wiring paths, and prepare material estimates.

The original thesis/proposal described two broad actors, User and Admin, and used a Python Flask backend. That historical architecture was approximately:

```text
User/Admin
   ↓
React.js Frontend
   ↓
Floor Plan Input
   ↓
AI Image Recognition
   ↓
Symbol Detection and Classification
   ↓
Layout Generation
   ↓
Spatial Routing Algorithm
   ↓
Cost Estimation Module
   ↓
System Output
   ↓
MySQL Database
```

This section preserves source context only. Flask and the original authentication assumptions are not current implementation requirements.

## 2. Current Users and Authorization Roles

| Local role | Human-readable responsibility |
|---|---|
| `DESIGNER` | Works on authorized electrical floor-plan projects: upload, review, correct, visualize, route, estimate, and report. |
| `ADMIN` | Performs system-level administration such as future user-role assignment, symbol administration, material pricing, and audit review. |

OAuth/OIDC establishes an external identity. A local VED role controls authorization inside the application. The external identity provider must not implicitly grant `ADMIN` or `DESIGNER`.

## 3. Current System Architecture

### 3.1 Application Layers

```text
React + JavaScript Frontend
        ↓ HTTP / JSON / Multipart Upload
FastAPI
        ↓
Service Layer
        ↓
Repository Layer
        ↓
SQLAlchemy
        ↓
PyMySQL
        ↓
MySQL-Compatible Database
```

The preferred Windows local-development database server is managed through XAMPP. FastAPI connects directly to that server; phpMyAdmin is optional administration tooling, and Apache/PHP are not FastAPI dependencies. XAMPP is a local-development convenience, not a production requirement.

The verified local development server identifies itself as MariaDB-compatible and is accessed through the approved MySQL/PyMySQL connection path. The project target remains a MySQL-compatible database.

### 3.2 Major Planned Application Areas

```text
React Frontend
├── OAuth/OIDC Sign-In Entry
├── Project Workspace
├── Floor Plan Upload
├── Detection Review
├── Konva 2D Editor
├── Three.js 3D Viewer
├── Routing Controls
├── Estimation
├── Reports
└── Administration

FastAPI Backend
├── Authentication and Authorization
├── Project and Floor-Plan APIs
├── Processing Orchestration
├── Detection Review
├── Canonical Geometry
├── Routing
├── Materials and Estimation
├── Reports
└── Audit Services

AI / CV Layer
├── PDF-to-Image Conversion
├── OpenCV Preprocessing
├── Wall and Boundary Detection
├── YOLO Symbol Detection
├── Confidence Filtering
└── Detection Normalization
```

These application areas are planned unless their tickets are already marked complete in the Functional Spec and repository history.

## 4. Technology Stack

### 4.1 Frontend

| Area | Stack | Purpose |
|---|---|---|
| Main UI | React + JavaScript/JSX | Dashboard, project pages, forms, and editor screens |
| Build tool | Vite | Frontend development and production builds |
| Routing | React Router | Page navigation |
| API communication | Axios and/or TanStack Query | FastAPI communication |
| Forms and validation | React Hook Form + Zod | Runtime form validation |
| 2D visualization | Konva.js / React-Konva | Editable floor-plan overlays |
| 3D visualization | Three.js / React Three Fiber | Geometry-derived interactive 3D views |

The frontend uses JavaScript, not TypeScript.

### 4.2 Backend

| Area | Stack | Purpose |
|---|---|---|
| Language | Python | Backend, geometry, routing, reporting, and AI/CV modules |
| API framework | FastAPI | HTTP API and server-side authorization enforcement |
| ASGI server | Uvicorn | FastAPI development/runtime server |
| Validation/configuration | Pydantic + Pydantic Settings | Request schemas and environment-backed settings |
| ORM | SQLAlchemy 2.x | Database engines, sessions, metadata, and ORM models |
| MySQL driver | PyMySQL | SQLAlchemy DBAPI driver for the MySQL-compatible database |

During the current prototype phase, do not introduce Alembic or a migration workflow. Production schema-migration strategy is deferred.

### 4.3 AI and Computer Vision

| Area | Stack | Purpose |
|---|---|---|
| Image processing | OpenCV, NumPy, Pillow | Normalization, filtering, thresholding, and wall detection |
| Symbol detection | Ultralytics YOLO | Electrical-symbol inference |
| PDF conversion | PDF-to-image processing | Convert selected PDF pages for analysis |
| AI output | Normalized JSON/domain data | Preserve detections for review and canonical geometry |

## 5. Implemented Database Foundation

### 5.1 B1 — Connectivity

B1 is implemented:

```text
Environment-backed DATABASE_URL
        ↓
Lazy SQLAlchemy Engine
        ↓
Reusable synchronous session factory
        ↓
PyMySQL
        ↓
XAMPP-managed MySQL-compatible server
        ↓
ved_electrical
```

Database credentials are not hard-coded. Engine creation and connectivity occur only when database functionality is invoked. Importing or starting FastAPI does not require an immediate database connection.

`GET /health` is application liveness only. It does not represent database readiness; explicit database connectivity verification is separate.

### 5.2 B2 — Development Schema Foundation

B2 is implemented:

```text
backend/app/models/base.py
        ↓
Canonical DeclarativeBase
        ↓
Canonical SQLAlchemy metadata

backend/app/core/schema.py
        ↓
Explicit development invocation
        ↓
Base.metadata.create_all()
```

Run the initializer deliberately from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.core.schema
```

The initializer:

- is available only when `APP_ENV=development`;
- imports the `app.models` registration package;
- uses B1's existing engine;
- creates missing registered tables;
- does not run during FastAPI startup;
- does not run from `/health`;
- does not implement drop/reset automation.

After B2 alone, the canonical metadata contains zero domain tables. Successful initialization that leaves the application table set empty is expected.

`Base.metadata.create_all()` is not a migration system. It creates missing registered tables but does not reliably transform existing tables when model definitions change. Any prototype reset/recreation remains manual and deliberate. No production migration guarantee is claimed.

## 6. Authentication and Authorization Architecture

### 6.1 Identity Flow

```text
OAuth 2.0 / OpenID Connect Provider
        ↓
FastAPI Authorization Callback
        ↓
State and Identity Validation
        ↓
Local VED User Mapping
        ↓
Local ADMIN / DESIGNER Authorization
```

Authentication is performed through a configurable external OAuth/OIDC provider. Authorization is determined by the local VED role and enforced by FastAPI. React visibility controls are only a UI convenience and are not sufficient authorization.

Current security requirements:

- OAuth client secrets remain server-side.
- Provider tokens and authorization codes must not be logged.
- OAuth state validation is required.
- OIDC identity validation is required when the selected flow uses OIDC.
- Provider selection remains configurable and deferred.
- Application session mechanics are deferred to the authentication implementation ticket.

There is no current local password authentication, `password_hash` requirement, or local JWT access/refresh-token architecture.

### 6.2 Conceptual Authentication Routes

| Endpoint | Method | Current conceptual purpose |
|---|---|---|
| `/api/auth/login` | GET | Start the configured OAuth/OIDC authorization flow |
| `/api/auth/callback` | GET | Validate the callback and resolve the external identity |
| `/api/auth/me` | GET | Return the authenticated local application user when implemented |

Exact provider integration, application-session mechanics, and response details remain deferred to the authentication tickets.

## 7. Database Schema Ownership

### 7.1 Implemented Through B2

Implemented schema infrastructure:

- one canonical `DeclarativeBase`;
- one canonical metadata registry;
- an explicit development schema initializer;
- zero application/domain tables.

### 7.2 Next: B3 Roles and Users

B3 owns the first domain tables:

- `roles`
- `users`

Supported B3 facts:

- Local roles are `ADMIN` and `DESIGNER`.
- Users map a verified external OAuth/OIDC identity to a local VED authorization role.
- A user supports an external provider identifier and provider subject/user identifier.
- Provider plus provider subject uniquely identify an external identity.
- Email and display name can be stored when supplied.
- Avatar/profile image URL is optional.
- A user references a valid local role.
- There is no local password or `password_hash`.

Exact column names, SQL types and lengths, primary-key type, timestamp/status fields, email uniqueness, role-name uniqueness, foreign-key delete behavior, additional indexes, role-seeding mechanism, provider selection, and application-session mechanics are implementation details deferred to B3 design.

### 7.3 Future Ticket-Owned Tables

The following are conceptual future entities and are not implemented through B2:

| Area | Planned concepts |
|---|---|
| Projects | `projects` |
| Floors and uploads | `project_floors`, `floor_plans` |
| Processing | `processing_jobs`, `processed_images` |
| Structural geometry | `rooms`, `walls`, `doors`, `windows` |
| Symbols and review | `symbol_legends`, `detected_symbols`, `manual_corrections` |
| Layout history | `layout_versions` |
| Routing | `electrical_panels`, `wiring_routes`, `route_segments` |
| Materials and pricing | `materials`, `material_prices`, `price_history` |
| Estimation | `estimates`, `estimate_items` |
| Reporting | `reports` |
| Audit | `audit_logs` |

Ticket ownership is defined by the Functional Spec. The conceptual list does not define unresolved columns or imply that these tables already exist.

### 7.4 Project and Floor-Plan Relationship

The planned hierarchy is:

```text
projects
    ↓
project_floors
    ↓
floor_plans
```

B4 owns projects. B5 owns project floors and floor-plan records. Original filename, stored filename/path, MIME type, file size, and processing status belong to the floor-plan/upload design when B5 is implemented. Original uploads must not be overwritten.

There is no generic application `files` table in the current Functional Spec. File metadata belongs to the record that owns the resource, while file contents remain filesystem-backed unless a later ticket explicitly changes that architecture.

### 7.5 Materials and Pricing

Material definitions and prices are separate concepts:

```text
materials
    ↓
material_prices
    ↓
price_history
```

Material prices must come from the database. Estimate items capture the price used at estimate generation so later administrative price changes do not silently rewrite historical estimates. Precision, currency representation, and unresolved pricing columns remain deferred to their schema tickets.

## 8. Canonical Geometry

Verified canonical project geometry is the shared downstream source:

```text
AI Detection
      ↓
Designer Verification
      ↓
Canonical Geometry
      ├──→ Konva 2D
      ├──→ Three.js 3D
      ├──→ Electrical Routing
      └──→ Material and Cost Calculation
```

2D and 3D must not maintain independent authoritative geometry. Konva state and Three.js scene data are derived representations. Planned `layout_versions` may store versioned snapshots when its ticket is implemented, but its fields are not defined here.

Conceptual canonical geometry includes:

- coordinate system and unit;
- floor/elevation association;
- walls;
- rooms;
- symbols;
- routes.

The exact shared contract belongs to the canonical-geometry ticket.

## 9. End-to-End Workflow

```text
OAuth/OIDC Sign-In
    ↓
Resolve Local VED User and Role
    ↓
Create/Open Project
    ↓
Upload Original Floor Plan
    ↓
Validate Input
    ↓
Preprocess Image
    ↓
Detect Walls and Electrical Symbols
    ↓
Designer Reviews and Corrects Results
    ↓
Save Verified Canonical Geometry
    ↓
Render Synchronized 2D and 3D Views
    ↓
Calculate Electrical Routes
    ↓
Calculate Material Quantities
    ↓
Generate Cost Estimate
    ↓
Generate PDF Report
```

Most workflow modules are planned future work. The completed foundation currently includes the frontend/backend foundations, B1 connectivity, and B2 schema infrastructure.

## 10. Conceptual API Areas

Resource-oriented API areas include:

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

These routes are conceptual and ticket-owned unless already implemented. They must use Pydantic request/response schemas, thin route handlers, service/repository layering, and server-side authorization.

## 11. AI Processing Pipeline

```text
Input Validation
    ↓
PDF-to-Image Conversion when needed
    ↓
Image Normalization
    ↓
Grayscale Conversion
    ↓
Noise Reduction / Gaussian Blur
    ↓
Thresholding
    ↓
Wall and Boundary Detection
    ↓
YOLO Symbol Detection
    ↓
Confidence Filtering
    ↓
Coordinate Normalization
    ↓
Designer Review
    ↓
Persist Verified Results
```

The default symbol-confidence threshold is configurable and currently documented as `0.50`. Low-confidence detections remain reviewable. Original AI class and confidence should be retained when a designer corrects a detection.

## 12. File Storage

Local development uses:

```text
storage/
├── uploads/
│   └── originals/
├── processed/
├── detections/
├── previews/
└── reports/
```

Original uploads are preserved separately and never overwritten by preprocessing, detection, preview, layout, or report output. Database records store paths and metadata rather than binary file contents unless a later approved ticket changes that design.

## 13. Routing, Materials, and Estimates

Routing consumes verified canonical geometry, including panels, devices, walls, floors, elevations, and valid vertical connectors. A* or the selected spatial pathfinding implementation must not replace valid electrical-path constraints with arbitrary diagonal shortcuts.

Routing output conceptually includes ordered points/segments and horizontal, vertical, and total length. Canonical route geometry—not Three.js mesh measurement—is authoritative for material quantities.

Backend estimation is authoritative:

```text
line_total = quantity × captured_unit_price
```

Historical estimates retain captured prices. Generated outputs are planning and estimation results, not permit-ready or professionally approved electrical plans.

## 14. Administration

Planned `ADMIN` capabilities include:

- local VED role assignment independently of external identity verification;
- symbol legend administration;
- material and price administration;
- administrative record and audit review.

Administration does not include creating password-backed accounts or managing local application passwords. Authentication remains external OAuth/OIDC identity verification, while authorization remains local FastAPI enforcement.

## 15. Testing and Evaluation Plan

Testing remains planned and should follow the framework choices present when each owning ticket is implemented.

| Test area | Planned focus |
|---|---|
| Backend and API | Configuration, database connectivity, validation, authentication, authorization, uploads, projects, materials, estimates, and reports |
| Geometry and routing | Coordinate transforms, 2D/3D alignment, A* routes, horizontal/vertical measurement, and multi-floor connections |
| AI/CV | Symbol precision/recall, confidence handling, wall detection, and normalized output |
| Costing | Quantities, captured prices, historical estimates, and authoritative totals |
| Performance | Large floor plans, processing time, scene responsiveness, and database queries |
| Usability | Upload, detection review, correction, visualization, estimation, and report workflows with VED designers |

Tests must not be claimed as passing until they are actually run.

## 16. Development Roadmap

| State | Ticket area | Responsibility |
|---|---|---|
| Complete | B1 | SQLAlchemy/PyMySQL connectivity to the configured MySQL-compatible database |
| Complete | B2 | Canonical Base and explicit development schema initializer |
| Next | B3 | OAuth-linked users and local roles tables |
| Planned | B4 | Projects |
| Planned | B5 | Project floors and floor plans |
| Planned | Later epics | Authentication, upload, processing, detection, canonical geometry, 2D/3D, routing, materials, estimation, reports, audit, and deployment |

The current prototype does not maintain migration files. Future work must follow the ticket sequence and acceptance criteria in the Functional Spec.

## 17. Repository Structure

### 17.1 Implemented Backend Foundation

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── routes/
│   │       └── health.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── schema.py
│   └── models/
│       ├── __init__.py
│       └── base.py
├── README.md
└── requirements.txt
```

### 17.2 Planned Feature Areas

```text
backend/app/
├── api/routes/
├── models/
├── schemas/
├── repositories/
├── services/
├── ai/
├── geometry/
├── routing/
└── reports/
```

Planned feature directories and model files are added only by their owning tickets. There is no current Alembic directory.

## 18. Assumptions and Boundaries

- FastAPI is the backend API framework.
- MySQL is the required database family; XAMPP is only the preferred Windows local workflow.
- Configuration and credentials come from environment variables.
- Authentication is provider-configurable OAuth 2.0/OIDC.
- Local authorization roles are `ADMIN` and `DESIGNER`.
- Original floor plans remain unchanged.
- Canonical verified geometry is the downstream source of truth.
- Cost calculations remain backend-authoritative.
- Ambiguous engineering, routing, price, schema, and provider behavior must not be guessed.
- Reports are planning/estimation outputs and require professional review where applicable.

## 19. Final Architecture Flows

Application data path:

```text
React Frontend
      ↓
FastAPI
      ↓
Service / Repository Architecture
      ↓
SQLAlchemy
      ↓
PyMySQL
      ↓
MySQL-Compatible Database
```

Authentication and authorization:

```text
OAuth/OIDC Provider
      ↓
FastAPI Identity Validation
      ↓
Local VED User
      ↓
ADMIN / DESIGNER Authorization
```

Floor-plan workflow:

```text
Floor Plan
      ↓
Preprocessing and Detection
      ↓
Designer Verification
      ↓
Canonical Geometry
      ├──→ 2D
      ├──→ 3D
      ├──→ Electrical Routing
      └──→ Material and Cost Estimation
```

Only completed tickets should be described as implemented. All other modules remain planned until their acceptance criteria are implemented and verified.
