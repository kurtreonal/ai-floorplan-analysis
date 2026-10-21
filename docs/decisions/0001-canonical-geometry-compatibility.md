# ADR 0001: Canonical Geometry Compatibility After K1

- Status: Accepted
- Decision date: 2026-09-06
- Owning ticket: PRE11
- Current implemented contracts: K1 schema version 1; separate extension versions 2 through 6
- Original PRE11 decision is retained below; see the implementation addendum.

## October 11 implementation addendum

U11 has since implemented extension version 2 in the separate immutable
`layout_extensions` record. K1 remains version 1. Extension version 3 now adds
optional explicit symbol `installation` data (`elevation_meters`, nullable
canonical `wall_id`) in `symbol_details`. Python and JavaScript dispatch by
integer extension version; version 2 still rejects the new field and unknown
versions still fail closed. Existing snapshots are neither upgraded nor
rewritten. New saves use version 3 only when mounting data was supplied.

Installation elevations come from stored floor elevation plus a supplied
mounting height. The same canonical route points contain any derived vertical
drop; rendering must not infer another connection from nearby pixels. The
original observed source path and explicit attachment remain in the append-only
review. Missing measurements do not prevent saving an unfinished 2D review.

Rollback: existing version-1/version-2 snapshots remain readable by the prior
application. Do not downgrade or discard a version-3 installation; an older
extension reader must reject it explicitly. No schema/table migration or
destructive contraction is introduced by this change.

## Context

K1 is a strict, renderer-independent schema used by Python, JavaScript, K2
snapshots, the K3 API, and the K4/K5 editor. Existing version-1 snapshots lack
explicit page identity, first-class openings and electrical panels, optional
symbol orientation/bounds, and route provenance. Adding optional keys to K1
would still break its exact-key validators and would silently change a frozen
historical contract.

PRE4 and PRE5 now provide immutable source/page and derived-artifact identity.
PRE6 provides approved scale and elevation evidence. Future VLM work must use
those records without turning model output into canonical geometry or inventing
missing architectural or electrical meaning.

## Decision

K1 schema version 1 remains frozen and readable in its current exact shape.
Existing K2 snapshots are returned and edited in version 1 without migration,
backfill, or rewrite. The current Python and JavaScript entry points continue to
reject every unsupported schema version with their existing sanitized errors.

Canonical extension version 2 is reserved for a separately implemented U11
contract. The existing `layout_versions` table has a database check requiring
`schema_version = 1`, and prototype `create_all()` cannot alter it. U11 must
therefore use an additive one-to-one extension record associated with a newly
created, immutable K2 version-1 snapshot; it must not place version-2 JSON in
the existing geometry column or weaken the live constraint. Creation of the
base snapshot and extension must be one transaction.

There is no implicit read-time upgrade. A version-1 document that lacks required
source/review evidence remains version 1; software must not fabricate values to
make it extendable. Existing consumers read the stored version-1 base exactly as
they do now. A future extension-aware consumer must select an exact extension
validator by integer extension version and may compose a versioned view without
rewriting the base. Unknown versions fail closed. Downgrading or silently
discarding extension data is not promised.

The shared compatibility fixture is
`fixtures/canonical_geometry_compatibility_v1.json`. Python and JavaScript tests
must consume the same matrix. It requires the existing
`canonical_geometry_v1.json` to remain accepted and extension version 2 to
remain rejected by the K1 validator until U11 deliberately supplies both
runtimes with matching extension validators and
representative valid, empty, partial, malformed, and unsupported-version
fixtures.

## Data ownership

Candidate interpretation and append-only review records own evidence:

- immutable source document, source page, and one-based page number identity;
- source-pixel region or tile bounds and reversible transforms;
- model, prompt, adapter, artifact, OCR, and ambiguity provenance;
- raw opening, panel, symbol-orientation/bounds, and observed-route proposals;
- reviewer decisions, corrections, approval state, actor, and time.

The candidate uses source pixels. Regions may be absent for whole-page evidence.
Orientation, bounds, opening dimensions/types, panel attributes, and route
meaning remain nullable, unknown, or ambiguous when evidence and professional
review do not resolve them.

Canonical geometry owns only approved, renderer-independent metric results and
stable references needed to trace them back to approved evidence. The additive
version-2 extension is reserved to add:

- an approved source-plane reference tied to PRE4 source/page identity;
- first-class openings associated with canonical structure, without guessed
  type, height, thickness, or clearance;
- first-class electrical panels with stable identity and approved position,
  while electrical ratings and other undefined attributes remain deferred;
- optional approved symbol orientation and bounds when downstream rendering
  needs them; a position alone remains valid when those facts are unknown;
- an explicit route kind of `observed` or `generated` plus a provenance
  reference. Missing visible wiring produces no observed route.

Later routing-domain records, not VLM candidates or canonical rendering fields,
own generated-route algorithm identity, rule-set version, segments,
measurements, and electrical design choices. `observed` means visibly supported
by source evidence. `generated` means produced later by an approved routing
process; it must never be relabeled as observed.

## Adapter and negotiation rules

U2 must define candidate/review identifiers and source-pixel evidence compatible
with this ownership boundary. U11 must implement the extension dispatcher,
version-2 extension schema, and additive persistence in Python and JavaScript
together, then adapt only approved records using approved scale/elevation. It
must create a new K2 version-1 base snapshot and its extension atomically rather
than mutate history, and must preserve machine and review records independently.

APIs and consumers must inspect both the base `schema_version` and any explicit
extension version; they must not infer a version from available keys. A
version-1-only consumer continues to return the native base. An
extension-capable endpoint must fail closed on unsupported extensions rather
than drop their fields. No current K3 response claims to expose an extension.

## Consequences and deferred work

This decision adds no schema, table, endpoint, adapter, worker, model, route
algorithm, or 3D renderer. It approves no default opening dimensions, wall
height, panel rating, symbol rotation, electrical rule, or route. Exact
version-2 extension validation and additive persistence are U11 work after U2 defines the
candidate schema. K1/K2/K3 behavior and existing original uploads remain
unchanged.

## Connected wiring extension (version 6)

The additive version-6 reader retains the version-1 base and the exact version
2–5 shapes. It adds optional route `vertex_ids` and `network_lineage`, explicit
device `terminal_id`, and `manual` route provenance. New writes select version
6 only when these features are used. Unknown versions and malformed references
fail closed; old reviews are not rewritten or implicitly connected.

Existing path IDs remain editable edge records. Explicit junction references
and matching device-terminal references define connected components, not
crossings, distance, or common device bounds. Component identity is the stable
lexical minimum active path ID; persisted lineage retains predecessor path IDs
after branch removal. Per-path vertex IDs survive edge insertion and loops;
shared junction/device references carry cross-path node identity. Unspecified
historical terminals remain isolated. Source proposals derive terminal identity
from the validated source port, never the device bounding box. A deliberate
manual device click may select a design anchor; it is not an inferred electrical
pin or approval of observed pixels.

Drawing commits one continuous polyline and its explicit splits/joins in one
undo transaction. Connected paths retain their original IDs and per-path
provenance. Both draft renderers use the same component resolver. Backend
physical takeoff unions supported overlapping spans only within explicit
compatible groups; circuit/conductor assignments are not inferred or discarded.
Unscaled source lengths remain pixels. Metric publication still requires the
existing approval, scale, routing and device-elevation checks.

Generated A* drafts keep their existing separate review/publication lifecycle;
cross-origin draft joins remain rejected, rather than silently promoting them
to reviewed source wiring. Version 6 does not approve generated routes or
relax final estimate eligibility. This restriction is explicit remaining work
for a future unified reviewed-route lifecycle, not a geometric merge heuristic.

## Measurement checkpoint 1a (October 19)

K1 and extension snapshots remain unchanged. Backend physical centerline
measurement now shares `canonical_centerline_3d_v1` across generated route
materials, circuit previews, and saved-canonical path takeoff. Horizontal and
vertical figures are projections; a supported 3–4 sloped span measures 5 metres,
not 7 or 8. Explicit physical-path identities keep coincident independent runs
separate; numerical collinear interval union never discovers circuit membership
or junctions. Canonical inter-floor edges without connectors remain excluded
and flagged. Stored generated orthogonal route totals are still validated.
Estimates capture the measurement revision with existing immutable layout,
route/configuration and price snapshots; historical estimates are not rewritten.

Known-dimension calibration is an optional input on the existing scale approval
endpoint. The backend computes pixels/metre and appends the measured pixel and
real lengths to existing approval evidence. Its page identity, image dimensions,
actor, revision and resulting scale persist in existing append-only fields; no
database schema reset, migration or new table is involved. Legacy explicit-scale
approval remains compatible. Explicit similarity-transform propagation is tested
for crop translation, quarter rotation and uniform resizing; nonuniform resize
and shear reject a scalar scale. This helper does not infer transforms from
dimensions, create new source views, or make a printed 1:100 label trustworthy.

This slice does not complete checkpoint 1: draft paper assumptions and incomplete
drop pricing still need tightening; allowances/purchase rounding, physical-path
identity in all editing commands, and live transformed-view calibration require
further integration/verification. Checkpoints 2–7 remain separate authorized work.

## Measurement checkpoint 1b (October 19)

The normal draft BOM no longer derives pixels/metre by fitting an arbitrary
image to A-series/custom paper at 1:100. Paper dimensions remain metadata;
without matching reviewed calibration, route quantities remain source pixels
and unpriced. A trusted physical page/render calibration is not implemented by
that dropdown. Missing device drops/rises also block catalog and custom route
pricing instead of showing a partial length as a complete cost.

Conduit SKU selection no longer equates a purchased `length` with one metre.
Non-metre products remain unresolved without an explicit purchase conversion;
the saved-estimate flow retains its existing explicit conversion fields. Drop
deduplication is scoped to an explicit connected path group and terminal, not
globally to any paths touching the same device/service elevation. Genuine
independent runs retain their own drops. Original reviews, prices and estimates
remain immutable. No allowance, conductor count, elevation, or real-world scale
is invented. Remaining checkpoint-1 integration listed above is still pending.

