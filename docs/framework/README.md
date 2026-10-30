# VED theoretical framework revision

The new design follows `C:/Users/kupal/Downloads/ref.pdf` as a **visual template only**: a gray central system column, stacked white modules, external people symbols, Internet context above, database below and separately labeled request/response arrows. The supplied `Theodore Framework (1).png` provides the VED subject and intended functions. Both source attachments are preserved.

## Module grouping

1. User and Access Management.
2. Project, Floor Plan and AI Review.
3. 2D/3D Visualization.
4. Electrical Routing and Measurements.
5. Cost Estimation and Reporting.

Project handling and Designer review of AI proposals are grouped together. Visualization is separated from input and AI review, so the Client's permission can be drawn explicitly. Routing remains separate from cost viewing. The reporting function from the supplied current framework is retained as a target capability for the Designer, not granted to the Client.

The Administrator is linked to the whole system boundary for access/legend/material-price administration. This summarizes administrative scope without implying that the Administrator designs routes or modifies Client outputs. The database is likewise linked to the whole system, rather than just the bottom module. The Internet cloud represents web access; it does not imply cloud AI inference.

## Client scope

Client connects **directly** to three modules using six dashed arrows, one request and one response per operation:

| Target | Request | Response / restriction |
|---|---|---|
| User and Access Management | Sign in and request access | Session/access result with read-only permissions |
| 2D/3D Visualization | Request saved layout | Authorized saved layout, view only |
| Cost Estimation and Reporting | Request stored cost estimate | Stored cost breakdown and total, view only |

There is no Client-to-Designer connection, upload, AI-review/correction, layout edit/save, routing, material-price change, estimate generation or report export. The fact that reporting shares the cost module does not grant Client reporting permission: the Client arrows specify only estimate retrieval.

Client remains **planned**, consistent with the earlier instruction that implementation comes later. The current layout/estimate routes and layout/project services still authorize ADMIN/DESIGNER reads; Designer owns write operations. The authentication service still provisions new external identities with a DESIGNER default. Later Client implementation therefore needs explicit CLIENT provisioning, role rules, project access scope and backend enforcement. The framework describes the proposed design; it does not claim those permissions or every target reporting/administration function are implemented. No application code or database was changed.

Relevant files checked: `backend/app/api/routes/layouts.py`, `estimates.py`, `materials.py`; `backend/app/services/authentication.py`, `project_service.py`, `layout_service.py`, `estimate_service.py`; repository AGENTS instructions.

## Files and verification

The draw.io document has one native editable page. Module boxes, people symbols, labels, cloud, database and arrow segments remain editable. PNG/SVG previews use the same coordinates. The very large source PNG was not decoded or modified; the attached image was used for its visible diagram content.

- PASS: five modules and three external roles.
- PASS: all 20 directional arrows have a corresponding reverse response/request.
- PASS: Client has exactly the three allowed operation pairs and no path through Designer.
- PASS: no crossed arrows, arrow/node collisions, other-arrow label collisions or overlapping flow labels.
- PASS: text fits and actor symbols do not overlap their role labels.
- PASS: native XML parses with valid references, without embedded raster diagram shapes.
- PASS: final preview visually reviewed.
- NOT TESTED: import in diagrams.net; saved XML is independently checked.
- NOT TESTED: application regression tests, outside this design-only request.

`verification.json` records delivery checks and source hashes. `build_framework.py` regenerates the artifact and validations.
