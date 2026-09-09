# Codex execution prompt: development demo first, then local VLM migration

This is a reusable execution handoff, not a report of implemented U work.
Preparing this file starts no ticket. Assign the instructions below explicitly
to authorize implementation. All fourteen tickets remain documented, but the
September 9 demo amendment below is the current execution priority.

## 0. CURRENT ASSIGNMENT: September 10 upload-to-2D/3D demo

When the user assigns this updated prompt, execute DEMO-0 through DEMO-4 from
the active-priority section of `docs/LOCAL_VLM_MIGRATION_PLAN.md` first.
The target is September 10, 2026, Asia/Singapore; no exact delivery hour was
specified. Do not promise the date or 50% quality before measuring. This
amendment takes precedence over the sequential-U dependency and L2+ exclusion
wording below ONLY for the bounded demo. This is implementation work in the
existing application, not another standalone annotation HTML workspace.

The user wants to upload a previously unannotated floor plan, click Analyze,
receive actual room/wall and electrical-symbol proposals in 2D, review/correct
them, and obtain aligned basic 3D after explicit geometry/metric approval.
Single floor / one explicitly selected PDF plan page is sufficient initially;
report other PDF pages as not processed rather than claiming document success.
Target >=50% room recall AND >=50% symbol recall on reviewed development pages,
with the plan's fixed IoU matching, precision, FP/FN and denominators. Do not
confuse this target with confidence=0.50. Missing truth is NOT TESTED, not PASS.
No wiring extraction/routing, quantities, costing, fine-tuning or full Admin
dataset-workspace implementation is required for this demo.

1. Inspect the repository, current branch, dirty files, model artifacts and
   real execution paths before editing. Read the mandatory context below and
   verify current evidence. Preserve existing work and the protected service.
   Report the smallest implementation plan and actual gaps. Published U1/U2
   are not to be restarted. L1 currently initializes an empty 3D scene; do not
   mistake it for floor-plan reconstruction. Recheck this against current code.
2. Freeze a small readable, VED-authorized development page set for evaluation.
   Do not wait for all scans/annotations, the eight U3 decisions, a degraded
   training record or a new sealed-test project to implement this demo. Keep
   those corpus/release gates BLOCKED in their existing records. Do not approve
   records, weaken intake validation or claim U3 passed. Unreadable/unsafe
   input still fails visibly; use a readable alternative for the demo.
3. Implement DEMO-1 using the fastest working local provider within U1 bounds.
   Verify usable weights before selecting YOLO; inspect existing OpenCV walls
   and add bounded room-boundary proposals where missing. If a small local VLM
   is genuinely usable, isolate and validate it; otherwise use a disclosed CV /
   legend-template baseline. A template prototype is not VLM completion or
   trained-model accuracy. Keep inference opt-in for local development and
   separate from production model promotion. Do not spend the entire deadline
   on acquisition, a broad bake-off or LoRA. No fake/precomputed detections,
   hosted inference, upload-triggered downloads or automatic training.
4. Implement DEMO-2: reuse the actual upload/source/artifact/job lifecycle,
   PRE9 bounded worker controls and existing review/save services. Return
   promptly, persist real results, show partial/empty/failure outcomes and
   provide room/wall/symbol correction. Reuse U2 and canonical contracts, with
   honest provider identity and no fabricated legacy confidence. Preserve
   authorization, original files, immutable evidence, idempotency and review.
5. Implement DEMO-3: the minimum L2-L5 floor/room-surface, wall-extrusion and
   simple symbol-marker rendering using the SAME saved canonical document as
   Konva. Implement real 2D-to-3D coordinate transforms and reload synchronization,
   not hard-coded meshes. Require explicit scale/elevation and wall parameters;
   missing values remain visible and cannot be guessed. Keep the review step
   usable, not an undocumented database-edit prerequisite. No raw inference
   output may silently become approved geometry.
6. Complete DEMO-4 with at least one actual unannotated-upload -> Analyze ->
   review/correct -> approve metric inputs -> save -> 2D + 3D -> reload browser
   demonstration. Also measure the separate 50% targets on the fixed reviewed
   development pages, excluding manual corrections from inference scores.
   Test rotated/scaled coordinates, rejected-symbol exclusion, changed 2D
   positions in 3D after reload, unavailable-model/invalid-input failures,
   persisted results after restart, authorization and original-file integrity.
   Run relevant backend/frontend tests and build. If actual browser validation
   is unavailable, say NOT TESTED; mocked tests do not replace the demonstration.
7. Deliver a runnable local application with exact startup commands, any model
   requirements, page/legend/scale setup, controls to reach both views, measured
   results and honest limitations. A static screenshot, manual annotation file,
   empty grid or fixture-only success does not satisfy the requested output.

Use separate small demo commits/checkpoints, not an oversized U3 change. Inspect
and reuse an existing matching demo branch, or create
`codex/demo-floorplan-2d-3d` from verified main. Preserve the blocked U3 branch
and safely carry only explicitly scoped planning inputs/dependencies; do not
merge blocked U3 wholesale. Existing publication permissions apply to passing
scoped demo work when this prompt is assigned, subject to protection and tests.
Never claim an entire U/L ticket passed because its demo subset works. Update
the existing progress ledger after each checkpoint; create no new Markdown
planning files. Stop at the demo handoff and request direction before returning
to the full U sequence. Do not repeatedly poll the unchanged U3 data gate.

## 1. Authorized objective and stopping point

The remainder describes the full migration path retained for later resumption.
Section 0 is the active assignment and its stopping point until the user
explicitly returns to the full sequence.

