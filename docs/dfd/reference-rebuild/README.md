# Reference-style VED DFD

This rebuild discards the previous split-row and single-column designs. The reference is the current four-page `C:/Users/kupal/Downloads/reference.pdf`; its application content is a design example, not VED requirements.

## How the reference is organized

- The first figure is a compact, staggered Level 1 overview of five broad processes.
- Subsequent pages are marked **Continuation** and decompose those parent processes into Level 2 subprocesses.
- One continuation page expands access; the next two pages each contain two smaller continuation figures.
- Processes are small rounded boxes with a numbered header. External actors use rectangular boxes. Logical data stores have an open right end and a code compartment.
- Labeled arrows take horizontal/vertical turns around the drawing and return to actors and stores. They do not form a sequence of large module panels.

The new draw.io document follows that structure with four tabs:

1. **Level 1 - Overview:** 1.0 Access, 2.0 Floor Plan Analysis and Review, 3.0 Layouts, 4.0 Routing and Measurements, 5.0 Materials and Cost Estimation.
2. **Continuation - Level 2.1 Access:** OIDC sign-in, local identity/role resolution, authorized session.
3. **Continuation - Level 2.2 and 2.3:** project/upload/analysis/review, then saving shared canonical geometry and reading an authorized 2D/3D layout.
4. **Continuation - Level 2.4 and 2.5:** retrieving metric geometry, generating/measuring routes, then catalog prices, captured estimates and authorized cost viewing.

Unlike crossings in the example, unavoidable long connections use paired letter circles. **K** carries the Client's cost-view request, **G** carries approved geometry, **L** carries canonical metric geometry, and **R** carries route data. Matching circles in the same logical view carry identical labels and data. The reference's actual commerce, registration/profile editing, support and AR-overlay processes were not copied.

## Project analysis

The relevant current files were rechecked: auth/project/layout/processing/symbol-legend/routing/material/estimate routes; authentication, project, layout, routing and estimate services; role dependencies; and the repository-wide AGENTS instructions. The drawing groups the actual durable processing/review workflow rather than treating raw AI output as final geometry. Source files remain unchanged, canonical geometry serves both visualizers, and saved estimates retain captured prices.

| Store | Logical meaning |
|---|---|
| D1 | External identity mapping, VED users and local roles/access records |
| D2 | Project/floor/source records, unchanged original files, durable jobs/results, Designer review and approved legends |
| D3 | Saved shared canonical layout versions |
| D4 | Saved measured route versions and source references |
| D5 | Material catalog/prices and historical estimate/item snapshots |

These are logical DFD stores, not new SQL tables. Repeated labels identify the same actor/store. Route data includes source/version context; estimates read canonical geometry for authoritative component quantities. Grouped request/result flows in the overview expand into their component flows in Level 2.

## Planned Client boundary

Client* is explicitly planned, as requested. In the sign-in figure it is one of the roles listed in the external-user rectangle; only its membership is planned. Its dedicated view arrows are dashed. Client can sign in, retrieve authorized saved 2D/3D layouts, and view stored captured estimates. It cannot upload, review, edit, generate routes, change prices, generate estimates or export reports.

The current backend allows ADMIN/DESIGNER reads and DESIGNER writes for layouts/estimates. Project authorization currently covers Designer ownership and Admin access, and new external identities default to DESIGNER. The later Client implementation needs explicit provisioning, a CLIENT role and server-enforced client/project scope. Project assignment rules have not been specified, so no new assignment table or workflow is invented. The read processes include those future authorization checks. No application or database changes were made for this diagram task.

## Verification

- PASS: four native editable draw.io tabs, five overview processes and fourteen Level 2 subprocesses.
- PASS: all five parent processes have continuation figures; paired letter flows carry matching data labels.
- PASS: the Client layout and estimate request/response labels balance between the overview and continuations; sign-in appears in both access figures.
- PASS: each process has input and output; no direct actor/store or store/store shortcuts.
- PASS: every arrow uses horizontal/vertical segments; geometric checks find no crossings, node collisions, other-flow label collisions, overlapping labels or overlapping nodes.
- PASS: text fits and final PNGs were visually inspected.
- NOT TESTED: import in the diagrams.net editor; the native XML was reopened and its references checked independently.
- NOT TESTED: application regression tests, outside this artifact-only task.

`verification.json` records the final Downloads copy check. PNG/SVG files and `preview.html` share the draw.io coordinates. `../build_reference_dfd.py` regenerates all four figures and runs their validations. Prior Downloads versions are backed up under `../superseded` when replacing them.