Verification of the clean staged 1a/1b snapshot: 144 selected backend tests
(including schema/OpenAPI, permissions and historical snapshots), 15 subtests,
55 focused frontend tests, scoped lint and build pass. It retains 49 OpenAPI
operations and 34 tables. The mixed worktree retains an unrelated uncommitted
50th API operation and its existing count-assertion failure; that change is not
included or hidden by adjusting the assertion. Live browser controls were
inspected without approving a real project scale. Full-suite and measured live
2D/3D/BOM verification remain unclaimed.

The shared-span follow-up reuses canonical explicit route groups in circuit
takeoff. An explicitly joined overlapping span now measures identically in
canonical BOM and circuit preview; independent coincident runs remain separate.
Circuit conductor multiplication remains separate from physical length. The
clean scoped snapshot passes 157 selected backend tests, including save/reload
and API contracts, without changing the 49-operation/34-table contract.

## Magnetic wiring checkpoint 2 (October 19)

Endpoint magnets now enumerate equally near compatible device terminals and
path targets rather than discarding their identities on a tie. A shared compact
chooser in 2D/3D resolves an overlap only after the designer selects one target.
Focus/hover previews its exact device ID/terminal or path; Escape cancels. The
original endpoint stays unchanged until selection. Scene/document, selection,
tool or editing-session changes invalidate pending choices. Commit uses existing
revalidated device/junction commands, edge splitting and one-step undo; there is
no proximity-based crossing join, positional spreading or connect-all operation.

Existing explicit terminal IDs remain distinct. Where there is no saved terminal,
the deliberate manual choice uses the existing `design-anchor` convention, not
an invented electrical pin. The current review contract requires these anchors
at the canonical device center; unsupported/inconsistent off-center terminal
records are not offered as saveable targets. Offset pin geometry is not newly
supported. Automatic detection/review approval and source evidence are unchanged.
Advanced numeric wire coordinates remain available behind a collapsed control;
normal endpoint editing does not depend on them.

Live verification uses temporary unsaved overlap edits on lighting job 24339:
the chooser lists two switch IDs, selects only the requested one, and one undo/
redo restores the original/chosen binding respectively. These temporary edits
are discarded, not published as a review. Checkpoint 3 (genuine 3D drawing),
checkpoints 4–7 and the explicitly remaining measurement integration are not
claimed complete by this interaction slice. BDO detection/training stays paused.

Verification: the clean scoped export passes 142 focused frontend tests and 60
restricted-database backend tests, including independent co-located device
bindings, rejected invalid anchors without revision replacement, save/reload,
permissions and historical contracts. Frontend API tests use the documented
`VITE_API_BASE_URL=http://localhost:8000`; without that exported environment their
two fixed-base URL assertions fail. Scoped lint and production build pass
(existing large-chunk warnings remain). No API operation/table changes: the clean
contract remains 49/34, while unrelated worktree additions remain excluded.
Full suites are not claimed. Live 2D chooser/undo/redo and discard/reload pass;
live 3D interaction is BLOCKED by this browser's WebGL fallback, despite passing
handle/chooser unit tests. Original images, reviews and estimates were not
written; the verification tab was closed and stash@{0} retained.

## Work-plane drawing checkpoint 3a (October 19)

3D wall and multi-point wiring drawing now call the existing shared wall and
connected-wire commands. The first slice is deliberately a horizontal plane on
the current calibrated source view, not arbitrary screen coordinates or a new
Three.js-only model. Camera rays intersect that explicit plane; parallel,
backwards and out-of-page hits reject. Camera/device dragging and competing 2D
keyboard handlers are suspended appropriately while drawing. Finish, cancel,
Backspace and existing undo/redo preserve transaction boundaries. Failed commits
retain the stroke for correction. Tool/session changes invalidate pending targets.

Wiring requires an explicit service elevation from the project datum and uses
compatible path/device magnets, including the overlap chooser. An optional
designer-entered circuit ID is not inferred from nearby circuits. One continuous
path retains manual provenance, vertex/terminal identities and one stored route
elevation; existing shared projection/measurement handles supported device drops.
Walls use the configured floor plane and explicit height/thickness, optional
exact metric length, axis constraints and existing corner/edge splitting. Existing
opening and mounted-device protections remain in the shared commands.

Missing approved scale or floor elevation blocks this measured 3D drawing slice,
not 2D editing. Preview dimensions and illustrative mounting presets never become
stored measurements. Per-vertex varying elevations, arbitrary sloped/multi-floor
drawing and off-center electrical pins are not added to the current review
contract. Final quantities still require existing measurement and approval gates.

Correction to the previous browser assessment: the accessibility tree exposes
the canvas fallback text even while WebGL renders successfully. That text was
not evidence of WebGL failure. Visual inspection at this checkpoint confirms a
rendered live scene; checkpoint-2 live 3D drag remained NOT TESTED, rather than
proven blocked. The live uncalibrated plan correctly disables measured drawing.

In an isolated synthetic browser fixture (10 pixels/metre, floor datum 12 m),
actual pointer clicks created one three-point wire at datum 14.8 m and two
connected 5 m walls of thickness 0.2 m/height 3 m. JSON save/reload and 2D/3D
switching retained identical records, one wire and two walls; both wall lengths
computed as 5 m from the displayed source coordinates and the known fixture
scale. Whole-wire undo/redo passed. This fixture is editor proof, not independent
detection ground truth, a production project save or a final live BOM result.
Separate restricted-database tests verify real review endpoint persistence,
invalid-elevation rejection, unchanged candidate/history and permission contracts.
No real project calibration, upload, review or estimate was written. BDO remains
paused; unrelated changes and stash@{0} are retained. Checkpoints 4–7 and remaining
measurement integration are not completed by this slice.

Scoped verification: 116 selected frontend tests, 61 restricted-database backend
tests, scoped lint and production build pass. The live synthetic fixture also
cancelled an actual two-point 3D stroke with Escape and retained identical
committed geometry. Large bundle and existing backend deprecation warnings
remain. Full suites and a measured production-project BOM are NOT TESTED. The
API/table contract is unchanged (49/34 in the clean snapshot; unrelated mixed
worktree additions excluded). Browser fixtures/screenshots are local diagnostics,
not shipped application routes or new project records; temporary fixture source
is retained under ignored `tmp/` after the verification tab is closed.
The 3D canvas stays mounted after a drawing session even if undo removes the
last shape, so that operation does not discard the camera/viewport. A focused
empty-scene regression covers that lifecycle in addition to keyboard ownership.

## Searchable object lists checkpoint 4 (October 19)

The review inspector now has separate Devices, Wiring and Walls tabs. Each keeps
its own local search. Searches use existing labels/types/IDs, wire names and
circuit IDs/references, and wall names/IDs; stable IDs distinguish co-located
devices. Natural display ordering never sorts source arrays. Arrow/Home/End
navigation, native result buttons, clear-search focus and bounded scrolling keep
the lists keyboard usable. The collapsed all-items selector retains room access
and removed-item restoration. Selection is disabled during pending strokes/saves.

Result selection uses the shared selected kind/ID and enables only its view
layer. Existing device/wire highlighting is reused; joined and legacy 3D walls
now highlight the exact selected wall without altering footprints, dimensions,
meshes' stored identities, or camera configuration. Search never writes a draft,
changes undo history, filters BOM input, approves geometry or changes provenance.
Automatic camera focusing and saved search preferences are not added.

The clean scoped snapshot passes 95 focused frontend tests, 80 restricted-database
backend tests plus 15 subtests, scoped lint and production build. Tests include
co-located identities, field searches, independent queries, keyboard/disabled
states, unchanged geometry/BOM inputs, exact 2D/3D selection, wall highlighting,
undo/redo, review save/reload and existing authorization/history contracts. The
API/table contract remains 49/34; unrelated mixed-worktree additions are excluded.
An initial mixed-worktree run had additional UI/test mismatches (12 failures
outside the scoped snapshot); a new list-ordering failure and an export dependency on an
uncommitted helper were corrected. This does not claim those unrelated failures
are resolved or that the full suites pass.

Live lighting job 24339 verifies exact device-ID search/2D highlighting, independent
wall/wire queries, keyboard tab switching and selected-wall highlighting in an
actually rendered 3D scene. Search/selection left Undo disabled and the draft
without unsaved changes. Reload was read-only; no real project save, calibration,
review, estimate or original upload was written. Browser screenshots are local
diagnostics under ignored tmp/, not inference evidence. Existing large-chunk and
backend deprecation warnings remain. BDO stays paused; originals, historical
reviews, unrelated edits and stash@{0} are preserved. Full suites, screen-reader
testing and a production measured BOM remain NOT TESTED. Checkpoints 5–7 and the
previously listed measurement integration are not completed by this slice.

## Project client pricing checkpoint 6 (October 20)

Checkpoint 6 is explicitly prioritized ahead of checkpoint 5; project intake and
floor-plan deletion remain on hold. BDO detection, annotation and training remain
paused. This slice does not change detection, canvas geometry, calibration,
electrical routing rules, allowances, or the shared Admin catalog.

The estimate page now supports project-owned XLSX and UTF-8 comma-separated CSV
imports. A price list supplies prices for backend-calculated quantities; a client
BOM additionally retains source quantities for comparison, never as replacement
calculated quantities. Designers explicitly map worksheet/header, columns,
catalog materials and catalog units per quoted purchase unit. No material match,
wire gauge, conduit size, roll/pack factor, currency conversion or missing price
is guessed. Identical units use identity conversion only. Duplicate codes or
material bindings, formulas, missing values and invalid conversions require
correction or explicit row exclusion. Zero prices are valid; blank prices are not.

The Admin import's bounded ZIP/XML safety envelope is shared without changing
its catalog-write workflow. Client imports reject macros and external workbook
links, never evaluate formulas (including cached numeric formula results), and
never execute CSV cells. Limits are 5 MB source, 1,000 selected data rows per
worksheet, bounded cells, and the existing ZIP expansion/member limits. The UI
shows at most 5,000 catalog choices and the latest 100 import versions; older
versions remain addressable by ID. PDF/scanned BOM extraction is not supported.

One additive table, project_price_versions, retains immutable source bytes,
SHA-256, mapped/excluded rows, actor and per-project version. Owner/Designer
access is enforced server-side; Admin has read-only project inspection. Apply
reparses the source, checks the preview fingerprint and current material identity,
serializes on the project lock, and rejects stale versions. Identical concurrent
retry UUIDs return one saved version; changed retry inputs conflict. No update or
delete endpoint is provided. Uncertain saves lock UI inputs for identical retry.