Implement U1 through U14 from docs/FUNCTIONAL_SPEC.md and
docs/LOCAL_VLM_MIGRATION_PLAN.md, in order, through verified publication.
This assignment explicitly authorizes the scoped implementation, necessary
local dependencies and model downloads in their owning tickets, offline
training on approved data, separate feature commits and pushes, explicit
non-fast-forward merges, post-merge verification, and main pushes.

Do not ask again for routine commit/merge/push permission between tickets.
After each passing published ticket, report progress and continue to the next
authorized ticket. Stop after U14's real release/rollback gate and final report.
Do not implement L2+, M-series generated routing, material quantities, costing,
reports, general Admin UI outside the scoped dataset annotation workspace
defined in U5/U9 below, or unrelated refactors.

This authorization does NOT grant permission to:
- impersonate a human approver or invent VED classes, labels, scale or elevation;
- upload private material to hosted inference, Roboflow, public repositories,
  issue trackers, external annotation services or cloud training;
- spend money, rent GPUs, change external-service visibility or permissions;
- install/change system drivers, enable WSL/Docker, move existing private
  collections, or use another machine without the required U1 approval;
- delete original files, reset live databases, rewrite Git history, force-push,
  remove YOLO, or bypass branch protection;
- automatically train from production uploads or promote an unsigned model.

If a required human approval, data permission, gold record, resource budget or
release gate is missing, finish only safe work within the current ticket,
report BLOCKED with the exact missing item and resume instructions, and stop
dependent work. Infrastructure tests alone do not complete data/model tickets.
Do not silently skip failed gates to announce all U tickets complete.

### Planning amendments confirmed by the user on 2026-09-08

Resume the actual current ticket rather than restarting published U1/U2.
The standing U1-U14 implementation/publication authorization remains active;
passing ticket checkpoints do not require another planning-chat approval.

The user confirms VED collection-level permission for the supplied documents,
including additional VED-supplied hard-copy documents still being scanned,
for training, development evaluation, sealed evaluation and reference grounding.
Bind source records to this collection authorization privately. Record the
authority as VED approval confirmed by the user and reference the confirmation;
do not invent a named signer or require repeated per-source permission within
this scope. Unrelated third-party material is not automatically covered.
This permission does not manufacture annotation correctness, independent PRE10
review, approved gold, numeric thresholds or release sign-off.

Historical projects supply training and independent development-validation
groups. New independent projects are intended for final testing. Assign splits
before tuning; keep related pages, revisions, crops and rescans together.
Scanning an old drawing now does not turn it into an independent test project.
Incomplete scans/metadata remain pending. Missing actual test coverage must
remain visible at the owning gate; do not fabricate it to continue.

Device encryption is DEFERRED with user-accepted risk and no approved deadline.
It no longer blocks U3 intake or U6 acquisition. Do not mark encryption PASS.
All remaining local-only, data-integrity and resource boundaries still apply.

The user delegates preparation of annotation proposals to the assistant and
will review completeness, corrections and unresolved areas. Record the actual
author and reviewer; never invent approval or claim an automatic connection
between a conversation and the application. Support explicit validated import
of assistant-prepared proposals where appropriate, with source/legend hashes,
dimensions and coordinate conventions. No hosted inference integration is
authorized by this amendment.

Implement the future workspace at Admin > AI Datasets > Annotation inside the
existing VED application, using React/JavaScript and React-Konva. U5 owns the
minimum local bootstrap review/import capability; U9 extends it with durable
pseudo-label review and richer editing. Do not create a standalone competing
annotation application or bring the full U9 scope into U3. Maintain these
requirements in existing documentation; add no new Markdown planning files.

## 2. Mandatory context review and baseline

Before planning or editing, read completely:
- AGENTS.md and any applicable nested repository instructions;
- README.md;
- backend/README.md;
- docs/ARCHITECTURE.md;
- docs/FUNCTIONAL_SPEC.md;
- docs/geometry.md;
- docs/LOCAL_VLM_MIGRATION_PLAN.md;
- docs/PRE_VLM_FOUNDATION_PLAN.md;
- docs/PRE_VLM_READINESS_REPORT.md;
- docs/decisions/0001-canonical-geometry-compatibility.md;
- this entire handoff.

Read relevant source-reference documentation when a domain decision needs it.
Compare documents against actual source, tests and latest reports; do not treat
old acceptance checkboxes or aspirational architecture as implementation proof.
At each ticket refresh all four mandatory high-level documents completely and
the relevant changed contracts. Correct material inconsistencies in that ticket.

Reported PRE12 starting evidence, to verify rather than blindly impose:
- main merge: 81ecd833bfa3; PRE0-PRE12 complete; L1 is the product milestone.
- main/origin and PRE feature upstreams were synchronized; working tree clean.
- 34 OpenAPI operations; 23 modeled/live tables.
- unittest 627; combined pytest 667 plus 504 subtests; frontend 280.
  These are historical overlapping counts, not sums or guaranteed current totals.
- Six originals, total 146,958 bytes; each 24,493 bytes with SHA-256
  55C511400C9B6F166B691C1569D9FAAA8DD7C97A8FECEADBB98A0C5CA13BC243.
- Protected backend/app/services/project_service.py:
  blob 44e01c22ede76f30182b1056b0cb4e6fce3df96a; no diff.
- No VLM model, adapter or U implementation was present.
- Live legend, metric settings, dataset-approver assignments and layouts were
  empty. PRE12 tested those contracts; it did not populate approved data.

