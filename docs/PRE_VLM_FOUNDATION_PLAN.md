# Pre-VLM Foundation Plan

## 1. Purpose and stopping boundary

This plan closes repository gaps that would otherwise interrupt the local
multimodal migration in `LOCAL_VLM_MIGRATION_PLAN.md`. It does not install,
download, fine-tune, or run a VLM. It does not remove or replace the implemented
YOLO path. PRE0-PRE12 must be completed and the readiness gate signed off before
U1 begins.

The current application baseline is L1, with PRE0-PRE12 foundations complete:
34 OpenAPI operations and 23 SQLAlchemy/MySQL tables. The implementation can
discover and reconcile persisted floor plans and bounded processing-job history
after a page reload, identify every source page, and verify registered derived
artifacts, collect authoritative scale/elevation inputs, and safely manage the
approved legend catalog, guarantee conditional/idempotent layout saves, and
control processing attempts safely, persist dataset-approver authority, and
freeze the canonical compatibility boundary. PRE12's readiness gate passes;
U1 has not started.

The foundation must preserve these boundaries:

- original uploads remain immutable;
- private drawings, references, annotations, prompts, and model artifacts do
  not enter Git or an unapproved hosted service;
- no production legend values, scale, elevation, or engineering rule is
  invented;
- current YOLO records and K1/K2 layout snapshots remain readable;
- frontend work remains JavaScript/JSX;
- FastAPI routes remain thin;
- schema changes use the approved prototype strategy and do not destructively
  reset live data without separate authorization;
- each ticket is committed, published, merged, verified, and reported before
  the next ticket begins.

PRE0 is complete and published. It established this maintained documentation
set and the private-artifact ignore baseline without changing application
behavior, dependencies, the then-21-operation API, or the 13-table schema. PRE1
is also complete and adds one read-only operation without a table. PRE2 is
complete and adds one bounded read-only operation without a table. PRE3 is
complete without a backend operation or table. PRE4 is complete with two
private source/page tables and verified backfill. PRE5 is complete with one
private processing-artifact manifest table. PRE6 is complete with two additive
reviewed-setting tables and three operations. PRE7 is complete with one
append-only history table and three Admin operations. PRE8 is complete with one
conditional-save request table and no new operation. PRE9 is complete with two
execution-control tables and one cancellation operation. PRE10 is complete with
one history-preserving authority table and four privacy-bounded operations.
PRE11 is complete with an accepted architecture decision and shared
cross-runtime compatibility fixture, without API or table changes. PRE12 is
complete with the published evidence in `PRE_VLM_READINESS_REPORT.md`. All
U-series work remains unimplemented.

## 2. Evidence-backed gaps

| Gap | Repository evidence | Why it blocks or risks migration |
|---|---|---|
| Persisted floor-plan discovery not yet consumed by UI | PRE1 adds the safe GET operation; the project UI still stores `sessionUploads` in React memory | PRE3 must reconcile persisted plans after PRE2 adds job history |
| Persisted recovery foundation complete | PRE3 consumes PRE1/PRE2 with abort-safe reconciliation and active polling | PRE4 can add immutable page identity without session-only UI assumptions |
| No page identity | `processing_jobs` references a floor plan, but no persisted PDF page entity exists | Multi-page plans, legends, schedules, and detail sheets cannot be tracked safely |
| Derived-artifact provenance foundation complete | PRE5 registers G1/G2 PNGs by job/source page and makes J1A resolve and revalidate the exact manifest row | Optional G3 debug output and future U7 tiles can use the bounded registry without fabricated legacy rows |
| No persisted source hash | `floor_plans` stores path, MIME, and size but no durable SHA-256 manifest | Reproducible training/inference provenance is incomplete |
| Reviewed floor elevation foundation complete | PRE6 stores append-only Designer-reviewed floor elevation with evidence and explicit unresolved state | Future adaptation can require approved values without inventing them or rewriting K1 history |
| Reviewed page scale foundation complete | PRE6 stores append-only per-source-page pixels-per-meter plus exact reference dimensions and evidence | Pixel candidates can be rejected when reviewed scale is absent or dimensions mismatch |
| Approved catalog management foundation complete | PRE7 adds Admin-only create/revise/all-status APIs and actor/time history without seed data | U4 can later build a reference pack only from deliberately managed active records |
| Conditional/idempotent layout saving complete | PRE8 adds an expected-version envelope, client UUIDv4, floor lock/compare, and durable request record | Stale writes and duplicate identical retries are rejected or reconciled before a K2 snapshot is appended |
| Processing execution-control foundation complete | PRE9 adds atomic single-owner claims, bounded leases, named-stage heartbeats, attempt recovery, and cancellation records/API | U13 can later orchestrate a chosen engine without inventing concurrency controls inside model work |
| Dataset-approver authority foundation complete | PRE10 persists one active human assignment plus full Admin-only history and a privacy-reduced current view | U5/U9 can later bind decisions to verified active authority without adding an OAuth role |
| Canonical compatibility decision complete | PRE11 freezes K1 v1, evidence ownership, fail-closed version negotiation, and the reserved version-2 domains | U2/U11 must follow the accepted ADR and shared fixture strategy rather than mutate K1 history |
| Prototype schema evolution is implicit | `create_all()` adds tables but does not transform existing tables | Tickets must avoid assuming an existing-table change has been applied |

