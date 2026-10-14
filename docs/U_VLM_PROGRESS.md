# Local VLM Migration Progress

This ledger separates implementation, real-data validation, human approval,
activation, and publication. A checked implementation item is not equivalent
to a trained or released model.

### October 12 automatic endpoint contacts and draft vertical takeoff

- Cause: endpoint attachments previously required an explicit magnet commit; the
  draft 3D adapter also omitted stored mounting metadata and gated connections
  behind `metricRouting`, which the draft scene never supplied. Draft BOM counted
  only planar edges. No detector, model, upload or canonical-layout mutation.
- PASS: actual device-port contacts now normalize through the shared draft on
  load, edits and normal save. Backend validates/persists the same attachments.
  Interior crossings, ambiguous targets and known circuit conflicts do not join.
  Disconnect opt-outs survive reload; older clients removing an attachment also
  preserve disconnect intent. Approved historical documents are not rewritten.
- PASS: 3D preserves mounting metadata, reaches rear terminals, and deduplicates
  shared device drops. Unmeasured preview heights remain illustrative. Draft BOM
  measures `abs(service_elevation - (floor_elevation + mounting_height))`,
  counting one shared device drop at a given service level. Missing drop
  inputs are flagged; known planar draft lengths stay priceable without approval.
- PASS live: job 24260 normal browser save created review revision 3, then reload
  retained 69 endpoint attachments across 45 devices / 35 existing paths. 3D shows
  45 connected devices; disconnect/undo and live missing-drop BOM notices checked.
  Original SHA256 remains 915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9;
  prior revision 2 integrity, walls, device centers and interior wire points preserved.
- PASS verification: 85 isolated backend tests; 83 frontend files / 688 tests;
  production build and scoped ESLint. Numeric regression: 7 m planar + 1.6 m drop
  at nonzero floor elevation = 8.6 m; PHP 10/m yields PHP 86 for each conduit and
  selected draft wire row. No guessed conductor multiplication or allowance.
- NOT TESTED: measured vertical pricing on this live plan (saved measurements
  missing), native 3D drag commit, universal connectivity/detection accuracy.
  Build retains existing large-chunk warnings; no dependency, table or route added.
- Files: backend endpoint_connections, demo interpretation schema/service/API,
  draft_bom_service and tests; frontend deviceConnections, shared draft page,
  draftRoomScene/draftWiringScene/DraftRoomPreview, connection inspector, BOMPanel
  and tests. Scoped helper/test checkpoint `a44a3ca` on
  `codex/vlm-localization-experiment`; mixed pre-existing integration edits
  remain uncommitted. Original uploads, saved canonical data and stash@{0} kept.
  Screenshot/diagnostics are private and ignored under lighting-inspection-20261010.

### October 12 explicit wire-endpoint magnets

- Cause: the existing draw-wire tool had geometric magnets, but existing 2D
  and 3D wire handles only moved vertices and deliberately discarded endpoint
  attachments. Clicking an existing trace therefore could not magnetically
  connect it to a device. No detector/model changes in this ticket.
- Added a shared endpoint-to-device eligibility/commit path in
  `frontend/src/features/detection-review/deviceConnections.js`. A preview does
  not create connectivity; release stores exact (including fractional) source
  coordinates and `device_attachments`, without moving devices, changing
  circuit/provenance metadata, or creating another route. Interior points,
  annotations, rejected devices, collapsed segments, equidistant targets and
  devices already attached to an unrelated run are excluded. Commit revalidates
  against current state; drag-away or explicit Disconnect detaches intentionally.
- Integrated into DemoInterpretationCanvas / DemoInterpretationPage,
  DraftRoomPreview / Viewer3DCanvas / DraftWiring3D. 2D uses a constant
  screen-space acquisition radius under pan/zoom; 3D projects the existing
  device connector through the active camera before comparing screen distance.
  Green target feedback and Escape/pointer-cancel prevent accidental commits.
  Selected 3D handles and target markers retain useful CSS-pixel sizing as the
  camera moves. `wireHandleProjection.js` affects editing controls only, not
  physical tubing, canonical geometry or takeoff quantities.
- UI/canvas/3D skills kept geometry in the shared draft. The focused UI guidance
  added a keyboard/click alternative: WireDeviceConnections in the existing
  inspector, with alphabetically ordered device choices and explicit Disconnect.
  No added approval gate or automatic proximity-based circuit merging.
- PASS full frontend tests: 83 files / 684 tests; focused event
  tests cover Konva endpoint drag/preview/cancel, R3F captured pointer drag and
  camera-projected targets, perspective/orthographic handle sizing, both-view
  save/reload, undo/redo, exact anchors and detachment. PASS 24 isolated backend
  attachment API tests, including existing single measured canonical drop.
  PASS Vite build and scoped ESLint on all files changed in this ticket. Existing
  large-chunk build warning and backend Starlette/HTTPX deprecations remain.
  Full lint was not rerun; the preceding checkpoint recorded six unrelated
  DeviceMeshCatalog errors. Full backend suite NOT TESTED for this UI ticket.
- PASS live browser save/reload: plan 9384 / job 24260 revision 1 stored an
  explicit start attachment to symbol-0037. Reload and the 3D inspector restored
  it. A temporary 3D-side end connection was undone. Revision 2 disconnected
  the diagnostic attachment and restored the exact raw wire points. Read-only
  database verification found all 35 original paths and all 58 device centres
  unchanged, zero new generated paths, and no layout approval. Original runs
  and uploads were not edited or reanalyzed; these are appended review revisions.
- NOT TESTED/conclusive: native live drag automation selected an overlapping
  device in one 2D attempt (immediately undone), and did not conclusively acquire
  the 3D handle. Do not count those attempts as a browser drag pass. Automated
  component event tests and the live keyboard/click save path are separate proof.
  Missing measurements still prevent measured wall drops; no heights inferred.
- Files: the shared helper plus the six integration components above,
  WireDeviceConnections.jsx, wireHandleProjection.js and related tests,
  including new WireHandle.test.jsx / wireHandleProjection.test.js. This is an
  uncommitted feature diff on codex/vlm-localization-experiment; existing dirty
  files and stash@{0} remain untouched. No dependency, API or schema changes.
  No next roadmap or training ticket started.

### October 11 source-evidence refinement checkpoint

- Evidence-backed cause: fresh upload 9384 / job 24258 exactly matched the
  earlier raw result, so this reproduction was not random reanalysis drift.
  Global Hough voting/masked fixture endpoints favoured repeated ceiling grids;
  dashed-corner grouping retained interrupted grid/text fragments. Grayscale
  wall seeding missed faint chromatic structural bands. Old manually corrected
  geometry was cleaner than raw inference and must not be counted as detector
  accuracy. This diagnosis does not exclude every historical failure mode.
- Implemented bounded fixture-axis source-ink extraction, including real
  repeated dashes, with glyph interiors excluded from evidence. Alignment
  bounds the search but creates no electrical attachments/junctions. Ambiguous
  connections remain unresolved. Fixture-rich scans no longer use global
  Hough corner grouping to promote interrupted grid/text strokes. Other drawing
  styles retain the previous path; existing gateway observations are untouched.
- Implemented guarded chromatic wall-band refinement after symbol detection:
  sustained broad evidence in both axes, glyph exclusion, grid/outline guards,
  source-backed endpoints and same-filled-band duplicate suppression. White
  openings and distinct parallel partitions remain separate. Monochrome and
  insufficient-colour evidence fall back unchanged. Opening references are
  protected; rooms derived from superseded wall hypotheses are invalidated.
  No filename/hash-specific coordinates or annotation overlay in production.
- PASS exact-source private replay: original SHA256 remains
  `915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9`.
  Against the **partial** 34-segment wall reference, length-weighted coverage
  at 12 pixels improved 22.8% -> 84.1%, distance precision 40.8% -> 80.2%.
  Against eight annotated wiring polylines, coverage at 16 pixels improved
  24.1% -> 82.6%, distance precision 31.6% -> 92.0%. These are geometric
  partial-reference comparisons, not electrical/topology correctness or
  independent detection accuracy. FAIL/unproven 85% overall wall target.
  Private evidence: `refinement-metrics.json`, `refinement-before.png` and
  `refinement-after.png` under the ignored lighting-inspection directory.
- PASS browser reanalysis: new jobs 24259 and 24260 on fresh plan 9384 contain
  identical raw payloads and pinned source/model/runtime/configuration. Each
  has 43 walls, 58 unchanged symbols, 35 observed paths, no invented electrical
  connections and zero review revisions. Reload preserved the result. Raw
  evidence versions are CV v11 / wiring v6; parameters are stored in provenance.
  Actual browser screenshot: `refinement-live-24259.png`. No new manual
  annotation was used to produce these runs.
- PASS preservation: old plan 9376 / job 24256 still has exactly 34 corrected
  walls and eight ceiling annotations; historical candidate/review hashes and
  original pixels unchanged. `power-layout.png` separately retains its 13-wall
  monochrome fallback; this is a compatibility check, not power-layout accuracy.
- PASS final focused backend gate: 97 tests + 13 subtests (9 new evidence
  regressions included). PASS 44 frontend editor/connection tests and Vite build.
  PASS final full frontend run: 81 files / 670 tests.
  FAIL full frontend lint: same six pre-existing DeviceMeshCatalog errors;
  not changed in this ticket. Build warns about large chunks; backend reports
  existing Starlette/HTTPX deprecations. OpenAPI 41 paths / metadata 34 tables,
  no DDL or dependency changes. Full backend suite NOT TESTED in this checkpoint.
  Additional candidate/concurrency/source-coordinate gate: 68 tests + 8
  subtests PASS, including immutable/stale-safe review saves.
- Remaining: curved/elbow switch branches and missing symbols are not all
  recovered; fixture-rich extraction deliberately leaves unsupported branches
  unresolved rather than inventing topology. General coloured drawing styles
  need a larger independently annotated regression set. Candidate wall-band
  width is used as evidence but the existing candidate contract still does not
  persist that width as a measured wall thickness. Measured 3D drops require
  stored scale/elevations; no new 3D guarantee or model-training claim.
- Git scope: `f605974` on `codex/vlm-localization-experiment` checkpoints only
  the new evidence helpers and isolated regression
  file. Integration edits in automatic_wiring, demo_cv and the worker, this
  ledger, and prior unrelated dirty work remain in the working tree rather than
  being silently swept into the component checkpoint. Original uploads,
  corrections and stash@{0} remain preserved. No next roadmap/VLM ticket started.

### October 11 manual fresh-upload comparison

- PASS requested computer-use workflow: selected Downloads
  `4-lightinglayout.jpg` through the normal file chooser, clicked Upload floor
  plan, then Start processing and Open plan editor. Separate plan 9384 / job
  24258 completed; original plan 9376 and its corrections were not edited.
- PASS read-only source comparison: the new stored upload matches the original
  SHA256 `915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9`.
  Its raw payload exactly equals job 24256; there are no review revisions on
  the new run. The UI shows 11 walls and 37 wiring paths; the payload has 58
  symbols. This comparison does not inherit the 34 manually corrected walls
  or eight manually annotated paths from the old plan.
- FAIL detection-quality result: fresh overlays remain fragmented/messy versus
  the user's first supplied screenshot. Prior annotation-preservation success
  was not automatic detector improvement. No production algorithm change or
  accuracy claim in this upload-only verification. Evidence screenshot:
  `storage/training/lighting-inspection-20261010/manual-upload-fresh-24258.png`.
  Computer-use and CV guidance kept the fresh case separate from human review.

### October 11 exact-source reanalysis and explicit connections checkpoint

This is a **partial implementation checkpoint, not completion of the raw
wall/wiring quality ticket**. No model training, promotion, download or
page-specific detector overlay was introduced.

- PASS exact comparison: Downloads `4-lightinglayout.jpg` is byte-identical to
  stored plan 9376/page 2975: SHA256
  `915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9`,
  1340 x 3264. Jobs 24249 and fresh 24256 have exactly equal raw payloads:
  11 walls, 58 symbols, 37 observed trace segments and zero rooms. Tested
  tolerance: exact payload/coordinate equality, not a universal runtime claim.
  Earlier runs used different checkpoints/configurations and are not equivalent
  repeated-inference comparisons. The supplied screenshots lack run IDs, so
  they cannot establish a particular historical raw candidate association.
- PASS preservation: fresh job 24256 inherited the exact 34 corrected wall
  segments and eight source-bound ceiling paths, with no generated branches.
  Saved unfinished review revision 1 through the browser and reloaded it;
  private read-only verification matched every vector and verified prior
  candidate/review hashes and original-file integrity. No layout or dataset
  approval was inherited. Job 24255 failed during this verification due to a
  missing provenance-serialization import; it remains in history. The import
  was fixed and retry 24256 completed successfully.
- Cause/owners: only full manual replacements previously carried forward;
  partial corrections could disappear. `reviewed_reference.py` now rebases
  corrections by exact source/evidence identity, preserves unmatched human
  geometry as manual drafts and remaps explicit attachments. Original
  candidates/history remain separate. Repository/service latest-run queries now
  use submitted processing-job order, not completion/insertion order. An
  isolated regression completes an older job last and confirms the newer run
  stays current and saved canonical geometry is unchanged.
- Cause/owners: ordinary review loads/saves previously added nearest-anchor
  A* branches, geometrically joined independent runs and pruned paths;
  draft 3D also inferred nearby-device drops independently. `draft_wiring.py`
  now preserves saved paths without that completion policy. The old algorithm
  remains an explicit legacy benchmark opt-in, not a load/save API behavior.
  `draftWiringScene.js` no longer manufactures proximity connections or measured
  drops in relative previews. Observed/user-edited/generated data stay distinct.
- PASS placement/attachments: `DemoInterpretationCanvas.jsx`,
  `DemoInterpretationPage.jsx`, `deviceConnections.js`, schemas and review
  service implement pointer-follow placement, inverse-transform coordinates,
  one-click placement then exit, Escape cancellation including focused chooser,
  select-mode-only dragging, explicit endpoint snap feedback/commit, immutable
  connected movement, detach and undo/redo/save integration. Ambiguous/occupied
  endpoints are not guessed; detach before choosing an independent run. Interior
  junction splitting is deliberately unsupported. Browser: selected a switch,
  cancelled without adding it, placed one temporary device (58 -> 59), then
  undid it (59 -> 58) with all eight paths unchanged and reloaded the saved
  result. Live pointer-hover and live drag-to-snap were NOT TESTED; unit/API
  tests cover these interactions and persisted attachment validation.
- PASS measured model contract: `canonical_extension.py`,
  `canonicalExtension.js`, `canonicalScene.js` and compatibility tests add
  version-3 explicit mounting data without changing K1 or version-2 snapshots.
  Canonical save uses supplied mounting height, approved floor elevation/scale,
  explicit service-level route and an optional validated wall reference to put
  the vertical segment in the same canonical route. There is no second inferred
  connection. Configured wall placement outside its measured wall band fails
  measured save, not unfinished 2D save. Actual measured 3D for plan 9376 remains
  NOT TESTED: its saved paths have no measured elevation/mounting configuration;
  the relative preview is not a measurement source.
- FAIL raw wall target: production wall evidence remains v10 and the detector
  still emits 11 walls on the lighting source. Pair/grid contamination and a
  page-wide outlined-width cutoff remain unresolved. Private color/width
  experiments recovered more reference length but also accepted fixtures and
  unrelated strokes (one guarded variant: 73.04% reference-length coverage,
  78.42% distance precision at 12px). They were NOT activated. These are
  annotation-distance diagnostics, not independent detector accuracy. The
  automatic detector has not met an 85% wall-quality gate. No permanent or
  universal detection guarantee is claimed.
- Separate regression drawing: read-only `power-layout.png` replay, 1765 x 1084,
  SHA256 `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`,
  gives 13 raw walls; original unchanged. No independent complete wall reference
  is available for an accuracy claim. General observed-path extraction/junction
  quality still needs additional work; disabling unsafe completion is not proof
  that dashed/grid/fixture separation is solved.
- PASS gates: full frontend 81 files/670 tests; final focused placement/snap
  suite 39 tests; production build and scoped ESLint. Backend isolated broad
  geometry/wall/grid/gap/coordinate/observed-wire gate: 207 tests + 901 subtests;
  separate CV/routing/worker set: 104 tests + 13 subtests; worker/execution set:
  32 tests. Final attachment API retest: 24 tests. These overlap; do not sum them
  as unique coverage. Full backend suite NOT RUN. Full frontend lint FAILS on
  six pre-existing `DeviceMeshCatalog.jsx` errors outside this patch. Existing
  >500 kB build and Starlette/anyio deprecation warnings remain.
- Preservation/cleanup: 41 OpenAPI paths/34 metadata tables, no DDL/dependency
  changes. Original files, historical reviews, unrelated dirty edits and
  stash@{0} (`bb78854e87833124a1725b51f0be6099a8ac0cfa`) retained. Diagnostic
  images/logs remain private ignored artifacts, not training labels or uploads.
  Scoped checkpoint covers nine isolated mounting/connection contract files;
  integrations overlapping pre-existing dirty files remain unstaged rather than
  sweeping unrelated work into a commit. Next priority remains the raw wall and
  observed-wire quality ticket: investigation started, production fix not yet
  validated or activated.

### October 11 consistent UI list ordering

- Scope: one shared, non-mutating display-order helper. Named lists use English
  case-insensitive A-Z with natural embedded numbers and stable identity ties;
  blank labels come last. Floor lists retain explicit saved sort_order (then
  name), source pages use plan/page numbers, and wiring lists use natural IDs.
  Projects default to name order; the existing newest-update option remains.
  Fixed workflows, coordinate/boundary points, user-added form row indices,
  estimate version history and captured estimate line order retain their
  meaningful existing sequence. No global DOM sorter or geometry reordering.
- PASS implementation owners: utils/listOrder.js, shared legendChoices,
  AdminMaterialImport, BOMPanel, EstimatePage, DemoInterpretationPage,
  ObservedWiringPanel, DetectionInspector, LayoutSymbolEditor, Viewer3DPage,
  RoutingPanel, CircuitPlanningPanel, ProjectDashboardPage,
  ProjectFloorUploadPanel and AnalysisSettingsPanel. Catalog aliases retain
  selected IDs and identity grouping; imports/prices, canonical geometry,
  routing, quantity calculations and persistence contracts are unchanged.
- PASS verification: all 80 frontend files /663 tests, scoped ESLint and Vite
  production build. Existing greater-than-500-kB bundle warning remains.
  Tests cover frozen/non-mutated input arrays, natural numbers, explicit floor
  and page order, selected catalog aliases, alphabetized material choices,
  unchanged prices and project name/newest-update switching. Two old default
  order assertions were updated to match this requested behavior. Backend
  tests NOT RUN: no backend/API/database changes; full-repository lint NOT RUN.
- PASS live browser: job24246 device picker, class catalog, conduit options and
  material table show sorted descriptions. Selecting the first downlight retains
  its catalog ID1779 and saved coordinates; Undo stays disabled. No console
  errors, save, reanalysis, price change or role switch. Proof screenshot:
  storage/training/alphabetical-catalog-lists-20261011.jpg.
- Safety/state: presentation-only, no new dependency/table/endpoint, original,
  annotation, detector or training change. Focused-change skill kept sorting at
  existing display boundaries. Work remains uncommitted on
  codex/vlm-localization-experiment at5789c6b; unrelated dirty edits and stash
  retained. No commit/push and no next roadmap phase started.

### October 11 bottom estimation table and left wiring toolbar

- Scope: presentation-only work in the shared plan editor. Estimation is the
  last full-width section below the workbench and optional measured-layout
  controls. Conduit, wire/cable and plan-scale inputs are grouped above a
  bordered, alternating-row material table; priced subtotals live in its footer.
  Numeric columns remain aligned, missing prices remain explicit, and the
  labelled keyboard-focusable table region scrolls locally on narrow screens.
- PASS wiring controls: Show wiring, point editing, trace add/restore/remove
  controls and new-wire ceiling/under-floor selection live in the left tool
  rail, before layer controls. Selected device/wall/wire properties stay in
  the inspector. Existing shared wiring state, undo/save behavior and saving
  locks are preserved. Side-panel scrolling prevents a long inspector from
  extending the blueprint column into excess blank space.
- PASS verification: all 79 frontend files /659 tests, scoped ESLint and Vite
  production build. Existing greater-than-500-kB bundle warning remains.
  Focused 34 tests cover sidebar containment, visibility across 2D/3D, placement
  persistence, last-section estimation, pricing controls and table subtotals.
  Backend tests NOT RUN this turn: no calculation/API/database changes.
- PASS live browser: Designer job24246, wiring toggle and ceiling option
  confirmed in the left rail; last-section estimation and 1073-pixel table
  confirmed at 1440-pixel desktop test width. At 375 pixels, the 560-pixel table
  scrolls inside a 286-pixel local region without page-width overflow. Temporary
  viewport override reset; wiring visibility restored; no live save or prices
  changed. No browser console errors. Proof screenshots:
  `storage/training/bom-left-wiring-controls-20261011.jpg` and
  `storage/training/bom-bottom-table-20261011.jpg`.
- Owners: DemoInterpretationPage, ReviewToolRail, BOMPanel, workspace.css and
  focused UI tests. UI/canvas skills kept canonical geometry untouched; styling
  guidance retained existing tokens and semantic controls. No new dependency,
  table, endpoint, model/training/original/annotation change or next roadmap
  phase. Work remains uncommitted on codex/vlm-localization-experiment at
  5789c6b; unrelated dirty edits and stash preserved; no commit/push.

### October 11 wire price controls and matching-device batch edits

- Scope: replace the misleading wire allowance label with draft cable route
  length, without an extra allowance charge. Wire and conduit remain separate
  products/cost lines. Optional custom PHP/metre wire pricing overrides the
  calculator price, including zero; roll pricing divides the database purchase
  price by explicit metres per purchase unit. Only a unique explicit product
  length such as `(305M)` supplies a suggested conversion. No inferred gauge,
  conductor multiplier, waste or installation specification. Missing saved
  circuit specifications remain flagged; this is not conductor purchase takeoff.
- PASS device identity: unique exact active catalog class IDs or complete
  approved drawing-legend identities automatically populate the class control.
  Model indices are not database IDs; ambiguous/unknown matches stay editable.
  Raw detector identity, confidence, originals and approval state are preserved.
- PASS matching-device edits: class/price changes apply together to active
  matching devices in the current plan. Unknown identities stay isolated and
  deleted items are excluded. Positions remain individual. Changing class
  clears old custom prices; an explicit group PHP price overrides catalog
  pricing for the draft only. Existing append-only save, concurrency and
  ownership controls persist changes without creating approval or changing
  Admin prices or historical estimate snapshots.
- PASS backend verification: 106 tests and 15 subtests passed using the isolated
  restricted verification database; two existing deprecation warnings remain.
  Coverage includes custom/zero pricing, roll conversion, source scale,
  historical price snapshots, persistence and authorization. Full backend suite
  NOT RUN. PASS frontend: all 79 files /658 tests, scoped ESLint and production
  build. Existing greater-than-500-kB chunk warning remains; full-repository
  lint NOT RUN. Batch-edit tests prove unchanged positions and rejected items.
- PASS live computer-use: job24246 automatically selected catalog class159 for
  troffers. A temporary PHP123.45 edit appeared on a second matching device in
  the 43-device group; Undo restored it. Temporary wire PHP20/metre priced all
  eight source paths, subtotal PHP2046.51 using approximate A3 sheet scaling,
  without an allowance surcharge. Explicit 100-metres-per-roll conversion of
  the PHP13594.50 test SKU also priced the eight paths (PHP13910.61 subtotal);
  that fire-alarm SKU was a transient unit-conversion test, not a lighting cable
  specification. Test prices restored and no live draft saved;
  persistence is verified in isolated tests. Proof screenshot:
  `storage/training/bom-wire-group-pricing-20261011.jpg`.
- Safety/state: no training, detection, original/annotation/model edits, role
  changes, pricing import or scale approval. No added tables/dependencies/API
  paths; previous 41 paths /49 operations /34 tables not recounted. Query inputs
  extend existing BOM/CSV endpoints. Changes remain uncommitted on
  `codex/vlm-localization-experiment` at `5789c6b`; unrelated dirty changes and
  stash retained. No push and no next roadmap ticket started. Routing/CV skills
  kept costs server-owned and detector evidence separate; focused-change and
  UI guidance kept this inside existing draft controls.

### October 11 separate wire/tube pricing, custom sheets and device-price fallback

- Scope: user explicitly accepted approximate paper-size pricing rather than
  aspect-ratio blocking. A4/A3/A2/A1/A0 and optional custom width/height in mm
  fit the long image edge to the long sheet edge at 1:100. A3 is the new-plan
  default. Cropped/mismatched images now produce an advisory approximation,
  not a measured calibration; stored exact-page scale still wins. No scale
  record, source drawing or detection is modified by the calculator.
- PASS: separate conduit and wire/cable dropdowns, independent database SKU
  prices and separate BOM lines. Explicit draft cable choice is labelled an
  assumed one-priced-metre-per-route-metre allowance, NOT aggregate conductor
  purchase quantity. No inferred gauge, count, waste or vertical drops. Roll
  conversion remains flagged for that item without blocking conduit costs.
  Cable managers/accessories are excluded; data/fibre cable is not silently
  assigned to power circuits. Saved current circuit specifications retain
  their existing measured quantity/conductor/conversion rules.
- PASS: selected-device right sidebar accepts optional bounded PHP unit price.
  Saved through existing immutable draft review JSON and concurrency/ownership
  controls, survives reload, and prices that individual device only when
  catalog costing cannot resolve it. Different custom prices remain separate
  quantity groups. Catalog prices and saved historical estimates are unchanged.
  Saving a draft creates no layout/dataset approval. No new table/dependency.
- PASS verification: restricted empty verification database, 104 tests and 15
  subtests passed (two existing deprecation warnings); all 79 frontend files /
  653 tests passed; scoped ESLint and Vite production build passed. Existing
  >500 kB build warning remains. Tests cover every standard/custom size,
  invalid dimensions, measured-scale precedence, read-only scale fallback,
  separate wire/conduit known answers, roll-unit refusal, device-price grouping,
  zero-price handling, save/reload/authorization and historical price snapshots.
  Full backend suite and full-repository lint NOT RUN.
- PASS computer-use: live Designer job24246 calculates on all standard sizes.
  With temporary EMT half-inch product at PHP360 per stated one-metre length:
  A4 subtotal26049.10, A3 36837.11, A2 52098.08, A1 73761.77, A0 104284.01;
  custom300x600mm subtotal52624.37. These are priced conduit subtotals, not
  engineering-approved measurements or complete project totals. Temporary
  fire-alarm roll selection flags eight purchase-unit conversions. Temporary
  PHP123.45 selected-device input was tested and undone, NOT saved to the live
  project; persistence is verified by isolated API/UI tests instead. Temporary
  conduit/cable overrides and custom dimensions restored; A3 fallback retained.
- Safety/state: no live project save, pricing import, scale approval, reanalysis,
  training, original/annotation/model modification or role change. Only verified
  owned local backend processes refreshed. No new API paths/tables (prior
  41 paths /49 operations /34 tables not recounted); query/review schema fields
  extended compatibly. Work remains uncommitted on
  codex/vlm-localization-experiment at5789c6b; unrelated edits/stash preserved.
  Proof screenshots under ignored storage/training/bom-*-20261011.jpg.
  No commit/push and no next roadmap ticket started.

### October 11 read-only draft conduit calculator and paper-scale fallback

- Scope: make the stated one-metre conduit price basis usable in the BOM without
  approving symbols, changing training data or rewriting saved estimates.
  Routing, surgical-patch and lean-build guidance kept calculation server-owned,
  reused the existing BOM/CSV services, and excluded inferred conductor/waste
  rules. UI guidance kept two labelled calculator inputs inside the BOM.
- PASS implementation: explicit active priced conduit SKU choice maps measured
  drawing conduit rows to metre/length units at one metre per listed length,
  as supplied by the user. Installation labels stay distinct. Device quantities,
  cable conductor semantics and saved route specifications are not overwritten.
  Product category plus pipe/tube/conduit identity excludes accessories such as
  threaded rods even if the workbook groups them under conduit. Missing scale,
  ambiguous identity and missing prices never become zero-valued costs.
- PASS planning fallback: optional A4/A3/A2/A1/A0 full-sheet sizes at 1:100,
  orientation independent; page aspect mismatch beyond 5% refuses calibration.
  Stored measured scale always wins. Assumed scale is labelled in item basis,
  source metadata, warnings and CSV, never persisted as a reviewed scale.
  The selected draft SKU and requested paper assumption are also recorded in
  CSV metadata. Existing saved estimate downloads remain unchanged.
- PASS tests: 79 frontend files / 650 tests, focused two files / six tests,
  scoped ESLint and Vite build. Restricted empty verification database gate:
  63 passed, 15 subtests passed, two existing deprecation warnings. Includes
  7-metre × 360 = 2520 known answer, separate ceiling/under-floor traces,
  source immutability, invalid SKU/scope refusal and price-history preservation.
  The accessory filter first exposed a generic test fixture name; fixture now
  uses an actual pipe identity and the final affected gate passes. Full backend
  suite/full-repository lint NOT RUN. Existing >500 kB chunk warning remains.
- PASS computer-use: Designer job24246 now has priced database conduit options
  (catalog was populated independently since the prior empty-catalog check).
  Temporary EMT half-inch choice280 and A3 assumption trigger the explicit
  cropped-page rejection. All eight traces remain source pixels, not invented
  metres. CSV downloaded and verified with the rejection reason; UI selection
  controls restored to no overrides. Undo disabled; no captured console errors.
  Screenshot: storage/training/bom-calculator-20261011.jpg. Downloaded test CSV:
  C:/Users/kupal/Downloads/ved-draft-bom-10218 (1).csv. Final CSV choice metadata
  is covered by the isolated API gate, not another live download.
- BLOCKED actual plan total: current tall cropped source does not match a full
  standard sheet and has no exact-page scale. A known dimension or reliable
  uncropped source remains necessary. Device SKU mappings and reusable saved
  conductor specifications also remain explicit inputs, not engineering guesses.
- Safety/state: no live import, account switch, project save, scale approval,
  reanalysis, training or original/annotation/model writes. Only verified owned
  local backend processes refreshed to load code. Existing 41 paths / 49
  operations / 34 tables unchanged (not recounted), no dependency/schema changes.
  Local uncommitted work remains on codex/vlm-localization-experiment at5789c6b;
  unrelated edits/stash preserved. No commit/push or next ticket started.

### October 11 rear device terminals, selection glow and proportional wiring

- Scope: shared 3D presentation only. Routing/asset/visualizer and surgical-patch
  guidance kept display geometry out of canonical measurements; spreadsheet
  guidance kept the supplied price workbook read-only. No backend pricing,
  detection, circuit specification or training change in this slice.
- PASS implementation: devicePlacement exposes a shared rear terminal for wall
  devices and top terminal for ceiling fixtures. Draft wiring and trusted saved
  route connectors consume it without moving stored source anchors. Display
  tubes use a 0.006 illustrative radius scaled with draft scene units, removing
  the absolute radius floor that dwarfed switches in whole-plan previews.
  DeviceMesh passes selection into DeviceBody: warm emissive plates, housings
  and light surfaces remain visible from front/rear/top. Contacts stay dark.
  Selection is not an energized-circuit simulation or engineered conduit size.
- PASS tests: 79 frontend files / 648 tests; seven focused files / 37 tests;
  scoped ESLint and Vite production build. Rear terminals cover rotated walls,
  immutable inputs, ceiling tops, draft and saved attachments. Tube/device ratio
  covers four preview scales. Selection covers faceplates, housings and lenses.
  Existing >500 kB chunk warning remains. Full lint and backend suite NOT RUN
  for this frontend-only slice; no dependencies, endpoints or tables added.
- PASS computer-use: direct 3D fixture click selects symbol-0026 (Troffer
  lights), with warm housing glow visible in the connected Designer preview.
  Slender ceiling tubes render at close zoom. Undo remains disabled and no
  captured console errors. Screenshot: storage/training/device-rear-selection-
  20261011.jpg. Rear wall-terminal geometry is test-proven, not a separate live
  close-up visual gate. No browser save, reanalysis, import or account change.
- Pricing evidence: the supplied workbook contains conduit priced per length
  (e.g. PANASONIC row65, EMT half-inch, selling price360), without specifying
  meters per length in that description. No accepted row explicitly names
  THHN/THWN; fibre/data cable prices must not substitute for power conductors.
  Ceiling vs under-floor labels identify installation, not a product SKU or
  engineering diameter. Reuse saved conductor counts and meter/unit mappings;
  missing inputs remain unpriced. Live catalog is still empty and exact-page
  scale absent: actual total BLOCKED by inputs, not silently zero-valued.
- Safety/state: workbook/originals, annotations, stored routes, historical
  estimates, database and model weights untouched. Local uncommitted work on
  codex/vlm-localization-experiment at5789c6b; unrelated edits/recovery stash
  preserved. No commit/push, process restart or next roadmap ticket started.

### October 11 automatic draft BOM and Excel-price calculation basis

- Scope: read-only draft takeoff from the open saved plan/job and project data,
  without confirming individual detections or approving a canonical layout.
  Routing/estimation guidance kept prices database-authoritative and reused only
  saved, explicit circuit specifications for the same current measured route.
  Spreadsheet guidance kept the supplied workbook read-only; UI guidance kept
  the BOM compact, outside the optional measured-layout approval section.
- PASS implementation: new draft_bom_service.py, BOM API/CSV service and route,
  frontend BOM API and BOMPanel, and plan-editor integration. Active device
  counts include unresolved drafts but exclude rejected symbols and circuit
  notations. Canonical geometry takes precedence where available. Stored source
  polylines are measured without taking display-only 3D lane offsets as length.
  Exact-page scale is required for meters. Complete approved training/catalog
  identities name predictions without creating a saved review mapping.
- PASS pricing: unique exact-description matches or explicit saved purchase
  mappings use current database prices, with separate currency subtotals.
  Ratings/brands are preserved. Missing/ambiguous material matches, missing
  prices, scale and unit conversions remain unpriced, not zero. Saved conductor
  counts and roll conversions are reused only for the same current route;
  stale specifications do not propagate. No invented gauge, conductor count,
  waste allowance or vertical drop. Historical estimate CSV prices stay fixed.
- PASS verification: all 79 frontend files / 645 tests; scoped ESLint; Vite
  build. Affected isolated backend gate: 274 passed, one skipped, 183 subtests
  passed, five existing deprecation warnings. The gate covers current-price
  draft vs historical snapshots, saved conductor/roll known answers, stale
  route refusal, naming ambiguity, ownership and read-only database counts.
  Full backend suite/full-repository lint NOT RUN. Existing >500 kB build chunk
  warning remains. OpenAPI: 41 paths / 49 operations; 34 tables unchanged. No
  dependency, schema migration or table additions.
- PASS computer-use: Designer lighting job24246 shows 43 troffers, four
  downlights, two switches and two outlets; seven circuit notations excluded.
  Eight exact ceiling paths remain. Draft CSV downloaded successfully without
  approving or saving a layout. Undo disabled and no captured console errors.
  Current live catalog has zero active materials, and no exact-page scale or
  reusable project circuit purchase configuration is available: actual monetary
  totals remain unavailable, clearly flagged. Admin must import Excel prices;
  no role bypass, account switch or live import was performed.
- PASS safety: read-only integrity check on latest job24249 still reports 34
  exact walls, eight exact ceiling paths, zero generated extras; historical
  records and original source unchanged; no layout/training approval inherited.
  No live database writes, inference/reanalysis, training or model mutation.
  Only the verified local backend was refreshed. Screenshot proof:
  storage/training/bom-runtime-20261011.jpg; downloaded draft:
  C:/Users/kupal/Downloads/ved-draft-bom-10218.csv.
- State: local uncommitted work on codex/vlm-localization-experiment at 5789c6b;
  unrelated dirty work and recovery stash preserved. No commit/push or next
  roadmap ticket started. Pending real-input costing is not a passing final
  estimate or a professionally approved electrical plan.

### October 11 shared 3D wiring presentation refinement

- Scope: apply the reference's cleaner parallel-tube presentation through one
  shared renderer for draft, saved canonical and generated routes. Routing,
  asset/visualizer, UI and surgical-patch guidance kept this a display-only
  change, with no inferred circuits, installation methods or engineering sizes.
- PASS implementation: continuous 12-sided tubes, restrained material shading,
  local rounded elbows and terminal caps replace per-edge cylinders. Known
  ceiling runs with coincident/near-parallel spans get deterministic, tapered
  vertical display lanes. Source endpoints, branch contacts and device drops
  stay pinned; unknown installation methods and underground depths stay exact.
  Original canonical coordinates, 2D wiring and takeoff inputs are unchanged.
- PASS tests: all 78 frontend test files / 643 tests; scoped ESLint and Vite
  production build. Coverage includes parallel collisions, source immutability,
  branch/drop anchors, bounded dense-page fallback, local bend containment,
  renderer integration, picking/disposal and a three-point underground trace
  retaining cumulative distances rather than shortcutting its bend. Existing
  >500 kB build chunk warning remains. Full lint/backend suites NOT RUN for this
  frontend-only slice; no new dependencies or schema/API changes.
- PASS computer-use: lighting job24246 and power job24232 render WebGL without
  captured console errors. Direct tube selection selects manual-wiring-0006;
  original edit handles remain. Camera/selection checks did not dirty lighting
  (Undo disabled), and power's pre-existing unsaved edits remain (Undo enabled).
  No browser save/reanalysis/reload or account change performed. Screenshot:
  storage/training/lighting-inspection-20261010/lighting-refined-wiring-20261011.jpg.
- PASS read-only integrity: latest independently created job24249 still contains
  34 exact annotated wall segments, eight exact ceiling paths, zero generated
  extras; historical records/original bytes unchanged and no inherited layout
  or training approval. No database writes, detector/training/model changes,
  process restarts, commit or push performed. Branch remains
  codex/vlm-localization-experiment at5789c6b; unrelated changes/stash preserved.
  Existing 40 paths / 48 operations / 34 tables unchanged, not recounted.
- Limits: lane offsets and visual bends MUST NOT feed BOM measurements or become
  stored elevations. Very dense scenes (>512 runs or >1024 edges) fall back to
  exact source geometry, and crowded groups cap total spread; this is not a
  promise of collision-free routing. Bundle separation is regression-tested;
  the live annotated lighting view proves presentation and selection, not a
  synthetic dense-bundle visual gate. No new approval gate or spacing option.
  The earlier general wall-quality release gate remains unachieved below.

### October 11 wall-evidence investigation; release gate not achieved

- Scope: continue general wall-quality work on 4-lightinglayout, comparing the
  existing power-layout source without overriding the user's reference wiring.
  CV/investigation/surgical-patch guidance kept experiments image-only and
  rejected settings that inflate coverage by admitting fixtures or ceiling grids.
- Reproduced baseline on the unchanged 1340x3264 source: 11 wall candidates,
  22.82% length-weighted reference coverage and 40.81% reference-distance
  precision within 12 source pixels. These are private comparisons against
  the 34 user-drawn segments, NOT calibrated accuracy, IoU, a frozen test-set
  result or proof of the requested 85% detection target.
- Cause evidence: outlined evidence accepts 112 bands (median width 24 px),
  including ceiling-grid pairs. That median raises the solid-ink cutoff to a
  12-pixel radius, suppressing thinner actual walls. Native-axis reservation
  already activates on this scan; forcing it changes nothing. Rejecting
  repeated-grid pair edges reduces coverage to 19.67%; excluding through-grid
  ties alone leaves the final 11-wall result effectively unchanged.
- Private chromatic-ink falsification: 12-channel-level chroma evidence with
  bounded original-ink extension and original-image fixture guards reaches
  70.18% coverage / 85.37% reference-distance precision, but still misses walls
  and retains false fixture/line fragments. Lowering the stroke radius reaches
  89.50% coverage / 57.78% precision (105 walls), visibly admitting ceiling
  grids. Intermediate radius gives 79.51% / 78.87%. Component-only filtering
  loses fragmented walls. NONE activated, added as a setting, or incorporated
  into production. Color alone does not establish architectural semantics.
- Power comparison: unchanged monochrome power-layout.png yields 13 raw wall
  candidates. Native preview shows perimeter/partition evidence distinct from
  dashed wiring, but there is no independently annotated power-wall metric in
  this checkpoint; NOT TESTED 85% accuracy on that plan. Its zero-chroma source
  also disproves treating the color experiment as a universal replacement.
- PASS focused existing regression gate using the isolated backend runner:
  wall detection/gap recovery/native resolution/grid/junction/thinning and
  demo CV interpretation: 131 tests plus 898 subtests, 16.72 seconds. Synthetic
  gates passing does not override the failed real-scan gate. No frontend build
  or full-suite rerun because product source/dependencies were not changed.
- PASS preservation: computer-use observes lighting job24246 with 34 active
  wall segments/eight wiring paths and disabled Undo. Read-only integrity also
  verifies latest job24247 still has 34 exact annotated wall segments/eight
  exact ceiling paths/zero generated extras, historical hashes and original
  bytes unchanged, and no inherited layout/training approval. Power original
  SHA256 remains 2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94;
  lighting remains 915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9.
- FAIL / NOT ACHIEVED: general wall-quality fix and independent 85% wall gate.
  No product CV/router/UI edit, browser save/reanalysis, process restart,
  database mutation, API/table/schema change, retraining, weight change, commit
  or push. Existing 40 paths / 48 operations / 34 tables unchanged (not
  recounted). Only this existing ledger and Git-ignored local replay artifacts
  changed this checkpoint. Branch codex/vlm-localization-experiment at5789c6b;
  unrelated dirty work and recovery stash preserved. Lighting tab retained;
  power tab's pre-existing unsaved edits not reloaded or saved. Next bounded
  implementation must distinguish crossing-grid cavities from wall bands and
  verify monochrome/colored positives plus fixture/wiring negatives; not started
  as a production change. No VLM roadmap phase started.

### October 10 shared wiring design across detected plans

- Cause: draft styling keyed color to observed/generated origin rather than
  installation. The 3D draft adapter also discarded source line style; saved
  canonical paths used a separate thin-line renderer. Power and lighting
  therefore did not share a consistent wiring presentation.
- Added shared display palette in routing/wiringDesign.js, used by draft 2D,
  draft 3D, saved canonical 3D and generated routing. Explicit ceiling runs are
  orange, wall attachments muted, underground runs blue, and unresolved types
  amber. Origin remains in inspector/provenance, not an installation guess.
  Preserved solid/dashed source conventions and original source vertices;
  drawing preview reflects the selected ceiling/underground placement.
- Continuous 3D tubes and rounded end caps now cover saved canonical paths as
  well as draft paths. Shared minimum display radius is 0.018 scene units;
  this is visual thickness only, never conduit sizing or BOM input. Draft
  wall-device attachments use the same muted wall styling. Existing device
  attachment geometry, A* routes and editing callbacks are unchanged.
- PASS: 80 focused frontend tests/12 suites, scoped lint, production build
  (2123 modules), scoped diff checks. Three old canonical-render assertions
  initially expected line primitives; replaced them with tube-transform,
  exact elevation and provenance assertions, then reran successfully.
  Full frontend/backend suites NOT RUN this frontend-only checkpoint.
- Live computer-use PASS on lighting9376/job24246 and power9382/job24232:
  both 2D/3D views render shared installation colors; lighting wire selection
  and spectator movement work. No captured lighting console errors. Private
  native PNG proofs: lighting-shared-wiring-design.png and
  power-shared-wiring-design.png under ignored lighting-inspection-20261010.
- Read-only integrity PASS: latest lighting job24247 (unsaved review) retains
  34 exact source wall segments/eight ceiling paths/zero generated extras;
  prior candidate/review hashes, original bytes and power snapshot unchanged.
  No review saves, training, weights, auth, prices, schema or API changes.
  Unknown heights remain illustrative; general detection accuracy is unchanged.
- Uncommitted on codex/vlm-localization-experiment at5789c6b. Existing dirty
  work retained; no push, process restart, new controls or dependencies. Existing
  large-chunk and CRLF warnings remain. Next detector-quality work NOT STARTED.

### October 10 reanalysis preserves source-specific annotation replacements

- Reproduced lighting9376/job24245 in the connected Designer browser: 11 raw
  wall hypotheses and 100 automatic wiring paths replaced the eight reference
  paths saved in job24240. Read-only DB comparison confirmed identical page2975,
  source SHA915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9,
  and source plane1340x3264; no source-file drift caused this reset.
- Narrow fix: the nearest earlier saved review may seed a new unfinished draft
  with its manual wiring/wall replacements only when floor-plan/page identity,
  source SHA, source plane and drawing-region bounds match. Require explicit
  rejection of all automatic alternatives, not a mere added wire. Rejected
  manual vectors remain rejected. Detector IDs are never recycled across runs;
  new raw hypotheses stay recoverably rejected. Existing current reviews win.
  No approvals, symbol anchors, circuits, heights, dataset authority or raw
  candidate JSON are copied. No training, model activation or weights changed.
- Exact manual reference paths suppress automatic A* additions on load and save;
  separate authored branches are not silently joined. Optional `draft_walls`
  response field exposes inherited geometry without inventing a saved review ID.
  Updated the hidden drawing-region safeguard copy to describe this limited
  carry-forward behavior. No new public controls, routes, tables or dependencies.
- Source annotation exportSHA
  df8cbb83a3935d32a4cb3786c6f6e8f9ecf2f192a914fb93650ce7c3b85296f3 contains22
  user-reviewed Standard-wall polylines on sheet11 (34 ordered segments). Applied
  them through normal UI drawing/coordinate controls to job24245/revision1;
  retained all eight exact ceiling wiring polylines. Earlier auto walls remain
  recoverable. Excluded deleted coarse walls and opening/doorway annotations;
  no guessed closure across those intentional gaps. Source workspace unchanged.
- Live reanalysis through the project button produced job24246. PASS: before
  saving any new revision, its draft retained34 exact wall segments, eight exact
  ceiling paths, zero generated paths. Normal save/reload passed; revision2
  records source/reference provenance, with review/layout approval false. Exact
  read-only vector comparisons PASS, all captured prior candidate/review hashes
  PASS, original SHA PASS, prior power-plan24232 hash/history PASS. Symbol count
  and coordinates remain unchanged. 3D uses the same edited draft and rendered
  in the connected browser with no captured console errors; heights illustrative.
- Fixed a related drawing interaction: a top draw-only hit surface prevents
  existing wall/device hit targets from intercepting A-B-C wall clicks. Stage
  handles each click once. Regression test PASS; live continuous drawing created
  the34 editable wall segments before exact source-coordinate entry.
- PASS focused isolated backend71 tests (reference/routing/review API), frontend
 64 tests/six suites, scoped frontend lint, production build2122 modules, scoped
  diff checks. New optional response is backwards compatible; actual OpenAPI40
  paths/48 operations/34 tables unchanged. Full backend/frontend suites NOT RUN
  at this checkpoint. Existing deprecation, CRLF and large-chunk warnings remain.
- General automatic wall quality NOT FIXED: raw replay still yields11 incomplete
  hypotheses. Wide paired ceiling/fixture evidence sets outline median24px and
  suppresses thinner real structure. Private low-radius/solid-only falsification
  probes increased noise, so no threshold/CV patch was activated. The current
  plan is corrected using its source-specific annotation, not an85% detector
  claim. Partial manual corrections and changed source/region are not full
  replacement carry-forward; wiring inheritance currently requires at least one
  new observed trace. Unannotated future-plan accuracy remains a separate gate.
- Uncommitted on codex/vlm-localization-experiment at5789c6b; no push. Existing
  dirty edits and recovery stash retained. Diagnostic/reference/proof files stay
  private and ignored under lighting-inspection-20261010. Restarted only verified
  idle backend14108/33612 to load the fix; replacement launcher28640 stays active
  on loopback8000. Frontend/other services untouched. Existing UI annotations and
  originals preserved. Next independent wall-evidence ticket NOT STARTED.

### October 9 visible wiring review and general wall falsification (after 3dd748b)

- Added source-pixel observed-wiring draft review through the existing strict
  review contract: explicit polyline entry, bounded finite coordinates, per-trace
  disposition/completeness, edit, soft removal, Undo/Redo, save and reload. Purple
  dashed 2D observations are distinct from generated orange ceiling/wall routes;
  no circuit, class, height, depth, connectivity or quantity is inferred. Explicit
  previously stored elevations survive editing; unknown heights remain null.
- Independent review found and fixed two seams: historical partial reviews must
  restore omitted candidate traces unresolved while preserving tombstones; applied
  wiring edits must be disabled during in-flight save. No remaining review blocker.
  Responsive card uses existing theme tokens; no new dependency or geometry model.
- PASS focused frontend42 tests/four files; restricted isolated interpretation
  API13 tests (draft reload, removal history, no unintended canonical layout).
  Full frontend65 files/568 tests; full isolated backend1267 passed/4 skipped,
  1396 subtests, five existing warnings,102.91s. Full runs preceded the final
  responsive markup/CSS correction; focused42 and build passed again afterward.
  Scoped staged-only snapshot independently passed40 focused frontend tests,
  build and lint; it excludes unrelated worktree changes. Initial snapshot build/
  lint used an incorrect relative runtime path (0 checks); absolute-path retry
  passed. Snapshot archived under ignored training storage, outside test discovery.
  Scoped lint, build, compilation and diff checks PASS. Full lint FAIL: six existing
  unrelated errors in untracked DeviceMeshCatalog.jsx; large build chunks warned.
  Initial sandbox frontend rename failure ran0 tests; host rerun succeeded. Initial
  new backend test insertion accidentally absorbed prior test assertions; corrected
  insertion and rerun13 PASS, then full regression above. Failures not hidden.
- Actual connected DESIGNER browser: plan9376/job24213 original manifest matches
  source915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9.
  One sheet-11-user-mu8o2vah polyline copied as an assistant import proposal, partial
  and unresolved. Blank entry rejected; revision2 saved/reloaded, revision3 retained
  removal tombstone, Undo restored unresolved revision4. No human approval claimed.
  Source overlay visually aligned; unmeasured traces intentionally absent from 3D.
  Browser evidence: ignored wall-routing-runtime-20261009-v1/browser-visible-wiring-
  review.jpg and browser-visible-wiring-overlay.jpg. No duplicated upload or layout
  publication. Required approved scale, elevation, wall dimensions and canonical
  geometry remain absent for live measured wiring; this does not block draft review.
- General wall diagnosis, not per-page patch:48 immutable synthetic cases repeated
  exactly; all12 hatch cases erase real walls before Hough by inflating page cutoff;
  all24 doorway cases preserve openings. Original-stroke statistics plus local
  radius checks recover walls but also accept wiring/furniture and reduce lighting
  trace agreement. Dense overflow retry discards useful original votes, but keeping
  those votes introduces text/parking/fixture bands. Existing tolerant junction
  checks also pair dimension lines with exterior walls. These trials are REJECTED;
  detector defaults/weights unchanged, broad wall quality still NOT COMPLETE.
- Evidence: ignored wall-synthetic-diagnostic-20261009-v1,
  wall-original-line-guard-20261009-v1, wall-original-vote-preservation-20261009-v1.
  Reviewed wiring inventory62 records:7 deleted,2 needs_review,9 unresolved excluded;
  44 explicit reviewed traces source-verified,30 clear crop windows/14 ambiguous
  windows separately excluded by assistant crop review. No new training or approval.
  Existing8/8 wall/opening memorization remains only earlier pipeline evidence.
- OpenAPI36 paths/44 operations; ORM34 tables, unchanged. Original export, source
  files, annotations/history, unrelated work and recovery stash retained. Scoped
  checkpoint only; unpushed, not a release. Overall wall/wiring objective ACTIVE.
  Next: actual mate-to-transverse-wall corner support and rotation-robust thickness
  qualification, tested against wiring negatives before any detector activation.

### October 9 explicit obstacle workflow and wall learning diagnosis (after ccd859f)

- Added single-floor rectangular barrier entry to circuit and single-route forms
  through the existing Obstacle contract. All six bounds are explicitly entered
  in saved metric coordinates/absolute elevations; no automatic depth, wall
  attachment or measurement. Strict finite/ordered/exact-key/floor validation,
  128-item cap, accessible inline errors and focused submit failures. Empty input
  remains no additional entered barriers, not evidence of an unobstructed floor.
- Circuit obstacle values survive compatible save/reload and stable refresh;
  add/remove/edit invalidates preview and uncertain-save retry identity. Review
  caught a single-route reload loss: now matching saved ceiling-route barriers
  restore; stale/foreign/underground/malformed barriers block recalculation
  rather than silently disappearing. Endpoint/elevation inputs in that older
  form still require explicit re-entry. No route/schema/auth/API changes.
- PASS: root56 focused routing frontend tests; full frontend63 files/545 tests;
  focused restricted isolated backend82 routing/underground/API/material tests,
  two existing dependency warnings; build, scoped lint and diff checks. Independent
  review46 tests/four files PASS after its reload finding was fixed. Full backend
  NOT RERUN for this frontend-only change; prior1265/4 skips/1396 subtests belongs
  to ccd859f. Full lint FAIL: six pre-existing errors in untracked
  DeviceMeshCatalog.jsx. Large bundle warning remains. Initial test invocation
  named nonexistent circuit files and ran zero tests; corrected five-file run
  above passed. OpenAPI36 paths/44 operations/ORM34 freshly unchanged.
- Computer-use browser checked the actual shared obstacle component in an
  explicitly labeled ignored local fixture: restored bounds, reversed-bound
  rejection retaining edits, new blank required row, removal retaining original
  values. Screenshot browser-obstacle-controls.jpg under the existing runtime
  evidence directory. This is component evidence, NOT live route generation or
  database persistence. Existing browser review remains job24213's unfinished
  draft. Read-only live inventory: zero canonical layouts/route versions; all
  three floors6323/6324/6325 lack approved scale and elevation. Live measured
  routing/2D-3D circuit validation remains BLOCKED by those specific inputs.
- Actual bounded local wall learning completed: OpenCV RTrees, one tree, eight
  unique reviewed sheet24 strips (four standard walls/four explicit openings),
  four exact repetitions each. Eight/eight TRAINING matches versus constant-class
  four/eight; fit0.005245s. Root reconstructed every crop/feature from original
  coordinates and reproduced checkpoint predictions. Checkpoint SHA256
  2cd64ce3a3dbed12d768acf2437414ce7d0c638059e38df2e1d9d5531235b8ed.
  Artifacts: wall-strip-learning-check-20261009-sheet-24-v1/run-001-trees.
  Four inspected ambiguous strips excluded; remaining332 audit records unused,
  not rejected. No unlabeled background supervision, full-page localization,
  generalization score, larger training run or runtime activation. Existing
  user attestation applies; no new human approval fabricated. Originals intact.
- General wall diagnosis continues: independent-original-mate/two-existing-junction
  local seeding adds no new geometry on24/35/11/school controls; retained as
  ineffective, not activated. Expanding original Hough pool256->768 adds pairs
  on35/43/11 but no supported long architectural seed for poor pages. No thinning
  rerun in that pool probe;43's prior failure remains unscored. Reports preserved
  in wall-local-pair-seeding-20261009-v2 and wall-original-pool-20261009-v1;
  pool report SHA25675dc2dee73e51b63f58ba370191c093725945af8147921dc70bdf52f8398686b.
  Next: repair original architectural stroke/mate extraction with positive and
  wiring/hatch controls, not arbitrary global cutoff or per-page coordinates.
- Scoped checkpoint on codex/vlm-localization-experiment only; general wall
  quality, live measured wiring and release acceptance remain incomplete.
  No push, model promotion, dataset/original deletion or stash mutation. Existing
  unrelated1479 ledger lines and other edits preserved; no new Markdown files.

### October 9 exact thinning performance (after d60dd6c)

- Replaced repeated Zhang-Suen predicates with two immutable256-entry lookup
  tables and a bounded deletion-region search. Same region for both synchronous
  phases; deletion union plus TWO-pixel halo for the next round. Input bytes,
  output raster, border/disconnected strokes and exact128-round success/error
  boundary preserved. No threshold, model, dependency or inference budget change.
  Native coordinate and 2D/3D/canonical contracts unchanged.
- PASS: root72 existing wall/gap tests/64 subtests;21 equivalence/demo tests/738
  subtests;5 standalone replay tests; independent21 equivalence/gap tests/733
  subtests and lookup review. Final isolated full backend1265 tests/4 skipped/
  1396 subtests,5 dependency warnings,92.54s. Compilation/scoped diff PASS.
  Frontend unchanged; its previously recorded514 tests/build/scoped lint belong
  to the earlier checkpoint, not a fresh run here. Six unrelated full-lint
  errors and bundle warning remain. Endpoint/table contracts not modified.
- Exact production adaptive-mask comparisons: source03 thinning12.466s->2.028s
  (same raster,38 rounds); source43 60.638s->6.932s (same diagnostic intermediate
  raster and THINNING_BUDGET_EXCEEDED at128 rounds). These timings measure ONLY
  thinning, not upload/job/model latency or improved detection quality. Additional
  3560 bounded diagnostic comparisons match rasters/round outcomes. Worst-case
  O(128N) time/O(N) memory retained. Tracemalloc tracked allocation17.77MiB for
  one sparse3200x2868 fixture and5.73MiB for a dense million-pixel fixture;
  these are not total resident/native-memory measurements.
- Local backend verified idle then restarted with the tested thinning code.
  Browser reload retains job24213's54 walls/5 rooms/70 unresolved symbols and
  non-approval notes. This reload is persistence evidence, not a fresh inference
  or live measured-routing check. OpenAPI36 paths/44 operations/ORM34 unchanged.
- Wider failure diagnosis: closing11px inflates source24 sustained radius p90
  4.0->27.58px, raising cutoff1.6->11.03px. Using original statistics alone
  produces84 candidates vs4, and lighting54->185, including furniture/wires.
  Manufactured-core guardA lets43 complete but reaches only5.31%12px trace
  agreement;24 reaches81.46% but adds furniture/CCTV wiring;35 reaches14.65%
  with outside/noise strokes. These development trials are REJECTED for runtime
  activation; no disguised page-specific removal or increased thinning budget.
- Training feasibility:255 physical traces are source-positive development
  evidence, not fully labeled segmentation masks. Explicit85 openings retained.
  The non-wall geometry inventory is mostly rooms, symbols or deleted/unresolved
  records, not an adequate reviewed wiring/hatch-negative set. Do not label
  unannotated areas as background or call these CV trials model training.
  General wall quality and live measured routing remain incomplete; reviewed
  scale/elevation/canonical inputs are still absent on the current floor.
  Originals, unrelated edits, historical results and recovery stash preserved.

### October 9 wall-label reconciliation and replay compatibility (after bd85594)

- The earlier313-polyline feasibility total was lexical, not a physical-wall
  training total. Fresh exact-export/source audit identifies85 explicit
  opening/doorway polylines; preserve them as openings and exclude them from
  positive-wall labels. Remaining228 candidates:214 standard,3 glass,11 untyped.
  No duplicate IDs, exact reversed polylines or source hashes found. Later source
  lookup reconciles27 previously unmatched traces to exact additional reference
  PNG hashes/dimensions:14 pages/340 wall-named polylines,255 physical traces
  (214 standard,3 glass,38 untyped),85 openings. Keep untyped traces separate;
  visual interpretation can cross openings and is not wall-width truth. Groups1-6
  remain related development evidence, not independent project evaluation.
  Existing user attestation is retained; no separate approval is invented.
- Dimension/wiring investigation: outside-dimension source crop contains paired
  baselines, ticks and numeric labels. Current preparation emits SYM_n text-region
  placeholders, not recognized numbers; no local Tesseract runtime was found.
  Position-only rejection would endanger detached structural walls. No such
  guard or page-specific deletion was activated. A later safe dimension filter
  needs actual text plus geometry evidence and structural-wall preservation.
- Narrow diagnostic fix forwards new partial_pairs/evidence options through the
  existing --thin-outline-votes wrapper. New CLI regression failed with
  INFERENCE_FAILED before the fix; all5 standalone diagnostic tests pass after
  it, compilation/diff PASS. Initial test tempfile location was sandbox-denied;
  fixture now uses a disposable directory inside repository storage. Production
  inference defaults and bd85594 detector are unchanged. Full backend/frontend
  results recorded for bd85594 belong to that checkpoint; no new full run
  claimed here.
- Additional browser proof: job24213's saved draft rendered in WebGL3D after
  reload with the same wall proposal set. Screenshot browser-job-24213-3d.jpg
  retained beside 2D evidence. Preview dimensions are illustrative, not saved
  measurements; no scale/elevation/canonical approval or metric route invented.
- Frozen c30967b vs bd85594 replay finished the original12-page manifest:
  11 successful pages; both versions fail page43 with THINNING_BUDGET_EXCEEDED
  after about69 seconds. Its34 standard traces are unscored, not zero accuracy.
  On successful pages'180 standard traces, length-weighted agreement within12
  source pixels/15-degree tangent improves45.357%->46.231%; page11 improves
  82.967%->89.279%. Page24 remains7.793%,25=12.697%,27=12.194%,35=0%,38=0.752%.
  Three glass traces remain0%. This is partial reviewed-positive trace coverage,
  NOT wall accuracy, precision or independent recall; centerline interpretation
  and false-positive coverage are incomplete. All12 source hashes unchanged;
  exact detector/demo Git hashes, outcomes, records and overlays frozen in
  wall-positive-coverage-20261009-v1/report.json. The recovered two PNG pages
  are not silently included in this original benchmark. General detection is
  demonstrably incomplete; next: hatch/style failures and bounded thinning.
  Precision, independent accuracy, training and production release unverified.
  Originals, historical manifests, unrelated edits and stash@{0} preserved.

### October 9 bracketed wall-gap recovery (after 84eda30)

- Diagnosed actual missing edges: original grayscale AND primary binary retain
  exterior mates, but the page-wide stroke-radius skeleton discards their thin
  ink. A one-direction hollow style fails the global two-direction outline
  gate. General recovery now uses compatible existing fragments, bounded paired
  hypotheses, both original mate rays and white cavity evidence. No page-specific
  coordinates, new wall seeds, unbracketed extension or changed Hough voting.
  True two-edge openings and filled-wire gaps remain unbridged. Caps:512
  fragments/pairs,128 endpoint hypotheses, gap<=40% of raster short edge.
- Existing grid/glyph guards qualify anchors BEFORE recovery; proposed merges
  pass the same guards BEFORE replacing them. A rejected merge preserves both
  original accepted fragments. Initial replay exposed a fixture-as-long-wall
  regression despite passing tests; fixed ordering and added its regression.
  In-memory red/green proof confirms the prefilter-less version produces that
  false extension and the final version rejects it. Earlier artifacts retained.
- Frozen final detector SHA256
  c4ad4b61d9008520d52d26e7698c047a4600a6a92c138d00c0967ad9877340a3,
  evidence cv-bracketed-outline-recovery-v6. Lighting source22f024...350d28:
  56->54 walls,4->5 rooms. Exactly three exterior fragments become one observed
  band(217,1439)->(210,2986), recovering both gaps; every other53 wall geometries
  unchanged. Selected school sourcecfb10f...8cac72 retains11 walls/5 rooms and
  byte-identical before/after JSON. Both original hashes unchanged; v5
  geometry-delta artifacts bind code/source/JSON/overlay hashes. These are
  development comparisons, not precision, recall or human approval.
- PASS: final focused wall95 tests/126 subtests; independent review13 tests;
  final isolated full backend1257 tests/4 skipped/663 subtests,5 warnings;
  compilation/diff checks. Frontend remains514 tests passing, scoped lint/build
  PASS; six unrelated full-lint errors and chunk warning remain. Endpoint/table
  counts unchanged36 paths/44 operations/34 tables. Mixed worktree, not release.
- Verified idle backend restarted locally with final code; credentials,
  configuration, source uploads and selected symbol checkpoint unchanged.
  Browser computer use: fresh lighting job24213 completed54 walls/5 rooms;
  unfinished review revision1 saved and reloaded with70 unresolved symbols and
  explicit non-approval notes. Wall-only overlay inspected; screenshot retained
  under wall-routing-runtime-20261009-v1/browser-job-24213.jpg. No duplicate
  upload or canonical approval created. Pending: dimension-chain false
  wall and ambiguous fixture/grid/wiring fragments; metric wiring requires
  real reviewed scale/elevation/canonical layout. No wall model trained:313
  source-verified polylines/12 pages are a potential partial benchmark; complete
  masks, deduplication and project splits remain unverified. Current OpenCV has
  no trainable weights. Unrelated work and recovery stash retained.

### October 9 explicit underground planning (after c30967b)

- Added single-floor underground circuit planning to the existing orthogonal
  shared-tree engine. Requires an entered service elevation below the saved
  floor and explicit passage inputs at selected endpoints. Above-floor legs
  require real verified wall attachments; no implicit riser, depth, wall,
  mounting height or engineering approval is created. Closed obstacles still
  block horizontal and vertical spans. Legs split at the saved floor boundary;
  overlapping branches count shared path length once.
- Existing save/CAS/retry/authorization contracts persist the new inputs and
  segment kinds without new tables. Legacy ceiling retry comparison normalizes
  only the absent passage default, without rewriting historical JSON. Dedicated
  isolated API checks prove underground save/reload/idempotence and unchanged
  canonical geometry. Measurement validation recognizes underground kinds;
  planning circuits remain blocked from unconfigured material estimation.
- Shared 2D/3D projection uses blue dashed below-floor runs and passages. The
  explicit 3D X-ray inspection toggle changes occlusion, not coordinates or
  saved geometry. Ordinary depth occlusion remains default. Compatible saved
  membership, depths and passage inputs restore; general confirmation is not
  assumed. Existing ceiling fallback remains.
- PASS: focused isolated backend82 tests; focused frontend7 files/45 tests;
  full isolated backend1244 tests/4 skipped/663 subtests,5 dependency warnings;
  full frontend61 files/514 tests; scoped lint, compilation and diff checks;
  build with existing >500kB chunk warning. Full lint FAIL: six pre-existing
  errors in unrelated untracked DeviceMeshCatalog.jsx. Full runs cover the
  current mixed worktree, not a clean production release. OpenAPI endpoints
  and ORM tables unchanged (36 paths/44 operations/34 tables).
- Browser computer use: fresh whole-page school job24212 completed with14 wall
  proposals/2 rooms/29 unresolved symbol proposals; 2D overlay and draft WebGL
  scene rendered. Unfinished review revision1 saved without approval; reload
  retains14 walls,29 unresolved symbols and non-approval notes. Current
  floor6323 still lacks an approved scale/elevation and reviewed canonical
  layout; live metric circuit generation/X-ray rendering remains NOT TESTED.
  Screenshots retained under wall-routing-runtime-20261009-v1. No measurements
  were fabricated. Template/VLM/model/training activation unchanged.
- Initial DB preflight was blocked by sandbox connectivity; a privileged
  read-only check verified restricted account, empty data tables and seeded
  roles. Isolated reruns above passed; no credentials, permissions or data reset.
  Initial legacy test assertion incorrectly expected raw JSON on a defaulted
  response; corrected while retaining exact stored-history assertions.
- Scope checkpoint only. Multiple simultaneous saved circuits remain open;
  wall skeleton gap diagnosis continues separately. Originals, dataset history,
  unrelated edits and recovery stash bb78854e87833124a1725b51f0be6099a8ac0cfa
  retained. Independent detection accuracy and production release pending.

### October 9 native-resolution hollow-wall recovery (after 98f1f05)

- General detector repair, without source-specific coordinates: native outline
  separation now scales with the page within a 64px cap. Overflowing dense Hough
  pools receive at most 256 deterministic axis proposals, checked against the
  original ink/cavity, enclosure and existing wiring/fixture guards. Two halves
  beside a true door gap survive high-resolution voting; the opening is retained.
  Row-streaming uses 128-entry heaps per axis instead of raster-sized coordinate
  arrays. Demo geometry evidence is versioned cv-native-outline-recovery-v5.
- PASS: focused wall regression 60 tests/64 subtests plus bounded-stream test;
  independent review's two native tests passed. Additional 4000x3200 synthetic
  drawing retains six architectural walls, suppresses bold wiring and preserves
  its doorway (22.76s full detection). At 4096x4096 the supplement takes 1.63s
  on alternating strokes and 0.223s on filled ink, with <=256 proposals.
- Current-source frozen v2 replays bind detector SHA256
  74a62d098bacdea2c350d516e60d477cc31f13c6690d6a961b627c6aa4aa3266:
  lighting24210 keeps exact56 walls/4rooms; selected school keeps exact11
  walls/5rooms. Both original hashes unchanged. This proves retained geometry,
  not improved accuracy on those two pages. Lighting still has weak-gray exterior
  gaps, a dimension false wall and uncertain grid/fixture/wiring segments; see
  ignored wall-native-20261009-lighting-inspection-v1 proposal overlay.
- Wall training feasibility, source export SHA256
  829de08a31e2c8014ac6194cb958f999b2aa534297af749a661b31d7a383afc9:
  313 wall-named polylines on12 exact-source-verified pages pass finite/bounds
  checks. Excluded58 non-wall records,20 deleted walls,5 needs-review walls,
  53 wall bbox/polygon records and27 unmatched-source wall polylines. These are
  preparation counts; deduplication, project splits and complete mask coverage
  remain unverified. No wall model was trained; OpenCV has no learnable weights.
- Full isolated backend PASS1208 tests,4 skipped,663 subtests,5 existing warnings.
  This run covers the then-current worktree, not a clean-checkout release gate;
  it supersedes the earlier recorded OpenAPI-count failure. Final streaming and
  provenance changes additionally passed focused25 tests/5 subtests. OpenAPI
  freshly inspected36 paths/44 operations; ORM34 tables. No schema change.
  Full frontend510 tests/build and scoped lint passed in the preceding wiring
  checkpoint; full lint still has six unrelated DeviceMeshCatalog errors.
- Experimental symbol repairs remain inactive: v1 removed seven inspected
  mezzanine errors while retaining8/8 known positives, but introduced hatch-like
  troffers. v2 also retains8/8 there but loses a known sheet17 positive; its
  training-source replay is805/830 exact-class matches, precision unscored.
  Existing power80 checkpoint/fallback retained. No larger training run.
- Next: apply these verified changes to the idle local runtime and browser-check
  processing; preserve grayscale wall evidence generally. Saved metric wiring
  on current floor still needs an actual reviewed canonical layout; no scale,
  height, approval or walls will be fabricated. Multiple-circuit and underground
  work remains open. Originals, historical artifacts, unrelated changes and
  stash bb78854e87833124a1725b51f0be6099a8ac0cfa preserved.

### October 9 saved 2D circuit workflow and ceiling boundary (after 056c2bb)

- Saved canonical 2D now uses the existing shared circuit preview/save workflow,
  the same route projection and immutable backend route versions as 3D. Moving
  devices clears the preview and suspends routing until layout save/discard.
  Designer-only controls remain enforced by the existing backend authorization.
- Compatible saved circuits restore explicit membership, panel position/wall,
  device/service elevations, installation method and grid spacing. Ordinary
  rerenders preserve edits; changed snapshots abort outstanding requests and
  clear previews. Stale, mismatched or unsupported configurations stay blank.
  No dimensions, circuit assignments or confirmation are inferred.
- Fixed a general routing defect at the exact verified wall-top service plane:
  structural occupancy excludes its upper boundary (1e-9 arithmetic tolerance).
  Lower service planes, taller walls and closed explicit obstacles remain
  blocking. New tests reproduce committed behavior in memory (4 failed/5 passed)
  and verify current ceiling drops, shifted floor elevations and explicit risers.
- PASS: restricted isolated MySQL routing/persistence regression 47 tests, two
  existing dependency warnings; focused frontend 5 files/39 tests; full frontend
  61 files/510 tests; scoped lint; build; routing compilation. Build retains the
  existing >500 kB chunk warning. Full lint FAIL: six errors in unrelated untracked
  DeviceMeshCatalog.jsx. Full backend NOT rerun here; earlier OpenAPI-count
  failure remains unresolved and is not represented as passing.
- Computer use inspected the actual authenticated Designer's current project
  10218/floor6323: saved 2D reports no current layout. No approval, scale, elevation
  or canonical geometry was fabricated to exercise wiring. Live circuit
  generation/save/2D-to-3D reload remains NOT TESTED for this floor; isolated API
  save/reload and UI integration above are distinct evidence.
- No schema/API-count change or model activation. Only the latest saved project
  circuit is displayed; historical versions remain stored. Underground routing
  and explicit below-floor geometry remain unimplemented. Next: general wall
  recovery/source replay, then multiple saved circuits and underfloor inputs.
  Original uploads, training artifacts, unrelated edits and recovery stash
  bb78854e87833124a1725b51f0be6099a8ac0cfa are preserved. Scoped local checkpoint;
  production, independent accuracy and electrical release approval remain pending.

### October 8 mezzanine native-context diagnosis (after 1d25c21)

- Fresh shared power80 replay on supplied sheet-08, source SHA256
  `6ad0b03b0fede2142fabd88114af086184e8fa97d1acaa70fbdb506e87b34128`:
  20 proposals at score0.50, 6.853s, no candidate truncation. Frozen output:
  `storage/training/mezzanine-symbol-review-20261008-v1/report.json`.
- Exact-class one-to-one IoU>=0.50 matches all8 existing source-bound training
  labels (five recessed downlights, three homeruns). This is training-source
  recall on eligible positives, NOT complete-page or independent accuracy.
- Assistant visual inspection identifies seven false proposals: two elongated
  solid columns called troffers, two grid bubbles called homeruns, OPEN BELOW
  text and a dimension number called switches, and a solid column called smoke
  detector. Five other proposals remain unresolved, including competing classes
  on real glyphs; those areas are not negative training truth. No human-review
  claim, full-page precision, or new approval is inferred.
- Existing negatives include overlapping grid/dimension/column crops, but not
  the two elongated columns or OPEN text. Native-context mismatch is a testable
  training hypothesis, not a proven explanation for every error. Merely raising
  a threshold or masking this page's perimeter would not solve internal errors.
- Added `scripts/prepare_native_symbol_context.py`: source/hash/legend-checked,
  immutable diagnostics reuse the actual native256 serving lattice, preserve
  all80 head identities, and supervise only complete existing positives plus
  explicit inspected negative rectangles. Unknown pixels and clipped positives
  remain ignored; overlapping positive/negative evidence is rejected.
- Prepared43 native windows with8 unique positives and7 negative regions under
  `storage/training/mezzanine-native-context-20261008-v1`. Original source and
  historical manifests preserved. The output is a diagnostic bundle, not a
  full-page training dataset or automatically consumed production dataset.
- Focused preparation/frozen-tail/partial-label tests:37passed,122subtests.
  Initial sandbox temporary-file denial resolved by host test execution; no
  database access. Browser/full-backend/frontend gates NOT rerun for this
  preparation-only change. Earlier full-backend OpenAPI-count failure remains.
- Next checkpoint: consume these masked native windows in a bounded candidate
  repair with real positive controls for affected classes; replay original
  sources before any activation. No checkpoint/threshold/live service changed.
  Detection improvement and ceiling/wall/underground routing goal remain open.

### October 8 boxed fixtures and anchored corners (after 12b61ee)

- Inspected native school-plan crops: six false wall segments follow closed,
  narrow fluorescent rectangles containing a printed2 and circuit crossings.
  Their two sustained side strokes bypassed the existing three/five-bar guard.
  New bounded original-pixel evidence requires two compatible sides, both closed
  caps and a localized partial-width interior mark. Original wire crossings,
  plain hollow/solid partitions, open-ended strokes and long walls are retained.
  The final check runs after consolidation; it does not change global wall votes.
- Rotation tests exposed raster cap staggering and partial pixels from ordinary
  wire crossings. Cap-only one-pixel neighborhood evidence and observed exterior
  wire flanks resolve those failures. Interior pixels are not dilated. Tests
  include native/2x,90-degree/6-degree rotation, crossed walls, short partitions,
  unchanged source arrays, and an end-to-end outlined-wall scene.
- The selected school page's left band had observed mates through its full
  length but depended on a top band recovered in the same pass. Two bounded
  recovery waves now allow a previously anchored band to support the next corner.
  Whole-wave decisions prevent mutual approval or order dependence. Unsupported
  cycles and the512-hypothesis/support budget retain conservative behavior.
  Geometry provenance:`cv-boxed-glyph-anchored-corners-v4`.
- Development replay against12b61ee, selected(18,45,660,270):17->11 wall proposals;
  all six inspected fluorescent false walls removed; left(24,146)->(24,246)
  restored to(24,50)->(24,309); other retained wall coordinates unchanged.
  Room proposals6->5 remain unreviewed. Native lighting selection remains50
  walls/4 rooms, source hashes unchanged. Same development project; no independent
  detection precision/recall measured. Original images and weights unchanged.
- Final staged proof `boxed-index-proof-20261008-v1`:156 focused tests passed/
  151 subtests; working focus157 includes an unrelated pending test. Full isolated
  backend1122 passed,4 skipped,593 subtests,5 dependency warnings,ONE FAIL:
  existing `test_review_image_api.py:367` expects44 operations; scoped source43.
  Full suite remains FAIL. No API/schema changes:35 paths/43 operations/34 tables.
  Compilation and scoped diff checks PASS. Frontend tests/build/lint NOT RERUN
  for this backend-only change; known unrelated frontend lint work remains.
  Automatic school replay is unchanged at13 walls/2 rooms; its previously noted
  diagonal artifacts remain. Selected replay confirms17->11 walls and repaired
  left boundary. All50 lighting wall coordinates remain identical.
- Browser job24203 completed with saved selection(18,45,660,270), geometry v4,
  11 walls/5 rooms/20 unresolved symbol proposals. Persisted wall payload exactly
  matches the staged replay. Saved unfinished revision1 and its assistant note
  survive reload; review_complete/approved_for_layout remainFALSE. Earlier
  job24202/revision1 and its false-wall rejection remain stored. Source/candidate
  hashes PASS. Browser2D wall overlay and3D draft both rendered and screenshots
  were saved beside the selected final replay. Device layer was temporarily
  hidden for the wall-only screenshot, then restored. Measured canonical routing
  remains BLOCKED by missing approved scale/elevation and legend-mapped reviewed
  placements; draft40m/3m dimensions are illustrative.
- Acceptance:inspected fluorescent false walls removed, observed corner recovery,
  negative controls, source integrity and save/reload PASS. Overall independent
  detection readiness remains unverified; general symbol errors need the next
  diagnostic. Unrelated padding/catalog/UI work and recovery stash preserved.
  Next:inspect raw symbol mistakes and approved legend linkage on the supplied
  pages, then proceed to shared ceiling/wall/underground routing implementation.
  Routing development has not started in this checkpoint.

### October 8 junction-backed cavity recovery (after b0ea5e7)

- Missing school-plan left perimeter traced to original-pixel evidence, not
  absent Hough votes: sustained outlines at x21/27 from y52..307 exist. A dashed
  middle stroke leaves only37.5% white at the exact center, below the45% cavity
  test; nearby original cavities retain96.9%/57.8% white. Short fragments also
  trigger the equally thin three-bar wire guard. No source coordinates enter
  application rules. Four native/2x/rotation RED subcases reproduced the loss.
- Deferred recovery requires two independently established perpendicular wall
  junctions at the band endpoints, long span, observed white on both interior
  sides, compatible original stroke widths, and actual gaps in a three-bar
  middle stroke. Filled-wire interiors, continuous wire bundles, wide bundles,
  unjoined bands and mutual self-support cannot qualify. Optional hypothesis
  and support pools are bounded at512. Geometry version
  `cv-junction-backed-cavity-v3`; no symbol model or detector threshold changed.
- Live wider-padding context fragments the same observed Hough mate into73px,
  53px and37px pieces. Deferred bands now follow BOTH original observed edges
  until the first unsupported raster step, then require independent endpoint
  junctions. Recovery cannot bridge a doorway-sized blank; native/2x opening
  controls pass. Established transverse support needs the normal minimum line
  span, while the recovered band must remain long. Current working padding stays
  unrelated/unstaged; an intermediate replay restored(24,46)->(24,313).
  That intermediate working context still had incomplete horizontal spans / zero room proposals;
  this is not represented as complete live geometry or measured room detection.
- Focused new/previous ceiling-grid checks13 passed /35 subtests. First rotation
  retry failed because the global center sample was white45.3% while the
  narrower bar sample looked continuous; explicit observed-middle-gap evidence
  resolves that discrepancy. No failed attempt is represented as passed.
- Initial staged mask-mutating replay restored the left boundary and room partition, removed
  two apparent diagonal artifacts:12 walls/1 room->12 walls/3 rooms. Lighting
  selection50 walls/4 rooms and all wall coordinates unchanged. Both sources
  retain their SHA256. Same development project, not independent accuracy.
  The tight school drawing crop still produces fixture-shaped wall proposals;
  this remains a failing development case, not evidence of detection readiness.
- A later tight-crop replay exposed a newly introduced fixture-wall proposal:
  appending recovered ink to the mask changed distance/skeleton/Hough statistics
  for unrelated objects. Recovery now occurs AFTER consolidation, replacing only
  covered collinear fragments. Original vote mask, median width and existing
  end recovery stay identical. Dedicated invariance and duplicate tests cover
  this boundary. Latest working tight-crop replay retains17 wall proposals and
  extends only the top outline(522,53)->(675,53) to(20,53)->(675,53).
  The left crop-boundary fragment and existing lamp false walls remain unresolved;
  six room proposals are unreviewed development output, not measured correctness.
- Initial staged focus126 passed/124 subtests, isolated persistence67 passed/
  34 subtests. Full staged1114 passed/4 skipped/566 subtests with ONE FAIL:
  existing review-image OpenAPI assertion expects44 operations; scoped source43.
  These totals precede the additional observed-edge recovery; they are not final
  checkpoint verification.
- Final staged proof `cavity-index-proof-20261008-v3`:152 focused tests passed /
  126 subtests. Working-tree focus153 passed/126 subtests includes an unrelated
  pending test; it is not substituted for staged evidence. Isolated persisted
  review/save/processing focus41 passed/34 subtests. Full isolated staged run:
  1118 passed,4 skipped,568 subtests,5 dependency deprecation warnings,ONE FAIL
  at `test_review_image_api.py:367` (43 versus44 operations). Scope has35 paths,
  43 operations,34 model tables. The count failure already exists at HEAD;
  unrelated catalog endpoint/test edits remain unstaged. Full suite is NOT PASS.
  Compilation and staged diff checks PASS. No frontend code changed in this
  checkpoint; frontend unit/build/lint NOT RERUN. Existing unrelated untracked
  DeviceMeshCatalog lint failures are not resolved by this backend checkpoint.
- Final immutable before/after evidence:school automatic1%-padding scope
  12 walls/1 room->13 walls/2 rooms, adding ONLY observed left(24,50)->(24,309)
  while preserving every previous wall coordinate. Drawing-only selection
  (18,45,660,270) remains17 walls, room proposals1->6; only the top band extends,
  with other coordinates unchanged. Native lighting selection remains50 walls/
  4 rooms with every coordinate identical. Both source SHA256 values unchanged.
  Explicit selection avoids the unrelated live3%-padding hunk. These pages belong
  to the same development project; no independent precision/recall is measured.
- Computer-use browser verification PASS for existing plan9377 (no duplicate
  upload):job24202 completed with `development_multiclass56_yolo`, geometry
  `cv-junction-backed-cavity-v3`, saved selection(18,45,660,270),17 raw walls,
  6 raw room proposals,20 unresolved symbol proposals. Visually compared the
  fluorescent body at(511,82)->(511,124); saved wall-0006 rejection as an ASSISTANT
  development proposal in revision1, with explicit non-approval notes. Reload
  retained rejection and note; active wall count16. Review-complete and approved
  remainFALSE. Previous job24189/revision1 fluorescent legend correction retained;
  source/candidate hash checks PASS. Raw candidates are unchanged by draft review.
  Browser 2D and shared draft3D rendered; evidence images are saved beside the
  final selected replay. Measured canonical2D/3D/routing verification BLOCKED:
  no approved scale/elevation or completed legend-mapped placements for this run;
  draft40m/3m display is explicitly illustrative, not approved measurements.
- Acceptance:source integrity, bounded recovery, unaffected vote mask, focused
  checks and draft save/reload PASS; general wall/symbol correctness still FAIL
  (cropped-left incompleteness, lamp false walls, spurious symbols). Wiring and
  production readiness NOT IMPLEMENTED/NOT CLAIMED. Next smallest experiment:
  suppress compact fluorescent-rectangle wall hypotheses using original-pixel
  side/end evidence while retaining hollow structural partitions, then replay
  both frozen native sources. It has not started in this checkpoint.
  Original scans, annotation history, model weights and recovery stash preserved.
  Incomplete boundaries/columns and erroneous symbol classes remain advisory;
  wiring implementation and production readiness remain unclaimed.

### October 8 native compact-fixture evidence (after 8a8e177)

- Source inspection identified two remaining troffer-body wall proposals:
  (372,1302)->(376,1401), (1071,1303)->(1069,1422). Original transverse profiles
  contain a bold body with two thin companion strokes on each side. One native
  companion is only1px; the old2px condition passed at2x but failed at native size.
  The other glyph exceeded the old10%-of-page-length guard despite compact
  length/thickness. RED tests reproduced three failing native/2x subcases.
- Retain the full four-companion evidence, centered bold body and existing16%
  outer size bound. Accept1px observed companions; above10% require a compact
  body aspect ratio as well. Preserve long narrow partitions, plain solid walls,
  empty double-outline walls, openings and existing grid controls. No drawing
  coordinates, model classes, templates, learned weights or inferred approval
  enter these guards. Geometry evidence version `cv-native-compact-fixture-v2`.
- Corrected native replay **52 walls / 5 rooms -> 50 walls / 4 rooms**. Removed
  exactly those two fixture segments; every other wall coordinate is identical.
  The eliminated room proposal depended on false fixture structure; this is not
  independently approved room geometry. No precision/recall or accuracy measured.
  Frozen source SHA256 remains
  `22f024231b6d02b6121dab7b9477d3624284f365619511190582978cea350d28`;
  selection(190,440,1060,2610). Private evidence:
  `storage/training/wall-evidence-20261008-fixture-v2-corrected`.
- A comparison-tool defect was found before accepting the result: dynamically
  loaded post8a8e177 code supports explicit drawing scope but function-identity
  dispatch omitted the flag, producing an invalid2-wall baseline. Historical
  execution now forwards scope only when that signature supports it; pre-scope
  code retains its original behavior. Invalid first replay is preserved privately,
  not reported as improvement. Observer tests cover both historical signatures.
- Fresh focused structural checks **124 passed / 109 subtests**; isolated worker,
  selection, review/save and wall persistence **71 passed / 34 subtests**; observer
  **4 passed**. Private isolation preflight passed; two dependency warnings remain.
  Staged-only replay verified the identical52/5->50/4 result; source unchanged.
  The exact staged snapshot excludes unrelated tests: structural **123 passed /
  109 subtests**, isolated persistence/workflow **67 passed / 34 subtests**,
  observers **4 passed**, compilation and scoped diff checks passed. An initial
  direct staged invocation mistakenly included database worker tests and hit ten
  sandbox temporary-directory setup errors before their execution; the corrected
  restricted-database runner passed all67 checks. No failed setup is counted PASS.
  Full regressions,
  frontend tests/build/lint not rerun after this change; prior8a8e177 evidence and
  its scoped OpenAPI-count mismatch / unrelated whole-tree lint remain historical.
- Frozen second-page control: normalized plan9377/job24189 sourceSHA256
  `cfb10f5329c82300fbae43933374078514c4d0c7be82d20ba0d1ec52ef8cac72`.
  Full automatic drawing scope, no threshold tuning, staged1% padding preserved:
  **12 walls / 1 room -> 12 walls / 1 room**, zero wall-coordinate differences.
  Same development project10218/floor6323, not independent held-out performance.
  Overlay still has missing left boundary and interior artifacts; unchanged counts
  do not establish correctness. Private `wall-evidence-20261008-fixture-control-v1`.
- Computer-use browser verified job24200: **50 walls / 4 rooms / 59 symbols**,
  persisted `cv-native-compact-fixture-v2`, exact frozen selection and sourceSHA.
  Soft rejection of wrong symbol0057 switch subtype plus explicit assistant-only
  notes survives draft save/reload. Reviewrevision1, complete=false, approved=false.
  Prior job24198/reviewrevision1 remains stored. Both candidate/artifact hashes
  match. Actual WebGL perspective/top draft renders; illustrative40m/3m dimensions
  remain preview-only. Canonical measured2D/3D and electrical routing NOT VERIFIED:
  recorded scale/elevation approvals and circuit/device mapping are absent here.
  No originals, model weights, authorization or production release changed.
  Screenshot: private staged evidence directory `browser-draft-3d.jpg`.
- Scoped source still **35 OpenAPI paths / 43 operations / 34 model tables**.
  Existing44-operation assertion depends on unrelated pending catalog endpoint;
  it is not made green by including that work. Recovery stash unchanged.
- Next: investigate missing outer-wall spans with source evidence, then wrong
  symbol interpretations before wiring. Missing outer-wall spans, ambiguous
  grid/column strokes and wrong symbol interpretations still require work. Wiring
  remains downstream of corrected canonical data; no invented scale/elevation,
  underground depth, circuit mapping or production activation.

### October 8 explicit drawing borders and dense outline votes (after f08ab9e)

- Verified missing-wall mechanism: selected drawings were cropped again by the
  automatic page-border heuristic. The native lighting selection had an extra
  16px interior margin; observed perimeter ink was erased near the selected
  edge. A RED synthetic border test reproduces this on all four sides.
  Explicit development selections now use the entire validated crop, restore
  source coordinates normally and retain the outside-unprocessed warning.
  Unselected uploads retain their automatic page/content mask; no coordinate
  rule or page-specific detector was added. The worker forwards this context
  explicitly. New CV geometry provenance version is separate from symbol weights.
- The untrimmed scan exposed a second failure: 3,946 raw weighted-stroke votes
  competed for the 256-line outline pool, causing incomplete/incorrect cavity
  qualification. Preserve sparse votes unchanged; only dense inputs retry using
  rising ink boundaries before the same bounded pool. Width, cavity and support
  still use original pixels. No extra model, download or training run.
- Failed variants retained privately: untrimmed/default votes produced **14 walls /
  0 rooms** and lost real partitions; cutoff1.25 did not repair it. Unconditional
  skeleton voting lost three existing native/2x opening/perimeter subtests.
  Unconditional boundary voting lost one doorway-partition test. Neither was
  accepted as a successful replacement. The density-gated version passes all
  those original controls, plus new unchanged-sparse/bounded-dense observer tests.
- PASS: working-tree focused wall/coordinate/demo/region/symbol-contract suite
  **158 tests / 126 subtests**, observer tests **2**; compilation/scoped diff.
  Includes exact-edge recovery, strict selected-scope Boolean validation,
  unchanged unselected masking, unchanged originals and sparse votes, and a
  two-call dense-vote bound. Isolated persisted worker/selection/demo API checks
  **50 passed**, with two existing dependency deprecation warnings. Private
  runner verified restricted credentials, empty verification tables and temporary
  storage. Staged-only focused structural checks **121 tests / 105 subtests**,
  observer **2**, compilation/diff PASS. Live working-tree full isolated backend
  **1185 passed / 4 skipped / 617 subtests**, frontend **61 files / 500 tests**,
  build PASS (existing large-chunk warning). Full frontend lint FAIL: six existing
  errors in unrelated, untracked `DeviceMeshCatalog.jsx`; it is not imported into
  the running viewer and is excluded from this checkpoint.
  Staged-only full backend FAIL: **1109 passed / 1 failed / 4 skipped / 547
  subtests**. Existing `test_review_image_api.py:367` expects 44 operations even
  in HEAD; scoped source has **35 paths / 43 operations / 34 tables**. Working
  tree includes the separate pending admin `/import-trained` endpoint and has
  **36 / 44 / 34**, explaining the discrepancy. Do not stage unrelated catalog
  work or change the existing assertion merely to hide that gate failure.
  Dependency deprecations and one staged pytest-cache permission warning remain.
  Restricted terminal port checks were misleading: read-only host checks and a
  fresh computer-use browser tab confirmed all services reachable. Browser job
  24197 completed with the old **39 walls / 2 rooms**; identified backend had no
  reload enabled. Verified no queued/processing jobs before restarting only that
  backend on the same loopback address/port, with access logging disabled.
  Fresh computer-use job **24198** now persists **52 walls / 5 rooms / 59 symbols**
  with `cv-native-scope-boundary-v1`, unchanged source/artifact hashes and the
  same symbol checkpoint. Rejected symbol-0057 remains rejected after draft save
  revision1 and browser reload; notes distinguish assistant inspection from
  comprehensive human review. Both approval flags remain false. Prior24196
  review retained, original upload and all three candidate hashes verified.
  Actual WebGL draft rendered after reload; this is illustrative geometry, not
  measured canonical/routing verification. Scale/elevation approvals are absent;
  no mounting height, underground depth or circuit mapping was invented.
  No database resets, credentials/grants/ACL changes or approval fabrication.
- Native source/region remain frozen: SHA256
  `22f024231b6d02b6121dab7b9477d3624284f365619511190582978cea350d28`,
  1340x3264, rectangle(190,440,1060,2610). Final comparison against f08ab9e:
  **38 walls / 2 rooms -> 52 walls / 5 rooms**. Assistant inspection sees
  recovered right/bottom architectural strokes alongside remaining grid-like,
  column/fixture and incomplete-perimeter proposals. Candidate coverage within
  inspected source bands: right x1218..1245/y490..3000 **1067 -> 1960px**;
  bottom y3010..3042/x220..1235 **276 -> 579px**, overlapping intervals unioned.
  These are source-dependent candidate-span checks, NOT precision, label recall,
  independent human review, complete geometry or general accuracy. Originals
  hash-identical; no earlier candidates/reviews/layouts were overwritten.
- Reports/overlays and failed variants remain ignored under
  `storage/training/wall-evidence-20261008-lighting-region-*`; final-v2 records
  exact historical commit and both implementation-file hashes. Diagnostic CLI
  supports explicit historical refs and opt-in cutoff/skeleton experiments;
  experimental flags never alter application defaults. Pre-existing bounds
  padding, catalog/detector work and recovery stash remain separate/preserved.
  The staged-only native replay independently reproduces **38/2 -> 52/5**, with
  code hashes recorded in `wall-evidence-20261008-lighting-region-staged-v1`.
  Local source checkpoint only; no remote publication or production release,
  with scoped full-suite count mismatch and whole-tree lint explicitly pending.
- Next: scope-aware source review of remaining ambiguous grid/column proposals
  and observed perimeter continuity, then symbol errors. Do not suppress a
  genuine partition merely because it lies among a ceiling grid. Wiring remains
  pending improved detection and reviewed canonical inputs; no invented scale,
  ceiling/underground depth, live activation, independent accuracy or release.

### October 8 parallel-stroke wall evidence checkpoint (after 9598675)

- Diagnosed two reproducible false-wall mechanisms: compact three-bar fixtures
  bypassed the existing five-bar guard; paired thin wiring could be filled into
  an outline band, while closing independently manufactured thick solid ink.
  The new original-pixel profile rejects repeated equally thin pair bundles and
  compact thin/bold-center three-bar glyphs. Solid-wall seeds on outlined plans
  now require original, not morphologically manufactured, thickness. No source
  coordinates, symbol-class prediction, page-specific template or new model is
  used by these rules. Existing long-wall, hollow-wall, solid-wall, crossing,
  opening, scan continuity and rotated-plan tests remain passing.
- PASS: new six-test regression file covers native/2x grids, real perimeter and
  partitions, thin bundles at 3px/6px pitch, three-bar fixtures and solid/empty
  outlined short-wall controls. Earlier fixture/bundle reproductions were RED.
  Focused database-independent wall/coordinate/demo/region/symbol contract suite
  passed **153 tests / 122 subtests**; diagnostic observer tests **2 passed**.
  Five initial broader failures were temporary-directory permission errors,
  not assertion failures; rerun with a workspace-local temporary directory
  passed. Compilation and scoped diff checks PASS. No frontend implementation
  changed; full backend/frontend/build/lint were NOT RERUN for this checkpoint.
  Staged-only source snapshot, independent of pending catalog/preprocessing work:
  **116 tests / 101 subtests**, plus **2** observer tests PASS; OpenAPI/model
  metadata stays **35 paths / 43 operations / 34 tables**. No external push.
- Source-dependent development evidence: supplied normalized lighting page
  SHA256 `22f024231b6d02b6121dab7b9477d3624284f365619511190582978cea350d28`,
  1340x3264, frozen architectural region (190,440,1060,2610). Before **39 walls /
  2 rooms**, after **38 walls / 2 rooms**: removed the apparent horizontal lamp
  at (435,979)-(516,979), with every other prior segment unchanged. Original hash
  is identical. Reports/overlays v1-v5 remain ignored and immutable under
  `storage/training/wall-evidence-20261008-lighting-roi-*`. This source uses the
  solid/unqualified-outline fallback, so outlined-plan improvements do not prove
  its broader quality. Assistant visual inspection still finds false ceiling-grid
  lines, fixture fragments and missing outer perimeter. Detection completeness
  and general accuracy remain FAIL/unmeasured, not established by lower counts.
- Existing diagnostic CLI now supports an exact native-pixel region and bounded
  original-pixel stripe/pair traces. Observer tests prove unchanged results,
  unchanged input pixels and a 256-segment trace limit. Existing sources,
  candidate/review revisions, trained weights and recovery stash are unchanged.
  Pre-existing plan-bounds padding and unrelated detector/catalog work are not
  included in this checkpoint. The comparison's removal also holds against the
  pre-patch working-tree diagnostic, not only against historical HEAD.
- BLOCKED: isolated MySQL preflight could not connect (2003). All local server
  listeners were stopped; one ordinary existing XAMPP launch aborted because
  `ibdata1` was not writable under this execution identity. File is not read-only;
  no database reset, ACL change, credential change or data deletion was attempted.
  Connected browser exposes the previously loaded Designer review for job24196,
  but this is cached evidence, not a fresh runtime test of this patch. Fresh
  persisted worker/review and 2D/3D browser verification remain NOT TESTED until
  XAMPP and the app servers are running with their normal filesystem access.
- Next: diagnose the solid-fallback grid admissions and missing observed perimeter
  before claiming overall wall correctness; then inspect remaining symbol errors
  on identical native inputs. Routing remains pending that detection work and
  reviewed canonical inputs. Supplied reference views support ceiling runs and
  wall drops, not a measured underground depth. No invented measurements,
  production activation, training run, independent precision or 85% claim.

### Durable drawing-selection review checkpoint (after 28f51ce)

- PASS: opt-in development drawing selection uses the existing tool rail,
  canvas, shared detector and processing endpoint. Two-corner selection inverts
  pan/zoom to source pixels; exact numeric bounds are also editable. Submitted
  bounds are locked across rail/canvas and ambiguous retries. No page-specific
  mask, automatic acceptance, new model, download or training run.
- PASS: one additive processing_drawing_selections table pins requesting user,
  request UUID, source run, exact normalized artifact hash and strict rectangle.
  Owner/Designer checks, immutable request fingerprint, payload-conflict checks
  and actual terminal retry status prevent duplicate/reinterpreted requests.
  Page identity comes from the hash-checked source run; other pages stay skipped.
  Existing no-body processing remains supported; forged JSON is now rejected.
- PASS: worker copies exact full-page normalized pixels to a new job/artifact
  namespace, interprets only the selected native-resolution crop and restores
  all geometry/raw model boxes and tile origins to the full source plane.
  Selection hash/bounds/source run are explicit provenance. Outside is
  unprocessed, not background; document state stays partial. Only deterministic
  demo CV or the shared development detector can execute this path. Production,
  promoted releases and gateway/template-specific processing are not substituted.
- PASS: candidate publication and failure/cancellation page outcomes use the
  current lease fence. Retried inference reuses its registered source artifact;
  stale bytes, selection/candidate tampering and unsupported providers fail
  before inference. No older review, canonical layout or original is overwritten.
- PASS: optional job-scoped interpretation reads retain access to historical
  candidates. Isolated SQL/API proof saves two unfinished review revisions with
  corrected coordinates, a rejected proposal and a manually added symbol, then
  reloads the exact latest revision. Original raw candidate, earlier revision,
  older run/review, current canonical layout and source bytes remain unchanged.
- PASS: development table initialized using the existing authorized local admin
  connection after the app account correctly refused CREATE (1142). Only that
  additive table was created; existing registered row counts were unchanged.
  Application read access works. No credential/grant changes, Alembic, reset,
  deletion of project data, dataset changes or stash operations.
- Verification: focused isolated backend 117 passed / 70 subtests. Fresh full
  isolated backend 1174 passed, 4 skipped, 597 subtests and 5 existing warnings
  (73.92s). Initial full run found seven contract/compatibility failures; fixed
  schema lists/counts, strict-body expectations, the pure worker mock seam and
  the existing reset utility's dependency allowlist. A subsequent run lost
  MySQL mid-run and was explicitly stopped, not counted as passing. Normal
  local server startup restored reachability; exactly nine verified synthetic
  fixture rows were removed from the restricted verification DB before rerun.
  Seeded roles and development data were preserved; fixtures are regenerated.
- PASS: final full frontend 61 files / 500 tests; production build with existing large
  chunk warning; scoped lint, compilation and diff checks. FAIL: full frontend
  lint retains six pre-existing DeviceMeshCatalog.jsx errors (unused import,
  mixed exports and conditional hooks); not hidden or edited by this checkpoint.
  Worktree OpenAPI remains 36 paths / 44 operations; model tables now 34.
  Schema-count changes are only the new selection table. The pending trained-
  legend admin operation and other training/catalog edits remain outside scope.
  Staged snapshot alone: 35 paths / 43 operations / 34 tables.
- PASS: staged-only snapshot gates: isolated backend 80 tests / 18 subtests;
  frontend 7 files / 33 tests, without pending power80/catalog changes or private
  frontend configuration. Initial index proof exposed an omitted forged-body
  assertion and misplaced JSX closing tag; corrected scoped staging, added page-
  to-canvas callback/freeze regression and removed environment-dependent URL
  assumptions from the new API test. Those initial failures are not passing runs.
- PASS: browser computer-use became available. Existing Designer session opened
  project 10218 / plan 9376 / prior job 24193; no login or role bypass. Rectangle
  (190,440,1060,2610) follows the architectural footprint plus margin, not symbol
  locations, excluding surrounding title/dimension areas. New job 24196 completed;
  source artifact remains 1340x3264, SHA256 22f024231b6d..., and prior candidate
  SHA256 a55cfea9e189... remains intact. No duplicate upload or existing-review save.
  Assistant-labelled unfinished revision 1 persists troffer center (1079,2707),
  rejected hold-up-button interpretation of S notation, and an unclassified
  marker (550,600). Browser reload verified all three; both approval flags false.
  Shared draft 3D renders. A temporary 3D-inspector edit appears in 2D and Undo
  restores the saved position; no second save or fabricated canonical approval.
- NOT VERIFIED: detector readiness and metric canonical 2D/3D. Live page has zero
  recorded metric scale/elevation settings; mounting heights and wall dimensions
  require real review. The cropped run still proposes questionable walls/classes;
  its 39 walls / 59 raw symbols are workflow evidence, not precision or accuracy.
  Reference site remains untested. Supplied views support ceiling runs/wall drops,
  not approved underground depth. Frontend/backend normal local previews started
  on loopback after read-only checks found zero active jobs/attempts.
- Preserved: original PDF efa570519f08..., prepared page 55ef8e2da6aa...,
  frozen checkpoint 2800866028ff..., unrelated work and recovery stash@{0}
  bb78854e87833124a1725b51f0be6099a8ac0cfa. CV/canvas/compatibility runbooks
  guided pixel identity, reversible additive storage and review preservation.
  This is a scoped local checkpoint, not detector publication or release.
  The existing untracked reset utility's one-line compatibility update remains
  in the workspace; unrelated source/training/catalog work is not committed.
- Next: diagnose remaining wall-outline/wiring ambiguity and lamp-on-corner /
  raceway false positives with identical-source overlays; assess unseen pages
  without tuning before further routing work. Existing circuit save and ceiling
  service/wall-drop preview are unchanged. Under-floor does not imply approved
  underground depth. Overall detection and full wiring goal remain active.

### Whole-sheet drawing-scope diagnostic checkpoint (after 9351e32)

- PASS: reproduced the actual page-7 PDF conversion/normalization path: 150 DPI,
  4500x3000 render, 4096x2731 normalized raster. Frozen power80 checkpoint,
  score threshold 0.50, class IDs, fusion and CPU/window bounds unchanged.
  Original PDF/page/crop hashes verified before inference. No training or
  model activation. Whole-sheet CV selects almost the full sheet, producing
  walls on notes, borders and non-floor diagrams: a verified scope failure.
- PASS: corrected diagnostic pairing of crop-local power targets with whole-
  page lamp/switch targets using exact manifest identities and offsets. The
  initial v1 omitted 16 power targets; preserved unchanged. Corrected v2 has
  45 class/location matches out of 45 checked positives, 98 total proposals,
  48.2815s wall extraction and 5.2014s symbol inference. Precision remains
  unscored because this is partially annotated same-source development data.
- PASS: reusable explicit DrawingRegion core runs unchanged-resolution copied
  pixels and restores all candidate geometry, evidence transforms and raw
  fused/alias boxes and tile origins to the full source plane. Strict integer
  selections, image/box bounds, 200-row/flat-observation limits, warning budget
  and validation fence malformed data. Originals and input payloads stay
  unchanged. Outside selection is explicitly unprocessed, not empty background;
  classes remain unresolved and all proposals require review. Separate views
  are not silently merged as one canonical floor. No page-specific runtime mask.
- PASS: v3 uses the existing assistant-proposed lighting/power rectangles from
  the source preparation manifest, independent of target positions. Same
  PDF/raster/model/settings: 45/45 checked class/location matches, 48 proposals,
  wall extraction 3.1048s and symbol inference 2.5964s. Lighting/power produced
  13/15 wall proposals and 31/17 symbol proposals. All raw candidates and source
  overlays retained under storage/training/whole-pdf-development-20261008-regions-v3.
  Current bounded recovery exactly reproduces its 48 frozen predictions,
  including retained raw observations. This does not establish general accuracy.
- Assistant inspection proposals, not human approval: the three unmatched crops
  show a probable one-gang prediction on S_ab two-gang notation, a wall corner
  mistaken for a fluorescent lamp and a raceway dash mistaken for a lamp.
  Versioned atlas/assessments retain source boxes, hashes and uncertainty in
  the matching regions-v3-inspection-v1 directory. No automatic label edits.
  Notes/legend/border wall proposals disappear with drawing scope, but some
  double-outline and short wiring-associated wall proposals remain. No wall
  completeness, measured precision, independent recall or release claim.
- Verification: focused backend 44 passed / 13 subtests; diagnostic script
  5 passed. Full isolated backend 1149 passed, 4 skipped, 597 subtests and
  5 existing warnings. Compilation and diff checks pass. Initial focused
  invocations used incorrect test paths and ran no tests; corrected and rerun.
  OpenAPI metadata probe initially shadowed the app binding; corrected and rerun.
  OpenAPI remains 36 paths / 44 operations; model tables remain 33.
  No frontend changes in this checkpoint; frontend tests/build/lint not rerun.
- NOT TESTED: live drawing selection, durable job pinning, process/review/save/
  reload, and WebGL rendering. Core is not wired into live worker defaults yet.
  Computer-use inventory still has no browser; no alternate browser bypass.
  Existing 9351e32 circuit workflow and its verification remain unchanged.
- Wiring evidence: source legend distinguishes concealed ceiling raceway
  (solid) from concealed under-floor raceway (dashed). Under-floor is not proof
  of underground burial depth. Supplied 3D screenshots clarify ceiling runs
  and wall drops, not underground rules. No invented measurements or approvals.
- Preserved: originals, prepared page, checkpoint, unrelated edits and recovery
  stash@{0} bb78854e87833124a1725b51f0be6099a8ac0cfa. No DB reset, schema changes
  or production promotion. Scope/coordinate handling follows CV/surgical-patch
  runbooks. Next: durable source/hash-bound drawing selection and development
  review reprocessing using this core; then address remaining class/wall errors
  before extending wiring installation types. Goal remains active.
  This is a local checkpoint, not publication: the diagnostic depends on the
  existing uncommitted power80/fusion workspace. Missing prerequisites fail
  explicitly rather than substituting a different model or inference method.

### Versioned circuit save and mounting checkpoint (after 0ef8e44)

- PASS: explicit save_planning_circuit requests append immutable route versions
  in existing storage. Project/floor locks, current reads and expected route /
  layout versions fence stale writes. Normalized UUID/payload retries return the
  same original record, including after later saves; changed payloads conflict.
  Ownership/Designer checks remain enforced. Preview stays read-only HTTP 200;
  save/retry returns 201 / saved_planning. No schema migration or data reset.
- PASS: development UI saves the preview configuration with an identity retained
  across uncertain network results. GET reload supports legacy and circuit
  versions. Late older saves, replay responses and obsolete-layout callbacks
  cannot downgrade the displayed latest route. Obsolete legacy requests abort
  and suppress callbacks, preserving newer previews. Errors remain visible outside
  closed configuration controls. Existing single-device routing remains usable.
- PASS: explicit circuit target elevations bind to the same saved canonical XY
  in 3D. Stale/project/layout/position/wall mismatches do not bind. Ceiling fixture
  tops meet the entered elevation; wall devices use entered elevations and only
  the specified wall. Unconfigured devices retain labeled illustrative defaults.
  Shared 2D/3D lines use identical persisted backend segments and existing styles.
  Inspector distinguishes saved planning inputs from unsaved preview inputs;
  dimensions, elevations and circuit saving are not engineering approval.
- PASS: saved circuits explicitly block new material takeoff / estimates until
  conductor and circuit material semantics exist. Options expose the blocker,
  generation returns a meaningful 422, and historical estimates remain readable
  and unchanged. Physical shared path length is not a wire/conductor quantity.
- Verification: focused backend 46 passed; focused frontend 53 passed. Full
  isolated backend 1140 passed, 4 skipped, 589 subtests, 5 existing warnings.
  Full frontend 56 files / 484 passed; Vite build and scoped lint pass.
  Compilation and diff checks pass. OpenAPI remains 36 paths / 44 operations;
  model tables remain 33. Review found a late-save downgrade; fixed and tested.
- NOT TESTED: live browser process/review/save/reload and actual WebGL visual
  placement. Connected-surface inventory is empty; opening the existing local
  preview binding is unavailable. Component/API results are not browser proof.
  Manual gate: reconnect localhost:5173 as Designer, retry the existing supplied
  upload 9382 without duplicating it, inspect/correct detections and save review;
  use saved 2D/3D after required scale/wall inputs are reviewed. Configure named
  circuit devices, explicit panel/service/device elevations and wall attachments;
  preview, compare 2D, save planning circuit, reload and inspect stored elevations.
  Compare saved 2D/3D and roof visibility; capture actual renders and failures.
- FAIL outside scope: full lint retains six existing errors in unrelated,
  untracked DeviceMeshCatalog. Large build chunks remain a warning. Originals,
  supplied source PDF/page hashes, trained checkpoint, unrelated work and
  stash@{0} bb78854e87833124a1725b51f0be6099a8ac0cfa remain preserved.
- Remaining: detection completeness / cross-source validation, live repaired
  job retry and review persistence, circuit conductor/material semantics,
  wall-only / underground routing rules and verified depth/obstacle inputs.
  No global optimality, independent detection accuracy or release claim.
  Next: inspect existing wiring legend metadata and bound installation-method
  planning without interpreting unknown glyphs as underground approval.

### Shared-circuit preview checkpoint (after b10e28d)

- PASS: one explicit circuit can preview 1–32 saved target devices on a shared,
  bounded service-plane graph. Greedy nearest-tree attachment reuses trunks;
  overlapping wall drops split at supplied elevations and count physical spans
  once. Per-device path lengths remain separate. No inferred class, membership,
  panel association, height or installation approval. No global optimum claim.
- PASS: existing route POST also accepts explicit circuit-preview requests;
  preview returns HTTP 200 / preview_not_saved without creating a route version,
  replacing the saved route or changing material/estimate quantities. Legacy
  single-target create/reload remains unchanged. Designer/owner checks apply;
  current locking reads reject a layout changed during planning, including under
  MySQL REPEATABLE READ. OpenAPI remains 36 paths / 44 operations; 33 tables.
- PASS: shared-circuit controls in saved 3D accept named canonical devices and
  explicit installation/elevation/wall inputs. Existing 3D lines and the reusable
  Konva 2D comparison consume the same projected backend segments. Edits, discard,
  reload and aborted/unmounted requests remove or fence obsolete previews. UI
  runbook informed labeled inputs, focused errors and explicit preview-only state.
- PASS: routing refactor baseline 12/12 before and after graph extraction;
  focused routing/API 26 tests; frontend preview/routing/viewer 25 tests.
  Fresh full isolated backend 1128 passed, 4 skipped, 589 subtests, 5 warnings;
  full frontend 55 files / 470 tests; Vite build, compilation, scoped lint and
  diff checks pass. Existing large-chunk warning remains. Independent review
  found overlap accounting and stale-read issues; both fixed and regression-tested.
- FAIL outside scope: full lint retains 6 pre-existing errors in the unrelated,
  untracked DeviceMeshCatalog. BLOCKED live browser proof: no connected surfaces.
  API/component tests are not screenshots or real-device interaction evidence.
- Remaining: versioned circuit persistence and circuit/material semantics;
  saved installation metadata to synchronize actual device mounting with route
  elevations; underfloor/underground rules and inputs; live process/review/save/
  reload proof. Preview is ceiling/service only, not release/design approval.
- Preservation: scoped local wall b8161be and source preparation b10e28d;
  originals, dataset/checkpoint files, unrelated edits and recovery stash retained.

### October 8 wall/source-preparation verification checkpoint

- PASS: outlined-wall recovery now extends fitted, qualified bands only. Faint
  paired tails and bracketed one-outline scan dropouts recover without changing
  Hough inputs, seeding wires/panel rules or bridging actual two-edge openings.
  The rejected pre-Hough variant remains in ignored v1 development evidence.
- PASS: v2 supplied-power probe retains 16/16 inspected class/location matches
  at native and 0.375 scale; zero proposals in 14 inspected negative patches.
  Native wall count remains 13; small count remains 10. Unrelated fitted walls
  are preserved. This is source-retention evidence, not measured precision or
  independent accuracy. Original PDF/page hashes and model checkpoint unchanged.
- PASS: job 24194 source-preparation failure traced to an unregistered old image
  at a reused job ID. New preparations use unique interpretation-runs namespaces;
  trusted registered artifacts still require integrity checks. Regression proves
  old pixels remain unchanged and are neither overwritten nor adopted. A real
  two-page PDF check also proves distinct page identities, preservation of old
  render/normalized files and reuse of registered output without reprocessing.
- PASS: focused wall/demo 72 tests + 69 subtests; fresh isolated backend full
  regression 1117 passed, 4 skipped, 589 subtests, 5 existing deprecation warnings.
  Worker/PDF focused checks after the added PDF regression: 30 passed (one
  initial test assertion used page_number instead of floor_plan_page_id; fixed).
  Compilation and diff checks pass. Frontend checkpoint is cfd3f4b on
  codex/vlm-localization-experiment; recovery stash unchanged.
- NOT TESTED: browser retry/review/save/reload after source repair; no connected
  browser surface. Downscaled cavity loss and ambiguous wiring-overlaid junctions
  remain unresolved. Full lint retains 6 unrelated DeviceMeshCatalog errors.
- Next: authoritative circuit/panel/device installation inputs, bounded shared
  network planning, then browser/2D/3D proof. No invented heights, underground
  classification, optimality, approval or general detection-readiness claim.

### October 8 shared wiring visualization checkpoint

- PASS: saved canonical wiring now reaches 3D with exact stored elevations and
  validated observed/generated provenance. Unknown installation methods remain
  unresolved; cross-floor edges are omitted without invented transforms. Both
  views share generated ceiling/service orange, muted dashed wall drops/rises,
  and riser styling. Geometry, routing measurements and approval rules unchanged.
- PASS: focused frontend 54 tests; full frontend 53 files / 459 tests; Vite
  build and scoped lint. Existing large-chunk warning remains. Full-repository
  lint still has unrelated DeviceMeshCatalog issues recorded below.
- BLOCKED browser proof: connected Designer account and manual power upload
  9382 were observed, but browser connection disappeared after interruption.
  Reconnect the preview for process/review/save/reload and rendered 3D checks.
  Source screenshots establish ceiling runs/drops, not underground routing.
- Remaining: wall-completeness repairs/source checks; reviewed device/panel
  elevations and circuit associations; explicit installation-method metadata;
  multi-target/shared-segment routing and underfloor/underground planning.
  No general detection accuracy, optimal circuit network or release claim.

### October 7 native-context refinement and development integration

- Cropped negative examples did not reproduce the native-tile column error
  (<.166 outlet score versus .916 in context). Frozen native-context v9 removed
  it but lost one outlet; v10 and ridge64 v11 retained the outlet but kept the
  false column. All failed artifacts are retained and inactive.
- Ridge16 v12 changes only the class58 output row: 81 scalars changed within
  the 243-scalar allowance; backbone, BN, box heads and other 79 class rows
  are byte-exact before save and after serialized reload. 29 dependent native
  windows / 54,810,000 cache bytes; 93 positive and eight inspected negative
  anchors; unknown pixels ignored. No new architecture, model download or
  inference-threshold change. Checkpoint SHA
  `2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa`;
  refinement manifest `b409bef77ca1...`, training manifest `286ebf9ec56f...`.
- PASS development source checks at native and .375 scale: **12/12 outlets,
  1/1 panelboard, 3/3 real LP homeruns**, zero proposals in all **15** inspected
  non-device patches (including the hatched column). The real homeruns must not
  be blanket-suppressed. Original 23-page retention **806/830**, 1,473 proposals,
  no caps, unchanged from run4; switches **3/4, 9/9, 9/9**, PDF lamps **20/20**.
  Matching remains class-aware one-to-one IoU >=.50, score threshold .50.
  These tuned/source-dependent checks do not establish full-page precision or
  independent accuracy; both remain unscored. No 85% or production claim.
- `power80` v12 is the experimental development default; configured gateway
  and production release selection remain unchanged. Old `lamps80`/`original56`
  rollback artifacts and fingerprints are retained. Compact serving manifest
  `7182de3a9b86...` decodes exactly to the training manifest; an older differing
  compact file was preserved and not used. All four artifact pins verified;
  independent read-only agent found no integration blocker. New provenance
  records refinement identity in the strict ordered inference-parameter tuple;
  raw candidates and old review revisions are unchanged.
- PASS: focused isolated worker/candidate/review/refinement **58 tests / 48
  subtests**, recovery/configuration **63 tests / 38 subtests**, and dedicated
  current/stale-worker cases **10 tests**. Final full isolated backend after
  recovery and failure-fence fixes **1,113 tests / 585 subtests**, four
  skips, five existing warnings; script diagnostic/preparation/probe **57 tests**;
  full frontend **52 files / 450 tests**, Vite build, compilation and diff checks.
  Full lint remains FAIL on the unrelated existing `DeviceMeshCatalog.jsx`.
- Browser job 24188 on existing upload 9377 was interrupted by backend hot
  reload. Natural lease recovery exposed a missing ORM flush between requeue
  and page selection (autoflush is disabled); recovery exhausted retries with
  `PROCESSING_PAGE_SELECTION_REQUIRED`. Added RED reproduction and explicit
  flush; fresh job **24189** recovered its expired first lease automatically
  and completed on attempt 2. It actually loaded **power80 / 80 classes / v12**
  with the pinned refinement, persisted 29 named proposals and valid candidate
  hash. Not a mock inference or uploaded power-panel browser accuracy claim.
- Independent review additionally identified stale failure writes bypassing
  the page-state fence. RED generic-error/timeout tests reproduced overwriting
  the successor's completed page. Failure handling now locks job, attempt and
  page, requires the active unexpired owned lease, and atomically commits page
  outcome with attempt acknowledgment. Stale generic/timeout/cancel paths
  preserve successor page, candidate and attempts; live failure/timeout retries
  and cooperative cancellation pass. Read-only reviewer found no remaining
  boundary blocker. No lease stealing, role bypass or database reset.
- Designer computer-use PASS: exact L02 trained legend mapping stays unresolved
  until a separate correction decision; symbol-0004 corrected to (620,268),
  catalog class161 / legend1782. Unfinished revision1 saved and reload retains
  name, mapping, state, position and explicitly assistant-authored note.
  Remove -> Reject -> Undo and Add -> unresolved -> Undo verified without
  saving temporary edits. Read-only database confirms revision1 hash and
  completeness/approval false, original SHA `e9f091252f66...` unchanged;
  old job24187 revision1 remains intact. Browser proof:
  `storage/previews/browser-verification-20261007/designer-power80-job24189-reloaded.png`.
- **Not all verification finished:** exact supplied power-panel browser upload
  was declined, with no bypass. Requested manual upload of the existing prepared
  `pdf-source-20261004-efa570519f08-v3/power-layout.png` to project10218/basement;
  then verify its 12 outlets, panelboard, three real LPs and removal of both
  false outside frame walls through the actual browser review/save flow.
  3D remains BLOCKED by preview WebGL and missing reviewed scale/elevation/
  geometry; draft saving needs none of those approvals. Wall-model research
  and deterministic frame regression are complete below; no trained wall-model
  or general precision claim. Branch HEAD `85448ef`, task edits uncommitted;
  unrelated changes and recovery stash remain preserved. No new epic started.

### October 7 resumed Designer verification and bounded column experiment

- Connected computer-use preview confirms the user-selected **DESIGNER** session.
  Keyboard activation works in the preview; the prior click-only failure is not
  an application authorization bypass. Reused upload 9377 in project 10218 /
  floor 6323; job **24187** completed using the unchanged `lamps80` default.
  Named lamp/switch proposals are visible. Unfinished revision **1** saved a
  lamp legend link, rounded source position (620,104), and corrected state with
  an explicit assistant diagnostic note; browser reload preserved all three and
  the note. Remove -> Reject -> Undo and Add -> unresolved -> Undo worked;
  temporary edits were discarded, leaving saved revision 1 only. Browser proof:
  `storage/previews/browser-verification-20261007/designer-draft-reloaded.png`.
  No completeness, scale/elevation, canonical or production approval recorded.
  Read-only database verification confirms exactly revision 1 with completeness
  and approval false; original upload SHA `e9f091252f66...` matches its frozen
  training derivative. Fresh OpenAPI **44** operations / ORM metadata **33**
  tables, not a live database row-count claim.
  Draft 3D reached the viewer but this connected preview cannot create WebGL;
  rendered 3D is BLOCKED here. Reviewed scale/elevation/geometry are also missing
  for canonical approval. Neither limitation blocks proposal/draft review.
- Run4 terminal success and guarded seam/box fusion checks: native and .375
  power views **16/16** class-and-location matches, **0** proposals in the 14
  previously inspected negative patches. Native still has one false outlet on
  a hatched column; it is not a passing full-page precision result. Switch
  checks **3/4, 9/9, 9/9**; both lamp checks **20/20**. Original 23-page replay
  **806/830**, 1,473 proposals, no capped pages versus a fresh unchanged default
  **800/830**, 2,787 proposals, one cap. All are dependent development evidence;
  partial-page precision and independent accuracy remain unscored.
- `power80` remains opt-in, pinned to run4 SHA
  `d68595066681238fa3cfaf612a1e3f30a9b5232b1ed343bf93ced9da43b49477`;
  compact serving manifest SHA
  `1a328b6fa391ea2cb22d8ebe32d9f96ab4b071e4fd490985b16a4f1b69432ab1`
  decodes identically to training manifest `cbea19db...`. Legacy rollback
  fingerprints/alias formatting remain unchanged. Power-only score warnings
  retain raw localization/alias evidence within strict candidate bounds.
- Small same-class clipped fragments are suppressed only with complete seam
  evidence and fragment/complete area >= .25; distinct classes and tiny adjacent
  observations are retained. Same-class indexing reduces comparison work, not
  measured model inference time. PIL success/failure cleanup and bounded cache
  confirmed by the memory reviewer; no demonstrated accumulating leak.
- Append-only column inspection v2 adds one wholly inspected non-device patch,
  no positive relabeling, no human-review claim. `column-v5` manifest SHA
  `286ebf9ec56ffda32d39f73d04f65058c2bad9e99544de6fcc26c4005ffc5470`:
  all **11,075** parent files byte-identical, **80** mappings, **16** prior power
  positives and **2,044** positive windows retained. **27** translated/resized
  negative views use inspected pixels plus known-white padding only. Totals:
  **547** negative windows / **15** inspected power negative regions. Before
  training, the column check reproduces **1 native / 0 small** false proposals.
  One CPU epoch `power-quality-20261007-run5` completed (exit 0), checkpoint SHA
  `9ef7f41096ec560fcccd96490ed13a9d23547ccad18ffe7011829a38dc595962`.
  **FAIL quality / inactive:** 16/16 power matches at both scales, but column
  false outlet remains (1 native / 0 small), and two small-scale grid bubbles
  become false homeruns in the old inspected negatives. Switch checks 3/4,
  9/9, 9/9 and PDF lamps 20/20 do not override those failures. Run4 stays pinned;
  unchanged `lamps80` remains default. No larger run/model/download/promotion.
- Fresh focused PASS: detector/profile/account selection **39 tests / 21
  subtests**; preparation/probe **40 tests**, plus source/sampling/hash validators.
  Fresh full isolated backend **1,097 passed / 558 subtests / 4 skipped / 5
  existing warnings**; full frontend **52 files / 450 tests**; Vite build,
  compilation and diff checks PASS. Full lint FAIL: six pre-existing errors in
  unrelated untracked `DeviceMeshCatalog.jsx` (unused React, mixed exports and
  conditional hooks), not changed to hide failures. Existing large-bundle warning
  remains. Explicit `power80` isolated worker/candidate/review/save integration
  **46 passed / 11 subtests**, with restricted empty verification database and
  temporary storage. Branch/HEAD and recovery stash unchanged;
  task changes are uncommitted, unrelated work preserved.

### October 7 frozen classifier/context diagnostic (not activated)

- Designer preview reconfirmed; existing job 24187 revision 1 reloads the named
  DepED L02 lamp, corrected decision and (620,104) position. New power-panel
  browser upload was declined by the browser's permission control; no alternate
  upload/session bypass attempted. Existing upload and draft remain usable.
- Preparation ancestry defect fixed: immediate parent manifest is archived by
  exact hash before extending history. Added missing `cbea19db...` archive to
  column-v5 after run5; manifest `286ebf9e...`, labels and original bytes unchanged.
  Fresh preparation/frozen-probe proof: **41 tests PASS**.
- Independent agent evidence: run5 changed 415/499 state entries, 162 BN
  buffers, 155 box-head entries and every class row. The 27 new column crops
  were only 0.486% of 5,556 shuffled training images. Dilution is a hypothesis,
  not proof of the entire failure mechanism; no reliable shape-only guard found.
- Narrow offline tool `repair_symbol_class_tail.py`: only 243 class58 output
  scalars train; backbone, BN, boxes and the other 79 rows remain exact. Checks
  all 499 state entries before save and after serialized reload. No optimizer
  resume, profile edits, production approval or unknown-region background labels.
  New optional loss masks rank at most 32 anchors inside explicit inspected
  rectangles; dimensions, finite values, class and image bounds fail closed.
- Cropped-negative v8: 100 steps, 59 dependent windows, 111,510,000 cache bytes;
  checkpoint `0f3fee40...`. **FAIL:** column remains. Exact training crops gave
  maximum raw outlet scores <0.166 whereas native tile (896,704) gave 0.916.
  Cropping/white-padding context therefore failed to reproduce the actual error.
- Native-context v9: nine exact source tiles + 32 old positive controls, 100
  steps, 77,490,000 cache bytes; checkpoint `51c91633...`. **FAIL / inactive:**
  column removed, but native matches fall to 15/16 (11/12 outlets); small 16/16.
  Original annotation coordinates and source images are never altered.
- Native-control v10: 29 source tiles, geometry-selected best-two contained
  views of each of 12 reviewed outlets plus inspected negative intersections;
  100 steps, 54,810,000 cache bytes. Teacher-logit preservation applies only to
  known positives with baseline class score >=.5 and source-box IoU >=.5.
  All other pixels remain ignored. Exact crop/PDF identities exclude foreign
  records. Checkpoint `176b51128bdd122c529a9934d7778a7add0cc46aaf47e86f2720da1094af3388`;
  original power check 16/16 both scales, old 14 negative regions zero. Separate
  column check found one native false outlet; v10 remains inactive. No
  independent-accuracy claim; successful later v12 is recorded above.
- Fresh **19 repair/native-context tests PASS** and full isolated backend
  **1,097 passed / 558 subtests / 4 skipped / 5 existing warnings** after loss-mask
  changes. Earlier frontend 450 tests/build remain recorded above (no new
  frontend edits). Full lint still FAIL on unrelated DeviceMeshCatalog.jsx.
  All scoped work remains uncommitted; unrelated edits and stash unchanged.

### October 7 account-selection fix

- During account switching, OAuth login now explicitly
  requests `prompt=select_account`; the sign-in page offers **Switch account**
  through the existing local logout. Valid session restoration, OAuth
  state/nonce validation, role checks, account records and datasets are unchanged.
- PASS: isolated authorization/account-selection checks 15 tests / 2 subtests;
  focused sign-in/sidebar/route tests 14; scoped ESLint, Vite build and diff check.
  Existing large-chunk/build-plugin and test-library deprecation warnings remain.
  Full regressions were not rerun for this narrow change.
- Restarted only the verified local backend, with reload and access logs off
  (avoid recording OAuth callback codes). Live redirect requests account selection.
  Computer-use preview shows Google's **Choose an account**; left open for the
  user to choose **Use another account**. Direct supported login navigation was
  verified; the preview's Sign in click did not navigate and is not claimed PASS.
  Designer sign-in is now confirmed; subsequent draft checks are recorded above. Recovery stash
  and unrelated changes preserved; this fix is uncommitted.

### October 6 detection-quality cluster checkpoint (in progress)

- User-prioritized detection repair, not global VS Code settings. Three
  GPT-6.1 Sol/medium agents handled unit tests, read-only memory review and
  wall-detector implementation; root reconciles training and integration.
  Branch `codex/vlm-localization-experiment`, original HEAD `85448ef`; unrelated
  edits and recovery stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` preserved.
- Exact screenshot source: authorized `MULTI-PURPOSE_DepED.pdf`, SHA
  `efa570519f08bc3596d443fcc63c96ddd6bf73039bcba7ed3e52881d0943d9af`, page 7,
  prepared power-panel SHA
  `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`.
  Source inspection proposes 12 duplex outlets, one panelboard and three actual
  LP-3/LP-4/LP-5 homeruns; grid letters/numbers are not homeruns. Sixteen
  assistant-inspected targets and 14 wholly non-device patches retain source
  legend aliases, delegated development provenance and no human-review claim.
  Original files, previous annotations and frozen before-results are unchanged.
- First bounded full-80-class replay (`power-quality-20261006-v1`, manifest
  `5245bca2f82ec6c2d84cbaf2ac28c23f88ae55c53a69ad9763882bf09b441924`): 576
  dependent positive views, 42 dependent negative views, all original mappings
  and prior replay retained. Two CPU epochs finished successfully; last weight
  SHA `a8888c27e4ff4231f11a22ccb5fde33b685cc63f3b1dd08fa2526ba42101b03e`.
  Frozen full-panel checks at score .50 / one-to-one class-aware IoU .50:
  native 7/16 -> 16/16, upload-like .375 scale 0/16 -> 13/16; outlets 7/12 ->
  12/12 and 0/12 -> 12/12 respectively. Inspected-negative proposals 6 -> 5
  and 2 -> 1: false grid/wire interpretations still exist. These are same-source
  development measurements, not independent accuracy or full-page precision.
  Switch retention checks: 3/4 on the other PDF, 9/9 related PDF, 8/9 derivative.
  First candidate remains inactive pending the bounded follow-up and retention.
- Follow-up completed: `power-quality-20261006-negative-v2` adds 336
  dependent phase-shift views of the same inspected negatives, with known-white
  padding only. This addresses centered training patches versus shifted
  inference tiles; it does not add independent data or label unknown space as
  background. `power-quality-20261006-run2`: two bounded CPU epochs finished;
  last SHA `4629d89fd250eb499254d27c4d6dce97d10206b6462cba828168270b412808ce`.
  Native 16/16 and .375 scale 15/16, both 12/12 outlets, but inspected-negative
  proposals 3 native / 4 small. Small-scale false matches worsened: candidate
  fails that gate and is not activated. Same architecture/head/threshold; no
  download/cloud. Original-23-page retention probe is preserved separately.
- Diagnosis: uniform background weights divide a fixed 32-anchor loss budget
  across 2,100 anchors at 320 input pixels, diluting the strongest four wrong
  anchors to about .061 total weight. Optional `top_score_anchors` now focuses
  the same budget on detached highest class logits only on explicitly wholly
  inspected negative images. Unknown/positive-region masks and legacy uniform
  fallback unchanged; no new architecture. Independent reviewer and gradient
  regressions pass. `power-quality-20261006-hard-v3` opts in; run3 is one bounded
  epoch from the exact run1 base SHA with a fresh optimizer, not a bypass of the
  same-dataset warm-start guard. Native/small-scale and retention gates pending.
- October 7 continuation: run3 finished, last SHA
  `4b4939c679ad0c54e0e882cc7176443987c4fc821410be6c08b112d4be71d70d`.
  Frozen native and .375 checks both 16/16 (12 outlets, one panel, three actual
  homeruns); proposals inside the 14 inspected negative patches both zero.
  Visual review still finds one extra native outlet on a hatched column outside
  those patches. Full-page precision remains unscored. Original pre-fusion
  retention 807/830, no capped pages; lamps 20/20 in both related views.
  Switch retention failed: other PDF 3/4 -> 2/4, derivative 8/9 -> 7/9 (related
  PDF remains 9/9). A correct high-score box shrank below IoU .50; another small
  switch disappeared at the frozen threshold. Do not call run3 a passing
  replacement. Default remains `lamps80`; `power80` is experimental opt-in.
  Compact serving manifest is decoded-identical to the original training
  manifest; serving SHA `b32a8d1c54412de717578f28454705dce2befd31bc51ac09baf05e8ff67f6d15`,
  training SHA `384ffd6a4c1b7f375cd543c1fc2c90d4be3a3349e39c199a8a50e77da09d2f06`.
  Both are pinned separately; no dataset or image/memory bound increase.
- Bounded switch repair: `power-quality-20261006-retained-v4b`, SHA
  `cbea19db3e4941a3d3222c7e5378b3f09aaa10bc0c91912714aff8c1f8f715bb`,
  copies 594 exact existing switch train windows; original labels, source
  aliases, previous restorative metadata and all 80 head identities remain.
  Copies are dependent, not new independent data. Partial unknown masks and
  inspected negative sampling unchanged. Initial `retained-v4` failed the
  source-artifact validator and is preserved, never trained; the corrected v4b
  passed preparation. One bounded CPU epoch `power-quality-20261007-run4`
  completed; fresh guarded-fusion power/switch/lamp/original checks are recorded
  above. One native column false positive remains, so the default is unchanged.
- Post-mining full isolated backend: 1,080 passed / 545 subtests, four skips.
  Post-profile regression exposed an unordered provenance-parameter failure
  (1 failed, 1,083 passed); fixed at the worker construction boundary, preserving
  strict ordering validation. Fresh isolated `power80` worker/detector check:
  23 passed / 11 subtests. Replay/probe scripts now 22 + 10 tests passed,
  including copied positive bytes and bounded hash-addressed multi-hop ancestry.
  Unit and memory agents reached service usage limits during the final follow-up;
  earlier completed contributions are retained, remaining checks done by root.
- Wall fix uses opposing detached outline bands surrounding a wall network
  with perpendicular junction evidence, not page-specific coordinates. Exactly
  two false outer-frame walls removed: native 15 -> 13, .375 scale 12 -> 10;
  remaining coordinates/order unchanged. Isolated walls, connected perimeters,
  scale/rotation and doorway regressions pass. This is deterministic CV, not a
  trained wall model; truly detached enclosing walls can remain ambiguous.
- Replay/probe tooling now preserves append-only structured revisions and
  hash-addressed inspection artifacts, rejects changed source/PDF/permission,
  validates exact frozen comparison lineage and preserves distinct adjacent
  outlets. Unknown partial-page regions remain ignored; precision unscored.
  Memory review found no demonstrated accumulating leak; explicit PIL cleanup
  now runs on success and inference failure (native PIL context alone was
  insufficient). Model cache remains one; batches eight; existing bounds intact.
- Fresh PASS: isolated focused backend 163 tests / 115 subtests; isolated full
  backend 1,074 tests / 531 subtests (four skips, five existing deprecation
  warnings; before the optional mining change); replay/probe scripts 27 tests;
  mining/cleanup focused 18 tests / 16 subtests and isolated inference/review
  integration 49 tests / 22 subtests; full frontend 51 files / 444 tests;
  build (existing large-chunk warning). FAIL: frontend lint in unrelated,
  pre-existing untracked `DeviceMeshCatalog.jsx` (unused React, mixed exports,
  conditional hooks); not changed to hide failures. Computer-use verification
  previously reached protected sign-in only. The later authenticated Designer
  workflow checks are recorded above; canonical 2D/3D remains unverified without
  actual reviewed scale/elevation and geometry.
  OpenAPI 44 operations / ORM metadata 33 tables; no API/schema mutation.
- Trainable walls are feasible with explicit wall polygons/centerlines,
  openings and wire/drafting negatives, preserving ignored unknown regions and
  project-separated evaluation. Existing combined export contains 476 geometry
  records (including 268 standard-wall and 85 opening labels), not proof of
  complete wall masks. [CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k) offers
  multitask polygon/junction training, but its
  [CC BY-NC 4.0 license](https://raw.githubusercontent.com/CubiCasa/CubiCasa5k/master/LICENSE)
  cannot be assumed suitable for commercial VED use.
  [GLSP](https://arxiv.org/abs/2303.03851) combines junction/semantic-line
  prediction, not evidence of Philippine wiring-layout accuracy. No wall model
  downloaded or trained; independent data, production training/approval and
  release gates remain separate.

### October 6 main synchronization checkpoint

- Selected source: `codex/verified-progress-20261006` at `24d1f1f`, integrating
  only verified PDF intake/public-source inspection, hollow-wall/wiring evidence
  and their tests/progress records. Non-fast-forward merge into `main` from
  `fae4a7c`; no unrelated implementation work included.
- PASS fresh merged-tree verification: 16 intake, 54 wall, 30 coordinate,
  12 demo-CV and 37 preprocessing tests (148 passed, one existing Windows
  symlink capability skip), compilation and scoped diff checks. Expected
  malformed-image OpenCV diagnostics only. Full database/backend/frontend/
  browser and independent real-drawing accuracy/release checks NOT RUN.
- Original implementation worktree/branch and pending training, detector,
  catalog, UI, database tools and planning edits retained locally. Recovery stash
  `bb78854e87833124a1725b51f0be6099a8ac0cfa` untouched. No data reset, deletion,
  credential change, private-artifact upload, model activation or deployment.
  API/schema/dependencies unchanged; OpenAPI/table counts not re-run.


### October 6 Git publication and retention checkpoint

- PASS remote publication: intake `acf661f`, hollow-wall fix `ba70005` pushed
  to `origin/codex/verified-progress-20261006`; remote branch hash verified.
  Built/tested from clean `origin/main` baseline `fae4a7c`, not from pending
  detector/UI/database edits. Main remains `fae4a7c`; no merge or deployment.
- Retention audit: 94 original changed/untracked/deleted path entries checked;
  92 byte/status-identical, two intentional changes (this ledger and the existing
  PDF preparation test module's standalone intake coverage/import correction).
  No unrelated edit, deletion, original drawing or training artifact discarded.
  Recovery stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` unchanged.
- Verification: 148 passed / one existing Windows symlink skip; focused only.
  Clean publication worktree, compilation/diff checks PASS; full database,
  frontend/browser and independent quality/release checks NOT RUN.
- Next: reconcile/verify pending runtime, legend/catalog, UI and PEC-training
  changes before any further publication. Original implementation branch
  `codex/vlm-localization-experiment` remains at `85448ef` with its WIP retained.
  Private source PDFs, annotations, datasets/results, weights and secrets remain
  local/Git-ignored. Publication does not activate the experimental 129-ID model.


### October 6 selected publication — hollow-wall evidence

- Scope: structural wall detection recognizes persistent paired outlines with
  a white cavity and evidence in both principal directions, rather than
  mistaking one filled circuit stroke for two wall edges. Broad solid/hatched
  structure retained; endpoint recovery and deduplication follow qualified
  observed wall ink and do not bridge white door openings. No page-specific
  coordinates, new class mappings or canonical geometry contract changes.
- PASS in the clean publication worktree: 54 wall detection tests (including
  scaled/rotated hollow walls, bolder connected circuits, neighboring circuits,
  door openings, solid structure and sanitized OpenCV failures), 30 coordinate
  tests, 12 unchanged demo-CV tests, 37 preprocessing tests with one existing
  Windows file-symlink capability skip. Thus 132 passed / one skipped for this
  checkpoint; combined with intake: 148 passed / one skipped. Compilation and
  scoped diff checks PASS. Malformed-image OpenCV messages are expected tests;
  LF/CRLF Git warnings remain. No failed required focused check remains.
- NOT RUN: full database-backed regression, frontend/browser workflow or
  independent real-drawing wall accuracy. These focused checks do not prove
  general detection or release readiness. API/database schema unchanged here;
  OpenAPI/table totals not re-counted. No model activation/training/download.
- Prior intake commit: `acf661f`. Pending runtime/catalog/UI/account-reset/PEC-
  training changes
  remain in the original workspace; no blind stash application or deletion.


### October 6 selected publication — electrical PDF intake

- Scope: bounded official-Philippine PDF discovery, explicit electrical-page
  inspection/legend-panel proposals, source-authorized PDF preparation and
  standalone regression coverage. Exact source hashes, one-based page identity,
  reversible rendered-page coordinates and immutable revisions preserved.
  Public accessibility/PEC notes do NOT establish training rights or certification;
  reference proposals do NOT become reviewed labels or training-ready pages.
- PASS: 16 focused intake tests against a separate worktree based on
  `origin/main` (`fae4a7c`), not the dirty implementation workspace; compilation
  and scoped diff checks. Decoupled discovery/selection tests from pending PEC
  learning helpers by including them in the existing PDF preparation test module.
  Initial extracted tests missed a TemporaryDirectory import; fixed and rerun
  all 16 successfully. No application/route/database/dependency changes.
- Publication branch: `codex/verified-progress-20261006`. Private PDFs, images,
  authorization records, training manifests/results, weights and credentials
  remain local and Git-ignored. Recovery stash remains untouched.
- Retained, NOT included in this checkpoint: pending detector/class/catalog/UI
  integration, database-repair/account-reset tools, unrelated planning changes
  and documentation deletion, and PEC training/diagnostic tooling. The local
  129-ID replay retains all 56 original mappings and reports 800/830 reviewed
  training-source matches, 29/29 dependent upload targets and 59/62 native
  reference glyphs; these are not independent accuracy or activation approval.
  Full application/database/frontend/browser/release acceptance NOT established
  by this intake checkpoint.


### October 6 bounded original-page retention replay

- **PASS preparation:** new immutable `pec-replay-20261005-v3`, manifest SHA256
  `44ccde85ff0470c462b2d2080bc5240817a49d53bac61aa82309dee290457099`.
  Source-family filenames retain the October 5 lineage; this checkpoint is
  October 6. **1,052 windows**: 117 additional native original-page views cover
  all **71** prior-correct/context-run1-missed targets; 69 hash-selected reference
  views preserve at least two complete views for each of 62 reference variants.
  The 179 omitted repeated reference views remain intact in frozen parent v2;
  no original/source/annotation or prior dataset file deleted or rewritten.
  All original 80 numeric IDs and 54 requested device meanings preserved in
  the 129-ID head, minimum four supervised windows/class. Original reviewed
  targets/neighbor labels unchanged; clipped/unknown regions ignored, no new
  independent examples or complete-page/production approval claimed.
- **PASS source/coordinate safeguards:** only exact user-attested original page
  hashes, existing source boxes and native inference-grid positions admitted.
  Explicit one-based image-page identity, reversible source/local transforms,
  full neighbor provenance and inherited authorization. At most two native
  views per focus target, 200 additional windows/1,200 total, unchanged 60 MP /
  10,000-pixel source bounds. All 71 focus targets covered; no box was resized
  to fit or relabeled. Groups 1-6 remain related training data; no new scored
  project-separated split. Public-agency sources remain training-excluded.
- **PASS byte-integrity fix:** all-class replay training now refuses altered
  image/label bytes, missing/extra files, symlinks and incorrect per-class counts
  before model loading/output creation. Scope restricted to the frozen 129-ID
  development replay; legacy namespace guard unchanged. Actual v3 inventory
  verified. This run began before that new trainer preflight was added; its
  inputs were verified during preparation and independently checked again,
  not falsely reported as having executed the new preflight inside training.
- **PASS bounded local execution:** initialized from context run1 (735/830 old
  retention), not context run2 (714/830), with explicit new-dataset initialization
  and optimizer reset. Existing CPU architecture/batch 8/input 320; four epochs,
  AdamW 0.0001, classification loss 0.53095 -> 0.40603, CSV elapsed 301.908 s.
  Terminal exit 0; checkpoint SHA256
  `9db51821e97b9c2100f7efc6ab24dd2ac668935092647334cac30eedb23720cd`.
  Trainer validation still uses training images; its mAP is NOT independent
  accuracy or permission to activate.
- **PASS bounded execution / NOT accepted quality:** both serial probes exited
  0. Frozen score 0.50, maximum one-to-one IoU >= 0.50/shared tiler unchanged:
  **800/830** class+location, **806/830** location, **1,448** proposals, zero
  truncated pages across 23 original training-source pages. Context run1 was
  735/830; current 80-ID parent is 802/830 and 806/830 location. Aggregate
  retention recovered substantially but remains two matches below the parent;
  no invented tolerance, held-out accuracy or release PASS. Dependent upload:
  **29/29**, including **20/20 lamps and 9/9 switches**, 29 proposals, no cap.
  Requested-reference synthetic checks **246/248**, native reference tables
  **59/62**. Original-source report SHA256
  `77e882bad3cf2e2811df185d5dcffa1dec3aa21ca7e3298164d2e5ae3f84c658`;
  reference/upload report
  `9542124e6144fac6004b0a183af26287bda66533ef9fc3d9ab4255a6278e1363`.
- **PASS per-entry evidence:** immutable
  `pec-replay-20261005-retention-entry-report-v1.json`, SHA256
  `0191a25da848e367faab3347e934d52772a2e838af0c7381604f1579324486b3`,
  reports all original 56 mappings, all 129 model IDs, 54 device references and
  12 wiring references individually. Window counts are dependent supervision,
  not independent examples; proposal counts are not confirmed devices. Report
  generation initially rejected class 53 (19 class-aware versus 17 location
  matches). Fixed the report's incorrect per-class nesting assumption: separate
  maximum matchings allocate overlapping targets differently. No frozen probe
  rewritten or metric changed; source outcomes, global totals and identities
  now independently verified, with a known-answer overlapping-target test.
- **PASS bounded miss diagnosis / remaining limitations:** all three native
  reference misses inspected against source pixels and training composites.
  Special-purpose outlet 1.20.15: native correct score 0.0264 vs composite
  0.9998; antenna 1.20.17: 0.4381 vs 0.9337; automatic-door switch 1.21.8:
  0.1902 vs 0.7892, isolated glyph confused with key-operated switch (0.4981).
  Raw threshold 0.01 is observational only; scored/live threshold stays 0.50.
  Diagnosis saved in `...-retention-reference-diagnostic-v1/report.json` with
  nine paired inputs and overlays; this is source/context dependence, not
  evidence that definitions generalize to new drawings. Synthetic misses are
  one single-pole and one duplex-switch example. Visually inspected both table
  overlays, upload overlay and two original floor-plan overlays. Text/furniture
  also attract proposals; precision remains unscored on partial annotations.
  Assistant inspection is NOT independent human approval. Live 80-ID detector
  and fallback unchanged; new reference IDs have no real-layout positives or
  approved project mapping. No claim of 85% independent detection accuracy.
- **PASS focused:** 15 native-context/sampling/hash/retention tests,
  11 replay/recovery/report, 15 catalog/reference and two matching tests (43),
  compilation and diff check (existing LF/CRLF warnings only).
  Full backend/frontend/database/browser NOT RUN (offline tooling only).
  Branch `codex/vlm-localization-experiment`, HEAD `85448ef`, changes uncommitted;
  unrelated edits and stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` preserved.
  No new dependency, download, model family, hosted inference or release change.
- **PASS integrity / exact resume:** supplied PDF, portable workspace approved
  references/session, parent v2, new v3 and live weights rehashed unchanged.
  No live training/inference job remains. Goal status `usageLimited` observed;
  no further training started. Next smallest experiment: pair native shared-grid
  reference views against the current target-centered context views for those
  three misses; preserve v3 and every frozen report, unknown-region masking,
  original 80 IDs and all requested references. Any new revision is development
  tuning, followed by bounded training and the same reference/upload/23-page
  probes; require evidence before changing the active provider. Reconcile
  untracked helper/runtime dependencies before a self-contained scoped Git
  publication; do not stage unrelated UI/API changes. Public Philippine rights,
  new-layout annotations, independent metrics and production approval pending.

### October 5 native source-context replay checkpoint

- **PASS immutable preparation:** `pec-replay-20261005-v2`, manifest SHA256
  `586a80b94a67b02911d99c9ec3ea0aaef27c021d737353a4c82ffe5cddc2fe24`.
  **1,114 windows** = frozen 727-window replay + 248 native supplied-reference
  views + 99 original-upload switch-retention views + 40 byte-verified historical
  crop backfills. All original 80 IDs and all 54 requested device meanings remain
  supervised in the same 129-ID head; requested 12 wiring patterns remain typed
  references, not point devices. Reference views are definitions, NOT real-layout
  positives. Original coordinates, exact source hashes, isotropic scale, tile
  origin and supervised neighbor identities preserved; no flips/rotation.
  Existing source-bound development authorization reused, no invented human or
  dataset-approver signature. Historical manifests/annotation files unchanged.
- **PASS loss/resource safeguards:** only construction-known composites receive
  full-background supervision. Native reference/retention views ignore unknown
  anchors; actual loss/provenance regression proves zero unknown-background
  gradient across 129 classes. Enlarged source allocations now fail before resize
  above the existing 60 MP/10,000-pixel bounds. No new dependency, architecture,
  hardware, download, hosted inference or application model selection.
- **PASS first bounded execution, FAIL old-class retention gate:** new-dataset
  initialization from prior replay run2, explicitly optimizer-reset, not a false
  same-dataset resume. CPU batch 8/input 320, AdamW 0.0002, four epochs;
  classification loss 0.95791 -> 0.54739, CSV elapsed 315.619 s. Context run1
  checkpoint SHA256 `cedd27914e7c7e95e4896852703d6ffbede4e082cedc4fc890efac6c78f91e00`.
  Frozen score 0.50/class-aware one-to-one IoU >= 0.50: reference synthetic
  **234/248**, every requested meaning nonzero; native reference tables
  **60/62** (39/40 + 21/22), up from 4/62. Misses: Special Purpose `1.20.15`
  not localized; Flame Detector `1.36.4` localized with wrong class. Original
  upload **28/29** (20/20 lamps, 8/9 switches). All same-source development,
  not independent accuracy; reference overlays still show text/unrequested-glyph
  proposals, not automatically accepted devices. Precision remains unscored.
- **PASS broader measurement, not quality acceptance:** 23 original pages/830
  positives, identical shared tiler/threshold/matching. Context candidate
  **735/830** class+location, **745/830** location, **1,272 proposals**, no cap;
  current 80-ID detector **802/830**, **806/830**, 2,886 proposals, three caps.
  Largest losses include new-smoke class 20 (37 -> 26), datacom homerun class
  33 (17 -> 10), panel-specific homerun class 53 (18 -> 12). No count reduction
  treated as precision improvement. Initial probe command incorrectly paired
  the candidate with the 80-ID manifest: namespace preflight correctly refused
  before result creation; rerun used exact 129-ID dataset, not a relaxed check.
  Reports/overlays: `pec-replay-20261005-context-probe-v1` and
  `pec-replay-20261005-context-original-pages-probe-v1`.
- **PASS bounded continuation execution, FAIL activation suitability:**
  `pec-replay-20261005-context-run2`, same
  frozen dataset, four epochs/input 320/batch 8/CPU/AdamW 0.0002, run1 warm-start
  with optimizer reset recorded. Classification loss 0.50793 -> 0.40668,
  CSV elapsed 455.276 s; terminal exit 0. Checkpoint SHA256
  `dee80d502baeec533269bfe8ce0827412ba859fe059da6edba126256bbbf07e1`.
  Terminal frozen probes: **244/248** reference synthetic, every requested meaning
  nonzero; **61/62** reference-table matches (40/40 + 21/22), 92 proposals, no cap;
  original upload unchanged **28/29**. Flame `1.36.4` is localized but predicted
  Ionization class 128 at raw score 0.546, NOT silently merged with class 127.
  Four synthetic switch misses: `1.21.1`, `.4`, `.9`, `.10`, each 3/4.
  Older 23-page retention worsened to **714/830** class+location, **726/830**
  location, **1,194 proposals**, no cap. Additional epochs did NOT fix forgetting;
  do not lower the scored threshold or use training mAP to override this failure.
  Both serial probes terminal exit 0: immutable `...context-probe-v2` and
  `...context-original-pages-probe-v2`. Keep live 80-ID detector/fallback unchanged;
  diagnostic 129-ID checkpoint not activated.
- **PASS targeted retention diagnosis:** deterministic four prior-correct/current-
  missed examples (classes 20/33/53/55), exact original target/source hashes,
  native 256-pixel tile versus isolated original glyph, both checkpoints/input 320,
  serial CPU. Native correct-overlap raw scores, parent -> candidate: new-smoke
  **0.987 -> 0.357**, datacom homerun **1.000 -> absent** (wrong class 34 at
  0.089), panel-specific homerun **0.999 -> 0.121**, troffer **0.965 -> 0.457**.
  Visually inspected all four native crops: source targets present; scores/class
  identity changed on the same pixels, not a missing image/checkpoint or only a
  coordinate conversion bug. Parent smoke/datacom performance itself depends
  strongly on surrounding source context when isolated. This supports a retention/
  context-overfitting diagnosis, not a proven generalization claim. Raw 0.01 is
  observation only; application/scored threshold remains 0.50. All 16 paired
  model/input observations, raw proposals and overlays preserved in
  `pec-replay-20261005-context-retention-diagnostic-v1`, report SHA256
  `c1fe77440f6915bc7d811c2145aa4e43542d1fe8a44cd77787b617b8ea30e976`.
- **PASS focused:** ten native-context/retention tests, nine replay/recovery/report,
  15 catalog/reference-probe, 19 source discovery/preparation, seven actual
  loss/masking tests (**60**), compilation. Supplied original, portable catalog
  and saved-session hashes unchanged; stash preserved. Full backend/frontend,
  database, browser and upload/correction/save/2D/3D **NOT RUN**: this checkpoint
  changes offline tooling only. API/table counts not remeasured, no schema/route
  edits. Branch `codex/vlm-localization-experiment`, HEAD `85448ef`; task changes
  uncommitted, unrelated work preserved. Public-source rights/real-layout labels,
  independent data, drawing-specific mapping and release approval remain pending.
- **Exact next checkpoint:** no more epochs on this imbalanced frozen revision.
  Prepare a separate bounded retention-context revision using existing reviewed
  original page targets/neighbor labels, deterministic class-aware sampling and
  immutable source/hash provenance; preserve all 129 numeric IDs and reference
  meanings, unknown-region masking and existing allocation/window bounds.
  Diagnose FD/ID text/context confusion without merging their meanings. Repeat
  identical broad retention/reference probes before any development activation.
  No new source rights, human approvals, independent examples or production
  readiness invented. Preparation of that revision has NOT started.

### October 5 all-class reference replay and context diagnosis

- **PASS preparation:** immutable `pec-replay-20261005-v1`, SHA256
  `cc73bd2d58c3f1bd9411aab7ff35c2f2596bce9ceac62e80eca6049bf7a4a7af`.
  **727 windows: 310 original real windows + 41 delegated PDF windows + 344
  construction-known composites + 32 previously inspected negative windows**.
  Every original 80 numeric class and all 54 requested device-reference meanings
  have supervision (129 head IDs, minimum four windows/class). All original 56
  drawing-specific entries retained; no new source-reference meaning presented
  as approved project mapping. Exact inherited image/label bytes retained;
  deterministic bounded sampling and authored text/table distractors are not
  independent examples. Existing reviewed-box/background loss ignores unknown
  real-page anchors; only construction-known composites supervise full background.
  Public-agency sources remain outside training; wiring remains separately typed.
- **PASS historical diagnosis, no silent repairs:** preparation initially refused
  40 recovered records lacking byte hashes, not proven corrupt. Preserved and
  excluded them in frozen v1, while retaining all classes. Located exact original
  recovery manifest (`402433b8b2a969f89ac695426d300e239b48f8b3ef5f569d5c34a41580645c3d`),
  then verified **all 40** stored crops against original RGB pixels, source hashes,
  groups 1-22/train identities and historical neighbor-label coordinates.
  Separate `pec-replay-20261005-recovered-audit-v1.json` SHA256
  `cdb74f91cc1cb6a732b40c21b6120cd70a9f48b4e82702e333c94ecb5e20793f`.
  No original/source/annotation file rewritten; this is technical reconstruction,
  not a fabricated human review. Backfill belongs in a new dataset revision,
  never the dataset used by completed runs.
- **PASS bounded local execution, FAIL candidate suitability:** unchanged local
  architecture/weights family; CPU batch 8/input 320, partial-label loss,
  AdamW 0.0003, four epochs then eight same-dataset epochs in new run/optimizer
  reset. Run1 classification loss 5.14854 -> 1.36524; run2 1.1428 -> 0.4685;
  CSV elapsed 191.283 s + 360.894 s. Trainer end-validation reuses training
  images; its mAP/precision are NOT independent real-page measurements.
  Score 0.50, class-aware one-to-one IoU >= 0.50 unchanged. Reference learning
  **46/248 -> 232/248**, now every requested meaning has a nonzero synthetic
  match. Full reference-page context **3/62 -> 4/62**, still failed. Original
  upload **20/29 -> 22/29** matches (20/20 lamps, 2/9 switches), versus the
  unchanged detector's 28/29. Candidate run2 `last.pt` SHA256
  `3943a088310b3d926b797293af56effb8af87ae9b3833b09688eff248a788911`.
- **PASS broader measurement, not a quality pass:** identical shared tiler,
  23 original development-source pages/830 prior positive boxes. Parent:
  **802/830** class+location, **806/830** location, **2,886 proposals**, three
  pages hit proposal cap. Replay candidate: **720/830**, **731/830**, **1,173
  proposals**, no capped pages. Reduction in proposal count is NOT measured
  precision improvement. All source-dependent/partial-label, no held-out project
  or 85% claim. Reports and overlays `pec-replay-20261005-original-pages-probe-v1`
  and `...-original-pages-parent-probe-v1`; both completed successfully.
- **PASS targeted diagnosis:** frozen class IDs, same weights/320 preprocessing,
  six paired inputs for Single Convenience `1.20.10` and Single Pole `1.21.1`.
  Native source tile versus exact same source glyph on white versus native-scale
  training composite. Correct overlapping raw scores: outlet absent / 0.278 /
  0.949; switch absent / 0.504 / 0.824. Native tiles instead favored old classes
  10/63 at 0.048/0.160; paired overlays visually inspected and source glyphs are
  present/readable. Evidence points to context/placement and class-confusion
  sensitivity, not a missing checkpoint or coordinate-only integration failure.
  Raw 0.01 threshold is diagnostic observation only; scored/live threshold stays
  0.50. `pec-replay-20261005-context-diagnostic-v1` preserves all raw proposals.
- Per-entry reports `pec-replay-20261005-probe-v1` and `...-probe-v2` enumerate
  **all 129 head identities and all 54 reference meanings**, included counts,
  synthetic outcomes, reference-context outcomes, applicable upload retention and
  limitations. Precision, independent accuracy, human review and production
  approval remain unscored/not claimed. Diagnostic 129 head remains blocked by
  the unchanged application artifact gate; live detector/fallback not changed.
- **PASS focused:** nine replay/recovery/report tests, 15 catalog/reference-probe
  tests, 19 existing preparation/matching tests, eight authored-extension tests,
  seven actual loss/masking tests (**58**), compilation and scoped whitespace/hash
  checks. Loss tests run through unittest without database fixtures. Initial
  preparation failure investigated and corrected with explicit exclusions/audit,
  not suppressed. Full backend/frontend/browser **NOT RUN** (offline tooling,
  no route/schema/UI edits); no model download, hosted inference or production
  activation. Branch `codex/vlm-localization-experiment`, HEAD `85448ef`, changes
  uncommitted; unrelated work and recovery stash preserved.
- **Exact next checkpoint:** new revision from frozen replay v1, backfill the
  40 technically verified hashes while keeping originals/audit, then add actual
  native reference-page context windows using the existing partial-label mask
  (unrequested glyphs/text never declared empty background). Strengthen retained
  real switch contexts using existing source/legend evidence. Start from run2
  only with explicit new-dataset initialization provenance, not a false
  same-dataset optimizer resume. Repeat frozen 54-reference/full-page/old-class
  probes before any development model switch. Public-source rights, independent
  data, drawing-specific mapping and release gates remain pending.

### October 5 complete requested-reference diagnostic and retention gate

- **PASS immutable preparation/mapping:** all **54 device-reference meanings**
  included, **62 glyph variants / 248 construction-known synthetic examples**;
  **12 wiring patterns** remain separately typed references, not installed point
  devices. `pec-reference-20261005-full-head-v1` retains all original 80 numeric
  IDs and appends 49 explicitly source-reference-only classes (129 head IDs).
  These additions are user-requested development labels, NOT drawing-specific
  catalog approval, gang/wattage guesses, independent PEC certification or live
  model coverage. Five existing exact-meaning links and nine catalog-meaning
  links preserve original identities/qualifications. Unresolved reference-only
  source pixels remain excluded; public-agency pixels were not used in training.
- **PASS catalog reconciliation, no workspace mutation:** 287 catalog entries
  inspected against current session/source hashes; 286 have current reviewed
  evidence. Preserved 16 deleted examples and one corrected-but-not-reviewed
  example as excluded. Reconciled 26 stale export boxes only where annotation
  ID, source hash, meaning and current `user_reviewed` identity agree; retained
  both exported/current boxes. The frozen dataset contains the earlier strict
  260-entry/43-exclusion audit; a separate immutable
  `catalog-reconciliation-v2.json` records the corrected 286/17 audit. No source,
  portable annotation, original manifest or history rewritten.
- **PASS bounded learning, NOT generalization:** same frozen dataset, CPU,
  batch 8, input 320, 8 epochs plus 12 further epochs in separate runs with
  optimizer reset. At score **0.50**, one-to-one **IoU >= 0.50**: initialized
  head **0/248** class+location, **23/248** location; run1 **134/248** and
  **135/248**; run2 **247/248** for both, 247 proposals. Every requested device
  meaning has a nonzero synthetic match. Sole remaining miss: Key Operated
  `1.21.9`, 0.65-scale variant. Initially missed native glyphs mostly had the
  right overlapping raw class below 0.50; junction box additionally confused
  with riser-up. Threshold was not lowered to improve reported scores.
  Run2 classification loss 1.21719 -> 0.46766, elapsed trainer CSV 181.827 s.
  Training-image validation and memorization metrics are NOT independent mAP.
- **FAIL full-page context suitability:** unchanged shared upload tiler on both
  complete supplied reference pages: page1 **16/40** class+location, **17/40**
  location, **35 proposals**, 5.229 s; page2 **10/22** for both,
  **25 proposals**, 5.081 s. Neither truncated. Expected/predicted overlays
  visually inspected: small switches missed, wall/ceiling variants inconsistent,
  and text/table content produces apparent false proposals. All unmatched
  proposals remain unresolved; precision and independent accuracy unscored.
  Reused reference pages are development evidence, not held-out floor plans.
- **FAIL existing-class retention:** identical complete DepED derivative upload,
  unchanged 0.50 threshold/shared tiling/first-80 meanings and source hash.
  Original pinned detector: 30 proposals, **28/29** class+location (20/20 lamps,
  8/9 switches), **29/29** location, 1.973 s. Reference-only candidate: zero
  proposals and **0/29** matches, 1.990 s. Targets are prior assistant-inspected
  development labels under user authorization, not independent human review.
  **75 original classes had no positive supervision in this reference run**;
  results are consistent with forgetting/context mismatch, not usable expansion.
  Live detector remains `switch-real-20261004-run3`; diagnostic cannot pass the
  unchanged application artifact gate. No production promotion or UI activation.
- Private evidence: dataset SHA256
  `efbf156f928ed5d3c9a80fe629b65edb10f751edd3d8f5ca77a34214f1c96881`;
  candidate run2 `last.pt`
  `604f68dad11e5e6cd63d798f4349f1ba2bb9728c3acd688f4a1703de9869627d`.
  Per-entry `reference-coverage-v1.json` (54 devices + 12 wiring, samples,
  aliases, prediction counts, misses and unsupported metrics):
  `9e643cd8ffc5cee7b5684d91ddaf744373d1de81ec862d76b9fa4d0ac899e7b9`.
  Full-page overlays/reports: `pec-reference-20261005-table-page1-v1`,
  `...-table-page2-v1`; retention reports `...-old-upload-regression-v1` and
  `...-old-upload-parent-probe-v1`. Catalog audit-v2 SHA256
  `88d6ba035b00859ba06e71089b51f6edbe985de30e2a8a3e31a16fd8b130c52d`.
- **PASS focused verification:** 15 catalog/probe tests + 19 source/reference
  tests + seven PDF-source tests + eight delegated-PDF tests + eight authored
  extension tests (**57**); scoped compilation/diff and original/parent hash
  checks. Coverage rejects mixed checkpoint/dataset hashes, incomplete/duplicate
  summaries, inconsistent measurements, altered labels and invalid coordinates;
  preserves deleted/rights-excluded items, immutable history and unscored metrics.
  Full backend/frontend/browser **NOT RUN**: offline source/training tools only,
  no schema/API/UI edits in this checkpoint. Recovery stash retained; unrelated
  work preserved. Branch `codex/vlm-localization-experiment`, HEAD `85448ef`,
  task changes uncommitted/unpublished. No claim of 85% or detection readiness.
- **Next bounded checkpoint:** retain these failed/positive diagnostics; prepare
  an old+new replay candidate with all existing class supervision, source-backed
  layout positives/ignore regions and construction-known varied context. Verify
  original-class retention and full-page context before any development switch.
  Four public Philippine source archives remain prepared but training-excluded
  pending intended-use rights evidence and source-specific label/split evidence;
  DPWH downloads remain unavailable. Dataset authorization for existing VED
  sources is unchanged; no routine/per-class reapproval requested.

### October 5 supplied-reference cleanup and bounded learning checkpoint

- **PASS reference preparation:** immutable `pec-reference-20261005-clean-v3`
  contains **62 device glyph variants + 12 unchanged wiring references** from
  all 66 requested logical entries. Ceiling/wall glyphs split at their authored
  divider; table rules removed by source-coordinate cropping, not destructive
  pixel edits. Switch subscripts/mount stubs retained. Failed cleanup v1/v2 and
  original preparations preserved as inspection-only history. Assistant visual
  QA is not a separate human approval or independent PEC certification.
- **PASS conservative mapping:** five reference entries match existing meanings:
  `1.23` Pull box -> 23; `1.26` Circuit home-run notation -> 0 (aliases 1/6/8/10
  retained); `1.27` Push button -> 72; `1.36.2` Fire alarm control panel -> 74;
  `1.36.5` Smoke detector -> 11 (aliases 30/44 retained). Generic fluorescent
  lamps are NOT 1x40/2x40 targets; single-pole switches are NOT guessed gang
  counts; main/power/lighting panelboards are NOT silently merged. **49 other
  device-reference entries remain reference-only, with no exact current-head
  equivalent**; all original reference identities remain available. No new
  project/catalog class or approval manufactured.
- **PASS actual local diagnostic, not detection readiness:**
  `pec-reference-20261005-diagnostic-v1` has 60 construction-known composite
  images (12 per matched reference), unchanged full **80-class numeric head**,
  native glyph orientation, isotropic scaling and known placements. Complete
  synthetic-background supervision is diagnostic-only; no unannotated real
  page treated as empty background. User-requested supplied-source development
  permission is hash-bound; public sources remain excluded. No new download,
  architecture, hosted inference or larger replay training.
- Exact-threshold probe: **score 0.50, IoU >= 0.50, one-to-one matching, 320 input**.
  Base: **0/60 classified+localized, 6/60 localized**. After three CPU epochs:
  **46/60 classified+localized, 56/60 localized**. After seven further bounded
  epochs (new immutable run, same-dataset warm start, optimizer reset): **60/60
  classified+localized and localized**, 12/12 for each of the five references.
  **67 raw proposals include seven unmatched/duplicate synthetic proposals**;
  memorization does not prove generalization or clean full-page behavior.
  Classification loss run1 5.20362 -> 1.23748; run2 1.03165 -> 0.55555.
  Trainer validation reuses training images: its mAP is NOT independent accuracy.
  No real-page recall/precision, 85% result, or production acceptance claimed.
- Reproducible private evidence: cleaned manifest SHA256
  `44d16ab12d86bf12b0900b33caff5a6021483456b807fa0090a68336cbc50240`;
  diagnostic dataset `d81890f913aabbc46037f30dffed51fa786084749df9a7ce18bd5a69c8d22c38`;
  run2 `last.pt` `621f13bfb3a9d2ed4fc76480c3c1691ea00f2f1b924948568c93a78a13ef2721`.
  Reports/overlays: `pec-reference-20261005-base-probe-v1`,
  `pec-reference-20261005-trained-probe-v1` and `...-v2`. Discovery index v2
  remains the earlier source-discovery snapshot, not this diagnostic's approval.
- **PASS focused:** 19 discovery/reference tests + seven PDF-source tests +
  eight delegated-PDF tests + eight authored-legend tests (**42 total**),
  compilation, scoped diff check and hash verification. Tests include variant
  separation, faint-wire retention, table fringes/subscripts, no subtype guesses,
  altered glyph/source rejection before writes, immutable revisions, unchanged
  numeric names and synthetic/source authorization. Full backend/frontend and
  browser **NOT RUN**: no application/UI/schema/API changes in this checkpoint.
  Live detector remains `switch-real-20261004-run3`, original/parent hashes and
  stash unchanged. Branch `codex/vlm-localization-experiment`, HEAD `85448ef`;
  task changes uncommitted; unrelated work preserved.
- **Next bounded work:** reconcile remaining reference meanings against actual
  drawing/catalog evidence (no per-class approval re-request), then prepare
  source-supported real-layout positives/ignore regions and an all-class replay
  candidate with old-class regression checks. Public-plan use additionally needs
  an intended-use rights basis; its posting alone is insufficient. Diagnostic
  weights MUST NOT replace the shared detector: 75 head classes had no samples
  in this run, and no old-class/full-page regression has been performed.

### October 5 Philippine public electrical-source preparation

- **PASS discovery/preparation, not training:** attempted 12 primary official
  Philippine source URLs; four PDFs downloaded, eight unavailable (including
  three DPWH URLs). No access-control bypass, hosted inference or model download.
  Only **34** explicitly selected electrical sheets enter preparation: **31
  layout sheets + three legend/notes sheets**. Complete procurement originals
  are hash-bound inspection archives, not 449 training pages. Sources:
  [TESDA NCR](https://www.tesda.gov.ph/Uploads/File/PhilGeps/2021/Bid%20Docs%20-%20RTC%20-%20NCR%20Part%202.pdf)
  (17 sheets: lighting, power, FDAS/PA and ELV/CCTV/voice/data),
  [SLSU Tomas Oppus](https://southernleytestateu.edu.ph/attachments/article/728/merged.pdf)
  (four lighting/power sheets; no verified drawing legend),
  [BSU veterinary teaching hospital](https://bsu.edu.ph/wp-content/uploads/IB2024/IB-2024-22A-bid-docs_whole.pdf)
  (three lighting/power/legend sheets), and
  [Quezon City school rehabilitation](https://quezoncity.gov.ph/wp-content/uploads/2025/02/25-00004.pdf)
  (10 electrical sheets). Title blocks and six extracted legend panels visually
  inspected by assistant; not independent human annotation approval.
- Supplied source `reference-8fa0851445cb` preserved with exact SHA256
  `8fa0851445cbe840c59af1b59042369aec4dc78eef8401f10e18ca22736f3af3`.
  All **66 requested entries** extracted from PDF pages 1-2: 54 point/reference
  entries and 12 separately typed wiring patterns. Ceiling/wall variants kept;
  generic fluorescent symbols do not imply 1x40/2x40 ratings. User-requested
  local reference use recorded, not publisher permission or a separate approver.
  Appendix attribution is user-supplied; edition/publisher not established from
  five scanned pages. Reference glyphs are not real-layout localization boxes.
- **PASS integrity/coordinates:** five original hashes, five selected manifests,
  36 rendered pages, 66 reference crops and six legend panels verified. Visual
  QA caught clipped initial crops; immutable corrected revisions retain failed
  drafts as inspection only. A real metadata omission affected seven 270-degree
  university pages: new preparation explicitly records rotation and rendered
  top-left point frame, never unrotated PDF user space. Rotation regression
  included; original scans and prior manifests unchanged.
- Private current index: ignored
  `storage/training/ph-electrical-discovery-20261005-v1/dataset-index-v2.json`.
  Public selections `electrical-selected-v2`, public panels `legend-panels-v3`,
  supplied reference `pec-reference-20261005-v3`. Unreviewed regions must be
  ignored/masked, not empty background. Related floors/crops stay together;
  no new independent evaluation split claimed.
- **BLOCKED public-source training eligibility:** consolidated missing evidence
  for `tesda-ncr`, `slsu`, `bsu`, `qc-masambong-school`: intended-use rights basis,
  drawing-specific class mappings, positive boxes/ignore regions and project
  relationships; `slsu` additionally lacks an explicit verified source legend.
  Public posting is not a rights grant. Government-work commercial-use
  restrictions remain relevant ([Section 176.1 court discussion](https://lawphil.net/judjuris/juri2020/jun2020/gr_236050_2020.html));
  PEC notes are not independent compliance certification. Existing VED source
  permissions and encryption deferral unchanged. No repeated VED approval asked.
  Supplied references still require class mapping and border cleanup before
  synthetic use; no ambiguous subtype silently merged or activated.
- **PASS focused:** 12 discovery/preparation tests + seven existing PDF tests,
  compilation and diff check. Full application/backend/frontend regressions and
  browser **NOT RUN** (offline preparation only; no application/schema/API edits).
  Model/checkpoint unchanged; no new measured detection accuracy or trained
  class coverage. Branch `codex/vlm-localization-experiment`, HEAD `85448ef`;
  task changes uncommitted, unrelated edits and recovery stash preserved.

### October 5 universal legend choices and duplicate-proposal fusion

- **PASS scoped implementation:** duplicate *choices* grouped by identical
  complete descriptions in Admin catalog, draft mapping, legacy correction and
  manual-placement menus. Live read-only inventory: **105 active source rows,
  69 unique descriptions, 36 duplicate choices**. Every original database ID,
  source name, inactive decision, trained class index and review history stays;
  no rows/files deleted or approvals invented. Admin exposes original aliases
  under Drawing references; a previously selected alias keeps its ID on save.
  Rated/mounted variants, one/two/three-gang vs three-way, single/twin lamps,
  new/existing detectors and unresolved descriptions are not family-merged.
- The existing default remains **one shared development detector**, unchanged
  80-index checkpoint/dataset, not another page-specific/template model or a
  newly trained "universal" architecture. Exact-description grouping yields
  **61 model meanings**, not 61 proven detectors or all 286 catalog definitions.
  Spatial fusion now removes co-located equivalent-class observations before
  the 200-proposal cap, using existing IoU/nested-center bounds. Adjacent or
  genuinely different classes remain separate. Highest raw observation wins;
  losing equivalent model IDs, source entries, boxes, scores and tile origins
  are retained as candidate warnings, without automatic acceptance.
- Historical original-replay predictions contain **140** such duplicate
  proposals. This count comes from postprocessing already capped saved
  predictions, **not** a new full inference/precision/recall measurement.
  Actual new-pipeline upload check: **30 unresolved proposals**, including
  16 twin lamps, four single lamps, five one-gang, four two-gang and one homerun;
  strict candidate roundtrip passes, no smoke output, no silent approvals.
  Previous measured misses and classification errors remain limitations.
- **PASS focused verification:** **53 isolated backend tests + 21 subtests**,
  **47 frontend tests / four files**, scoped ESLint, build, compilation, diff
  check. A new warning initially used an unqualified entity reference; strict
  roundtrip regression caught it, corrected reference and full focused rerun
  passed. Broader regression **NOT RERUN** this checkpoint; prior counts above
  are historical. Existing deprecation/chunk-size warnings remain.
- Configuration SHA256
  `4a6dd710ece41828271ccc94d7e6c863feeb674d196a9eda860093cd8e891f91`:
  pins `exact-complete-legend-description-v1` alongside unchanged artifact
  hashes. Restarted owned loopback backend after checking zero active leases
  and open jobs. Existing results are preserved; run a **new analysis** for
  changed fusion. Production release/gateway and rollback providers unchanged.
- **NOT TESTED authenticated browser catalog/review:** computer-use reload
  reaches sign-in only; no role impersonation or authentication bypass.
  Data consolidation is a reversible view/fusion change, not destructive DB
  contraction. Branch `codex/vlm-localization-experiment`, HEAD `85448ef`;
  scoped changes uncommitted, unrelated work and `stash@{0}` preserved. No
  larger training run, release promotion or additional epic started.

### October 4 switch localization replay (bounded development checkpoint)

- Existing switch IDs were present but ineffective on drawing tiles: original
  lamp-repair checkpoint matched **1/4** inspected three-storey switches and
  **0/9** on both the DepED PDF panel and its small upload. All four centered
  three-storey training crops predict their correct IDs (raw scores
  0.997–1.000). This supports grid-phase/context sensitivity, not a missing
  class head or an independent accuracy claim. Saved exact diagnosis and
  baseline JSON/overlays; inference threshold remains **0.50**.
- Under the existing delegated development permission, inspected real S/Sa,
  Sab/circuit-letter variants against both authored legends. Reused four
  three-storey records unchanged, added nine PDF and nine related derivative
  boxes. Identical one/two-gang meanings may share IDs 62/63 while each source
  legend alias remains traceable; three-gang ID 64 remains distinct. The
  ambiguous Sf mark conflicts with the displayed fan-control meaning and
  fluorescent branch context: excluded, not silently approved or relabeled.
- Immutable `switch-real-20261004-v1` SHA256
  `131e8dc0af696192e13924d7c1d3c31ecd77f0bccf7bf651c8b75ab9acab24ef`:
  preserves all **80** IDs, original reviewed records, old manifests, copied
  permissions and split history; adds **594 dependent context views**, varying
  x/y grid phase ±80 pixels and isotropic scale. Unreviewed areas remain masked.
  PDF/upload remain one project; assistant inspection is not human approval.
- Run1 completed one CPU epoch, 320 input, batch four/effective target 64,
  lr 0.0003, same local architecture/weights, no download. Last SHA256
  `c730369139bf308a7c4cef1871d1850ddca3bdfcf423df1f419793ac04e1b346`.
  Full pre-recorded panels and full upload, one-to-one class + IoU ≥0.50:
  switches **3/4** other PDF, **7/9** DepED PDF, **5/9** small upload; upload
  retains **20/20** lamps (16 two-lamp/four single-lamp), 26 total proposals.
  Two-gang misses/misclassifications remain explicit; overlays inspected.
  Other PDF **28/35** total targets. Original reviewed replay **802/830**
  matches, 805 localized, 2,483 proposals, no cap: versus previous active
  lamp checkpoint 795/830 and historical original baseline 806/830.
- Run2 completed, optimizer reset and exact run1 warm-start: switches **3/4,
  8/9, 6/9** (other PDF, DepED PDF, upload), both lamp views **20/20**; original
  replay **804/830**, one capped page. It regressed other-PDF outlets from
  **5/6 to 2/6** and was **not activated**. Its evidence remains unchanged.
- Restorative immutable `switch-real-20261004-v2` manifest SHA256
  `11ef819e20b120ea1bb44e08a64822f820f2f575c7c76212d5043f2b6249f527`
  keeps all v1 records and adds **162 dependent views of the six existing
  outlet boxes**, not new independent examples. Run3: one CPU epoch, 996 steps,
  same partial-label loss/architecture/settings, base run2 SHA256
  `cb2271b6ccccd8f03fb221f12a2fe6bec7bf6eedbf5b031b7f6d29e93e03c1f6`.
  Selected last checkpoint SHA256
  `867c7fb399104bf91caff1d6aad859504cc923443cb3e02fcb2b00255b2affa2`.
- Frozen full-panel/upload checks at **0.50**, class-aware one-to-one IoU 0.50:
  DepED PDF switches **9/9** (six one-gang, three two-gang); derivative upload
  **8/9** (five/six one-gang, three/three two-gang; the remaining one-gang is
  localized but misclassified). Other PDF **3/4** (one/two one-gang, two/two
  three-gang). Both related lamp views retain **20/20**; upload has 30 proposals
  including nine switch proposals and no smoke-detector output. Other PDF
  **31/35** total: lamps 20/22, outlets restored 5/6, homeruns 3/3. Upload/PDF
  overlays visually inspected: misses, the wrong gang subtype, grid/wall-edge
  false proposals remain unresolved. Precision and independent accuracy **unscored**.
- Original replay **802/830** classified, 806 localized, 2,886 proposals,
  **three pages capped at 200**; versus prior active lamp replay 795/830 and
  historical original baseline 806/830. All original 56 IDs retain nonzero
  matches; rare IDs 21/51 each 5/5. This is a measured development tradeoff,
  not release acceptance. Immutable all-80-entry coverage report:
  `storage/training/switch-real-20261004-run3-coverage/report.json`; source
  legend aliases/counts, each checkpoint-bound probe and limitations separate.
  **63 classes have source-positive boxes; 17 remain reference/synthetic-only.**
- **PASS implementation / experimental development selection:** existing
  `lamps80` shared model path now pins run3/v2, prompt revision
  `partial-label-80-switch-replay-v2`, configuration SHA256
  `bd5ce9767d9fed192e853876e2d5714b1ba6b5424c98f42d3a0101516557d986`.
  Actual weights/head/hash validation and strict payload roundtrip produce
  named one/two-gang proposals with unknown mapping, no catalog approval.
  Retained `original56` rollback and previous 80-entry checkpoints unchanged.
  Restarted only the owned loopback backend after checking zero active leases
  and zero queued/processing jobs. Existing results are not rewritten; new
  analysis is required. This is supervised YOLO, not local VLM inference.
- **PASS verification:** 22 script tests + 31 subtests; final focused backend
  **57 + six subtests**, including isolated MySQL switch persistence and review,
  candidate contracts and multipage lease regressions. Full isolated backend
  **1,069 passed / four skipped / 525 subtests** (before final artifact-pin
  update; final focused run after it). Full frontend **441 tests / 50 files**;
  scoped ESLint, frontend build, compilation and diff checks. Existing
  deprecation warnings and large build chunks remain. Initial test/diagnostic
  field-name/import mistakes were corrected and rerun, not counted as passes.
- Integration uncovered a pre-existing page-one queue stall: a succeeded
  page lease left the job processing, but the next claim treated it as legacy
  recovery; successful page ordinals also consumed the retry bound. Trusted
  continuation now requires persisted same-job/page candidates, while only
  failed/expired leases consume the three-failure budget. Fencing, cancellation
  and legacy recovery remain enforced. Four-page continuation and retry-budget
  tests pass. Live job **24178** advanced to page two, then exhausted retries
  with `INTERPRETATION_PROCESSING_FAILED`; page one preserved, page two failed,
  pages three/four queued inside that failed job. No direct status rewrite or
  claim of completed multipage processing. Read-only reproduction passed page
  two normalization, geometry and 44-symbol strict payload generation; the
  remaining worker failure needs separate diagnosis; registration, provenance
  and persistence have not been established as its cause.
- **NOT TESTED signed-in browser correction/save/reload or WebGL:** computer-use
  inspection reaches the sign-in screen only; no authenticated session or
  impersonated actor. Database-backed contract tests are not browser evidence.
  **PENDING** independent quality/precision, production catalog approval,
  real gold/release gates. Next bounded work: diagnose the one-gang miss and
  gang confusion using frozen overlays, then independently reviewed positives
  and false-positive coverage; do not scale training or claim 85% accuracy.
  Recovery stash and unrelated work preserved; no commit/push this checkpoint.
  OpenAPI **44 operations**, metadata **33 tables**, source hashes unchanged.

### October 4 fluorescent-lamp misclassification repair (bounded development checkpoint)

- Reconciled actual saved runs 100–104 / jobs 24172–24176 with upload SHA256
  `e9f091252f664a6c97e1d3202d5552f6e80507f6304e3dc5c2d1e653dd3f2a48`:
  each used the original `development_multiclass56_yolo` weights and proposed
  eight Smoke detector (new) plus one Conventional smoke detector. Neither
  fluorescent-lamp class exists in that checkpoint. This is model scope and
  misclassification, not a UI rename bug. Catalog registration does not train
  weights. Historical candidates remain unchanged; smoke detections are not
  globally suppressed or silently relabeled.
- Under the existing delegated local-development authorization, visually
  inspected the PDF legend and 20 actual DepED lighting-panel targets: **16
  two-lamp / four single-lamp** fixtures. Separately inspected all 20 boxes on
  the exact **691 x 488** upload. It is a related derivative of the same drawing,
  not an independent project or a verified PDF-to-image affine transform.
  Original images, prior box revisions and project grouping preserved; a new
  immutable revision tightens one single-lamp box to exclude switch lettering.
  These are assistant proposals, not fabricated independent human box review.
- Immutable datasets `lamps-real-20261004-v1` and `v3` preserve the complete
  **80-class** head and original replay/authorization history. Added 20 real
  PDF boxes, 160 dependent scaled/context views, 48 single-lamp sampling copies,
  plus 20 derivative boxes and 384 dependent upload views. Unreviewed regions
  remain loss-masked; no new empty-background assumptions. The v2 derivative
  revision is preserved but was not trained. Dataset v3 SHA256:
  `11b8ade4bc1318214243d807c4ea6a6cc4d381b3444c8482e3c46e81648123b1`.
- Two two-epoch CPU runs completed: existing YOLO architecture/weights, 320 input,
  batch four, effective batch target 64, lr 0.0003, offline, no new download.
  Run1 last SHA256 `250204bc7e65c71b58f49483aa7ae9ed3ad7e53b9a0420c5c99854f6550244e6`;
  run2 last SHA256 `7d8f5de180f2d47771e66f3153b9cb13f2bf0e150400d7da373c8646c10312bf`.
  Training-resubstitution auto-validation is **not** release-quality evidence.
- Frozen score 0.50, shared 256/192 detail tiler, bounded second grid/batch eight,
  one-to-one class + IoU >=0.50: original 56-class weights **0/20** DepED PDF
  fixtures; prior 80-class candidate **10/20** PDF fixtures and zero proposals on
  the exact upload. Run1 **20/20** PDF fixtures but misses all four singles on
  the upload. Run2 **20/20** PDF fixtures (27 proposals) and **20/20** exact-upload
  fixtures (**16 two-lamp + four single-lamp proposals, no smoke proposals**).
  Overlays visually inspected. These are same-source learning checks; partial
  precision, independent accuracy and the 85% objective remain unscored.
- Wider run2 replay check: **783/830** original reviewed class/location matches,
  801 localized, 1,827 proposals, no cap hit; recorded original baseline was
  806/830, 2,196 proposals and one cap hit. Classes 21 and 51 (drawing-specific
  pull-station variants, five positives each) regress to zero matches. Other
  supplied PDF is **23/35**, versus run1 26/35. Do not trade these failures for a
  misleading all-class success claim. A one-epoch restorative replay experiment
  completed: v4 preserves v3, adds **696 exact train-only sampling copies** for
  classes 21/51/62/71, no independent examples or altered labels. Manifest SHA256
  `d495f772a97b80b6121355cfac89396765f3d3656a241ec70bd92acabd412fb4`.
- Run3 last SHA256 `6185f40f8679d0183a9c97d5e2eaf15f89641ceef6d8823688c36175bf1d6d57`.
  Exact upload **20/20** with exactly 16 two-lamp/four single-lamp proposals;
  PDF panel **20/20**, 25 proposals including apparent wall-edge false matches;
  other PDF **26/35** (18/22 lamps, 5/6 outlets, 1/2 three-gang switches,
  2/3 homeruns, **0/2 one-gang switches**). Original replay **795/830** class
  matches, 800 localized, 2,362 proposals and no cap hit. Classes 21/51 restore
  to **5/5 each**; all original 56 classes have matches. The eleven-match deficit
  against the recorded baseline remains visible; no all-class or generalization
  success is claimed. Immutable all-80-entry JSON coverage preserves class IDs,
  legend mappings, sample counts, per-source matches/predictions and limitations:
  **62 classes have real source boxes; 18 have reference/synthetic-only examples**.
- Fixed source-scoped probe denominators: page number and coordinates cannot
  identify a PDF in a combined replay manifest. An earlier mixed-source report
  is retained as invalid evidence; v2 and later reports filter exact PDF hash.
  Added class-specific nested tile-duplicate suppression; adjacent fixtures and
  different classes are retained. Added hash-bound 80-class loader compatibility
  with integrity-checked restorative sampling, exact-upload scoring,
  and an honest missing-lamp-class warning for the original provider.
- Fresh **PASS:** 51 focused backend/script tests + 30 subtests; restricted,
  empty isolated MySQL review/save/worker/catalog regression **53 tests + 15
  subtests**; focused frontend **43 tests / four files**; scoped ESLint and Vite
  build (existing large-chunk warning). Initial full isolated backend run:
  **1,063 passed / four skipped / 525 subtests** before final profile-provenance
  checks. New persisted fluorescent-worker coverage exposed unordered inference
  parameters; fixed sorting at construction, preserving strict validation. A
  subsequent full run exposed one historical 56-version assertion (1,064 passed,
  one failed); updated it to assert the selected pinned head/profile, not bypass
  the provenance contract. Final restricted/empty isolated full rerun **PASS:
  1,065 tests / four skips / 525 subtests**, five existing dependency warnings.
  Final worker tests include persisted named fluorescent proposals and actual
  selected-profile/head provenance. Compilation and diff checks passed; OpenAPI
  **44 operations / 33 tables** unchanged. Full frontend suite
  **NOT RERUN**. Computer-use
  browser check again reaches normal sign-in, not an authenticated review session;
  live correction/save/reload and WebGL **NOT TESTED**. No account impersonation.
- **Development only:** one shared `lamps80` checkpoint now feeds new upload
  proposals through the existing unresolved correction/save workflow, with exact
  names and an experimental warning describing measured failures. The historical
  `development_multiclass56_yolo` provider key is retained for stored-contract
  compatibility; actual head count, profile, dataset/checkpoint SHA256, warm-start
  base and prompt revision are explicitly recorded. It is YOLO, not local VLM
  inference. `DEVELOPMENT_SYMBOL_PROFILE=original56` plus backend restart restores
  the original pinned 56-class rollback; both real loaders checked. Production,
  configured local-gateway and promoted-release selections remain unchanged.
  Actual exact-upload inference produced a valid strict 20-symbol candidate,
  correct lamp names and all mappings unresolved; this is not authenticated
  browser saving or approved canonical geometry. No model auto-learning.
- Idle local backend restarted with access logging disabled; a second verified
  repository backend on port 8000 was stopped to remove stale-server ambiguity.
  Health is 200, sole listener is loopback. Existing completed job JSON/reviews
  are not rewritten: re-run analysis for new proposals. Original sources/fallback
  weights rehashed unchanged and recovery stash
  are preserved; branch `codex/vlm-localization-experiment`, HEAD `85448ef`, task
  changes uncommitted with unrelated work preserved. No production promotion,
  new Markdown report or dataset approval invented. Next: authenticated live
  re-analysis and correction/save/reload; import the approved PDF catalog through
  the real Admin workflow if still absent. Further detection work must target
  the missed one-gang switches and high-resolution wall-edge false proposals,
  and check original-class regressions; independent evaluation remains pending.

### October 4 complete authored PDF catalog (implementation verified; live import pending)

- Owner instruction: "all those must be used in the legend catalog list for the
  user to use". Applies to the supplied approved sources: 16 DepED page-7 entries
  and 24 three-storey page-1 entries. **40 source-specific definitions**, including
  36 symbols/notations and four wiring patterns; no checkpoint inclusion or
  detection success is required for catalog availability. This does not assert
  independent human box review or production model approval.
- Added **Import approved PDF legends** to the existing Admin catalog. Uses the
  existing authenticated import endpoint with `catalog=approved-pdf`; verifies
  pinned preparation manifests, source permissions, originals, source pages and
  every glyph crop before an atomic catalog/history write. No client paths or
  model downloads. Sources/manifests remain private and unchanged; manifest pins
  are `41d23c6e6d477508e17068901d4018234fa0e7df84976b83dcb3a0676280bb9a`
  and `305a464ef9e907785dbc3b5712be5c9418f1d614c677f230ca6506c698030963`.
- Each name retains `[pdf-<source hash prefix>:p<page>:L<entry>]`. Identical wording
  across drawings remains traceable, allocated app IDs remain separate from
  model indices, repeat import is idempotent, and existing/inactive entries are
  never overwritten/reactivated. Authenticated Admin and development-only gates
  remain enforced. Wire definitions are catalog-visible references: disabled in
  device pickers and rejected as point devices by manual placement,
  classification, review approval and canonical save. Rejected proposals remain
  saveable. This does **not** add a wiring-pattern editor or auto-route wiring.
- **PASS:** actual pinned artifact verification found all 40 definitions / four
  wiring patterns; focused isolated MySQL regression **58 tests + 30 subtests**;
  frontend **52 tests / five files**; scoped ESLint, frontend build, Python
  compilation and diff whitespace checks. Initial new tests expected 422 rather
  than the existing 409 conflict contract; corrected assertions and reran to pass.
  Existing Starlette/anyio deprecations and large build chunks remain warnings.
  OpenAPI remains **44 operations**, metadata **33 tables**. **NOT TESTED:** full
  backend/frontend suites, authenticated live browser import/selection/reload.
- **BLOCKED only for live publication into the catalog:** computer-use reached
  the local app but `/#/app` redirected to sign-in; no connected authenticated
  Admin session. No role bypass, fabricated actor/history or development database
  write. Next: sign in as Admin, open **Symbol legends → Manage symbol legends →
  Import approved PDF legends**, then verify the Designer's named picker after
  reload. Existing fixture-backed API tests prove public catalog availability and
  named draft selection/persistence; they are not live browser evidence.
- Branch `codex/vlm-localization-experiment`, HEAD remains `85448ef`; these edits
  are uncommitted. Preserved all unrelated edits and `stash@{0}` unchanged. Both
  PDF original hashes and active 56-class checkpoint hash reverified unchanged;
  the failed 80-class candidate stays inactive. Catalog use is not detection
  readiness or an 85% accuracy claim.

### October 4 delegated electrical PDF training (completed experiment; inactive)

- User explicitly approved training and delegated preparation without routine
  reconfirmation. Recorded exact statement, PDF/preparation hashes and train-only
  source grouping in immutable private authorization revisions. This is local
  development authority, **not an independent human box review or production
  approval**. It supersedes the source-only pending status below for this experiment.
- Visually inspected **35 assistant-prepared page-3 targets**: 22 two-lamp fixtures,
  six grounding duplex outlets, two one-gang switches, two three-gang switches and
  three homeruns. Corrected clipped/rotated outlet and homerun boxes in new
  revisions; retained every prior proposal. Missing regions remain loss-masked,
  not assumed background; pages 2/4 are not used as negative examples.
- Dataset `storage/training/elect-20261004-v1/` retains all parent 60 numeric class
  IDs and replay data. It appends 20 drawing-specific definitions; L02/L14 share
  exact authored meanings with candidate IDs 56/58. **80-class head**, 22 traceable
  device/notation entries, two wiring definitions explicitly outside device
  detection. Added 176 reference-derived placements (eight per entry), separately
  counted from real labels; reference-only coverage is not demonstrated detection.
  Manifest SHA256 `9aeff278dab44abb438db366fd5fe9b986e0a283f94d76bf202a09ea473fa5d8`.
- Reused head-extension, known-composite generation, partial-label loss and shared
  bounded tiler. New preparation/probe tools validate source authorization, hashes,
  transforms, copied labels and same-source one-to-one matching. Production import
  and active provider unchanged. Three-epoch CPU run (320 input, batch 4, lr 0.0003)
  completed at `storage/training/elect-20261004-run1/`. Last checkpoint SHA256
  `15247c3eadd911d53f39855912f79f24cde6255024e9bdeae30bf5c5f3f11e1d`.
- Same inspected drawing panels, frozen threshold 0.50 and one-to-one IoU >=0.50:
  initialized candidate **0/35** correctly classified (2 localized), replay
  candidate **4/35** correctly localized/classified (four lamps; no outlet,
  switch or homerun matches). Five proposals; no cap hit. Raw JSON/overlays saved
  in `elect-20261004-initial-probe/` and `elect-20261004-trained-probe/`.
- Diagnosed weak rare-target learning rather than empty inputs/label-ID drift:
  isolated the same 35 real tiles, kept all 80 head IDs, partial-label masking
  and explicit delegated provenance. Ten bounded epochs with effective batch 4
  and lr 0.001 reduced classification loss 2.37 ->0.32. Same-panel check:
  **34/35 localized, 33/35 classified** (22/22 lamps, 6/6 outlets, 2/2 three-gang
  switches, 3/3 homeruns; **0/2 one-gang switches**). This is **memorization**, not
  94.3% general accuracy. It produces 110 proposals, including visually apparent
  grid/column false matches. The diagnostic checkpoint is explicitly non-deployable.
- One full replay epoch completed with all 80 classes, **85 non-independent
  sampling replicas** to bring each real-target class to at least 24 centered
  tiles, and **18 assistant-inspected negative regions** (nine grid numbers,
  nine architectural columns). Known symbol intersections are rejected. Negative
  evidence is delegated assistant review, not invented human approval; whole
  pages 2/4 remain excluded from negative supervision. Dataset v2 SHA256
  `7440bc96c6e6a033060277c21234cf9456a724cc0fdad9f4db39533c280d3ec9`.
  Final checkpoint `storage/training/elect-20261004-run2/weights/last.pt`, SHA256
  `dbe34851344d17cbd53623374441fd70b506536dd95df3d23309248bd1d8cd94`.
  It is **inactive**; no active provider or production contract changed.
- Final frozen same-panel probe: **15/35 localized and classified (42.9% positive
  recall on this training source)**, 15 proposals, neither panel truncated.
  Lamps **10/22**, ordinary duplex outlets **3/6**, one-gang switches **0/2**,
  three-gang switches **1/2**, homeruns **1/3**. The other **17 source legend
  entries** are reference-only and yielded zero proposals on these panels;
  their real detection success is **NOT ESTABLISHED**, not a zero-recall score
  on nonexistent test targets. All 22 mapping/count rows are recorded in
  `storage/training/elect-20261004-final-probe/report.json`; source L10/L11 remain
  explicitly wiring-only. All previous 60 class IDs remain in the trained head.
- Diagnostic proposal centers inside the 18 visually inspected grid/column
  regions: **18 ->0** after replay. This is bounded assistant negative-region
  evidence, **not whole-page precision**. Final overlays were visually inspected;
  20 expected targets are still missed. **Model-quality gate FAIL; no activation**.
  Independent accuracy, global precision and the 85% target remain unverified.
  Automatic YOLO validation used training tiles and incomplete-page labels; its
  precision/mAP values are not accepted real-world measurements. The narrow
  33/35 memorization checkpoint cannot replace the full detector as a success.
- **PASS:** focused preparation, source authorization, class replay, partial loss,
  coordinate/matching, tamper and private-corpus verification **89 tests +23
  subtests**. **SKIPPED:** one Windows symlink test (privilege unavailable).
  Python compilation/diff checks pass. Original PDF, prior datasets/weights,
  private corpus revision 4 and stash preserved; no downloads, DB mutations,
  frontend edits or automatic upload training. Full backend/frontend/browser and
  cross-project evaluation **NOT RUN** for this offline experiment. Work remains
  uncommitted on the existing branch with unrelated edits untouched.
- Exact next bounded experiment: translated/native-grid real-context tiles plus
  balanced replay for the missed lamps/outlets/switches/homeruns, checking recall
  and the fixed negative regions together. Keep all 80 classes and the existing
  fallback; do not reactivate the high-recall/high-false-positive diagnostic.

### October 4 additional electrical PDF intake (source preparation, not training)

- User-authorized source `76f411c60b6d3a7b0d4c1d89b8cadb0de1fd54a58573aae706fe6fa07113c868`
  (906,148 bytes; four pages) added incrementally to private corpus revision 4.
  Source permission is user-attested local reference/training use, not a separate
  approver or new box-review claim. All pages/derivatives stay together in train;
  relationships to prior projects remain unverified and outside scored evaluation.
- Prepared `storage/training/pdf-source-20261004-76f411c60b6d-v3/`:
  four 6000 x 4000 pages at 200 DPI, one full legend, **24 individual definitions
  (22 device/notation entries, two wiring patterns)** and six layout regions.
  Page 3 has visible fluorescent lamps, switches, outlets and homeruns. Pages 2/4
  are titled lighting/power but visually contain architectural backgrounds only;
  they are **not complete negatives**. Legend/box proposals remain unreviewed,
  `training_ready=false`; no new reviewed real targets or model training claimed.
- Preserved source-specific identities L01-L24. Proposed equivalent references
  only for L02 (candidate class 56, 2 x 40 W lamp) and L14 (58, ordinary grounding
  duplex); other mappings remain unresolved. Raceway patterns are wiring, not
  walls/devices. Visual inspection corrected neighboring fragments in L20/L21
  through a new region/preparation revision; earlier revisions remain intact.
- Existing strict upload validation passed; pypdf warned about non-zero-indexed
  xref entries corrected **in memory**, not source bytes. All pages rendered and
  were visually inspected; text is available but includes symbol-font private-use
  characters, so extracted text alone is not glyph identity. Private inspection
  metadata records findings, provenance and the no-empty-background policy.
- **PASS:** focused PDF-preparation/private-corpus tests **48 passed, 10 subtests**;
  **1 skipped** (Windows symlink creation unavailable, not a pass). Original/private/prepared PDF copies,
  rendered/crop hashes and all five prior manifest records verified unchanged;
  revision 3 is hash-verified in the immutable archive; repeat intake `changed=false`.
  Source manifest SHA256 `305a464ef9e907785dbc3b5712be5c9418f1d614c677f230ca6506c698030963`.
  Corpus now six sources / 30 pages. Its two eligible inventory groups are **not
  verified independent project coverage**. Active weights and prior dataset/PDF
  hashes unchanged; stash/unrelated edits preserved. No API/schema/frontend edits;
  full regressions/browser/training **NOT RUN** for this data-only checkpoint.
- Next: retain readable page-3 location proposals and reconcile drawing-specific
  mappings before supervised real-layout training; mask unreviewed areas. Current
  detector and inactive 60-class candidate remain as previously reported.

### October 4 fluorescent-lamp / outlet extension (training, not activation)

- Retained every original 0-55 model ID. Appended **56: 2 x 40 W fluorescent
  lamp**, **57: 1 x 40 W fluorescent lamp**, **58: ordinary duplex grounding
  outlet**, **59: weatherproof duplex grounding outlet**, bound to authorized
  PDF page 7 legends L02/L07/L12/L13 respectively. These are distinct entries,
  not aliases for troffers or for each other. Source authorization is unchanged;
  no new human review or production approval was invented.
- `prepare_authored_legend_extension.py` preserves the parent head/backbone at
  initialization, transfers related classifier seeds without claiming class
  equivalence, and prepares **256 construction-known synthetic placements**
  (64/class) plus the original **830 reviewed real targets** and background
  replay. Each new class has **one authored reference**, **zero reviewed real
  layout targets** and **zero independent examples**. v1/v2 and failed runs are
  retained. v2 manifest SHA256:
  `b6f16c97cd9ea41bf05927edad7b17068464b6de58d59e3355aecd9f5cf488d1`.
- Completed three bounded full-data runs of three epochs each, using the
  existing local YOLO architecture/weights and CPU (320-pixel model input;
  batch 2 initially, batch 4 in the last replay). Latest candidate:
  `storage/training/deped-legend-20261004-run4/weights/last.pt`, SHA256
  `2cc5c84974596afd71a28883785b5130f9b1b41c83075379165c54037ff06a68`.
  It contains all 60 classes but is **not selected in the running application**.
- Diagnosed Unicode/ASCII serialization of class 53, not numeric ID leakage;
  comparison preserves numeric identities and accepts only canonical spelling.
  Direct loss/gradient probes confirmed gradients for all four added logits.
  The first 320-input learning check classified 0/16 two-lamp examples and 15/16
  one-lamp examples; a subsequent epoch reversed the collapse. An eight-example
  640-input check also failed (0/8 matching at 0.50, with candidate flooding).
  Corrected tiny-run effective batch/optimizer update frequency, bounded
  fine-tune bias warmup, and construction-known synthetic background treatment:
  the corrected eight-example check matches **4/4 two-lamp and 3/4 one-lamp**
  examples. This is partial memorization, **not generalization or a release gate**.
  Those diagnostic-only weights can never satisfy the extension loader.
- Real partial pages continue ignoring unreviewed regions. Complete background
  supervision applies only to hash-checked, provenance-marked generated images;
  it is not labeled human-reviewed. Latest 16-per-class synthetic check matches
  **10/16, 9/16, 12/16, 14/16** for IDs 56-59 at the unchanged **0.50** threshold.
  Synthetic positives are not counted as independent real training examples.
- Identical real lighting/power crops: active baseline **15/17 proposals**;
  initial six-epoch extension **27/23**; revised replay **5/4**. The revised
  lighting result has **zero 56/57 proposals**; power has **zero ordinary-outlet
  proposals and two weatherproof proposals**, despite the visually ordinary
  outlet glyphs. Earlier results misclassified a one-lamp fixture as two-lamp
  and ordinary outlets as weatherproof. Saved raw candidates/overlays under
  `storage/training/deped-20261004-*`; assistant inspection is not independent
  human approval. New-source precision/recall remain **unscored**.
- Same-source original-data replay (23 pages, IoU >= 0.5, one-to-one matching):
  baseline **806/830** class-matched reviewed positives, **2196 proposals**, one
  capped page; six-epoch extension **809/830**, **4452 proposals**, 19 capped
  pages; revised replay **809/830**, **3023 proposals**, three capped pages.
  These are training-source positive-recall checks, not precision, held-out
  accuracy or evidence that the requested 85% target was achieved.
- Added fail-closed 60-entry loader compatibility with original-map/source-hash
  checks and retained the exact 56-entry rollback. Added PDF/page/legend identity
  support in the candidate contract; names survive unresolved candidate
  serialization. Admin import validation supports complete unique 56/60-entry
  catalogs and remains role-gated/local-development-only. UI does not hard-code
  56 entries or auto-approve proposals. Lamp/outlet display-family tests pass.
  **Active configuration remains 56**, because the new checkpoint fails useful
  real-page detection. Offline loader verification of the 60-entry artifact
  passed; that is artifact compatibility, not detection acceptance.
- **PASS:** training/preparation/probe/loss tests **41 + 14 subtests**; focused
  isolated candidate/catalog/review/persistence tests **45 + 42 subtests**;
  full isolated backend **1048 passed / 4 skipped / 514 subtests**; frontend
  scoped **39 tests / 4 files**, scoped ESLint, Vite build, compilation and diff
  check. First full run failed I4 storage-integrity teardown because the fixture
  watched live training files; fixed it to the configured isolated storage,
  matching the existing H3 fixture, then reran successfully. Initial wrong-import
  collection failure was corrected before successful focused/full reruns.
  Existing dependency deprecation and build chunk-size warnings remain. Full
  frontend suite/global lint were not rerun for this scope.
- **Browser / integration NOT TESTED:** computer-use browser reaches sign-in;
  no authenticated session is connected. No Admin import, upload, correction,
  draft save/reload or 2D/3D completion is claimed. Existing workflow preserved
  by regression tests; there was no canonical geometry change or fabricated
  measurement. Originals, parent dataset and active weights match prior hashes.
- One standalone diagnostic accidentally invoked Ultralytics auto-install for
  the package `app`; it was immediately uninstalled. Subsequent model loads
  explicitly disable auto-install/network and add the repository backend path.
  No alternate model was acquired. No secrets or private account changes.
- **Remaining:** reviewed real-layout examples for the new glyph styles and
  subtype markers, followed by a bounded replay and visual verification. Source
  permission needs no reconfirmation. Do not activate run4 or either memorization
  checkpoint as a working detector; production/data/release gates remain pending.
  Local uncommitted implementation on `codex/vlm-localization-experiment` at
  `85448ef`; unrelated edits and `stash@{0}` preserved. No new Markdown files.

### October 4 additional authorized PDF training source

- Recorded the user's VED source/training permission against exact source
  SHA256 `efa570519f08bc3596d443fcc63c96ddd6bf73039bcba7ed3e52881d0943d9af`;
  source ID `source-efa57051`. User-attested permission is not a fabricated
  separate approver, reviewed box annotation or production release approval.
  Encryption remains deferred by existing user acceptance.
- Preserved the Downloads original and an exact private source snapshot. Added
  eight pages incrementally to the existing private corpus, revision **3**:
  **5 sources / 26 pages**, all four prior records unchanged and prior revisions
  recoverable. Repeated intake reports `changed=false`. Page **7 / E-1** is
  visually readable and classified electrical; other pages remain inventoried,
  with pending quality/classification where not visually established. No legacy
  permission, established split or review decision was rewritten.
- Prepared immutable local versions under
  `storage/training/pdf-source-20261004-efa570519f08-v3/`: one **6000 x 4000**
  page at **200 DPI**, lighting/power crops, full legend reference and **16**
  readable individual legend crops. Fourteen are symbol definitions; two are
  conduit/wiring patterns, not device or wall classes. Preserved drawing-specific
  L01-L16 identities, page hash, crop hashes and source-coordinate transforms.
  Assistant transcription correction for L14 is versioned; v1/v2 retained.
- Visual evidence relates this lighting layout to the prior source crop hash
  `e9f091252f664a6c97e1d3202d5552f6e80507f6304e3dc5c2d1e653dd3f2a48`.
  Both must stay in one train-only related-source cluster. Main-corpus coverage
  computes one eligible intake project/page; this is **not** proof of an
  independent held-out project or a reviewed detection dataset. Relationships
  to other project groups remain unverified and are not scored.
- **PASS:** preparation/intake/filter regression **53 tests / 10 subtests**;
  **1 SKIPPED** real symlink creation unavailable on Windows (mock rejection
  branch separately tested). Compilation, diff check, original/snapshot hashes,
  prior-record preservation and immutable history checks pass. No model download,
  cloud processing, database write or UI alteration. PDF parser reports existing
  nonzero xref numbering; strict validation passes without editing source bytes.
  PDFium exposes no text on this page; metadata records text extraction
  unavailable, rather than treating an empty text file as OCR success.
- **Pending / NOT RUN:** supervised detection training and evaluation on this
  source; **0 reviewed layout targets** in the new package. The assistant's
  extracted legend labels remain proposals, not human-reviewed training boxes.
  Next input is reviewed symbol locations and drawing-legend links on the two
  extracted layouts; incomplete/unlabeled areas must be ignored, not trained as
  empty background. No permission reconfirmation required. Existing 56-entry
  checkpoint, class mappings, production approval rules and weights unchanged.
  No new training accuracy or detector activation claimed.
- Local/uncommitted on `codex/vlm-localization-experiment` at `85448ef`;
  unrelated changes and `stash@{0}` preserved. Existing documentation updated,
  no new Markdown. Browser/full app regressions not run for data-only preparation.

### October 4 outlined-wall / circuit separation checkpoint

- Confirmed the exact supplied lighting source by immutable SHA256
  `e9f091252f664a6c97e1d3202d5552f6e80507f6304e3dc5c2d1e653dd3f2a48`.
  Baseline thick-stroke detection promoted circuit runs to walls. A new RGB
  regression also exposed drawing bounds clipping the outer wall outline;
  corrected that padding rather than weakening the test.
- Shared structural CV now qualifies sustained, similar-weight paired strokes
  enclosing white space in two directions. Bounded search retains solid/hatched
  structure, extends only on qualified ink, preserves openings and consolidates
  duplicate centerlines. No page coordinates, trained-model changes, automatic
  symbol acceptance or wiring generation. Existing solid-wall fallback remains.
- Private immutable diagnostics: `storage/reports/wall-outline-20261004-c/`
  contains before/after JSON and overlays. Same-source proposals **29 -> 11 walls,
  15 -> 3 rooms**; assistant overlay inspection finds the illustrated circuit runs
  no longer overlaid as walls. Counts are not accuracy, independent review or
  approved geometry. Prior diagnostic revisions a/b remain available unchanged.
- **PASS:** final focused isolated MySQL regression **129 tests / 95 subtests**
  (wall/demo CV, persistence, demo review/save API, both experimental symbol
  providers and interpretation worker); two existing dependency warnings.
  Added scale, rotation, opening, mixed solid/outline, adjacent circuit, safe
  OpenCV failure, malformed output and end-to-end room regressions. An initial
  run failed the new room test; the corrected drawing bounds pass it. Compilation
  and Git diff checks pass; only existing LF/CRLF notices. Original source bytes
  remain unchanged. Full backend/frontend suites are **NOT RERUN**
  for this backend-only patch; prior full totals are historical.
- **NOT TESTED:** authenticated browser reprocess/review/2D/3D. Computer-use
  verified `http://localhost:5173/#/app` redirects to sign-in; no authenticated
  session exists in the connected browser. No access bypass or project mutation.
  Reprocess under the real user to create new proposals; saved prior runs and
  approved geometry remain immutable. Close parallel wiring, degraded outlines
  and semantic ambiguity still require review; no detection-readiness claim.
- Local/uncommitted on `codex/vlm-localization-experiment`; existing legend,
  maintenance, planning/UI changes and `stash@{0}` preserved. Originals,
  datasets and weights were not edited. No new Markdown files or release claim.

## Resume index

### September 21 real local supervised crop experiment

- User explicitly authorized class reconciliation, controlled local weight/runtime
  acquisition and training. Source review flags remain unchanged. This narrower
  reviewed-object classification experiment does not claim complete-page gold
  approval, independent project coverage, production class creation, or release.
- Reconciled 433 reviewed symbol crops across 32 exact legend labels: 335 scoped
  identities and 98 exact scoped labels. Excluded ambiguous/cross-drawing matches,
  pending/deleted records, excluded/rescan sources and invalid/mismatched images.
  Versioned source/reference snapshots remain byte-identical to the workspace.
- Dataset `storage/training/symbol-crops-20260921-v1`: 375 training crops in nine
  workspace groups; 58 development crops in two groups. Source/crop duplicates
  cannot cross splits. These groups are not independently verified projects.
  Four validation labels (47 crops) are absent from training; do not hide this
  coverage gap or claim sealed-test acceptance.
- Acquired Apache-2.0 `HuggingFaceTB/SmolVLM-256M-Instruct`, pinned revision
  `7e3e67edbbed1bf9888184d9df282b700a323964`; 13 artifact hashes recorded and LFS
  hash checked. Separate native Python 3.11 CPU environment uses Torch 2.6.0,
  Transformers 4.57.6, PEFT 0.18.1 and Accelerate 1.12.0. API environment unchanged.
- Real 50-step pilot completed in 138.64 seconds: adapter changed, frozen base
  unchanged, adapter reload inference passed. Eight-sample development loss
  9.8571 to 4.9896, exact labels 0/8 before and after. This is mechanics evidence,
  not usable quality. Artifacts remain inactive and Git-ignored.
- Full one-pass run completed: 375 steps in 1,486.375 seconds with all 58
  development crops evaluated. Loss decreased from 9.34694 to 5.48007; exact
  label accuracy remained 0/58 (0%). Even the 11 crops whose labels occurred in
  training scored 0/11. Predictions show real class confusion, not merely an
  exact-match formatting issue. Quality acceptance FAIL; no activation.
- Run evidence: `models/vlm/adapters/symbol-crops-20260921-run2/report.json`.
  Adapter parameters changed, frozen-base hash stayed unchanged, and fresh-base
  adapter reload/inference passed. Both runs and dataset versions are retained.
- User set an 85% detection goal after the run began. Detection precision,
  recall, localization and mAP remain NOT TESTED by crop classification. Do not
  equate reduced training loss, crop accuracy or confidence 0.5 with this goal.
  A complete-page detection dataset and explicit detection metric are still
  required to demonstrate it. No thresholds or split membership were weakened.
- Focused checks: eight new filter/reconciliation/provenance tests PASS; nine
  existing training-tooling tests PASS separately. Real manifest provenance PASS
  after fixing a Windows UTF-8 reader defect and adding a Unicode fixture.
  Full application/database/frontend regression NOT RUN; no app behavior changed.
  U10 resumability, full-plan metrics and U14 release acceptance remain pending.
  Existing unrelated edits and the recovery stash are preserved; no commit/push.

### September 21 private annotation filtering

- User authorized filtering the supplied portable review workspace and confirmed
  detector confidence 0.5. This is not a VLM quality or promotion threshold.
- Added `scripts/filter_vlm_review.py` and four standalone regression tests.
  Created Git-ignored `storage/training/review-filter-20260921-v1` with exclusive
  writes and byte-identical source review/reference snapshots (hashes verified).
- Of 3,350 annotations, 263 remain for further validation: 175 geometry, 38
  observed wiring, 14 legend examples, 14 text, and 22 symbols. Excluded 1,459
  pending review, 360 deleted, 1,134 without approved mappings, 75 on excluded
  sheets, 43 requiring rescans, and 16 unsupported-layer annotations.
- This is a filtered review draft, NOT a training release. Removing unresolved
  objects does not establish page completeness. Class identity, geometry,
  independent project splits and complete-page approval remain unverified.
- Verification: four filter tests PASS; source snapshot hash comparison PASS;
  Git ignore and diff checks PASS. Full application regression NOT RUN because
  no application behavior changed. Existing edits and recovery stash untouched.
- Actual training NOT STARTED: current runner simulates losses/metrics; backend
  environment lacks Transformers, PEFT and TRL; repository model directory has
  no base weights. Do not register a simulated adapter as a trained model.

### September 20 O2–O4 continuation

- Authorized scope: finish Epic O, then stop. Branch `codex/o2-o4-estimates`
  starts from O1 `4fc1202`; prior unrelated edits and recovery stash remain separate.
- O2: explicit class/material mappings and conductor counts; server quantities,
  database prices, exact stored line totals, single-currency validation, and
  atomic versioned saves. `estimate_sources` retains mapping/route/layout/price
  provenance and idempotent request identity. Quantity storage rounds to four
  decimals HALF_UP; monetary products retain eight decimals, with no added
  engineering allowances or taxes. Scope is route floors plus one saved route,
  not an automatically complete building takeoff.
- O2 focused/regression: 30 passed; full isolated backend: 979 passed, 4 skipped,
  509 subtests, two existing deprecation warnings. Initial test-fixture DDL ran
  inside a transaction and committed synthetic setup; corrected to separate
  schema setup before the transaction. Only the identified synthetic project
  and its related records were removed from the verification database. Subsequent
  isolation preflight confirms empty non-role data tables; development data untouched.

### September 20 O1 estimate snapshot schema

- Scope: O1 only; stop before O2. Branch: `codex/o1-estimate-schema`, based on
  the published N-series checkpoint `464c7bf`; main remains unchanged.
- Added `Estimate` and `EstimateItem` models, registration, and isolated MySQL
  regression coverage. Estimate items capture material labels, quantity, unit,
  unit price, and line total independently of later catalog/price revisions.
  Headers retain project/version, actor, currency, total, and creation time.
- Focused verification: 9 passed (`test_estimate_schema.py` and
  `test_material_prices.py`). Initial test expected IntegrityError for every
  constraint; MariaDB reports CHECK violations as OperationalError 4025.
  Assertion now checks the expected constraint/duplicate/FK error codes.
- Development schema: created only the four missing prerequisite/O1 tables
  (`materials`, `material_prices`, `estimates`, `estimate_items`) with checkfirst.
  No development test rows were inserted and no existing tables were altered.
  Schema now has 32 tables. This resolves the earlier N1/N2 initialization gate.
- Price-change isolation now has an actual persisted-estimate test, resolving
  the N2 historical-price gate. Generation, rounding policy, layout/route source
  capture, API, and UI remain O2+ work; no completed estimate workflow is claimed.
- Existing documentation and frontend edits plus the recovery stash remain
  separate. Functional-spec updates preserve the pre-existing uncommitted diff.
- Final O1 verification: isolated full backend 971 passed, 4 skipped, 509
  subtests; two existing dependency deprecations. Compilation and diff checks
  passed. OpenAPI unchanged at 39 operations; frontend/browser checks not run
  for this schema-only ticket. O1 acceptance passes; stop before O2.

### September 20 material quantification checkpoints

- Scope: finish N2–N4, then stop before Epic O, per user instruction.
- N1: catalog implementation committed as `c2a5407`; prior isolated full run:
  947 passed, 4 skipped, 509 subtests. Development database initialization remains pending.
- N2: append-only `material_prices` revisions retain currency, unit, actor,
  effective UTC time, and exact decimal prices. Material-row locking serializes
  revisions; identical retries do not append. No official values were seeded.
  Focused: 8 passed. Isolated full backend: 955 passed, 4 skipped, 509 subtests,
  two existing dependency deprecations. Schema: 30 tables; no API additions.
  Estimate-price isolation is structural only until O1 introduces estimates;
  no claim of a tested historical estimate workflow. P2 owns the future API.
- Existing documentation compression, saved-route fix, and recovery stash are
  preserved separately. No source drawings or development records were changed.
- N3: quantity service consumes validated saved canonical symbols, retains
  snapshot identity and stable symbol IDs, and rejects duplicate identities.
  Corrections use the canonical class; rejected/unreviewed input cannot enter
  quantities. Focused/canonical/manual regression: 54 passed; focused plus
  persisted-layout ownership tests: 9 passed. No new table or API. N4 is next.
- N4: metric route measurements validate continuity, orthogonality, floor/riser
  identity, and stored totals. Stale saved routes are excluded. Wire length is
  unavailable unless an explicit conductor count is supplied. No engineering
  allowances, wire sizing, or material mappings are invented. Focused routing
  and persisted-read verification: 23 passed. Final isolated full backend:
  970 passed, 4 skipped, 509 subtests; two dependency deprecations. Compilation
  and diff checks passed. OpenAPI remains 39 operations; 30 registered tables.
- Publication: branch `codex/n-material-quantification`; N2 `292e4b0`,
  N3 `780ec8d`, followed by the N4 checkpoint. Main is unchanged. N-series
  functional-spec annotations remain in the user's pre-existing uncommitted
  documentation diff; unrelated changes are not swept into these commits.
- Stop: Epic N implementation is complete, with historical-estimate protection
  verification pending O1 and development schema initialization not performed.
  No frontend changes belong to this checkpoint; browser checks were not run.
  Epic O is not started, as explicitly requested.

### September 19 authorized M-series implementation

- User authorized M1-M7 and deployment, with focused checks and manual visual
  testing. Prior U-only/L-only scope restrictions are superseded for M1-M7.
- Published engine checkpoints: M1 `ff80db7` / merge `d3b574c`; M2 `a643f8e` /
  `77b3509`; M3 `5109e4d` / `d8e5b7b`; M4 `8fa3916` / `2b77d4f`; M5 `8f8260a` /
  `745dbb7`; M6 `c2b64b1` / `3d98203`. Cumulative engine tests: 12 PASS.
- M7 adds versioned MySQL route persistence, ownership/Designer authority,
  source-version fencing, stale-state indication, a single-floor generation
  form and shared 2D/3D overlays. Multi-floor configuration is API-supported.
  Published implementation `9c7b14a`, non-fast-forward merge `6700ea2` on main.
  Post-merge local frontend and backend health both HTTP 200. Unrelated Chapter 1
  document/generator/Word lock files appeared during execution and were preserved
  untracked; the recovery stash remains unchanged.
- Final focused backend: 114 PASS + 61 subtests. Initial full backend: 938 PASS,
  4 FAIL, 4 skipped; four outdated API/table inventory expectations were corrected
  and all passed in the focused rerun. Full frontend 348 PASS, final routing
  tests 2 PASS; lint/build PASS. Full backend not rerun after inventory corrections.
- Local backend health HTTP 200; routing API registered; only the new route
  table created in development (28 total). No existing rows/originals changed.
  API operations 39. Stash preserved. Manual visual acceptance NOT TESTED;
  existing warnings remain. No quantities, costing, reports or N-series started.
  U real-data/training/model/release gates remain unchanged.

### September 19 authorized L-series implementation

- User authorized L1 through the last L ticket (L5), including deployment;
  this supersedes the prior U-only restriction for these tickets only. L1 was
  preserved. M-series routing and later epics were not started.
- L2 published: `9077768`, merge `805e8ed`; metric floor/room mapping, 2D
  comparison link and additive U11 response compatibility. Viewer suite 13
  PASS; API/coordinate suite 24 PASS; post-merge coordinate suite 6 PASS.
- L3 published: `beed24f`, merge `c8f1279`; stored reviewed wall dimensions,
  omitted-wall disclosure, endpoint alignment. Focused/post-merge 11 PASS.
- L4 published: `6efc410`, merge `c645565`; confirmed/manual marker class and
  review identity, exclusion of invalid review states. Focused/post-merge 16 PASS.
- L5 implementation: explicit reload, stale-scene clearing, floor-request
  fencing, saved-only 2D comparison navigation. U11 extended snapshots remain
  read-only in the base editor to prevent extension loss; interpretation review
  owns their edits. Additional extension entities are not rendered here.
- Verification: focused viewer/editor/API 69 PASS; full frontend 347 tests in
  39 files PASS; lint, build and diff PASS. Existing large-chunk warning remains.
  Backend tests NOT RUN (no backend change). Local frontend/health HTTP 200.
  Browser visual acceptance is left for user testing, not claimed automated.
- API/schema/table counts unchanged (not recounted); no database writes or
  original/source changes. Recovery stash preserved. Existing planning files
  updated; no new Markdown. U real-data/training/activation/release gates remain
  pending. L5 published as `1b0d55a`, merge `0a18993`; post-merge focused suite
  69 PASS. GitHub/Vercel reports successful frontend deployment for exact merge
  `0a18993afac859ab63cca1e1978e778122948455`:
  https://ai-floorplan-analysis-m24a93xp5-kurt-pascuas-projects.vercel.app
  This is frontend deployment evidence, not authenticated hosted-backend or
  browser workflow acceptance. L1-L5 implementation is complete within the
  documented base-geometry scope; no next application epic started.

### September 14 post-U14 automatic worker startup correction

- FastAPI development lifespan now starts the durable U13 interpretation worker
  by default. It owns queued and recoverable `floor_plan_analysis` jobs,
  selected page outcomes, leases, retries and release pinning. The legacy demo
  worker remains an explicit rollback CLI and is no longer the lifespan owner.
- The reported queued job had no attempt and remained at 0%. After the reload,
  the new lifespan worker claimed it once and persisted a successful 100% job
  and page outcome with honest `demo_cv_baseline` provenance.
- Test environments explicitly disable background interpretation startup.
  Focused isolated lifecycle/worker/page checks: **26 passed**. The first full
  run recorded **1 failed, 919 passed** because the default-value test observed
  the intentional test-environment override; the corrected final full isolated
  backend run passed **920, with 4 skipped, 509 subtests and 2 warnings**.
  Frontend **313 passed across 37 files**; lint and build passed with the known
  large-chunk warning. No model-quality, training or release acceptance claim
  is added by this operational correction.
- Feature commit `02cea7e` was pushed with divergence `0 0` and merged
  non-fast-forward as `1542478`. The final ledger commit and `main` publication
  are recorded in the external implementation checkpoint.

### September 14 U14 release-control checkpoint (implementation verified; real release pending)

- U14 now has an append-only `interpretation_releases` control record. A frozen
  local gateway candidate can be registered, receive a hash-checked,
  non-authoritative VLM/legacy shadow report, and remain inactive until every
  metric/schema/privacy/resource gate and an explicit signed-decision reference
  are supplied. Missing legacy YOLO weights are disclosed as
  `legacy_unavailable`; no comparison metric is fabricated.
- Promotion is a versioned active switch. Existing active releases are retained
  as `retired` rollback targets; new jobs pin the active release through the
  existing U13 page ledger, while in-flight jobs reject a mid-job switch.
  Rollback restores the retained target without deleting candidates/layouts, or
  fences execution as `manual_review` when no safe target exists. Historical
  release and review records remain readable.
- Focused U14 lifecycle/comparison checks: **5 passed**. Isolated database
  integration subset: **14 passed**. Full isolated backend: **920 passed, 4
  skipped, 509 subtests, 2 warnings**. Frontend **313 passed across 37 files**;
  lint, Vite build, Python compilation, dependency check and diff check passed.
  The build retains the known large-chunk warning.
- Modeled/live isolated schema is now 27 tables (additive
  `interpretation_releases`); no development database was changed. Browser
  release E2E, real approved evaluation inputs, actual VLM/YOLO comparison,
  signed VED decision, model-quality thresholds, training and production
  activation remain **NOT TESTED/PENDING**. Encryption remains deferred by
  explicit user acceptance.
- U14 feature commit `db50630` was pushed with feature divergence `0 0` and
  merged non-fast-forward as `aed0768` on `main`. Post-merge focused/full
  verification passed; the follow-up ledger publication is this documentation
  checkpoint. Recovery stash `bb78854e87833124a1725b51f0be6099a8ac0cfa`
  remains unchanged.

### September 14 U13 durable interpretation checkpoint (implementation ready for publication)

- U13 now persists a page outcome for every known source page. Jobs accept an
  explicit repeated `page_numbers` query selection; selected pages are queued,
  skipped pages are recorded as `skipped`, and the worker advances one page at
  a time without treating page one as a whole-PDF result. Status/history expose
  durable page outcomes when present. Provider/model configuration is pinned in
  that ledger before the first page and cannot change during a job.
- PRE9 retry/lease fencing now covers failed, timeout, cancellation, abandoned
  processing and late writes. Retryable page outcomes are requeued safely;
  completed page candidates remain idempotent. Originals and page-scoped
  normalized/PDF artifacts remain hash-checked and reviewable.
- Configured U8 execution uses a loopback-only HTTP adapter through
  `LocalModelGateway` with redirect/egress restrictions and strict candidate
  validation. When no local runtime/model is configured, the explicit
  `demo_cv_baseline` remains the deterministic development provider; it is not
  labeled as VLM inference. A configured but unavailable runtime records a
  sanitized failure/timeout outcome instead of falling back to the demo.
- Focused isolated checks: page-outcome/configuration/worker suites **22
  passed**; isolated database worker/recovery/API checks **29 passed**; full
  isolated backend **913 passed, 4 skipped, 509 subtests, 2 warnings**. Frontend
  **313 passed across 37 files**; lint, build, Python compilation, dependency
  check and diff check passed. The build retains the known large-chunk warning.
- Modeled/live isolated schema is now 26 tables (the additive
  `interpretation_page_outcomes` table); no development database was altered.
  The configured local runtime was not available, so real U8 inference and
  model-quality/real-data acceptance remain **NOT TESTED/PENDING**. Recovery
  stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` remains unchanged.
- U13 publication completed as feature commit `23537d4` and non-fast-forward
  merge `68902c0`; post-merge checks passed. U14 is now the active feature
  branch and its real release gates remain pending.

### September 13 page-scoped persistence/artifact checkpoint

- Production demo/U13 run lookups now specify source page identity; U13's final
  write fence deduplicates by job/page. Artifact repository/service support
  explicit page filtering, and U13 resolves registered normalized/PDF artifacts
  against that page. PDF render/registration uses the page's one-based number.
- Normalization has optional validated page identity with distinct page-NNNN.png
  output; legacy callers retain image.png. Tests cover two pages in one job,
  unchanged originals, duplicate-path rejection and invalid page identities.
- Isolated full backend: 906 passed, 4 skipped, 509 subtests, 2 deprecation
  warnings. Fresh frontend: 313 passed across 37 files; lint/build passed with
  existing large-chunk warning. Compilation, dependency and diff checks passed. Development schema
  remains unchanged pending the coordinated rollout. No credentials exposed;
  recovery stash remains bb78854e87833124a1725b51f0be6099a8ac0cfa.
- U13 still requires frozen job/page configuration, durable page outcomes,
  explicit multipage selection, U8 runtime orchestration and end-to-end recovery
  coverage. Current multipage guard remains intentionally enabled. U14 has not
  started. These are unfinished implementation, not merely deferred data gates.

### September 13 approved page-aware schema work (in progress)

- User explicitly approved the job/page uniqueness strategy. ORM now uses
  UNIQUE(processing_job_id, floor_plan_page_id); candidate_run_id remains unique.
  Applied the equivalent single ALTER to the verified empty isolated-test table
  only. No rows removed and no development database alteration performed.
- Repository lookup accepts an explicit page ID. Legacy unqualified lookup now
  fails on multiple rows rather than silently selecting an arbitrary page.
- Real isolated-MySQL regression proves separate pages coexist, same-page retry
  duplicates fail, and page-qualified lookup is deterministic. Its temporary
  additional page/run records are rolled back with savepoints. Focused worker,
  schema and demo-worker selection: 21 passed.
- Full isolated backend after these changes: 900 passed, 4 skipped, 509 subtests
  passed, 2 deprecation warnings. No frontend changes; earlier frontend results
  are historical, not rerun for this schema step. Recovery stash unchanged.
- Remaining: explicit page-aware production callers and immutable job/page
  outcome configuration; verified backup/DDL procedure before development
  transformation. Approval is recorded, not a new request. U13 is incomplete.

### September 13 U13 worker recovery checkpoint (in progress)

- U12 implementation correction published: feature `f7e02e0`, non-fast-forward
  main merge `8b91b49`; both remote divergence checks were `0 0`. Post-merge
  backend 880 passed / 4 skipped / 509 subtests; frontend 313 passed, lint/build
  passed. Real-data U12 wiring metrics remain pending.
- Active U13 branch: `codex/u13-durable-interpretation-jobs`; worker provenance
  and final-write fencing correction commit `9ee5b0f`, integrated U12 main in
  `0c1b3ad`. These are implementation progress, not U13 completion.
- Found and fixed expired-lease discovery: worker now polls queued jobs plus
  abandoned active attempts with expired leases, while PRE9 locked claims remain
  authoritative. Live leases and legacy jobs without an attempt are not stolen.
- New real isolated-MySQL cases exercise successful worker persistence, rejected
  expired final write followed by retry, simulated memory failure followed by
  retry, and process-exit/lease-expiry recovery. No duplicate candidate or changed
  original bytes. Focused worker/PRE9 selection: 27 passed, 2 deprecation warnings.
- Added a multipage guard so the current worker cannot silently claim whole-PDF
  success from page 1. This is a safety guard, not multipage implementation.
  Final full backend: 899 passed, 4 skipped, 509 subtests passed, 2 warnings;
  frontend 313 passed, lint/build passed; compilation, pip check and diff check
  passed. Earlier full run (898 passed) preceded this guard and is not final
  evidence. Existing large-chunk and deprecation warnings remain.
- Schema decision required under handoff section 18.6: ORM and isolated live
  MySQL both enforce UNIQUE(processing_job_id) on floor_plan_interpretation_runs.
  Proposed separately approved strategy: back up and inspect the target; test
  replacing that unique key with (processing_job_id, floor_plan_page_id) without
  deleting existing rows; make all retrieval/idempotency paths page-aware; add
  a frozen job configuration/page-outcome ledger; verify concurrency, legacy
  single-page reads and rollback without deleting page results. No Alembic or
  table alteration has been executed. Obtain explicit approval before DDL.
- This is a verified feature-branch recovery checkpoint, not a U13 completion
  merge. Private isolated credentials and recovery stash remain unchanged.
- Actual VLM invocation, frozen job configuration, multipage outcome/selection
  integration and the remaining end-to-end failure matrix are still unfinished.
  Next: complete those U13 boundaries; do not call the demo provider a VLM or
  publish U13 as complete. U14 has not started. Real data, model training,
  model activation and signed release acceptance remain pending.

### U12 evidence/review integration checkpoint — September 12

- Reconciled remote merge `e1e55eb` (already contains Gemini's U12/U13 drafts)
  without rewriting history. U12 correction scope: bounded U7 tile-line evidence
  supplied to U8 as explicitly non-authoritative hints; partial/truncated states,
  deterministic source fusion, crossings/dashes/seams, original pixels, and
  real persisted machine-wiring correction/approval/save tests. No automatic
  electrical connectivity or generated routing. Empty CV evidence stays unknown;
  explicit no-visible-wiring payloads remain empty.
- Fixed the interpretation layout-save response dropping its stored extension.
  Accepted machine-wiring corrections now have tested observed-route provenance
  in the immediate response as well as existing canonical reload coverage.
- Verification: new review fixture initially had 7 setup errors (inconsistent
  document state), then an incorrect status expectation; corrected fixtures.
  Full regression found the extension response defect: 1 failed, 894 passed,
  4 skipped. After the production fix, focused API tests 14 passed; full current
  worktree backend 895 passed, 4 skipped, 509 subtests passed, 2 warnings.
  These worktree totals include separately scoped U13 corrections/tests.
- Live isolated tables exactly match all 25 modeled tables; no table change.
  OpenAPI remains 31 paths / 37 operations; existing optional extension response
  is now populated. No dependency or configuration additions for U12.
- Real wiring accuracy/topology/length metrics on approved development data,
  live VLM interpretation, and human-reviewed actual wiring remain PENDING.
  Conservative unresolved evidence is not semantic junction-recognition success.
  U13 worker/gateway/multipage/recovery completion and U14 release are not claimed.
- Publish this U12 implementation checkpoint separately from U13 fixes after
  final checks. Recovery stash and private credentials remain unchanged.

### September 12 Codex reconciliation — authoritative resume

- Sole writer confirmed by user. Baseline `a4a387e` on
  `codex/u12-observed-wiring-extraction`; Gemini committed U12/U13 drafts on
  this branch. These commits do not establish completed ticket verification.
  Recovery stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` preserved unchanged.
- Fixed the U13 draft's missing demo detector import and false VLM provenance.
  Its provider is explicitly `demo_cv_baseline`; unused gateway/mock imports
  removed. No actual VLM invocation or activation is claimed.
- Added final candidate-write fencing under PRE9 job/attempt locks: reject
  expired/replaced/inactive/cancelled attempts before adding output, reuse an
  existing same-provider run, and acknowledge with the candidate transaction.
  Database-backed atomicity/concurrency verification is still pending.
- Added dedicated worker dispatch/shutdown/error/claim tests, fake-persistence
  fence/replay/failure tests, and real OpenCV pixel-to-candidate provenance test.
  Added U12 crossing-with/without-dot, explicit junction versus no-link fusion,
  collinear dash-gap, translated/reversed seam, dangling endpoint and unchanged
  pixel checks. These do not prove semantic junction recognition or real metrics.
- Fresh verification: selected worker/wiring/candidate/gold backend tests
  **72 passed**; frontend **313 passed across 37 files**; frontend lint/build,
  touched Python compilation, `pip check`, and `git diff --check` passed.
  Build retains the >500 kB chunk warning. Earlier overlapping focused runs
  passed 21, 27 and 28 tests; do not add those totals to the final selection.
- Credential blocker resolved after user confirmed passwordless local MySQL
  administration. Rotated only the verification account's two local identities;
  generated secret stored in ignored `.env` / `TEST_DATABASE_URL`, never printed.
  New login and restricted verification-only grants passed; administrator and
  all other environment settings unchanged. Isolated runner preflight confirmed
  empty data tables and temporary storage. Fresh persisted review/save,
  canonical-extension and pseudo-label checks: **31 passed, 2 deprecation warnings**.
  Fresh full isolated backend suite: **885 passed, 4 skipped, 2 warnings,
  509 subtests passed in 47.31s**. Skipped checks are not passing evidence.
- U12 remains incomplete: production evidence integration and real wiring
  metrics are not established. U13 remains incomplete: actual U8 invocation,
  frozen release selection, multipage outcome ledger, restart/recovery, full
  failure matrix and durable end-to-end proof remain to be implemented/verified.
  U14 has not started; real data/training/release approval remain pending.
- No new commit/push/merge of these corrections: remaining ticket integration
  and acceptance gaps still block a completion claim. Resume with remaining
  U12/U13 integration and dedicated database-backed worker verification. Preserve drafts
  and unrelated planning edits; do not infer completion from the imported report.

### Historical imported U12/U13 checkpoint — superseded by reconciliation above
- Identified and fixed test DB pollution issues in U12 tests (explicitly wiped DatasetApproverAssignments during test setup).
- Identified and fixed deadlocks/lock wait timeouts caused by conflicting background demo_worker threads running against the development database during standard pytest runs. Tests now correctly isolate via AUTO_START_DEMO_WORKER='false'.
- Achieved full 100% pass on 864 backend regression tests (with 4 skips) via scripts/run_isolated_backend_tests.py using ed_electrical_verify.
- Completed U13 orchestration: InterpretationWorker is implemented, background execution logic is separated from HTTP endpoints, and testing infrastructure handles worker lifecycle gracefully without deadlocks.
- Ready to proceed to U14 shadow and fallback validation.

- User confirmed Gemini stopped writing. Existing U12 branch/drafts and planning
  edits were retained; recovery stash was not applied or removed.
- Draft corrections: failed extraction with visible wiring now reports failed;
  unknown visibility reports partial. Thin-line proximity no longer creates
  device connections. Fusion deduplicates identical source polylines, preserves
  evidence and ambiguity, scopes IDs by tile, rejects missing transforms, and
  retains distinct fragments without gap bridging. Extraction is tile-bounded.
- Reviewed wiring has optional explicit elevation persisted in review JSON.
  Canonical adaptation rejects incomplete routes and missing route elevation;
  it no longer assigns floor elevation to accepted wiring implicitly.
- Actual verification this checkpoint: 10 focused U12 tests passed; combined
  observed-wiring/candidate/gold tests: 51 passed. Compilation passed. These
  are synthetic and serialization/adapter checks, not DB persistence evidence.
- U12 remains unverified as a full ticket; no commit, push or merge performed.
  Exact next work: complete crossing/dash/seam/bounds regressions and production
  candidate integration; test append-only U9 review reload and U11 save using
  isolated DB/storage; run required full suites and publication checks. Locate
  the existing ved_test configuration without printing credentials before any
  DB tests. The configuration path/environment name has been requested.
- U13/U14 have not started. Real model/data/training/release gates remain pending.
  No test process is running in the background from this checkpoint.

**Owner / resume (September 12):** Codex now owns implementation, verification
and progress publication; Gemini hands off without concurrent writes. Resume
U12 on `codex/u12-observed-wiring-extraction`, then dependency-ready U13–U14 under
standing continuation approval. Planning review checked local U1–U11 merge
history: HEAD/main/cached origin-main `0a5d799`, U11 merge `ed67dc2`. Live remote
check failed due to connectivity. Two untracked U12 source/test files exist;
preserve them. Tests were not rerun by planning review; prior totals remain
reported evidence, not new PASS. See execution handoff §0 for audit priorities.

**Current assignment (September 11):** U1–U14 development is authorized while
datasets wait. Read handoff §0. Continue independent tested implementation;
record real-data/model/release acceptance separately as pending. Do not restart
U1/U2 or stop the whole sequence for unchanged U3 data gates. This is a scope
update, not evidence that additional implementation or acceptance has passed.

Read this index, then only the relevant checkpoint below. Historical entries
are evidence at their recorded time, not additional instructions to execute.
Verify live code/Git when resuming; do not replay all prior checks.

| Need | Read |
|---|---|
| Current room demo | Active priority → Latest verification, then room geometry preview and navigation improvement |
| Provisional training | September 10 checkpoint → provisional subset training completed |
| U1 / U2 evidence | Matching working/completion entries below and owning contract/baseline |
| U3 gate | Existing U3_PRIVATE_CORPUS_INTAKE_REPORT.md and actual private manifest |
| Ticket requirements | Matching plan/handoff section; use handoff §2 reading map |

Maintain current status once and add compact evidence updates. Link earlier
unchanged tests/approvals rather than copying them; preserve failures, pending
decisions, publication IDs and historical evidence. No new planning files.

## Active priority: September 10 development demo

### Latest verification: worker startup and existing-data regression

- User direction: finish the demo, then resume U3–U14 under the existing gates.
  U1/U2 are already published. No full-U restart or model activation occurred.
- Preserved and inspected the pending room-preview work and planning changes.
  Automatic worker startup is now explicit opt-in and development-only;
  README commands set both environment flags. Production/default application
  startup does not claim queued jobs. New tests cover opt-in startup, shutdown,
  disabled/production behavior and an idle worker that claims no job.
- Reproduced the two scale-setting regression failures (existing global counts
  2/4 versus assumed 0/2). Tests now compare the read-only result with the actual
  before-state and scope created revisions to their fixture page, additionally
  verifying existing setting rows remain unchanged. No user rows were deleted.
- PASS: focused backend 29 tests and 20 subtests; final full backend 706 tests,
  509 subtests, 3 skipped and 2 existing dependency warnings. Frontend 296 tests
  across 34 files; lint/build and whitespace checks pass. One new lifecycle
  test initially hung because its thread mock also intercepted the async test
  executor; the test was stopped and corrected before the passing rerun.
- Browser discovery in this implementation session returns no browsers. Earlier
  draft WebGL evidence remains historical PASS; no fresh browser run is claimed.
  Live read-only checks report zero active legends, zero approved demo reviews,
  and zero current canonical layouts. Draft preview does not satisfy measured
  layout or quality gates. Recall remains NOT TESTED; the experimental model
  remains inactive and its failed useful-output result is preserved.
- U3 branch/report reconciliation confirms pending page/quality reviews and
  independent sealed-test project requirements; no new source approval is
  inferred from the later provisional crop-training experiment. Dependent U4+
  implementation and main merge remain blocked. Reconnect the browser, provide
  actual legend identities and human geometry/metric review, then complete the
  measured demo and reviewed-truth evaluation before declaring it complete.
- The protected project service has no diff. No source/model/dataset files were
  edited by this checkpoint. Private original-file behavior is covered by the
  synthetic worker regression; no new live-original hash audit is claimed.
- Worker/data-test checkpoint published as `c0254c2`. The preserved room CV,
  draft-preview controls, corner editing and navigation changes are included
  in the following separate demo checkpoint after the passing full suites.
  Unrelated PRE planning-document edits remain in the working tree.

### Latest: room geometry preview and navigation improvement

The user authorized unfinished room-only 2D/3D output and simpler navigation.
Implemented on `codex/demo-floorplan-2d-3d`, verified for scoped publication:

- Room detection now considers the lower page, extracts longer structural
  lines, bridges small gaps and preserves concave room contours. Short wiring
  dashes and narrow fragments are filtered more conservatively.
- Room-first 2D defaults, selectable corner editing, optional overlay layers,
  clear next-step guidance and an explicit unfinished-draft save action.
- Relative-height 3D outlines from the same room draft, using the existing
  Three.js viewer. This preview does not assert measured walls, openings,
  quantities, approved geometry or calibrated scale.
- PASS: sample browser displayed eight room proposals in 2D and actual WebGL
  3D; unfinished review revision 1 was saved without approval and restored
  after reload on job 23140. Eight is a
  proposal count, not eight verified rooms or a recall measurement.
- PASS: 296 frontend tests, lint and production build. Build retains large
  chunk warnings. Latest focused room/processing check: 11 tests passed;
  review API checks: 6 tests passed (17 total). Diff whitespace check passed.
- Full backend checkpoint: 644 tests ran, 2 failed and 3 skipped. Both failures
  were global scale-setting row-count assertions affected by existing saved
  records. Those records were preserved; the full suite is not marked PASS.
  One follow-up command named a nonexistent processing-service test module;
  the corrected command above passed.
- The provisional trained symbol model is not active. Room detection remains
  deterministic CV. Recall, full new-upload browser flow and measured canonical
  approval remain NOT TESTED for this change. U3 data gates remain blocked.
- Originally uncommitted by the planning task; the later implementation
  verification/publication checkpoint above supersedes that publication state.
  Earlier training notes and unrelated planning changes are preserved.

The older checkpoint table below describes the pre-preview demo gates; draft
WebGL display is now verified as stated above, while measured layout approval
and development-set quality evaluation remain separate outstanding work.
User-authorized planning change on September 9, 2026: execute the bounded
DEMO-0 through DEMO-4 track in `LOCAL_VLM_MIGRATION_PLAN.md` before resuming
the full U sequence. The current assignment is section 0 of
`CODEX_U_VLM_MIGRATION_PROMPT.md`. Target: real upload -> room/wall and symbol
proposals -> explicit review/metric approval -> shared saved geometry -> 2D
and basic 3D. Room and symbol recall targets are each >=50% on reviewed
development pages, not a confidence threshold or a release-accuracy claim.

| Checkpoint | Current status | Required evidence |
|---|---|---|
| DEMO-0 inspection and narrow plan | COMPLETE | Main baseline, bounded OpenCV provider decision, and one immutable authorized development page with pending human truth |
| DEMO-1 local detection | COMPLETE | Bounded deterministic OpenCV inference emits strict source-bound room/wall and unknown-class symbol proposals from real pixels |
| DEMO-2 review and persistence | IMPLEMENTED; automated checks PASS | Real worker and immutable reviews; explicit Designer placements; canonical save/reload; real human review pending |
| DEMO-3 basic 2D/3D | IMPLEMENTED; automated checks PASS | Shared saved canonical document, coordinate tests and reload; actual WebGL browser inspection NOT TESTED |
| DEMO-4 demonstration and metrics | BLOCKED; partial browser inspection PASS | Browser connected and user signed in; persisted proposal canvas displayed. Active legend absent, canonical save/human review/truth pending; end-to-end demo and recall NOT TESTED |

### September 10 planning-chat browser and temporary-data checkpoint

#### Latest: user-authorized provisional subset training completed

The user subsequently requested training now and explicitly approved corrected
or manually added symbols with clear legend matches as provisional labels for
a local experiment, excluding ambiguous, unresolved, deleted and untouched
proposals. This supersedes the earlier not-started status below for this narrow
experiment only; no dataset-approver assignment or production approval was
invented, and the live OpenCV demo remains unchanged.

- PASS: derived private dataset version 2 at
  `storage/training/demo-reviewed-v002/manifest.json`, linked by hash to the
  initial import. The original annotation export is unchanged; version 2 is a
  new approved-subset derivation, not a falsely claimed new source export.
- 38 corrected/manually added symbol records examined; 7 excluded by mapping
  and geometry eligibility. Of 31 candidate crops, visual inspection excluded
  10 clipped, ambiguous or multi-object crops. A further tiny 4x4 padded crop
  was rejected by the first training loader and explicitly excluded in run 2.
  Effective run-2 data: 12 training crops and 8 validation crops.
- Four provisional legend-backed classes: NEMA-3R enclosure symbol, panelboard,
  circuit home-run notation, and duplex 3-prong power outlet. No new production
  catalog entries were created. Training has 4/1/2/5 samples respectively;
  validation has only 8 homeruns. Groups 1 and 4 train; group 2 validates.
  Numbered groups are preserved, but independent-project status is not certified.
- Crops use their source bounding boxes plus synthetic white padding. Full
  partially annotated pages were not treated as negative/background truth.
  This crop experiment is not full-plan training/evaluation and trains no rooms,
  walls, lighting fixtures, switches or wiring routes.
- PASS: local CPU-only YOLOv8n training from the installed architecture, with
  random initialization and no pretrained-weight download. Runtime verified:
  PyTorch `2.14.0+cpu`, Ultralytics `8.4.131`, CUDA unavailable to this interpreter.
  Network connections blocked in the isolated process; telemetry/integrations
  disabled. Live HTTP processing, model configuration and app tables untouched.
- Run 1: 10 epochs, 13.14 seconds, zero crop-validation metrics. Run 2: 100
  epochs, 54.01 seconds. Both checkpoints/results retained under the private
  version directory. Run-2 best-checkpoint validation: precision 0.3838449,
  recall 0.125, mAP50 0.3905952, mAP50-95 0.1491061. These are library-reported
  metrics on eight provisional padded homerun crops, NOT full-plan accuracy or
  independent/sealed-test evidence. Do not call this a 50% demo-target pass.
- PASS execution / FAIL useful sample output: separate local inference from
  the run-2 best checkpoint on the user-supplied demo plan produced zero boxes
  at threshold 0.50; source bytes remained unchanged. Result persisted as
  `run-002/sample-inference.json`. No app model activation was performed.
- PASS: repeat dataset preparation verified the existing hash-bound version
  and returned unchanged. This does not implement arbitrary later-export merges.
- Operational notes: sandbox execution of the project interpreter was denied;
  approved escalated execution succeeded. Run 1 created a settings directory at
  repository root after a config-directory fallback; that run-owned directory
  was moved recoverably into its ignored run archive. Run 2 precreated the
  intended private settings directory. No global settings/dependencies changed.
- Next work: improve reviewed label coverage and source-box quality, establish
  suitable training/validation examples for every intended class, and evaluate
  a suitable initialization/training strategy. Do not activate this checkpoint
  merely because training completed. Initial-import data, versions and model
  artifacts remain private and Git-ignored. Full backend/frontend regression
  not rerun: this checkpoint changes no application code or schema.

Follow-up: the user explicitly requested an evolving supervised-training dataset,
not test use alone. The initial collection has been copied into the Git-ignored
local file store `storage/training/demo-initial-20260910/manifest.json`: 105 files,
51 copied image hashes verified, original export unchanged, all files confirmed
Git-ignored. At that import checkpoint there was no application-table ingestion,
detector integration, offline training or model activation. The
active OpenCV provider did not learn from this dataset. Subsequent-export merge,
target approval, offline training and versioned activation are newly recorded
implementation requirements in the existing handoff, not completed capabilities.
The export still contains unresolved labels and no blanket training-truth flag;
user authorization to use the collection does not certify every proposal.
One initial import attempt stopped before copying because the child process's
Git ownership check failed; the successful run used an exact-repository,
command-scoped read-only Git check without changing global Git settings.

- Inspected the running application at implementation commit `98f5105` after
  the user signed in. An existing uploaded development image already had a
  completed processing job; this chat did not perform a fresh upload or job.
- PASS: opened its persisted source-aligned proposal canvas in the browser:
  167 wall-line, 4 room and 4 unknown-class symbol proposals. These counts
  describe this page, not the different page in the earlier timing report.
- Visual quality remains poor: visible text and wiring are included in geometry
  proposals. No precision/recall claim is supported by these counts.
- BLOCKED: saved 2D reports no current layout; 3D reports no saved layout.
  The review page reports no approved active VED legend. No review-completion,
  placement, scale, elevation or wall-parameter approval was made by this chat.
  Displaying the 3D error screen is not a successful WebGL reconstruction test.
- Prepared a private temporary development pack from the supplied 52-page
  correction export. All 52 image hashes and annotation coordinate/legend
  bindings validated; the original review export is preserved byte-for-byte.
  The pack contains 30 active plan inputs, 21 reference-only pages and one
  explicitly excluded plan. All 20 deleted annotations remain audit tombstones
  and are omitted from active hints. Existing annotation-editor tests: 17 PASS.
- This pack is prepared, NOT imported into application review/canonical tables,
  NOT training-approved, NOT sealed-test data and NOT accuracy ground truth.
  No model weights, original images or application behavior were changed.
- The requested unfinished 3D preview is a remaining product gap: current 3D
  consumes reviewed canonical geometry only. Do not fake a completed review to
  unlock it. A separate clearly unapproved preview requires an explicitly scoped
  implementation decision; it is not evidence that DEMO-3/4 already supplies it.

The original amendment was planning only; subsequent implementation evidence
is recorded in the checkpoint entries below. U3 remains blocked under its original
criteria; its data decisions and sealed-test source are deferred dependencies
for the demo only. U10/U12/U14 and complete Admin annotation tooling are not
demo prerequisites. Do not relabel partially reused U/L tickets as complete,
fabricate human approvals or weaken the intake/release validators. Resume
the original sequence only after the demo handoff and further user direction.

| Ticket | Implementation | Real-data validation | Human approval | Activation | Publication | Current note |
|---|---|---|---|---|---|---|
| U1 | Complete | Native-Windows target measured | Approved operating/retention policy and standing VED collection authorization; encryption deferred with accepted risk, not passed | Not applicable | Published to `main` at merge `8c73183` | Collection authorization does not replace source rights, quality, annotation, gold, training-record, or release decisions |
| U2 | Complete | Synthetic contract fixtures pass | Not applicable | Not applicable | Published to `main` at merge `3f12087` | Strict source-pixel payload and host provenance envelope; no persistence or runtime |
| U3 | Implementation PASS; real-data acceptance blocked | Synthetic validation and real private intake executed; actual eligible coverage is zero sources/pages | Covered blueprint permission recorded; one degraded-page decision and eight page classifications remain; third-party references stay excluded | Not applicable | Published to `main` at merge `b909e12` | Private visual review is ready; encryption is deferred risk, not blocker; no genuine frozen-test project exists |
| U4 | Implementation PASS; real pack pending | Synthetic private-pack fixtures pass; six active live catalog classes rechecked | Reviewed aliases, descriptions, glyph regions and source rights remain pending | Not applicable | Published to `main` at merge `5845512` | Builder and Admin UI do not mutate approval state or train/activate a model |
| U5 | Implementation PASS; real gold pending | Synthetic authority/hash/split/sealed-access and comprehensive known-answer metric fixtures pass; 775 backend / 300 frontend tests pass | Independent gold review and numeric threshold approval missing | Not applicable | Published to `main` at merge `8076db8` | Complete calculable geometry evaluators implemented; unavailable real evidence remains pending |
| U6 | Implementation PASS; real bake-off selection pending | Offline egress guard, resource tracking, U2 candidate validation, and U5 metric reporting pass; 783 backend / 300 frontend tests pass | Independent model selection approval missing | Not activated | Published to `main` at merge `a578fae` | Local evaluation harness implemented; zero external downloads or unauthorized training |
| U7 | Implementation PASS | Deterministic overview, legend, plan-region, and overlapping tile transforms pass; 25 focused / 808 backend / 300 frontend tests pass | Not applicable | Not applicable | Published to `main` at merge `433f671` | Multi-resolution page, region, tile and OCR preparation implemented; memory limits checked before allocation |
| U8 | Implementation PASS; real-runtime activation pending | Lazy loading, loopback constraint, offline egress guard, timeout/cancellation, strict candidate validation, and error sanitization pass; 12 focused / 820 backend / 300 frontend tests pass | Independent model selection and weights pending | Not activated | Published to `main` at merge `a44a97e` | Isolated schema-constrained local VLM gateway implemented; zero external downloads or network egress |
| U9 | Implementation PASS; real human review decisions pending | Synthetic authority/monotonic/checklist/export fixtures pass; 144 backend / 300 frontend tests pass | Independent dataset approver review missing | Not activated | Published to `main` at merge `13b7dae` | Requires actual human review decisions |
| U10 | Implementation PASS; real adapter training pending | Sealed isolation, grounding formatting, checkpoint resume, and offline egress pass; 153 backend / 300 frontend tests pass | Independent training target and compute approval missing | Not activated | Published to `main` at merge `9f222e4` | Requires approved training records and compute |
| U11 | Implementation PASS; real human review decisions pending | Extension v2 schemas, fail-closed validation, canonical adaptation, and atomic persistence pass; 169 backend / 313 frontend tests pass | Independent designer review and approved canonical snapshot missing | Not activated | Published to `main` at merge `ed67dc2` | Requires approved candidate review and scale evidence |
| U12 | In progress; untracked source and test draft | Not independently verified | Pending | Not activated | Not published | Resume existing branch; observed wiring only; integration/review tests pending |
| U13 | Not started | Not started | Not applicable | Not activated | Not published | Depends on production gateway/persistence |
| U14 | Not started | Not started | Missing | Not activated | Not published | Requires sealed evaluation and independent signed release decision |

## U1 working state

- Baseline: `main` and `origin/main` at `81ecd83` before branch creation.
- Branch: `codex/u1-hardware-privacy-baseline`.
- On 2026-09-07 the user explicitly authorized committing and pushing unfinished
  U1 and the reviewed planning documents as a device-transfer WIP checkpoint.
  The restored native-Windows target was subsequently measured and the user
  approved the bounded operating and retention policy on 2026-09-07. The
  checkpoint commit is retained as part of U1 history; completion publication
  identifiers are recorded after merge and push.
- The device-migration Markdown, credentials, database backup and private files
  remain local-only and excluded from this publication.
- No model, adapter, inference dependency, API operation, database table, or
  application behavior has been added.
- Device encryption is explicitly deferred under the 2026-09-08 user policy
  amendment. The user accepts the risk, no restoration deadline is approved,
  and the control is not marked passing. It is no longer a U3 or U6 gate; all
  other local-only privacy, permission, resource, and acquisition gates remain.
- Standing VED collection authorization is recorded for covered VED project
  sources and bounded U-ticket purposes. It does not cover unrelated third-party
  rights or replace later annotation, quality, gold, training, or release review.
- U2 started only after U1 publication completed.

## U1 completion checkpoint

- Completion implementation commit: `baa0258`.
- Hardware evidence: Windows 11 build 26200, Ryzen 7 7435HS (8 cores/16
  logical), 16,989,728,768 bytes RAM, RTX 3050 Laptop GPU with 4,096 MiB VRAM,
  NVIDIA driver 566.07/CUDA 12.7 capability, and bounded local disk recorded in
  the U1 baseline.
- Privacy evidence: private root outside OneDrive; explicit user-only and
  `SYSTEM` ACL; full `models/vlm/` Git ignore probe passed; no local model
  weights found.
- Integrity evidence: `git diff --check` passed; ticket paths were limited to
  U1 documentation and `.gitignore`; the protected `project_service.py` blob
  matched `main` at `44e01c22ede76f30182b1056b0cb4e6fce3df96a`.
- Application regression: not rerun because U1 changes no application,
  dependency, API, schema, database, or canonical-geometry code. The restored
  PRE12 full-suite baseline remains 627 `unittest` tests with 3 skipped, 664
  `pytest` tests plus 504 subtests with 3 skipped, and 280 frontend tests across
  30 files, with frontend lint/build and Python compile checks passing.

## U2 working state

- Baseline: U1 merge `8c73183` on `main` and `origin/main`.
- Branch: `codex/u2-candidate-contract-v1`.
- Implementation commit: `90c90bb`.
- The immutable Pydantic contract, host provenance envelope, U9 review identity,
  U11 projection boundary, and representative/empty synthetic fixtures are
  implemented without a database table, API operation, model, gateway, or K1
  change.
- Focused candidate and canonical-compatibility verification passes 62 tests;
  the full backend regression passes 686 tests with 3 skipped, 2 dependency
  deprecation warnings, and 504 subtests.
- U3 started only after U2 publication completed.

## U3 blocked working state

- Baseline: U2 merge `3f12087` on `main` and `origin/main`.
- Branch: `codex/u3-private-corpus-intake`.
- Safe implementation commit: `cdb4684`.
- Planning-review correction implementation commit: `941eb9b`.
- Manifest-integrity implementation commit: `b4b4d57`.
- Real-intake/report reconciliation commit: `e4c0c85`.
- Page-classification and quality-review implementation commit: `d427be2`.
- Local-only intake now enforces project-level split isolation, safe incremental
  preservation/versioning, immutable recoverable prior revisions, full stored
  record/derived-data validation, bounded source and image/PDF allocations,
  explicit independent-project coverage, page-level mixed-document
  classification, and purpose-specific append-only degraded-quality review.
- The U3 suite passes 41 tests with 1 native Windows symlink test skipped. The
  focused U3/candidate/upload suite passes 94 tests with the same skip and 2
  subtests. The full backend regression passes 727 tests with 4 skipped, 2 known
  dependency warnings, and 504 subtests.
- Read-only interface reconciliation confirms 34 unique OpenAPI operations and
  an exact 23-modeled/23-live-table match. Live row counts and all six original
  file sizes/hashes match the published PRE12 baseline.
- Real intake ran idempotently inside the approved private boundary. Schema 1
  revision 1 was validated and archived byte-for-byte before the manifest was
  upgraded to schema 2 revision 2. It records four sources and 18 pages: nine
  blueprint pages and nine reference pages. Original hashes still match.
- Actual eligible blueprint source/page, drawing-group, and independent-project
  counts are all zero. A private ten-page visual review shows the degraded VED
  page and all eight pages of the mixed VED document with assistant proposals.
  One purpose-specific degraded-page decision and eight page classifications
  remain pending. The two third-party references remain inventoried and excluded
  while rights are unresolved; they do not block VED blueprint inventory. A
  genuinely new independent frozen-test project is still absent. Device
  encryption is deferred accepted risk, not the blocker.
- September 11 reconciliation merged published demo `d7e53c4` into the U3
  feature branch and retained both AI boundaries. Focused U3/candidate/upload
  verification passes 94 tests with 1 native-Windows symlink skip and 2
  subtests. The full backend suite passes 747 tests with 4 skips and 509
  subtests in a fresh isolated database, which was removed afterward.
- Current read-only integration checks report 37 unique OpenAPI operations,
  exact 25-modeled/25-live tables, and 10 configured originals totaling
  1,015,004 bytes at aggregate SHA-256
  `20751d51ff7c6240274f075ee5237f93c44d48a79e7cf103baca34fc1b6fc2f3`.
- U3 implementation is eligible for publication under the updated section 0;
  real-data acceptance remains blocked and is not relabeled as complete.
- U3 implementation was published to `main` at merge `b909e12`; feature and
  main upstream divergence were both `0 0` after push.

## U4 implementation checkpoint

- Baseline: U3 implementation merge `b909e12`; branch
  `codex/u4-approved-legend-reference-pack`.
- Added a strict local-only builder and sanitized CLI for immutable, parent-linked
  legend/reference manifests. Every active catalog record must have the same
  stable database/class identity, approved name, active state, aliases,
  description, approval revision and at least one source/page/region glyph.
- Source records are size-bounded and hash-verified inside the approved private
  root. Drawing mappings cannot cross drawing sets. PEC/reference metadata keeps
  edition, part, page, rights holder, explicit permitted use and evidence identity.
  Unknown glyphs remain separate and cannot be coerced into known classes.
- Restored the authenticated Admin dashboard catalog panel and its API client.
  Designers do not receive the control; FastAPI still enforces authorization.
  Catalog saves remain explicit and do not train a detector or approve geometry.
- Focused verification: 24 backend tests with 12 subtests in an isolated database;
  15 frontend tests. Full verification: 756 backend tests with 4 skipped and
  509 subtests in a removed isolated database; 300 frontend tests across 36 files;
  Python compilation, dependency check, CLI help, lint and production build PASS.
  Existing dependency deprecations and large-bundle warnings remain.
- No API, SQLAlchemy table, live row, dependency, runtime-model or canonical
  geometry change. No real private pack was created. Six active live catalog
  classes exist, but real U4 acceptance remains BLOCKED on reviewed aliases,
  descriptions, glyph evidence and purpose-specific source rights.
- Next: publish this implementation checkpoint, then start independently
  testable U5 gold-import and metric tooling without claiming real gold exists.

## U5 implementation checkpoint (reconstructed, superseded)

- Baseline: published U4 merge `5845512`; branch `codex/u5-gold-metric-tooling`.
  Recovery stash `stash@{0}` remains preserved; its planning/dashboard changes
  were reconciled without applying or discarding the stash.
- Added an offline private-root gold builder and database-authority CLI. Source
  and annotation hashes, page identity, five-layer completeness, project-level
  split isolation, immutable parent revisions, and non-removable prior records
  are validated. Incorrect, inactive, expired, self, and client-only approval
  authority fails closed.
- Development loading requires an expected manifest hash and returns eligible
  development records only; sealed-test records are excluded from U6/U10
  workflows. Original source bytes remain untouched.
- The metric contract requires all migration-plan metrics and hard gates.
  Unsupported deterministic outputs are N/A with reasons; missing measurements
  are pending. Known-answer overall/per-class symbol precision, recall, F1,
  count error, IoU and center error are implemented.
- Focused verification: 14 U5 tests; combined U2-U5 boundary suite: 86 passed,
  1 native-Windows symlink skip. Compileall, pip check, frontend 300 tests,
  lint and build passed. Full backend verification is still required in an
  isolated database before publication.
- Real U5 acceptance remains BLOCKED: representative independently approved
  gold membership and approved numeric promotion/regression thresholds are not
  available. No model selection or release claim is made.

## U5 implementation checkpoint (reconstructed)

- Baseline: published U4 merge `5845512`; active branch
  `codex/u5-gold-metric-tooling`. The recovery stash remains preserved as
  `stash@{0}`; its planning/dashboard changes are already present in this tree.
- Added an offline, private-root gold-manifest builder and sanitized CLI. It
  validates source/page identity, bounded reads, source and annotation hashes,
  complete five-layer annotations, project-level split isolation, immutable
  parent revisions, and recoverable membership (records cannot silently vanish
  or change split).
- Review decisions require active PRE10 authority snapshots, decision time,
  independent author/approver identities and matching annotation hashes.
  Incomplete and rejected records remain inventoried but are ineligible.
  The development loader requires an expected manifest hash and omits all
  sealed-test records; it never supplies sealed labels to model workflows.
- The metric contract requires all migration-plan metrics and hard gates. Missing
  evidence is `pending`; unsupported calculator outputs are `not_applicable`
  with a reason, never zero. Known-answer symbol matching is deterministic and
  reports overall and per-class precision, recall, F1, count error, box IoU and
  center error.
- Focused verification: 14 U5 tests; combined U2-U5 AI boundary tests: 86
  passed, 1 native-Windows symlink test skipped. Compileall, pip check, frontend
  300-test suite, lint and production build passed. The first full backend run
  was interrupted after unrelated shared-development-database failures; it is
  not evidence against U5 and requires a disposable isolated database rerun.
- Real U5 acceptance remains BLOCKED: no representative independently approved
  gold membership or approved promotion/regression thresholds exists. Current
  unsupported deterministic metrics are wall endpoint/angle/segment/duplicate,
  room IoU, opening/panel F1, scale errors, wiring presence/segment/topology/
  length and peak VRAM. No model selection or release claim is made.

## U5 implementation and verification checkpoint (completed)

- Baseline: published U4 merge `5845512`; active branch `codex/u5-gold-metric-tooling`.
  Recovery stash `stash@{0}` remains preserved untouched (`bb78854e87833124a1725b51f0be6099a8ac0cfa`).
- Safe test-database isolation established: dedicated user `ved_test` scoped strictly
  to `ved_electrical_verify` with zero access to development data. Verified before
  and after full backend regression: `ved_electrical` row counts remained 100%
  unchanged (25 tables, 178 rows intact).
- Implemented calculable geometry evaluators in `gold_evaluation.py` and exported
  in `floor_plan_interpretation/__init__.py`:
  - `evaluate_walls` (match rate, precision, recall, F1, mean endpoint error, mean angle error, duplicate rate)
  - `evaluate_rooms` (polygon IoU using `cv2.fillPoly` raster mask and bounding box fallback, precision, recall, F1, mean IoU)
  - `evaluate_entities_by_kind`, `evaluate_openings`, `evaluate_panels` (center distance matching, precision, recall, F1, mean center error)
  - `evaluate_scale` (absolute error, relative error)
  - `evaluate_wiring` (presence accuracy, route matching, precision, recall, F1, topology error, length error ratio)
- Comprehensive known-answer unit tests added in `test_gold_evaluation.py` covering
  perfect matches, displacements, duplicate predictions, partial overlaps, empty
  inputs, and error conditions.
- Verification results:
  - Focused U5 tests: 19 passed in 0.88s.
  - Combined U2–U5 boundary suite: 91 passed, 1 skipped in 1.95s.
  - Full backend regression in isolated test database: 775 passed, 4 skipped, 2 warnings, 509 subtests passed in 23.25s.
  - Full frontend regression: 36 test files passed, 300 tests passed; lint and production build passed cleanly.
  - `git diff --check`: passed cleanly.
- Real gold membership and approved numeric promotion/regression thresholds remain
  pending evidence. No model selection or release claim is made.

## U6 implementation and verification checkpoint (completed)

- Baseline: published U5 merge `8076db8` (progress ledger `32e50b7`); branch
  `codex/u6-local-vlm-bakeoff-harness`. Recovery stash `stash@{0}` remains preserved untouched.
- Implemented `evaluation_harness.py` in `backend/app/ai/floor_plan_interpretation/`
  and exported in `__init__.py`:
  - `OfflineEgressGuard`: context manager intercepting socket operations to guarantee
    zero external network egress during model inference.
  - `ResourceTracker`: measures execution wall-clock latency, peak process RAM (via tracemalloc),
    and peak VRAM (with 4GB RTX 3050 budget and CPU graceful fallback).
  - `ModelEvaluationConfig`: strict Pydantic model for candidate configuration (revision, license,
    runtime, execution mode, max tokens, timeout, and VRAM budget).
  - `ModelProviderAdapter` / `MockModelProviderAdapter`: protocol and deterministic mock adapter.
  - `EvaluationHarness`: loads development gold split via U5 `load_development_gold()`, validates
    candidate envelopes via U2 `build_candidate_envelope()`, calculates full metric observations
    across all 28 `REQUIRED_METRICS`, generates `MetricReportEntry` tuples via `build_metric_report()`,
    and honestly reports legacy YOLO comparisons (unavailable when weights are absent).
- Added comprehensive unit test suite in `backend/tests/test_vlm_evaluation_harness.py` covering:
  - Offline egress boundary enforcement and violation escalation.
  - Resource usage measurements.
  - Configuration schema validation.
  - Provider lifecycle (load/predict/unload).
  - End-to-end evaluation on development gold records.
  - Immediate abortion on egress violation.
  - Strict exclusion of sealed-test records.
  - Timeout and retry handling.
- Verification results:
  - Focused U6 suite: 8 passed in 2.49s.
  - Combined U2–U6 AI suite: 99 passed, 1 skipped in 3.74s.
  - Full backend regression in isolated test database: 783 passed, 4 skipped, 2 warnings, 509 subtests passed in 24.84s.
  - Full frontend regression: 36 test files passed, 300 tests passed; lint and production build passed cleanly.
  - Development database `ved_electrical` row counts strictly verified unchanged before and after test executions (25 tables, 178 rows intact).
  - `git diff --check`: passed cleanly.
- Real model selection and hardware activation remain PENDING until approved datasets and model decisions exist. Zero unapproved downloads or external inference performed.

## U7 implementation and verification checkpoint (completed)

- Baseline: published U6 merge `a578fae` (progress ledger `60d69ee`); branch
  `codex/u7-multi-resolution-page-context`. Recovery stash `stash@{0}` remains preserved untouched.
- Implemented `preparation.py` in `backend/app/ai/floor_plan_interpretation/` and exported in `__init__.py`:
  - `PreparationConfig`: strict bounds configuration for tile dimensions, tile overlap, overview size, pixel budgets, and resource limits.
  - `PreparationResourceExhaustion`, `InvalidGeometryError`, `ArtifactPersistenceError`: safe error hierarchy.
  - Reversible coordinate transforms: `invert_affine_transform`, `local_to_source_coords`, `source_to_local_coords`, `transform_bounds_local_to_source`, and `transform_bounds_source_to_local` with verified round-trip precision.
  - Enforced isotropic scaling check: `assert_isotropic_scaling` prevents asymmetric floor plan distortion.
  - Multi-resolution region extraction: `generate_overview_region`, `detect_plan_region`, and `detect_legend_region`.
  - Overlapping tile slicing: `generate_tiles` guarantees full image coverage with pre-allocation safety bounds checking `max_tiles` and `max_source_pixels` before any allocation.
  - Auxiliary evidence extraction: `extract_auxiliary_thresholded`, `extract_line_evidence` (classifying horizontal, vertical, and diagonal orientations), and `extract_ocr_evidence`.
  - Page classification and signals: `assess_page_signals` detecting electrical content, scale, dimensions, legend, and flagging degraded/unsupported/blank pages with sorted unique issues.
  - Cross-tile deduplication and fusion: `fuse_detected_symbols` merging duplicates in overlaps while strictly preserving distinct adjacent true symbols, and `fuse_detected_walls`.
  - PRE5 persistence: `persist_prepared_tiles` registering tile slices with `artifact_kind="vlm_tile"` without mutating original files.
- Added comprehensive unit and boundary tests in `backend/tests/test_vlm_preparation.py` covering:
  - Invertible affine round-trips and bounding box transformations.
  - Rejection of zero-determinant transforms and non-square/asymmetric scaling.
  - EXIF orientation transposition and RGBA transparency flattening.
  - Pre-allocation resource exhaustion guards against excessive tile count and image pixels.
  - Overview aspect ratio preservation, plan region detection, and legend extraction.
  - Auxiliary thresholding and line orientation classification.
  - Page signals and blank page detection.
  - Duplicate symbol fusion across tile overlaps, conflict marking for mismatched classes, and preservation of adjacent true symbols.
  - Collinear wall fusion across tile boundaries.
  - Full end-to-end page preparation and PRE5 tile artifact persistence.
  - Verification that original uploaded blueprints remain bit-for-bit identical (SHA-256 match).
- Verification results:
  - Focused U7 suite: 25 passed in 1.33s.
  - Combined U2–U7 AI suite: 124 passed, 1 skipped in 4.97s.
  - Full backend regression in isolated test database: 808 passed, 4 skipped, 2 warnings in 24.76s.
  - Full frontend regression: 36 test files passed, 300 tests passed; lint and production build passed cleanly.
  - Development database `ved_electrical` row counts strictly verified unchanged before and after test executions (25 tables, 178 rows intact).
  - `git diff --check`: passed cleanly.

## U8 implementation and verification checkpoint (completed)

- Baseline: published U7 merge `433f671` (progress ledger `9deec4d`); branch
  `codex/u8-local-vlm-gateway`. Recovery stash `stash@{0}` remains preserved untouched.
- Implemented `backend/app/ai/local_model_gateway/` containing:
  - `config.py`: strict Pydantic models for `LocalGatewayConfig`, `GatewayInferenceRequest`,
    `GatewayInferenceResult`, and `GatewayHealth`. Restricts runtime URLs strictly to loopback
    (`127.0.0.1`, `localhost`, `::1`) and enforces `allow_network=False`. Rejects external endpoints.
  - `diagnostics.py`: `DiagnosticsStore` for private offline execution logging with automated
    credential/path redaction (masking passwords, bearer tokens, and private filesystem paths).
    Hierarchical sanitized error types (`GatewayTimeoutError`, `EgressViolationError`,
    `SchemaValidationError`, `ModelExecutionError`, `ConcurrencyLimitError`) exposing clean API
    errors with diagnostic traceability without leaking internal traces or raw model text.
  - `gateway.py`: `LocalModelGateway` with lazy model loading and cached lifecycle,
    `OfflineEgressGuard` enforcement, `ResourceTracker` hardware budget monitoring (RTX 3050 4GB VRAM
    and process RAM), bounded concurrency controls, and timeout cancellation. Validates raw output
    against strict Pydantic candidate schemas (`parse_candidate_payload_json` and `build_candidate_envelope`).
    Invalid or partial text is rejected.
  - `MockLocalVLMAdapter`: deterministic local runtime adapter for testing lifecycle, validation,
    hangs, errors, and egress violations.
- Added comprehensive unit and boundary tests in `backend/tests/test_vlm_gateway.py` covering:
  - Strict rejection of external endpoints and network egress.
  - Loopback host resolution.
  - Redaction of sensitive tokens and paths in diagnostic logs.
  - Lazy model initialization, health checks, and shutdown.
  - Successful end-to-end inference producing valid U2 candidate envelopes.
  - Strict rejection of malformed or truncated JSON and missing candidate fields.
  - Timeout enforcement and cooperative cancellation.
  - Immediate escalation on attempted external egress.
  - Concurrency budgeting and queue overflow handling.
- Verification results:
  - Focused U8 suite: 12 passed in 12.65s.
  - Combined U2–U8 AI suite: 136 passed, 1 skipped in 15.88s.
  - Full backend regression in isolated test database: 820 passed, 4 skipped, 2 warnings in 40.90s.
  - Full frontend regression: 36 test files passed, 300 tests passed; lint and production build passed cleanly.
  - Development database `ved_electrical` row counts strictly verified unchanged before and after test executions (25 tables, 178 rows intact).
  - `git diff --check`: passed cleanly.
- Real model weights, fine-tuned adapters, and production runtime activation remain PENDING until approved datasets and model selection decisions exist. Zero unapproved downloads or external inference performed.

## U9 implementation and verification checkpoint (completed)

- Baseline: published U8 merge `a44a97e` (progress ledger `f0ba7f7`); branch
  `codex/u9-durable-pseudo-labeling`. Recovery stash `stash@{0}` remains preserved untouched.
- Implemented `backend/app/ai/floor_plan_interpretation/pseudo_labeling.py` and exported in `__init__.py`:
  - `CompletenessChecklist`: strict checklist for walls, rooms, symbols, openings, panels, scale, wiring, and ambiguous items.
  - `DatasetApprovalDecision`: models PRE10 sign-off with approver assignment ID, decision timestamp, and scope.
  - Review items for all 7 entity kinds: `SymbolReview`, `WallReview`, `RoomReview`, `OpeningReview`, `PanelReview`, `ScaleEvidenceReview`, and `ObservedWiringReview`.
  - `ReviewDocument`: append-only immutable review document schema with page revision hashes.
  - `record_pseudo_label_run()`: idempotent registration of `FloorPlanInterpretationRun` with hash and provenance integrity.
  - `submit_append_only_review()`: append-only revision increments (`revision_number = latest + 1`), completeness checklist validation, rejection of unresolved items when marked complete, and automatic reset of dataset approval upon newly submitted revisions.
  - `bind_dataset_approval()`: PRE10 dataset approver authority validation (`VED_AI_DATASET_APPROVER`), strict author/reviewer self-approval rejection.
  - `export_approved_training_candidates()`: strict export filtering excluding unapproved revisions, incomplete reviews, unresolved targets, and holdout splits; produces valid `GoldAnnotationDocument` instances.
- Updated `backend/app/schemas/demo_interpretation.py`, `backend/app/services/demo_interpretation_service.py`, and `backend/app/api/routes/demo_interpretation.py` to seamlessly integrate U9 review extensions, checklist verification, and status mappings without changing the 37 preserved OpenAPI operations or breaking existing consumers.
- Added comprehensive unit and boundary tests in `backend/tests/test_pseudo_label_review.py` covering:
  - Idempotent interpretation run recording.
  - Monotonic append-only review revisions.
  - Stale revision conflict rejection.
  - Completeness checklist and unresolved target enforcement.
  - Cross-owner access denial and Admin read-only behavior.
  - PRE10 dataset approver authority verification and self-approval denial.
  - Automatic dataset approval reset on subsequent edits.
  - Training dataset export filtering excluding incomplete or holdout data.
- Verification results:
  - Focused U9 suite: 8 passed in 1.99s.
  - Combined U2–U9 AI suite: 144 passed, 1 skipped in 20.32s.
  - Full frontend regression: 36 test files passed, 300 tests passed; lint and production build passed cleanly.
  - `git diff --check`: passed cleanly.
- Real human dataset approver decisions remain PENDING on live data.

## U10 implementation and verification checkpoint (completed)

- Baseline: published U9 merge `13b7dae` (progress ledger `22ecbb8`); branch
  `codex/u10-lora-qlora-adapter-manifests`. Recovery stash `stash@{0}` remains preserved untouched.
- Implemented `backend/app/ai/floor_plan_interpretation/training.py` and exported in `__init__.py`:
  - `BaseModelReference`: pinned base VLM model metadata (model_id, revision, sha256, license, context window).
  - `LoRAHyperparameters`: rank `r`, alpha, target modules, dropout, task type, quantization mode (`none`, `int8`, `int4`/QLoRA).
  - `TrainingBudget`: step/epoch bounds, learning rate, warmup, gradient accumulation, seed, VRAM limits (RTX 3050 4GB).
  - `TrainingConfig`: unified reproducible training run specification.
  - Spatial grounding coordinate normalization: `normalize_coordinates_to_1000` mapping source pixels to `[0, 1000]` bounding boxes with bounds validation.
  - `GroundingSample` & `format_gold_to_grounding_sample`: instruction tuning conversation conversion with assistant-only loss masking (`mask_type="assistant_tokens_only"`).
  - `build_training_manifest`: immutable versioned dataset manifest builder with deterministic SHA-256 hashing and strict sealed test isolation (`SealedDataLeakageError`).
  - `CheckpointManager`: immutable checkpoint persistence with metadata, simulated/real weights, and resume compatibility verification.
  - `AdapterRegistry`: local catalog management enforcing that all newly trained adapters are strictly registered as `status="inactive"`, rejecting overwrites and unauthorized activation.
  - `LocalTrainingRunner`: training orchestrator operating within `OfflineEgressGuard` and `ResourceTracker`, evaluating against the development validation split without test set leakage.
- Added comprehensive unit and boundary tests in `backend/tests/test_vlm_training.py` covering:
  - LoRA and budget schema validation.
  - Spatial grounding coordinate normalization and bounding box clamping.
  - Conversion of approved gold documents into grounding conversation samples.
  - Strict rejection of sealed test split leakage.
  - Deterministic training manifest SHA-256 hash calculation.
  - Checkpoint persistence and resume state validation.
  - Rejection of resume attempts with mismatched base model or altered training dataset.
  - Adapter registry enforcement of initial `inactive` status.
  - End-to-end training execution inside offline egress guard and inactive adapter registration.
- Verification results:
  - Focused U10 suite: 9 passed in 4.45s.
  - Combined U2–U10 AI suite: 153 passed, 1 skipped in 19.86s.
  - Full frontend regression: 36 test files passed, 300 tests passed; lint and production build passed cleanly.
  - `git diff --check`: passed cleanly.
- Real adapter training and compute allocation remain PENDING until approved training datasets exist. Zero unapproved downloads or external compute used.

## U11 implementation and verification checkpoint (completed)

- Baseline: published U10 merge `9f222e4` (progress ledger `806d424`); branch
  `codex/u11-candidate-persistence-k1-adapter`. Recovery stash `stash@{0}` remains preserved untouched.
- Shared compatibility fixtures created in `fixtures/`:
  - `fixtures/canonical_extension_v2.json`: representative valid extension document matching `canonical_geometry_v1.json`.
  - `fixtures/canonical_extension_v2_empty.json`: valid empty collections document.
  - `fixtures/canonical_extension_v2_partial.json`: partial collections with unclassified openings.
  - `fixtures/canonical_extension_v2_malformed.json`: negative coordinate rejection test fixture.
  - `fixtures/canonical_extension_v2_unsupported.json`: unsupported `extension_schema_version = 3` fail-closed test fixture.
- Implemented `backend/app/geometry/canonical_extension.py` and exported in `__init__.py`:
  - Data structures: `SourcePlaneReference`, `CanonicalOpening`, `CanonicalPanel`, `CanonicalPanelBounds`, `CanonicalSymbolDetail`, `CanonicalSymbolBounds`, `CanonicalRouteDetail`, and `CanonicalExtensionV2`.
  - Exact-key, fail-closed deserializer and validator `canonical_extension_from_dict` enforcing `extension_schema_version == 2`, `base_schema_version == 1`, strict types, and cross-reference integrity against base K1 geometry.
  - View composer `compose_canonical_view(base_doc, extension)`.
  - Adaptation engine `adapt_reviewed_candidate_to_canonical` strictly translating approved entities from U9 `ReviewDocument` + U2 `FloorPlanInterpretationCandidate` with approved scale/elevation validation from PRE6, producing a verified `(CanonicalGeometryDocument, CanonicalExtensionV2)` pair.
- Implemented `backend/app/services/canonical_extension_storage.py`:
  - Atomic JSON persistence and sha256 hashing at `<storage>/canonical_extensions/layout_<id>_extension_v2.json`.
  - Preserves live database constraint `schema_version = 1` in `layout_versions` without table schema mutation or 26th table addition.
- Updated layout persistence and interpretation services:
  - `backend/app/services/layout_version_service.py`: updated `LayoutVersionRecord` and `save_layout_snapshot_conditionally` to atomically persist and load extension documents alongside base geometry in one transaction.
  - `backend/app/services/layout_service.py`: updated `save_owned_layout` to accept and validate extension payloads.
  - `backend/app/services/demo_interpretation_service.py`: updated `save_approved_interpretation_layout` to construct `CanonicalExtensionV2` with source-plane references and pass to atomic layout save.
- Implemented frontend module `frontend/src/geometry/canonicalExtension.js`:
  - `normalizeCanonicalExtension(value, baseGeometry)`: deep-frozen normalization, exact-key validation, fail-closed checking, and base cross-referencing.
  - `composeCanonicalView(baseGeometry, extension)`: composable view utility.
  - `preserveExtensionOnSymbolMove(extension, symbolId, newPosition)`: updates symbol coordinates while retaining detailed provenance.
- Verification results:
  - Focused U11 backend suite: 16 passed in 1.37s.
  - Combined U2–U11 AI suite (10 test files): 169 passed, 1 skipped in 19.34s.
  - Layout and canonical regression: 75 passed in 5.73s.
  - Demo interpretation API regression: 6 passed in 3.81s.
  - Full frontend suite: 37 test files, 313 passed in 10.69s.
  - `npm.cmd --prefix frontend run lint`: 0 errors.
  - `npm.cmd --prefix frontend run build`: passed cleanly.
  - `python -m compileall backend/app backend/tests`: passed cleanly.
  - `git diff --check`: 0 issues.
  - MySQL database isolation verified: exactly 25 tables in `Base.metadata`, zero mutations to dev database.
- Real human review decisions and model weights remain PENDING. Zero unapproved downloads or external compute used.

## DEMO-0 completion checkpoint

- Baseline: published `main`/`origin/main` merge `3f12087`; branch
  `codex/demo-floorplan-2d-3d`. The isolated U3 implementation was not merged.
- The selected bounded runtime is the installed local OpenCV pipeline. No
  usable local YOLO weight or VLM artifact exists, so neither is represented as
  available and no model download is part of upload processing.
- Reusable foundations: protected uploads and source identity, one-based PDF
  rendering and normalization, preprocessing and deterministic wall evidence,
  PRE9 job leases, the U2 strict source-pixel candidate envelope, detection
  review, metric approval, K1 canonical geometry, append-only K2 snapshots,
  K3 reload and the Konva editor.
- Demo gaps requiring scoped implementation: an executable local worker,
  document-room and generic symbol proposal extraction, durable unified review
  revisions, reviewed-candidate-to-canonical adaptation, and a canonical-backed
  Three.js scene.
- One readable, purpose-authorized private development page is frozen outside
  the repository with its source/page identity, render bounds and unchanged
  original hash recorded. It is a historical development source, not the U3
  sealed test project. Unselected pages are not processed.
- Measurement truth is `pending_human_review`; therefore room and symbol recall
  remain `NOT TESTED` at DEMO-0. The >=50% targets and IoU >=0.5 matching rule
  are frozen and will not be lowered to manufacture a pass.
- Explicit exclusions remain wiring/routing, costing/reporting, model training,
  full U5/U9 annotation administration, U10/U12/U14 release claims and any
  assertion that the U3 corpus or sealed-test gates passed.

## DEMO-1 completion checkpoint

- Provider: local deterministic OpenCV only (`demo_cv_baseline` for downstream
  provenance). It performs no network access, file lookup, database mutation,
  filename matching, hosted inference, weight loading or download-on-upload.
- The provider accepts bounded decoded RGB pixels and emits the published U2
  source-pixel contract with a source-bound plan evidence region. Room, wall and
  circular-symbol proposals all remain review-only; symbols use
  `mapping_state=unknown` until a designer maps them to an approved live legend.
- The frozen private development page was normalized to 4096 x 2731 for the
  measured run. It produced 300 wall proposals (bounded and explicitly
  partial), 37 room proposals, and 129 unknown-class circular-symbol proposals.
  The strict serialized candidate was 86,480 bytes, below the 256 KiB contract
  limit. One measured warm-process run took 884.6 ms on the U1 Windows host.
- The first measured implementation used Hough-circle extraction, reached the
  500-symbol cap and took 24,752.6 ms. It was replaced before publication by
  bounded contour extraction; this failed experiment is retained here so the
  provider choice is auditable rather than silently optimized after the fact.
- Focused verification covers synthetic real-pixel extraction, empty input,
  deterministic unchanged input, rotation/scale variation, explicit
  truncation, unsafe input, sanitized OpenCV failure and isolation from files,
  HTTP, database and job state. Recall, precision, TP, FP and FN remain
  `NOT TESTED` pending reviewed development truth; proposal counts are not
  accuracy measurements.

## DEMO-2 implementation checkpoint

- Branch: `codex/demo-floorplan-2d-3d`, following DEMO-1 `38bffde`.
- Adds a separately started local worker using PRE9 leases and PRE4/PRE5
  source/artifact identity. Upload and Analyze remain separate operations.
  The worker handles page 1; all later document pages remain unprocessed.
- Adds immutable interpretation runs and append-only review revisions, with
  source-pixel room/wall/symbol correction and accepted/rejected decisions.
  Current schema: 25 tables and 37 OpenAPI operations.
- Explicit Designer approval creates real `manual_symbols` placements from
  reviewed positions, with deterministic run/review/symbol request identity.
  K1 remains unchanged and references the actual placement database IDs.
  Raw CV candidates and reviews remain separate immutable evidence; no YOLO
  record or confidence is fabricated. This is a human placement projection,
  not implementation of U11's machine-symbol extension contract.
- Save checks current review approval, live legend identity, exact approved
  scale/elevation and explicit wall dimensions. It uses the existing atomic
  conditional layout save; failed saves roll back placements. Repeated save
  requests preserve placement identity. Unsaved review changes disable publish.
- Regression: full backend run passed 700 tests and 509 subtests, with 3 skipped
  and 2 dependency deprecation warnings. A subsequent focused run after adding
  stale-approval rejection passed 7 worker/review tests. Full frontend run
  passed 292 tests including the in-progress DEMO-3 tests; the subsequent
  review/upload subset passed 72 tests. Lint, build and diff whitespace checks
  passed. Build reports the existing large-chunk warning.
- Tests use disposable synthetic pixels/records and restore their row counts.
  The protected project service and private originals are unchanged. Existing
  legacy detection review remains reachable alongside the demo review.
- Real Designer approval and browser demonstration remain pending. No active
  symbol legend exists on the local database; no classes were invented.

## DEMO-3 implementation checkpoint

- DEMO-2 published as `637054e` on the demo branch. DEMO-3 adds only the
  canonical 3D consumer and its tests; it changes no API or database contract.
- The existing layout API supplies both views. Canonical `(x, y)` maps to
  Three `(x, floor elevation, z=y)` in meters. Wall endpoints determine rotation,
  length and midpoint; approved thickness/height determine extrusion. Room
  polygons remain the same boundaries. Markers indicate floor positions with
  display-only glyph size and make no mounting-height claim.
- Missing wall height/thickness produces a visible error. Unverified walls
  are excluded. Top/perspective, orbit/pan/zoom, reset and persisted-layout
  reload are available. The 2D editor continues to use its existing save path.
- Verification: 292 frontend tests passed across 33 files, including negative
  elevation, vertical/rotated walls, changed saved symbol positions, removed
  symbols, input immutability, missing dimensions and saved-layout loading.
  Lint and production build passed; the bundle-size warning remains.
- Browser/WebGL inspection and an actual user 2D edit followed by 3D reload are
  NOT TESTED: browser discovery returned no browsers, and URL selection returned
  `No browser is available`. Automated geometry tests do not replace this gate.

## DEMO-4 partial handoff and remaining evidence

- DEMO-3 published as `70cd33a`; DEMO-2 as `637054e`. Both are on
  `codex/demo-floorplan-2d-3d`. Main merge and post-merge verification are
  withheld because the required real demonstration is incomplete.
- Fresh real-pixel measurement using the same G2 Pillow LANCZOS normalization
  as the worker: 4096 x 2731 pixels, 37 room proposals, 300 walls (partial/capped),
  129 unknown-class circular-symbol proposals, 1088.6 ms detector latency.
  This is one timing sample, not an end-to-end latency percentile. The frozen
  development image hash matches and its bytes are unchanged.
- A diagnostic using OpenCV AREA resize instead gave 36 rooms and 118 symbols
  in 1075.2 ms. It is not the worker preprocessing configuration or the scored
  baseline; the difference demonstrates sensitivity to normalization.
- Room/symbol TP, FP, FN, precision and recall: NOT TESTED. Reviewed polygons,
  same-class symbol boxes and excluded unresolved regions are absent. The
  >=50% recall targets remain unchanged. Manual placements cannot count as
  automatic correct detections, and unknown classes cannot count as class matches.
- Final verification on the committed implementation: backend `pytest -q
  --tb=short` passed 701 tests and 509 subtests, 3 skipped, 2 dependency warnings.
  Frontend full suite passed 292 tests; the later affected review/upload subset
  passed 72. Final lint/build passed with the large-chunk warning. The API
  health endpoint and Vite root each responded successfully on loopback.
- Three existing queued jobs were left untouched because no specific one was
  selected for this demo. No signed user session was forged for a real-data
  demonstration. The worker can target the new job ID using README commands.
- Exact remaining requirements: connect a browser to this session; an
  authorized Admin must configure the actual approved VED legend identities;
  the owning Designer must review/correct the page and approve its scale,
  elevation and wall dimensions. Then exercise upload, Analyze, save, 2D edit,
  3D reload and restart in that browser. Human-reviewed development truth is
  separately required to measure accuracy.
- The API and frontend were started locally for handoff. Startup and review
  steps are in the existing README. No new Markdown planning file was added.
  U3 remains isolated and blocked on its own gates; encryption remains deferred.
  No U4-U14 or other epic was started. Demo handoff is partial, not a verified
  release or a claim that the requested complete workflow has been demonstrated.

## Structural Wall Detector & Direct Wall Editing Checkpoint

- Problem Solved:
  The legacy wall detector (Canny + Hough) falsely classified thin interior ceiling grids, wiring, dimension lines, and troffer/lighting outlines as walls. The review workspace was room-first instead of wall-focused. Thin interior grid lines on commercial floor plans (such as `6-lightinglayout.jpg`) must remain unmarked, as true walls are only thick exterior boundaries and thick interior partitions. Saving an otherwise valid walls-only layout previously failed due to an artificial room polygon requirement in `demo_interpretation_service.py` and `pseudo_labeling.py`. Furthermore, 3D preview previously extruded walls from room boundaries instead of using actual `draft.walls`.

- Implementation:
  1. Structural Wall Detection (`backend/app/ai/wall_detection/`):
     - Added `structural_mode: bool = False`, `min_stroke_radius: float | None = None`, and `estimated_thickness_pixels: float | None = None` to `WallDetectorConfig`.
     - Enabled `structural_mode=True` in `demo_cv.py` for floor plan interpretation.
     - Implemented `_detect_structural_wall_lines` and `_consolidate_wall_segments` in `detector.py`:
       - Analyzes ink via local distance transform (`cv2.distanceTransform`) on inverted binarized plan.
       - Estimates stroke thickness relative to image resolution using Otsu/median of non-zero distance peaks.
       - Reconstructs thick structural strokes via morphological opening/reconstruction and rejects thin grid lines (< min_stroke_radius), dimensions, wiring, and fixture lines.
       - Filters out isolated non-wall blobs (such as lighting troffers or columns) using structural bounding box dimensions, aspect ratio, and stroke solidity.
       - Extracts centerlines using morphological skeletonization (`cv2.ximgproc.thinning` or iterative Zhang-Suen morphological thinning).
       - Consolidates supported parallel wall edges into one centerline with estimated pixel thickness.
       - Merges collinear fragments only where underlying ink evidence supports continuous connection across gaps.
       - Supports diagonal walls without forcing horizontal/vertical constraints.
       - Preserves raw candidate metadata, uncertainty score, and original source coordinates.
  2. Wall-Focused 2D Workspace & Direct Wall Editing (`frontend/src/features/detection-review/`):
     - `wallEditorUtils.js`: Helper functions for `formatWallDimension` (scales to feet/inches when approved scale exists, labels as unscaled otherwise), `constrainPoint` (90-degree horizontal/vertical locking), `findSnapPoint` (endpoint snapping with configurable tolerance), `wallMidpoint`, and `wallTextRotation`.
     - `DemoInterpretationCanvas.jsx`:
       - Default layers display walls and original blueprint; room polygons are hidden by default.
       - Large light-grid canvas matching reference UI.
       - Walls rendered as centerlines with estimated thickness (`estimated_thickness_pixels`) and dimension labels. Selected wall highlighted in electric blue (`#2563eb`).
       - Draggable endpoint handles for resizing + draggable wall body for translating.
       - Click-to-start / click-to-finish drawing tool with live preview line and snap indicator circle.
       - Floating status pill: "Press the 'Esc' key to stop drawing walls".
       - Escape key cancels drawing / returns to move tool; Delete/Backspace key deletes selected wall.
       - Shift key locks drawing / endpoint dragging to strictly 90° horizontal or vertical.
       - Mini viewport controls (+, −, Fit to screen, percentage indicator).
       - Pan & zoom aware coordinates for drawing, dragging, and snapping.
       - Allows manual wall creation even when detection finds zero walls.
     - `DemoInterpretationPage.jsx`:
       - Dedicated top toolbar: Move Walls, Draw Walls, Delete Walls, Undo, Redo, Blueprint toggle & Opacity slider, 2D / 3D toggle, Done ».
       - Full undo/redo history stack (`Ctrl+Z`, `Ctrl+Y`).
       - Flags dependent room geometry as stale when walls are modified, providing an optional action to exclude stale rooms on save.
  3. Save and Canonical 3D Synchronization:
     - Relaxed `demo_interpretation_service.py` and `pseudo_labeling.py` so layouts with accepted walls and/or symbols save successfully without requiring room polygons.
     - `draftRoomScene.js`: Extrudes 3D walls directly from `draft.walls` using position, length, relative height, and thickness, falling back to room edges only for legacy layouts.
     - `DraftRoomPreview.jsx`: Allows 3D preview when walls exist without requiring room polygons.

- Verification & Test Results:
  - Backend Unit Tests:
    - `tests/test_wall_detection.py`: 38/38 tests PASS (including synthetic structural stroke detection, thin grid rejection, collinear merging, diagonal wall preservation, and resolution scaling).
    - `tests/test_demo_cv_interpretation.py`: 10/10 tests PASS.
    - `tests/test_demo_interpretation_api.py`: 8/8 tests PASS (including walls-only layout save without room polygons).
    - `tests/test_canonical_geometry.py`, `tests/test_canonical_extension.py`, `tests/test_wall_coordinates.py`: 46/46 tests PASS.
  - Frontend Tests:
    - 39 test files, 328 tests PASS (`vitest run --run`).
    - ESLint: 0 errors, 0 warnings (`npm run lint`).
    - Production Build: Succeeded in 504ms (`npm run build`).
  - Sample Image Validation:
    - Sample 1 (`sample.jpg` / job 23954, residential): Reduced 207 fragmented line detections down to 21 structural wall centerlines.
    - Sample 2 (`6-lightinglayout.jpg` / job 23953, commercial): Dense interior ceiling grid lines (troffers, wiring, grid cells) are completely rejected from wall detection; exterior boundary and interior core walls are retained.
  - Limitations:
    - Automated browser subagent execution encountered a host environment limitation: Playwright driver download failed with HTTP 404 (`https://playwright.azureedge.net/builds/driver/playwright-1.57.0-win32_x64.zip`), so browser session recording could not be initialized by the subagent. The Vite frontend and Uvicorn backend are verified running locally for manual browser review.
    - No reviewed ground truth annotations exist for the commercial lighting layout, so no uncalibrated numerical precision/recall percentages are claimed.

## September 25 development-training reconciliation (not production approval)

- Owner personally attested review of groups 1–22 and authorized local development training on the exact combined export, SHA-256 `829de08a31e2c8014ac6194cb958f999b2aa534297af749a661b31d7a383afc9`. Private `storage/training/authorizations/dev-g1-22-829de08a31e2.json` binds that statement to 52 page IDs, source hashes, groups, coordinate frames, and page numbers. It explicitly records a development-only exception to separate dataset-approver sign-off. No independent approver or production-release approval is claimed. Source bytes and live workspace session were not changed.
- The combined export has 67 pages; 52 are in groups 1–22. Its annotation arrays differ from the newer live workspace on 59 pages, so this experiment uses the named export without overwriting the live session. Within groups 1–22, the export contains 2,046 symbol records: 1,639 corrected, 70 manually added, 52 needs-review, and 285 deleted. Six pages are marked exclude and three rescan-needed. These and unresolved items remain excluded or pending; omitted regions are not empty-background labels.
- Previous 433-crop SmolVLM run remains inactive. Its 0/67 score is exact generated-label matching on held-out workspace groups, not full-page detection. Fifty-five of 67 validation crops use labels absent from training; generation often repeats an incorrect label. The old group split is not project-safe: groups 1–6 contain related floors of one building. Project identity for the other groups remains unverified, and rights for the two third-party reference sources remain unresolved.
- Bounded two-class diagnostic used 12 training and 11 development crops from existing immutable records. Sixty CPU LoRA steps changed adapter weights, left the base unchanged, and reloaded successfully. Exact generated-label results: 2/12 on its training crops, 1/11 on its development crops (before: 0/11); development loss fell from 9.282 to 0.729. This demonstrates weight updates but **does not establish useful symbol learning**. Its old group split is diagnostic only, not project-separated evaluation. Private manifest SHA-256 `0e036a2ffcc7c4a8772f43f41af04de159706cc6cfe04bc1d393440ba447e5e0`; adapter SHA-256 `9e3fd084448866f3a19e221ca5d115acd011adca4ad33c970c6629fc49ef59e7` remains inactive.
- Full-page detector training, project-separated evaluation, demo integration, 85% detection claim, and production activation are **NOT COMPLETED**. Concrete next gates: verify project identities linking related pages across all groups; resolve third-party source rights before using those images; choose and verify a partial-label detection method or establish exhaustively reviewed regions; improve tiny-subset learning before a larger run. Do not reuse workspace group numbers as independent project IDs.

### September 25 bounded learning and localization diagnosis

- Inspected all 12 training crops in the two-class check. Five `Panelboard` crops are visually heterogeneous: some show only a circled number, while others show a clipped triangular/panel mark. Seven `LED orientable downlight` crops are tiny, often clipped line fragments; the orientable qualifier is not visually recoverable from several crops. Source annotation and exact drawing-legend identity/hash pairing validate mechanically, but that does **not** prove these crop pixels unambiguously show their intended class. The private side-by-side visual/output report is `storage/training/diagnostic-g1-22-829de08a31e2/crop-audit.html` (ignored); its JSON has all 12 raw base and adapter predictions, normalized predictions, expected labels, IDs, and processor shapes. On those 12 training crops, base exact = 0/12; adapter exact/normalized = 2/12. Two adapter outputs say `LED downlight` for `LED orientable downlight`; these omit a potentially distinguishing qualifier and are **not** counted equivalent. Other outputs are wrong or underspecified, not merely punctuation/case mismatches.
- The processor supplied `pixel_values` and an image mask (`[1,1,3,512,512]` pixel tensor for an example). The chat-template prefix exactly matches the training sequence; 93 prompt tokens are masked and four answer/end tokens supervised for the `Panelboard` example (` Panelboard<end_of_utterance>`). The same pinned local base and processor were used for pre/post generation and for adapter reload. Greedy decoding uses `do_sample=False`; the old 60-step loss fell but free generation remained weak. This separates answer-token loss reduction from actual class selection.
- A separate six-example, two-class **memorization-only** check used three reviewed source crops per class, stable short IDs `DOME`/`PULL`, and 90 bounded CPU LoRA steps. Exact training-ID matches at steps 0/30/60/90 were **0/6, 0/6, 3/6, 6/6**; the saved adapter reloaded on the same pinned base/processor and reproduced **6/6**. First-step LoRA gradient L1 was 2020.97, distinct image tensors differed by mean absolute 0.8055, the adapter changed and the frozen base did not. Private report and inactive adapter are `models/vlm/adapters/memorization-20260925-six-crops/`. This proves a small target can be memorized; it is **not** held-out accuracy, class disambiguation, full-page localization, or a live checkpoint. The source annotations still need class-specific visual QA before a larger supervised run.
- Historical crop evaluation was audited by drawing-legend **identity** rather than label text. Groups 1–6 are related floors and cross the old train/development split (groups 1,5,6 train; group 4 validation). Of 67 old validation crops, **65** have legend IDs absent from training, even though only 55 have absent label text; the remaining two are not verified independent projects. Consequently the valid project-separated closed-set score has **zero scorable records**, not 0% model accuracy. The `0/67` historical exact-text result remains a reproducible diagnostic, not a model-quality metric. Other project relationships are unknown and no split was silently rewritten.
- A bounded localization probe reused the existing local YOLO rollback checkpoint, without downloads, on a source-hash-verified page not in its training list. At threshold 0.50 it produced zero detections on the full page and across 90 overlapping 256-pixel tiles; reviewed-positive localization recall was **0/2** at IoU 0.5. There were no localized candidates for classification comparison. Precision is **unsupported**, because unmatched areas on this partially labeled page cannot be called true negatives or false positives. The private evidence is `storage/training/diagnostic-g1-22-829de08a31e2/localization-probe-v2.json`. This checkpoint is not the six-crop VLM adapter; no live model changed.
- Added diagnostic scripts and split-audit regressions. Future crop preparation joins groups 1-6 only for the exact reviewed export hash; future crop-training reports embed the evaluation audit and explicitly mark project-separated crop accuracy unsupported. Historical manifests/results are preserved unchanged (a prior-split conflict is rejected rather than rewritten). Focused script tests: 6/6 PASS. Local inference probes PASS as executions but fail the desired detection outcome. No full-page detector training was launched. Next checkpoint: establish verified project IDs/source rights, class-consistent readable crops and exhaustively reviewed regions (or an explicitly masked partial-label localization method); then run a project-separated, class-seen detection experiment and report actual precision/recall. No 85% claim, production approval, or activation.

### September 25 positive-only localization checkpoint

- Rechecked all 12 suspicious crop records against exact source hashes, source dimensions, annotation boxes, and RGB pixels. All 12 saved crop pixel arrays equal direct crops from their annotated source boxes. No coordinate conversion, scaling, or crop-generation defect was found. Source annotations themselves clip or ambiguously label the glyphs; changing crop code would not correct those targets. Private `proposed-corrections-v1.json` records 12 assistant exclusion/box-review proposals without changing original annotations or inventing replacement classes.
- New private dataset version `storage/training/symbol-crops-20260925-localization-v3/manifest.json` (SHA-256 `3f02d27dd19fd798509eaf53a98767fa07146b4c3656f7a782538b50db251b5f`) binds the authorized export and technical-exclusion snapshot. It has 421 train records, 43 drawing-legend IDs, 12 technical exclusions, and **zero scored validation records**. Original historical manifest remains unchanged. Groups 1-6 stay together; groups 8-20 form a conservative unresolved split cluster. Source title blocks distinguish the group-7, group-21, and group-22 projects. Identical label text across different legend IDs is not silently merged; orientable and ordinary downlights remain distinct. No project-separated closed-set score is available from this version.
- Exact local YOLO rollback checkpoint is `18b34d5143c3150e9dd4bed4b31e1cdf5615b1039dcc0f1d6c3fdb7c8e210771` (four classes; **no Pull station class**). Its run manifest records random initialization, 128-pixel crop training, and no production activation. On the same source page, its threshold-0.50 output has zero candidates; at 0.001, max raw score is 0.2344. This is unsuitable for this class, not an integration/coordinate failure. The comparison does not establish model class recall.
- Bounded development-only OpenCV template probe used two clear reviewed Pull station crops as positive exemplars (`sheet-20:L05`), five other positions on the same page held out, and no unlabeled-area negatives. At exploratory template score 0.60 and a documented page-specific plan ROI, it returned seven boxes: two exemplars plus **5/5 held-out reviewed positives**, all IoU >= 0.5; center error 1.4-5.7 source pixels. Score and ROI were examined against this page, so this is **not independent held-out accuracy or project generalization**. Precision remains unsupported on the partially annotated page. At 0.70, only 1/5 held-out positives matched; without the plan ROI, score 0.60 also matched one title-block mark. Cross-page raw similarity is lower and no cross-page recall is claimed.
- Private evidence: `storage/training/diagnostic-g1-22-829de08a31e2/pull-localization-roi-v2.json` (SHA-256 `f5d253b5c405a8928e685e0503d24da803ee22f26971fc4226c13ed49802b171`) and its `.html` SVG overlay, with reviewed targets, candidate boxes, and missed/uncertain states. This is a deterministic page-specific experiment, **not** the LoRA crop adapter, production detector, or demo checkpoint. No review/save/2D/3D integration or live activation changed.
- Focused tests: crop-training tests 7/7 PASS; localization tests 2/2 PASS; Python compilation and `git diff --check` PASS (line-ending warnings only). Full app/database regressions NOT TESTED because app integration did not change. Next: validate source-region candidate quality across distinct pages/projects, resolve unreviewed candidate regions or use fully reviewed ROIs for precision, and only then add an explicitly experimental model-selection path through existing review and canonical save. Do not claim 85% detection.

### September 25 frozen cross-page localization and development review path

- Frozen Pull station probe: exact `sheet-21` SHA-256 `8cd5962e233fe1dbbe2de981a6169665720e49fb0b2da81215d7532a4299b1ed`, two reviewed template IDs `1421451ddf2e1217c0833e17` and `0fa577e32ac65b7d915452e0`, source boxes `(1043,1779,1071,1807)` and `(1986,1895,2014,1924)`, OpenCV grayscale native pixels, `TM_CCOEFF_NORMED`, threshold **0.60** (similarity, not calibrated confidence), 9x9 local peaks, descending-score suppression at center distance <14 px or IoU >0.3. Positive match rule: center error <=14 source px; IoU >=0.5 separately. Cross-page search rule was declared as the **full image**, instead of carrying the prior page-specific ROI to a different layout. No target-location ROI or scale tuning was applied before the run.
- Frozen target `sheet-19` SHA-256 `c8501119a41e3686502af24d34c4554d19016802cc9ed28f691beec3b615389b`, 2512x2084 pixels, is a distinct second-floor FDAS page in the **same Group 7 project**, not independent test data. It returned seven candidates. The private immutable report is `storage/training/diagnostic-g1-22-829de08a31e2/pull-cross-page-frozen-v1.json`, SHA-256 `2cd5a78dd5211bcdd9ef8a51fa146b643357768d9aaed9054b8d316c123845d3`, with `.html`/`.png` overlays and a `-candidates.png` contact sheet. Visual comparison with the page and legend suggests all seven are edge/railing-hatch false matches; separate `pull-cross-page-assistant-review-v1.json` proposes rejection without claiming human approval. Boxed F glyphs are visible elsewhere, but no user-reviewed Pull station boxes or exhaustively reviewed negative regions exist on this page. **Cross-page reviewed-positive recall and precision are unscored**, and the result does not support cross-page detector quality. Re-running the old same-page diagnostic still returned seven candidates and 5/5 withheld positive locations; it remains page-tuned development evidence only.
- Added a development-only selectable `experimental_pull_station_template` processing mode. The exact source template page is copied byte-identically into ignored local `models/vlm/pull-station-template-v1`; job creation and worker execution verify its SHA and bounded size. The existing configured detector remains selectable. A selected one-based page is required for this mode; the job pins provider/settings and the durable worker writes strict immutable candidate provenance. Original normalized uploads are not changed. Pull station candidates carry unknown catalog mapping and explicit similarity warnings, start as **unresolved** in the existing Konva review, and support accept/correct/reject/add plus append-only draft save/reload. No automatic training, VLM inference claim, or production activation occurs. Production mode and an active release/manual-review fence reject the experimental mode.
- Verification: actual `sheet-19` payload validated with 7 advisory source-pixel symbols; source/template/target hashes remained unchanged. Isolated backend focused suite **100 passed, 2 deselected, 15 subtests passed**; the two deselected tests assert stale OpenAPI operation counts (39/old route set versus 43 with unrelated uncommitted estimate endpoints) and fail when run, so the combined broader regression is **FAIL**, not passed. Focused frontend 73/73; full frontend 355/355; ESLint and Vite build PASS (existing chunk-size warning); script tests 2/2; compilation and diff check PASS. A route test exposed and fixed a Pydantic constraint mistakenly applied to the entire `page_numbers` list. Browser UI verification is **NOT TESTED** because the shared browser surface was unavailable. The existing test client verifies draft correction revision/reload, but no authenticated live upload/click-through was performed.
- Canonical 2D/3D placement for these supplied pages is **NOT TESTED**: the second page has no exact uploaded source record in the local app, and no active Pull station legend entry was found. Approved page scale/elevation, wall dimensions and designer review would also be required before canonical publication. Draft proposal review/save is not blocked by those inputs. The frozen cross-page miss needs a separately declared development adjustment and new visually reviewed data before any quality claim. No 85% detection claim or larger training run.

### September 25 adjusted Pull-station review experiment (development only)

- Preserved the frozen second-page report (`2cd5a78d...`) and seven assistant reject proposals (`1f9ad10a...`) byte-for-byte. The original supplied `sheet-21` and `sheet-19` files still match their recorded SHA-256 identities. The latter is Group 7 second-floor FDAS, related to the template page, not an independent test.
- Inspected both boxed-F source templates, seven frozen candidate crops, the source legend, and full target image. Native-scale normalized correlation at threshold 0.60 confuses repetitive perimeter hatching with the boxed-F glyph. Core-only correlation scores were also high on hatch crops (up to 0.756) and weak on several reviewed true source crops, so an interior-glyph threshold was rejected. Exploratory 0.8 scale produced 49 target candidates/0 of 7 same-page reviewed positives; 1.0 produced 7 target candidates/7 of 7 same-page positives; 1.2 produced 5 target candidates/1 of 7 same-page positives. Rotation was not added: both supplied drawings display upright glyphs. The cross-page target was used to choose the adjustment and is now **development data**.
- The opt-in locator now evaluates 1.0 and 1.2 template scales and selects one page-wide scale by the count of matches in the central 82% of page width, while returning all matches at the selected scale for review. This avoids silent edge acceptance, preserves the original fallback, and pins the new configuration hash `9844af37...` to new jobs; old pinned configurations are not silently reinterpreted. On the actual supplied pages the runtime returned 8 native-scale proposals for `sheet-21` and 4 at 1.2 scale for `sheet-19`. The latter overlay (`pull-cross-page-adjusted-v2.png`) supports three assistant-proposed boxed-F matches and one assistant-proposed rejection; other visible symbols remain missed. Private `pull-cross-page-adjusted-assistant-review-v2.json` records those judgments without human approval. Similarity is not calibrated confidence. Precision and reviewed-positive recall on `sheet-19` remain **unscored**.
- Read-only local database check found **zero** upload source records with the exact `sheet-19` hash and **zero** active Pull station legends. `/api/auth/me` returned 401 without an authenticated session; the connected browser inventory had no browser. Therefore actual upload, role-checked legend creation, live process/review/save/reload, and canonical 2D/3D are **NOT TESTED**; no duplicate upload or unauthorized admin write was attempted. The exact proposed legend identity is `sheet-20:L05` (Pull station), requiring an active numeric VED legend class through the ADMIN workflow, not an invented approval. Page scale/elevation, wall geometry and designer review remain prerequisites for authoritative 2D/3D placement.
- The unrelated dirty estimate router adds four OpenAPI operations, yielding 43 against older 39-operation assertions. No estimate files/tests were edited. Current focused synthetic backend locator/candidate/outcome checks: **32 passed**; focused frontend review test: **4 passed**. Database-backed checks and browser walkthrough remain pending isolated test configuration/authenticated session. No larger training or production activation was started. Next smallest experiment: obtain designer/admin authenticated UI access, import the exact source once, review these four candidates and missed glyphs, save/reload a draft, then collect complete reviewed target/negative coverage on a distinct project before scoring.

### September 27 supervised multi-class development checkpoint

- User-attested groups 1–22 development authorization remains bound to export SHA-256 `829de08a31e2c8014ac6194cb958f999b2aa534297af749a661b31d7a383afc9`; no separate human approver or production authorization is inferred. The exact reviewed-crop source manifest has 421 records across 43 legend IDs, but no verified independent evaluation split or complete page labels. Two third-party reference source sheets (51 and 52) remain excluded for unresolved underlying-image rights; their reviewed annotations are not enough to authorize those pixels. Centralized approved legend semantics may still label VED-owned pixels, such as the troffer examples on sheet 11. Originals and prior manifests remain unchanged.
- Developed a bounded partial-label YOLO loss that trains on full-context 256-pixel tiles with reviewed positives and only a 12-pixel local negative collar; other pixels are ignored, not scored as empty background. Used existing local COCO `yolo11n.pt` weights (SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfdf94632bd9a8da63ae6417644ee1`), CPU, no new model download. Three-family diagnostic dataset: 96 reviewed examples, 4 drawing-scoped class IDs, 3 source pages, manifest SHA-256 `22fab4a937e3e0cc95cc1a726e59f1da17ec7565987531fd9187e41ccec96add`. Pinned 12-epoch development checkpoint SHA-256 `42c950006c3abe91af8218d14d6b4a52c8bc58b376457d75348dfc16992dd5cc`; ignored private weights at `storage/training/symbol-detector-dev-20260925-partial-run3/weights/best.pt`. Resubstitution mAP50 0.778 is **not** independent accuracy.
- Frozen page probe: 256-pixel tiles, 192-pixel stride, 320-pixel model input, detector score 0.25, same-class NMS IoU 0.5, reviewed-target match IoU 0.5. On training-source sheets 11/21/40, reviewed-positive recall was 41/42, 30/43, 10/11; fused proposals 67/51/48. A different page in the same building (sheet 17) yielded 71 proposals, visually including troffers and text/grid mistakes, without a reviewed target set; it is **not** independent evaluation. Precision and 85% detection accuracy remain unscored. The previously attempted 138-class fine-tune was invalid for deployment and remains inactive.
- Tested a broader rights-safe nine-family, ten drawing-ID dataset (158 reviewed boxes, 7 pages), manifest SHA-256 `af909af79ae630f2d773fbeb26f46d1bf6f12950317670cca6c5e0b23da4c578`, 12-epoch checkpoint SHA-256 `78860a73a5ec64f2957626d1f5f1e7cb817cae4b2b5a2b947da12c77ce885e32`. Frozen same-source page probes gave reviewed-positive recall 42/44 sheet 11, 36/48 sheet 21, 6/11 sheet 40, 0/5 sheet 49, 2/11 sheet 30, 3/32 sheet 38 and 1/7 sheet 12. Sheet 11 had 103 proposals versus 67 for the narrower model, with visible grid/text mistakes. This broader checkpoint is **not activated**; its resubstitution scores are not generalization evidence.
- The all-available-class experiment used all 280 rights-safe reviewed boxes, 31 drawing-scoped IDs (28 visible labels), 12 source pages, and the same frozen preprocessing/threshold. Dataset manifest SHA-256 `7ec7f66cc3feee6f2b7c47d7eba07566f681843fb65834035e3bdfff5c08b4ec` and 12-epoch checkpoint SHA-256 `fa6434e709fb64f9100f921d29a81c17772c4f4659815a2e79a6965ab6fd1290` are private/ignored. Five of twelve same-source pages returned zero candidates at score 0.25; reviewed-positive localization/class recall on the others ranged from 0/3 to 42/47, including 11/48 sheet 21 and 9/40 sheet 31. This is a failed breadth experiment, **not activated**. Several classes have only one or two examples, so broad class detection is not established by falling training loss or resubstitution metrics.
- Development-only opt-in processing now pins and verifies the narrow checkpoint/dataset hashes and explicit page; existing detector remains selectable. It sends unresolved, uncalibrated, drawing-legend-provenanced symbol proposals into the existing review/draft workflow while keeping geometry review authority and original bytes unchanged. A source page was run through the locator and candidate schema; synthetic/database-backed tests cover pinning, worker persistence, and draft reload. Live authenticated browser upload → correction → save → 2D/3D was not verified. Local model artifact is ignored and must be provisioned separately on another machine. Ultralytics code/weights carry licensing obligations; no commercial/production release is authorized.
- Next data-quality gate: project-separated reviewed page set with adequately reviewed negative regions, wider symbol-class coverage, drawing-specific class reconciliation, and measured held-out precision/recall. Correct or reject proposals before canonical save; do not turn unreviewed predictions into training truth. Keep local VLM, training, and production activation statuses separate from this supervised YOLO development experiment.
- Checkpoint verification: dataset/partial-loss unit tests 3/3 PASS; isolated focused backend 36 tests plus 10 subtests PASS; isolated template-worker regression 7/7 PASS after correcting its missing synthetic `scale`; frontend 357/357 PASS, ESLint PASS, Vite build PASS with size warning, Python compilation PASS, staged diff check PASS. Isolated full backend: **991 passed, 17 failed, 4 skipped** after the fixture correction; the failures are historical OpenAPI route-count assertions against four unrelated, uncommitted estimate operations in the dirty worktree. Browser walkthrough and canonical 2D/3D placement remain NOT TESTED. This is an implementation checkpoint, not model-quality or release acceptance.

### September 27 linked-legend development detector (opt-in only)

- The owner-requested portable link revision `legend-links-g1-22-7a586d576d8e` was consumed without changing its source review or original scans. Its source-review SHA-256 is `7a586d576d8e6eeabb6dff5274424159f87ae3fe788af21bdac216ea72de7f21`. This revision is distinct from the older combined-export attestation; the owner's present request authorizes this local development experiment, not production approval or a separate human-approver signature. The link audit records 201 new associations across five legend IDs. Strict import checks reject changed page/annotation identity, unrecorded class edits and source-image dimension mismatch. The derived private manifest contains 206 reviewed boxes on seven VED-owned source pages; source pixels from rights-unresolved sheets 51/52 are excluded. Dataset SHA-256 `f5e8a06963bd9b820fdb4bfe66e3815c27dad8ed64336a674426bd807ebd0b53`; class counts: troffer 129, duplex-normal outlet 45, circuit homerun notation 20, magnetic contact 8, 200 mm LED recessed downlight 4. Other legend classes and unresolved/deleted/excluded boxes were not converted into training background.
- Bounded CPU 12-epoch partial-label YOLO run used the already-local base checkpoint; best checkpoint SHA-256 `c1236f94bfaf34e0b41c0ff8d7fa2c5122b06256201974bc32715e64bbf97d4c`. At frozen score 0.25, 256/192 tiling and class-aware IoU-0.5 matching, **171/206 reviewed positives** localized/classified on the same training-source pages, with **537 fused proposals**. Per class: troffer 121/129, duplex 28/45, circuit notation 18/20, magnetic contact 2/8, downlight 2/4. This is resubstitution/development evidence, **not held-out recall or precision**; visually, many unmatched boxes cover grid marks, text and structural features. Raising score to 0.50 reduced proposals to 312 but also positives to 144/206. No threshold was called calibrated confidence.
- A distinct-style supplied residential `sample.jpg` (800x600, unscored) produced eight proposals at 0.25: six duplex and two troffer. Visual inspection of the saved private overlay found all eight on other marks (not the proposed classes). This demonstrates domain-shift failure, not new-plan quality improvement. No 85% detection or production-readiness claim is made.
- Added a separate `experimental_linked_legend_yolo` development-only, explicit-page selector. It verifies local checkpoint/dataset hashes at job creation and worker execution, pins configuration and provenance, and sends five-class proposals through the existing candidate and correction flow with unknown catalog mapping. The prior narrow experimental model and configured fallback remain unchanged. Fixed the review page so **both** trained experimental providers initialize symbol proposals as unresolved (not silently accepted), while preserving an already saved review revision. The model does not auto-accept or auto-map project legends, train on uploads, alter canonical geometry, or activate a production release.
- Verification: builder/partial-label script unit tests **6 passed**; final isolated focused backend **45 passed, 2 deselected, 10 subtests passed** (the two deselected tests are stale OpenAPI-count assertions); frontend focused **75 passed**, full **361 passed**, lint and build **PASS** (existing chunk-size warning). Isolated full backend **994 passed, 17 failed, 4 skipped, 509 subtests passed**; this run preceded the final added configuration-fence regression, which then passed in the focused run. All 17 full-run failures are stale OpenAPI-count assertions affected by unrelated uncommitted estimate routes. Browser import/review and actual 2D/3D publication remain **NOT TESTED**. A direct API-test invocation initially selected the development database and hit teardown trouble; no further direct database tests were run. Read-only inspection showed 36 synthetic `f2-test` users, 9 synthetic F2 projects and 9 synthetic F2 roles in that database, but without a prior snapshot their origin cannot be attributed or safely cleaned here. Subsequent database tests used the isolated runner's restricted/empty-database preflight. Preserve unrelated dirty files and `stash@{0}`.
- Next gate for useful automatic detection on newly imported drawings: obtain complete, independently reviewed positive/negative regions from distinct projects and improve cross-style localization/class discrimination. Until measured, the five-class selector is an experiment for manual review only; production use and 85% target remain pending.

### September 27 approved-catalog coverage and generic-localization diagnostic

- Started the owner-requested path toward all **286 approved legend entries** without treating catalog approval as proof of detectable image examples. The immutable, hash-bound private `all-approved-g1-22-7a586d576d8e-v1.json` manifest (SHA-256 `d2531f7422f827b8d1be02b0fb07f8e0cfc5c2689dd043f78d09bd21fce6881e`) inventories **790 eligible reviewed boxes, 56 legend IDs, 21 source pages** under the existing groups 1–22 development authorization and source-rights fence. Of 286 catalog IDs, **230 have zero eligible boxes**: 218 have no approved symbol instance in the link audit, and 12 have instances excluded by the current gates. Eligible-class support is imbalanced: 10 IDs have 20+ boxes, 26 have 5–19, and 20 have only 1–4. Third-party source pixels, excluded/rescan pages, unresolved mappings, deleted symbols, and protected splits were not converted to training labels. Original source/review/audit hashes still match the revision.
- Prepared a separate class-agnostic, partial-label **YOLO** localization diagnostic from the same 790 boxes (private dataset manifest SHA-256 `5c02e3d2308053789c8f1ba4ce3a07eea6b294139f52a3a2194b4bd031f8eb99`). It preserves each original legend ID in the audit but trains **one generic location class**, not 56 or 286 class identities. A bounded three-epoch local CPU run produced checkpoint SHA-256 `e412cffe131a2a9edd55350a17b5599eea6be260bb7bdaafe6c9d9bac3250e31`. Training-image mAP50 was 0.155 and is not held-out evidence. At score 0.25 on its 21 training-source pages, **290/790 reviewed positives** localized at IoU >=0.5, alongside **5,597 fused proposals**. Visual overlays show frequent boxes on blank grid cells, margins, and text; precision is unscored because those pages lack exhaustive negative-region review. This generic checkpoint **failed** the usability diagnostic and remains inactive. Longer training alone is not justified: the partial-label loss intentionally ignores most background, so it does not teach this generic model to reject those regions.
- No page carries an explicit exhaustive symbol-completeness/negative-region decision; `candidate_after_corrections` is not such a decision. Project-separated, independent detection performance remains unverified. The existing five-class opt-in mode and fallback are unchanged; there is no 286-class detector, new production model, or automatic class mapping. Focused script tests: catalog-manifest **3 passed**, dataset/loss **5 passed**; compilation and real full-page probe executed successfully. App/backend/frontend regressions were not rerun for this script-only checkpoint. Next safe work: obtain verified complete positive/negative regions on distinct projects and more reviewed examples for the 230 unsupported IDs, then compare class-agnostic localization and drawing-legend classification separately before expanding the selector.

### September 27 56-legend general-detector diagnostic

- At the owner's request, prepared an immutable, Git-ignored 56-class YOLO dataset from the same hash-bound 790 eligible boxes on 21 rights-cleared source pages. Each drawing legend ID is a separate class even when labels have identical wording. Manifest SHA-256: `2cc09b229bc24ed21fc58d1eb8238cc1f3a5ffc68f070c9daa5372c50a09775a`. Twenty classes have fewer than five reviewed examples. Original images and prior manifests were not changed; no external data or model was downloaded.
- Ran a bounded three-epoch CPU diagnostic with the existing local `yolo11n.pt` base and partial-label loss. Best checkpoint SHA-256: `78b4536e75e40fe3341d469b20dc807fb2c987741e1e43684c4ce0ae589105c2`. Training-image mAP50 was **0.01768**, not an independent metric. A full-page, same-training-source probe at score 0.25, 256/192 tiling and same-class IoU-0.5 NMS matched **32/790** reviewed positives at IoU >= 0.5, with **37 fused proposals on only 3/21 pages**; all proposals were class 55 (troffer lights). The page-17 overlay visibly misses many reviewed troffers. Precision and generalization remain unscored because pages are partially annotated and share training sources.
- **Usability gate FAIL:** this checkpoint cannot identify the 56 classes on new uploads, so it was not connected to automatic processing, added to the selector, or activated as a release. The existing configured fallback and experimental selectors are unchanged. Focused dataset/loss tests: **5 passed** when invoked as a script; an initial module-style invocation failed due the test script's existing import-path assumption, then was rerun correctly. App/browser/database regressions were not run because no application code changed. Next smallest safe step is complete reviewed positive/negative regions and independent-project examples, then a class-aware full-page detector evaluated before any automatic default change.

### September 28 detector-improvement review queue checkpoint

- Started the data-quality path for a small, measurable symbol set without retraining or activating the failed 56-class checkpoint. Added a source/hash-bound private queue generator that rejects changed source/dataset/probe membership or class mapping and refuses a probe that claims precision/generalization from partial pages. Its output keeps model proposals pending, records missed reviewed targets separately, and marks project identity and exhaustive symbol/background review as missing; it does not convert unmatched proposals to false positives or negatives.
- Immutable private queue `storage/training/approved-56-detector-20260928-review-queue-v4.json` (SHA-256 `78da3feb00ba3f5c100500b62d2b26ea2c3ba150d060dbf3958df90704bd063a`) covers **21 source pages, 56 IDs, 37 pending model proposals and 758 missed reviewed targets** from the frozen 56-class same-source probe, with source-bound overlay references. Highest-support IDs are troffer 129 boxes/3 pages, conventional smoke detector 59/1, and normal-power duplex outlet 45/2. Page count does not establish independent-project diversity; no page has a complete negative-region decision. These are candidate pilot classes, not a release set or performance result.
- Focused queue tests **4 passed**, including a source-bounds rejection; Python compilation **PASS**, generated queue hash and schema **PASS**, scoped diff check **PASS**. No app/API/database/browser behavior changed; those regressions were not rerun. Original source images, old manifests, existing dirty work and recovery stash remain untouched. Next checkpoint: visually review a bounded set of full-page symbol/background regions and source project identities, then train/evaluate only where the completed region and project separation permit honest precision/recall. The automatic upload detector remains unchanged.

### September 28 neighboring-label and partial-loss repair (development only)

- Diagnosed the frozen 56-ID checkpoint on 104 class-balanced training tiles: only 26 localized at score 0.001, four matched the correct class, and two matched at 0.25. Threshold reduction alone does not repair it. Packaging omitted 1,082 visible reviewed-neighbor label occurrences from 446 tiles. Found 25 IoU >=0.5 overlapping annotation pairs, including duplicates/conflicting identities; a private contact sheet documents assistant inspection. Original labels are preserved; exclusions are experiment proposals, not revised human approval.
- New version `approved-56-detector-20260928-neighbors-v2` retains numeric legend IDs, supervises fully contained reviewed neighbors, quarantines ambiguous overlaps, and skips collars intersecting known partial/ambiguous targets. It contains 617 tiles, 1,201 label occurrences and **673 unique reviewed targets across 53 IDs/21 pages**; IDs 5/9/45 have no usable target. Dataset SHA-256 `d702b3988c5bc242ffa5a2ba3ec8fbb019c4c365191fdb066587e372ae4fecd1`. All source permissions, protected splits and the development-only approval exception remain unchanged.
- The first neighbor run was stopped during epoch 9 after discovering that the historical 12-pixel loss collar assumes unreviewed background. Its partial checkpoints remain preserved, inactive and incomplete. New `ReviewedBoxOnlyLoss` excludes every anchor outside reviewed boxes; legacy classes remain compatible for old checkpoints. Disabled wording-based class-head remapping so duplicate legend names cannot collapse numeric identities. Training/probe scripts now enforce Ultralytics offline/no-autoinstall settings. A fresh bounded 12-epoch CPU run, `approved-56-detector-20260928-neighbors-run2`, uses only the existing local base; no larger model or hosted service is involved.
- One-to-one IoU matching separates localization from class matches and cannot reuse a prediction for two targets. The clean 12-epoch run completed in 612 seconds; best checkpoint SHA-256 **`43a66050b2b8841370f822961e74a5c0c80ec7be6f3e3a061536ba4bb0bbc80d`**. At frozen score 0.25 on the same 673-target subset, the old checkpoint matched **31/673**; the repaired/longer run localized **308/673 (45.8%)** and matched class plus IoU **280/673 (41.6%)**, with **516 proposals**. Fourteen IDs had at least one correct training-source match; this is not a claim of general detection support for all 53 IDs. Troffer 104/117, smoke `sheet-20:L02` 36/41, conventional smoke 44/59, duplex-normal 20/33, and floor-mounted data outlet 13/14. Median matched center error: 3.30 source pixels. These are resubstitution results, not independent accuracy; packaging, loss and training duration changed together, so gains are not attributed to one change alone. At postfiltered score 0.50: **232 locations, 221 class matches, 331 proposals**. Precision remains unscored.
- Private `approved-56-detector-20260928-neighbors-probe2/report.json` and 21 overlays preserve all proposals/misses. Assistant inspection confirms many true troffer locations, remaining missed targets, and incorrect proposals on structural circled numbers in the upside-down security drawing. This is assistant evidence, not independent approval or exhaustive negative review. The supplied distinct-style source SHA-256 `185cac629279cbd96fe21e5b0e8df4d58b91641f9322b2f5880d7eb1ec704270` produced **zero proposals** at 0.25 (and at postfiltered 0.50); its unscored report/overlay are `approved-56-detector-20260928-sample-probe2`. **New-plan usability FAIL; 85% independent detection NOT ESTABLISHED.** No model selector, automatic upload detector, canonical geometry or production activation changed.
- Focused packaging/loss/probe tests **14 passed**; queue **4 passed**, link-manifest **3 passed**. Compilation and scoped diff checks **PASS**. Full app/API/database/frontend/browser/2D-3D checks **NOT TESTED** in this training-only checkpoint; prior unrelated OpenAPI regressions are not claimed fixed. Originals, old manifests/checkpoints, unrelated edits and `stash@{0}` remain preserved. Next bounded experiment: visually verified complete positive/negative regions across different drawing styles, box/class QA and rare-class support before another broad run or default-detector change. Keep real-data independent evaluation, production training approval and release gates pending.

### September 28 all-56-entry development implementation (live persistence gate blocked)

- Scope: ONE shared supervised YOLO checkpoint, not VLM inference, five classes, page templates, or a production release. Existing groups 1–22 owner-attested authorization and development-only approver exception stand. All **56 drawing-specific IDs / 790 reviewed targets / 21 source pages** are retained; identical wording does not merge numeric classes. Original annotations, prior artifacts, rights exclusions, deleted/unresolved targets and protected split history remain unchanged. All scored pages are training-source diagnostics; groups 1–6 are not independent projects and no sealed test was opened.
- Diagnosed/removed scarce-class omission from overlap quarantine for this owner-attested experiment only; original conflicts remain flagged, not relabeled. Two panelboard targets resemble homerun notation on assistant inspection. Reviewed-box-only loss ignores unlabeled background. Deterministic scarcity balancing adds **413 synthetic variants** (no independent sources): isotropic shrinking, contrast and mild blur, no directional flips/rotation. Version `multiclass56-20260928-v3` has **1,203 training images**, SHA-256 `e850443682f1b2f2fc6963beb7b60f4b316ca11d7417b1e664c6bddff3465c78`. Of 790 originals, 782 use actual inference-grid windows; eight seam-spanning targets retain explicitly flagged, unclipped centered supervision. Partial failed version v2 is preserved and not selected.
- Completed a 12-epoch CPU warm-start run and then a bounded **four-epoch** context-alignment run using existing local weights. No download, dependency install or hosted inference. Numeric class remapping disabled; all 56 head channels changed and all 56 selected training windows have raw expected-class/IoU score >=0.50. This proves learning/pipeline behavior, not generalization. Selected development checkpoint: `multiclass56-20260928-run3/weights/best.pt`, SHA-256 `865c5bceb3c62e4ba3ac9642e51b1b5cfae944a262de0ca840237342282c87de`; warm-start hash `523e47b9c8fd659091e3f0736baa300c4665fdc6d79d09a11eb19bbd558660df`. Earlier checkpoints remain retained.
- Same-source full-page results at fixed score **0.50**, 256px windows / 192px stride, deterministic second lattice offset 128, same-class IoU-0.5 suppression, one-to-one target matching: centered run matched **645/790** class+location; adding the frozen second lattice matched **703/790**; inference-grid training matched **767/790 (97.1%)** and localized **769/790 (97.3%)**, with **2,112 delivered proposals**. All 56 entries have at least one class+IoU match, including previously zero-output Bell/chime. These are partially annotated training-source recall measurements, NOT 97% independent accuracy. Precision, independent-project accuracy and production-quality acceptance are unscored. Candidate truncation is explicit; omitted proposals are not silently represented as complete output.
- Individual 56-entry report: private `storage/training/multiclass56-20260928-shared-coverage5/coverage.csv` and JSON contain reviewed training counts, numeric model/legend mapping, original training images versus synthetic variants, prediction counts, class+IoU matches and limitations. Report versions 1–4 are retained; version 4 corrects a report-only double count of augmented images as original center images. Version 5 binds the final shared-runtime repeat, `multiclass56-20260928-shared-probe4`, which reproduces the above matches and explicitly records one truncated page at the 200-candidate cap. Source-page overlays and head diagnostics remain in the corresponding ignored probe/diagnosis folders.
- Distinct residential sample at identical shared settings produced **two proposals in 2.184 seconds**. Assistant inspection identifies apparent wall-as-smoke-detector mistakes and many missed visible fixtures; no exhaustive reference labels or drawing-specific mapping exists for a numeric score. **New-style usability remains FAIL / 85% independent detection NOT ESTABLISHED.** This evidence is preserved in `multiclass56-20260928-sample-probe3`; no blanket readiness claim follows from training-source recall.
- Development integration implemented: new unconfigured development jobs pin this one hash-bound checkpoint for selected/all uploaded pages. Configured local gateways and promoted/production runtimes are not overridden; historical providers and rollback paths are retained. Removed page-specific detector choices from the upload UI. Proposals remain unresolved with training-legend/tile provenance and uncalibrated scores; existing approved-legend correction/draft saving and shared canonical geometry are reused, never auto-approved. User delegated the 96-versus-500 choice; selected development-only **500 small windows**, batch 8, serial CPU, unchanged other bounds, recorded in U1. No production budget increase.
- Task files: `scripts/{prepare_symbol_detector_dev,train_symbol_detector_dev,probe_symbol_detector_dev,diagnose_multiclass_symbol_detector,report_multiclass_symbol_detector}.py` and preparation/report tests; `backend/app/ai/floor_plan_interpretation/{experimental_symbol_detector,multiclass_symbol_detector}.py`; `backend/app/services/{processing_job_service,interpretation_job_configuration_service,interpretation_processing_service}.py`; new detector/worker tests; frontend `api/processingJobs.js`, `features/projects/ProcessingJobPanel.jsx`, `features/detection-review/DemoInterpretationPage.jsx` and their tests; existing U1 baseline/this ledger. Related pre-existing linked-provider edits remain in overlapping files, not blindly committed. Verification commands: bounded preparation/training/probe/report/diagnosis CLIs above; `python -m pytest` selected script/backend files (DB classes excluded); `python scripts/run_isolated_backend_tests.py` focused/full requests; `npm test -- --run` focused/full; `npm run lint`; `npm run build`; `python -m py_compile` changed modules/scripts; `git diff --check`.
- Fresh verification: **25 script tests PASS** (packaging, ignored loss, source/label transforms, seam fallback, matching, per-entry reporting, rights/link/queue contracts); **99 database-independent backend tests + 5 subtests PASS** (detector, candidate contract, canonical geometry/extensions, CV fallback). Dedicated all-56 worker persistence/provenance test written but **BLOCKED**, not passed. **78 focused frontend tests PASS**; full frontend **42 files / 364 tests PASS**, lint **PASS**, build **PASS** with existing >500KB chunk warning. Frontend mocked save/reload retains corrected coordinate/legend and original AI candidate; this is not live MySQL persistence evidence. Python compilation/diff checks **PASS**. Current source-generated OpenAPI: **35 paths / 43 operations**, SQLAlchemy metadata **33 tables**; includes unrelated estimate work, not live DB validation or a passing count regression.
- Required DB/API/review-save/full-backend checks **BLOCKED**: user authorized private restricted test-account repair. Passwordless local root connected; restricted account was absent. CREATE USER failed with XAMPP Aria `aria_log.00000001` write error 22; grants and ignored `.env` update did not execute. MySQL is now unreachable. An initially broader unit selection hit three connection setup errors before any connection succeeded; rerun explicitly excludes DB fixtures and uses an unreachable verification target. Isolated preflight refuses execution; no destructive database fixtures/reset ran. Account state must be reconciled after backup-first engine recovery, then retry private credential repair and isolated checks. Engine recovery is a separate requested authority, not inferred from credential replacement.
- Browser surfaces unavailable; live upload → correction → save/reload and canonical 2D/3D **NOT TESTED**. No geometry, scale, elevations or human approval invented. Branch remains `codex/vlm-localization-experiment` at `8683efa`; task edits are uncommitted pending required live verification. Unrelated wall/estimate/planning edits and `stash@{0}` preserved. No merge/push or completed-detector/release claim. Exact resume: recover MySQL with authorized backup-first procedure; reconcile/create restricted account and privately update TEST_DATABASE_URL; run isolated worker/review-save/full regression; connect browser for upload/correction/reload; publish only the scoped verified checkpoint. More reviewed styles/complete negative regions and independent projects are needed for quality, not a repeated permission request.

### September 28 stale backend follow-up

- Follow-up 503 traced to orphaned Uvicorn server child PID 27604 from terminated reloader PID 34448, still retaining the old port-8000 listener/settings. The first restart killed the launcher/reloader but not that spawned child; concurrent new server health did not prove which instance served login. Corrected by identifying and stopping both verified repository backend process trees and launching one instance without reload or access logging.
- Fresh verification: all three existing configured-provider identities resolve/flush with repaired database settings (rolled back; no profile or role changes); isolated authorization suite 12 passed, 2 subtests passed, 2 existing warnings. Fresh Google login remains NOT TESTED until a new user login. Database backups, unrelated changes, and recovery stash preserved; no production authentication bypass or OAuth-code replay.

### September 28 local MySQL recovery and authentication repair

- Owner-authorized backup-first recovery completed after InnoDB redo/data inconsistency and damaged privilege tables blocked authentication. Original damaged data remains at `C:/xampp/mysql/data-failed-20260928-auth`; verified offline snapshots remain outside the repository. Clean engine restored application, isolated verification, and accounting databases. Originals, unrelated edits, and `stash@{0}` preserved.
- Recovery limitation: original `floor_elevation_settings` was missing from the source engine despite retained table files. Previous rows could not be dumped; prototype schema initialization recreated this table empty. Historical elevation approvals need restoration/review before relying on affected geometry. Original table bytes remain preserved; complete historical-data restoration is not claimed.
- Restored application: 19 roles, 115 users, 55 projects, 54 floors, 69 floor plans; 33 tables. Existing roles retained. Privately repaired restricted `ved_app` CRUD access and verification-database-only `ved_test`; updated ignored `.env` URLs without exposing credentials. XAMPP MySQL binds to loopback, uses 64 MiB server packets, and runs with recovery mode off.
- Fresh PASS: all 75 restored tables passed `mysqlcheck --check`; actual configured authentication resolver create/commit/reload/reuse and default DESIGNER role passed, temporary identity removed, users restored to 115; isolated test connection passed. `python scripts/run_isolated_backend_tests.py tests/test_authorization.py -q`: 12 passed, 2 subtests passed, 2 dependency deprecation warnings. Backend restarted with repaired settings and access logging disabled; health 200, unauthenticated auth/me expected 401.
- Full backend suite and fresh Google browser login NOT TESTED here. Initiate a new login; posted single-use OAuth codes were not replayed. Detector/data/training/release statuses unchanged. Branch `codex/vlm-localization-experiment`, HEAD `8683efa`; no commit/push. Next: fresh browser login and isolated detector-worker/review-save verification.

### September 28 device-workspace UI checkpoint

- Screenshot/site-inspired layout preserves VED palette/fonts and shadcn-style primitives: vertical tool rail, floating viewport controls, persistent 2D/3D inspector. Detector names remain provisional; approved legend selections supply full device names without changing the original candidate. New symbols stay unresolved. Device dragging, classification, remove/reject, undo/redo, draft save/reload use one draft; removal is a preserved tombstone, not destructive deletion. Strict review serialization also fixes display-only wall-width fields leaking into API writes and retains untouched extension layers.
- Class-family Konva glyphs and procedural Three.js equipment replace anonymous markers/spheres: troffers, linear/round fixtures, outlets/switches, panel cabinets, alarms/detectors and pull stations. Unknowns stay neutral; homeruns are annotations. Draft 3D planar moves recover source pixels; saved 3D is inspection-only. Shapes have illustrative dimensions at recorded floor positions, not approved equipment sizes or mounting heights. No furnishings, loads, measurements, model improvements or release approvals invented.
- Changed owners: review page/tool rail/presentation adapter/Konva canvas, draft scene/preview, shared DeviceMesh/drag math/camera controls, saved 2D names and saved 3D inspector; corresponding frontend tests plus one existing backend review API regression. README and architecture aligned; no new Markdown, backend schema or production API change.
- PASS: focused frontend **10 files / 68 tests**; full `npm.cmd run test` **47 files / 405 tests**; lint/build (existing >500KB chunk warning); isolated `scripts/run_isolated_backend_tests.py -q tests/test_demo_interpretation_api.py` **10 passed**. Move/remove/reload preserves revision history/candidate JSON and excludes rejected symbols from canonical output in isolated MySQL. A UI test timing race now waits for the dirty-state effect instead of assuming DOM appearance proves that callback ran.
- Broader isolated review/layout selection: **27 passed, 1 FAIL, 26 subtests passed**. Existing `test_layouts_api.py:368` expects 39 OpenAPI operations; current unrelated estimate routes yield 43. Left untouched rather than change unrelated acceptance. Full backend suite NOT RUN. Browser/WebGL/visual responsiveness NOT TESTED: connected-surface inventory is empty. Local frontend and backend health both HTTP 200; HTTP health is not browser proof. Next manual check: open review, select/classify/drag a device in 2D and 3D, remove/undo, save draft and reload; inspect schematic equipment and responsive rails.
- Uncommitted on `codex/vlm-localization-experiment` at `8683efa`; no commit/push/deployment. Unrelated edits, originals and recovery `stash@{0}` preserved. No new real-data hash audit or training run; existing data/training/model/release gates unchanged.

### September 29 physical 3D preview and wall repair

- Replaced page-extent-scaled floor glyphs with typical-size equipment presets. Troffers are 0.6 × 1.2 m at the wall-top ceiling; switches/outlets/panels are upright at 1.2/0.3/1.5 m visual mounting defaults. Nearby wall-face orientation/offset does not rewrite the logical plan anchor; dragging converts back to shared source coordinates. Unknowns remain markers. No engineering dimensions or approval written to canonical data.
- Draft preview dimensions are adjustable (40 m page long side, 3 m walls, 180 mm thickness defaults); these are not approved drawing measurements. Saved metric geometry retains its actual scale and wall dimensions. Roof toggle starts hidden; covers use room polygons or an explicitly approximate wall-envelope fallback, without claiming known courtyard/opening geometry.
- Connect walls is an explicit undoable action in either review view: source-pixel bounded T/corner extension/overshoot repair, overlapping collinear union and preserved duplicate rejection records. Door gaps/distant gaps remain unchanged. Future editing snaps onto wall interiors as well as endpoints. Both views and revision saves consume the same repaired draft; no automatic modification of existing private saved layouts.
- PASS: focused frontend **7 files / 48 tests**; full `npm.cmd test` **50 files / 422 tests**; lint and build (existing >500 KB chunk warning). Tests cover physical scale, ceiling/elevation placement, wall-face drag conversion, roof controls, bounded joins, overlap tombstones, idempotence, doorway preservation, undo and mocked API save/reload. First focused run found floating-point intersection jitter; deterministic six-decimal source-coordinate normalization fixed it, then all checks above passed.
- NOT TESTED this checkpoint: actual browser/WebGL appearance and live database save/reload. Browser inventory empty; in-app browser unavailable. No backend changes or backend rerun; previous unrelated OpenAPI-count regression remains recorded above, not declared passing. README/architecture aligned. Uncommitted on `codex/vlm-localization-experiment` (`8683efa`); unrelated changes and `stash@{0}` preserved. No training, release promotion or deployment.

### September 29 shared symbol-quality repair (development only)

- Confirmed two general pipeline defects behind the sheet-08 complaint: reviewed placements moved into `layer=legend` by historical class linking were omitted despite preserved `original_annotation.layer=symbols`; reviewed-box-only loss provided no explicit non-electrical background examples. No page-specific inference mask, hardcoded target location, outside-wall deletion, new architecture/model download or hosted processing was introduced. Unknown switch subtypes, unrepresented orientable fixtures, wiring/geometry/open-below annotations remain distinct from supported device labels.
- Existing owner authorization reconciled without new approval requests. Immutable link revision recovery found **73 additional placements**, making **863 records / 59 drawing-specific IDs / 23 pages**. This bounded checkpoint preserves the existing **56-class head**: 40 recovered placements enter training, while 33 records belonging to three newly recovered IDs remain explicitly deferred (`sheet-04:L01`: 26; `sheet-01:L04`: 3; `sheet-07:L01`: 4), not merged into similar wording. These are not another 33 rejected user reviews. Original sources/review history, deleted/excluded/unresolved records and protected splits remain unchanged; all 23 source hashes and three revision-file hashes verified.
- Assistant visually inspected 31 bounded non-electrical regions across sheets 06/08/30 (grid bubbles, dimensions, columns). These produce 124 label-preserving negative variants, not independent samples or human approval. Negative crops cannot overlap recovered positives. New loss supervises only explicitly identified negative crops and reviewed positive boxes; other unlabeled areas remain ignored. Recovered placements now use actual shared inference windows (40/40), with tested unclipped seam fallback. Dataset `symbol-quality-20260929-v2` has **1,367 images / 830 reviewed targets / 56 stable numeric classes**; manifest SHA-256 `26c3dcc6a843e110f4ed373ba2abbf15d0261d70ecbe6dd1fba1d91410c10d37`.
- Actual bounded CPU training: first three-epoch attempt failed final validation because empty-target assigner masks were floating tensors. Fixed boolean normalization, added a real-model empty-target gradient regression, and preserved the failed run. Continued its two saved epochs with one same-dataset warm-start epoch in a new directory (optimizer explicitly reset); checkpoint `2c46051a30673d1fcee9255b7890ef9c2a5ff9481073b06bb4e419c0c272dafc`. A further two-epoch inference-grid-alignment run completed successfully. Selected development checkpoint `symbol-quality-20260929-run3/weights/best.pt`, SHA-256 **`5951c7375bed147244e36cbd93bfdd6ecc8ab3942b0a96fa842363ea087efa22`**. Final run train losses: box 0.46236 -> 0.40915, class 0.44137 -> 0.40285. Ultralytics resubstitution validation is NOT independent quality evidence.
- Frozen comparison: score 0.50, shared 256/192 tiling plus bounded second lattice, source-coordinate recovery, same-class IoU-0.5 suppression, one-to-one IoU >=0.5 matching. Baseline reused 21 checkpoint/configuration/source-hash-bound earlier predictions and freshly inferred the two recovered pages; candidate freshly inferred all 23. **Reviewed class+location matches 785 -> 806 / 830; localization 791 -> 807 / 830; inspected-negative-region proposals 33 -> 9; total delivered proposals 2,288 -> 2,196.** Original 790-target subset: 767 -> 777 matches. No page loses reviewed matches; all 56 IDs have matches. One page remains capped at 200 proposals and explicitly partial. Private comparison reports, overlays and all-56-entry `symbol-quality-20260929-coverage/coverage.csv` preserve counts and limitations.
- Sheet-08: **2 -> 6 / 8** supported reviewed targets matched (all five downlights, one of three homeruns); class-agnostic localization 7/8. Inspected-negative-region predictions **18 -> 3**; total proposals **54 -> 47**. Columns, intersections and other false proposals still occur outside those inspected regions. This is NOT a claim of three total false positives. Distinct residential sample produced three proposals in 2.521 s, visually on walls/kitchen objects while missing visible fixtures: **new-style usability still FAIL**. Whole-page precision, independent-project performance and the 85% objective remain unscored/unmet. Related floors and all tuned pages are development evidence, never an independent test set.
- Development integration: one shared checkpoint for new development jobs, unchanged 56-class IDs, explicit supervised-YOLO provenance (`reviewed-background-56-detector-v3`), hash fencing and unresolved review proposals. Old weights/datasets retained for rollback; no production promotion or automatic acceptance. Actual application detector entry point exactly reproduced the measured sheet-08 predictions (47, 8.085 s including load). Backend restarted after read-only preflight found no active leases or pending selected-page jobs; health HTTP 200. Twenty-four historical processing rows without page outcomes were reported, not modified. Existing saved detections/corrections are not overwritten; reprocessing creates new evidence.
- **PASS:** script unittest groups 5 importer + 4 preparation + 3 comparison + 17 existing dataset/loss/matching + 1 coverage = **30**; restricted isolated-MySQL pytest selection **37 passed**, two dependency warnings (background loss, detector/candidate contracts, worker provenance, review/save persistence, page outcomes). Compilation and diff checks pass. Commands: `build_linked_symbol_manifest.py`, `prepare_symbol_quality_experiment.py`, `train_symbol_detector_dev.py`, `probe_symbol_quality_experiment.py`, `probe_symbol_detector_dev.py`, `report_multiclass_symbol_detector.py`; `run_isolated_backend_tests.py -q tests/test_reviewed_background_training.py tests/test_multiclass_symbol_detector.py tests/test_experimental_symbol_detector.py tests/test_multiclass_worker_database.py tests/test_demo_interpretation_api.py tests/test_interpretation_page_outcomes.py`. All generated sources/artifacts stay Git-ignored. **NOT TESTED:** full backend/frontend regression, fresh authenticated browser upload/correction/reload and WebGL in this checkpoint. Earlier unrelated OpenAPI-count failure is not claimed fixed.
- Code owners changed: linked-manifest importer, versioned quality preparation/comparison scripts and tests; partial-label loss/training CLI and background tests; development detector pins/worker provenance and focused tests. Existing backend README and this ledger updated only; no new Markdown. Uncommitted on `codex/vlm-localization-experiment` at `8683efa`; no push/merge. Unrelated UI/wall/estimate/planning edits and recovery stash preserved. Next bounded work: context-preserving inspected negatives beyond isolated patches, cross-drawing class/box ambiguity (especially homeruns), and reviewed evaluation regions from another project/style. Do not extrapolate training-source recall to new-plan accuracy or silently discard the three additional recovered legend identities.

### October 2 source publication audit

- Consolidated the completed, previously uncommitted development work on the existing feature branch: estimates, review/2D/3D workspace, bounded wall/detector improvements, scripts, tests and existing documentation. Updated the legacy OpenAPI assertions for the four actual estimate operations (39 to 43); route-set assertions now enumerate those endpoints. This is a source checkpoint, not detector-quality, model-artifact, training, or production-release acceptance.
- Fresh verification before publication: restricted/empty isolated MySQL preflight and full backend **1029 passed, 4 skipped, 509 subtests passed**, with five dependency deprecation warnings; frontend **50 files / 422 tests passed**, Vite build passed with the existing large-chunk warning; ESLint passed for the published `src` tree; six directly relevant script test files passed **34 tests**. A broad script-discovery run had one unrelated import error because optional `peft` is absent locally; it is not reported as a pass. Staged diff check and added-line secret scan passed. In-app browser loaded the local landing page; authenticated review, WebGL, save/reload, and production model acceptance were **NOT TESTED** by browser in this audit.
- Deliberately excluded an unused/untracked `DeviceMeshCatalog.jsx` that fails lint and references unavailable assets/dependencies, a local MySQL repair script, and an unrelated deletion of the Gemini review prompt. Ignored private dataset, original images, manifests and model weights were not staged. The local 56-class development checkpoint must be provisioned separately on another host; it remains experimentally fenced and known to fail cross-style usability. Keep the recovery stash unchanged.

### October 2 local account/session reset

- Owner-authorized maintenance completed against local development `ved_electrical`. Live account/role tables checked OK and all four Google mappings resolved before reset; corruption was not reproduced. Complete database dump plus private configuration snapshot saved in ignored `storage/reports/account-reset-20261002T144611213579Z/`; dump completion marker and SHA256 recorded privately. Cleared cached profiles for 53 retained accounts, removed 63 unreferenced synthetic accounts and 17 unused synthetic roles. Four Google identities, existing ADMIN/DESIGNER assignments and 49 referenced synthetic identities retained. Every unaffected table's row counts/content hashes matched before/after; no uploaded source, annotations, model weights or project geometry changed.
- Rotated private session key and restarted backend with OAuth-code-bearing access logs disabled. Fresh live checks: health 200, signed-out `/api/auth/me` 401, pre-reset signed session 401, fresh login 302 to Google with state session issued; four Google profile-refresh/resolution checks passed in rollback-only transactions. Browser computer-use verified landing and sign-in screens. Fresh interactive Google callback for each Gmail **NOT TESTED**; users must begin a new sign-in rather than replay an old callback.
- **PASS:** four reset utility tests (dry run, identity/authority/reference preservation, idempotence, rollback); restricted isolated MySQL authentication/reset suite **13 passed, 2 subtests passed**, two existing dependency warnings; compilation and diff checks. Full regressions **NOT RERUN** for this maintenance scope. Added `scripts/reset_local_accounts.py`, its script tests and `backend/tests/test_account_reset.py`; existing backend README documents maintenance/recovery. Changes remain uncommitted on `codex/vlm-localization-experiment`; unrelated deletion, untracked UI/repair files and `stash@{0}` preserved. U/data/training/release acceptance unchanged.

### October 2 project-only reset (owner clarification)

- Explicit authorization to delete projects and linked application data while preserving datasets/trained data. Fresh private dump/configuration recovery snapshot: ignored `storage/reports/project-reset-20261002T150148024805Z/`. Deleted **575 rows** in FK-safe transactional order: **56 projects, 55 floors, 73 plan records**, plus linked jobs/outcomes/artifacts/detections/walls/reviews/settings. All **25 project-owned tables now empty**; no schema drop, ID resequencing, disabled FK checks, or filesystem deletion. Account/role/session, shared legend/history/material, dataset authority and release table contents unchanged by hash verification. Stored originals retained privately for recovery: **23 original files hash-identical**. All **47,748 training/model files metadata-identical** (size/mtime inventory; not a claim of full content rehash). Downloads and annotation workspace untouched.
- **PASS:** eight maintenance tests, including project-only dry run, dependency deletion, preserved accounts/catalogs, unknown-dependency refusal, rollback and idempotence; isolated MySQL authentication/project/floor/upload/reset regression **103 passed, 25 subtests passed**, two existing dependency warnings; compilation/diff checks. Command: `run_isolated_backend_tests.py tests/test_account_reset.py tests/test_authorization.py tests/test_projects.py tests/test_project_floors.py tests/test_floor_plan_upload_api.py -q`. Post-reset dry run returns zero removable project records, and all four Google accounts' actual project-service lists are empty. Session configuration unchanged. Backend restarted (health 200); frontend was stopped, restarted and browser computer-use verified its protected app route redirects to normal sign-in. Initial frontend connection checks failed during startup, then recovered. Authenticated browser project list **NOT TESTED** because the connected browser is signed out; full regressions **NOT RERUN** for maintenance scope.
- Extended existing reset utility/tests/README only; ledger updated here. Changes uncommitted on `codex/vlm-localization-experiment`; unrelated work and recovery stash preserved. U/data/training/release statuses unchanged. Refresh the existing authenticated project page to retrieve the empty list; backend and frontend are already running.

### October 2 trained-legend names and review mapping

- New proposals from the pinned `development_multiclass56_yolo` checkpoint retain a typed `training_legend` snapshot: exact user-attested training name, drawing-specific entry, model index and dataset SHA256. Verified all **56 actual manifest entries** against pinned dataset/checkpoint hashes and validated their snapshot shapes. Display names feed the existing shared draft 2D/3D presentation; model predictions and reviewer corrections remain separate. Existing candidate JSON, original images, annotations and weights were not rewritten or retrained.
- Added authenticated, **ADMIN + development-only** `POST /api/admin/symbol-legends/import-trained` and the existing Admin panel's **Import 56 trained legend entries** action. It registers unique `name [drawing:legend]` entries with separate app class numbers and normal actor-attributed history. Imports are transactional/repeat-safe; existing meanings and inactive decisions are retained. **Use trained legend mapping** matches only the exact active drawing-specific name, never a checkpoint index or similar wording, and leaves the detection unresolved until explicit review. No role/production approval bypass or fabricated approver was used.
- **PASS:** focused backend **62 tests / 12 subtests**; focused frontend **34 tests**; final restricted/empty isolated MySQL full backend **1036 passed, 4 skipped, 509 subtests passed**, five existing dependency deprecation warnings; full frontend **50 files / 426 tests passed**; scoped ESLint, Vite build (existing large-chunk warning), compilation and diff checks. Final full run includes the added database save/reload snapshot test. Initial runs failed old OpenAPI totals and a new test fixture/query; corrected the exact route contracts (now **44 operations / 33 tables**) without changing application gates. An initial full run also failed H3's storage hash assertion because it watched live development logs; H3 now honors the isolated runner's configured temporary storage and retains the hash comparison. The final full rerun passed.
- **NOT TESTED / pending:** authenticated browser import and real-plan review/2D/3D interaction. Computer-use verified that the protected local app redirects to sign-in; no signed-in Admin is available in the connected browser. Live catalog remains **9 entries**; the 56-entry import has **not** been executed against it. Next action: sign in as the actual Admin → Manage symbol legends → Import 56 trained legend entries; refresh/open a newly processed review and explicitly select its trained mapping. No account impersonation, restored projects, model activation, production promotion or accuracy improvement is claimed.
- Implementation remains local/uncommitted on `codex/vlm-localization-experiment`; earlier maintenance/planning edits, unrelated files and `stash@{0}` preserved. Existing README updated; no new Markdown report. Dataset/training/real-data/release gates unchanged.

### October 9 source-supported wall junctions

- Draft-only 3D browser check **PASS**: WebGL rendered the same saved wall/device draft, with roof initially hidden and unmeasured observed wiring explicitly withheld from 3D. Screenshot `wall-supported-junctions-20261009-v5/browser-shared-wall-draft-3d.jpg`. This is an illustrative draft using existing preview dimensions, **not** measured canonical geometry or engineering approval. Returned the connected browser to 2D after verification. Canvas alternative text initially suggested a WebGL failure; the actual screenshot and empty WebGL error log demonstrated rendering, so no browser failure is claimed.

- User priority: fix detection gaps without turning wiring into walls or filling real openings. This is a narrow shared structural-detector change, not a page-specific template, retraining release or a claim that all missing walls are recovered. Uses the floorplan-CV/surgical-patch guidance: original-pixel evidence, stable source coordinates and regression proof; computer use for live browser checks.
- Added `wall_detection/junctions.py` after existing final candidate filtering. Extends existing centerlines only to source-supported L/T intersections, including independently supported two-ended corners. Original solid-wall radius or both hollow-wall outline mates must survive the extension. Original anchors are frozen: repaired walls cannot bootstrap other repairs. Extensions are bounded by 32 pixels, 3% of source short side and four times the configured line gap. Single thin strokes, missing mates, blank openings, short thick hatch blocks, distant and collinear doorway gaps are not joined. Wall count/widths remain unchanged and existing glyph/grid guards run again. Geometry evidence version is `cv-source-supported-junctions-v7`; no symbol weights or release approval changed.
- Frozen native-source replay (`wall-supported-junctions-20261009-v5`) and full detector execution (`wall-junction-pipeline-20261009-v1`): **sheet-11 54 -> 54 walls**, three original-ink-supported joins extended **6 / 8 / 23 source pixels**; wall indices 24, 42, 45 (zero-based). Assistant source inspection verified their structural joins. **sheet-24 4 -> 4; sheet-35 31 -> 31; school-selected 11 -> 11**, unchanged endpoints. A seven-pixel hatch-block extension appeared during development, was visually rejected and excluded by the linear-anchor guard; earlier diagnostic versions are preserved. All four source-file hashes are unchanged. Initial helper-only replay did not test the whole pipeline; the separate full-pipeline report does. Two-ended corner expansion subsequently reproduces the same real-page endpoint replay, with additional synthetic regression proof.
- These are development cases, not independent-project accuracy. Whole-page precision/recall is **UNSCORED**. Entire missing walls on sheets 24/35 remain **FAIL**; this patch repairs eligible joins, not their failed candidate extraction. Do not substitute similarity, memorization or candidate counts for detection quality. Next smallest wall experiment: original-outline candidate recovery that does not disturb global thickness statistics, with lighting-wire and hatch negatives retained.
- **PASS:** final focused wall/junction/automatic-wire checks **75 tests, 106 subtests**; final isolated MySQL full backend **1,283 passed, 4 skipped, 1,438 subtests**, five existing dependency-deprecation warnings. Full frontend **65 files / 568 tests**, focused review/save/reload **6 files / 51 tests**, scoped ESLint and Vite build passed (existing >500KB chunk warning). Full frontend lint remains **FAIL: six unrelated errors in untracked `DeviceMeshCatalog.jsx`**, untouched. Two earlier direct backend selections included database fixtures without isolated execution and were interrupted; they are not passing evidence. Final full backend uses the restricted empty verification database and temporary storage. Initial new rotation/hollow-corner fixtures failed, exposed rasterization/junction problems and were repaired; only final runs are cited as passing. Python compilation/diff checks pass. Current source OpenAPI **36 paths / 44 operations**, metadata **34 tables**; no endpoints/tables added by this wall ticket.
- **PASS browser:** reused the existing upload 9376 in project 10218/floor 6323; no duplicate upload. Computer-use reanalysis created job **24218**, showing **54 walls / 5 room proposals**. Selected wall-0046 endpoint is **448,3032** versus prior raw **448,3009**. Exercised a one-pixel edit and undo, set its draft disposition unresolved, saved unfinished review **revision 1**, reloaded and verified the endpoint and notes. Original job **24213/revision 4** remains stored. Read-only hash/source/revision verification is in `wall-supported-junctions-20261009-v5/persisted-verification.json`; browser screenshot is `browser-persisted-wall.jpg`. Neither review completeness nor canonical approval was granted. No canonical layouts exist; approved scale/elevation remain missing, so measured routing/canonical 2D/3D is **NOT TESTED**, not fabricated.
- Adjacent already-in-progress automatic visible wiring/simple-UI work remains separately uncommitted: the browser job carries **27 partial unresolved visible-ink traces**, retained on save/reload; measurements/names and optional detailed forms start hidden. This is observed drawing ink, **not** an approved A*-generated circuit or measured 3D route; false symbol anchors can still produce false wiring proposals. No coverage/precision claim. The wall-versus-wire training diagnostic is also separate/unselected: 67 unique hash-bound local examples memorized, but exploratory transfers **20/38 and 20/46** expose severe wall/wire collapse. No diagnostic model is activated. Do not commit unrelated overlapping worker/UI/planning changes with this wall checkpoint.
- Scoped checkpoint on `codex/vlm-localization-experiment`, starting from `f8dbc12`: only junction helper, detector call, evidence-version line, regression tests and this section are included. Original images/annotations/model artifacts and recovery stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` preserved. Unrelated dirty edits retained; no automatic push, production promotion, new Markdown or broader detector-readiness claim.

### October 9 automatic scan continuity and direct wiring review

- User correction: improve the shared scan, not add another wall-gap option; remove drawing-region/pixel-entry controls and automate visible wiring while retaining manual drawing. The floorplan-CV/investigation skills identified the actual regression before editing; canvas/UI guidance keeps correction and save explicit. UX search results were unrelated and were not used as design authority.
- Reproduced the pictured school-plan regression on the exact normalized source SHA-256 `cfb10f5329c82300fbae43933374078514c4d0c7be82d20ba0d1ec52ef8cac72`. The uncommitted 3%-padding change widened the automatic drawing mask and changed bounded outline votes: 14 proposals had a missing right half of the top wall and fragmented bottom wall. Historical `12b61eec` and HEAD `4cec132` at 1% padding had continuous perimeter proposals. Restored narrow automatic scope with a six-pixel minimum to retain both mates on compact hollow-wall plans; geometry evidence version `cv-stable-drawing-scope-v8`. No per-page coordinates, model training, new detector selector or client gap-repair step. Source-backed junction v7 remains inside the detector.
- Same-input whole-page replay `wall-stable-scope-20261009-v1`: school **14 -> 13**, continuous top/bottom perimeter restored; sheet-11 **54 -> 54 with identical endpoints**; sheet-24 **6 -> 4**, sheet-35 **33 -> 31**, returning to the prior narrow-scope baseline rather than claiming those difficult pages improved. All four source files remained hash-identical. These counts are NOT precision/recall. Missing walls on sheets 24/35, diagonal/hatch artifacts and some interior sections remain **FAIL**. Initial minimum-four-pixel restoration clipped a synthetic hollow mate and failed one test; minimum-six retains that mate, excludes detached nearby annotation strokes and reproduces the school perimeter result. Earlier diagnostic failures/versions remain preserved.
- Removed visible **Connect walls**, **Select drawing region** and the entire **Process a drawing region** panel from the review page. Underlying region API/component/tests remain for history/compatibility, but this editor no longer exposes them. Default names/length labels are hidden; detailed limitations and wiring forms are collapsed. **Draw wiring** uses two fresh source-coordinate clicks (Shift orthogonal lock, Escape cancellation), shared draft history/undo, append-only save and reload, without touching walls. Existing wall snapping is preserved. Manual traces retain unknown elevation and partial completeness; no circuits/heights are invented.
- Added the already-in-progress `automatic_wiring.py` extraction to ordinary demo/shared-model processing: continuous original ink between distinct detected-device bounds within the automatic plan region; existing observations retained, symbol glyph interiors/known wall overlaps rejected, bounded 128 segments with explicit truncation. Output remains partial/unresolved with no inferred connections or calibrated confidence. False symbol anchors can still create false traces; curves, unsupported gaps and one-ended runs may be missed. Valid pages over the extractor's 12MP working bound skip only automatic wiring with a warning, not fail wall/symbol processing. No production weights, routes or training truth changed.
- **PASS focused:** 90 backend tests / 111 subtests; four frontend files / 25 tests, followed by three edited-file suites / 18 tests after preserving click snapping/tool-session isolation. **PASS full working-tree verification:** isolated MySQL backend **1,285 passed / 4 skipped / 1,438 subtests**, five existing dependency warnings; frontend **65 files / 569 tests**. Vite build and scoped ESLint pass; existing >500KB chunks remain. **FAIL full ESLint:** six unrelated errors in untracked `DeviceMeshCatalog.jsx`, left untouched. Full suites include unrelated working-tree edits and do not establish independent detection accuracy. No APIs/tables added: **36 OpenAPI paths / 44 operations / 34 metadata tables**.
- **PASS computer-use browser:** existing project 10218/floor 6323/upload **9377**, normal project reanalysis (no duplicate import, no drawing selection) created **job 24222**, **13 walls / 2 rooms / 29 unresolved symbol proposals / 12 partial unresolved wiring proposals**. Drew test trace **402,89 -> 453,89**, saved unfinished review **revision 1**, reloaded and verified the exact source coordinates; removed the test duplicate and saved **revision 2**. The tombstone, revision 1 and prior raw jobs **24220/24221** remain. Neither human review completeness nor canonical approval was granted. Read-only proof: `wall-stable-scope-20261009-v1/browser-verification.json`. Job 24221's old 90x5 selected region remains historical evidence, not a full-plan detection. Screenshot records the simplified editor and restored automatic perimeter.
- **NOT TESTED this checkpoint:** fresh measured canonical 2D/3D and engineered routing, because no saved canonical layout/approved scale/elevation exists. Prior draft-WebGL verification remains separate; unmeasured observed wiring is not fabricated in 3D. No new model download, larger training run, dataset reset, production promotion, accuracy claim or GitHub push. Scoped checkpoint starts at `4cec132`; unrelated legend/class-tail/auth/estimate/training edits and stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` retained. Next smallest wall experiment remains source-supported missing-section recovery with lighting, wiring and hatch negatives, not additional UI controls.

### October 9 Admin Excel pricing, reviewed BOM and metric route tubes

- Priority: Admin Excel import, user BOM, then 3D ceiling/wall wiring. Reused the existing MySQL materials/price revisions, estimate snapshots, role checks, canonical route projection and React controls; no new dependency, table, training or engineering default. Routing/3D skills kept geometry authoritative; spreadsheet inspection exposed ambiguous purchase-unit quotes rather than treating them as per-meter prices. Current branch `codex/vlm-localization-experiment`, starting at `5789c6b`; this work remains uncommitted, with unrelated edits and recovery stash preserved.
- **PASS import implementation:** ADMIN-only XLSX preview/apply, bounded ZIP/XML parsing, no formula evaluation/macros/external-link execution, stable brand/SKU codes, explicit currency, row selection, file hash, optimistic price revisions, transactional rollback and actor-attributed append-only history. Existing material name/unit conflicts are not overwritten. Repeating identical prices creates no revision; after an uncertain apply the UI requires a fresh preview. Supplied workbook SHA-256 `e6ac185848d507a8fa2a273887f2b941470d1d042e1f62e6ca5c16e09d480640` is unchanged. Initial numeric extraction found 571 rows/25 issues; source/browser inspection found nine explicitly unresolved price bases. Final preview is **562 eligible / 34 skipped**, with roll/length/piece units retained and historical-source warning. TBA, formula prices, duplicate codes and ambiguous price bases remain unimportable until clarified in a copy of the workbook. No source workbook was rewritten. **NOT TESTED live apply:** browser preview only; no application prices were changed.
- **PASS BOM implementation:** reviewed canonical component quantities, missing-floor/route state, explicit additional purchase quantities, explicit meters per wire/conduit purchase unit and historical CSV download bound to a selected estimate. No inferred roll size, wastage, purchase rounding, conductor count, live repricing or raw-AI quantity acceptance. Old meter-only requests remain compatible. Isolated tests prove extra quantities, package conversion, ownership checks and fixed CSV contents after later price changes. Existing circuit-planning snapshots remain excluded from monetary estimates (`CIRCUIT_ESTIMATION_NOT_CONFIGURED`) until circuit conductor/material configuration is implemented; the new BOM does not disguise that limitation.
- **PASS 3D implementation:** saved metric route segments now render as slim tubes, orange ceiling runs and copper wall rise/drop, retaining underground inspection and ordinary depth occlusion. A display-only 8 mm radius is not conductor sizing or a takeoff input. Exact endpoint/elevation and zero-length tests pass; geometry is shared with existing 2D projection and backend length calculation. The existing routing engine requires actual wall attachment and elevations for a switch drop. This change does not infer which switch controls a light, invent wall heights, move unknown wiring into the ceiling, or create furniture. Unknown installation remains unresolved.
- **PASS focused/full verification:** focused import/BOM/price/estimate backend selection 24 tests before the additional ambiguous-basis check; final restricted isolated-MySQL full working-tree suite **1,292 passed / 4 skipped / 1,438 subtests**, five existing dependency warnings. Initial full run had three exact OpenAPI-set failures caused by the four new endpoints; updated only their contract expectations and operation counts, then reran successfully. Final frontend **68 files / 577 tests**, production build and focused ESLint pass. Two earlier renderer contract tests expected line-only children and failed after the tube change; revised assertions preserve endpoint/style/depth and immutability checks and pass. **FAIL full lint:** six pre-existing errors in unrelated untracked `DeviceMeshCatalog.jsx`, untouched. Temporary browser-fixture lint errors were removed from frontend by archiving the fixture in ignored storage. Existing >500 KB chunk warnings remain. Working-tree OpenAPI **40 paths / 48 operations**, metadata **34 tables**; four new endpoints, no new schema tables.
- **PASS computer-use browser:** user switched the connected localhost session to ADMIN; uploaded the exact supplied workbook to preview, verified final **562/34**, deselected all and left confirmation unchecked. Admin dashboard retains the pending preview, not an applied import. Existing project 10218 BOM correctly shows **0 reviewed snapshots**, floor **6323** missing a reviewed layout, no measured route and disabled saved-BOM download. Separate labeled synthetic WebGL fixture exercises the actual `RouteLines3D` in perspective/front views, visibly demonstrating ceiling-to-wall-to-switch routing; this is NOT the user's uploaded plan or approved measurements. Screenshots/archived fixture: `storage/training/pricing-bom-runtime-20261009-v2/`. Initial fixture used unavailable Drei; removed that fixture-only import, no library installed. Reference website fetch failed; supplied screenshots guided the visual treatment.
- **BLOCKED only for live measured-plan demonstration:** no saved canonical layout, approved scale/elevation, reviewed device heights/attachments and confirmed light-switch circuit associations on the current plan. Live populated BOM generation/download and measured canonical 2D/3D routing remain **NOT TESTED**; isolated API and synthetic renderer evidence are distinct. Need genuine review/measurement inputs, not fabricated approval. Local API was refreshed only after confirming zero active jobs; it remains loopback-only. Originals, datasets, annotations and trained artifacts were not modified; stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` and unrelated work retained. No push or production activation. Next smallest ticket: supply reviewed canonical measurements/connections, then verify a real saved ceiling-to-switch route and configure circuit-specific conductor/material takeoff.

### October 9 whole-plan draft wiring and continuous walls

- **PASS implementation:** every valid, non-rejected observed/manual wiring polyline in the shared review draft is projected into 3D from its original source coordinates, independent of page identity, dimensions or layout approval. No demo box or synthetic plan is required. Explicit heights (including negative heights) are preserved; unknown heights use the illustrative preview ceiling, never saved as measured geometry. Display-only wall drops require an observed endpoint near one unambiguous wall-mounted device; proximity does not prove a light-switch circuit relationship. Invalid traces are reported, not silently hidden. Canonical measured routes remain separate and unchanged.
- **PASS editing:** click a 3D wire, drag its blue source-point handles, or edit its XY/optional height in the inspector. The same points appear/edit in 2D and persist through the existing immutable draft-save endpoint. Removal is a tombstone; undo/redo and role enforcement remain. Both Add wall and Draw Walls enter continuous A → B → C drawing; Escape finishes. Moved the stale-room warning below the canvas because browser verification exposed a layout shift between B and C. No source-backed wall detection or model weights changed in this ticket.
- **PASS live Designer browser:** reused project 10218/floor 6323/upload 9377, current job **24223**, with **13 walls / 2 rooms / 29 symbol proposals / 12 partial wiring proposals**. Clicked segment-0001 in real-plan 3D, dragged its endpoint **179,250 → 212,274**, saved unfinished revision **1**, reloaded and verified exact coordinates. Restored original coordinates/unresolved state in revision **2**, then reloaded again. Both revisions have null wire height and false review-complete/layout-approval flags, confirmed by read-only database inspection. Continuous wall clicks produced **438,408 → 544,408 → 544,456**; Escape ended the chain and both test walls were undone before saving. Source original SHA-256 `e9f091252f664a6c97e1d3202d5552f6e80507f6304e3dc5c2d1e653dd3f2a48` rehashed identically. Evidence: ignored `storage/training/draft-wiring-runtime-20261009/`; connected tab retained on the actual plan's 3D view.
- **Reconciled failure:** initial browser save against historical job **24222** correctly returned **409 STALE_INTERPRETATION_RUN** because 24223 superseded it. Historical results/revisions were not changed; the UI now explains this condition. Initial canvas drags missed tiny handles and the browser screenshot scale; enlarged the visual handles and used observed coordinate mapping, then verified a real drag. An initial regression test used the wrong accessible 3D button name and failed; corrected the assertion. Incorrect test-runner/source-inspection paths were corrected without modifying configuration or data. Temporary save diagnostics removed.
- **PASS verification:** final frontend **70 files / 588 tests**, build, scoped implementation/test ESLint and diff whitespace checks. Restricted isolated-MySQL review/wiring tests **33 passed / 8 subtests**, two existing dependency warnings. OpenAPI **40 paths / 48 operations**, metadata **34 tables**; no new API/schema/dependency. **FAIL full lint:** six existing errors in unrelated `DeviceMeshCatalog.jsx`, untouched. Existing >500 KB build chunk and Konva layer/Three.Clock warnings remain. Full backend suite **NOT RERUN** for this frontend-only ticket.
- **Limits/state:** current floor has **0 canonical layouts**. Unknown real scale/heights, missed traces and unconfirmed light-switch associations still prevent measured circuit/BOM claims, but do not block draft 3D display/edit/save. No independent human review, inferred engineering approval, training run or production promotion. Branch `codex/vlm-localization-experiment`, HEAD `5789c6b`; scoped work remains uncommitted with unrelated edits and stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` preserved. Next smallest experiment: verify an observed ceiling-to-switch endpoint on another supplied page, separating draft visibility from confirmed circuit topology.

### October 9 device-connected wiring and cross-plan hollow-wall recovery

- **PASS bounded implementation:** draft wiring now attaches at every eligible source-polyline vertex, including ceiling fixtures and intermediate switches, using corrected glyph bounds and the same `devicePlacement` as the rendered device. Ceiling connectors reach fixture tops; switch/outlet/panel drops reach actual wall-mounted meshes. Ambiguous proximity and absent nearby mounting walls remain unresolved. Explicit elevations, including underground traces, are untouched. Connectors are illustrative display geometry, not inferred circuit associations, measured lengths or BOM inputs. Source points and original glyph evidence remain immutable. Owners: `devicePresentation`, `draftWiringScene`, `devicePlacement` and their tests.
- **PASS saved-route alignment:** exact-version saved single-target A* records now supply explicit device installation metadata to the shared renderer, as circuit records already did. Short display-only connectors join exact stored route endpoints to actual mounted mesh centers without moving canonical anchors or changing backend route lengths. Stale, unrelated-floor, unknown-algorithm and unbound nearby lines are rejected. Owners: `circuitMounting`, `routeDeviceConnectors`, `Viewer3DCanvas`, `routeProjection` and focused tests. Reused FUNCTIONAL_SPEC M1-M7 contracts and existing obstacle-aware A*; no A* path or guessed light-switch topology was inserted into detection.
- **PASS power-plan failure reproduction and bounded wall fix:** user-reported `powerlayout.png` is upload **9382**, filename **power-layout.png**, normalized original **1765 x 1084**. Its repeated tied, hollow triple-line walls were excluded as thin wiring bundles. Qualification now requires distributed transverse ties in original pixels, sufficiently long narrow bands and tied evidence in both native axis directions. Bounded direction-balanced proposals, overlap consolidation and reapplying detached enclosing-frame rejection after supplements recover the perimeter/interior without introducing page IDs, template coordinates or model classes. Plain parallel wiring, two end caps and clustered crossings fail the qualification. Evidence version `cv-balanced-outline-ties-v9`; owner `wall_detection/detector.py`, `demo_cv.py` and native-resolution tests.
- **Cross-plan evidence, NOT an accuracy percentage:** power **9 -> 13 walls / 3 rooms** (`storage/training/power-wall-repro-20261009-v8/`); school lighting **13 -> 11 walls / 2 rooms** after overlap consolidation (`lighting-wall-crosscheck-20261009-v2/`); mezzanine **53 -> 53 walls / 5 rooms** (`mezzanine-wall-crosscheck-20261009-v3/`). Counts do not establish correctness or 85% recall. An intermediate broadly enabled voting experiment regressed mezzanine to two walls; it was not retained. Two-direction tied-band gating restored the existing path before runtime activation. Synthetic cross-tied perimeter fixtures at 1x/2x pass >=95% sampled reference coverage; this is synthetic regression evidence only. The final detached-frame supplement guard does not activate for the other two examples. Door gaps are not indiscriminately bridged.
- **PASS additional observed wiring, partial completeness only:** a bounded second Hough pass accepts repeated regular dashed ink after original-pixel support validation; single erased spans and irregular missing intervals remain rejected. Known parallel walls and symbol interiors remain excluded; distinct device bounds anchor fragments, not electrical connectivity. On the power plan, **3 -> 7** observed traces. Evidence version `device-anchored-visible-and-dashed-ink-v2`; owners `automatic_wiring.py` and its tests. **NOT ACHIEVED:** complete curved, one-ended and unsupported-gapped branches. Existing observations are retained; all proposals remain partial/ambiguous, with no inferred connections or elevations. No claim that every drawn cable or circuit is detected.
- **PASS verification:** final frontend **71 files / 594 tests**, production build, scoped implementation/test ESLint and diff whitespace check. Restricted isolated-MySQL wall/native-resolution/gap/grid/junction, interpretation, A*, ceiling boundary, routing API, automatic wiring and review API selection **193 passed / 173 subtests**, two existing dependency warnings. Full backend suite **NOT RERUN** this checkpoint. Full ESLint is not claimed clean: six previously recorded errors in unrelated untracked `DeviceMeshCatalog.jsx` remain untouched. Existing >500 KB build chunks remain. OpenAPI **40 paths / 48 operations**, metadata **34 tables**; no new API, table or dependency. An initial read-only proof query incorrectly treated the stored wiring list as an object; corrected query verified counts without writing data.
- **PASS live Designer computer-use save/reload:** normal project reanalysis created power-plan jobs **24227**, then **24228** after the dashed-ink update. Final UI and read-only persisted review show **13 walls / 3 rooms / 16 symbols / 7 partial unresolved traces**. Saved unfinished **revision 1**, reloaded and verified notes, original coordinates and false `review_complete` / `approved_for_layout`. First trace remains **(288,592) -> (291,759)** with null elevation. No human approval or circuit association was granted. Final screenshot `storage/training/device-wiring-wall-runtime-20261009/power-plan-saved-overlay.png`; connected tab retained on this actual result. Historical jobs/reviews remain stored. Runtime refreshed only after an idle-job preflight; API remains loopback-only with OAuth-bearing access logs disabled.
- **BLOCKED visual 3D/reference inspection:** the connected browser could not create WebGL on either the retained or a fresh actual-plan tab. Geometry and renderer tests pass, but this checkpoint does not claim a live visual 3D pass; prior successful WebGL evidence is separate. Reference-site browser access was declined by the saved security preference and was not bypassed; supplied screenshots guided ceiling runs and wall drops. **NOT TESTED:** independent real-plan 85% wall accuracy, complete wiring recall, real measured populated routing/BOM, and new connector appearance in working WebGL.
- **Integrity / state:** originals rehashed unchanged: power `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`, lighting `e9f091252f664a6c97e1d3202d5552f6e80507f6304e3dc5c2d1e653dd3f2a48`, mezzanine `6ad0b03b0fede2142fabd88114af086184e8fa97d1acaa70fbdb506e87b34128`. Originals, datasets, approved annotations, trained weights, unrelated edits and stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` preserved. Branch **codex/vlm-localization-experiment**, HEAD **5789c6b**; no staging, commit, push, production promotion or model training this checkpoint. Existing documentation updated only. Next bounded work, not started: source-supported curved/junction/one-ended trace recovery with negatives and a working-WebGL visual check, without fabricating engineering topology or claiming evaluation coverage from proposal counts.

### October 9 immediately editable wiring drafts, without item confirmations

- **PASS normal draft workflow:** removed per-item Accept/Confirm decision selectors and proposal badges from the plan editor. Devices, walls, rooms and wiring are immediately editable, removable and restorable; Save draft requires no confirmation. Legacy detection review now offers Remove/Restore device instead of a normal confirmation step. Measured-layout controls are collapsed and separate from ordinary draft saving. Explicit whole-layout review remains optional and must still satisfy existing scale, elevation, mapping and completeness gates; automatic processing does not fabricate Designer approval or training truth. Existing visual design and libraries retained; routing/CV/canvas skills preserved shared geometry and separate evidence, while UX guidance informed disclosure of secondary controls.
- **PASS general automatic fallback:** new pure `app/routing/draft_wiring.py` reuses existing A*, with orthogonal source-pixel grid routes, drawing-region bounds, wall-band obstacles and no direct-diagonal fallback on NO_ROUTE. Visible traces are prioritized, followed by nearby panel/device anchors. Nearest-anchor selection is an editable visual heuristic, **not inferred circuit association or guaranteed globally optimal engineering routing**. Local wall-device exits are bounded by the drawn glyph size, not whole-wall shortcuts. Limits are 64 devices, 128 wall records, 256 visible traces and a three-second between-path budget; unavailable paths are reported rather than silently omitted. Saved edits/removal tombstones are not regenerated, and moved devices disconnected from saved paths produce a coverage warning. This is shared behavior, not a power-plan template.
- **PASS additive persistence/provenance:** generated paths use separate `generated_wiring` review JSON, A* origin, source/target anchor IDs, partial completeness and null elevation. They are never inserted into immutable image observations, canonical observed routes, measured quantities or BOM. API service validates references, source bounds, uniqueness, ownership and existing save concurrency. Both 2D and draft 3D consume the same saved paths. No new API, table, dependency or migration: **40 paths / 48 operations / 34 tables**.
- **PASS actual Designer browser save/reload:** current power-layout upload **9382**, user-created latest job **24229**, saved unfinished **revision 1** through normal Save draft with no confirmation clicks. Computer-use reload and read-only DB check verify **7 observed traces + 13 automatic paths**, false `review_complete`/`approved_for_layout`, and unchanged seven immutable machine observations. All recognized physical device anchors on this sample touch an active trace/path; three homerun annotations are not physical devices. Runtime route generation measured **0.496 seconds** before save. Earlier 12-path result left one offset outlet unwired; bounded glyph attachment recovered it. Coverage is proximity to polyline, not proof of correct circuit topology, electrical safety or detection accuracy. Historical job 24228 save correctly refused STALE_INTERPRETATION_RUN; no old review was overwritten. Screenshot: `storage/training/device-wiring-wall-runtime-20261009/no-confirmation-editor.png`; actual editor tab retained.
- **PASS verification:** final full frontend **71 files / 596 tests**, Vite build, scoped ESLint and diff whitespace checks. Restricted isolated MySQL selection `test_draft_wiring.py`, `test_observed_wiring_review_api.py`, `test_demo_interpretation_api.py`, `test_routing.py`, `test_routing_api.py`: **76 passed**, two existing dependency warnings. Tests cover obstacles/NO_ROUTE, local mounts, saved removals/moves, evidence priority, fallback starvation, API validation, persistence without confirmation and prevention of generated-path laundering into canonical quantities. Initial UI checks failed changed copy/ambiguous X selection and generated tombstone precedence; corrected and final gates passed. Final copy change briefly failed an outdated warning-string test; preserved all-56 scope wording, updated the exact unverified-accuracy assertion, and reran all 596 tests successfully. Full backend and full ESLint **NOT RERUN**; existing >500 KB chunks and unrelated DeviceMeshCatalog lint findings remain.
- **BLOCKED visual 3D:** current saved result opens the draft preview but the connected browser cannot create WebGL. Shared geometry/renderer tests pass, not a live visual rendering claim. **NOT ACHIEVED/NOT TESTED:** universal complete image-wiring recall, independent real-plan 85% wall accuracy, correct light-switch circuit association, measured populated BOM, automatic routing of unidentified/manual-only newly added devices, or guaranteed routes for impossible/budget-limited layouts. Users can draw/edit wiring directly; unavailable paths are not forced through walls. Explicit saved wire edits take precedence over automatic rerouting.
- **Integrity/state:** original power SHA256 reverified `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`; originals, datasets, approved labels, trained weights and unrelated changes untouched. Stash remains `bb78854e87833124a1725b51f0be6099a8ac0cfa`, branch **codex/vlm-localization-experiment**, HEAD **5789c6b**. No staging, commit, push, training or production promotion. Refreshed only verified idle localhost API processes; loopback binding/no OAuth access logs preserved. Existing ledger updated only. Further accuracy/unknown-device/WebGL work is not silently marked complete or started as a new phase.

### October 10 incremental wiring for added and reclassified devices

- **PASS reproduced/fixed:** regression tests first reproduced manual devices omitted from routing and an empty saved `generated_wiring` collection preventing future automatic paths. The shared backend draft router now uses current saved symbol geometry plus manual symbols, excludes rejected/omitted devices, and appends paths for newly known devices while keeping every prior generated path/edit/removal unchanged. New IDs follow the largest saved identity, not the count. Devices already touching a trace/path do not get redundant routes. Existing generated source/target anchors are protected from automatic regeneration even after moves/removals; disconnected saved devices remain reported rather than overriding wire edits.
- **PASS save contract:** normal Save draft resolves explicitly chosen active catalog names even while item disposition is unresolved, without declaring human approval. Existing catalog mapping can establish routing eligibility without guessing an unfamiliar name; the name-based fallback also covers existing camera, contact, keypad, breaker, meter, service entrance, push button and box entries. This changes draft eligibility only, not detector classes, training weights, circuit assignment, quantities or engineering rules. Unknown device types receive an explicit limitation, and homerun annotations remain excluded as nonphysical anchors. New generated paths are stored in the same append-only revision and returned immediately; frontend merges service additions while saved edits/tombstones win for existing IDs. Owners: `routing/draft_wiring.py`, `demo_interpretation_service.py`, `observedWiringDraft.js` and their tests. Routing/canvas/3D skills kept shared geometry, separate evidence and original coordinates; surgical-patch skill kept the change at these existing boundaries.
- **PASS live Designer computer-use test/cleanup:** actual power job **24229**, revision 2 saved a temporary mapped **1 x 40 watts fluorescent lamp**. At its initial center **(883,542)** it was **0.5 pixels** from an existing draft path, so no duplicate route was required. Moving it to **(1100,650)** and saving revision 3 generated **manual-route-0014**, taking active wiring from **20 to 21 paths**, with no confirmation or approval action. Removed only this temporary lamp/path using recoverable editor removal and saved **revision 4**. Reload shows original **16 symbol records / 20 active wiring paths**, with the test entries retained only as removed history. Read-only DB equality verifies all original walls, rooms, symbols, observed wiring and the original **13 generated paths** unchanged; flags remain false and no coverage notes remain on this sample. Screenshot `storage/training/device-wiring-wall-runtime-20261009/incremental-wiring-cleaned-20261010.png`; cleaned-up editor tab retained. An initial browser catalog selection failed because grouped option numbering differed from the AX description; read its actual visible option and selected the correct original entry, without catalog modification.
- **PASS verification:** final isolated MySQL routing/review selection **92 passed**, two existing dependency warnings; full frontend **71 files / 598 passed**; Vite build, scoped ESLint and diff whitespace checks passed. Tests cover new mapped/unresolved manual persistence, empty-list reclassification, old route/removal preservation, unknown/omitted/rejected devices, other existing catalog families and immediate frontend service additions. Initial three reproducer tests failed as expected; the old unknown-device silence assertion then failed and was replaced with an explicit warning assertion. All final focused gates passed. No new endpoint, table, dependency or migration: **40 paths / 48 operations / 34 tables**. Full backend and full ESLint **NOT RERUN** this slice; existing large build chunks remain.
- **BLOCKED/NOT TESTED:** actual 3D preview was retried on the saved 21-path result and still cannot create WebGL in the connected browser. No live visual 3D success is claimed. Complete wiring recall across arbitrary plans, independent 85% wall accuracy, correct inferred light-switch topology and final measured BOM remain unproven. Newly mapped devices receive automatic paths on draft save; unclassified devices and impossible/bounded-out paths need editing, not fabricated connections. Existing budget and evidence/engineering separation remain unchanged.
- **Integrity/state:** original power SHA256 remains `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`; originals, datasets, approved annotations, weights and unrelated changes preserved. Stash `bb78854e87833124a1725b51f0be6099a8ac0cfa`, branch **codex/vlm-localization-experiment**, HEAD **5789c6b**, no staging/commit/push/training/promotion. Only verified idle loopback API processes refreshed, with access logs disabled; no accounts/roles/schema reset. Existing ledger updated only. Further CV recovery/WebGL validation is not silently marked complete or started as a new phase.

### October 10 continuous draft wiring instead of disconnected branches

- **PASS reproduced/fixed:** a four-device fixture produced two separate local paths despite complete device coverage. The initial regression failed on two paths rather than three. `routing/draft_wiring.py` now finds literal geometric contacts (including crossings, tolerance only `1e-5` source pixels), then appends orthogonal A* joins between exact known-device anchors on separate unmeasured runs. Nearby parallel lines are not mistaken for contact. This is geometric draft continuity, **not electrical circuit membership or a junction/safety determination**. Existing image traces and saved paths remain unchanged; no new options or item confirmations were introduced. Routing/canvas guidance kept the same source coordinates in both views and generated joins separate from observations; surgical-patch guidance kept the implementation at the existing draft-router boundary.
- **PASS safeguards:** joins stay within one drawing region, use existing wall-band obstacles and bounded local device exits, and have no diagonal/through-wall fallback. Different explicit elevations are not automatically bridged. Removed generated joins protect their associated runs against alternate-endpoint recreation. Runs without exact known-device anchors, blocked paths, separate drawings and budget-limited paths remain explicitly reported rather than silently called connected. Pairwise geometry is bounded to **256 active paths / 512 segments**; existing **64-device / 128-wall / three-second between-path** bounds remain. This is a nearest-reachable-component heuristic using A* grid paths, not a globally optimal engineering network. No detection/class/model change, new endpoint, table, dependency or migration: **40 paths / 48 operations / 34 tables**.
- **PASS actual plan save/reload:** read-only probe of power upload **9382**, job **24229**, revision 4 found **six disconnected runs**. Four joins (`manual-route-0015` through `0018`) reduced them to **one geometrically connected draft network**, taking **20 to 24 active paths**; probe elapsed **0.145 seconds**. Normal Designer Save draft through computer use saved **revision 5**, and browser reload retained all four joins. Selected join `0018`, edited its third point X to `630`, and Undo restored exact X `625.0517457389237` without saving that temporary change. No approval/confirmation was applied. Screenshot: `storage/training/device-wiring-wall-runtime-20261009/joined-wiring-saved-20261010.png`; connected 2D editor tab retained.
- **PASS verification/integrity:** final restricted isolated MySQL selection **107 passed / 8 subtests**, two existing dependency-deprecation warnings; full frontend **71 files / 599 tests**, Vite build, scoped ESLint and diff whitespace checks passed. Added pure regressions for disconnected pairs, save idempotence, blocking walls, removed joins, different heights/drawings, exact contacts and missing anchors; API regression proves normal append-only save/reload without approval; frontend projection regression proves both bridge endpoints contact the existing branches at the same shared ceiling height. Read-only comparison of revisions 4/5 verifies original walls, rooms, symbols, observed wiring and all existing generated paths/tombstones unchanged. Candidate/review hashes verify; `review_complete` and `approved_for_layout` remain false. Original power SHA256 remains `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`. Full backend/full ESLint **NOT RERUN**; existing large build chunks remain.
- **BLOCKED/NOT TESTED:** live 3D preview still reports inability to create WebGL; shared projection tests pass, not live visual 3D rendering. Correct electrical circuit assignments, complete image-wiring recall on arbitrary plans, measured BOM and independent wall accuracy remain unproven. Joins are editable unmeasured drafts and are not canonical takeoff inputs. This change does not retrain detection or claim all impossible/unknown-device layouts are connected.
- **State:** local/uncommitted on **codex/vlm-localization-experiment**, HEAD **5789c6b**; stash `bb78854e87833124a1725b51f0be6099a8ac0cfa` unchanged. Originals, datasets, approved labels, trained weights and unrelated edits preserved. Only verified idle loopback API processes refreshed, access logs disabled; no account/role/database reset, staging, commit, push, training or promotion. Existing documentation updated only. Further CV recovery/circuit validation is not started as a new phase.

### October 10 approved dashed wiring, connected branches and BOM identities

- **Scope/acceptance:** the owner authorized reuse of the approved dashed-line meaning on similar drawings. Drawing-specific active wiring legends take precedence; unavailable explicit mappings remain unknown. This is catalog semantics for editable drafts, not inferred conductor sizes/counts, burial depths, prices, circuit safety or professional approval. CV, electrical-routing, shared 3D and surgical-patch guidance kept pixel evidence separate from generated geometry and quantities. No new controls or per-item confirmations were introduced.
- **PASS CV regression:** `automatic_wiring.py` now recovers bounded regular dashed spans and orthogonal bends, trims unsupported tails, masks device/homerun glyphs, rejects short two-stroke/text fragments and continuous architectural-border negatives, while preserving repeated dashes parallel to walls. One-ended supported traces remain partial with no inferred circuit membership. `candidate.py` adds backward-compatible `line_style`; prior immutable JSON is hash-verified before parsing. Actual power replay yields **9 observed dashed segments**, including the right-side bends and central branch. Some left-side ink and glyph/curve gaps still need generated links; complete image-wiring recall is **NOT PROVEN**. No page-specific coordinates, model weights or training changes were introduced.
- **PASS routing regression:** `routing/draft_wiring.py` attaches devices at literal geometric contacts, including short masked-glyph gaps, inherits unambiguous approved trace types and connects existing components toward one known panel using bounded orthogonal A*. It reuses the network rather than generating independent panel-to-device stars. Multiple panels require explicit assignment; conflicting known installation methods/heights are not automatically merged. Only unresolved automatic routes whose endpoints already have an alternative observed-connected path are suppressed, longest-first with connectivity recomputed. Suppressed paths remain recoverable tombstones; manually edited/accepted/added paths, user removals and explicit heights are preserved. This is geometric connectivity and a nearest-reachable-component heuristic using shortest grid paths, **not global network optimality or electrically verified circuits**.
- **PASS catalog/BOM/3D contract:** new `services/wiring_legend_service.py` resolves names from active database catalog entries, sanitizes client names and enriches copies only. Additive fields in `schemas/demo_interpretation.py`, `demo_interpretation_service.py` and its API response give fresh scans and saved drafts the same meanings. `observedWiringDraft.js` merges service metadata/suppressions without overwriting edited geometry. `draftWiringScene.js`, `DraftRoomPreview.jsx`, `ObservedWiringPanel.jsx` and `DemoInterpretationPage.jsx` preserve shared coordinates; under-floor wiring with unknown depth uses the illustrative floor reference, not the ceiling, and explicit user elevations win. Manual edits clear automatic-suppression reasons. `services/bom_service.py`, the estimates API and `BOMPanel.jsx` list approved draft wiring names separately from reviewed quantities and captured prices. Draft lengths remain **null**, not fabricated takeoff inputs. Active approved references 1789/1790 and 1806/1807 remain unchanged; no legend deactivation or schema changes.
- **PASS live Designer computer-use:** ordinary reanalysis of existing power upload **9382** (`power-layout.png`), project **10218**, floor **6323**, created **job 24232**. The normal editor saved unfinished **revision 1**, without confirmations or canonical approval. Reload and read-only stored-geometry comparison preserve **9 observed + 17 active generated = 26 active paths**, one literal connected network reaching the panelboard; automatic route `manual-route-0010` remains recoverably removed. Read-only replay routing elapsed **0.766 seconds** on this drawing. BOM visibly shows **Raceway conduit concealed under floor · Plan 9382**. After final idle API refresh, the browser again loads these 26 paths and remains on the saved 2D draft. Evidence: `storage/training/device-wiring-wall-runtime-20261009/dashed-network-saved-20261010.png` and `dashed-wiring-bom-20261010.png`.
- **PASS final verification:** guarded restricted/disposable MySQL selection **220 passed / 8 subtests**, two existing dependency warnings; full frontend **71 files / 602 passed**, existing mocked-Konva DOM warnings. Vite production build, scoped ESLint on nine relevant frontend files and `git diff --check` pass; existing >500KB chunks and LF/CRLF notices remain. Tests cover bent/one-ended/near-wall dashed evidence and negatives, literal attachments, redundancy recovery, panel connectivity, incompatible installations, approved pattern/drawing-specific precedence, foreign-owner rejection, append-only save/reload, historical pricing and shared 3D elevations. An initial final verification command referenced an incorrect test filename and ran no tests; corrected selection above passed. Full backend and full ESLint **NOT RERUN** this slice. No dependency/migration/API/table additions: **40 OpenAPI paths / 48 operations / 34 tables**.
- **BLOCKED / NOT TESTED:** live 3D still cannot create a WebGL canvas in the connected browser; projection regressions pass but visual 3D rendering is **BLOCKED**. Final priced wire/conduit BOM is **BLOCKED** by zero active wire/cable/conduit materials in the database and missing approved metric/conductor inputs. Independent wall precision/recall (including 85%), arbitrary-plan completeness, correct electrical circuit topology and global optimization are **NOT TESTED/PROVEN**. This checkpoint does not declare them complete or infer engineering inputs.
- **Integrity/state:** original power SHA256 remains `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`; old job 24229/revision 5 and their verified immutable hashes remain intact. Originals, datasets, approved annotations, weights and unrelated dirty-tree work retained. Branch **codex/vlm-localization-experiment**, HEAD **5789c6b**, stash `bb78854e87833124a1725b51f0be6099a8ac0cfa`; no staging/commit/push/training/promotion/account reset. Only verified idle API launcher/worker processes were refreshed on loopback; no access logs, frontend interruption or database mutation beyond the authorized normal analysis/draft revision. Existing progress ledger updated only. Further wall/CV coverage or engineering validation is not silently started as another phase.

### October 10 horizontal devices, magnetic wiring and keyboard navigation

- **PASS implementation:** shared device placement now uses horizontal outlet plates at every wall angle, grounded socket details or data-port cavities according to the existing family/label, recognizable switch paddles, and distinct single/twin fluorescent bodies. No new detection classes or brands. New `viewer-3d/DeviceBody.jsx` replaces the inline generic bodies in `DeviceMesh.jsx`; `devicePlacement.js` retains saved anchors, mount rules and existing illustrative dimensions except the outlet aspect ratio and single-tube width. `DeviceGlyph.jsx` supplies matching horizontal 2D outlet details and single/twin light glyphs. Source device coordinates and engineering quantities are not inferred from meshes.
- **PASS cleaner wiring:** `draftWiringScene.js` prevents coincident vertical drops to the same mounted device while retaining each branch's horizontal attachment. The regression first reproduced two drops and passes with one. `DraftWiring3D.jsx` uses narrower conduit cylinders, closed ends, generous invisible picking targets and smaller point handles. `wiringAppearance.js` shares ceiling/underfloor styling with the 2D canvas; `CanonicalScene.jsx` and `Viewer3DCanvas.jsx` use restrained architectural materials/lighting, without furniture or geometry changes. These visual connectors remain illustrative and are not authoritative BOM lengths.
- **PASS keyboard movement:** `cameraMovement.js` and `ViewerCameraControls.jsx` implement W/A/S/D and all four arrow aliases, translating camera and orbit target together on the ground plane. Top view has a stable direction. Movement requires the focused viewer, ignores inspector inputs/modifiers, pauses during dragging, invalidates the demand-rendered view and removes listeners on cleanup. Existing orbit/pan/zoom/reset remain. `Viewer3DCanvas.jsx` is focusable; `viewer3d.css` keeps the compact navigation hint visible inside the canvas rather than clipped below it.
- **PASS magnetic drawing / placement:** `wireDrawing.js`, `DemoInterpretationCanvas.jsx` and `DemoInterpretationPage.jsx` snap clicks to exact active device centers, existing vertices or projected segment points with scale-adjusted tolerance and green device/wire feedback. Rejected items and nonphysical annotations are excluded. The right inspector supplies Ceiling / Underground-underfloor while drawing and for an existing wire. Installation intent and solid/dashed style persist through the existing review API; approved catalog mapping is resolved server-side. Explicit elevations are retained, and unset depth/height remains null rather than invented. No per-wire approval gate, API/schema change or new dependency.
- **PASS live computer-use:** reopened localhost after the prior tabs/servers had closed, restored the existing Designer session using the normal retry, and tested actual power plan 9382 / job 24232. Drawing slightly off the two outlets snapped to exact fractional anchors `(283.08581298205627,571.8851742582465)` and `(284.15019234924546,778.616051476317)`. Revision 2 saved underground intent; reload preserved it and both anchors. Revision 3 saved Ceiling; reload preserved that change with height unset. Green Wire snap was separately reproduced against an existing segment and cancelled without adding another path. The current connected browser now successfully renders WebGL (the earlier slice's limitation no longer reproduces). W plus ArrowRight visibly translated the live 3D scene; screenshots record before/after. Unit tests cover all aliases, top view, focus/input exclusion, disabled mode and cleanup.
- **PASS recoverable cleanup / integrity:** removed only temporary `manual-wiring-0001`. Its presence had automatically suppressed original branch `manual-route-0005` and, after removal, generated `manual-route-0019`; restored the original branch and removed the incidental replacement through the normal editor, saving revision 5. All original walls, rooms, symbols, observed traces and generated route coordinates match revision 1. Original branch 0005 has only its disposition changed from unresolved to corrected by Restore item. The two temporary paths remain rejected in append-only history, with **26 original active paths** restored and approval flags false. Read-only verification script and browser confirm this; original SHA256 reverified `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`. No original, dataset, annotation, weight or account reset.
- **PASS verification:** full frontend **74 files / 618 tests**; final production build **2122 modules**; scoped ESLint across 23 relevant JS/JSX files; diff whitespace check. Guarded restricted empty verification database: `test_observed_wiring_review_api.py` and `test_wiring_legend_service.py`, **20 passed**, two existing dependency warnings. Two initial full-frontend failures were overly broad structural assertions: socket-detail circles counted as semantic markers and the new wiring halo group lacked an explicit listening prop. Narrowed the marker query and retained explicit group interaction state; final full suite passes. Final CSS overlay was built and checked live. Original-hash utility initially used the wrong relative storage root; corrected to the app's configured upload directory and passed.
- **FAIL full lint outside this change:** six existing errors in unused, separately authored `DeviceMeshCatalog.jsx` (unused import, mixed exports, conditional hooks). This file was neither adopted nor modified. Full backend **NOT RERUN**; focused backend checks above passed. Existing large frontend chunks remain warnings. Physical sizing/elevations, electrical circuit correctness, independent wall accuracy, arbitrary-plan completeness and final measured/priced BOM are **NOT VERIFIED** by this display/control slice.
- **Evidence / handoff:** `storage/training/device-wiring-wall-runtime-20261009/` contains `wiring-magnet-horizontal-outlets-20261010.png`, `wire-to-wire-magnet-20261010.png`, `keyboard-before-20261010.png`, `keyboard-after-20261010.png`, `controls-3d-saved-20261010.png`, read-only `check-controls-integrity.py`, and loopback runtime logs. Clean saved 2D editor retained as a browser deliverable. Frontend launcher PID 27680; backend launcher PID 28688 / uvicorn PID 23432, loopback only, no OAuth access logs.
- **Scope / skills / Git:** the asset, visualizer and design skills guided recognizable procedural bodies, shared geometry and uncluttered styling; canvas/routing skills kept magnetic source anchors, installation metadata and illustrative attachments separate from engineering measurements. Surgical-patch / lean-build constrained changes to these existing boundaries. Branch **codex/vlm-localization-experiment**, HEAD **5789c6b**, recovery stash retained. No staging, commit, push, model training, promotion, dependency, table or endpoint additions; prior contract baseline remains **40 paths / 48 operations / 34 tables** (counts not remeasured in this frontend slice). Unrelated dirty-tree work preserved. No next roadmap phase started.

### October 10 POV-relative smooth spectator flight

- **PASS reproduced / fixed:** a focused regression first failed because forward movement discarded camera pitch (`delta.y == 0`). `viewer-3d/cameraMovement.js` now derives forward and strafe from the camera quaternion, including pitch and a stable straight-down view. Held W/A/S/D or arrow keys move continuously; Q/E descend/ascend. Simultaneous directions are normalized, opposites cancel, and Shift targets **3x** translation speed rather than relying on OS key-repeat timing.
- **PASS smooth navigation:** `ViewerCameraControls.jsx` uses R3F frames with exact exponential acceleration/braking and a bounded frame delta. Camera and look target translate together. Demand rendering continues only during movement/braking, then stops. Focus loss, window blur, hidden document, dragging/disabled controls, camera presets, mode changes, Escape and unmount clear movement; inspector inputs and modified browser shortcuts are not captured. Right-drag turns the spectator in place with bounded pitch and no orbit-position change. Pointer capture/listeners are cleaned up. This is a non-colliding spectator, not a walk-through with wall collision or eye-height assumptions.
- **PASS mode / UX:** `Viewer3DCanvas.jsx` starts in **Free fly**, keeps a single Free fly / Orbit switch, and shows the right-drag, movement, Q/E and Shift guide in the viewport. `viewer3d.css` styles the compact mode button and focus state. Existing orbit/pan/zoom and perspective/top/front/reset presets remain available; no route, device, wall, measurement or persistence changes. The visualizer skill guided quaternion-based navigation and on-demand frames; surgical-patch kept this inside the navigation owner. No additional libraries or guessed engineering rules from skill examples were introduced.
- **PASS verification:** focused four-file selection **19 passed**; full frontend **74 files / 625 tests passed**; production build **2122 modules**; scoped ESLint across all six changed JS/JSX files; diff whitespace checks. Regression coverage includes pitched/rotated POV, top view, arrows, normalized diagonals, opposite keys, 30/60/144 FPS path equivalence, smooth launch/braking, sprint ratio, long-idle delta bounds, key release, focus/blur/input/disabled/mode guards, idle rendering stop, right-drag in-place look and listener disposal. Three test files changed: `cameraMovement.test.js`, `ViewerCameraControls.test.jsx`, `Viewer3DCanvas.test.jsx`. Initial old ground-plane test failed as expected; no failed final gate remains in this slice. Existing large-build-chunk warning retained; full lint and backend tests **NOT RERUN** (no backend changes; unrelated catalog lint findings from the preceding slice remain).
- **PASS live computer-use:** current Designer draft power plan 9382 / job 24232 renders in the connected browser. Holding W for **800 ms** moves along the pitched view, enlarging the plan as the camera approaches. After Reset, **Shift+W for the same 800 ms** visibly travels much farther. Free fly / Orbit toggling and reset worked, and the browser remains in Free fly with its guide visible. Right-drag look is covered by component/geometry tests; a live right-button drag was **NOT TESTED** with the available browser drag API. Smoothness is mathematically verified across frame rates; no device-specific sustained-FPS benchmark is claimed. No Save draft was invoked, and the prior saved revision 5 / 26 paths remain untouched.
- **Evidence / integrity / stop:** `storage/training/device-wiring-wall-runtime-20261009/free-flight-normal-20261010.png`, `free-flight-sprint-20261010.png` and `free-flight-controls-20261010.png` record browser checks; existing current tab retained as deliverable. Originals, datasets, weights, database, roles and unrelated dirty-tree work untouched. No backend/schema/API/table/dependency addition, migration, training, commit or push. Branch **codex/vlm-localization-experiment**, HEAD **5789c6b** retained. Existing ledger updated only; this request is complete, with no next roadmap phase started.

### October 10 lighting localization and pre-annotation wiring evidence

- **Scope:** reproduce `4-lightinglayout.jpg` (upload 9376, project 10218/floor 6323) and improve shared evidence handling, not add sheet-specific coordinates, another detector selector, confirmation steps or training from an unreviewed upload. CV/investigation guidance separated source pixels from review overlays; routing/surgical-patch guidance kept observed traces distinct from generated unmeasured A* paths. This is a partial detection improvement, not a completed accuracy/release gate.
- **PASS source isolation:** `interpretation_processing_service._decode_rgb` explicitly makes normalized pre-annotation RGB read-only. Wiring receives that same registered source array after device localization, never a detection-overlay or review screenshot. Worker regressions compare exact pixel hashes/array identity before and after extraction. Symbol bounds only mask glyph interiors in a private working raster and anchor source strokes; they cannot become source ink. Original uploads and earlier candidate/review bytes remain unchanged.
- **PASS bounded shared localization:** `multiclass_symbol_detector` first uses the existing 256px crops, then selects native 320px context/160px stride for fixture-majority content (at least eight fixture observations and 70% of physical observations), only when both passes fit the existing 500-window cap. The score cutoff remains .50; one pinned approved numeric class map and checkpoint are retained. Power/mixed content and rollback profiles retain baseline localization. `experimental_symbol_detector` uses actual per-pass crop sizes for seam filtering and preserves crop-size/box/score/origin evidence during fusion. This is broader context, not a lower threshold or an added zoom pass. No model weights, training manifests, catalog identities or dataset approvals changed.
- **PASS source-region/anchor safeguards:** `demo_cv` can delimit a drawing from repeated compact structural-column rows before falling back to existing ink bounds; synthetic tests include detached dimensions/title ink and scaled inputs. `multiclass_symbol_detector.with_proposals` excludes observations outside those plan regions. `automatic_wiring` requires centre-axis device-port contact for both solid and dashed observations, reducing fixture-tip/grid attachments. Unverified wall hypotheses through two ceiling-fixture cores are warned/preserved and omitted before routing, with opening-host walls protected. No saved review walls are changed. Actual lighting replay still has 11 wall segments and no rooms; complete walls are **NOT PROVEN**.
- **PASS ceiling intent:** `wiring_legend_service` resolves automatic lighting defaults from the filename/OCR intent to the approved ceiling-raceway catalog. Explicit active drawing/manual wiring assignments, underfloor choices, unavailable explicit mappings and entered elevations retain precedence. The service annotates copies before routing and after generating paths; immutable evidence remains untouched. Defaults do not invent ceiling height, burial depth, conductor specification or price. Tests cover lighting dashed/solid defaults, generated defaults and explicit/manual overrides.
- **PASS routing/coverage:** `routing/draft_wiring.draft_path` searches the complete zero/one-bend Manhattan candidate graph with the existing A* and wall-band checks before building the dense grid. Successful candidates attain the Manhattan distance lower bound; blocked candidates fall back to the existing obstacle-safe grid, never a diagonal/wall shortcut. Three-second lighting replay now finishes in approximately **1.623s**, matching the previous ten-second coverage rather than timing out with 18 runs. All **51 currently detected physical devices** touch **one geometric network**; seven additional unanchored source fragments remain preserved. Status now distinguishes those fragments from truly disconnected device-anchored networks. This does not establish electrical circuit membership, global network optimality or takeoff lengths.
- **PASS live Designer computer-use:** normal project reanalysis created **job 24238/run 167** from the same original, then the editor saved unfinished **revision 1** and reloaded. New output: **58 candidate items** (43 troffers, four downlights, two ordinary switches, two outlet labels and seven circuit annotations), versus the previous 70-item run with 42 troffers and false panel/smoke/hold-up labels. Lower total is not a recall score; missed fixtures/switches and the remaining outlet labels still require source review. Saved active wiring: **37 observed + 63 generated = 100**, all `concealed_in_ceiling`, no explicit elevations. Four redundant automatic generated paths remain recoverably suppressed. Approval/review-complete flags remain false. Old job 24237 and power job 24232/revisions 1–5 retain valid immutable hashes; power draft remains 26 underfloor paths, one network and 13 connected physical devices.
- **PASS final focused verification:** restricted isolated MySQL **308 passed / 1 skipped / 138 subtests**, two existing dependency warnings; four frontend projection/review suites **50 passed**; production build **2122 modules** and diff whitespace checks passed. Earlier over-wide stroke-band experiments increased scan false positives and were fully reverted. A status-test insertion accidentally displaced three existing assertions and an orphan status obscured a moved-device warning; restored assertion ownership, limited orphan counts to observed fragments and reran the entire final selection successfully. Full backend/frontend suites and full ESLint **NOT RERUN** this slice. Existing large-build chunks and unrelated catalog lint findings remain. OpenAPI remeasured **40 paths / 48 operations / 34 metadata tables**; no API/schema/dependency additions.
- **FAIL / BLOCKED / NOT TESTED:** complete missing-symbol recovery and arbitrary-plan wall/wiring accuracy remain **FAIL/NOT PROVEN**, including the requested independent 85% wall threshold. Seven unanchored traces remain unresolved and there is no verified panelboard on this lighting scan; no fictitious panel or engineered circuit was added. Live 3D visual verification is **BLOCKED** because the connected browser cannot create its WebGL canvas; source-point/ceiling/drop projection tests pass but are not a visual pass. Final metric/priced BOM and professionally validated circuits are **NOT TESTED** by this draft slice.
- **Integrity/handoff:** original lighting SHA256 reverified `915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9`; pinned weight SHA256 remains `2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa`. Content-gate power inference still returns 12 outlets/one panel/three homeruns. Ignored local diagnostics and browser proof: `storage/training/lighting-inspection-20261010/`, including `check_saved.py` and `lighting-saved-raw-source-ceiling.jpg`. Final backend launcher PID 14108, loopback-only/no access logs; existing frontend retained. Branch **codex/vlm-localization-experiment**, HEAD **5789c6b**, recovery stash and unrelated dirty work preserved. No training, production promotion, account reset, staging, commit or push. Existing ledger updated only; no next roadmap phase started.

### October 10 user-designated wiring reference from the earlier workspace

- **PASS reference recovery:** computer-use opened the user's existing `http://127.0.0.1:3000/` tab, selected Group 4 / `4-lightinglayout.jpg`, and downloaded a normal Export review copy without editing annotations. Export schema `ved-editable-review-v2`, sheet `sheet-11`, original-pixel frame **1340 x 3264**, original SHA256 **915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9** exactly match production upload 9376. This establishes source registration without estimating coordinates from screenshots.
- **PASS path preservation:** the private comparison retains **8 user-reviewed Conduit wiring polylines / 38 edges**, including **4 polylines stored under the symbols layer**. Geometry and label semantics, not layer alone, identify the reference paths. Original point order, connection IDs, human method/review state and provenance are preserved. Filtered source-matched reference is `storage/training/lighting-inspection-20261010/user-wiring-reference.json`; comparison script/result are alongside it and Git-ignored. The broader export remains in Downloads, unmodified.
- **FAIL reference completeness of current draft:** length-weighted geometric sampling at 2px spacing against the existing local shared-pipeline replay finds reference coverage **18.96% observed / 54.34% observed-plus-generated within 8px**, and **24.24% / 65.50% within 16px**. These are partial-reference path coverage, not calibrated detection accuracy, circuit correctness, false-positive precision or an engineering approval. Exact branches/turns need improvement; the preceding single-geometric-network result is explicitly insufficient to establish correct wiring. The sparse source-trace recovery and global nearest-component joins are relevant mechanisms to investigate, not a proven solution.
- **NOT TESTED implementation change:** no production detector/router/UI change, reprocessing, database write, new training release, schema/API/dependency addition, commit or push in this reference-recovery slice. No production tests rerun because product code was unchanged. User designation makes these paths the comparison reference; the export still records `training_approved=false` / `training_eligible=false`, so no automatic training or production class creation occurred. Existing saved drafts, original images, model weights and unrelated dirty work remain intact. CV/routing and investigation guidance kept reference annotations separate from raw source ink and A* suggestions.

### October 10 apply reference wiring to the lighting plan only

- **Scope / PASS:** user explicitly narrowed the request: keep previous detection behavior and use this specific annotation only on `4-lightinglayout.jpg`. No production code or model changes. Used the existing Designer editor's Add visible wiring trace, exact source-pixel points, Ceiling placement and Save review revision controls; no raw API/SQL writes, hidden React-state injection, new import option or confirmation gate. CV/routing guidance kept this a human project correction rather than a detector benchmark improvement or automatic training.
- **PASS saved result:** latest lighting analysis **job 24240 / run 169 / review revision 1** contains exactly **8 active manually added source-reference paths**, with all **38 ordered edges** matching the exported annotation coordinates exactly. Four reference paths originally filed under symbols were included. Approved ceiling installation intent is stored; explicit heights remain unset. Old 37 observed and 67 generated paths are retained as recoverable rejected entries in this review, not deleted from raw candidates or previous revisions. Review evidence notes record source SHA256 and ordered annotation-ID mapping. No circuit membership, conductor specification, real measurement or engineering approval was inferred.
- **PASS preservation / verification:** before/after read-only `verify_plan_reference.py` checks exact path-coordinate equality, ceiling intent, inactive prior paths, unchanged candidate/review hashes, unchanged wall endpoints and device centers, unchanged original source bytes and unchanged power job 24232/revisions 1–5. Normal browser save reported revision 1 saved; reload still shows **Wiring · 8 paths** and Ceiling placement. Original lighting SHA256 remains **915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9**. Prior job 24238/revision 1 is unchanged.
- **Recovery / warning:** initial attempt to save against historical job 24238 was correctly rejected as superseded; no historical write occurred. Read-only discovery found job 24240 with the identical source, and the exact correction was reapplied there. A long browser loop timed out after partial UI edits; fresh state was inspected and only remaining active paths were processed in bounded batches. Full-page screenshot capture was unavailable; native browser screenshot captured the saved 2D result at `storage/training/lighting-inspection-20261010/lighting-reference-applied-24240.png`. Diagnostics/baseline/reference artifacts remain local and Git-ignored.
- **NOT TESTED / stop:** no detection-accuracy improvement, retraining, future-upload annotation override, new canonical/BOM approval, or new live 3D rendering claim. Full unit/build gates were not rerun because product code and dependencies were untouched; live save/reload plus exact persisted-data checks are the applicable acceptance gates here and pass. Existing reference workspace, originals, datasets, weights, roles and unrelated dirty work were not modified. Only this project's latest draft and existing progress ledger changed; no commit/push/schema/API/dependency changes and no next roadmap phase started.

### October 12 source-supported initial device connections and labelled elevation guidance

- **Evidence / cause:** the latest screenshots reproduce the power source (plan **9382/page 2984**, `power-layout.png`, **1765 x 1084**, SHA256 `2c4fb66b01bcd37aecfd91e9264e907e5dae1a0e6bca7f896662574b7ab4ce94`), not the ambient lighting tab. Exact screenshot job identity is unavailable. Old job **24248/review 1** has **9 raw observed segments and zero candidate device contacts**; legacy generated/proximity-derived display connections are not persisted source evidence. The extraction symbol mask removes the final stroke through the glyph, and the final observed-route return discarded associations. A tight box-boundary endpoint helper rejected those mask-cut ports, endpoint-only logic missed inline devices, and observed canonical wiring did not use the mounted rear-terminal projection. Earlier nearest-device rendering is not a defensible source-backed fix; an exact historical working renderer artifact cannot be reconstructed from the mixed uncommitted workspace.
- **PASS implementation:** bounded `device_contact_evidence.py` proposes typed direction/bounds/source-ink contacts, including glyph occlusion and inline devices. Nearby devices alone do not qualify; crossings do not become segment junctions, overlapping ports remain ambiguous. Candidate/fusion contracts retain anchors, edge indexes and evidence, including reversed tile coordinates. `endpoint_connections.py` adapts only untouched proposals, retains every raw source vertex and inserts distinct proposed short leads; new evidence-required routes do not fall back to proximity. Save validates run/contact/source references. Actual human edits, mounting/pricing data and detach opt-outs remain authoritative; untouched machine attachments regenerate on reanalysis without acquiring human approval. Wiring provenance version **raw-source-device-port-evidence-v8** is persisted through the existing processing path.
- **PASS shared geometry:** canonical extension **v4** stores stable device references/anchors while preserving v2/v3 snapshots. `geometry/observed_connections.py` produces one stored measured branch per device/service elevation; `canonicalScene.js` and shared `connectionGeometry.js` project that same branch to the rear terminal without adding a second route or altering BOM geometry. Display lane anchors pin terminals. Draft projection supports interior attachments, movement and detachment, and marks missing-height connections explicitly. Concealed underfloor traces/selected wires use existing inspection rendering to expose concealed geometry; this is display-only and not the root-cause repair.
- **PASS user-authorized guidance:** draft preview uses labelled **switch 1.2 m AFF / outlet 0.45 m AFF** planning presets, relative to each floor. The outlet preset is accessibility-oriented, not a universal building mounting mandate. Stored dimensions override presets; no standard floor-to-floor or service height is invented. Preset-only rises/drops are excluded from measured takeoff and do not block a 2D draft save.
- **PASS live initial analysis/save/reload:** ordinary Designer reanalysis created **24268**, then the final source-preserving run **24269/review 1**. Final candidate and persisted draft have **12 source-supported attachments across 9 outlets / 9 active observed paths**. A temporary outlet move updated its attached vertex without creating another path; Undo restored the exact original coordinate, and the temporary change was not saved. Computer use verified 2D and a rendered 3D planning preview. Read-only verification proves raw wire vertices, symbols, walls, original bytes and old 24248 review unchanged. Source and saved correction history were not overwritten; original user lighting tab remained untouched. Screenshots: `storage/training/lighting-inspection-20261010/power-connections-before-24248.png`, `power-connections-after-24269.png`, and `power-connections-after-24269-3d.png`.
- **PASS tests:** final full frontend **86 files / 699 tests**; focused backend **158 tests / 8 subtests**, plus independent canonical-contract **6 tests**; earlier wider selection **185 / 29 subtests**. Vite build **2130 modules**, scoped ESLint and whitespace checks pass. Coverage includes masked boundary contacts, inline devices, adjacent/unconnected devices, crossing non-junctions, ambiguity, raw immutability, tile reversal/fusion, API save/reload, reanalysis inheritance, stored nonzero floor/service/mount elevations, a single measured rise/drop, rear-terminal projection, movement, detach and pinned display anchors. Full backend/full ESLint **NOT RERUN**. Existing two backend deprecation warnings and large build chunks remain.
- **Unresolved / NOT TESTED / BLOCKED:** outlets **symbol-0010, symbol-0011 and symbol-0014** still lack extracted short/curved branch evidence; they are visibly unresolved rather than forced onto nearby wiring. Complete wire recall and wall accuracy are not established. Additional lighting association-stage replay proposes **72 contacts, 4 ambiguous**, preserving its 35 raw polylines; this is not fresh YOLO inference or a detection-accuracy score. Lighting **9384/job 24260/review 3** remains unchanged. The exact live power source has no approved measured canonical layout; measured live 3D/BOM verification is blocked by missing scale/elevation inputs, while synthetic API/canonical measured tests pass. Browser preview renders and shows rises, but a pixel-level close-up of every rear terminal is **NOT TESTED**. No universal detection, engineering approval, VLM training or release promotion claim.
- **Owners changed this slice:** backend candidate/automatic_wiring/observed_wiring plus new device_contact_evidence; routing/endpoint_connections; schemas/demo_interpretation; services/demo_interpretation_service; reviewed_reference; geometry/canonical_extension plus new observed_connections. Frontend canonicalExtension; canonicalScene/CanonicalScene; new connectionGeometry; DraftWiring3D; devicePlacement; DraftRoomPreview/draftRoomScene/draftWiringScene; deviceConnections; DemoInterpretationPage; wiringPresentation. Corresponding evidence, fusion, review/API, measured-connection, contract, planning-mounting and presentation tests updated/added. Only this existing ledger updated, no additional planning document.
- **Scoped checkpoint / integrity:** branch **codex/vlm-localization-experiment**, commit **dff2f94** contains only the four independent backend/frontend canonical-v4 contract and contract-test files. Integration/evidence/rendering changes remain local and uncommitted in the pre-existing mixed worktree; the checkpoint alone is not the complete release. Index empty after commit; no push. Stash **bb78854e87833124a1725b51f0be6099a8ac0cfa** unchanged. OpenAPI measured **41 paths / 49 operations / 34 metadata tables**, no endpoint/table/dependency/DDL addition by this slice. Originals, historical reviews, weights, roles and unrelated changes preserved. Final verified-idle loopback API refreshed (launcher **7196**, server **39400**, access logs disabled); no active job interrupted. CV/canvas/routing/3D and investigation/migration/surgical-patch guidance kept source evidence, human corrections, measured geometry and planning assumptions separate. No next roadmap ticket started.

### October 12 wall evidence, joined footprints and non-destructive reanalysis

- **Diagnosis:** the supplied corner matches lighting plan **9384**, `4-lightinglayout.jpg`, **1340 x 3264**. Old **24260/review 3** has 43 raw wall hypotheses; `wall-0043`, `(1237,465) to (1175,527)`, crosses a filled corner block without corresponding diagonal wall evidence. The diagonal is already in detection, not coordinate conversion. Separate square-capped Konva strokes and independent Three.js boxes cause additional internal overlap seams. Source thickness was discarded at the candidate/review boundary. Tile fusion retained exact overlapping observations, but the reproduced live CV result is not tile-derived. An interim new run displayed 82 walls because unchanged auto-accepted walls in an incomplete/unapproved draft were inherited as human corrections alongside new proposals. These defects have separate owners.
- **PASS extraction:** new `wall_detection/band_geometry.py` fits supported centerlines from contiguous cross-sections of already qualified masks, excludes corner blobs from typical thickness, trims supported thin tails and rejects compact oblique corner hypotheses only in independently observed junction context. `detector.py` uses common-band/gap evidence for consolidation rather than merging neighboring walls or white openings. `junctions.py` bounds source-backed trim/extension and deduplicates identical/reversed spans; `chromatic_walls.py` shares this refinement, retains openings and float source coordinates. `preparation.py` fuses only exactly collinear overlapping tile observations, retaining evidence references, touching identities and separate parallel walls. No filename-specific rules, page overlay, forced boundary or rescaling. Provenance: **cv-qualified-wall-junctions-v14**, **qualified-band-centres-v2**, **source-supported-overshoot-trim-dedup-v3**.
- **PASS topology/rendering:** new `frontend/src/geometry/wallTopology.js` derives exact L/T/X/angled contacts from shared geometry, partitions connected footprints by stable per-wall ownership and retains IDs. `wallGeometry.js` / `JoinedWallMesh.jsx` emit triangulated footprints and exterior side faces only: internal caps are removed, not merely hidden. Demo and canonical 2D/3D consume the same topology. Estimated source thickness survives candidate/draft/presentation contracts; approved metric thickness remains authoritative. `draftRoomScene.js` no longer creates walls from room boxes. Joined movement propagates shared endpoints; T-branch movement projects the joined end onto its existing support instead of bending the straight wall. **Alt-drag moves a wall independently**; existing undo/redo, Shift constraint and revision saves remain.
- **PASS reanalysis/live preservation:** `reviewed_reference.py` regenerates only unchanged automatic wall snapshots in incomplete/unapproved drafts. Actual edits, different thickness, mounted-wall references, manually added/corrected walls and complete/approved reviews remain protected. Historical records are not rewritten. Ordinary Designer reanalysis created **24271**, **24272/review 1**, then final **24273/review 1**, containing **38 walls / 58 symbol records / 35 observed paths**. The 43-to-38 count is not an accuracy score. Actual UI numeric movement changed a shared endpoint X from **365.11569752504926** to **366.11569752504926** and updated its neighbor; Undo restored the original exactly. Temporary changes were not saved. Final baseline saved/reloaded normally. Read-only checks prove old **24260/review 3**, source bytes and symbol candidates unchanged; power **24269/review 1** was not edited. Lighting SHA256 remains **915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9**. Actual 2D and illustrative 3D inspected at 24272; final 24273 deduplicates identical spans.
- **Evidence artifacts:** private ignored `storage/training/lighting-inspection-20261010/wall-before-after-comparison.png` shows source/red-before/green-after corner; `wall-final-source-overlay.png` shows whole drawing. Actual browser screenshots: `wall-24273-saved-2d.png`, `wall-24272-junction-2d.png`, `wall-24272-joined-3d.png`. Final saved-result tab retained; original user tab untouched. Images are diagnostics, not page-specific detection overlays.
- **PASS gates:** guarded restricted/disposable backend selection **207 tests / 168 subtests**, including structural masks/grid distractors, real thin/thick/short/angled walls, faint continuity, gaps/parallel walls, junctions, transforms/native sizes, tile fusion, review inheritance, append-only API save/reload and stale 409 checks. Full frontend **88 files / 711 tests passed**; triangle-level tests verify absent internal caps, topology tests cover contacts and detach, and page integration covers joined movement/save/reload. Vite build **2133 modules**, scoped ESLint and whitespace checks passed. One outdated footer assertion failed initially, then was corrected and the full suite rerun passed. Existing two backend deprecation warnings, large build chunks and LF/CRLF notices remain. Full backend/full ESLint and live concurrent-job overwrite injection **NOT TESTED**.
- **Additional drawings / remaining limitations:** frozen-code wall-stage repeat replay was deterministic and preserved native dimensions. Baseline/current chromatic hypothesis counts: lighting4 **53 to 49**, lighting6 **49 to 41**, datacom23 **15 to 14**; power has no chromatic result and retains 13 monochrome hypotheses. These isolated replays omit live symbol masks: they are not the live 38-wall count or labelled precision/recall. Additional lighting6/datacom23 were not threshold-specific tuning targets. Visual overlays still contain fixture/grid-like short fragments, faint missing sections, residual corner ambiguity and inadequate datacom coverage. **FAIL complete wall coverage / fully clean arbitrary-plan detection; NOT TESTED independent labelled accuracy or 85% recall.** Unsupported gaps remain unbridged. This is a reusable improvement of the reproduced regression, not a universal guarantee. Draft heights/scales are illustrative, not approved engineering measurements; live approved metric-layout/BOM verification is outside this wall slice.
- **Changed owners:** backend `band_geometry.py`, `detector.py`, `junctions.py`, `chromatic_walls.py`, `preparation.py`, `candidate.py`, `demo_cv.py`, `schemas/demo_interpretation.py`, `reviewed_reference.py`; frontend `wallTopology.js`, `wallGeometry.js`, `JoinedWallMesh.jsx`, `DemoInterpretationCanvas.jsx`, `DemoInterpretationPage.jsx`, `devicePresentation.js`, `draftRoomScene.js`, `canonicalScene.js`, `CanonicalScene.jsx`, `CanonicalLayoutCanvas.jsx`; corresponding tests and this existing ledger. CV/canvas/3D and investigation/surgical-patch skills kept evidence, shared editable geometry and rendering separate. No new planning Markdown or dependencies.
- **Scoped checkpoint/integrity:** branch **codex/vlm-localization-experiment**, core commits **91513ca** and **50f1d04**. Only task-owned core files/hunks committed; mixed UI/preprocessing/review integration and mixed tests remain local/uncommitted alongside preserved unrelated edits. Commits alone are not the complete integrated release. Index empty; no push. Stash **bb78854e87833124a1725b51f0be6099a8ac0cfa** unchanged. **41 OpenAPI paths / 49 operations / 34 tables**, no endpoint/table/DDL changes by this slice. Only verified-idle loopback API refreshed: launcher **27392**, server **25268**, access logs disabled, no active job interrupted. Original uploads, historical reviews, corrections, roles, weights and datasets preserved. No VLM training/promotion or next roadmap phase started.

### October 13 researched centerline editing, paired partition recovery and provisional switch counts

- **Baseline and scope:** owner supplied a pasted task plus five October 12 screenshots. Full source pixels confirm the lighting drawing **9384/page 2986**, `4-lightinglayout.jpg`, **1340 x 3264**; screenshots contain no exact job ID, so their precise run cannot be proven. Reproducible live baseline **24273/review 1** contains **38 walls / 58 symbol records / 35 observed paths**, source SHA256 **915bcaeed344b890c517c2148422c4c9886fa0f93caba30c325f6347089880b9**, artifact hash **22f024231b6d02b6121dab7b9477d3624284f365619511190582978cea350d28**. Local frozen model is **power80**, checkpoint **2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa**, detector cutoff **0.50**, configuration **afa2134684254cdd639436072cfd5f4252feaee30f6ca4e3b802a63c01f72747**; raw predictions and all run provenance retained. Private immutable baseline: `storage/training/lighting-inspection-20261010/wall-followup-live-baseline.json`. Originals, historical reviews, model artifacts, source annotations and unrelated changes were not overwritten.
- **Verified primary research / limitations:** [Liu et al., Raster-to-Vector, ICCV 2017](https://art-programmer.github.io/floorplan-transformation/paper.pdf) reconstructs junction primitives with integer-program topology constraints; its axis-aligned Manhattan assumptions are not suitable as a blanket rule for these angled walls. [Kalervo et al., CubiCasa5K](https://arxiv.org/pdf/1904.01920) combines segmentation and junction/opening heatmaps before geometric reconstruction. [Zeng et al., ICCV 2019](https://arxiv.org/pdf/1908.11025) separates semantic room-boundary elements from generic edges and uses spatial context, including diagonal directions. [Fan et al., FloorPlanCAD](https://arxiv.org/pdf/2105.07147) jointly studies symbol instances and wall semantics on CAD entities; that vector input differs from scanned raster electrical drawings. Applicable architectural lesson: separate wall evidence, vector reconstruction and topology; edges/thickness alone do not establish semantics. This slice implements small deterministic evidence checks, **not those trained networks or their published accuracy**. No paper dataset/model download, imported ground truth, retraining or promotion.
- **Diagnosis:** filled physical footprints were the default editing presentation, independently causing oversized 2D overlays. Existing topology extended every endpoint at a junction by its own half-width; a wide T branch could consequently protrude through a thinner support. Missing walls were already absent from source candidates, not merely invisible meshes. Chromatic refinement replaced the earlier monochrome proposals and required sustained filled colour bands, omitting some outlined partitions; blanket symbol bounding-box masks cut structural ink around switches and broad homerun boxes. Native dimensions and existing source transforms remain unchanged. Remaining standalone slabs still correspond to unresolved detected fragments; centerline styling is not presented as their detection fix.
- **PASS wall/editor implementation:** new `wall_detection/paired_boundaries.py` recovers sustained paired narrow banks with clear interiors only when anchored to independently qualified structural walls. It follows source banks through Hough fragmentation, stops at real white gaps, rejects interior window rails and free-floating fixture boxes, protects separate parallel partitions, suppresses overlapping duplicate observations, and remains bounded. `chromatic_walls.py` excludes ceiling-fixture interiors rather than erasing all annotation/device bounding boxes and joins recovered outlined walls using original ink evidence. Shared `wallTopology.js` omits T endpoint extension and bounds end/end angled joins by the other wall width, preserving individual IDs/exterior faces. Demo/canonical 2D now show thin, selectable centerlines by default; **Wall footprints** is optional, and physical source/metric thickness remains unchanged for 3D. Existing endpoint handles, movement, undo/redo, openings and exact-contact rules remain. No forced room-box boundaries or nearest-wall joins.
- **PASS provisional gang policy:** new `switch_semantics.py` and additive candidate `SwitchGangProposal` preserve original labels, trained legend IDs, pixel locations and uncertainty. Only an already identified gang switch without a determined count gets **one gang / user_requested_default / provisional=true**. Existing two-/three-gang names and credible local `S2/S3` OCR evidence retain their count; placeholder `SYM_n` is never treated as text. Unknown marks, homeruns, fan-control and three-way switches do not receive this fallback. The frontend suggests an existing active one-gang class only when unambiguous, displays provenance and allows correction. Optional persisted `gang_count_confirmed` records explicit class correction, omitted when unset for historical-shape compatibility. Merely moving the device cannot set it. Final complete review rejects uncorrected defaults with public **409 PROVISIONAL_SWITCH_COUNT_REQUIRES_CORRECTION**, while unfinished saves remain available. Candidate truth is not rewritten or automatically converted to approved training labels.
- **FAIL missed-switch recovery / honest investigation:** native frozen-checkpoint context/rotation diagnostics around the existing switch/homerun observations yielded no additional switch proposals at the unchanged cutoff; these experiments were **not promoted**. The CV OCR helper produces placeholder tokens, not recognized text. Installed Windows OCR language availability was checked (en-US); a diagnostic bridge was blocked by script execution policy. No policy bypass/weakening, software/model installation or runtime integration occurred. The screenshot's switch-versus-homerun confusion and missing switch recall remain unresolved. This is an explicit fallback for identified switches, not a claim that OCR or switch detection is fixed. Live source has two predicted one-gang symbols, not unknown-count defaults; live fallback UI on a real unknown-count source is **NOT TESTED**, while synthetic integration/API tests exercise it.
- **PASS live reanalysis/save/reload:** normal Designer UI created **24276**, saved unfinished **review 1**, then reloaded **37 walls / 58 symbol records / 35 paths**. Raw 38-to-37 is not a quality score. Read-only verification proves baseline 24273 candidate/review, original bytes, checkpoint and original symbol predictions unchanged; new gang metadata is additive. Long outlined partition recovery and continuity across former annotation masks appear in shared 2D and rendered 3D. Earlier user lighting/power reviews remain intact. Optional footprint display was exercised without saving geometry. Matched top-view comparisons use the same browser viewport, top preset, one identical scroll-zoom gesture, roof hidden, devices/wiring hidden and illustrative **40 m / 3 m** dimensions. Baseline 3D capture uses the corrected shared renderer on old saved geometry, so it demonstrates geometry recovery—not a historical before-image of the T-cap renderer. Screen positioning differs by a few pixels; exported full-source red/green overlays share an exact raster frame.
- **Artifacts / regression drawings:** private ignored `wall-followup-live-before-overlay.png` / `wall-followup-live-after-overlay.png`; browser `wall-followup-before-24273-3d.png`, `wall-followup-after-24276-3d.png`, `wall-followup-after-24276-2d.png` under the same inspection directory. Side-by-side presentations: `wall-followup-comparison-overlays.png` / `wall-followup-comparison-3d.png`; final editor `wall-followup-final-editor-24276.png` retains wiring/devices visible and footprints off. Additional frozen wall-stage baselines/current counts: lighting6 **45 to 41**, datacom23 **11 to 14**; monochrome power keeps its legacy path unchanged (no chromatic result). These were not tuned by filename/coordinates and no original labels changed. Isolated replays omit live YOLO symbol context on those additional drawings: counts are **not precision/recall or proof of non-regression**. Visual coverage remains partial, with fixture/grid-like fragments and missing partitions; datacom coverage is insufficient. **FAIL complete walls / all isolated-slab removal / missed switches; NOT TESTED independent labelled accuracy or universal generalization.**
- **PASS final gates:** broad guarded restricted/disposable backend **262 tests / 179 subtests**; focused final compatibility source check **17 passed**. Full frontend **88 files / 715 tests passed**; build **2133 modules**, scoped ESLint and whitespace check pass. New tests cover paired-bank recovery, real openings/windows, nearby partitions/rotation, annotation-mask preservation, unequal-width T caps, thin styling independent of physical thickness, provisional semantics and readable counts, historical schema shapes, explicit correction versus movement, unfinished save/final guard and reload. Earlier failures were an invalid partial test fixture, a stale configuration assertion, an unregistered public validation code and a multiple-note test locator; corrected, then gates rerun. Full backend/full lint and labelled wall/switch recall **NOT RUN**. Existing two dependency deprecations, >500KB build chunks and LF/CRLF notices remain.
- **Changed owners:** core `candidate.py`, `chromatic_walls.py`, new `paired_boundaries.py` / `switch_semantics.py`, `wallTopology.js` and new/updated core tests; mixed integration `demo_cv.py`, `interpretation_processing_service.py`, `schemas/demo_interpretation.py`, `demo_interpretation_service.py`, demo API public errors, `DemoInterpretationCanvas.jsx`, `ReviewToolRail.jsx`, `devicePresentation.js`, `DemoInterpretationPage.jsx`, `CanonicalLayoutCanvas.jsx`, `layoutLayers.js`, `LayoutEditorPage.jsx` and corresponding integration tests. Existing ledger updated only. CV/canvas/3D and investigation/surgical-patch skills separated source evidence, canonical properties and display styling.
- **Scoped checkpoint / runtime / stop:** branch **codex/vlm-localization-experiment**, commit **b6058fd**, eight task-owned core files/hunks, **327 insertions / 9 deletions**. Mixed UI/review/preprocessing integrations and tests remain local/uncommitted among preserved pre-existing edits; this commit alone is **not a complete integrated release**. Index empty, no push, stash **bb78854e87833124a1725b51f0be6099a8ac0cfa** unchanged. Existing **41 paths / 49 operations / 34 tables** retained; no endpoint/table/dependency/DDL changes. Verified-idle local API refreshed with access logs disabled; final launcher **37640**, server **7216**. No active processing job interrupted, role/account reset, original rewrite or weight mutation. No VLM training or next roadmap phase started.

### October 13 - Blueprint3D wall editor interaction and dimension adaptation

- **Reference / inspect first:** pinned `charmlinn/blueprint3d-modern` commit **f56f0b2a4a6e177181aefbf535d2945b937b5c02**, cloned into ignored `storage/training/blueprint3d-reference` for read-only inspection. Examined `src/floorplanner/floorplanner.ts`, `floorplanner_view.ts`, `src/model/corner.ts`, `wall.ts`, `floorplan.ts`, `half_edge.ts`, `src/core/configuration.ts`, `dimensioning.ts` and demo `FloorplannerControls.tsx`. Live Vercel demo inspected in 2D: continuous drawing, corner/edge merge, wall hover, dimensions and controls observed. The deployed demo's commit is not independently known. MIT copyright/permission/disclaimer retained in root `THIRD_PARTY_NOTICES` and the shipped `frontend/public/blueprint3d-wall-editor.LICENSE.txt` (verified copied to build output). No reference TypeScript, furniture/catalog application, Next.js or IndexedDB persistence imported.
- **Evidence / smallest seam:** VED already had continuous source-pixel drawing, endpoint/edge preview snapping, joined movement, review revisions and history. It lacked committing a split at a wall-edge contact, automatic axis alignment, numeric wall length, confirmed-scale delivery to the canvas and per-wall physical dimensions reaching canonical save. Reference colors/strokes come from code: normal `#dddddd` / 5 screen px; hover/preview `#008cba` / 7 px; edges `#888888` / 1 px; delete `#ff0000`; corner hover radius 7; Arial 12 px labels with white outline. Reference tolerances 20 cm merge / 25 cm alignment are converted at its 15 px/foot view scale, then made VED zoom-aware. Physical thickness remains independent of screen stroke. New calibrated manual walls use the reference's 10 cm design default; uncalibrated pages retain source-pixel thickness, not assumed real-world units.
- **Implementation / PASS:** new `wallDrawing.js` operates on the existing shared draft, with endpoint/corner alignment, continuous chain/closure, atomic wall-edge and manual X-intersection splits, original-wall identity retention, mounted-device reassignment, overlap/collapse checks and deletion tombstones. Moving shared corners uses existing canonical topology, moves explicitly mounted devices and their existing attached wire geometry, and keeps saved opening widths rather than scaling openings with wall length. Splits through saved or source-supported openings are blocked; unreviewed detected openings protect their supporting wall. No proximity electrical connections introduced by this module. Numeric length keeps start anchored; positive units convert to canonical source coordinates. All changes use existing history and backend revision/concurrency paths. Escape (including focused length input), Done and tool changes cancel preview; a drag gesture cannot commit an accidental wall. Undo/redo cancels pending drawing anchors.
- **Measurements / 2D and 3D:** `wallMeasurements.js` derives interior-face lengths only for explicit closed endpoint faces. Open walls and live previews are explicitly labelled centerline; numeric editing always edits centerline. No inferred room closure or measured length on unknown scale. Confirmed page scale is returned only when its stored reference dimensions match the candidate source plane; canvas and draft 3D use it. Optional per-wall thickness/height persist through strict review schema, `reviewGeometryPayload`, canonical save and 3D projection; existing global approval dimensions remain compatible fallbacks. Original detection output and weights are not modified. The lighting page has **no confirmed scale**, so its inspector correctly displays **161.11 source px (unscaled)** rather than fabricated metres. Live length edit to **170 px**, Undo, Redo and Undo back to baseline verified; temporary edit was **not saved**. Its illustrative 3D defaults remain explicitly labelled as assumptions.
- **Changed integrations:** `DemoInterpretationCanvas.jsx` / test, `DemoInterpretationPage.jsx` / test, `ReviewToolRail.jsx`, `devicePresentation.js`, `DraftRoomPreview.jsx`, `draftRoomScene.js`; backend `schemas/demo_interpretation.py`, `services/demo_interpretation_service.py`, `tests/test_demo_interpretation_api.py`. New task-owned modules/tests: `wallDrawing.js`, `wallDrawing.test.js`, `wallAppearance.js`, `wallMeasurements.js`, `WallDimensionEditor.jsx`, `WallDimensionEditor.test.jsx`; notices above. Canvas/3D and lean-build skills kept interactions, physical dimensions and shared persistence separate; no detector changes or new dependency/endpoint/table/DDL.
- **PASS verification:** full frontend **90 files / 729 tests**, Vite **2137 modules**, scoped ESLint and whitespace checks. Guarded disposable MySQL backend **40 tests**, including per-wall split dimensions through review/save/canonical reload, immutable review/stale-save gates and reanalysis durability. Tests cover exact rectangle/interior dimensions, angled walls, zoom-aware axes, edge/X splits, duplicate/collapse prevention, opening preservation, mounted device/wire movement, numeric metre/cm/mm/feet conversion, undo/redo, save/reload, and matching metric 3D sizes. Initial test failures were stale continuous-chain assertions and a missing strict response-schema scale field; fixed and gates rerun. Existing two backend dependency deprecations and >500KB frontend chunks remain. Full backend/full lint and exhaustive pathological polygon topology **NOT TESTED**.
- **Browser / evidence / intentional differences:** ordinary live Plan editor **9384 / 24276 / review 1** reload, numeric wall edit/undo/redo and loaded 3D view checked. Matched-scale normal and hover comparisons use the actual Konva component in an isolated fixture (not a fake toolbar or historical saved layout). Evidence under ignored `storage/training/blueprint3d-wall-editor`: `wall-editor-comparison.png`, `wall-editor-hover-comparison.png`, `ved-preview.jpg`, `live-inspector-24276.jpg`, `live-3d-24276.jpg`; fixture source archived there after verification. Reference room-grid/background/furniture UI not copied. VED retains selected endpoint handles and shared seam-free footprints instead of copying reference internal diagonal half-edge seams. It explicitly marks open-wall centerline labels and refuses destructive attachment edits. Complex/open/non-manifold faces do not receive invented interior dimensions; exact pixel-for-pixel parity in every topology is **not claimed**. Canonical measured 2D/3D dimensions are proven on calibrated synthetic save/reload, not on the uncalibrated live lighting scan.
- **Preservation / checkpoint:** branch **codex/vlm-localization-experiment**, scoped core checkpoint **f689542**, **8 new task-owned files / 418 insertions**. Mixed UI/backend integrations and tests remain local/uncommitted among pre-existing edits: checkpoint alone is **not a complete integrated release**. Index empty; no push. Stash **bb78854e87833124a1725b51f0be6099a8ac0cfa** preserved. Read-only before/after checks cover originals and every candidate/review hash on plans **9376/9382/9384**, all unchanged. No reanalysis, reviewed-layout overwrite, model/training promotion, role reset or new planning Markdown. Idle API refreshed once (launcher **40976**, server **17184**, no access logs); no active jobs interrupted. Temporary verification files removed from the served frontend and archived in ignored storage. Next roadmap phase not started.
- **Final read-only gate:** **41 OpenAPI paths / 49 operations / 34 metadata tables**, unchanged. Frozen model checkpoint SHA256 matches the earlier preserved baseline; original uploads/candidate/review hashes still match this task's baseline, with **0 active jobs**. Served build includes the full MIT notice. Live user/editor tabs retained; agent-created reference/fixture tabs closed. Source and private diagnostic artifacts remain local.
- **User-requested wall color override:** normal walls now dark navy `#0f172a`, with near-black edges `#020617`, in the Plan editor, canonical 2D canvas and joined/fallback 3D meshes. Hover/selection/preview cyan and deletion red stay distinct. Display-only shared `wallAppearance.js` change, no geometry/detection/persistence mutation. Updated canvas color assertion; focused frontend **21 tests passed**, build **2137 modules**, scoped lint and whitespace checks passed. Build chunk warning remains. No backend tests required for this appearance-only follow-up; changes remain local/uncommitted. Canvas/3D/design-system guidance preserved the common color token and interactive feedback.

### October 13 - Essential permanent application publication

- **User-authorized scope:** publish the essential permanent implementation to the tracked `origin/codex/vlm-localization-experiment` branch; no merge or force-push to `main`. Integrates the prior scoped wall/routing checkpoints with their required frontend/backend dependencies, dark-navy appearance, editable shared connections, draft BOM/material workbook import, corrected review persistence and regression tests. **192 changed/new application, test, safe-template and existing-ledger files** selected explicitly. Earlier statements that these integrations were only local are historical; this publication packages them together.
- **Excluded / preserved:** original uploads, private source/annotation/reference packs, model weights/manifests, actual pricing workbooks, `.env` credentials, generated builds, temporary browser fixtures and diagnostic scripts. Account-switch/reset work, unrelated planning/diagram edits, the unused `DeviceMeshCatalog.jsx` prototype (uninstalled optional dependency) and other unrelated working-tree changes remain local. `stash@{0}` hash **bb78854e87833124a1725b51f0be6099a8ac0cfa** unchanged. No ignored/private files force-added, reanalysis, model training, source rewrite or live review mutation.
- **PASS export gates:** tested a Git-index export independent of unstaged edits. **89 frontend files / 723 tests**, Vite **2137 modules**, **full frontend ESLint**, staged whitespace checks. Restricted/disposable MySQL **1442 backend tests / 1411 subtests passed**, **4 skipped**, with **5 dependency/deprecation warnings**. The initial frontend failures required the documented public `VITE_API_BASE_URL=http://localhost:8000`; development-only catalog tests required `APP_ENV=development` and still explicitly test production denial. Two stale assertions were aligned with the already-implemented contract: the additive runtime wiring response is distinct from immutable persisted review bytes, and OpenAPI includes `/api/projects/{project_id}/bom.csv`. Historical byte/hash assertions remain intact. No product features changed during publication verification. Existing >500KB frontend chunks remain warnings.
- **Integrity / reproducibility:** index-to-export content audit passed across **627 tracked files**, allowing only Git's configured Windows text line endings; source/test content otherwise matches. Sensitive-token and private-artifact path checks found none in the selected publication. Read-only checks confirm all original bytes, candidate hashes and saved review hashes for plans **9376/9382/9384** unchanged, with **0 active jobs**. Local model packs, reviewed catalog/scale/elevation inputs and pricing data must be supplied separately on another machine; publication does not make private weights/data available or claim independent detection accuracy. Verification skill kept the operation scoped to publication and gate maintenance.
- **Checkpoint:** application integration committed on the current branch and pushed using ordinary fast-forward Git push after the passing gates. Remote commit equality is checked separately; original/stash/unrelated files remain local and untouched. No next roadmap phase started.

### October 14 - PDF native evidence and partial coordinated source-view checkpoint

- **Scope / status:** source/view orchestration checkpoint, not completion of the requested detection-quality objective. Read the supplied request and CV/canvas/routing/3D/PDF guidance; inspect first, reuse the shared candidate/review/canonical paths, no new planning Markdown, model download, training, schema/table or dependency. The source contains two separate layouts plus legend/detail/parking/hatches, not one physical floor.
- **Evidence-backed causes:** whole-sheet raster-first interpretation discarded native PDF styles and used one broad plan region, allowing legend/title/parking proposals and confusing architectural hatches with walls. Wiring already masks its declared plan region; full-page RGB alone was not leakage. Crop restoration translated route points but not typed device/path anchors. The strict upload reader rejected duplicate non-geometric /PageMode metadata while PDFium rendered the source. Universal dash defaults were inappropriate without this drawing's legend. Browser verification also exposed previous-floor cards momentarily relabelled with new-floor links.
- **PASS implementation:** bounded PDFium primitive extraction preserves rotation/transforms/Bezier controls/styles/fill/text/image/native clips and parent-container identities in immutable hash-bound JSON sidecars. A spatial index avoids all-pairs primitive comparisons. Capability-driven raster fallback remains. Conservative caption + embedded-image-bank regions independently run existing CV, trained symbols and observed wires; fusion remaps IDs/evidence/contacts without cross-view joins. Partial region identity, per-layer outcomes, parser/pipeline versions and actual per-view/full-page preprocessing configurations are persisted. Missing/unsupported scopes remain unresolved, not verified negatives. Guarded regular-vector-hatch exclusion removed three supported distractor hypotheses; it is not a universal semantic classifier.
- **PASS preservation / coordinates / UI:** crop contacts translate with raw routes. PDF installation meaning stays unknown unless an explicit active legend mapping is selected. Multi-view 2D drafts save normally; measured canonical publication requires one view assigned to its floor through the existing versioned region workflow. Device proposals and annotations are counted separately. Loaded plan cards are bound to project/floor scope immediately; superseded responses cannot create wrong-floor editor links. No separate Three.js routing inference or fabricated service/floor heights.
- **Recovered live failure:** jobs 24282/24283 failed because the new crop loop attempted a backward geometry_evidence heartbeat after symbol_evidence. Private write-disabled replay isolated orchestration, and temporary local worker tracing identified the existing monotonic PRE9 rejection. Fixed by refreshing the current coordinated stage; did not weaken the lease/cancellation/concurrency guard. A real leased-worker database regression now exercises two synthetic views through persistence. Temporary tracing was removed; ordinary API restored, no active jobs interrupted.
- **Source / frozen model:** supplied BDO PDF SHA256 384fe30d0c03d9ddfe9e334d9076142a4107a583869a93b62dc805b817c9c973, one rotated 270-degree page. pdfplumber inventory: 66,775 lines / 661 rectangles / 6,464 curves / 25 images. PDFium inventory: 73,048 objects / 72,709 paths / 314 native text objects / 25 images / 178,446 path segments. These are primitives, not devices/walls. Existing power80 checkpoint SHA256 2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa and score threshold 0.50 unchanged; legacy provider alias still contains 56 but actual head has 80 classes.
- **Before/after, NOT accuracy metrics:** whole-sheet baseline 6 walls / 64 symbol-and-annotation proposals / 5 observed paths / 3 contacts; independently scoped result 38 / 18 / 11 / 4. The 18 comprise only 6 physical-device proposals and 12 annotations. Regions are deliberately partial and omit some perimeter/parking areas; remaining missing outlets and false furniture/hatch/fixture hypotheses remain visible. A sharper native-crop trial increased false fixture detections and was NOT promoted. Counts do not establish recall, precision, approved connections or completeness.
- **PASS live workflow:** normal Designer upload created floor 6328 / plan 9388. Initial successful job 24281 / saved unfinished review 204 revision 1 remains unchanged. Final corrected new job 24284 / unfinished review 205 revision 1 saved and reloaded; approved=false, complete=false. Both payloads have identical sorted SHA256 3d4abf13c55021463d186530648790cf01e6cef8e9290ca48ce79c4433044201. Full envelope hashes differ appropriately with run identity/provenance. 2D and shared draft 3D browser views checked; 3D remains illustrative, not measured or approved. Source sidecar hashes and view configuration verified. No accepted layout replaced.
- **PASS other drawings separately:** three complete current-stage raster replays repeat exactly and match the pre-refactor stage sequence: lighting 9384 = 37/58/35/72, power 9382 = 13/16/9/12, additional untuned raster 9377 = 11/29/8/15 (walls/symbols/paths/contacts). Lighting also matches its saved v15/v8 payload exactly. Older power/additional candidates used different CV/wiring versions; differences from those are not attributed to this PDF orchestration change. No model held-out accuracy metric claimed.
- **PASS gates:** final full workspace backend 1,480 tests / 1,438 subtests, 4 skipped, 5 deprecation warnings; full frontend 91 files / 735 tests; Vite 2,140 modules; scoped ESLint and whitespace checks. Focused PDF/upload/canonical checks 55 tests, followed by 13 leased-worker tests after the heartbeat correction. Initial frontend sandbox temporary rename denial recovered using normal installed dependencies; a long Windows test-temp path exceeded MAX_PATH and passed with a short fresh temporary path. Tests use restricted ved_electrical_verify and isolated storage, never live project tables. Existing chunk-size/deprecation warnings remain.
- **Research, selectively used:** [Raster-to-Vector](https://art-programmer.github.io/floorplan-transformation/paper.pdf) separates junction recognition from topology assembly; its Manhattan/closed-loop assumptions are not imposed here. [FloorPlanCAD](https://arxiv.org/html/2105.07147v2) supports combining image/primitive context. [CADSpotting](https://arxiv.org/html/2412.07377v5) motivates bounded large-drawing processing. [Modular Graph Extraction](https://arxiv.org/html/2402.11093v1) separates symbols/strokes/text/ports from graph assembly. Concrete reuse is source evidence, view isolation and distinct existing wall/electrical modules. No paper network, integer program, pretrained framework or reported paper score implemented/adopted.
- **FAIL / NOT TESTED / BLOCKED:** complete wall coverage, reliable outlet recall, all false positives and complete electrical graph are not achieved. Automated full legend interpretation, arbitrary curved-wire connectivity, exhaustive unknown PDF layouts and quantitative quality without approved references NOT TESTED. Unreviewed regions are not negative labels. Measured live 3D/drop/BOM/canonical publication BLOCKED pending single-view floor assignment and stored approved scale/elevations; 2D draft saving is not blocked. Existing joined-footprint/topology and canonical rendering remain reused, not claimed as a new PDF semantic wall solver.
- **Files / checkpoint scope:** task-owned PDF evidence/view/hatch/scoped modules and service, crop-anchor restoration, processing/provenance/configuration/upload/legend/publication guards; real/synthetic regression tests; source-view panel/choice utility, plan header/counts, processing message and floor-card scope guard; existing candidate contract and this ledger. Separate prior 2D labels/3D color fixes, account/reset/training work, private originals/model/pricing/artifacts and stash remain unstaged. Scoped local checkpoint on codex/vlm-localization-experiment; no push or next roadmap phase.
- **PASS exact staged checkpoint:** independent Git-index export contains 639 tracked files, audited against index bytes with only Windows text-line-ending normalization. Full exported frontend **90 files / 727 tests**, Vite **2,140 modules**, **full ESLint**; exported focused backend **56 tests** against restricted empty verification database. These counts exclude unrelated local auth/color/label work; workspace full gates above are reported separately. No private/source/model/pricing artifacts selected, secret-pattern scan passed. Read-only contract inventory **41 OpenAPI paths / 49 operations / 34 metadata tables**, unchanged; frozen model artifacts verified again. Final editor-focused browser screenshot retained as browser-editor-24284.png. Local checkpoint only, not pushed.
- **Private evidence / integrity:** retained actual baseline, rejected trials, raster comparisons, live hashes and before-after-24284.png / browser-2d-24284.png / browser-3d-24284.png under ignored storage/training/unified-pdf-investigation. Read-only original/candidate/review checks on 9376/9382/9384 pass; PDF 24281 history unchanged; active jobs 0. Stash bb78854e87833124a1725b51f0be6099a8ac0cfa unchanged. Temporary tracing and fixtures remain outside product code.