New estimates use a selected Admin catalog or client import version. The follow-up
below defaults to the latest confirmed client import while retaining the selector.
No fallback is made for a missing client material price. Existing route/layout
measurement gates remain required. Catalog quantities are converted to the quoted
purchase unit with the confirmed factor; the existing four-decimal quantity
policy remains unchanged, with no purchase rounding or waste added. Prices,
conversion factors, row IDs, import version, file identity and source document
are captured in the estimate snapshot. Later imports cannot reprice history.
Quantity comparison is displayed as calculated minus client in the
import's purchase unit; unreconcilable or absent estimate materials are explicit,
not fabricated zeros. Legacy catalog retry hashes remain compatible. Initial and
reloaded totals now share the stored eight-decimal scale (zero padding only).

Deployment used an isolated HEAD export, then an additive table before code
activation. A private logical backup is retained under ignored
tmp/checkpoint6-db-before. All 34 pre-existing live table counts and extended
checksums were identical before/after creation; the 35th table was empty and
readable by ved_app. No existing table was altered, reset or dropped, and no
permissions or credentials changed. Rollback can run the prior code while
retaining the unused table and any future imports; do not drop imported history.

Verification includes restricted-MySQL API tests for explicit mapping, invalid
files/formulas/macros/links, ownership, zero/missing prices, duplicate decisions,
stale catalog/preview rejection, real concurrent identical imports, save/reload,
pack conversions and historical estimate preservation. A disposable browser
project completed CSV upload, column/material mapping, explicit 10 m/roll,
validation/confirmation, save and estimate generation. The actual 2 m synthetic
route with three conductors produced 0.6 roll of wire, two device units and 2 m
conduit: PHP 30 total. Reload retained that estimate, its captured client version
and client/calculated differences (9 versus 2 devices, 20 versus 2 m conduit,
1 versus 0.6 roll). This is workflow/known-answer proof, not detection accuracy
or independent real-client workbook validation. Screenshots/fixtures remain
private diagnostics under ignored tmp/; synthetic records are cleaned by exact IDs.

Client prices apply to saved measured estimates and saved BOM exports. The draft
canvas/catalog BOM preview is unchanged and may still show missing catalog
prices; it is not silently repriced by an import. Full-suite, arbitrary client
workbook, PDF import and computer-reboot verification remain NOT TESTED. Existing
large frontend chunks and backend deprecation warnings remain. The clean API/
table contract is 54 operations/35 tables; the live mixed worktree has one
additional pre-existing uncommitted canvas-BOM endpoint (55 operations). Unrelated
edits, originals, historical reviews/estimates and stash@{0} are preserved.
Checkpoint 5 had not started in this slice.

Final staged gate: 421 backend tests and 234 subtests pass, one skip; 25 focused
frontend tests, scoped lint and production build pass. The expanded gate first
identified exact table/operation enumerations needing the additive contract;
five unrelated development-only legend-import checks also required explicit
APP_ENV=development instead of the isolated copy's production-default setting.
Their application behavior was not changed, and all analysis workers remained
disabled. Live authenticated project 10219 confirms import controls and the
existing missing-measured-route gate without saving real project data. Temporary
verification records were removed by exact IDs. API and frontend were restarted
normally after they were found stopped; no automatic analysis jobs were started.

## Project intake checkpoint 5A (October 20)

After checkpoint 6, the authorized checkpoint 5 is split into intake/editing (5A)
and recoverable floor-plan deletion (5B). This slice completes intake only; it
does not implement or claim deletion, job fencing, restore or DWG support. BDO
work remains paused. Existing project name/client/location fields are reused.
Five nullable project columns retain contact_number as a string, service_type,
service_type_other, preferred_start_date as DATE, and blueprint_availability.
No values are inferred for legacy projects. The Other option requires a supplied
description. Dates are date-only, within MySQL's supported range, with no timezone
conversion or invented start date. Available now/Later/Unavailable are metadata,
not a requirement to upload before creating a project.

Create and edit share the same intake controls. Available-now projects hand off
to the existing floors/upload panel without creating a floor or duplicating an
upload. Designer owners can PATCH only metadata; Admin remains read-only.
Owner, status and server-managed fields are rejected. An expected content-based
details revision and current row lock prevent lost updates even with second-
precision MySQL timestamps. A retry of already-applied values returns the current
result, while a conflicting newer edit returns 409. Uncertain UI saves lock
inputs for identical retry; conflicts retain inputs until explicit discard/reload.
Audit logging contains project/user IDs, not contact details.

Development schema initialization remains explicit, never an HTTP startup write.
The existing app.core.schema initializer now adds only these missing nullable
columns, validates definitions already present, and can be rerun after a partial
DDL application. It does not reset, populate, drop or rewrite data, and refuses
production mode or incompatible existing definitions. Back up first and use a
local DDL-capable configuration for this explicit development step; the normal
ved_app CRUD grants and application DATABASE_URL are not changed. No Alembic or
separate migration framework/files are introduced. Older code can keep using the
expanded table; rollback retains the nullable columns and any entered intake data.

Before live model activation, a private logical backup was taken under ignored
tmp/checkpoint5a-db-before and the expansion was verified against the restricted
database first. Original-column project values/counts match their pre-expansion
hash; all 34 other application tables retain identical counts/extended checksums.
The four real projects retain NULL in all five new fields. The table count stays
35; clean API count is 55 (56 in the mixed live worktree due to the unrelated,
uncommitted canvas-BOM endpoint). Existing schema readers and ved_app access
were checked before activating/restarting only the local API, with workers off.

A disposable browser fixture created a project without a blueprint/floor,
preserved a formatted phone/date/Other description, changed to Maintenance and
Available now, then reloaded with the literal phone 000123 and date 2027-01-05.
Upload handoff focused the existing empty floor panel without creating anything.
This is synthetic workflow proof, not a real client intake change. Fixture data
was cleaned by exact synthetic identity. Screenshots/backups remain private,
Git-ignored diagnostics. Originals, reviews, estimates, client price versions,
unrelated changes and stash@{0} are preserved. Full suites, reboot behavior and
5B floor-plan deletion are not established by this checkpoint.

The exact staged snapshot passes 438 selected backend tests and 234 subtests
(one skip), 47 frontend tests, scoped lint and production build. Checks cover
nullable legacy records, phone strings, dates, invalid Other combinations,
permissions, stale edits, identical uncertain-save retry, schema idempotence and
incompatible-definition refusal. Checkpoint-6 import/estimate and route regressions
remain passing. Existing large-chunk and backend deprecation warnings remain.
The live legacy project page shows new fields as Not specified without changing
its original metadata or uploads. The next separately verified ticket is 5B;
its dependency review and deletion implementation have not started in this slice.

### Checkpoint 5B — recoverable floor-plan removal (2026-10-20)

Floor-plan removal is an append-only lifecycle transition, not a file, floor,
review or layout DELETE. `floor_plan_lifecycle_events` records the plan, actor,
action, monotonically increasing revision and unique request identity. Plans
without events remain active without fabricated metadata. Owner Designers may
preview the exact target, move it to Trash and restore it; Admin access remains
read-only. Stale requests return 409. An uncertain request can be retried with
the same identity, but cannot undo a later restore/removal (ABA protection).

Removal locks floor -> plan -> jobs and atomically cancels unfinished jobs,
active leases and unfinished selected pages. Completed pages/jobs remain history.
Restore never requeues cancelled work. Job claims, heartbeats, completion and
publication share the parent-first order. The legacy demo worker previously
committed candidates before its final cancellation check; it now reuses the
production publication fence. Production page initialization is also fenced
after claim, preventing a late initializer from reviving cancelled page state.
Artifact registration also rejects cancelled jobs after plan restore; legacy
wall/symbol persistence checks the active plan.
Review edits and canonical saves reject removed plans while retaining history.

Active upload lists, calibration-page selection, current layouts, draft BOM and
routing inputs exclude trashed plans explicitly. Historical current markers,
canonical documents, original upload paths/bytes, review revisions and captured
estimates are not rewritten. A saved route becomes stale when its current source
plan is removed; restoring the unchanged source makes it current again. Saving
a new current layout on another upload still supersedes the old marker normally.

Deployment adds only the new table through the existing explicit prototype
schema mechanism; no ALTER, Alembic, reset or HTTP-startup DDL. A private SQL
backup precedes deployment. All 35 existing table counts/extended checksums and
44 uploaded-file hashes matched before/after; history starts empty in the real
database. The create operation is idempotent. Code rollback must preserve the
history table: older code ignores lifecycle state and would show removed plans
again, but no original or historical content is lost. This is recoverable
removal, not a permanent purge or archival-retention policy.

Browser verification used a disposable project in the restricted verification
database: inspect target/consequences -> remove -> reload -> Trash -> restore ->
reload, with the sibling upload unchanged. Exact synthetic rows and temporary
servers were cleaned; screenshots/backups stay private and Git-ignored. No real
plan was removed/restored and no BDO analysis/training was started. Both live
workers remain disabled. The clean API has 59 operations and 36 tables (the
mixed live API has 60 due to the unrelated uncommitted canvas-BOM operation).

Focused checks cover owner/Admin access, request validation, stale/identical
retry, rollback of partial cancellation, concurrent completion/removal, late
candidate/artifact/page writes, restore without job resurrection, current-layout
and route eligibility, unchanged review history and captured estimates. The
existing upload integration test's obsolete recovery-v2 assertion also failed
on the pre-change baseline; its assertion now names the already-implemented v3
contract. No detector configuration/model or recovery algorithm changed here.
Full-suite and reboot behavior are not established by this checkpoint; existing
large frontend chunk and backend deprecation warnings remain.

The exact staged scope passes 422 selected backend tests plus 219 subtests and
47 frontend tests, scoped lint and both isolated/live frontend production builds.
One review-image symlink check is NOT TESTED because the environment cannot
create symlinks. No failed gate is silently counted as a pass. Live `/health`
returns 200; the existing three-column project list and its new Trash section
load with the original uploads intact. The unrelated live worktree and
stash@{0} remain preserved; scoped commits do not publish those edits.

