# Proposal review, notifications and workspace reset

Admin's Proposal review separates Awaiting review and Approved proposals. Open
workspace uses the current processing job. The Decision column requires a
comment for approval or return. Unapprove returns the plan to its Designer and
removes its Client publication. A return supersedes earlier submissions and
approvals until the Designer submits again. Prior immutable BOM files are kept
during ordinary approval/return operations; they cannot restore withdrawn access.

Designer notifications use existing Admin activity records, scoped to assigned
projects. Catalog/default changes are shared System notifications. System and
Comments open a detail modal. Product reports distinguish current prices from
captured historical estimate prices. Read acknowledgements are append-only.
No notification or measurement table was added. The bell is fixed at top-left.
Icons8's free empty-state PNG includes visible attribution when displayed.

## Wiring

New source extraction recovers continuous curved ink between paired power
outlets and their homerun leaders, outside the recognised symbol bounds. It
does not infer a lead across a white gap or add data-port electrical terminals.
Source route nodes describe physical route continuation through an ordinary
power outlet; they are not hot, neutral or earth terminals. Explicit circuit,
height, installation and designer terminal assignments remain authoritative.

Source-backed corner repair joins free dashed-wire ends only with continuous
thick-ink evidence. It clips an unsupported wall-bank tail only when an actual
perpendicular source arm ends at that supported corner. Saved review geometry
is never passed through these detection functions.

Homerun A* proposals start at the source leader's endpoint and share an explicit
junction and route placement with that leader. Generated paths remain proposals,
separate from observed takeoff; no conductor multiplier or waste was added.
Unresolved source evidence stays unresolved. In Check wiring, a saved duplicate
can be removed with Undo. Removed panel suggestions can be explicitly restored;
their deletion tombstones are not silently overridden.

## Workspace cleanup — Admin settings → Workspace data

The current reset preserves project content. It archives active projects and
keeps the signed-in Admin plus one selected Designer. Other accounts lose sign-in
access and profile information, including extra Admins. Identity rows without
history references are deleted; disabled anonymous author keys remain where
project, catalogue or audit history still refers to them.

The UI previews the scope, requires a checkbox and `RESET WORKSPACE ACCESS`, and
starts a minimum five-minute cancellation period. Closing the browser does not
cancel a scheduled cleanup. Queued/running scans must finish first. A successful
private MySQL backup is required before any account/project changes.

Floorplans, originals, processing artifacts, saved layouts, BOMs, estimates,
reports, settings, prices, pairings, assemblies, legends and model/training data
are preserved. No project files are moved or deleted. Protected-table fingerprints
are checked inside the same transaction as archiving/revocation. Completion is
committed atomically with the changes. Interrupted uncommitted cleanup rolls back.
The old full-erasure mode is no longer accepted; old pending requests stop safely
instead of inheriting the new scope without review.

Recovery-email challenges are removed before the emails they reference. Ordinary
account administration still protects Admins; the reset is the explicit, reviewed
exception that can remove extra Admin access while keeping its requester.

See [the 30 October publication checkpoint](PUBLICATION_20261030.md) for the live
cleanup result. The historical verification entries below describe their original
implementation checkpoints, including the superseded full-erasure design.

## Verification — 29 October 2026

- PASS: production frontend build and focused ESLint on changed UI modules.
- PASS: backend imports and compilation; read-only reset preview reports idle.
- PASS: actual browser shows the bell at top-left and a System details modal
  with the affected product, item code, author and clearly labelled current price.
- PASS: supplied source recovers four paired-outlet/homerun curved leads, joins
  two pixel-supported corners and clips a 21-pixel wall-bank tail. The resulting
  source/proposal graph validates. Other unproven connections remain unresolved.
- PASS: in-memory repair removes the saved duplicate segment-0012 while keeping
  segment-0011 and a valid network. Saved review JSON and source-image hashes
  remain unchanged. The existing Git stash remains unchanged.
- NOT TESTED: actual approval/unapproval writes and permanent reset execution.
  No real reset was scheduled, and no saved geometry was rewritten.
- FAIL: full-repository ESLint still reports six existing errors in
  `frontend/src/features/viewer-3d/DeviceMeshCatalog.jsx` (unused React import,
  mixed exports and conditional hooks). This file was not changed here.

### Saved-plan repair and settings follow-up

`scripts/repair_saved_wiring.py` previews source-backed repairs by default.
Explicit `--apply` saves through the normal authorized review service, with
expected processing-job and review-revision checks. It retains the immutable
candidate and previous review, all non-wiring geometry and material identities.

Plan 9379 / job 24378 was repaired as review 285, revision 4, from revision 3.
The v18 repair removes duplicate segment-0012, repairs the two right-hand
source corners and two paired-outlet source leaders, and restores their
separate A* panel proposals. The third homerun stays unresolved where source
evidence is insufficient. Original v15 scan metadata is retained as history;
this is a new reviewed draft revision, not a replacement raw detection record.

Device focus now takes one second; other camera presets retain their timing.
Reduced-motion preferences and interruption by camera interaction still apply.
Frontend build and focused lint pass. No new test files were added and no
workspace erasure was scheduled or executed.

### Power plan 9386 — 2D selection crash

Reproduced on project 10220 / floor 6326 / job 24388: clicking an observed
2D wire threw from `wiringComponents` during selection rendering and unmounted
the page. An inherited source-backed join at (684, 900) and a new source corner
at (1668, 902) both used the run-local name `junction-0001`.

Source adaptation now allocates collision-free draft join IDs. An inherited
source-backed join can retain its identity only with the exact same source
anchor and assignment; its original evidence identity remains separate. The
operation is repeatable and preserves saved edits and immutable candidates.
Selection and the shared-height inspector also report incompatible joins without
throwing during rendering; mutation validation remains strict.

BOM preparation now mirrors the workspace's second source-placement pass.
Calculation-only projection excludes one-sided bindings to omitted pending
panel proposals after validating the complete node, without counting or
modifying those proposal routes. This fixes the related unavailable BOM.

PASS: reproduced the original exception; corrected graph validates and remains
stable across repeated adaptation; source points, device attachments, heights,
circuits and inherited review geometry remain unchanged; full BOM service
returns successfully; frontend build and focused lint pass. No test files added.