Inspect current Git HEAD, branches, remotes, upstreams, dirty/untracked paths,
relevant implementation and test commands. Refresh remote references before
publication. If main has legitimate later work, reconcile its ancestry and
scope, retain it, and update the baseline; do not reset to PRE12.
If an interrupted U branch already exists, inspect and resume it rather than
duplicating its work. Unexpected overlapping edits require clarification.

Preserve the protected file's measured bytes and diff. Do not recreate an old
newline-only diff: the accepted PRE12 baseline is clean.
Any pending Markdown-only handoff changes are planning inputs, not proof that
U1 is done. Review their explicit paths and include the applicable planning
baseline with U1 publication; never stage unrelated files.

Record a private baseline manifest of existing database rows and original
file sizes/hashes before mutation. Keep drawings, OCR, names, private source
hashes, labels, crops and prompts out of public reports. Do not read secrets
into tool output. Recheck ignore coverage and tracked files.

## 3. Architecture and data invariants

Keep JavaScript/JSX, React, Konva, Three/R3F, FastAPI, SQLAlchemy/PyMySQL and
the prototype schema strategy. No TypeScript, Flask or Alembic. Keep the model
runtime and training dependencies isolated from the existing backend environment.
Use thin authenticated routes, services for workflow and repositories for data.

Reuse:
- PRE1-PRE3 discovery/reload reconciliation;
- PRE4 source/page records and PRE5 processing_artifact_service.py;
- PRE6 analysis_settings_service.py and require_approved_metric_inputs;
- PRE7 symbol-legend governance and PRE10 dataset_approver_assignment_service.py;
- PRE8 layout_service.py/layout_version_service.py and LayoutSaveRequest;
- PRE9 processing_execution_service.py/repository and its attempts/cancellations;
- K1 canonical.py, frontend canonicalGeometry.js and shared fixtures;
- existing J review, K editor and L1 empty-viewer boundaries.

Inspect these paths before extending them; do not duplicate completed foundations.

The pipeline produces advisory candidates, then human review, then deterministic
canonical adaptation. No raw VLM output writes geometry or renderer state.
All model-provided text and text found on drawings is untrusted content, not
instructions to run commands, change permissions, fetch URLs or approve results.
Host code owns identity, hashes, model manifest, authorization and review state.

Maintain immutable raw corpus, pseudo-labels, reviewed gold and sealed final test
as distinct data levels. Upload-time annotation is not required; trustworthy
supervised targets and independent review still are. Training is explicitly
offline and versioned. Uploading or correcting a production plan never changes
active weights automatically or grants training permission.

A project Designer approves project geometry. The active PRE10 human Dataset
Approver independently approves dataset/release records. Check authority at
decision time and retain its snapshot/history. Neither Codex nor the model may
sign; reject human proposal-author self-approval too. Do not infer authority
from a display name, client-supplied role or a typed approval string.

Only approved active VED class identities can become canonical symbols.
Drawing-specific approved legends take precedence. Unknown mappings remain
unresolved and reviewable. PEC references require traceable permitted-use
metadata; possession of a book or an old export license is not training consent.
No fabricated PEC compliance, panel ratings, wire sizes or engineering defaults.

Coordinates:
- Native/oriented high-resolution evidence, normalized reference image,
  crop/tile/model coordinates and canonical meters are distinct frames.
- Record invertible transforms, dimensions, rotation and crop/resize offsets.
- K1 v1 reference dimensions remain bounded at 4096 per edge.
- Never crop/upscale reduced G2 output and claim native glyph detail was recovered.
- PRE6 approved scale must match the exact reference dimensions. Do not turn
  PDF DPI, paper size, floor order or a VLM guess into metric truth.
- Multi-page/multi-region drawings cannot be merged into one metric plane
  without explicit source/floor association and approved transform/scale.
- Every page must have an explicit included, non-plan, unsupported, failed,
  partial or needs-review outcome; no silently ignored later PDF pages.

Canonical compatibility:
- K1 v1 and historical YOLO/layout records stay native and unchanged.
- U11 implements PRE11's separate extension-v2 record transactionally linked
  to a NEW v1 layout snapshot, not version-2 JSON in the v1 database column.
- Validate extension versions explicitly in Python and JavaScript.
- Preserve PRE8 expected version and idempotency for the entire base+extension.
- No silent extension loss through legacy GET/POST or K5 movement.
- Resolve canonical symbol identities/provenance explicitly; do not fabricate
  YOLO confidence, reuse colliding IDs, or mislabel VLM output as legacy YOLO.
  If the exact v1/extension identity contract cannot express a required case,
  document the conflict and seek a bounded ADR decision before implementation.

## 4. U1 — Hardware, privacy and runtime requirements

Inspect the machine read-only: OS, CPU, physical/available RAM, GPU(s), dedicated
VRAM, driver/CUDA capability, Python/runtime compatibility and available disk.
Distinguish measured values, unavailable information and proposed budgets.
Record a sanitized hardware/privacy decision document, not machine secrets.

Define input-quality limits and numeric page/render/tile/context/output budgets,
concurrency, timeouts, inference latency goals, model storage and training
budget. Have the responsible user approve operational budgets and any separate
host/WSL/container boundary. Do not silently treat recommended limits as approved.

Inspect synchronized storage risk: the repository is under OneDrive.
Git ignore does not prevent OneDrive/backup upload. Establish a verified approved
private processing/training location and retention policy; do not move or
delete the existing corpus without authority. Record unresolved historical
Roboflow visibility concerns without modifying that service.