### Feature verification audit (2026-10-20)

DWG checkpoint 7 is cancelled at the user's request. Its special-case upload
messages and tests have been removed; DWG uses the existing unsupported-format
validation. Only JPEG/PNG/PDF uploads remain supported. No converter was installed
or integrated. The non-DWG feature audit and checkpoint-5B API expectation fix
are retained. The following results are historical, before this removal.

Removal verification: 64 focused backend upload tests and six subtests pass
(the unrelated global OpenAPI assertion is excluded). All 16 upload-form tests
and scoped frontend lint pass. The complete upload test file has 33 passes and
the same two existing project-panel failures about the review link and empty
analysis text. The 35 existing table fingerprints and 44 uploaded files remain
unchanged; there are no active analysis jobs. No full-suite rerun is claimed.

#### Cross-feature verification (not a universal completion claim)

| Area | Evidence and status |
| --- | --- |
| Authentication / authorization | PASS for existing session, owner/Admin isolation and synthetic OIDC/role contracts. No new provider consent/login or live permission change. |
| Measurement / routing / BOM | PASS for known lengths, shared branches, independent coincident routes, slopes, configured drops, explicit risers, calibration transforms, current/stale routing and price snapshots. Live unscaled geometry remains source pixels; incomplete drops and unmatched materials stay unpriced. Full transformed-view UI calibration, configurable allowances/purchase rounding and physical-path identity through every editing command remain earlier documented integration limitations. |
| Magnets / overlapping devices | PASS in geometry/interaction tests for explicit targets, split/join, crossing separation, distinct terminal identities, compatibility, undo/redo and save/reload. No new manual correction of a private plan. |
| 2D / 3D editing | PASS for committed work-plane, camera, wall/wire commands and canonical round trips in controlled tests. The live 3D scene renders; selection and workspace-only fullscreen/Escape preserve the no-unsaved-changes state. No real measured drawing was fabricated; arbitrary varying-elevation/sloped editing is not added. |
| Search / navigation / settings | PASS in committed frontend tests. Live device-ID search, independent wiring/wall queries, selected-wall 3D highlight, panel reopening and browser-preserving fullscreen were exercised without saved edits. |
| Project intake / lifecycle | PASS for nullable legacy fields, no-blueprint creation, phone/date/Other validation, concurrency, Trash/restore, cancelled late writes, original/review/estimate preservation. Previous disposable browser proof remains applicable; no real plan is removed. |
| Client pricing / estimate / export | PASS for CSV/XLSX safety, explicit mappings/pack units, project ownership, immutable versions, known totals, client/calculated quantity separation, historical estimates and CSV exports. Prior checkpoint-6 browser proof remains applicable because these source files are unchanged. PDF report generation is not present in the current API and is not established by this audit. |

The clean checkpoint snapshot passes all 847 frontend tests and full source
lint (zero errors/warnings), plus 1,041 backend tests and 356 subtests across 72
explicit feature modules. Two file-symlink checks are NOT TESTED on this host.
The backend selection deliberately excludes BDO recognition, annotation,
training/model evaluation and private-drawing tuning; it is not the full backend
suite. The broad gate exposed an omitted checkpoint-5B project OpenAPI
expectation; the four already-existing lifecycle operations were added to that
test. No production API/geometry change was needed for that failure.

The mixed live worktree is **FAIL**, not release-ready merely because the clean
snapshot passes: 1,020 backend tests pass and 21 fail due to the unrelated
uncommitted POST /bom/preview changing the expected 59-operation contract to
60. All 356 subtests pass; the same two symlink checks skip. Its complete
frontend run has 820 passing / 39 failing tests (859 total). Failures span the
changed viewport/sidebar, canvas/inspector controls and mocks, editor/viewer and
project table. Many assert removed controls; a saved-route provenance expectation
also remains unresolved and is not dismissed as cosmetic. Live source lint has
six errors in the untracked DeviceMeshCatalog.jsx (unused React import, mixed
exports and conditional hooks). That catalog is not imported by current source,
but must be corrected before integration. These unrelated edits were preserved,
not reverted, staged or silently made passing by changing expectations.

Both clean and mixed-live production builds pass with existing large-chunk
warnings; backend deprecation warnings remain. Runtime browser proof confirms a
rendered scene, not electrical approval or complete wiring recognition. No real
scale, elevation, review, estimate, upload or original is written. Database/table
contract remains 36 tables / 59 clean operations (60 mixed live); no schema
expansion in this audit. Original-file and data fingerprints, restricted verification
cleanup, preserved stash and scoped publication state are checked at handoff.
BDO detection/annotation/training remains paused. Reboot durability and complete
future-upload recognition are not established by these feature checks.
Both live analysis auto-start flags remain disabled, as at the prior checkpoint.
New live analysis requests can queue but will not be automatically consumed in
this state; automatic live upload-to-recognition is therefore PAUSED/NOT TESTED,
not counted as a working end-to-end feature. No real upload was submitted.

### Checkpoint 6 follow-up — Designer BOM pricing applies automatically (2026-10-20)

The Designer's existing Cost estimation import is now labelled **Upload BOM
pricing (XLSX or CSV)** and appears before the BOM. Existing bounded parsing,
explicit column/material mapping, conversion review, exclusions, confirmation,
version concurrency, source retention and idempotent retry are reused. Saving
an import automatically selects its version for the next estimate and refreshes
the live BOM. Opening the estimate page defaults to the latest confirmed import;
the Designer can explicitly choose the Admin catalog for a new snapshot. Valid
product, conversion and conductor choices survive repricing, with confirmation
cleared. A deliberate input reload still clears draft choices.

The backend planning BOM now uses the latest confirmed project price version
for existing, exact-identity material mappings. Quoted pack/roll prices are
normalized by the reviewed number of catalog units per quoted purchase unit.
No product, device-class binding, wire gauge/count, purchase length, scale,
elevation or engineering approval is inferred from a price file. Client quantities
remain comparison inputs, never substitutes for measured/count-derived quantities.
Existing explicit custom draft prices take precedence and retain custom provenance.
If a project import exists, unmatched or identity-changed products stay unpriced
instead of silently falling back to the Admin catalog. New catalog products still
require catalog administration; imports do not grant Designers global catalog writes.

Price provenance includes project version and source row IDs. Shared catalog
prices and historical estimate snapshots are unchanged. The latest quote lookup
loads one version and defers its original workbook bytes rather than reading every
historical import on each BOM request. No new endpoint, schema/table or dependency
is added: 59 clean operations / 36 tables; the unrelated live preview endpoint
still makes 60 operations in the mixed worktree. BDO remains paused; DWG stays
cancelled.

PASS: 70 backend tests covering pricing import, draft BOM, estimate snapshots,
unit conversion, exclusions, identity changes, missing measurements and zero-valued
custom overrides. PASS: 27 focused frontend/API tests and scoped source lint,
including default client selection, explicit catalog choice, preservation of valid
material choices, retry fencing and read-only Admin behavior. Clean production
build passes with existing bundle-size warnings. Full suites are not rerun here;
the mixed-worktree failures recorded above are not declared resolved.

Browser PASS in a disposable restricted-database project: upload the generated
five-row XLSX, map its columns and material identities, validate, confirm and save.
The next-estimate source changes automatically; live device price changes from
PHP 10 to 125, wire roll from PHP 10 to 3,000 and conduit length from PHP 10 to
120. Priced draft subtotal changes from PHP 26.864 to 389.104, retains the same
calculated quantities, and still exposes an unmeasured path as unpriced. Reload
retains the client prices and default version. The original saved estimate stays
PHP 26.864. These synthetic fixture mappings test software, not product suitability.
The temporary browser services and their exact synthetic records are removed.

The requested `VED-SYNTHETIC-Client-BOM-Pricing.xlsx` is saved to Downloads,
visually checked and previewed read-only against actual active catalog identities:
five valid mapped rows, no formulas, invented PHP prices clearly labelled synthetic.
Its client-quantity arithmetic totals PHP 11,200; this is test input, not a project
estimate or supplier quote. No real project import or price is saved during this
verification. All 35 existing table fingerprints, 44 uploaded files and stash@{0}
remain unchanged. Unrelated pending canvas/BOM preview edits are preserved and
excluded from the scoped checkpoint.

Workspace placement follow-up: the plan workspace BOM now exposes **Upload BOM
pricing** beside **Download draft BOM** for authenticated Designers. It opens the
same import component inline with its file controls expanded. Close/reopen retains
pending input; a confirmed import invalidates only the BOM price request, retaining
calculator choices and the canvas draft, viewport and undo state. Session role is
passed through the protected shell; backend Designer/ownership checks are unchanged.
The Cost estimation page retains its existing separate import without duplication.
PASS: 31 focused frontend tests, scoped lint and isolated production build (existing
large-chunk warnings). Browser PASS on the actual workspace: button visible, file
input opens, close/reopen works, editor remains “No unsaved changes.” No real import,
geometry save or backend mutation is performed. No backend/API/schema changes;
backend/full-suite gates are not rerun for this placement-only change. Unrelated
pending auth/canvas/BOM-preview edits and stash@{0} are excluded and preserved.

One-step pricing follow-up: choosing an XLSX/CSV now automatically recognizes and
applies project prices in both the workspace and Cost estimation import. The
normal UI no longer exposes worksheet/header/column mapping, material selectors,
preview, confirmation or save controls. History remains optional and read-only.
The upload action authorizes pricing application, not geometry or engineering
approval. Stored provenance records `automatic_exact_identity`.

Recognition scans the first 20 populated rows per worksheet for one pricing table
with known Description, Unit, Unit price and explicit Currency headers (currency
may instead appear in the price header). A supplied code must exactly identify an
active catalog product; without a code, a unique normalized exact description is
required. Purchase units must match the catalog: no fuzzy product selection,
pack/roll conversion, currency guessing or new catalog product is inferred.
Formulas, duplicates, unknown identities, incompatible units, ambiguous tables
and invalid amounts reject the whole upload with an actionable error. No partial
subset is silently applied. Client quantities remain separate from takeoff.

