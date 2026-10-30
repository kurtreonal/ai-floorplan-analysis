# Theoretical framework: Admin rights restored explicitly

This revision keeps the **four original modules** in the supplied `Theodore Framework (1).png`. The PDF reference supplies only the visual design: gray central column, white module boxes, external user symbols, individually explained connections, Internet context above and the shared MySQL database below.

The prior redesign replaced Admin's separate module arrows with a generic system-boundary arrow. That hid capabilities and removed their explanation. This revision replaces it with twelve explicit Admin arrows: six operation/result pairs. No Admin capability is represented solely by an arrow to the system boundary.

## Admin capability audit

| Capability shown | State/evidence | Diagram connection |
|---|---|---|
| Sign in | OIDC auth routes and session dependencies | User and Access Management |
| Manage user records and VED roles | Original framework / AGENTS target; general user/role CRUD API not implemented | Access input and user/role result, marked planned |
| Assign/deactivate dataset approver; inspect assignment history | Admin-only `dataset_approver_assignments.py` routes | Access input and assignment-history result |
| Inspect all projects and floor-plan records | `project_service.py` grants Admin access to all projects; project, floor and floor-plan read routes allow Admin | Project/Floor Plan/Visualization input/result |
| Read job history/status and saved layouts | Processing and layout read routes allow Admin | Project/Floor Plan/Visualization result |
| Manage symbol legends, including trained import | Admin symbol-legend list/create/update/import routes | AI Analysis/Detection input/result |
| Inspect candidates, detection and review results | Detection/interpretation/review-image read routes allow Admin | AI Analysis/Detection input/result |
| Manage approved datasets | Original framework target; broader dataset CRUD is not established by the dataset-approver-assignment API | AI input/result, marked planned |
| Inspect saved routes and measured lengths | Routing GET permits Admin; route generation remains Designer-only | Routing/Cost/Reporting route-inspection input/result |
| Import/update global material catalog and prices | Admin-only material workbook preview/import routes | Catalog/price input and revision-status result |
| Inspect estimates, BOM and project-price versions | Estimate/BOM routes and project-pricing read routes allow Admin | Cost-inspection input and captured-cost/quantity result |
| Export cost/BOM CSV | Estimate/BOM export routes permit Admin | Cost-export input/result |
| Update report records and export PDF reports | Original theoretical framework target; no PDF report-management route is implemented | Report-record management and report export, marked planned |

The diagram does not grant Admin project editing, uploads, analysis execution, detection corrections, canonical layout writes, route generation or estimate generation. Those remain Designer operations under current route/service rules. Dataset review authority is separately assigned; Admin role alone must not be treated as an automatic project/dataset approval grant. Designer-specific project-price imports/assignments remain separate from Admin's global catalog-price administration.

## Designer and Client

The Designer retains twelve explicit arrows: sign-in, project/upload management, layout editing/saving, AI execution and human correction, route generation, and project pricing/estimate/report output.

Client remains planned and read-only. Its only logical pairs are:

- **A:** sign-in request and read-only access result.
- **V:** request an authorized saved 2D/3D layout and receive a read-only layout.
- **C:** request a stored estimate and receive captured costs.

Matching letter circles are continuation endpoints, not separate modules or additional people. They avoid crossings through the Designer's arrows. Each letter has exactly two matched labels and directions on its module side and Client side. Client does not gain the other functions in the Project/Visualization or Routing/Cost/Reporting modules and never passes through Designer. No project assignment mechanism is invented.

The source PNG and PDF are preserved. This is an artifact-only redesign; no product permissions, database records or application source were changed.

## Verification

- PASS: all four original module names/scopes retained.
- PASS: all six Admin operation/result groups explicitly connect to the responsible module.
- PASS: original user/role, project inspection, approved dataset/legend, material-price/report administration and cost/report export capabilities remain visible.
- PASS: additional implemented Admin read/authority permissions are shown without assigning Designer writes.
- PASS: all 38 physical arrows are paired; Client continuation labels match.
- PASS: zero crossed arrows, node collisions, other-flow label collisions or overlapping arrow labels; text fits.
- PASS: native draw.io XML parses with valid references and editable shapes/text.
- PASS: final PNG visually reviewed.
- NOT TESTED: diagrams.net editor import; independent XML checks were performed.
- NOT TESTED: application tests, outside this diagram-only task.

`verification.json` records the delivered files. `../build_framework_v2.py` rebuilds this revision. The earlier version is superseded.