## 3. Foundation data-flow target

```text
Project workspace reload
        ↓
Persisted floors → persisted floor plans → persisted job history
        ↓
Immutable source manifest → explicit source pages
        ↓
Versioned derived-artifact manifest
        ↓
Approved floor elevation + approved page scale evidence
        ↓
Approved legend catalog + assigned VED dataset approver
        ↓
Conditional/idempotent canonical layout saving
        ↓
Engine-neutral job claim/lease/cancel/retry primitives
        ↓
Canonical v2 compatibility decision
        ↓
PRE12 readiness gate
        ↓
U1 local-VLM hardware/privacy baseline
```

## 4. Foundation tickets

### PRE0 — Publish the documentation and privacy baseline

**Goal:** Turn the current reviewed Markdown and ignore rules into a clean,
auditable baseline before application changes begin.

**Dependencies:** Current L1 `main` baseline.

**Expected scope:** `AGENTS.md`, `.gitignore`, maintained Markdown documents,
and no application source.

**Implementation status:** Complete and published. The baseline protects the
private training/reference directories and local model/checkpoint formats,
tracks no private artifacts, and leaves application behavior unchanged.

**Acceptance criteria:**

- All mandatory documents are reread completely and compared with the current
  repository before editing.
- The pending documentation changes, local-VLM plan, pre-foundation plan, and
  Codex execution prompt agree on current versus planned behavior.
- Git ignore rules cover private blueprint/reference/training directories and
  local VLM weight/checkpoint formats such as `.gguf`, `.safetensors`, and
  adapter checkpoint directories without ignoring safe source code.
- `git ls-files` confirms that no private PDFs, rendered pages, labels, prompts,
  model weights, or training exports are tracked.
- The Roboflow URL/license metadata concern is reported; no remote deletion,
  publication, or permission change is attempted without explicit authority.
- No API, table, dependency, environment template, or application behavior is
  changed.
- The documentation feature branch and `main` are pushed and both track their
  remotes at `0 0` divergence.

### PRE1 — Add ownership-aware floor-plan discovery API

**Goal:** Make uploaded floor plans discoverable after reload without exposing
storage paths.

**Dependencies:** PRE0, D3, E3A, E3.

**Expected scope:** floor-plan response schemas, repository/service/route,
router registration if needed, OpenAPI assertions, and focused tests.

**Implementation status:** Complete and published. The API adds one read-only
operation, exposes no storage path or hash, performs no file or database write,
and leaves the schema at 13 tables.

**Acceptance criteria:**

- `GET /api/projects/{project_id}/floor-plans` returns authorized persisted
  plans with project-floor identity and safe metadata.
- An optional validated `project_floor_id` filter may narrow the collection;
  it cannot escape the project.
- Owning Designers and Admins may read; cross-owner and missing projects use
  non-disclosing behavior consistent with existing project APIs.
