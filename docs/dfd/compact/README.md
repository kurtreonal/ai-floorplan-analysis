# Compact VED data flow diagram

**Superseded design.** Use `../reference-rebuild/` for the current five-process overview and Level 2 continuation figures. This earlier single-column layout has been discarded.

The complete Level 1 DFD is on **one editable draw.io page**, with six connected processes. It replaces the earlier split-page presentation for this revision. The earlier artifacts and reference PDFs are preserved.

The design comes specifically from the current `C:/Users/kupal/Downloads/reference.pdf`, inspected on 12 October 2026. It now contains four DFD reference pages: one Level 1 overview and subsequent Level 2 continuations. Its rectangular entities, numbered rounded process boxes, open-ended data stores, plain black lines, and labeled arrows are used as design cues. The reference application's commerce, AR, support, registration, and account-management behavior is not copied into VED.

## Repository analysis

The current routes and services were rechecked before this revision. The actual data path is external OIDC sign-in, project and original-plan records, durable analysis and Designer review, canonical layout versions shared by 2D and 3D, measured routes, and backend estimates using captured prices. Each arrow is a data flow, rather than a screen-navigation instruction.

| Process | Repository ownership |
|---|---|
| 1.0 Authentication and Access Control | `backend/app/api/dependencies.py`, `backend/app/services/authentication.py`, auth routes |
| 2.0 Project and Floor Plan Management | Project/floor/upload routes and `backend/app/services/project_service.py` |
| 3.0 AI Analysis and Designer Review | Processing/detection/manual-symbol/symbol-legend routes and processing/review services |
| 4.0 Shared 2D/3D Layout Management | Layout routes and `backend/app/services/layout_service.py`; both visualizers consume canonical geometry |
| 5.0 Electrical Routing and Measurements | Routing routes/services, route versions and canonical measurements |
| 6.0 Materials and Cost Estimation | Material import routes, estimate routes, `backend/app/services/estimate_service.py` |

Client is a **planned** role. Its six dashed arrows represent three request/response pairs only: sign-in, authorized saved 2D/3D layout viewing, and stored captured-cost estimate viewing. There is no Client upload, editing, routing, catalog maintenance, estimate generation or export flow.

Current layout and estimate reads authorize ADMIN/DESIGNER, with DESIGNER writes. Project access currently implements Designer ownership or Admin access only. New external identities currently default to DESIGNER. A later implementation must introduce an explicit CLIENT policy, suitable identity provisioning, and project scope checks in the backend. Client project assignment policy has not been specified, so the DFD does not invent a sharing table or assignment workflow. No application source or database was changed by this diagram task.

## Logical stores

| Code | Meaning |
|---|---|
| D1 | User identities, roles and access/authority records |
| D2 | Projects, floors, original-source metadata and unchanged original files |
| D3 | Processing jobs/results, Designer review and approved legend records |
| D4 | Saved canonical layout versions |
| D5 | Saved measured routing versions |
| D6 | Material/catalog prices and historical estimate snapshots/items |

These are grouped logical DFD stores, not six new database tables. Repeated entity names and store codes represent the same actor or store. Process 5.0 passes route information and source geometry context to 6.0; estimate quantities and totals remain backend-authoritative. Historical estimate viewing reads captured prices rather than applying current prices.

## Verification

- PASS: one native editable XML page and six connected numbered processes.
- PASS: every process has inputs and outputs; all 46 arrows have labels.
- PASS: the Client has exactly the three allowed request/response pairs, marked planned.
- PASS: no direct entity-to-store or store-to-store shortcut flows.
- PASS: geometric checks find zero crossed arrows, node collisions, flow/label collisions or overlapping labels.
- PASS: text fits and the final PNG preview was visually inspected.
- NOT TESTED: import in the diagrams.net editor; XML was reopened and checked independently.
- NOT TESTED: application tests, which are outside this diagram-only change.

`verification.json` records delivery verification. `dfd-data.json`, SVG/PNG and `preview.html` use the same geometry as the draw.io file. `../build_compact_dfd.py` regenerates the document and runs its checks.
