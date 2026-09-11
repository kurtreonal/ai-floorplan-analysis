# Local VLM Migration Progress

This ledger separates implementation, real-data validation, human approval,
activation, and publication. A checked implementation item is not equivalent
to a trained or released model.

## Resume index

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
| U3 | Implementation PASS; real-data acceptance blocked | Synthetic validation and real private intake executed; actual eligible coverage is zero sources/pages | Covered blueprint permission recorded; one degraded-page decision and eight page classifications remain; third-party references stay excluded | Not applicable | Implementation publication in progress after demo reconciliation | Private visual review is ready; encryption is deferred risk, not blocker; no genuine frozen-test project exists |
| U4 | Not started | Not started | Not started | Not applicable | Not published | Depends on U3 and approved catalog data |
| U5 | Not started | Not started | Missing | Not applicable | Not published | Requires independent human-approved gold and thresholds |
| U6 | Not started | Not started | Not started | Not activated | Not published | Requires measured target hardware and passing U5 |
| U7 | Not started | Not started | Not applicable | Not applicable | Not published | Depends on U2 and U6 |
| U8 | Not started | Not started | Not applicable | Not activated | Not published | Depends on U2, U6, and U7 |
| U9 | Not started | Not started | Missing | Not activated | Not published | Requires actual human review decisions |
| U10 | Not started | Not started | Missing | Not activated | Not published | Requires approved training records and compute |
| U11 | Not started | Not started | Not started | Not activated | Not published | Depends on U9 durable review records |
| U12 | Not started | Not started | Not started | Not activated | Not published | Observed wiring only |
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
- U4 has not started.

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
