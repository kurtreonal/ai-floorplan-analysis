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
