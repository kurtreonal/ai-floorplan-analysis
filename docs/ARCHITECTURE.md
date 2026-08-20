# Implementation Architecture

> **Codex usage:** This document describes the intended implementation architecture and technology choices.
> The implementation backend is **FastAPI**, and the frontend uses **React with JavaScript/JSX**.
> References to Flask in the thesis source describe the earlier academic architecture and are not implementation instructions.

## 1. Source-Based System Understanding

The system is titled **“VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation.”** It is an undergraduate thesis system for Cavite State University - Bacoor City Campus under the Bachelor of Science in Computer Science program.

Based on the Markdown file, the system addresses the manual workflow used in electrical planning, where designers manually trace 2D blueprints, count electrical components, estimate wiring paths, and prepare material estimates. This manual process is described as time-consuming and prone to errors, especially for complex or unclear floor plans.

The main goal is to develop a system that can transform 2D residential blueprints into interactive 3D floor plans with integrated electrical layout and cost estimation. The project includes Computer Vision for symbol detection, 3D visualization, spatial routing, and SQL-based cost calculations.

The source architecture describes two primary actors: **User** and **Admin**. It also describes six major modules: floor plan input, AI image recognition, symbol detection and classification, layout generation, spatial routing algorithm, and cost estimation. The original backend in the source is Python Flask, but this plan updates the backend to FastAPI.

## 2. Target Users

| User | Source-Based Role | Main System Needs |
|---|---|---|
| Electrical Designer / User | Uploads floor plans, reviews 2D/3D layouts, edits/corrects symbols, views wiring overlay, and receives reports. | Faster symbol counting, visual checking, routing review, cost estimate generation. |
| Admin / Project Engineer | Maintains symbol datasets and material pricing database. | Manage symbols, update prices, review records, maintain official material costs. |
| VED Electrical Services | Organization affected by slow manual estimation, overestimation, and report preparation problems. | Improve workflow, reduce manual work, produce cleaner estimates and reports. |

## 3. Updated System Architecture Using FastAPI

### 3.1 Original Architecture From the Source

The uploaded architecture image and Markdown describe this flow:

```text
User/Admin
   ↓
React.js Frontend
   ↓
Floor Plan Input
   ↓
AI Image Recognition
   ↓
Symbol Detection & Classification
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

The source states that the floor plan image is sent to a Python Flask backend API, then processed through OpenCV, YOLOv8, Konva.js, Three.js, A* routing, and a MySQL pricing database.

### 3.2 Updated FastAPI Architecture

```text
React.js Frontend
│
├── User Dashboard
├── Project Upload Page
├── 2D Layout Editor using Konva.js
├── 3D Visualization using Three.js
├── Cost Estimation Page
└── Report Viewer

        │ REST API / JSON / Multipart Upload
        ▼

FastAPI Backend
│
├── Authentication & Role Access
├── Project Management API
├── Floor Plan Upload API
├── AI Processing Orchestrator
├── Symbol Detection API
├── Layout Metadata API
├── Spatial Routing API
├── Cost Estimation API
├── Report Generation API
└── Admin Management API

        │ Internal Python Service Calls
        ▼

AI / CV Processing Layer
│
├── PDF-to-Image Conversion
├── OpenCV Preprocessing
├── Wall and Boundary Detection
├── YOLO-Based Symbol Detection
├── Confidence Filtering
└── JSON Output Generation

        │ Read / Write
        ▼

SQL Database
│
├── Users and Roles
├── Projects
├── Floor Plans
├── Detected Symbols
├── Manual Corrections
├── 2D Layout Data
├── 3D Metadata
├── Routing Paths
├── Materials and Prices
├── Estimates
├── Reports
└── Audit Logs

        │ File References
        ▼

