# Local VLM Migration Progress

This ledger separates implementation, real-data validation, human approval,
activation, and publication. A checked implementation item is not equivalent
to a trained or released model.

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