- Ordering is deterministic by floor order/identity and floor-plan identity.
- `storage_path`, private hashes, and filesystem details are not returned.
- Empty projects return `200` with `[]`; reads perform no writes or file access.
- Focused authorization, ordering, empty, validation, and sanitized-failure
  tests pass; the exact OpenAPI count is reported.

### PRE2 — Add processing-job history discovery API

**Goal:** Recover the job IDs and states associated with a persisted floor plan.

**Dependencies:** PRE1, F1-F3.

**Expected scope:** processing-job list schema/query/service/route and tests.

**Implementation status:** Complete and published. The read is bounded to 50
jobs by default and at most 100, returns only `floor_plan_analysis` history,
sanitizes failure details, and performs no job or file mutation.

**Acceptance criteria:**

- `GET /api/floor-plans/{floor_plan_id}/processing-jobs` returns authorized
  `floor_plan_analysis` jobs in deterministic newest-first order.
- Each safe summary includes job ID, type, status, progress, sanitized public
  error, and server timestamps needed for recovery.
- Owning Designers and Admins may read; cross-owner, missing, and mismatched
  access does not disclose existence.
- Empty valid history returns `200` with `[]`.
- Listing does not claim, retry, cancel, mutate, or run a job.
- Pagination is either implemented with a bounded contract or a documented
  conservative maximum prevents unbounded reads.
- Focused tests and exact OpenAPI count pass.

### PRE3 — Make the project workspace reload-safe

**Goal:** Use PRE1/PRE2 so persisted uploads and processing state survive a
browser refresh.

**Dependencies:** PRE1, PRE2, E4, F4.

**Expected scope:** frontend API clients, project workspace components, tests,
and accessible states. No backend production changes.

**Implementation status:** Complete and published. Persisted plans and bounded
job histories reconcile after reload, active jobs resume polling, completed
jobs retain review links, optimistic cards deduplicate by ID, and Admins remain
inspection-only.

**Acceptance criteria:**

- Persisted floor plans load for the selected project/floor after reload.
- Each plan shows safe metadata and its latest/history job state without
  depending on `sessionUploads`.
- The owning Designer can start a new job only when the backend allows it and
  can resume polling a discovered active job.
- Completed jobs expose the correct detection-review link using the persisted
  job ID; Admin remains inspection-only.
- Loading, empty, retry, session-expired, forbidden/not-found, stale response,
  abort, and unmount paths are tested.
- Session-only upload feedback may remain optimistic but reconciles with the
  server collection without duplicate cards.
- Full frontend tests, lint, and production build pass.

### PRE4 — Persist immutable source and page identity

**Goal:** Give every raster upload or PDF page a stable, verifiable identity
before VLM page classification exists.

**Dependencies:** PRE1, E1-E3, G1.

**Expected scope:** additive source-manifest/page models, upload transaction,
repositories/services, relationship registration, schema checks, and tests.

**Implementation status:** Complete and published. New uploads atomically store
the original SHA-256 and exact one-based page rows. The explicit dry-run/apply
backfill validates existing bytes and imported all six live raster sources
without changing their original files.

**Acceptance criteria:**

- An additive one-to-one source manifest stores a validated SHA-256 for each
  original floor-plan record without exposing it through normal APIs.
- A raster source creates exactly one page record; a PDF creates one record per
  validated page, using one-based unique page numbers.
- Page records carry only immutable source identity at this stage; they do not
  guess sheet type, legend status, floor, scale, or electrical content.
- Upload, manifest, and page rows commit atomically; storage compensation still
  removes only a newly written original if the database transaction fails.
- Existing floor plans receive a separately verified backfill/import strategy;
  no destructive reset or silent fabricated hash is allowed.
- Original bytes and current upload validation remain unchanged.
- SQLAlchemy and live schema match exactly; table counts, existing row counts,
  stored-original hashes, and focused/full regressions are reported.

### PRE5 — Add a durable processing-artifact manifest

**Goal:** Replace implicit derived-file assumptions with explicit job/page/hash
provenance while keeping derived files separate from originals.