Define offline inference, no fallback/telemetry, safe diagnostic retention,
model/reference licensing requirements and controlled public model acquisition.
No model selection, download, inference dependency or API/table change in U1.

Verify: reproducible inventory, budgets/approval evidence, private path/ignore
audit, no model files or application changes, protected-file integrity.
PASS requires actual measurements and required decisions, not guessed hardware.

## 5. U2 — Strict candidate contract v1

Implement application-owned strict immutable candidate schemas and synthetic
fixtures under the existing backend AI boundary, plus contract documentation.
Cover page type/quality, source plane, regions/tiles/transforms, OCR evidence,
scale proposals, walls, rooms, openings, symbols, panels, observed route
segments/connections, warnings, ambiguity, partial/truncated results, optional
orientation/bounds and deterministic identifiers/order.

Separate generated payload from the host-owned provenance envelope. Define
bounded strings/arrays, valid finite numbers, safe IDs, geometry bounds and
polygon/graph/reference consistency. Define unavailable versus empty versus
failed extraction. Unknown class mapping must not require a made-up class.
Candidate approval cannot come from generated JSON.

Freeze the proposed U9 storage/review identity and U11 canonical projection
mapping early, including legacy/VLM symbol collision prevention. Do not change
K1 v1 or implement persistence/runtime in U2.

Verify: valid/empty/unknown/partial cases; malformed JSON, extra keys, NaN,
Boolean/string-number coercion, invalid polygons, dangling graph references,
out-of-bounds geometry, duplicate IDs, wrong source identity, oversized output
and instruction-like OCR. Preserve canonical compatibility fixtures.

## 6. U3 — Private corpus intake and leakage-safe splits

Build local explicit intake tooling and manifests using existing source identity
where applicable. Preserve originals, deterministic hashes, page inventory,
source/drawing-set/project grouping, permissions by purpose, quality and sheet
classification metadata. Unknown metadata remains pending, not approved.

Inventory approved local sources including docs/blueprints,
docs/electrical-symbols and storage/training only within the U1 privacy boundary.
Do not upload to an annotation website or change existing Roboflow exports.
Do not treat six identical live originals as six independent training examples.

Assign train/development-validation/sealed-test groups BEFORE pseudo-labeling.
Keep related revisions/pages/crops/exports in one group. Detect exact duplicates,
flag near-duplicates for resolution and exclude ambiguous cross-split groups.
Store private manifests/derivatives locally and Git-ignored; commit tooling and
sanitized synthetic fixtures only.

Verify: idempotent re-intake, changed-source conflict, unsupported/corrupt input,
multipage identity, permission restrictions, duplicate grouping, cross-split
leakage rejection, path traversal/symlinks and unchanged original hashes.
Record actual eligible coverage; insufficient independent projects is BLOCKED.

## 7. U4 — Approved legend and local reference pack

Reuse PRE7 catalog records/history. Build a versioned private reference pack
containing stable approved class ID/name, aliases, descriptions, permitted glyph
references, source page/region, drawing-specific crosswalk, approval revision
and hashes. Cover each active supported class; mark incomplete coverage blocked.

Extract/propose legend entries for human review; do not auto-create or activate
catalog classes. Maintain unknown glyphs separately. Validate drawing-specific
mapping precedence and prevent retrieval from changing approval state.
Keep prior pack versions reproducible after catalog revisions/deactivation.

Record source edition/part/page, rights and allowed use for PEC/reference
material without copying private book content into Git or model releases.
Do not claim approval merely because an exported file says CC BY.

Verify: empty catalog, inactive class, conflicting aliases, version changes,
unknown glyph, cross-drawing mix-up, missing rights, private artifact access,
historical snapshot stability and authenticated Admin/Designer boundaries.
A builder with synthetic fixtures is not a completed real approved pack.

## 8. U5 — Independent gold and predeclared metrics

Create a bounded OFFLINE bootstrap review/import workflow so initial gold does
not depend on the later U9 UI or U6 model. It must validate source/record hashes,
completeness, actual active PRE10 authority, authorship independence, decision
time and revision; a client-written approver ID/signature is insufficient.
Retain reviewable evidence locally and auditable decision provenance.

Expose the minimum bootstrap workflow under Admin > AI Datasets > Annotation.
It must work without U6 inference or U9 pseudo-labeling: display original scans
and associated legends, import validated proposals or accept manual labels,
support correction and explicit completeness review, and preserve revisioned
outputs for reuse by U9. Keep source pixels and original files unchanged.
Separate annotation complete, review complete and approved for training states.
Scope access to explicitly authorized dataset sources; Admin navigation alone
does not grant dataset-approver authority or access to all Designer projects.
Enforce the role/access and PRE10 approval checks on the backend, including an
authorized review path for assigned approvers without granting them general
Admin privileges. Do not treat the user's standing data-use permission as a
completed independent gold/quality decision.

Collect independently corrected representative examples across supported classes,
source projects, empty/hard negatives, dense/small glyphs, multiple scales,
supported degraded scans and wiring/no-wiring pages. Resolve sample sufficiency
with VED; do not claim accuracy from a single drawing or duplicate pages.

Freeze reviewed development-validation and sealed final-test memberships.
Implement deterministic metric tooling with known-answer fixtures.
Report all migration-plan metrics: schema/retry rates, sheet classification,
per-class precision/recall/F1/count/box IoU/center error, wall/room/opening/panel
quality where supported, scale errors, wiring presence/topology/length errors,
hallucinations, unknown handling, per-group quality, latency and RAM/VRAM.