The existing preview/apply API is reused; manual API clients remain compatible.
Automatic matches are revalidated on apply, while project locking, version checks,
source fingerprints, retry identities and historical manual retry hashes remain
intact. Uncertain saves expose one retry action using the same request identity.
Designer/ownership authorization and immutable estimate snapshots are unchanged.
No new route, table, dependency, detection/model change or global price mutation.
BDO remains paused and DWG remains cancelled.

PASS: clean-snapshot 81 focused backend tests; 31 frontend/API tests; scoped source
lint; production build (existing large-chunk warnings). Full unrelated suites NOT
TESTED in this checkpoint; previously recorded unrelated failures are not claimed
resolved. Browser PASS: selecting the Downloads synthetic XLSX alone creates one
project import, changes live device/wire/conduit prices to PHP 125/3,000/120 and
draft priced subtotal from PHP 26.864 to 389.104, without changing quantities.
Reload retains pricing; the saved estimate remains PHP 26.864 and the unmeasured
path remains unpriced. These mappings validate software, not product suitability.
The disposable fixture records/services were removed. No real project price
version was created. All 44 previously checked original files remain byte-identical;
one newer upload and other newer project/job records exist since the older
integrity snapshot and were left untouched, not rolled back. No analysis job is
active. Unrelated edits and stash@{0} remain outside the scoped checkpoint.

### UX checkpoint 1 — existing-item client price assignments

An optional, initially collapsed **Apply client prices to selected items** panel
is shared by the workspace BOM and Cost estimation BOM. One-step file upload is
unchanged. Designers choose an immutable uploaded version and entry, search/filter
saved devices, conductor/cable items and conduit items, select compatible targets,
preview old/new unit prices and totals, then apply atomically. Floor/project scope
is explicit. Apply-all wiring is resolved by the server and reports incompatible
or unresolved products/units; it never changes gauge, circuit, conductor count,
material binding, geometry or quantities. Unsaved canvas edits disable assignment.

The add-only `item_price_assignments` table stores actor, time, idempotent request,
preview fingerprint, application audit and cumulative existing identity choices.
Existing canonical device identities, candidate/page identities and explicit
connected path-group identities remain distinct. Reanalysis candidates and future
items do not inherit a prior bulk selection. A new saved route is also a new
identity, not an implicit pricing default. Current material identities/conversions
are revalidated; stale assignments are unpriced with an actionable reason rather
than silently replaced with another price. No default-rule feature is enabled.

Project/floor locks, scope and source-revision fingerprints fence concurrent
changes. An uncertain response retries the same request. The shared BOM resolves
overrides from the referenced client version; newly generated estimates capture
applicable item prices and their provenance. Historical estimates/imports and the
Admin catalog are immutable. Floor BOMs now reuse saved bindings from the same
current measured route; an aggregate multi-floor quantity is never allocated to a
single floor by guess. Unclassified/unmapped/unmeasured paths stay unresolved;
applying a price does not turn them into measured purchase quantities or approval.

PASS: clean checkpoint snapshot, 88 backend tests, 35 frontend/API tests, scoped
lint and production build (existing large-chunk warnings; two backend deprecation
warnings). Tests cover compatible multi-item pricing, scope/tampering, different
products/units, stale previews, retry, new-device/new-candidate identity, unchanged
geometry, project/floor BOM equality, immutable history and new estimate capture.
Full unrelated suites NOT TESTED; earlier unrelated failures are not resolved by
this checkpoint. Browser PASS in the restricted disposable database: select two
devices from client version 1 rather than latest version 2; each changes from PHP
250 to 125. Draft priced subtotal changes from PHP 778.208 to 528.208. Apply-all
for one floor changes only the compatible wire roll from PHP 6,000 to 3,000,
skipping conduit and an unresolved path; subtotal becomes PHP 469.108. Reload
retains the choices and the old estimate remains PHP 26.864. Synthetic bindings
test software, not engineering/product suitability. Fixture services and exact
synthetic records are removed; no real assignment/import is created.

Three new API operations reuse the existing project-pricing router (62 operations
in the clean checkpoint; 63 in the mixed worktree) and one additive table (37).
Deployment verified all 36 pre-existing table counts/checksums unchanged. Originals,
unrelated pending edits and stash@{0} are preserved. BDO remains paused. This
checkpoint does not implement UX checkpoints 2–5 (deletion, Add Device search,
3D gestures, compact Plan Information); those remain separate responsibilities.

### UX checkpoint 2 — active-view deletion

Rejected items remain only in draft/save history for undo and audit. The 2D wall
loop now excludes them before creating stroke/hit nodes, matching the existing
3D draft builder. Object search, counts, the all-item selector and numeric wiring
editor exclude deleted records and expose no restore/deletion markers. Mutations
clear deleted selections, and stale selections cannot open their properties.
Undo/redo restores the prior complete snapshot rather than editing tombstones.

Numeric wire removal now uses the same junction-aware commands as canvas edits,
clearing orphaned junction contacts while preserving surviving branches. Device
detachment retains other devices/paths and invalidates affected generated proposal
assignments. An explicit **Keep devices in place & delete wall** action clears
mounting-wall bindings without moving/deleting devices or changing wire geometry;
openings still require reassignment before wall deletion. Unsaved edits visibly
separate saved BOM data (or identify a live preview when that pending feature is
present); deleted entities are already excluded by the shared server takeoff.

PASS: clean checkpoint 128 frontend tests (2D/3D filtering, search, junctions,
device dependencies, mounting, undo/redo and reload), 67 backend tests (review
persistence, inherited deletions, BOM and pricing), scoped lint and build.
The obsolete schema/operation-count assertion is updated for checkpoint 1's 37
tables/62 operations; mixed worktree has the separate uncommitted 63rd operation.
Build retains existing chunk warnings; Konva DOM test doubles emit known prop
warnings and backend tests emit two deprecations. Full unrelated suites NOT TESTED.
Browser PASS in a disposable synthetic project: delete one of two devices, see
one active search item and BOM quantity one; undo restores both, redo removes it,
save/reload retains removal. Delete a wall, see four active walls instead of five,
no stale inspector, and verify the synchronized 3D scene. Browser wire deletion
and mounted-wall deletion NOT TESTED; those have focused command/API tests.
No backend schema/route change in this checkpoint; originals, historical versions,
unrelated edits and stash are preserved. BDO remains paused. Checkpoints 3–5 are
not part of this deletion checkpoint.

### UX checkpoint 3 — searchable Add Device picker

Add Device now searches the approved, active placement choices, separately from
placed-object search. Display names, existing alias records, family/type text,
class codes and supplied catalog-code/specification metadata are searchable;
gang/outlet distinctions remain visible in the full description. The current
legend API exposes ID/class/name only, so absent catalog-code or semantic-alias
metadata is not invented. Existing source-tag aliases and their exact selected
record IDs are retained. Wiring legends, annotations and inactive entries remain
unavailable. Search never rewrites a class or adds catalog data.

The compact native list supports keyboard navigation: Down transfers focus from
search, arrows choose, Enter returns to pointer-follow placement and Escape
cancels. Clear and empty-result states are explicit. Filtering does not silently
change the pending selected class. The existing canvas magnet/placement/save
commands are reused unchanged. Styling follows the existing workspace tokens.

PASS: 67 focused frontend tests, scoped lint and clean build; existing Konva DOM
double and chunk-size warnings remain. Browser PASS: search approved entries,
choose by keyboard, click to place, save revision 3 and reload the same named
manual device. Alias/variant/inactive edge cases have component tests, not an
independent catalog-quality evaluation. Backend/full suites NOT TESTED again for
this frontend-only checkpoint. No route/table change (62/37 clean; mixed API 63).
Originals, unrelated edits and stash are preserved; BDO remains paused. The
synthetic fixture remains active only for the following 3D gesture checks.

### UX checkpoint 4 — separate 3D selection, orbit and movement

Normal Select uses a five-screen-pixel click tolerance: a click selects, a left
drag orbits and never selects on release. The gesture tracks maximum displacement,
pointer cancellation, capture loss, outside release and multiple pointers.
Move selected in 3D explicitly enables device dragging and wire handles. Drawing
reserves the left button; middle-drag orbit, right-drag pan and wheel zoom remain
available. Escape/blur cancel object previews without committing coordinates.
Switching back to 2D resets the 3D-only Move tool. Wall selection shares the
existing inspector; this does not introduce 3D wall translation.

PASS: 73 focused frontend tests, scoped lint and clean build (existing chunk
warnings). Browser PASS: dragging directly on a selected device orbits without
changing coordinates/save state; clicking a wall selects it; explicit Move changes
the device coordinates with a stationary camera; Undo restores the exact position.
Workspace expansion and Escape exit PASS with inspector closed. An open floating
inspector can obscure the expansion button in the pending canvas-first layout;
this layout overlap is carried into checkpoint 5, not reported as a passing gate.
Physical touch and right/middle hardware gestures NOT TESTED in browser; mapping,
multi-pointer and cancellation events have focused tests. Backend/full unrelated
suites NOT TESTED again: no API/schema change (62 operations/37 tables clean).
Originals, history, unrelated work and stash remain preserved. BDO remains paused.

### UX checkpoint 5 — compact optional plan information

Plan Information is a small, initially closed, keyboard-accessible control.
Diagnostics, recovery statistics, source-view controls and limitations remain
available only on request. Escape closes the panel and restores trigger focus.
The 3D preview removes its default connected-device summary and repeated editing
paragraphs. Illustrative dimensions and their measurement caveat are in optional
3D settings; camera instructions are in optional Camera help. Selected detection
provenance is collapsed, while an assumed switch class still has a concise
correction action. Identity, tools, view controls, save/unsaved state, actionable
errors and measured-operation gates remain unchanged. No approval is inferred.

The existing floating inspector now leaves a bottom control strip clear, resolving
checkpoint 4's covered fullscreen button. Canvas-first workspace expansion uses
the full viewport height rather than the legacy 200-pixel header deduction;
Plan Information remains reachable above the expanded frame. Styling reuses the
existing tokens and original workspace palette under either theme preference.

