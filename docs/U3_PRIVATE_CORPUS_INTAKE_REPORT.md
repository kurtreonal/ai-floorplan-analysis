# U3 Private Corpus Intake Report

- Ticket: U3
- Inspection dates: 2026-09-07 through 2026-09-09 (Asia/Manila)
- Implementation status: PASS and ready for scoped publication
- Real-data acceptance status: BLOCKED after safe real intake
- Baseline: U2 merge `3f12087`
- Latest safe implementation: `d427be2`

This report is sanitized. It contains no source names, paths, full hashes,
drawing text, labels, reviewer identity, or private approval evidence.

## Safe implementation completed

The feature branch implements local-only intake tooling under
`backend/app/ai/floor_plan_interpretation/corpus_intake.py` and a quiet command
wrapper at `scripts/intake_vlm_corpus.py`. Synthetic tests prove:

- strict purpose-specific permission and metadata records;
- deterministic source/project/drawing-set identity and pre-label split, with
  every blueprint from one project isolated to one split;
- immutable SHA-256 and one-based multipage inventory;
- page-level sheet classification for mixed documents while retaining the
  document, project, drawing-set, and one-based page identities;
- safe incremental re-intake that preserves absent records, versions manifest
  changes, and rejects changes to established source identity, grouping, split,
  classification, quality, or approved permission;
- strict validation of every preserved record and page plus recomputation of
  eligibility, exact/near duplicate groups, and coverage before any merge;
- exact prior manifest bytes archived under exclusive filenames, with every
  revision hash link validated so prior revisions remain recoverable and
  tampering stops intake;
- exact-duplicate grouping plus separate source, drawing-group, reference, and
  independent eligible blueprint-project coverage;
- perceptual near-duplicate flagging and cross-split rejection;
- related-project cross-split rejection;
- 25 MiB bounded reads before content allocation and 10,000-edge/60-megapixel
  image and PDF-render preflight limits from the U1 baseline;
- structural validation, per-page renderability, visual-quality classification,
  and dataset eligibility are recorded separately;
- unsupported pages remain inventoried but ineligible, while degraded pages
  require an append-only, source/page-bound quality-review decision for the
  exact intended purpose; accepted pages retain their degraded classification;
- a PDF rejected by the strict application validator may be inventoried only
  through an explicit recoverable-document option, with degraded/unsupported
  page classifications and the same page/allocation bounds;
- unsupported/corrupt input, traversal, absolute path, symlink, and private
  manifest-boundary rejection; and
- unchanged original bytes.

The tool writes only a private manifest beneath the explicitly supplied private
root. It prints aggregate counts, not private metadata. No database or HTTP API
is involved.

## Actual private intake

The restored transfer contains four source records: two historical VED blueprint
projects and two private third-party reference documents. Transfer verification
rechecked all 112 private-manifest entries with zero missing files, size
mismatches, or hash mismatches before intake.

The 2026-09-08 standing VED collection authorization was bound to both covered
blueprint records using the user-confirmed authority wording and private session
reference. The records were grouped as two independent historical projects and
assigned to train and development-validation respectively. Neither was assigned
to sealed test because no genuinely new independent project exists. Legacy
free-text declarations were not treated as the new evidence.

The original intake wrote manifest schema 1 revision 1. The corrected tooling
fully validated that revision, archived its exact bytes, and upgraded the live
private manifest to schema 2 revision 2. An identical schema-2 run reported
`changed=false`. Original hashes remained identical to the transfer baseline.
Actual inventory is four sources and 18 pages: two blueprint sources with nine
pages and two reference sources with nine pages. Current eligible coverage is
zero blueprint sources/pages, zero drawing groups, zero independent blueprint
projects, and zero reference sources/pages. Exact- and near-duplicate counts are
both zero. The separate 87-file legacy training workspace remains preserved
privately; its crops, provisional labels, scripts, and exports were not
miscounted as independent source projects.

A private ten-page visual review preview was rendered and inspected. It contains
a cover, the single degraded VED blueprint page, and all eight pages of the mixed
VED document. It uses opaque source IDs and shows the original page beside the
proposed sheet type, strict structural status, local renderability, visible
quality assessment, and pending decision. It is not tracked by Git and is not
an approval record.

## Consolidated remaining decisions

The only public identifiers below are opaque private-manifest IDs:

| Source | Type | Smallest remaining action |
|---|---|---|
| `source-384fe30d` | Blueprint | Review the visible page evidence and accept it as readable degraded data for training, or reject it; the degraded classification and structural finding remain either way |
| `source-cef52bcc` | Blueprint | Confirm the eight page-level proposals, or return corrections by one-based page number; the current private manifest keeps all eight classifications pending |
| `source-7638337a` | Reference | Remains inventoried and excluded while purpose-specific third-party rights are unresolved; no decision is required to inventory eligible VED blueprints |
| `source-d51f60d0` | Reference | Remains inventoried and excluded while third-party rights and degraded-quality use are unresolved; no decision is required to inventory eligible VED blueprints |

U3 additionally needs a genuinely new independent blueprint project reserved for
sealed test. Re-scanning or deriving crops from either historical project does
not satisfy that requirement. Source, drawing-group, independent-project,
duplicate-cluster, and reference counts remain separate.

Device encryption is explicitly deferred with user acceptance as of
2026-09-08. It is not a passing control and does not block U3 intake under the
amended policy. The at-rest risk remains documented, with no approved deadline;
all other privacy and permission gates remain unchanged.

## Acceptance status

| Criterion | Status | Evidence |
|---|---|---|
| Local strict intake tooling and private manifest boundary | PASS | Synthetic implementation and tests |
| Safe incremental preservation, recoverable immutable revisions, idempotency, and conflict controls | PASS | Synthetic tests preserve omitted members, archive exact prior bytes, validate the hash chain, reject tampering, and reject established split rewrites |
| Full validation of preserved records and derived manifest data | PASS | Malformed stored page and falsified coverage regression tests fail closed before merge |
| Bounded reads and image/PDF pre-allocation limits | PASS | Synthetic oversize source, image-edge, and PDF-render tests |
| Supported/corrupt, multipage, traversal and original integrity | PASS | Synthetic tests |
| Native Windows symlink creation case | NOT TESTED | Current account cannot create a native symlink; the same rejection branch passes with deterministic simulation |
| Exact/near duplicate, project-level split, and related-source leakage controls | PASS | Synthetic tests |
| Independent coverage dimensions and unsupported/degraded eligibility | PASS | Synthetic tests report sources, drawing groups, independent projects and references separately |
| Mixed-document page classification | PASS | Synthetic three-page fixture records distinct one-based types and leaves an uncertain page pending |
| Revisioned degraded-quality review | PASS | Accepted, rejected, pending and wrong-purpose cases recompute eligibility; review history is append-only and bound to unchanged source/page identity |
| Structured permission and pre-label split enforcement | PASS | Synthetic tests |
| Device encryption | DEFERRED | User-accepted risk; not a passing control and no longer an intake blocker |
| Real private source intake | PASS | Schema 2 revision 2 created locally with the exact schema-1 revision archived; idempotent rerun reported no change; all four source hashes match |
| Covered VED blueprint permission and historical grouping/splits | PASS | Collection authorization bound privately; two historical projects assigned train/development-validation |
| Private visual review preview | PASS | Ten-page PDF was generated and visually inspected outside Git; it exposes the two outstanding VED decisions with visible evidence |
| VED page classification and degraded-quality decisions | BLOCKED | Eight page classifications and one purpose-specific degraded-quality decision await human review |
| Third-party reference eligibility | BLOCKED | Rights evidence remains unresolved, so both references remain inventoried and excluded without blocking VED blueprint inventory |
| Actual independent eligible blueprint-project coverage | BLOCKED | Current proven count is zero; no genuine sealed-test project exists |
| U3 implementation publication and merge | PASS | September 11 policy permits separately verified implementation publication while preserving the blocked real-data status |
| U3 real-data acceptance | BLOCKED | Page/quality decisions and independent sealed-test coverage have not passed |

The U3-specific suite passes 41 tests with one native Windows symlink test
skipped. After reconciliation with the published demo baseline, the focused
U3/candidate/upload suite passes 94 tests with the same skip and 2 subtests.
The full isolated-database backend regression passes 747 tests with 4 skipped,
2 known dependency deprecation warnings, and 509 subtests.

The original U3 read-only reconciliation found 34 unique OpenAPI operations and
23 modeled tables matching live state. After merging the published demo baseline,
the current contract has 37 unique operations and 25 modeled tables exactly
matching the 25 live tables. The configured original store now contains 10 files
and 1,015,004 bytes with aggregate SHA-256
`20751d51ff7c6240274f075ee5237f93c44d48a79e7cf103baca34fc1b6fc2f3`;
the increase belongs to later demo activity, and U3 changed none of those bytes.

Under the September 11 policy, U4 and later independently testable implementation
may proceed after this U3 implementation is published. The unresolved U3 data
decisions remain required for real-data acceptance, training/evaluation claims,
and production promotion; downstream code must surface those states rather than
substitute synthetic fixtures as real data.