**Dependencies:** PRE4, G1-G3, J1A.

**Expected scope:** additive artifact model/repository/service, integration at
existing derived-image boundaries, review-image resolution, and tests.

**Acceptance criteria:**

- Every registered artifact has processing-job ID, source-page ID, bounded
  artifact kind, safe relative path, MIME type, byte size, SHA-256, optional
  pixel dimensions, and creation time.
- The registry supports current G1 render, G2 normalized image, optional G3
  debug outputs, and later U7 tiles without inventing those future artifacts.
- Path containment, symlink, hash, MIME, and dimension checks occur before an
  artifact is trusted or served.
- J1A resolves its normalized review image through exact manifest provenance;
  it does not fall back to an ambiguous filename convention.
- Retry registration is idempotent for identical content and rejects conflicting
  reuse.
- Existing derived files require an explicit verified import path or remain
  unregistered; no fake rows are created.
- Originals remain unchanged and full storage/database regressions pass.

### PRE6 (complete) — Persist Designer-approved floor elevation and page scale

**Goal:** Supply the explicit metric inputs required for deterministic K1
adaptation without allowing the VLM to guess them.

**Dependencies:** PRE4, H2, K1-K3.

**Expected scope:** additive analysis-setting records, thin read/update APIs,
minimal Designer UI, validation, authorization, and tests.

**Acceptance criteria:**

- Project-floor elevation and per-source-page scale are stored in additive
  records rather than relying on an un-applied existing-table alteration.
- Values are finite, bounded, unit-explicit, and carry source/evidence notes,
  reviewer user ID, and timestamps.
- Owning Designers may create or revise values; Admin is read-only unless the
  documented authorization decision explicitly says otherwise.
- Scale supports an unresolved state; no DPI-, paper-, floor-name-, or
  sort-order-based metric value is invented.
- K1 snapshots remain self-contained and historical values do not change when
  settings are later revised.
- Safe APIs/UI expose missing/unverified state clearly and do not block upload.
- Focused geometry/API/UI tests and full regressions pass.

### PRE7 (complete) — Implement approved symbol-legend administration

**Goal:** Make the existing empty J3A catalog operational before U4 builds a
local reference pack.

**Dependencies:** PRE0, J3A, P3 requirements.

**Expected scope:** Admin-only create/update/activate/deactivate operations for
the current catalog, safe all-status retrieval, audit-ready history or snapshots,
frontend management only if required by the approved P3 scope, and tests.

**Acceptance criteria:**

- Only Admin can manage catalog records; Designers retain active-only reads.
- Class ID/name normalization and uniqueness remain enforced consistently in
  API, service, and database boundaries.
- Deactivation never deletes or rewrites historical detection, correction,
  manual-symbol, or layout snapshots.
- No production VED/PEC classes are seeded or inferred by Codex.
- Changes record actor and time through an append-only history/audit-ready
  mechanism approved for the prototype.
- Private glyph/reference files are not returned by ordinary catalog APIs.
- Empty catalog remains valid; focused authorization, conflict, history, and
  regression tests pass.

### PRE8 (complete) — Add conditional and idempotent layout saving

**Goal:** Prevent silent stale writes and duplicate K2 versions before
machine-assisted geometry creates more save activity.

**Dependencies:** K2, K3, K5.

**Expected scope:** expected-version contract, client request identity,
additive idempotency record if required, K3 service/API, K5 client, and tests.

**Acceptance criteria:**

- A Designer save identifies the current version it was based on and carries a
  bounded client-generated idempotency UUID.
- The server locks and compares the authoritative current version before
  inserting the next K2 snapshot.
- Stale expected versions return a sanitized `409` with no new snapshot.
- Repeating an identical successful request returns the original result without
  another version; conflicting UUID reuse returns `409`.
- First-layout creation has an explicit, tested no-current-version contract.
- Admin remains read-only; authorization and complete K1 validation are
  unchanged.
- K5 reconciles success/retry/conflict without claiming unsupported atomicity.
- Historical K2 snapshots remain append-only and full backend/frontend tests
  pass.

### PRE9 — Add engine-neutral processing execution controls