File Storage
│
├── Original Floor Plans
├── Converted Images
├── Processed Images
├── AI Result JSON
├── 3D Metadata JSON
└── Generated PDF Reports
```

### 3.3 FastAPI-Specific Change

The original document mentions a **Python Flask backend API**. In this updated plan, FastAPI replaces Flask as the backend controller for uploads, authentication, AI job orchestration, layout metadata, cost estimation, and report generation. The source concept stays the same; only the backend framework changes.

FastAPI is suitable here because the system needs file upload handling, API security, background processing, and JSON-based communication with the React frontend. FastAPI officially supports file uploads through `UploadFile`, security utilities such as OAuth2 helpers, and background tasks for operations that do not need to finish inside the initial request.

## 4. Recommended Tech Stack

### 4.1 Frontend

| Area | Recommended Stack | Purpose |
|---|---|---|
| Main Web UI | React.js + JavaScript | Dashboard, project pages, forms, editor screens. React uses components and Hooks for UI logic and state handling. |
| Build Tool | Vite | Fast local development for React. |
| Styling | Tailwind CSS or Bootstrap 5 | Professional responsive UI. |
| UI Components | shadcn/ui or Material UI | Tables, modals, drawers, forms, tabs. |
| Routing | React Router | Page navigation. |
| API Communication | Axios or TanStack Query | Connect frontend to FastAPI endpoints. |
| Form Handling | React Hook Form + Zod | Project forms, material forms, pricing forms. |
| 2D Canvas | Konva.js / React-Konva | Editable floor plan canvas, symbols, wiring paths. |
| 3D Visualization | Three.js + React Three Fiber | Interactive 3D floor plan visualization. Three.js is used for browser-based 3D rendering and commonly uses WebGL. |
| Report Preview | PDF.js or browser PDF viewer | Preview generated reports before download. |

### 4.2 Backend

| Area | Recommended Stack | Purpose |
|---|---|---|
| API Framework | FastAPI | REST API, file uploads, role-based endpoints. |
| Server | Uvicorn | ASGI server for FastAPI. |
| Data Validation | Pydantic models | Request and response validation. |
| ORM | SQLAlchemy | Database models and queries. SQLAlchemy provides ORM support for Python database work. |
| Migrations | Alembic | Schema migrations. Alembic is a database migration tool for SQLAlchemy. |
| Authentication | JWT access tokens + refresh tokens | User and admin login. |
| Authorization | Role-based access control | Separate User and Admin permissions. |
| Background Jobs | FastAPI BackgroundTasks for simple jobs; Celery/RQ for heavy AI jobs | AI processing and PDF generation. FastAPI includes background task support for request-related background work. |
| Report Generation | WeasyPrint, ReportLab, or HTML-to-PDF service | Generate PDF reports. |
| Logging | Python logging + database audit logs | Track uploads, edits, price changes, and report generation. |

### 4.3 AI and Computer Vision

| Area | Recommended Stack | Purpose |
|---|---|---|
| Image Processing | OpenCV | Grayscale conversion, thresholding, noise reduction, wall detection. |
| Wall Detection | OpenCV Hough Line Transform / contour detection | Detect wall lines and boundaries. OpenCV documents HoughLines and HoughLinesP for line detection, usually after preprocessing or edge detection. |
| Symbol Detection | Ultralytics YOLO model | Detect outlets, switches, lights, data ports, and other standard symbols. Ultralytics supports YOLO model training and prediction through Python usage. |
| Annotation | Roboflow, CVAT, or Label Studio | Prepare annotated floor plan dataset. |
| Model Format | `.pt` for training/inference; optional ONNX export later | Model deployment. |
| AI Output | JSON | Store detected class, confidence, bounding box, center point, scale, and room reference. |

### 4.4 Database

Recommended database: **PostgreSQL** for production or **MySQL** if the thesis must follow the original architecture. The source mentions MySQL as the database storing detected symbol records, material pricing, and project history.

For thesis consistency, use:

```text
MySQL + SQLAlchemy + Alembic
```

For stronger future scalability, use:

```text
PostgreSQL + SQLAlchemy + Alembic
```

### 4.5 File Storage

| Environment | Recommended Storage |
|---|---|
| Local Development | `/storage/uploads`, `/storage/processed`, `/storage/reports` |
| Production | S3-compatible object storage, Supabase Storage, Cloudflare R2, or server-mounted storage |
| Database Storage | Store only file metadata and file paths, not full files as database blobs |

## 5. Detailed End-to-End Workflow

| Step | User Action | Frontend Action | FastAPI Action | AI Module Action | Database Saved | Output |
|---|---|---|---|---|---|---|
| 1. Login | User/Admin enters credentials. | Sends login form to API. | Validates user and returns token. | None. | Login audit log. | Authenticated session. |
| 2. Project Creation | User creates project. | Sends project details. | Creates project record. | None. | `projects`. | Project workspace. |
| 3. Floor Plan Upload | User uploads JPEG, PNG, or PDF. | Sends multipart file upload. | Validates type, size, and project ownership. | None yet. | `floor_plans`. | Stored original file. |
| 4. File Validation | User waits for validation. | Shows upload status. | Checks format, resolution, and file integrity. | May convert PDF page to image. | `processing_jobs`. | Valid or rejected upload. |
| 5. Image Preprocessing | User starts analysis. | Calls process endpoint. | Creates AI job. | Converts to grayscale, reduces noise, applies thresholding. | `processed_images`. | Cleaned image. |
| 6. Wall Detection | None. | Shows progress. | Receives wall result. | Uses line/contour detection. | `walls`, `rooms`. | Wall coordinate JSON. |
| 7. Symbol Detection | None. | Shows progress. | Calls YOLO inference service. | Detects symbols and classifications. | `detected_symbols`. | Symbol JSON. |
| 8. Confidence Filtering | None. | Displays review warnings. | Filters detections below threshold. | Marks low-confidence detections. | `detected_symbols.confidence`. | Accepted and flagged symbols. |
| 9. 2D Canvas Generation | User views editable 2D layout. | Renders walls, rooms, and symbols in Konva. | Provides layout JSON. | None. | `layout_2d`. | Interactive 2D editor. |
| 10. Manual Correction | User moves, adds, deletes, or corrects symbols. | Updates canvas state. | Saves corrected layout. | None, unless retraining data is collected. | `manual_corrections`, `layout_2d`. | Corrected layout. |
| 11. 3D Generation | User switches to 3D view. | Sends corrected 2D layout request. | Converts layout metadata to 3D-ready JSON. | None. | `layout_3d_metadata`. | Three.js scene data. |
| 12. Spatial Routing | User requests wiring route. | Sends selected panel and symbol points. | Runs routing algorithm. | None, unless routing uses CV-derived wall data. | `wiring_routes`. | Wiring overlay and route length. |
| 13. Material Calculation | User reviews quantities. | Displays quantity table. | Calculates wire/conduit length and symbol counts. | None. | `estimate_items`. | Material quantity list. |
| 14. Cost Estimation | User generates estimate. | Requests costing. | Reads material prices and calculates totals. | None. | `estimates`, `estimate_items`. | Bill of Materials. |
| 15. Admin Price Update | Admin updates material prices. | Sends material price changes. | Validates role and saves update. | None. | `materials`, `price_history`, `audit_logs`. | Updated pricing. |
| 16. Report Generation | User clicks generate report. | Sends report request. | Generates PDF report. | None. | `reports`. | PDF file. |
| 17. Export PDF | User downloads PDF. | Opens or downloads report. | Returns report file. | None. | Download audit log. | Exported PDF. |
| 18. History Tracking | User reviews saved projects. | Loads project list and reports. | Retrieves records. | None. | Existing tables. | Project history page. |

## 6. FastAPI Backend Plan

### 6.1 Route Groups

| Endpoint | Method | Purpose | Request Data | Response Data | Tables Affected |
|---|---|---|---|---|---|
| `/api/auth/login` | POST | Authenticate user/admin. | Email, password. | Access token, user profile, role. | `users`, `audit_logs` |
| `/api/auth/me` | GET | Get current authenticated user. | Token. | User profile. | None |
| `/api/users` | GET | Admin lists users. | Token. | User list. | `users` |
| `/api/users` | POST | Admin creates user. | Name, email, password, role. | Created user. | `users`, `roles`, `audit_logs` |
| `/api/projects` | GET | List user projects. | Token. | Projects. | `projects` |
| `/api/projects` | POST | Create project. | Project name, client, location, description. | Project details. | `projects` |
| `/api/projects/{project_id}` | GET | Open project workspace. | Project ID. | Project details, layouts, estimates. | Multiple read-only |
| `/api/projects/{project_id}` | PATCH | Update project info. | Project fields. | Updated project. | `projects`, `audit_logs` |
| `/api/projects/{project_id}/floor-plans` | POST | Upload floor plan. | JPEG, PNG, or PDF file. | Floor plan record. | `floor_plans`, `files`, `audit_logs` |
| `/api/floor-plans/{floor_plan_id}/process` | POST | Start AI analysis. | Floor plan ID. | Processing job ID. | `processing_jobs` |
| `/api/jobs/{job_id}` | GET | Check AI processing status. | Job ID. | Status, progress, errors. | `processing_jobs` |
| `/api/floor-plans/{floor_plan_id}/detections` | GET | Get detected symbols. | Floor plan ID. | Symbol JSON. | `detected_symbols` |
| `/api/layouts/2d/{project_id}` | GET | Load 2D layout. | Project ID. | Konva-ready JSON. | `layout_2d`, `detected_symbols`, `walls` |
| `/api/layouts/2d/{project_id}` | PUT | Save manual edits. | Updated layout JSON. | Saved layout. | `layout_2d`, `manual_corrections` |
| `/api/layouts/3d/{project_id}` | GET | Load 3D metadata. | Project ID. | Three.js-ready JSON. | `layout_3d_metadata` |
| `/api/routes/{project_id}/calculate` | POST | Calculate wiring paths. | Panel location, selected symbols, routing options. | Routes and total lengths. | `wiring_routes` |
| `/api/materials` | GET | List material library. | Token. | Materials and prices. | `materials` |
| `/api/materials` | POST | Admin adds material. | Material data. | Created material. | `materials`, `audit_logs` |
| `/api/materials/{material_id}` | PATCH | Admin updates price. | New price, unit, effective date. | Updated material. | `materials`, `price_history`, `audit_logs` |
| `/api/estimates/{project_id}/generate` | POST | Generate cost estimate. | Project ID, selected pricing set. | Estimate summary. | `estimates`, `estimate_items` |
| `/api/reports/{project_id}/generate` | POST | Generate PDF report. | Project ID, estimate ID. | Report metadata and file URL. | `reports` |
| `/api/reports/{report_id}/download` | GET | Download PDF report. | Report ID. | PDF file. | `audit_logs` |
| `/api/admin/audit-logs` | GET | Admin reviews system actions. | Filters. | Audit logs. | `audit_logs` |

## 7. Proposed SQL Database Design

### 7.1 Core User Tables

| Table | Important Fields | Notes |
|---|---|---|
| `roles` | `id`, `name`, `description` | Example roles: `admin`, `electrical_designer`, `project_engineer`. |
| `users` | `id`, `role_id`, `full_name`, `email`, `password_hash`, `status`, `created_at` | Stores account records. |
| `audit_logs` | `id`, `user_id`, `action`, `entity_type`, `entity_id`, `details_json`, `created_at` | Tracks uploads, edits, pricing changes, and report generation. |

### 7.2 Project and Floor Plan Tables

| Table | Important Fields | Notes |
|---|---|---|
| `projects` | `id`, `owner_id`, `project_name`, `client_name`, `location`, `description`, `status`, `created_at`, `updated_at` | Main project workspace. |
| `floor_plans` | `id`, `project_id`, `original_filename`, `file_type`, `file_path`, `page_number`, `resolution_width`, `resolution_height`, `status` | Stores uploaded floor plan metadata. |
| `processed_images` | `id`, `floor_plan_id`, `processed_type`, `file_path`, `parameters_json`, `created_at` | Stores cleaned image outputs. |
| `processing_jobs` | `id`, `floor_plan_id`, `job_type`, `status`, `progress`, `error_message`, `started_at`, `finished_at` | Tracks AI processing jobs. |

### 7.3 AI Detection and Layout Tables

| Table | Important Fields | Notes |
|---|---|---|
| `walls` | `id`, `floor_plan_id`, `start_x`, `start_y`, `end_x`, `end_y`, `thickness`, `confidence` | Stores wall line geometry. |
| `rooms` | `id`, `floor_plan_id`, `name`, `polygon_json`, `area`, `created_at` | Optional room segmentation. |
| `symbol_legends` | `id`, `symbol_code`, `symbol_name`, `description`, `icon_path`, `is_active` | Company standard electrical symbols. |
| `detected_symbols` | `id`, `floor_plan_id`, `symbol_legend_id`, `class_name`, `confidence`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `center_x`, `center_y`, `status` | Stores AI output. |
| `manual_corrections` | `id`, `project_id`, `detected_symbol_id`, `correction_type`, `old_value_json`, `new_value_json`, `corrected_by`, `created_at` | Tracks user edits. |
| `layout_2d` | `id`, `project_id`, `layout_json`, `scale_ratio`, `updated_by`, `updated_at` | Stores Konva-ready layout. |
| `layout_3d_metadata` | `id`, `project_id`, `metadata_json`, `wall_height`, `scale_ratio`, `updated_at` | Stores Three.js-ready metadata. |

### 7.4 Routing, Materials, Estimates, and Reports

| Table | Important Fields | Notes |
|---|---|---|
| `wiring_routes` | `id`, `project_id`, `source_symbol_id`, `target_symbol_id`, `route_points_json`, `route_type`, `total_length_meters` | Stores A* route output. |
| `materials` | `id`, `material_code`, `name`, `unit`, `current_price`, `category`, `is_active` | Official company material list. |
| `price_history` | `id`, `material_id`, `old_price`, `new_price`, `updated_by`, `effective_date` | Tracks pricing changes. |
| `estimates` | `id`, `project_id`, `created_by`, `subtotal`, `contingency`, `labor_cost`, `grand_total`, `status`, `created_at` | Estimate header. |
| `estimate_items` | `id`, `estimate_id`, `material_id`, `quantity`, `unit_price`, `line_total`, `basis_json` | Bill of Materials rows. |
| `reports` | `id`, `project_id`, `estimate_id`, `report_type`, `file_path`, `generated_by`, `created_at` | PDF report metadata. |

## 8. AI Processing Pipeline

### 8.1 Accepted Inputs

The source states that the Electrical Designer uploads digital floor plans in **JPEG, PNG, or PDF format**.

Recommended validation:

```text
Accepted: .jpg, .jpeg, .png, .pdf
Rejected: hand-drawn sketches, very low-resolution images, corrupted files, unsupported CAD files
```

The source states that hand-drawn sketches and low-resolution images are outside the system’s supported scope because they may cause detection errors.

### 8.2 Processing Flow

```text
Upload
  ↓