Define matching rules, coordinate units/tolerances, aggregation, absent-class
handling, minimum coverage and approved numeric promotion/regression thresholds
BEFORE model/prompt tuning. Unsupported metrics are N/A with a reason, not zero.
Hard safety gates are mandatory independent of accuracy scores.

Seal final-test images AND labels from model/prompt/training workflows.
U6/U10 use only development validation. U14 opens sealed test after the release
candidate is fixed. Document evidence access and test-reuse rules.

Verify: known metric calculations, deterministic splits, leakage checks,
incomplete-page exclusion, self-approval/expired-authority rejection,
tampered manifests, permissions and inaccessible sealed-test data.
Missing actual human-approved gold/thresholds blocks U5 completion and U6.

## 9. U6 — Local model/runtime bake-off

Reverify candidate model cards, licenses, official runtime/fine-tuning support
and supported platform/dependency combinations from primary sources.
Treat the migration-plan model list as candidates, not guaranteed compatibility.
Evaluate feasible named candidates or record specific measured reasons to skip.
Do not silently substitute a text-only LLM or hosted model.

Acquire only bounded, licensed, pinned public model artifacts into the approved
ignored local location, with hashes and manifests. Keep experiment environments
separate from FastAPI; no download on app import, startup or user processing.
Do not enable trust_remote_code without code review and explicit justification.

Use a bounded offline experimental harness with U2 validation, recorded RGB
overview/tile transforms and fixed experiment settings. It does not depend on
the future U7/U8 production implementation. Compare on U5 development validation,
never the sealed test set. Record model/load latency, memory, output validity,
quality, prompts/context, revisions, quantization and reproducibility.

Test actual local inference and egress restrictions. Compare available legacy
YOLO/CV honestly; missing YOLO weights means unavailable, not a zero baseline.
Select only a candidate meeting approved selection gates; otherwise report
no qualifying model and the precise hardware/data/quality constraint.

Verify: real image inputs, malformed/empty/negative cases, memory/timeout
bounds, offline restart, pinned artifact integrity, license records, isolated
dependency integrity and unchanged backend behavior. Publish sanitized results.

## 10. U7 — High-resolution page, region, tile and OCR preparation

Implement deterministic production preparation under the AI/preparation and
artifact service boundaries, reusing G1/G2 and PRE4/PRE5 without changing
originals. Preserve a higher-resolution oriented evidence render under bounded
resource limits; maintain a separate aligned G2/K1 reference image.
Record page number, crop/region/tile identity, rotations, resizing and reversible
transforms between evidence, reference and model inputs.

Provide overview, legend, plan-region and overlapping tile views plus local OCR
and deterministic line evidence. RGB is primary; thresholded imagery is optional
auxiliary evidence. Report unreadable, non-electrical, missing-legend and partial
pages explicitly. Do not guess a floor or combine different scales on one sheet.

Extend PRE5 artifact kinds/metadata only as necessary and document additive
schema implications. Keep every trusted artifact tied to its source page/run.
Do not force JSON results into the existing PNG-only artifact validator.
Implement deterministic tile fusion/deduplication without silently suppressing
close distinct fixtures or losing conflict evidence.

Verify: rotated PDFs, EXIF/transparency, non-square/asymmetric scaling rejection,
multipage sources, tiny glyphs, crop edges/overlap, invertible coordinate round
trips, duplicates versus adjacent true symbols, unsafe paths, artifact replay
and conflicts, pixel/tile caps before allocation, unchanged originals.
Validate preparation quality on approved development inputs without test leakage.

## 11. U8 — Isolated local VLM gateway

Implement bounded process-isolated serving and a thin local client boundary;
keep AI work out of FastAPI routes. Pin the selected model/adapter/runtime and
prompt/schema/reference pack. Use explicit startup/health/readiness and bounded
lazy cache; do not load per symbol or permit user-selected model paths/URLs.

Record host-owned run provenance, inputs, decoding and resource metrics.
Constrained decoding is preferred where supported; strict complete U2 validation
is mandatory in all cases. Invalid/truncated text is not a partial success.
Never execute generated commands, parse unsafe objects or trust model approval.
Keep raw diagnostics private with retention controls; ordinary API errors are safe.

Enforce local endpoint policy, no redirects/hosted fallback, bounded queue,
concurrency, output length, timeouts, cancellation and limited retry policy.
Define actual process termination behavior when cooperative cancellation fails.
Do not mutate active model weights or production canonical geometry.

Verify with fakes AND actual pinned local model: malformed/adversarial text,
image/prompt injection, missing files, initialization failure, health failure,
concurrent first loads, overload, timeout/cancel, memory pressure, offline
inference, logging redaction, model hash mismatch and no app-import download.
Do not mark real-runtime criteria PASS using only mocked generation.

## 12. U9 — Durable pseudo-labeling and human correction

Run explicit private non-test batch pseudo-labeling via U7/U8. Retain original
machine output, source/model/prompt/reference/transform provenance, validation
warnings, agreements and immutable run identity. Retries do not erase reviews.

Implement the MINIMUM durable candidate and append-only review storage now,
with repositories/services and authenticated review access; U11 must reuse it.
Extend the existing review feature instead of creating an unrelated parallel app.
Support accept/correct/add/reject/unresolved for symbols, walls, rooms, openings,
panels, scale evidence and observed wiring, with accessible overlays/inspectors,
page navigation, safe reload and stale-review conflict handling.

