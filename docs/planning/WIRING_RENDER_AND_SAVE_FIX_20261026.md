# Plan 9379: wiring save and 3D presentation

## Save failure

Local backend logs contained repeated HTTP422 responses for plan 9379 review saves. A source-bound replay reproduced `INVALID_WIRING_JUNCTION` when a new manual path joined an existing trace. The request schema accepted the connected geometry, but `annotate_wiring` subsequently derived the manual wire's installation from its unknown stroke instead of the inherited network placement. It also cleared placement on unresolved generated proposals. Final network validation then rejected the now-inconsistent junction.

Annotation now respects explicit Designer placement independently of stroke style and retains known placement on proposals without clearing their unresolved assignment state. Active explicit legend mappings still take precedence; a missing drawing-specific mapping is not fabricated. Genuine conflicting circuits/heights/junctions remain rejected. Original observed and generated provenance stays separate.

The public endpoint now describes junction, attachment and page-boundary problems instead of showing the opaque “demo interpretation” message. The frontend handles both API error envelopes and bounded validation guidance, without exposing raw validation inputs or server traces.

## 3D presentation

Whole-path uniform sampling could miss short legs and pinned bends, causing the tube to cut diagonally across corners. Tubes, enlarged pick geometry and inspection strokes now share a local-curve sampling path that includes every pinned bend. Physical tubes use normal depth testing; a thin inspection stroke retains visibility through walls. The additional raw dashed stroke was removed from generated route rendering.

Draft, canonical and routing viewers no longer fan runs into artificial parallel lanes. Their source-coordinate paths and resolved heights remain authoritative. Unresolved automatic proposals appear as lighter dashed inspection paths with retained pick targets/handles, rather than extra solid physical conduits. Accepted routes remain solid. These changes are display-only and do not change engineering coordinates, conduit diameters, quantities or captured prices.

## Verification

| Criterion | Status | Evidence |
| --- | --- | --- |
| Save a new wire joined to the existing network | PASS | The same source-bound request failed before the fix and passed afterward, including API response serialization. The database transaction was rolled back; current run300 still had zero saved reviews afterward. |
| Preserve source geometry | PASS | Real plan9379 review7 was projected without changing its input data. Fifteen on-path pinned anchors missed by the old mesh sampling were all retained by the new path; no non-finite mesh coordinates or display lane offsets. |
| Actual WebGL output | PASS | Current plan9379/job24375 inspected in Isometric and Top views. Solid routes and dashed proposals rendered; browser error log empty. Camera returned to Isometric. No plan edits were saved in the browser. |
| Frontend checks | PASS | Vite build: 2,239 modules. Focused ESLint: six changed frontend modules. Existing large-chunk warning remains. |
| Backend syntax | PASS | Parsed both changed Python modules. |
| Full Designer drawing/save/reopen walkthrough | NOT TESTED | Left to the user as requested. The transaction check verifies the save service and response contract without publishing diagnostic geometry. |
| Automated suites | NOT TESTED | No test files added/changed and no test suite run for this checkpoint. |

The supplied comparison images informed the visual investigation. The raw source-bound diagnostics and screenshots remain local under `outputs/wiring-save-20261026/`, excluded from Git. The current analysis is job24375; historical job24353/review7 remains preserved. Saving against a superseded analysis continues to require opening the current result.

## Files and integrity

- Save: `backend/app/services/wiring_legend_service.py`, `backend/app/api/routes/demo_interpretation.py`, `frontend/src/api/demoInterpretation.js`.
- Rendering: `wiringPresentation.js`, `WiringTube3D.jsx`, `RouteLines3D.jsx`, `DraftWiring3D.jsx`, `CanonicalScene.jsx`.
- No table/migration, authentication change, route regeneration, detector retuning or price update. Originals, prior reviews, approved versions, historical estimates and existing worktree/stash were retained. No commit or push performed.
