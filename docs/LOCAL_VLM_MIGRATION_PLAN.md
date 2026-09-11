# Local Multimodal Floor-Plan AI Migration Plan

Reading map: use §1 for demo scope, the matching §13 entry for a U ticket, and
only its relevant policy sections. The [handoff §2](CODEX_U_VLM_MIGRATION_PROMPT.md#2-ticket-scoped-context-and-baseline)
maps those dependencies. Read selected criteria completely; unchanged unrelated
tickets need not be loaded. Current results belong in U_VLM_PROGRESS.md, not
duplicated throughout this specification.

## 1. Decision and status

### Current priority: U1–U14 development; real datasets deferred

September 11 user amendment: continue all feasible U implementation now while
datasets wait. The execution matrix and scope in handoff §0 supersede the older
demo-only stopping point and data-gated ban on independent downstream coding.
Dependencies on actual code/contracts remain; synthetic fixtures can verify
implementation but cannot pass real-data, training, accuracy or release criteria.
Record implementation and real-data acceptance separately. Preserve working demo
behavior, pending approvals and all original final acceptance criteria below.
No new automatic training or production model activation is authorized by this
deferral. Publish tested development portions under existing permissions without
claiming entire U tickets passed. Finish with the remaining evidence checklist.

### Active priority: September 10, 2026 development demo

On September 9 the user changed the immediate objective: upload a floor plan,
obtain automatic room and electrical-symbol proposals, review/correct them,
and see aligned 2D and basic 3D output by September 10 (Asia/Singapore).
This is a target date, not a guarantee of measured quality or completion.
The demo track below records the earlier priority, superseded by the amendment above.
It is a bounded development milestone, not completion of the full product MVP.

**Scope and gate exception:** U3 remains blocked for the original corpus/release
sequence. Its eight pending classifications, degraded-quality decision and
missing independent sealed-test project are not silently approved. They do
not block implementing and exercising the separate demo on readable,
VED-authorized development inputs. Do not repeatedly recheck an unchanged U3
gate instead of implementing the demo. Fine-tuning (U10), observed wiring
(U12), generated routing, costing, full Admin dataset tooling and production
promotion (U14) are deferred for this milestone. Sealed-test evidence remains
required for a later production-release claim, not for this development demo.
Existing test members must stay sealed; development-exposed drawings cannot be
renamed as untouched tests. No corpus-eligibility validator is weakened.

**Authorized draft-preview amendment:** unfinished room-first 2D and illustrative,
relative-height 3D may share the current draft without metric approval or a
symbol legend. Draft save/reload does not approve a measured canonical layout.
The flow below remains the measured-layout acceptance target.

**Minimum user-visible flow:** existing authenticated project/floor workflow
-> immutable image upload (or explicit selection of one PDF plan page)
-> Analyze -> real persisted room/wall and symbol proposals with 2D overlays
-> explicit Designer correction/approval and scale/height input
-> saved shared canonical geometry -> aligned Konva 2D and Three/R3F 3D
floor/room surfaces, wall extrusion and simple symbol markers -> reload.
No upload-time annotations are required. Human-reviewed annotations are only
needed to measure detection quality or later prepare training data.

**Measured development target:** at least 50% room recall and 50% symbol recall,
separately, on a small fixed set of readable development pages reviewed by the
user. This is not a detector-confidence setting or a 50% whole-plan accuracy
claim. Freeze the page list and matching rules before measuring: one-to-one
room-polygon matches at IoU >= 0.5, and one-to-one same-class symbol-box matches
at IoU >= 0.5. Count unmatched/duplicate predictions as false positives; report
TP, FP, FN, precision and recall for rooms and symbols, per page and symbol
class, with raw denominators. Room-name OCR accuracy is separate. Exclude
legend examples from installed-device truth. Use at least two reviewed pages
with both target types if available; otherwise report limited sample coverage.
Unresolved ground-truth regions must be declared and excluded transparently,
not used to inflate recall. Missing reviewed truth means quality NOT TESTED;
below-target results mean target FAIL even if the integration works. Manual
corrections never count as automatic detections. Report development-set reuse;
do not imply independent generalization evidence.

**Time-boxed implementation order (separate small checkpoints):**

| Step | Deliverable and owners to reuse | Acceptance / stopping point |
|---|---|---|
| DEMO-0 | Inspect current code, weights, hardware and working tree; freeze a narrow single-floor demo and baseline | State actual reusable components and missing integration; do not restart U1/U2 or wait for a sealed test project |
| DEMO-1 | Real bounded local room/wall and symbol inference; reuse G/H/I and U2 validation, with only necessary U4/U6-U8-style pieces | New uploaded pixels produce finite source-bound candidates; supported classes use the drawing legend; unknowns and failures remain visible |
| DEMO-2 | Durable Analyze/review/save path; minimum U9/U11/U13-style integration with PRE4-PRE10 and K1-K5 | Correct/add/reject rooms, walls and symbols; approve project geometry explicitly; save/reload the same source-bound canonical snapshot |
| DEMO-3 | Bring forward the minimum L2-L5 behavior | Render canonical room/floor surfaces, walls and simple verified-symbol markers; 2D edits survive save/reload in 3D; known-coordinate tests pass |
| DEMO-4 | Actual upload-to-2D/3D demonstration and quality measurement | Real browser run, source integrity, restart/reload and failure checks; report integration separately from the two 50% recall targets |

Start with the existing implementation, not a mandatory new large-model bake-off.
Within the first implementation checkpoint, inspect whether usable local YOLO
weights actually exist and whether a small pinned local VLM is already usable.
The measured GPU has 4 GiB VRAM; do not assume a model fits. Select the fastest
honest local path: existing usable detector plus OpenCV room/wall proposals,
or a bounded local VLM only when its real load/inference fits existing U1 limits.
If weights are absent, do not claim the YOLO path works; a clearly identified
legend-template/CV prototype may be used and measured instead. Do not label
heuristics as a trained VLM. Controlled public-model acquisition follows U1
privacy/license/budget rules and never downloads during startup/upload. No
hosted fallback, driver changes, cloud rental or training on unreviewed labels.
Time-box model exploration; preserve a running integration path and report
the actual provider and limitations rather than spending the entire window
on training or model downloads. Never return canned or filename-matched boxes
as detection output; synthetic fixtures are tests only.

**Non-negotiable geometry and review safeguards:** use one validated candidate
contract and one saved canonical model, not a parallel demo geometry database.
Persist provider/version/source provenance without fabricating YOLO identities
or confidence. Follow ADR 0001 and PRE8 for any required additive adaptation.
Pixels, render pixels and metric coordinates remain distinct. Obtain explicit
scale, floor elevation, wall height/thickness and any needed display parameters
through the existing approved-input workflow; do not guess measurements from
DPI or silently use a model-house preset. Missing metric inputs keep 2D
candidates reviewable and explain what is needed for metric 3D. Simple 3D
symbol markers need not imply real mounting height or equipment specifications.
Only explicitly reviewed geometry enters the canonical 2D/3D views; show
candidate overlays separately. Project review is not training approval.

Wiring is **not attempted** in this demo: retain an explicit not-attempted
capability/outcome, with no generated routes and no claim that an empty route
array proves the source has no wiring. Do not run quantities, costing or
engineering-compliance logic from this partial output. Legends are interpreted
in this order: current drawing's supplied legend, PEC, then other references;
none may silently invent an approved application class.

The full U/L ticket definitions below remain their completion criteria.
Track DEMO-0 through DEMO-4 separately in `U_VLM_PROGRESS.md`; partial reuse
does not complete U4-U14 or L2-L5. The earlier U-only prohibition on L2+ is
overridden only for this demo's floor/wall/symbol rendering and synchronization.
Use the demo execution amendment at the top of the existing handoff file.

The target AI architecture is changing from YOLO-only electrical-symbol
detection to a **locally hosted multimodal vision-language model (VLM)** that
interprets scanned floor plans. A text-only LLM is not suitable because it
cannot inspect image pixels. In this document, "local VLM" means an open-weight
vision-language model and VED-specific adapter that run on VED-controlled
hardware without sending private drawings to a hosted inference API.

This is a target architecture and implementation plan. I1-I4 YOLO remains the
legacy comparison/rollback path. The separate CV demo now has processing and
draft 2D/3D; it is not the production VLM pipeline. Consult the latest progress
checkpoint for implemented, trained, active and published status.

Before this migration begins, PRE0-PRE12 in
`docs/PRE_VLM_FOUNDATION_PLAN.md` close the repository's non-model readiness
gaps. U1 must not start until PRE12 publishes a passing readiness report.
PRE12 passes in `docs/PRE_VLM_READINESS_REPORT.md`, and U1's measured local-only
operating baseline passes in `docs/U1_HARDWARE_PRIVACY_BASELINE.md`. U2's
application-owned candidate contract is implemented and documented in
`docs/FLOOR_PLAN_INTERPRETATION_CANDIDATE_V1.md`. The complete U1-U14 handoff is
[`CODEX_U_VLM_MIGRATION_PROMPT.md`](CODEX_U_VLM_MIGRATION_PROMPT.md); when the
user assigns it, it authorizes the sequential tickets and their publication,
not bypassing human approvals or failed gates. No model/runtime implementation
or model selection is implied by U1/U2 completion.
PRE11 has accepted
`docs/decisions/0001-canonical-geometry-compatibility.md`; U2 and U11 must
follow its evidence ownership, fail-closed negotiation, and append-only
versioning rules.

The migration does not change these core rules:

- original uploads remain immutable;
- machine output is advisory until Designer review;
- only verified canonical geometry feeds 2D, 3D, routing, quantities, estimates,
  and reports;
- a model never writes Konva or Three.js state directly;
- observed wiring from the drawing is different from a system-generated route;
- professional electrical review remains required.

## 2. Meaning of "without annotation"

Users may upload ordinary JPEG, PNG, or PDF floor plans without sidecar labels,
boxes, polygons, or JSON. The production system should interpret those files
without asking the uploading user to prepare an annotated dataset first.

Unannotated scans alone do not state the correct symbol class, coordinates,
walls, room boundaries, scale, or wiring topology. They therefore cannot, by
themselves, supervise the exact structured output required by the application.
The project will use four distinct data levels:

| Data level | Contents | Permitted use |
|---|---|---|
| Raw private corpus | Immutable VED-approved scans with source manifests | Baseline inference, optional domain adaptation research, and pseudo-label generation |
| Pseudo-labeled corpus | Machine-generated candidate structure with model and prompt provenance | Review queue and experiments; never final ground truth by itself |
| Reviewed gold corpus | Candidate output corrected and approved by the VED AI Dataset Approver | Fine-tuning, validation, and accuracy measurement |
| Frozen test corpus | Approved examples isolated by source project before training | Final comparison only; never prompts, training, class design, or threshold tuning |

This approach removes the need to pre-annotate every incoming blueprint. The
system proposes the structure, and normal Designer review produces reusable
training examples over time. A small reviewed gold set is still mandatory
before a model can be released or an accuracy claim can be made.

Production uploads must not automatically retrain the active model. Training is
an explicit, offline, versioned operation over approved data. A released model
remains frozen until another candidate passes the full evaluation and approval
gate.

### What VED supplies and what automation supplies

For each drawing set, VED supplies only the source PDF/image plus information
that cannot be safely guessed:

- permission to use the drawing for inference only, evaluation, or training;
- project/drawing-set identity, sheet number/type, and whether pages belong to
  the same leakage group;
- the drawing-specific legend when present and any approved class crosswalk;
- traceable PEC/reference edition, part, page, and permitted-use metadata;
- known scale/elevation evidence when the scan does not state it clearly;
- whether visible wiring should be captured as source evidence; and
- the named VED AI Dataset Approver for release decisions. PRE10 persists this
  as an application authority assignment rather than a third OAuth role. The
  assigning Admin cannot assign themselves, and U5/U9 must enforce that an
  approver cannot approve a proposal or annotation they authored.

The system/Codex may hash and inventory originals, render pages, identify plan
regions and legends, create tiles, run OCR/line extraction, propose structured
pseudo-labels, generate review overlays, check completeness, convert approved
records into training format, run experiments, and assemble evaluation reports.
Those actions do not constitute final approval. VED's assigned reviewer decides
class meaning, ambiguous geometry, completeness, and whether a record may enter
a training or gold release.

Before U6, VED also supplies access to the intended inference/training machine
so U1 can measure rather than guess its resources. More floor plans improve
coverage only when source groups, permissions, review status, and duplicates
are controlled; volume alone does not create trustworthy targets.

## 3. Target processing flow

```text
Authenticated floor-plan upload
        |
        v
Immutable original storage + SHA-256 manifest
        |
        v
PDF page rendering when needed (G1)
        |
        v
Normalized RGB source image (G2)
        |------------------------------|
        |                              |
        v                              v
Whole-page overview              Overlapping high-resolution tiles
        |                              |
        |                    Local OCR + line/shape evidence
        |                              |
        |------------------------------|
                       |
                       v
         Local VLM + approved VED legend context
                       |
                       v
         Schema-constrained candidate JSON
                       |
                       v
      Deterministic validation, coordinate remapping,
       tile deduplication, and evidence-based fusion
                       |
                       v
         Versioned machine interpretation result
                       |
                       v
          Designer review and correction
                       |
                       v
          Deterministic K1 adapter and K2 snapshot
              |             |             |
              v             v             v
           Konva 2D     Three.js 3D   Routing engine
                                         |
                                         v
                              Quantities and estimates
```

The diagram describes logical inputs, not permission to derive all tiles from
G2's reduced image. U7 preserves a bounded higher-resolution oriented raster
or PDF render separately, with explicit reversible transforms into the G2/K1
reference plane (currently at most 4096 pixels per edge). Cropping or upscaling
a reduced reference does not recover lost glyph detail. PRE6 approval must
match that reference plane; DPI is never architectural scale.

G3 thresholded imagery and H1 line candidates may remain auxiliary evidence,
but the local VLM receives the normalized RGB page because thresholding can
remove text, line-weight, color, and legend information. OpenCV remains useful
for deterministic geometry proposals and validation; it is not the semantic
source of truth.

## 4. Machine interpretation contract

The VLM must not emit K1 canonical geometry directly. It produces a separate,
strict, versioned `FloorPlanInterpretationCandidate` document. The planned
contract includes:

- source floor-plan, processing-job, page, image dimensions, and source hash;
- model release, base-model revision, adapter revision, prompt/schema version,
  inference parameters, and runtime version;
- page type and whether electrical content, a legend, dimensions, scale evidence,
  and drawn wiring are visible;
- OCR observations with bounded source regions and normalized text;
- scale candidates with explicit evidence and an unresolved state;
- wall and room candidates in source-pixel coordinates;
- symbol candidates with approved class identity, box, center, evidence tile,
  and review state;
- electrical-panel candidates;
- observed wiring/conduit polylines only when visible in the source;
- ambiguity, truncation, conflict, and incomplete-page warnings;
- deterministic IDs and source-pixel ordering.

All coordinates must be traceable to the normalized source image. Tile-local
coordinates are converted to page coordinates before persistence. The validator
rejects unknown fields, non-finite values, out-of-bounds geometry, invalid
polygons, impossible class IDs, missing provenance, and malformed route graphs.

Model-written confidence text is not assumed to be calibrated probability. The
application derives review priority from deterministic checks, cross-pass or
cross-model agreement, source visibility, and later measured calibration. Every
candidate begins as `needs_review`. U1-U14 authorize no automatic acceptance
into canonical geometry, regardless of model score.

The application, not generated text, supplies and verifies job/source/artifact
IDs, hashes, release identity, and human review state. Unknown-class candidates
have an explicit unresolved mapping and cannot enter the approved catalog or
canonical symbols. U2 includes openings and optional orientation/bounds under
ADR 0001, without inferred dimensions or engineering attributes.

## 5. Local model strategy

VED should not train a foundation VLM from random initialization. That would
require a very large image-text corpus and substantially more compute than this
project has established. The intended meaning of "our own local model" is:

```text
Pinned open-weight multimodal base model
        +
VED-owned prompt and output schema
        +
VED-trained LoRA/QLoRA adapter
        +
VED-approved class and reference pack
        +
Versioned local release manifest
```

The first model bake-off should include:

1. Qwen3-VL 4B Instruct as the initial resource-conscious candidate.
2. Qwen3-VL 8B Instruct as the quality candidate when available hardware permits.
3. Qwen2.5-VL 3B or 7B as a compatibility fallback with established visual
   grounding and local-runtime support.
4. Florence-2-large as an optional local grounding/OCR specialist, not as an
   automatic architectural source of truth.
5. PaddleOCR or PaddleOCR-VL as an optional local OCR/document-layout helper.

These are candidates, not an approved production choice. U6 selects a model
only after measuring the actual target machine, license, accuracy, latency,
memory, Windows/WSL deployment reliability, and structured-output compliance.

Parameter-efficient fine-tuning is preferred. LoRA keeps the base checkpoint
frozen and trains small adapter weights; QLoRA may be evaluated when memory is
limited. Full-model fine-tuning and training from scratch are out of scope until
the measured data and hardware justify them.

## 6. Local runtime and isolation

The model runtime must be process-isolated from FastAPI. FastAPI calls a local
model gateway over loopback or an authenticated private network. The gateway
must support image input, deterministic or bounded decoding, timeouts,
cancellation, health checks, request-size limits, and structured output.

Runtime candidates include Transformers for the first reproducible baseline,
llama.cpp when the selected multimodal checkpoint is supported, and a Linux/WSL
or dedicated GPU deployment using vLLM/SGLang when justified by benchmarks.
Training should use a separate environment from the application backend so
PyTorch, CUDA, Transformers, PEFT, TRL, OCR, and serving dependencies do not
destabilize FastAPI's pinned environment.

Requirements:

- no remote inference fallback;
- no automatic model download during application startup or a processing job;
- pinned model revision, license record, SHA-256 checks, and local path;
- model and adapter files excluded from Git;
- loopback binding by default;
- sanitized failures with no model path, prompt, source text, or stack trace in
  normal API responses;
- bounded concurrency so multiple large pages cannot exhaust host memory;
- raw prompts and outputs stored only in protected diagnostic storage with a
  defined retention policy.

## 7. High-resolution blueprint interpretation

Large floor plans cannot be reliably reduced to a single small model image.
The interpreter uses coordinated passes:

1. **Overview pass:** classify page/sheet type, find plan regions, title block,
   legend, scale notes, north arrow, and likely electrical content.
2. **Legend pass:** read the drawing-specific legend and align its visible
   entries with the approved VED class catalog. Unknown symbols remain unknown.
3. **Tile pass:** inspect overlapping high-resolution tiles with absolute tile
   offsets and stable page coordinates.
4. **Geometry pass:** combine VLM proposals with OCR and deterministic line/shape
   evidence for walls, rooms, dimensions, and observed routes.
5. **Fusion pass:** map tile results to page coordinates, merge duplicates,
   preserve disagreements, and emit completeness warnings.
6. **Validation pass:** enforce schema, bounds, topology, identity, and provenance
   before any result is stored.

Page regions, tiles, and crops are derived artifacts. They never replace or
modify the uploaded original.

## 8. Legends, PEC references, and retrieval

The drawing-specific legend is the first source for interpreting that drawing.
The approved `symbol_legends` catalog controls class identities accepted by the
application. PEC 2017/2020 material may be held locally as private reference
evidence, subject to provenance and licensing review; it must not be copied into
model releases or represented as training permission merely because it is
available to the project.

A local reference pack may provide short approved descriptions, aliases, sample
glyphs, and source citations to the VLM at inference time. Retrieval context is
advisory. It cannot activate a class, override a drawing-specific legend, or
make an uncertain mapping authoritative without VED approval.

## 9. Bootstrap and fine-tuning curriculum

### Stage A - zero/few-shot baseline

Run pinned candidate models on reviewed development/validation pages using a stable prompt
and candidate schema. This establishes whether a model can read the page, locate
symbols, and return usable coordinates before any training investment.

### Stage B - unannotated-domain experiments

Use private scans for non-supervised research such as image-quality robustness,
tile-policy selection, OCR adaptation, and, only if supported by a reproducible
method, domain-adaptive pretraining. This stage cannot claim task accuracy
without reviewed targets.

### Stage C - synthetic and weak supervision

Generate synthetic plan fragments using only approved VED legend glyphs and
licensed fonts/assets. Combine deterministic OpenCV/OCR proposals and VLM
outputs to create pseudo-labels. Retain producer versions and agreement scores.
Pseudo-labels remain review material, not gold truth.

### Stage D - VED review capture

Present candidate walls, rooms, symbols, panels, and observed routes over the
source image. The VED AI Dataset Approver accepts, corrects, adds, rejects, or
marks ambiguous elements. Store append-only correction provenance.

### Stage E - supervised adapter tuning

Convert approved examples to the selected model's image-and-conversation
format with strict candidate JSON as the assistant target. Train a LoRA/QLoRA
adapter, record parameters and data-manifest hashes, and keep validation/test
projects isolated.

### Stage F - release evaluation

Run the candidate once on the frozen test set. Compare it with the untuned base,
the legacy YOLO/CV baseline where applicable, and manual ground truth. A failed
candidate is retained as an experiment and never becomes active production
state.

## 10. Wiring and routing boundary

The interpreter must distinguish:

| Result | Meaning | Downstream treatment |
|---|---|---|
| `observed_route` | A wire/conduit path is visibly drawn in the uploaded plan | Preserve source polyline, evidence, and review state |
| `generated_route` | The system computes a path because no usable route is drawn | Produce later through the approved routing engine and rules |

If no wiring is visible, the VLM returns an empty observed-route collection. It
must not invent a path. If wiring is visible but ambiguous, it emits candidate
segments and an ambiguity warning. Only reviewed observed routes or deterministic
M-series generated routes enter canonical geometry.

The VLM does not perform A* pathfinding, wire sizing, conduit sizing, PEC
compliance decisions, or material costing. Those remain explicit backend domain
services with professionally approved rules.

## 11. 2D and 3D generation boundary

The VLM does not generate Konva nodes or Three.js meshes. After review, a
deterministic adapter converts approved source-pixel candidates into K1 metric
geometry using an explicit validated scale. K2 persists the complete snapshot.
Konva and Three.js consume that same snapshot.

This preserves reproducibility: the same approved K1 document must render the
same coordinates even if the active VLM, prompt, or adapter later changes.

## 12. Evaluation and release gates

U5 records numeric release thresholds before U6 model/prompt selection or U10
tuning, using VED requirements and non-test evidence. Development validation
may guide selection; the sealed final test set is opened only for U14 after
the candidate is fixed. Test results may not be fed back into tuning. A failed
candidate requires a documented new independent holdout for a new release
claim, or an explicit disclosure that reused data is no longer untouched test
evidence. Reproducibility reruns must not change the candidate. The
evaluation suite must report at least:

- schema-valid response rate and retry rate;
- page classification and electrical-content accuracy;
- symbol precision, recall, F1, count error, per-class confusion, box IoU, and
  center-coordinate error;
- wall endpoint, angle, segment-match, and duplicate-rate errors;
- room polygon validity and overlap where room truth exists;
- observed-wiring presence accuracy, segment/topology errors, and route-length
  error where source wiring exists;
- false-positive or hallucinated object/route rate;
- unknown/ambiguous-class handling;
- latency per page and tile, peak RAM/VRAM, model-load time, and timeout rate;
- performance by scan quality, page size, source company, and sheet type.

Hard safety gates apply regardless of model score:

- 100% of persisted results pass the strict candidate validator;
- zero out-of-bounds or non-finite geometry reaches review persistence;
- zero unreviewed model candidates enter authoritative K1 geometry;
- zero original uploads are modified;
- zero private blueprint bytes leave the approved local environment;
- zero project/drawing-set leakage exists between train, validation, and test;
- every active release has a pinned manifest, hashes, license record, evaluation
  report, and rollback target.

## 13. Detailed migration tickets

### U1 - Freeze migration requirements and hardware/privacy baseline

**Goal:** Record the exact target machine, privacy boundary, supported input
quality, page limits, concurrency, latency objective, and model-license policy.

**Dependencies:** PRE12 passing readiness gate; L1 current implementation
baseline.

**Acceptance criteria:**

- CPU, RAM, GPU, VRAM, operating system, CUDA/driver, and available disk are
  measured without guessing.
- Local-only means no remote inference, telemetry, source upload, or hosted fallback.
- VED approves whether training may use WSL/Docker or a separate GPU machine.
- Maximum page, tile, context, timeout, concurrency, and storage budgets are
  documented.
- No model is downloaded or selected in this ticket.

### U2 - Define `FloorPlanInterpretationCandidate` schema v1

**Goal:** Freeze the model-output contract before selecting or tuning a model.

**Dependencies:** U1, K1, and accepted PRE11 ADR 0001.

**Acceptance criteria:**

- Strict schema represents page metadata, source/model provenance, scale
  evidence, OCR, walls, rooms, symbols, panels, observed routes, and warnings.
- Candidate coordinates are source pixels and remain separate from K1 meters.
- Unknown and ambiguous values are representable without invention.
- Python validation and representative fixtures cover valid, empty, partial,
  malformed, out-of-bounds, and adversarial output.
- The schema contains no Konva or Three.js types.
- Source document/page/region evidence stays in candidate/review records and
  follows the PRE11 compatibility fixture; it is not added to K1 v1.

### U3 - Build private unannotated-corpus intake and split manifests

**Goal:** Accept VED-approved scans without requiring upload-time annotations.

**Dependencies:** U1.

**Acceptance criteria:**

- Original hashes, approvals, project groups, pages, image quality, and sheet
  types are recorded.
- Train, validation, and frozen-test membership is assigned by project/drawing
  set before pseudo-label generation.
- Duplicate and near-duplicate checks prevent leakage.
- Private inputs, derivatives, prompts, labels, and model artifacts remain
  excluded from Git.
- Original bytes remain unchanged.

### U4 - Build the approved local legend/reference pack

**Goal:** Provide local class grounding without turning private books or legend
pages into unreviewed truth.

**Dependencies:** U3, J3A.

**Acceptance criteria:**

- Every active class has a stable ID, approved name, aliases, description,
  sample-glyph provenance, and active state.
- Drawing-specific legend mappings are versioned and reviewable.
- Unknown symbols remain unknown instead of being forced into a known class.
- PEC/source copyright, edition, page, and permitted-use metadata are recorded.
- Retrieval cannot create or activate production classes.

### U5 - Create the frozen gold evaluation set and metric contract

**Goal:** Establish trustworthy ground truth and release thresholds.

**Dependencies:** U2-U4.

**Acceptance criteria:**

- The VED AI Dataset Approver reviews representative pages and signs each record.
- Gold data includes empty pages, hard negatives, dense symbols, multiple scales,
  poor scans within supported limits, and pages with/without drawn wiring.
- Metrics in Section 12 are reproducible and reported per class and source group.
- Numeric promotion thresholds and allowed regressions are approved before model
  tuning.
- Frozen test data is inaccessible to training and prompt selection workflows.

### U6 - Run a local VLM and grounding-model bake-off

**Goal:** Select a reproducible base model and runtime from measured evidence.

**Dependencies:** U1, U2, U5.

**Acceptance criteria:**

- Pinned Qwen3-VL 4B/8B and fallback candidates are evaluated where hardware
  permits; skipped candidates state the measured reason.
- Model license, revision, hashes, memory, latency, schema validity, and accuracy
  are recorded.
- All inference remains local and network egress is checked.
- The selected model beats documented minimum gates or the ticket reports no
  suitable candidate instead of forcing a choice.
- The legacy YOLO result remains available as a comparison, not hidden.

### U7 - Implement multi-resolution page, tile, and OCR context preparation

**Goal:** Preserve small symbols and full-page relationships for the chosen VLM.

**Dependencies:** U2, U6, G1-G3.

**Acceptance criteria:**

- Overview, legend, plan-region, and overlapping tile transforms are
  deterministic and reversible to page pixels.
- Normalized RGB is primary input; thresholded/line/OCR evidence is auxiliary.
- Tile overlap and deduplication behavior has fixtures and boundary tests.
- Derived files are isolated and originals remain unchanged.
- Page/tile limits fail safely before memory exhaustion.

### U8 - Implement the isolated schema-constrained local VLM gateway

**Goal:** Produce validated candidate documents without HTTP-route business
logic or cloud inference.

**Dependencies:** U2, U6, U7.

**Acceptance criteria:**

- Model loading is lazy, pinned, cached, and local-only.
- Requests include the approved prompt, reference-pack version, images, and
  strict output schema.
- Temperature/decoding, timeouts, cancellation, concurrency, and retry limits
  are explicit.
- Invalid or partial model text never bypasses Pydantic validation.
- Failures expose sanitized application errors and retain protected diagnostics.

### U9 - Generate pseudo-labels and capture VED review corrections

**Goal:** Turn unannotated scans into reviewable candidates and approved
training targets.

**Dependencies:** U4, U8, J2-J5.

**Acceptance criteria:**

- Pseudo-labels retain model, prompt, source, tile, and agreement provenance.
- Review supports symbols, walls, rooms, panels, scale evidence, and observed
  routes required by U2.
- Accept, correct, add, reject, and ambiguous decisions are append-only.
- Partially reviewed pages cannot enter the gold or supervised-training set.
- Codex/model proposals cannot approve their own output.

### U10 - Fine-tune and register a VED LoRA/QLoRA adapter

**Goal:** Produce the first VED-owned local adapter from approved targets.

**Dependencies:** U5, U6, U9.

**Acceptance criteria:**

- Only approved training examples and permitted synthetic data are used.
- Base weights remain pinned; adapter configuration, seed, hyperparameters,
  framework versions, data hashes, and checkpoints are recorded.
- Validation drives checkpoint selection without reading the frozen test set.
- Interrupted training can resume without corrupting prior releases.
- The adapter is not activated until U14 promotion.

### U11 - Persist candidate interpretations and build the K1 adapter

**Goal:** Preserve machine provenance and convert only approved candidates to
canonical geometry.

**Dependencies:** U2, U8, U9, K1-K3, and accepted PRE11 ADR 0001.

**Acceptance criteria:**

- Each machine run is immutable and associated with its processing job and
  model release.
- Raw candidate, validation warnings, and latest human decisions are retrievable.
- Deterministic conversion requires an explicit approved scale.
- Only approved walls, rooms, symbols, panels, and routes reach K1/K2.
- Existing historical YOLO detections and layout snapshots remain readable.
- Version dispatch is fail-closed; K1 v1 is read natively, and any approved
  version-2 extension is stored additively with a new append-only v1 base
  snapshot rather than rewriting history or weakening the v1 database check.

### U12 - Extract and distinguish observed wiring

**Goal:** Represent wiring/conduit drawn in the source without inventing missing
routes.

**Dependencies:** U2, U7-U9.

**Acceptance criteria:**

- Pages with no visible wiring produce an empty observed-route set.
- Visible routes retain source polylines, endpoints, evidence, and ambiguity.
- Tile fragments merge deterministically without impossible jumps.
- Reviewer corrections persist and can enter K1 only after approval.
- No A*, wire sizing, conduit sizing, or PEC compliance rule is implemented.

### U13 - Orchestrate the local interpretation processing job

**Goal:** Connect the existing durable job to the local page interpretation
pipeline without blocking the request.

**Dependencies:** U8, U11, U12, F1-F4.

**Acceptance criteria:**

- A worker claims jobs safely and advances only real measurable stages.
- Cancellation, timeout, process crash, restart, and retry behavior are defined.
- Idempotency prevents duplicate candidate versions from accidental retries.
- Original and derived-file protections remain enforced.
- Completed means persisted reviewable candidates exist; it does not mean
  professionally approved geometry.

### U14 - Shadow deployment, promotion, rollback, and YOLO retirement

**Goal:** Replace active YOLO inference only after the local VLM proves safe and
more useful on the approved evaluation contract.

**Dependencies:** U5-U13.

**Acceptance criteria:**

- VLM and legacy results run in shadow mode on approved evaluation inputs.
- The candidate passes numeric quality, schema, privacy, latency, and resource
  gates with a signed VED decision.
- Activation uses a versioned feature/config switch and has a tested rollback.
- Existing YOLO records remain readable and auditable.
- YOLO dependencies/code are removed only in a separately reviewed cleanup after
  rollback retention is no longer required.
- Model release, evaluation report, and active version are auditable.

## 14. Git and stopping protocol for every U ticket

Use the single execution protocol in [handoff §18](CODEX_U_VLM_MIGRATION_PROMPT.md#18-verification-publication-and-checkpoint-protocol)
and the compact evidence checklist in [§19](CODEX_U_VLM_MIGRATION_PROMPT.md#19-mandatory-progress-report-after-each-implementationpublication).
They govern separate tickets, branches, scoped staging, verification before/after
non-fast-forward merges, upstream checks and stopping on failed gates.

Reading this plan grants no publication authority. Assigning the handoff carries
its explicit scope and publication permissions; its current demo stop takes
precedence until the user resumes the U sequence. No private egress, invented
approval, destructive reset, paid resources, YOLO deletion or later epic is
authorized by this document.

Dependency clarifications (full implementation/tests are in the matching handoff
ticket): PRE12 proves foundation behavior, not populated approved data. U4 reuses
PRE7; U5/U9 reuse PRE10. U5 bootstraps gold offline before U9 UI exists. U6 uses an
experimental harness before U7/U8 production services and development validation
only. U9 owns durable runs/reviews; U11 reuses them and implements ADR 0001 with
atomic PRE8 saves and extension-preserving clients. U12 handles observed routes;
U13 reuses PRE9 with late-write fencing and explicit page outcomes. U10 requires
real training; U14 requires fixed-candidate evaluation, signed release evidence
and tested rollback. Missing YOLO weights mean comparison unavailable; a tested
disabled-interpreter/manual-review rollback is allowed. Missing data/approval
blocks dependent work even when infrastructure tests pass.

## 15. Source basis for the model bake-off

- [Qwen3-VL official repository](https://github.com/QwenLM/Qwen3-VL) documents
  open-weight multimodal models, local inference, deployment, and its official
  fine-tuning framework.
- [Qwen3-VL fine-tuning framework](https://github.com/QwenLM/Qwen3-VL/tree/main/qwen-vl-finetune)
  documents image/annotation records, visual-grounding conversion, and LoRA
  options.
- [Qwen2.5-VL official release](https://qwenlm.github.io/blog/qwen2.5-vl/)
  demonstrates point/bounding-box grounding and JSON-style output.
- [Hugging Face TRL VLM training](https://huggingface.co/docs/trl/en/sft_trainer#training-vision-language-models)
  documents supervised VLM datasets with image inputs and assistant targets.
- [Hugging Face PEFT LoRA guide](https://huggingface.co/docs/peft/main/conceptual_guides/lora)
  explains frozen base weights and lightweight trainable adapters.
- [llama.cpp multimodal documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
  documents local image input for supported models.
- [llama.cpp grammar documentation](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)
  documents JSON-schema/grammar-constrained generation; application validation
  remains mandatory.
- [Microsoft Florence-2 model card](https://huggingface.co/microsoft/Florence-2-large)
  documents local prompt-based object detection, grounding, OCR, and regions.
- [PaddleOCR-VL local pipeline](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md)
  documents local document parsing and runtime options.

Model capabilities, licenses, dependencies, and runtime support must be pinned
and reverified during U6 rather than assumed from this planning snapshot.