Validate file
  ↓
If PDF: convert selected page to image
  ↓
Normalize image size and scale
  ↓
Convert to grayscale
  ↓
Apply Gaussian blur / noise reduction
  ↓
Apply thresholding
  ↓
Detect walls and boundaries using line/contour detection
  ↓
Run YOLO symbol detection
  ↓
Filter low confidence detections
  ↓
Store detected symbols and wall geometry
  ↓
Send JSON to frontend
```

The source specifically mentions grayscale conversion, Gaussian blur, noise removal, binary thresholding, Hough Line Transform, and YOLOv8-based symbol detection.

### 8.3 AI JSON Output Structure

```json
{
  "floor_plan_id": 1,
  "image_width": 2400,
  "image_height": 1800,
  "scale_ratio": "1px = 0.01m",
  "walls": [
    {
      "start": { "x": 120, "y": 200 },
      "end": { "x": 900, "y": 200 },
      "confidence": 0.91
    }
  ],
  "symbols": [
    {
      "class_name": "power_outlet",
      "confidence": 0.88,
      "bbox": { "x": 350, "y": 420, "w": 32, "h": 32 },
      "center": { "x": 366, "y": 436 },
      "status": "accepted"
    }
  ],
  "low_confidence_symbols": [
    {
      "class_name": "switch",
      "confidence": 0.42,
      "bbox": { "x": 700, "y": 520, "w": 28, "h": 28 },
      "status": "needs_review"
    }
  ]
}
```

The source mentions a confidence threshold of **0.5** for symbol detections.

## 9. 2D and 3D Visualization Workflow

### 9.1 2D Layout Using Konva.js

The 2D editor should display:

- Original blueprint as a locked background layer.
- Detected walls and room boundaries as editable vector lines.
- Detected symbols as draggable icons.
- Wiring routes as editable polyline overlays.
- Low-confidence symbols highlighted for review.
- Manual tools for adding outlets, switches, lights, data ports, and conduits.

The source states that layout generation uses Konva.js for the interactive 2D canvas and Three.js for 3D visualization through 2D-to-3D wall reconstruction.

### 9.2 3D Visualization Using Three.js

The 3D view should generate:

- Floor plane from the 2D room boundary.
- Walls extruded from 2D line coordinates.
- Electrical symbols positioned on walls or floor/ceiling surfaces.
- Wiring and conduit routes as 3D paths.
- Camera controls for orbit, zoom, and pan.
- Toggle controls for showing/hiding wiring, conduits, symbols, and cost layers.

### 9.3 2D-to-3D Mapping

```text
2D wall line → 3D wall mesh
2D room polygon → 3D floor area
2D symbol point → 3D electrical fixture placement
2D wiring polyline → 3D wiring/conduit route
2D scale ratio → real-world measurement conversion
```

[Inference] The system should use one shared coordinate model for both Konva.js and Three.js so that manual edits in 2D can update the 3D layout without duplicating layout logic.

## 10. Spatial Routing and Cost Estimation Plan

### 10.1 Routing Concept

The source states that the Spatial Routing Algorithm applies **A\* pathfinding** to compute optimal wiring paths between detected symbols and the electrical panel while calculating total wire lengths in metres and navigating wall boundaries.

Recommended routing inputs:

```text
- Electrical panel location
- Symbol coordinates
- Wall coordinates
- Room boundaries
- Routing mode: wall-embedded, ceiling-level, floor-level
- Vertical elevation rules
- Scale ratio from pixels to meters
```

### 10.2 Routing Output

```json
{
  "route_id": 1,
  "source": "panel_main",
  "target": "power_outlet_12",
  "route_type": "wall_embedded",
  "points": [
    { "x": 100, "y": 200, "z": 0 },
    { "x": 100, "y": 200, "z": 2.4 },
    { "x": 600, "y": 200, "z": 2.4 },
    { "x": 600, "y": 420, "z": 0.4 }
  ],
  "total_length_meters": 8.75
}
```

### 10.3 Cost Estimation

The source states that the Cost Estimation Module receives symbol quantities and wire lengths, then queries the MySQL pricing database to compute an itemized Bill of Materials and total project cost.

Recommended costing formula:

```text
Material Cost = Quantity × Unit Price
Route Material Quantity = Total Route Length × Material Conversion Rule
Subtotal = Sum of Material Costs
Grand Total = Subtotal + Labor Cost + Optional Contingency
```

[Inference] To avoid excessive overestimation, the system should separate computed wire length, safety allowance, and manually added contingency as different estimate fields instead of hiding extra allowance inside the raw route length.

## 11. Admin Workflow

The Admin should have a separate dashboard for:

1. Managing symbol legend records.
2. Uploading or updating symbol reference images.
3. Managing material names, categories, units, and prices.
4. Reviewing project estimates.
5. Viewing generated reports.
6. Managing users and roles.
7. Checking audit logs.
8. Reviewing manually corrected detections that may be reused for dataset improvement.

The source states that the Admin maintains the symbol dataset and material pricing database.

## 12. Testing and Evaluation Plan

The source states that the system should be tested through AI symbol recognition accuracy validation, manual count versus AI count comparison, unit testing for 3D spatial alignment, SQL-based cost calculations, and ISO 25010 evaluation for functional suitability, usability, and performance efficiency.

| Test Area | What to Test | Suggested Method |
|---|---|---|
| Unit Testing | Cost formulas, route length calculations, file validators. | Pytest for FastAPI services. |
| API Testing | Authentication, uploads, projects, materials, reports. | Pytest + HTTPX or Postman. |
| Frontend Testing | Project creation, canvas editing, 3D viewer controls. | React Testing Library. |
| AI Accuracy Testing | Symbol detection correctness. | Compare AI count vs manual count. |
| Wall Detection Testing | Wall coordinate accuracy. | Compare detected walls against manually marked floor plans. |
| 2D-to-3D Alignment | Correct placement of walls and symbols in 3D. | Visual inspection + coordinate tests. |
| Cost Calculation Testing | Material quantities and total estimate. | Compare generated estimate against manually computed sample. |
| Usability Testing | Ease of upload, correction, viewing, and report export. | User evaluation with VED designers. |
| Performance Testing | Upload time, AI processing time, 3D rendering smoothness. | Measure processing duration and FPS. |
| ISO 25010 Evaluation | Functional suitability, usability, performance efficiency. | Survey and rubric-based validation. |

## 13. Development Roadmap

| Phase | Deliverables | Dependencies |
|---|---|---|
| 1. Requirements Finalization | Final module list, user roles, accepted file types, symbol list. | Interview notes, thesis scope. |
| 2. UI/UX and Figma Refinement | User dashboard, admin dashboard, upload page, 2D editor, 3D viewer, report page. | Confirmed workflow. |
| 3. Database Design | ERD, SQL schema, migration files. | Final data requirements. |
| 4. FastAPI Backend Setup | Project structure, routers, database connection, environment config. | Database decision. |
| 5. Authentication and Project Management | Login, roles, project CRUD. | Backend setup. |
| 6. File Upload System | Floor plan upload, validation, storage paths. | Auth and project module. |
| 7. AI Preprocessing Pipeline | PDF conversion, image cleanup, wall detection prototype. | Upload module. |
| 8. Symbol Detection Integration | YOLO model inference, confidence filtering, result JSON. | Dataset and trained model. |
| 9. 2D Canvas Editor | Konva-based layout editor, manual correction tools. | AI output format. |
| 10. 3D Visualization Module | Three.js scene generation from 2D metadata. | Stable layout JSON. |
| 11. Spatial Routing Module | A* routing, route length calculation, route overlays. | Wall and symbol coordinates. |
| 12. Cost Estimation Module | Material quantity calculation, price lookup, estimate summary. | Routing and material database. |
| 13. PDF Report Generation | Exportable Bill of Materials and layout summary. | Estimate module. |
| 14. Admin Dashboard | Symbol management, material pricing, users, audit logs. | Auth and database tables. |
| 15. Testing and Evaluation | Unit, API, AI accuracy, usability, ISO 25010 testing. | Feature-complete prototype. |
| 16. Deployment and Documentation | Local setup guide, production setup guide, user manual. | Tested system. |

## 14. Recommended Folder Structure

```text
ved-electrical-system/
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── projects/
│   │   │   ├── floor-plans/
│   │   │   ├── layout-2d/
│   │   │   ├── layout-3d/
│   │   │   ├── estimates/
│   │   │   └── admin/
│   │   ├── services/
│   │   ├── types/
│   │   └── utils/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── projects.py
│   │   │   ├── floor_plans.py
│   │   │   ├── ai_processing.py
│   │   │   ├── layouts.py
│   │   │   ├── routing.py
│   │   │   ├── materials.py
│   │   │   ├── estimates.py
│   │   │   └── reports.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── ai/
│   │   │   ├── preprocessing.py
│   │   │   ├── wall_detection.py
│   │   │   ├── symbol_detection.py
│   │   │   └── output_formatter.py
│   │   ├── routing/
│   │   ├── reports/
│   │   └── database.py
│   ├── alembic/
│   └── requirements.txt
│
├── storage/
│   ├── uploads/
│   ├── processed/
│   ├── ai-results/
│   └── reports/
│
├── models/
│   └── yolo-symbol-detector.pt
│
└── docs/
    ├── architecture.md
    ├── api-routes.md
    ├── database-schema.md
    └── user-manual.md