Extend the U5 Admin > AI Datasets > Annotation workspace using shared existing
review components/services. Provide project/floor/sheet/revision navigation,
an associated legend view, a zoomable/pannable original-image canvas and a
selected-annotation inspector. Use separate editable layers for:

- symbols: boxes/locations, approved legend mappings and associated text;
- geometry: wall lines, room polygons and door/window locations;
- observed wiring: visible polylines and reviewed connections, not invented
  paths or circuits;
- text/dimensions: readable labels and dimension evidence with uncertainty;
- review markers: missing items, unresolved areas and page completeness.

Support drawing, moving, resizing and deleting appropriate annotation shapes,
class correction and accept/reject/add/unresolved actions. Keep legend examples
distinct from installed devices and unknown glyphs distinct from approved
classes. Retain original proposals alongside corrections and review history.
Readable degraded scans may become eligible only through an explicit supported
quality/review policy; unreadable targets stay unresolved. Do not equate all
degraded scans with unusable data or silently declare them supported.

Persist revisioned annotations and reload them safely. Export only eligible,
fully reviewed and independently approved training records. Keep annotation
completeness, user review and training approval visibly distinct. Verify
original-pixel overlay alignment, each editing operation, proposal import
validation, layer visibility, save/reload and stale-edit handling, cross-source
and cross-role denial, and exclusion of pending/rejected/sealed-test records
from training export. Reuse this storage in U11; no parallel source of truth.

Separate owner-scoped project review from dataset approval. An ordinary project
approval does not grant training permission. Implement a completeness checklist,
page revision hash and independent PRE10 approval binding. Correction after
approval creates a new revision needing approval; no in-place gold rewrite.
Partially reviewed pages and unresolved training targets are excluded.

Export only permission-eligible, fully approved non-test records. Import or
reconcile U5 bootstrap gold without manufacturing a new approval or changing
frozen evaluation membership. Dataset reviewers get only explicitly authorized
data, not unrestricted access to all Designer projects by virtue of assignment.

Verify: cross-owner denial, Admin project read-only behavior, reviewer authority,
author self-approval rejection, review concurrency, reload persistence, stale
approvals, batch retry/crash, immutable machine provenance, missing/add/reject
cases, incomplete-page exclusion and private export integrity.
Use actual human decisions for real data; automation can demonstrate workflow,
not supply final sign-off.

## 13. U10 — Actual VED LoRA/QLoRA training and registration

Implement reproducible model-specific image/conversation conversion and training
in an isolated local environment. Use approved training records and explicitly
permitted synthetic data only. Keep reference packs and validation/test groups
separate; never train on raw pending scans, unreviewed pseudo-labels or holdout.

Pin base/model/tokenizer/processor revisions, licenses, hashes, framework versions,
seed, adapter targets/configuration, precision, hyperparameters, data manifest,
prompt schema, budgets and checkpoints. Verify image token handling, assistant
loss masking and grounding coordinates match the chosen model's documented format.

Run an actual bounded training job within U1-approved resources. Verify that
intended adapter parameters change and the frozen base does not. Support resumable
checkpoints with compatibility checks; never overwrite a released artifact.
Register the resulting hashed adapter as INACTIVE with its training provenance.

Evaluate checkpoint selection on development validation, including regressions
against the untuned base, resources and invalid/hallucinated output. Do not
open sealed final test. A smoke run proves mechanics, not useful model quality.

Verify: rejected unapproved/test examples, conversion round trip, deterministic
configuration, masking, real adapter load/inference, interrupted resume, corrupt
checkpoint failure, base integrity, validation report and inactive registration.
Scripts plus mock training are NOT a completed U10. If data or compute is
insufficient, state exactly what is missing; do not rent a cloud GPU.

## 14. U11 — Production persistence and approved canonical adaptation

Reuse U9 immutable runs/reviews. Add production retrieval/version selection,
safe schemas, authorization and bounded pagination where needed. Preserve raw
machine evidence privately, exposed validated data and latest review separately.
Never rewrite historical YOLO detections, correction histories or prior layouts.

Implement deterministic adaptation of an explicitly selected approved revision.
Resolve project/floor/source-page identity, stable entity IDs and approved
reference dimensions, scale and elevation through PRE4/PRE6. Confirm references
and decisions have not changed during approval/save. Exclude rejected/pending/
unknown entities; partial extraction must not masquerade as a complete layout.
Keep original class evidence separately from corrected authoritative class.

Implement ADR 0001's exact additive extension-v2 schema/dispatcher/persistence
in Python and JavaScript together, with shared fixtures. Include approved
source-plane, opening/panel, optional symbol bounds/orientation and route-kind
provenance. Unknown engineering attributes remain unresolved, not defaulted.

Create the new K1-v1 base snapshot, its extension, the approval binding and
PRE8 idempotency record in ONE transaction. Lock/recheck the expected current
version; any failure rolls back all outputs and preserves the old current layout.
No version-2 payload in layout_versions.geometry_document, no weakened v1 check.

Resolve VLM symbol source-to-canonical mapping according to U2's documented
identity decision, with genuine provenance and no synthetic YOLO confidence.
Expose extension support explicitly. Preserve native v1 clients/history.
Update K5 saves to preserve validated extensions or reject unsupported edits
clearly; never silently drop an extension on a new layout snapshot.
Use the approved explicit source-plane for aligned review/editor images.

Verify: full approved conversion and known coordinates, missing/stale scale,
mismatched dimensions, cross-page/floor references, original/corrected classes,
legacy/VLM ID collision, unknown extensions, frontend/backend fixture parity,
partial data, extension-aware reload/movement, stale saves, identical/conflicting
retry, simultaneous saves and rollback injected at each transaction boundary.
Test legacy J/K behavior and readable historical versions.