**Goal:** Establish durable worker claim/lease/attempt/cancellation primitives
without implementing a worker or VLM pipeline.

**Dependencies:** PRE2, F1-F4.

**Expected scope:** additive execution/attempt records, repository/service
primitives, cancellation request API/UI if approved, and concurrency tests.

**Implementation status:** Complete and published. PRE9 adds durable attempt and
cancellation records, single-owner transactional claims, bounded leases,
named-stage heartbeats, deterministic retry/expiry/terminal rules, explicit
legacy-row recovery, and owning-Designer queued/cooperative cancellation. It
does not add a worker, scheduler, or AI/CV execution.

**Acceptance criteria:**

- A queued job can be claimed atomically by one worker identity for a bounded
  lease and attempt number.
- Heartbeat/lease renewal, expired-lease recovery, success, failure, retry
  exhaustion, and process-crash scenarios have deterministic state rules.
- An owning Designer can request cancellation; the contract distinguishes a
  queued cancellation from cooperative cancellation of active work.
- Progress is tied to named measurable stages and never advances on a timer.
- The foundation does not execute G1-G3, H1-H3, YOLO, or a VLM.
- Existing job records remain readable and require a verified compatibility or
  backfill path.
- Concurrent claim tests prove that two workers cannot own one active attempt;
  API, schema, and regression checks pass.

### PRE10 — Persist VED AI Dataset Approver authority

**Goal:** Turn the documented reviewer policy into an auditable local authority
assignment before gold data exists.

**Dependencies:** PRE0, C3-C4, reviewer policy.

**Expected scope:** additive assignment/history model, Admin management API,
safe current-assignment retrieval, privacy decisions, and tests.

**Implementation status:** Complete and published. PRE10 persists a single
active assignment to an existing application user, preserves deactivated rows,
keeps qualification/reference details Admin-only, exposes only a reduced active
view to authenticated users, and rejects Admin self-assignment. It creates no
review decision; U5/U9 must also reject proposal-author self-approval when those
records exist.

**Acceptance criteria:**

- A dataset approver is an assigned application user, not a model, Codex, or a
  new OAuth identity role invented by the frontend.
- Assignment records capture active dates, assigning Admin, VED authority,
  qualification category, and only the minimum approved professional-reference
  data.
- Activation/deactivation is append-only or history-preserving.
- Ordinary users cannot enumerate private qualification/license details.
- No review decision is implemented yet; U5/U9 will reference an active
  assignment and retain its snapshot.
- Self-approval and independence policy is decided explicitly and tested rather
  than assumed.
- Authorization, privacy, schema, and regression tests pass.

### PRE11 — Freeze canonical-geometry compatibility decision

**Goal:** Decide how future interpreted pages, openings, panels, and route
provenance will reach canonical geometry without breaking K1 v1 history.

**Dependencies:** PRE4-PRE6, K1-K5, L1, M1 requirements.

**Expected scope:** architecture decision record and versioned fixtures only,
unless a separately approved implementation sub-ticket is necessary. Do not
guess electrical engineering semantics.

**Implementation status:** Complete and published. ADR 0001 keeps K1 version 1
strict and natively readable, assigns source-page/region and raw evidence to
candidate/review records, reserves an additive canonical version-2 extension for approved
source-plane references, openings, panels, optional symbol orientation/bounds,
and route provenance, and requires a new version-1 snapshot plus transactional
extension instead of changing the existing database constraint or performing
read-time rewrites. The shared compatibility matrix is exercised by Python and
JavaScript. No version-2 extension schema or persistence is implemented.

**Acceptance criteria:**

- The decision explicitly covers source document/page/region identity,
  openings needed for 3D, electrical-panel identity, symbol orientation or
  bounding data if needed, and observed-versus-generated route provenance.
- It states which information belongs in VLM candidate data, review records,
  canonical geometry, or later routing models.
- K1 v1 and existing K2 snapshots remain readable; the version negotiation or
  deterministic upgrade policy is specified.
- Python and JavaScript fixture strategy is defined before schema implementation.
- Unsupported or professionally undefined fields remain nullable/unknown or
  deferred; no fabricated defaults are approved.