PASS: 52 focused clean-checkpoint frontend tests, scoped lint and production
build; 29 focused live-worktree integration tests. Browser PASS on the disposable
synthetic project: initially collapsed diagnostics; Enter opens and Escape closes
information; optional settings/help; unchanged save state and source geometry;
light/dark preferences (original System preference restored); fullscreen with an
open inspector and a 720-pixel canvas in a 720-pixel viewport. Physical touch
hardware and the full unrelated suites remain NOT TESTED. Existing chunk-size
warnings remain; no dependency, API, schema, detector or approval change.

Final combined gates PASS: 128 focused frontend tests across pricing, deletion,
search, topology, 3D gestures and compact information; 138 isolated backend tests
across item/project pricing, material import, BOM, historical estimate snapshots,
review persistence and observed-wire review. Backend emits two existing
deprecations. The verification database is empty again except reference roles;
only the exact disposable fixture and its temporary servers/tab were removed.
No real item-price assignment was applied. Live schema remains 37 tables; clean
OpenAPI remains 62 operations (mixed worktree has the separate pending 63rd).
All 44 originals in the earlier integrity baseline retain identical bytes; a
newer 45th original and concurrent user-created project/pricing records remain
untouched. Historical table fingerprints differ only in those newer workflow
records; this is not represented as an unchanged whole-database snapshot.
Stash remains bb78854e87833124a1725b51f0be6099a8ac0cfa.

All five authorized UX responsibilities are now implemented and separately
verified. BDO detection/training remains paused. No further roadmap work started.

### Wiring BOM follow-up — paired components and precise measurement gaps

The Designer now specifies that every wiring path carries conduit. Planning
takeoff therefore returns wire/cable and conduit components for every existing
physical path/network, sharing horizontal and supported vertical geometry.
This is a BOM policy, not newly detected source geometry or an electrical-code
claim. Products, gauges/sizes, units and captured prices remain distinct. Cable
route metres are not an invented conductor count. Existing saved circuit purchase
quantities/conversions remain untouched; explicit product choices replace their
component rather than appending another copy. Both workspace and project BOM use
the same backend. The item-type filter is Devices or Wiring paths (plus All),
and Wiring paths includes both material components.

Device attachment and measurement were being conflated in feedback. A 2D source
contact does not establish device mounting height, absolute service elevation or
floor reference. Drop/rise still uses saved service elevation minus (saved floor
elevation + mounting height), with absolute length. Missing-input notes now name
only absent values; a matched material identity is retained even when vertical
measurement is incomplete. The previous early return hid that identity and made
some valid matches look like unresolved specifications. Incomplete lengths remain
excluded from complete costs, and unsupported inter-floor edges are not labelled
as connected devices. Product/size mismatches and missing product mappings now
have separate pricing explanations. Wire gauge, conductor count, conduit size
and heights are not inferred merely from a visible stroke.

Wire/conduit item keys are component-specific to prevent collisions on the same
path. Older shared-key assignments are read only for their matching product and
fingerprint; historical assignment records and estimate snapshots are not rewritten.

PASS: 90 isolated backend regressions (paired geometry/drops, idempotency, product
selection, unit safety, legacy price bindings, permissions, BOM API/reload and
historical estimate snapshots); 16 focused frontend tests, scoped lint and build
with VITE_AUTH_ENABLED=true. Existing chunk-size and two backend deprecation
warnings remain. Browser PASS on a disposable synthetic saved review: Wiring
paths shows both components at the same 0.4 m route length; connected-drop details
identify only the missing device mounting height; reload retains both components
without inventing a vertical distance or price. This is not a new detection-quality
evaluation. The fixture/tab/servers were removed and test data cleaned. Full
unrelated suites and the user's particular live drawing are NOT TESTED in this
follow-up. No schema/API, model, approval or live-project data writes. Clean schema
and operations remain 37/62 (mixed worktree retains the pending 63rd operation).
All 44 baseline originals remain byte-identical; the newer 45th original and two
concurrent real pricing imports are preserved. Unrelated edits and stash remain
untouched; BDO remains paused. Missing real measurements and unassigned product
specifications remain explicit limitations, not automatically resolved inputs.

### Authorized workspace sequence — integrated pricing through dashboard