## 15. U12 — Observed wiring extraction, not electrical design

Harden extraction and fusion of drawn wires/conduits using U7 evidence and U8
interpretation. Preserve visible polylines, endpoint candidates, page/tile
provenance, ambiguity and review corrections through U9/U11.

Distinguish line crossing from connected junction, dash breaks from continuity,
nearby structural lines from wiring, and unresolved endpoint associations from
confirmed symbol/panel links. Do not join distant fragments or infer circuits
solely because a panel and devices exist. Preserve incomplete visible fragments.

No visible wiring must produce empty observed routes. Poor/occluded evidence
must report unknown/partial, not a confident no-wiring conclusion. A route
without approved elevation/scale remains candidate evidence; do not invent
height merely to satisfy K1's elevated points.

Verify: positive wiring, true no-wiring and unreadable cases, crossed lines with
and without junctions, broken/dashed fragments, tile seams, false connections,
deterministic fusion, endpoint references, human corrections/reload and approved
canonical route provenance. Measure U5 wiring metrics on development validation.
No A*, wire/conduit sizing, generated path design, quantities or PEC-compliance
claim. Any tuning needed uses approved non-test data and a new inactive release.

## 16. U13 — Durable end-to-end local interpretation jobs

Implement the actual bounded worker/orchestrator using PRE9, not a competing
queue/state system. F2 returns promptly; worker claims one authorized job,
prepares/classifies its pages, collects evidence, invokes U8, validates/fuses,
persists U11 candidates and finishes only after durable reviewable output exists.
Freeze run configuration/model release so a mid-job switch cannot mix results.

Map stages to truthful PRE9 progress. Handle cancellation before claim, during
render/inference, before persistence and after persistence-before-acknowledgment.
Use attempt/lease fencing at final writes: expired/replaced/cancelled workers
must not publish late results. Retry idempotency must prevent duplicate run
versions and partial artifacts from becoming successful output.

Maintain a document/page outcome ledger. Non-plan pages may be explicitly
excluded; unsupported/failed/partial plan pages are visible and require action.
Support safe page/floor/region selection without silently assigning different
floors or merging coordinate planes. Never claim whole-PDF success from page 1.

Connect workspace status/history/reload and review links to persisted output.
Retain explicit Start/Analyze semantics. If providing an Upload and analyze
shortcut, make it an explicit user action after successful storage, reuse the
existing protected start flow, and handle uncertain upload/start outcomes
without duplicate jobs. Reads, polling and page reload never enqueue work.

Completed means reviewable candidates, NOT approved geometry or model training.
Designer review/save remains explicit. Admin cannot start/cancel/save merely
because UI controls are hidden.

Verify real worker plus deterministic fakes: two-worker claims, queued/active
cancellation, lost lease, late output, crash at each stage, restart/recovery,
bounded retries, out-of-memory/timeout, unavailable model, database failure,
persist-before-ack replay, authorization, multipage outcomes, reload and originals.
Run an authorized isolated end-to-end upload-to-review-to-approved-layout case;
do not seed or modify protected live production records merely for a screenshot.

## 17. U14 — Shadow evaluation, signed promotion and tested rollback

Freeze the complete release candidate: model, adapter, prompt, reference pack,
decoding, preprocessing/fusion, candidate schema and canonical adapter versions.
Run non-authoritative shadow cases on approved inputs and record discrepancies.
Compare untuned base and available YOLO/CV results with identical approved metric
rules. If no usable YOLO weights exist, disclose that limitation and use a real
disabled-interpreter/manual-review rollback; do not fabricate a comparison run.

Open the sealed test set only now for the fixed candidate. Apply U5 thresholds
unchanged, with all required classes/source groups and hard safety gates.
Report raw denominators and uncertainty/coverage; never claim general accuracy
from inadequate samples. No threshold lowering or prompt tuning on test results.
A failed candidate stays inactive. A later changed candidate needs independent
holdout evidence or clear disclosure that reused test data is no longer untouched.

Obtain the actual independent signed VED release decision bound to the release
manifest and evaluation. This prompt does not sign it. Demonstrate bounded local
runtime, privacy/egress, memory/latency, valid coordinates, review-before-canonical,
unchanged originals and historical record readability.

Promote through an explicit versioned local release switch only after all gates
pass. Test pre-activation validation, new-job adoption, in-flight job pinning,
rollback with bad/missing model artifacts and post-rollback history/review access.
Never roll back by deleting candidates/layouts or restoring an old database.

Run actual browser end-to-end verification in an isolated authorized test setup:
unannotated upload, processing/page outcomes, legend/wiring evidence, review,
approved scale/elevation, canonical save/reload and K5 edit preservation.
Record screenshots privately. If browser or required data is unavailable,
report NOT TESTED/BLOCKED and do not claim a verified live user workflow.
Automated UI tests remain required but are not manual-browser evidence.

Do not remove YOLO code/dependencies in this sequence. Record retirement as a
future separately reviewed cleanup after the rollback-retention decision.
Do not start L2 or claim working 3D/routing/cost/report generation.

## 18. Verification, publication and checkpoint protocol

Apply this to EVERY U ticket, not just U14:

1. Record ticket scope, complete inherited acceptance criteria, affected modules,
   baseline state, dependencies and explicit out-of-scope items before editing.