```

## 15. Assumptions and Boundaries

[Inference] The system should use FastAPI as the main backend API, while AI processing remains in Python modules under the same backend project or a separate worker service.

[Inference] The system should store files in object storage or local storage and keep only file paths and metadata in the SQL database.

[Inference] The system should keep the original uploaded blueprint unchanged because the source states that the system uses the uploaded blueprint as a reference and does not modify it.

[Inference] The cost estimate should be treated as a planning estimate only because the source states that layouts and cost estimates still require review, validation, and signature by a Licensed Professional Engineer before installation or permit use.

## 16. Final Recommended System Flow

```text
User uploads floor plan
        ↓
FastAPI validates and stores file
        ↓
AI module preprocesses image
        ↓
OpenCV detects walls and boundaries
        ↓
YOLO detects electrical symbols
        ↓
FastAPI saves AI result JSON
        ↓
React renders editable 2D layout in Konva.js
        ↓
User reviews and corrects layout
        ↓
FastAPI saves corrected 2D layout
        ↓
Three.js generates interactive 3D model
        ↓
Routing module calculates wiring/conduit paths
        ↓
Cost module calculates materials and prices
        ↓
System generates Bill of Materials and PDF report
        ↓
Project history stores layouts, estimates, and reports
```

This plan preserves the original thesis concept while replacing the Flask backend with a FastAPI-centered backend architecture.