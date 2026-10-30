# System audit before revising the use case diagram

The previous diagram was not a precise description of implemented behavior. It mixed a proposed academic scope with the repository's current prototype. This revision follows a static inspection of API authorization, services and the user interface. No application behavior or permissions were changed. A code audit does not prove runtime success or production readiness.

## Current behavior

- **Identity:** OAuth/OIDC establishes identity and a local record supplies the VED role. `backend/app/services/authentication.py:13` defaults newly mapped identities to Designer. `backend/app/core/seed.py:10` seeds ADMIN and DESIGNER; no Client authorization path was found.
- **Admin access:** `backend/app/services/project_service.py:79` allows Admin to inspect any project, while Designers access owned projects. Read endpoints also allow Admin to inspect plans, processing/detection data, saved layouts, routes, estimates, BOM and pricing versions. Admin cannot gain Designer writes from the diagram's module-level associations.
- **Admin management:** `backend/app/api/routes/symbol_legends.py` implements legend administration. `dataset_approver_assignments.py` implements assignment/history/deactivation of a separately authorized dataset approver. `materials.py:35` and `:40` implement global price-workbook preview/import. Assigning an approver is not the same as general user/role management or approving all datasets automatically.
- **Projects/upload:** Designer-only project writes are in `backend/app/api/routes/projects.py`; upload is in `floor_plans.py:200`. `backend/app/services/floor_plan_upload.py:45` checks project/floor access and invokes storage. `floor_plan_storage.py:158` validates the original file before storing it. It does not invoke AI processing. The UI tolerates an `initial_job` field, but that is not evidence that the current upload service enqueues a job.
- **Analysis/review:** `backend/app/api/routes/processing.py:130` starts a separate processing job. `demo_interpretation_service.py:212` and detection routes persist human review/corrections. AI/CV results remain suggestions. Correction is optional within the review goal when the results already look correct; this does not make final engineering approval optional.
- **Draft versus approved geometry:** `frontend/src/features/detection-review/DemoInterpretationPage.jsx:468` can save a draft with `review_complete=false` and `approved_for_layout=false`. The draft workspace renders 2D/3D and provisional quantities/costs. Conversely, `backend/app/services/demo_interpretation_service.py:534` requires a complete approved review before publishing an approved canonical layout. The diagram therefore does not make approval a prerequisite for every preview.
- **Routing:** `backend/app/services/routing_service.py:25` previews circuits; `:52` creates route versions. Designer-only generation uses stored layout snapshots and rechecks them before publication. Circuit preview/save is distinct from final estimate generation.
- **Costs:** `backend/app/services/bom_service.py:44` produces BOM views, with draft validation and planning-cost support in `draft_bom_service.py`. `estimate_service.py:81` creates an authoritative versioned estimate using compatible stored routes, reviewed component quantities, explicit material mappings and captured catalog/project/item prices. It rejects unsupported saved planning circuits and stale inputs. No diagram claim is made that every new routing mode already supports final estimates.
- **Export:** `backend/app/api/routes/estimates.py:120` exports the stored estimate/BOM as CSV for Admin/Designer. `frontend/src/features/estimation/BOMPanel.jsx:56` exposes optional draft or saved BOM downloads. A saved estimate is read rather than repriced at download time.

## Planned, rather than currently implemented

1. Client provisioning and backend-enforced access to authorized saved 2D/3D layouts and saved cost estimates. The user's requested future Client is retained, but receives no editing, generation or export rights.
2. General user-record and application-role administration. Models and identity mapping do not establish a general Admin CRUD feature.
3. Broader approved-dataset management. Legend administration and approver assignments are implemented, but do not establish all dataset-management operations.
4. PDF report generation/administration. The current route inspection establishes CSV downloads, not an implemented PDF report API.

## Relationship decisions

The diagram uses two mandatory include relationships and two optional extend relationships, with directions, conditions and evidence documented in `README.md` and `verification.json`. Module-to-function dashed lines remain a presentation of module scope; they are not mislabeled execution dependencies. Admin connects only to modules, exactly as requested. The more detailed permissions above limit what that visual association means.

Validation covers editable XML, target references, module-only Admin associations, planned Client's three actions, dependency directions, monochrome graphics, text fit and unrelated-shape collisions. No runtime application test or diagrams.net editor-import test was run for this artifact-only change.