2. Branch from verified main as codex/uN-short-description (N = 1 through 14),
   unless the user supplies another exact prefix. Work on one ticket at a time.
3. Implement the smallest coherent change; update affected maintained Markdown
   and a sanitized docs/U_VLM_PROGRESS.md ledger. Separate implementation,
   actual-data validation, human approval, activation and publication statuses.
4. Verify focused tests plus affected regression suites and all applicable
   privacy/data/geometry/authorization checks. Use existing test tooling.
   After production changes run full backend and frontend suites, compilation,
   dependency/environment checks, lint and build as applicable. For docs-only
   U1, use documentation/Git checks and cite—not rerun and relabel—PRE12 evidence.
   Run heavyweight suites sequentially if resource contention affects reliability.
5. Use isolated test databases/storage. Inspect cleanup behavior before live
   integration tests. Do not delete pre-existing rows/files or reset a database.
   Clean only proven run-owned fixtures under the authorized test boundary.
6. Inspect exact OpenAPI method/path and modeled/live table sets, not only counts.
   Counts may grow for scoped U changes; document each delta. create_all adds
   missing tables but cannot migrate existing ones. A required destructive or
   existing-table transformation needs a separate approved strategy.
7. Reconcile original hashes and pre-existing database rows. Authorized new U
   artifacts/data are expected to increase; manifest them separately instead of
   incorrectly requiring all artifact directories to remain empty forever.
   Keep evaluation and training state separate from protected live records.
8. Review complete diff and staged content for private data/secrets. Stage only
   explicit ticket paths; no broad add-all. Never commit private models, PDFs,
   crops, OCR, real prompts/labels, credentials or client-identifying evidence.
9. Commit the passing ticket with an accurate feat/test/docs message. Push its
   feature branch, set upstream and verify feature divergence 0 0.
10. Refresh remote main. If it moved, inspect/integrate legitimate changes and
    rerun affected checks before merge; stop for conflicts needing user choices.
    Do not force-push, overwrite others' work or bypass branch protection.
11. Merge with an explicit non-fast-forward commit:
    merge: complete U<N> <ticket description>
    Run the required post-merge focused/regression checks on main, including
    full applicable suites for production changes. Failed post-merge checks
    block pushing main; diagnose/fix within scope without hiding failed attempts.
12. Push main only after passing checks; refresh and verify origin/main...main
    is 0 0 and the feature still tracks its upstream at 0 0. If protections
    require a PR or review, report pending publication and follow that policy.
13. Publish the complete checkpoint below, then continue to the next authorized
    ticket. No separate routine publication permission is needed. Genuine gates
    still stop dependent work. Finish with a consolidated U14 closeout.

Maintain a durable per-ticket ledger before commit; report the resulting commit
and merge hashes in the external checkpoint after publication. Do not amend
history endlessly to place a commit's own hash inside itself. Later tickets
may append prior publication IDs to the ledger.

## 19. Mandatory progress report after each implementation/publication

Use this format and provide actual results, not a promise to report later:

Ticket and outcome:
Implementation / real-data validation / human approval / activation statuses:
Dependencies verified:
Baseline commit:
Feature branch and upstream:
Feature commit:
Merge commit:
Feature divergence:
origin/main...main divergence:
Current branch and working-tree state:

Delivered behavior and files created/modified/deleted:
API/schema/dependency/configuration deltas:
Documentation inconsistencies found and corrected:
Every acceptance criterion: PASS / FAIL / BLOCKED / NOT TESTED, with evidence:
Focused tests and full suites (commands, totals, subtests, failures and reruns):
Lint / build / compilation / dependency / environment validation:
Actual model or training runs versus mocked tests:
Manual browser verification and private evidence location:
OpenAPI operations and exact modeled/live schema comparison:
Existing database and original-file integrity:
New run-owned artifacts/dataset/model manifests, hashes and version references:
Private Git/egress checks (without exposing private content):
Protected project_service.py blob and diff:
Cleanup performed, exact run-owned scope and recoverability:
Warnings, limitations and unresolved decisions:
Next ticket, whether started, and precise blockers if any:

Do not sum overlapping unittest and pytest counts. Do not mark PASS from
inspection alone when a test, real inference, training run or approval is required.
A pending push is not published; a trained adapter is not promoted; a generated
candidate is not verified geometry.

## 20. Final U1-U14 closeout and user handoff

Provide one consolidated matrix of all fourteen tickets with feature/merge
commits, publication, acceptance evidence and outstanding gates. Include:
- exact active local release/model/adapter/runtime and sanitized license record;
- actual training data eligibility/coverage and independent review evidence;
- validation and final-test metrics against unchanged approved thresholds;
- model/prompt/reference/schema/adapter hashes and reproducibility instructions;
- tested rollback target and command/workflow;
- verified upload/process/review/save/reload workflow and supported input limits;
- separate observed-wiring support and unresolved/unsupported cases;
- API/table changes, full final tests and original-data integrity;
- private storage/retention and no-automatic-training behavior;
- current Git synchronization and protected-file status;
- remaining product work, explicitly including L2+ and generated routing.

Give the user practical instructions for starting the local runtime/worker,
uploading a new unannotated drawing, resolving a missing legend/scale/elevation,
reviewing results, saving geometry and submitting eligible corrections for
separate dataset approval. State that generated plans are planning aids and
are not professionally approved electrical installation documents.

Only declare the whole U sequence complete if implementation, actual training,
required human/data approvals, release evaluation, rollback and publication
really pass. Otherwise finish with the exact completed tickets, blocked gate
and smallest required human action. Do not continue into another epic.
