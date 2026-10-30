# Wiring, Client access, pricing removal and Admin presentation

## Scope and implementation

- Wiring extensions and endpoint magnets inherit missing circuit/height/placement settings from an explicitly joined network. Conflicting explicit values remain blocked. Stale drag previews are revalidated. The 2D magnet radius is 22 screen pixels, independent of zoom. Handles have a 28-pixel invisible grab area so overlapping devices do not steal slightly imprecise drags. Observed/manual and generated origins remain recorded separately even when the Designer explicitly joins them.
- Generated proposals become eligible for measurement only after both endpoints have explicit connections and their installation method is specified; missing scale/heights/products remain separate incomplete inputs. A* proposals do not become observed evidence.
- Homerun A* proposals start at an existing explicit trace endpoint where one is available. Multiple anchors, multiple panels or a conflicting written panel reference remain unresolved. Edited routes and removal tombstones are preserved. Unedited proposals can be refreshed without replacing reviewed geometry.
- New-wire placement follows the dominant specified method. Backend suggestions are scoped to one plan region; other drawings cannot supply its majority, and a tie stays unspecified. Ceiling is no longer the toolbar fallback. Inspector instructions are shorter and height/conductor/circuit fields are collapsed.
- Client access now includes the exact immutable, Admin-approved saved review, not subsequent Designer revisions or unsaved drafts. Only associated Clients can retrieve it. Geometry is whitelisted; unpublished item prices, candidate diagnostics and private paths are excluded. Read-only 2D/3D reuse the existing geometry renderers. A captured estimate remains a separate publication, and unscaled 3D is labelled illustrative.
- Designer project queries already enforced ownership. Project lists now reload on identity/role changes, discard aborted responses and clear the old list. This does not expand project authorization.
- BOM downloads are real XLSX files with wrapped descriptions, fixed column widths, numeric quantities/amounts, frozen/filterable headers, alternating rows and landscape print setup. Existing CSV endpoints remain compatible through the default format; the UI requests `format=xlsx`. Formatting does not recalculate prices or quantities. Missing prices stay blank, and supplier text cannot execute formulas.
- Remove client pricing detaches uploaded price lists, records activity and appends a new item-assignment revision. It keeps manual price overrides, uploaded source bytes, old assignment revisions and captured estimates. Repeating the operation is idempotent. The confirmation explains its project-wide scope.
- Admin sections now have grouped navigation and a single page heading. Users have fitted columns and wrapping; long pairing specifications remain collapsed. Under-floor alternatives are visible next to the default product. Existing legend/import form state is retained across section changes.
- Fixed an existing glyph fallback null dereference exposed by the Client preview: an absent legend image now renders the procedural symbol instead of blanking the canvas.

## Material review and data change

The active supplier catalog contains EMT tubing, IMC/RSC pipe and flexible/liquid-tight conduit. Supplier item names are retained verbatim, including products called “EMT pipe”; matching does not treat their nominal trade size as a measured bore or interchangeable fitting size.

Cable discovery no longer excludes products merely because their category is a brand such as ALANTEK. Conduit discovery includes roll-priced flexible products. Actual outside diameters, fill and installation approval are not present in the supplied price data and are not fabricated.

The authorized local default correction moved revision **4 to 5**, from **19 to 27** provisional cable pairs. Five outdoor-labelled products use IMC by default; indoor products use their provisional indoor selection, and the 27 products have IMC under-floor alternatives. Only the previous generated assumptions were replaced; there were no custom pairs to replace. Other ceiling/scale/mounting defaults are unchanged. Quantities using these assumptions remain estimated. Unstated 3 m stick lengths are explicitly assumptions, not supplier-verified dimensions. Recorded cable purchase lengths take precedence, and no conductor multiplier is inferred.

Rollback source: `outputs/workspace-followup-20261025/pairing-defaults-before-correction.json`. It contains non-secret planning settings and the prior revision. Restore through the existing Admin defaults API with the current expected revision, not by rewriting estimate records.