Start: branch codex/vlm-localization-experiment, HEAD 99ba8f5 verified present.
Six new checkpoints are authorized: integrated BOM upload/selection and delivered
synthetic fixtures; calibration and VED mounting defaults; numeric dimensions and
angles; copy/paste; approved glyph/product inspector; stored-data dashboard.
Checkpoint 1 inspection found two separate pricing tables and immediate import
application. Next: reuse parsing/preview/versioned assignments while moving item
selection into the existing BOM table, with explicit item-only import usage and
atomic multi-product assignments. No checkpoint in this sequence is complete yet.
Confirmed heights are outlet 0.30 m and switch 1.20 m above finished floor,
measured to device center (user clarification). Service/floor
elevations, conductor counts, sizes and scale remain independent inputs.
Autodesk Set Scale or Calibrate confirms known-distance, sheet-specific calibration
(https://help.autodesk.com/cloudhelp/ENU/Takeoff-Takeoff/files/Set_Scale.html).
The supplied Quezon City PDF could not be fetched by the web reader (49 MB);
it is not used as evidence for universal mounting rules. No private data uploaded.
BDO remains paused. All pre-existing dirty CV/auth/editor files and stash must be
preserved. The ignored clean checkpoint mirror remains the verification/staging
surface for overlapping files; do not commit unrelated live-preview/UI changes.

#### Checkpoint 1 — integrated existing-item prices (verified)

PASS: Upload BOM in the shared workspace/Cost BOM opens a source-price preview,
then selection controls in the SAME BOM table. Devices retain individual stable
identities; each wiring row groups wire/cable and conduit. Search, All/Devices/
Wiring paths, select-visible/clear, explicit floor/project scope, compatible
product suggestions, per-item choices, price-change/skipped previews and atomic
multi-product application reuse the existing parser/version/assignment services.
Finish/Cancel leaves applied prices intact; uncertain writes retry identically,
while definite stale-input rejection allows a fresh preview or cancellation.

New item-selection quote versions do not replace project-wide defaults. Application
binds existing item keys only; no new database table, endpoint, catalog update,
client-quantity substitution or estimate-history rewrite. Explicit quote-to-catalog
conversions support rolls/stock lengths. Conservative checks reject conflicting
family, known gauge/core count, material, conduit size and unit. Unknown product
specifications require an explicit compatible selection, not guessed sizing.
Missing route measurements remain uncosted. Aggregate device cost is divided with
quantity when expanding per-device selection rows (previously repeated the whole
group cost in each previous-price preview).

Delivered synthetic-only files: frontend/public/fixtures/ved-synthetic-pricing.xlsx,
fixtures/synthetic_pricing.json, backend/tests/synthetic_pricing.py and
scripts/serve_synthetic_pricing_fixture.py. The workbook contains valid and explicit
duplicate/missing/ambiguous/incompatible examples, plus independently calculated
expectations. It was authored, recalculated and visually checked with the bundled
spreadsheet runtime. Local fixture CLI refuses non-restricted/nonempty databases,
binds localhost:8001 with a test identity, disables workers and removes exact fixture
IDs on Ctrl+C. Run it with TEST_DATABASE_URL for ved_test/ved_electrical_verify;
run frontend on 127.0.0.1:5174 with VITE_AUTH_ENABLED=true and
VITE_API_BASE_URL=http://127.0.0.1:8001. Open the printed URL; upload the workbook,
exclude Client prices rows 10–13, Check mappings, then Use imported prices.
Select devices and the JSON's path products, preview/apply and reload.

PASS expected = API actual = browser-reloaded actual: PHP 980 (devices 240;
14 m path wire/conduit 168+350; 6 m path cable/conduit 72+150). Client quantities
999 never replace measured quantities. Browser exercised source rejection reasons,
saved-list resume after interruption, device selection, paired product choices,
project-wide existing-wiring application, Finish and reload. Proof screenshot:
tmp/ux-checkpoints/integrated-pricing-reloaded.png (ignored diagnostic artifact).
Browser fixture/tab/servers removed; verification preflight confirms empty test
data tables. A test-harness shared-session concurrency failure was corrected with
independent request sessions; it was not a production pricing defect.

PASS focused clean-snapshot gates: 89 backend tests (integrated/item/project pricing,
estimates and draft BOM); 38 frontend tests (BOM/estimate/legacy pricing and
interruption/retry/project switching); scoped lint; authenticated frontend build.
Existing two backend deprecation and build chunk-size warnings remain. Full unrelated
suites and live client-drawing browser pricing are NOT TESTED; synthetic pricing
does not establish electrical approval. Shared workspace component is covered in
UI tests; full canvas-browser integration is NOT TESTED in this checkpoint.
Clean schema/API remain 37 tables / 62 operations. Integrity check: all 44 baseline
originals byte-identical; 45 current originals, two real price imports and subsequent
concurrent project/job records preserved; no active analysis jobs. Unrelated dirty
files and stash@{0} bb78854e87833124a1725b51f0be6099a8ac0cfa preserved. BDO paused.

Relevant modules: project_pricing API/schema/model/repository/service/auto parser;
item_pricing schema/service; product_compatibility; frontend pricing APIs,
BOMPanel/BOMTable/BOMPricingControls/useBOMPricing/bomPricingRows, EstimatePage and
clientPricing.css; focused tests and synthetic fixtures above. Stage overlapping
BOMPanel only from tmp/ux-checkpoints/clean, not the dirty root live-preview edits.
Next: checkpoint 2 inspection of calibration/upload metadata and mounting/terminal
defaults. Checkpoints 2–6 have not started; do not claim those features complete.

Checkpoint 1 committed as 9449a44 on codex/vlm-localization-experiment. Checkpoint 2
has now started (not complete): mounting defaults/reference implementation is in
the root and ignored clean mirror. Backend supplies the VED policy; mapped outlet/
switch drafts acquire center-referenced 0.30/1.20 m defaults only when no override
or conflicting reference exists. Explicit old heights remain unchanged, including
unspecified historical references. Terminal offsets are separate; absent offsets
mean the declared reference endpoint, not a manufacturer terminal measurement.
Review persistence, draft BOM, canonical publication and 3D placement share this
meaning. Optional reference/offset metadata uses canonical extension v7; v2–v6
round trips remain unchanged. No historical file/review is rewritten.

Initial focused backend run: 70 passed / two new assertion-type failures; fixed
Decimal-vs-float test comparison. Subsequent run: 73 PASS, including review and
canonical save/reload, 3 m service -> 2.7 m outlet / 1.8 m switch, offset handling
and shared v7 fixture rejection. Focused frontend run: 114 PASS before the final
shared-v7 fixture assertion was added; final lint/re-run pending. Mounting browser
verification, full calibration/upload/paper/orientation/ceiling-service settings,
checkpoint-2 build and publication are still NOT TESTED / unfinished. Preserve
uncommitted mounting work in device_mounting/deviceMounting, demo review schema/
service/Page, draft_bom_service, observed_connections, canonical extension Python/JS,
devicePresentation/clipboard/draftRoomScene/devicePlacement, tests and v7 fixture.
Continue with the pending focused frontend result and browser mounting proof, then
the remaining checkpoint-2 measurement settings. Checkpoints 3–6 not started.

Mounting sub-checkpoint 2a gate: 109 backend PASS (mounting, canonical extension,
observed/canonical contacts, measurement, interpretation API, BOM and item pricing);
115 focused frontend PASS; scoped lint and authenticated build PASS. Expanded
gate found a stale pre-existing 36-table assertion (actual schema already 37 from
item assignments), corrected to 37, and a new legacy-reference/offset canonical
case missing connection metadata, fixed before the final passing run. Neither
failure was skipped. Existing deprecation/chunk-size warnings remain.
Browser PASS: disposable synthetic outlet shows 0.30 m center default and separate
+0.10 m offset. Changing center height to 0.50 m, saving and reloading retains both
values; at 3.0 m service elevation BOM shows 2.40 m drop + 0.40 m horizontal =
2.80 m for both components. Proof tmp/ux-checkpoints/mounting-reference-reloaded.png.
Visual 3D BLOCKED: browser cannot create WebGL. Numeric shared 3D projection and
canonical contract tests PASS; no rendered-3D claim. Synthetic fixture/tab/servers
removed; subsequent isolated preflight passed. No models, original files, historical
reviews or real project data changed; schema/API remain 37/62; stash unchanged.
This is a bounded mounting sub-checkpoint, not completion of checkpoint 2. Upload
paper/orientation/scale metadata, separate floor/ceiling/service settings and their
remaining integration/calibration proofs are next; checkpoints 3–6 remain open.

Sub-checkpoint 2a committed as f286522 (branch unchanged). Checkpoint 2b backend
draft is UNCOMMITTED: new PlanMeasurementSetting append-only model/repository,
plan_measurement schema/service, models registration, floor_plan upload/storage
integration, GET/PUT measurement-settings routes and test_plan_measurement_settings.
Four isolated tests PASS: per-PDF-page paper/crop/rotation metadata preservation;
raster A1/nominal-100 defaults without calibration; revisions/retries/authorization
and independent floor/ceiling/service fields without touching approved scales;
normal upload storage preserves byte-identical original while storing metadata
atomically. Legacy upload calls omit the new optional arguments. Frontend for 2b,
configured-height consumers, broader new-schema regressions and live multipart
browser flow have NOT started / NOT TESTED. New modeled surface is 38 tables and
64 operations; previously committed 2a surface remains 37/62. Do not publish 2b as
complete or treat its four focused tests as a full regression gate. Existing count
assertions must be aligned with the expanded schema/API when finishing 2b.

Live provisioning BLOCKED: read-only SHOW GRANTS check confirms configured
application account has NO CREATE permission, consistent with authorized CRUD-only
access. Do not grant it DDL or use guessed administrator credentials. The new table
exists only in ved_electrical_verify so far. Obtain an approved administrator-run
prototype schema initialization for ONLY plan_measurement_settings before wiring
live UI to it. No live schema or permission change was attempted. Existing upload/
editor behavior does not query this draft table; new inputs are opt-in and no 2b UI
is deployed. Next: administrator provisioning decision, then 2b UI/persistence/
calibration integration and gates. Preserve this backend draft and all unrelated
dirty files; BDO still paused, recovery stash untouched.

2026-10-21 continuation — bounded 2b backend foundation, not checkpoint-2 completion.
Verified HEAD f286522 on codex/vlm-localization-experiment before editing. Live
read-only recheck: plan_measurement_settings remains absent; ved_app has no CREATE;
no administrator database connection is configured. No grants or live schema were
changed. Legacy uploads still omit the optional measurement input and never query
the new table. UI and routing/default consumers remain unimplemented; do not enable
them or advertise paper/nominal ratio as calibrated metric geometry.

Hardened the backend draft: save/retry returns the current floor datum consistently;
read-only GET no longer commits; revision/retry reads use current locking reads to
avoid stale MySQL REPEATABLE READ snapshots. Uploads that explicitly change floor
datum acquire the parent lock before their child FK insert. Added real multipart
upload/reload, invalid-input no-write, sanitized failure/atomic rollback, legacy
upload compatibility, append-only history/default preservation, and two-session
stale-snapshot/retry tests. Only allocated verification fixture IDs are cleaned up.
Scoped files: plan_measurement model/schema/repository/service, models registration,
floor_plans routes, floor_plan_upload/storage, test_plan_measurement_settings, and
schema/API assertions in analysis_settings/canonical_extension/demo_interpretation
tests. Existing ledger only; no UI, model weights or detection code changed here.

Final clean-snapshot gate PASS: 187 backend tests + 23 subtests across measurement,
upload/storage, approved analysis settings, mounting, canonical geometry/contacts,
observed-route measurements, interpretation, draft BOM and integrated/item pricing.
Nine tests are specific to plan measurements. Initial broader run FAIL: stale
36-table/59-operation assertion; aligned assertions with the actual 38-table/64-
operation modeled surface, then reran. One intermediate selection named a nonexistent
test file and ran no tests; corrected selection passed. Existing two test-client
deprecation warnings remain. Live schema remains 37 tables. Browser/full frontend
build NOT TESTED this backend-only sub-checkpoint; no new measurement UI deployed.

Integrity PASS: all 44 baseline original files byte-identical (45 current files),
two real project price imports retained, zero active analysis jobs. Historical
baseline table fingerprints differ from earlier concurrent/user additions; do not
claim every table is unchanged. This work writes only the restricted verification
database. Recovery stash still bb78854e87833124a1725b51f0be6099a8ac0cfa; unrelated
dirty files preserved; BDO remains paused. No temporary servers/tabs started.

Next dependency remains administrator provisioning of ONLY plan_measurement_settings
using an approved private administrator connection to the existing development
ved_electrical database. Keep ved_app CRUD-only and ved_test verification-only;
never try guessed credentials. Administrator may use the existing registered model
and SQLAlchemy table.create(checkfirst=True), not broad schema repair/reset. After
provisioning: finish 2b upload/edit UI, per-page calibration provenance and configured
height/service consumers, then browser/reload and shared measurement gates. Checkpoint
2 as a whole and checkpoints 3–6 are NOT complete; no later UI work started here.

2026-10-21 client-pricing revision (base 37135c6, same branch): user superseded the
CP1 preview/select/apply UX. Upload BOM now calls one atomic POST client-pricing/
automatic with file, explicit current-floor/project scope and stable retry ID.
No catalog-registration/mapping, selection, confirmation or review UI. Client
products/prices live in existing project quote/assignment JSON and source bytes;
VED catalog prices are not compared or changed. Match supported device families
and explicit ratings, plus each existing path's separate wire/conduit component.
One compatible client product is selected automatically; multiple compatible
products, incompatible specs, conflicting duplicate codes, missing literal prices
or purchase conversions are skipped with concise reasons, not a blocking review.
Exact duplicate rows are retained once. Explicit roll/stock conversions are used;
client quantities (including unevaluated reference formulas) never replace takeoff.
Unscaled/missing-drop/circuit inputs remain incomplete, even with an assigned price.

Shared BOM UI replaces mapping/selection steps with upload status and optional
unmatched details; manual material/measurement overrides are collapsed by default.
Client product descriptions appear in the table and draft CSV. Saved, compatible
route estimates capture client prices/names without rewriting historical snapshots.
This is pricing only, not geometry approval, electrical sizing or payment handling.
Existing item identities only; no implicit pricing defaults for future devices.

Scoped code: automatic_client_pricing service; shared table-header recognition;
project_pricing route/schema/service, item-price repository/service, product
compatibility, estimate_service, the narrow CSV change in bom_service; frontend
projectPricing API, useBOMPricing, BOMPricingControls, BOMTable, and narrow BOMPanel
changes. Tests: automatic-client service/API, pricing API/hook/BOM panel and two
OpenAPI count assertions. No dependency/model/table or live-grant change. Clean
surface: 38 modeled tables unchanged, 65 operations (one added automatic operation).

PASS: 132 focused backend tests + 15 subtests; 43 frontend tests; scoped ESLint;
authenticated Vite build. Existing test-client deprecations/chunk warnings remain.
Earlier checks caught a generic synthetic fixture with no recognizable product
type, removed initial legacy-version loading (restored), an asynchronous table
refresh assertion (awaited), and API tests run without their expected base URL
(reran with explicit localhost:8000). No failed gate was skipped.
PASS browser, disposable fixture only: one CSV choice automatically prices 3 devices
and 4 wiring components, PHP 980 expected/actual, retained after reload; no mapping,
selection or Apply step. XLSX and CSV both pass the real multipart API workflow
with every VED product inactive. Proof tmp/ux-checkpoints/automatic-client-pricing-
full.png; previous viewport proof automatic-client-pricing-reloaded.png. Full
canvas browser workflow NOT TESTED; shared workspace BOM covered by component test.

Interrupted helper shutdown left only verification fixture records. Final isolation
preflight refused to run; exact project/floor/plan/user/material IDs were validated
and removed by ignored cleanup-automatic-pricing-fixture.py, then the 132-test run
passed. No test fixtures remain; temporary servers/tab stopped. All 44 baseline
originals are byte-identical (45 current). Live quotes now total four, reflecting
changes since the older baseline; do not claim a globally unchanged database.
This work's writes used only ved_electrical_verify; live OpenAPI read confirms the
new automatic route loaded. Recovery stash bb78854e87833124a1725b51f0be6099a8ac0cfa
preserved, unrelated dirty work excluded, BDO paused. Prior measurement-table
provisioning dependency is unrelated and remains unresolved; no measurement UI or
later checkpoint work was resumed here.

2026-10-21 conduit pricing follow-up (base 651a891): supplied synthetic workbook
contains PVC PHP25/metre and EMT PHP75/3 metres. Both parsed successfully; distinct
compatible products previously caused the conduit price to be skipped. Resolve an
exactly equivalent rate/currency/unit without choosing a physical product. Retain
all source alternatives and price-only provenance; conflicting rates/specifications
remain unresolved. Existing skipped identities can derive the common rate on reload
without changing the immutable upload/assignment history, inheriting future-item
defaults, or overriding explicit assignments. Floor-scoped imports stay isolated.
New uploads persist the equivalent-rate source IDs; estimates capture those rates
and alternatives while historical estimates remain unchanged. Missing calibration/
vertical measurements still prevent complete totals; no fabricated metres.

PASS: 108 clean-snapshot backend pricing, BOM and estimate tests, including equal
rates, exact conversion/currency checks, old-file reload with no writes, future-item
exclusion, floor scope and captured estimate provenance. An initial additional test
used a nonexistent floor_number fixture field (107 pass/1 fail); corrected to the
existing sort_order field and reran the complete selection successfully. Existing
two test-client deprecation warnings remain. PASS live read-only browser: 37 conduit
rows show PHP25/metre, retained after reload; wire quote remains PHP12/metre. No new
upload, geometry correction, review or approval was performed. Main project imports
have concurrent additions; no claim of a globally unchanged database. All 44 baseline
originals remain byte-identical (45 current). No frontend source/API/schema/table
changes in this pricing follow-up; full frontend gate NOT RERUN. Recovery stash
bb78854e87833124a1725b51f0be6099a8ac0cfa and unrelated dirty work preserved. BDO paused.

Latest attached sequence re-read: automatic pricing supersedes the old manual
preview/select steps. Next is the unfinished measurement input/calibration scope;
do not repeat completed pricing or mounting defaults. Checkpoints 3–6 remain open.

Conduit follow-up committed as 796bdd1. User will have the administrator create
plan_measurement_settings; no application grants or schema changes made by this
agent. Copy/paste pointer-placement follow-up began (63 focused frontend tests
passed), but user explicitly reprioritized compact BOM first. Preserve root edits
in useDeviceClipboard, its test, DemoInterpretationPage, its test and canvas; these
are NOT included in the BOM checkpoint and are not advertised as checkpoint-4
completion. The clean BOM verification/staging mirror excludes those pending edits.

2026-10-21 prioritized compact BOM (base 796bdd1, same branch): backend read model
groups matching purchase components after pricing, sums existing quantities/costs
with Decimal, and retains scoped symbol/path reference members. Separate class,
product/specification, rate, currency, units, measurement state and observed/
generated provenance remain separate. No circuits, geometry, attachments, saved
assignments or physical spans are merged. Both wire/cable and conduit remain
components of a wiring group. Detailed existing items/CSV and historical snapshots
are unchanged. Additive planning.display_groups; no API operation or table added.

Shared workspace/cost table uses compact reference-only symbol/path dropdowns,
combined row costs and an always-present Total/partial-subtotal footer. Unknown
amounts remain a dash, never zero or a fabricated full project total; currencies
stay separate. Removed calculation-basis, connected-drop details, catalog/quote
paragraphs, override/calibration calculator dropdowns and repeated processing text
from the normal BOM. Retain upload/download, unsaved changes, upload failure/retry,
and one small incomplete-price/measurement warning. Underlying diagnostics remain
in backend response/export data. Design skill guidance influenced compact spacing,
semantic controls, existing theme tokens and keyboard-readable reference dropdowns.

PASS final BOM-only clean snapshot: 111 backend tests; 35 frontend tests; scoped
ESLint; authenticated production build. Real CSV/XLSX upload fixtures retain PHP980
expected/actual, grouped-cost sum equality and grouped save/reload equality with
VED products inactive. Initial grouping edge case exposed duplicate component-kind
buckets (fixed); old UI tests expected explicitly removed controls (updated to the
new acceptance); two added API assertions initially summed JSON decimal strings
without conversion (corrected). All final gates rerun and passing. Existing two
test-client deprecations and large Vite chunks remain; full repository suite NOT
RUN. No changes to model weights/detection or engineering approval.

PASS read-only live browser: cost page 10 grouped rows rather than per-device
rows, working reference selector; workspace 6 groups, zero details dropdowns,
visible Total and one small warning. Workspace text identical after reload. Current
plan lacks applicable prices/measurements, so its Total is honestly unavailable,
not a claimed measured amount. Proof: tmp/ux-checkpoints/compact-grouped-bom.png
and compact-bom-total.png. Browser did not upload, edit, save or approve real data.
All 44 baseline originals byte-identical (45 current), zero active analysis jobs;
concurrent main-database additions are preserved, not claimed globally unchanged.
Only verification fixtures written by tests; no temporary servers started. Recovery
stash bb78854e87833124a1725b51f0be6099a8ac0cfa retained. Stage overlapping bom_service
and BOMPanel ONLY from the clean mirror, excluding earlier live-preview work.
BDO-specific work paused. Next: administrator provisioning, then measurement UI/
calibration integration; independent copy/paste work remains preserved unfinished.

### 2026-10-21 — Known-cost subtotals and individual price editing

Checkpoint based on 5817779, branch codex/vlm-localization-experiment. Backend
known-cost totals now always expose separate devices/conduit/cable subtotals per
currency and a partial total so far. Unknown line costs remain null, not free.
Edit prices opens a compact searchable individual-item dialog, validates units,
currency and prices server-side, saves immutable project overrides atomically,
checks stale versions and retries idempotently. Catalog/geometry/historical
estimates are unchanged. Design guidance influenced the on-demand dialog, existing
theme tokens, keyboard controls and compact rows rather than another default panel.

Fixed generic number-word gang and fixture lamp-count compatibility. Delivered
updated frontend/public/fixtures/ved-synthetic-pricing.xlsx and copied it to the
same Downloads filename; previous bytes retained in ignored workbook backup.
Synthetic lighting devices: 4 single40W + 16 twin40W + 6 one-gang + 3 two-gang =
PHP14445; with synthetic measured paths, conduit500 + cable240 = PHP15185.
Original independent workbook fixture remains PHP980. No live client prices imported.

PASS: 51 focused backend tests; 14 frontend tests; scoped ESLint; authenticated
production build. Real multipart workbook upload, pricing/reload, zero prices,
authorization, conflict/retry and historical snapshots exercised in isolated DB.
PASS browser isolated fixture: one device100→15, total280→195, remaining items
unchanged, partial subtotals visible; reload/editor reopen retained15. Proof in
tmp/ux-checkpoints/individual-prices-editor.jpg and individual-prices-persisted.jpg.
Test identity helper interrupted during Ctrl+C; exact validated fixture IDs were
removed, verification tables empty. No live records targeted. Full suite NOT RUN;
test-client deprecations and large Vite chunks unchanged. API66 operations,
38 modeled tables, no new table. Recovery stash and unrelated edits preserved.

Next started: user-confirmed A1/1:100 draft policy, preserve saved calibration and
reliable page metadata; charge known horizontal lengths while missing elevations
remain partial. This policy is not engineering approval. Measurement settings table
provisioning remains administrator-owned; no DDL or grants on the live database.

### 2026-10-21 — VED nominal page scale and partial wiring costs

Based on pricing commit f7a6e5c, same branch. User confirmed A1 + 1:100 for VED
draft blueprints. Added a shared, read-only scale resolver for editor routing
context and BOM: saved calibration first; otherwise reliable PDF page dimensions
and stored input settings precede A1/100 defaults. One isotropic factor, 2% aspect
tolerance; stale calibration, known crop/multiple-view warnings, mismatched paper
or unavailable PDF metadata do not silently fall back. Rotation/resizing preserve
metric lengths. Paper inference cannot prove that an image is a full sheet or
that every view uses the nominal ratio; this remains explicit nominal provenance,
not approval. Known-distance calibration remains preferred when mapping is
unreliable (Autodesk Set Scale or Calibrate reference previously supplied).

Automatic draft takeoff already accepted active partial source traces. Removed
the optional completeness selector, preserving stored completeness and uncertainty.
Price known horizontal/available vertical lengths even if other drops are missing;
retain partial flags, exclude unknown drops and block incomplete manual/client
quotes from final estimates. No guessed service elevation, gauge or allowance.
Shared 3D source-space paths use the same factor, CSV includes scale provenance,
and normal BOM retains one concise warning. Even wholly unpriced BOMs show zero
known-cost subtotals/total so far without inventing a currency or zeroing unknown
line costs. Unknown line costs stay null. Generic 3D skill examples do not define
new project engineering defaults.

PASS: 128 backend tests, 15 subtests; 31 UI tests; scoped ESLint; authenticated
production build (existing large-chunk warning). Tests cover rotated/resized A1,
calibration override/staleness, aspect/crop/multi-view safeguards, partial costs,
exact 10m shared 3D length, real API draft save/reload without approval and final
estimate regressions. Initial gate found strict response schema omissions and a
test source-provenance/attachment mismatch; fixed and reran. Older missing-drop
expectations updated to partial-cost behavior; legacy unit mock updated for the
existing automatic-price lookup. Full repository suite NOT RUN.

PASS live read-only workspace: source lengths now 203.4761 nominal metres each
for conduit/cable; grouped references and Edit prices remain. With no applicable
prices, known total0.00 is Partial, never a final project cost. No real prices,
review or geometry written. Screenshot: tmp/ux-checkpoints/a1-draft-bom.jpg.
All44 baseline originals byte-identical (45 current), zero active analysis jobs,
stash bb78854e87833124a1725b51f0be6099a8ac0cfa retained. Concurrent real data
additions preserved; no assertion that the whole database was unchanged.
API66/38 modeled tables unchanged. Live37 tables: measurement settings table
still absent, administrator provisioning BLOCKED; saved measurement UI not
claimed complete. No live DDL or grants. BDO remains paused. Next: verify the
preserved independent copy/paste work; do not restart detection or overwrite edits.