- U2 and U11 dependencies are updated to the accepted decision.

### PRE12 — Run and publish the pre-migration readiness gate

**Goal:** Prove the foundations are coherent before U1 begins.

**Dependencies:** PRE0-PRE11.

**Implementation status:** Complete and published. The consolidated evidence is
maintained in `PRE_VLM_READINESS_REPORT.md`. All functional, schema, storage,
privacy, documentation, protected-file, test, and Git publication gates pass.
No U1 branch, VLM dependency, model, training run, or external-service mutation
was created.

**Acceptance criteria:**

- A clean reload can discover a project, floor, floor plan, and processing-job
  history and can resume monitoring an active job.
- Every original has verified source/page identity and every trusted derived
  image used for review has exact artifact provenance.
- Missing scale/elevation and an empty legend catalog fail safely without
  invented values.
- Conditional/idempotent layout-save and concurrent job-claim tests pass.
- An active approver can be identified without exposing private details.
- The canonical compatibility decision is accepted and referenced by U2/U11.
- Full backend/frontend suites, compilation, dependency checks, lint, build,
  OpenAPI count, SQLAlchemy/live schema equality, live row counts, original
  hashes, artifact counts, Git status, and protected-file hash are reported.
- All maintained Markdown matches the actual implementation; stale roadmap,
  table, operation, test-total, and next-ticket claims are corrected.
- `main` and every PRE feature branch are published and at `0 0` divergence.
- U1 is not started in PRE12.

## 5. Required execution and publication protocol

For every PRE ticket:

1. Read `AGENTS.md`, `README.md`, `backend/README.md`,
   `docs/ARCHITECTURE.md`, and `docs/FUNCTIONAL_SPEC.md` completely, plus this
   plan and the local-VLM plan.
2. Inspect the current branch, `origin/main`, status, untracked files, exact
   relevant implementation, tests, live schema, storage, and protected file.
3. Do not begin if remote main moved, the prior ticket is unpublished, private
   data is tracked, or the working tree contains an unexplained overlapping
   change.
4. Create `feature/pre<n>-<short-name>` (for example,
   `feature/pre1-floor-plan-discovery`) from the verified main baseline.
5. Implement only the named ticket; preserve unrelated user changes.
6. Update all maintained Markdown claims affected by the ticket in the same
   feature change.
7. Run focused tests and proportionate full regression, structure, database,
   storage, privacy, and artifact checks.
8. Review the complete diff, stage explicit paths only, commit, push the feature
   branch, and verify upstream divergence `0 0`.
9. Recheck remote main, merge with an explicit non-fast-forward merge commit,
   rerun required verification on `main`, push, and verify
   `origin/main...main = 0 0`.
10. Publish a progress report, then continue to the next authorized PRE ticket.

No destructive database reset, deletion of existing uploads/rows, hosted-service
action, model download, VLM dependency, or YOLO removal is authorized by this
plan. If one becomes necessary, stop and request explicit approval with the
exact target and recovery consequences.

## 6. Mandatory progress report after every ticket

Each ticket report must include:

- ticket and outcome;
- baseline, feature branch, feature commit, merge commit, upstreams, and both
  divergence checks;
- created/modified/deleted files;
- implemented behavior and boundaries intentionally left unchanged;
- every acceptance criterion marked `PASS`, `FAIL`, `BLOCKED`, or `NOT TESTED`;
- focused and full test totals, lint/build/compilation/dependency checks;
- exact OpenAPI operation and SQLAlchemy/live table counts;
- database row-count comparison, original-upload size/hash comparison, derived
  artifact and model artifact counts;
- documentation contradictions found and corrected;
- protected `backend/app/services/project_service.py` diff and blob hash;
- warnings, manual/browser verification, cleanup performed, and whether cleanup
  is recoverable;
- next ticket status and any authority needed.

Progress must be reported truthfully. A missing browser, unavailable database,
unknown domain rule, failed suite, or unverified external privacy setting is
`BLOCKED` or `NOT TESTED`, never `PASS`.