Reference constraints consulted: [Wheatland EMT/IMC dimension tables](https://www.wheatland.com/wp-content/uploads/2018/03/EMT-and-Conduit-Brochure.pdf) and [CommScope fibre installation guidance](https://www.commscope.com/globalassets/digizuite/2518-fiber-optics-const-manual-co-107147.pdf). These do not certify the provisional VED pairs.

## Verification

| Acceptance | Status | Evidence |
| --- | --- | --- |
| Explicit endpoint joining, inheritance and provenance | PASS | Inline Node checks covered a previously unassigned wire joining a generated under-floor path, explicit conflicting circuits, insertion and inherited new-path settings. Stale preview guard remains exercised by the existing suite. |
| Pointer-drag on the live canvas | PASS | Actual Designer drag at 28% zoom snapped an endpoint near an existing route onto its centreline, with a shared blue junction and live backend takeoff refresh. Browser verification exposed a small handle hit area, which was enlarged before the successful snap. Temporary wire/device moves were undone; the UI confirmed “No unsaved changes.” No drawing edit was saved. |
| Homerun placement and route preservation | PASS | Inline calculation used the explicit contact rather than glyph centre, produced the unobstructed orthogonal 155 px minimum and retained an edited route. This is not proof that every recognized drawing has complete topology. |
| Region-specific default placement | PASS | Inline checks covered a local under-floor majority despite a larger ceiling majority in another view, a tie, and a reviewed route. |
| Client access | PASS | Actual Client basic sign-in opened the approved revision in 2D and WebGL 3D. Google sign-in worked for the separate Designer/Admin identities. No credentials were changed. |
| Designer isolation | PASS | Read-only verification covered 49 Designer records, five owned project rows, and 48 cross-owner rejections. API checks returned 404 for another owner's project. |
| Pricing removal and history | PASS | Real MySQL transaction checks confirmed append-only removal, retained source hashes and old assignment documents, preserved manual overrides and idempotent retry; the outer transaction was rolled back. No active Client import was removed during verification. |
| Pairing rules | PASS | Catalog-backed preview and per-route under-floor resolution checked before the authorized revision-5 save. Compatibility remains provisional rather than professionally verified. |
| Excel download | PASS | Actual Designer browser downloaded a 14-row XLSX. Excel-file reader checks verified widths, frozen headers, numeric values, leading-zero/formula-safe identifiers and blank unknown prices. Rounded total reconciled to the visible PHP26,025.77 BOM. |
| Native Excel visual rendering | NOT TESTED | The live file was parsed and its formatting inspected; it was not opened in desktop Excel. |
| Admin visual layout | PASS | Actual browser screenshots show grouped navigation, fitted user actions and visible under-floor alternatives. No user/project/approval mutation was submitted. |
| Focused backend suite | PASS | 49 existing tests across `test_wire_network.py`, `test_wiring_bom_components.py` and `test_draft_wiring.py`. No new test files. |
| Focused frontend suite | FAIL | 27 passed, 2 failed out of 29 existing tests. Two assertions retain the old rule that unknown settings must reject inheritance. They were not rewritten under the no-test-writing instruction. Do not claim a green editor suite. |

Final verification: **PASS** Vite production build (2,239 modules); **PASS** focused ESLint (23 frontend files); **PASS** AST parsing (290 application Python files) and OpenAPI generation (89 paths). Full suites and a 500-device performance benchmark were not run. Existing large-bundle warnings remain. Focused diff whitespace checks passed.

## Files and contracts

- Routing/topology: `backend/app/routing/{draft_wiring,homerun_proposals}.py`, `backend/app/geometry/wire_network.py`; frontend `wireAssignments`, `wireJunctions`, `wirePathSnap`, `connectedWiring`, `deviceConnections`, `observedWiringDraft` and the existing 2D/3D review components.
- Access/publication: `approved_draft_presentation.py`, `client_workflow_service.py`, `ClientPortal.jsx`, `ProjectDashboardPage.jsx`, `AdminDraftReviews.jsx`, `WorkspaceSidebar.jsx`.
- Pricing: existing project-pricing repository/service/API, item-pricing service and BOM pricing controls; optional under-floor product/purchase-length fields extend the existing defaults JSON contract.
- Export: `bom_spreadsheet.py`, existing BOM service/export endpoints and the BOM download API/UI. No installed dependency, new table or migration.
- Presentation: `AdminWorkspace.jsx`, `AdminWiringPairs.jsx`, `adminCatalog.css`, `ManualBOMSettings.jsx`, notifications and existing Client/3D styles.

## Integrity and handoff

Branch remains `codex/vlm-localization-experiment`, HEAD `a823ce5`; no commit or push. The worktree already contains substantial unrelated work, including pre-existing test edits. This checkpoint does not stage or discard it. Original uploads, reviewed geometry and captured estimates were not rewritten. Existing 50 database tables and 89 OpenAPI paths are retained.

The stopped local backend was restarted in a hidden window on loopback port 8000 (launcher PID25960); no running listener was killed. Source reload is scoped to `app`. Logs are in the checkpoint output folder, not in a published report. No other roadmap phase, detection retuning or model training was started.

Browser evidence: `client-approved-2d.png`, `client-approved-3d.png`, `designer-wiring-inspector.png`, `admin-workspace-redesign.png`, `admin-context-pairings.png` and `wire-magnetic-snap.png` under `outputs/workspace-followup-20261025/`. The snap screenshot documents a temporary unsaved interaction, subsequently undone. Device/reference ambiguities, missing product specifications and ambiguous panel/terminal choices remain reviewable rather than silently inferred.
