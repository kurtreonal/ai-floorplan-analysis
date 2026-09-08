# U3 Private Corpus Intake Report

- Ticket: U3
- Inspection dates: 2026-09-07 through 2026-09-08 (Asia/Manila)
- Status: BLOCKED after safe real intake
- Baseline: U2 merge `3f12087`
- Latest integrity implementation: `b4b4d57`

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
- unsupported and degraded sources remain inventoried but are not eligible;
  a PDF rejected by the strict application validator may be inventoried only
  when explicitly classified degraded/unsupported and safely renderable within
  the same page/allocation bounds;
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

The first run wrote private manifest revision 1; a second identical run reported
`changed=false`. Original hashes remained identical to the transfer baseline.
Actual counts are four records, two blueprint sources, two reference sources,
zero eligible blueprint sources, zero eligible drawing groups, zero independent
eligible blueprint projects, zero eligible references, zero exact-duplicate
groups, and zero near-duplicate pairs. The separate 87-file legacy training
workspace remains preserved privately; its crops, provisional labels, scripts,
and exports were not miscounted as independent source projects.

## Consolidated remaining decisions

The only public identifiers below are opaque private-manifest IDs:

| Source | Type | Smallest remaining action |
|---|---|---|
| `source-384fe30d` | Blueprint | Decide whether its safely renderable but strict-validator-rejected PDF is accepted as supported degraded data; otherwise it remains inventory-only |
| `source-cef52bcc` | Blueprint | Classify the mixed eight-sheet source at an adequate page/sheet boundary; do not force one inaccurate source-level type |
| `source-7638337a` | Reference | Supply purpose-specific rights/provenance evidence for private reference grounding, or keep it excluded |
| `source-d51f60d0` | Reference | Supply rights/provenance evidence and decide whether the degraded scan is acceptable for reference grounding, or keep it excluded |

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
| Structured permission and pre-label split enforcement | PASS | Synthetic tests |
| Device encryption | DEFERRED | User-accepted risk; not a passing control and no longer an intake blocker |
| Real private source intake | PASS | Revision 1 created locally; idempotent rerun reported no change; original hashes match |
| Covered VED blueprint permission and historical grouping/splits | PASS | Collection authorization bound privately; two historical projects assigned train/development-validation |
| Third-party reference rights and degraded-source decisions | BLOCKED | Rights evidence is missing for two references; two sources have unresolved degraded-quality decisions |
| Actual independent eligible blueprint-project coverage | BLOCKED | Current proven count is zero; no genuine sealed-test project exists |
| U3 completion publication and merge | BLOCKED | Real-data gates have not passed |

The U3-specific suite passes 32 tests with one native Windows symlink test
skipped. The focused U3/candidate/upload suite passes 85 tests with the same
skip and 2 subtests. The full backend regression passes 718 tests with 4
skipped, 2 known dependency deprecation warnings, and 504 subtests.

Read-only contract and integrity reconciliation found 34 unique OpenAPI
operations and 23 modeled tables exactly matching the 23 live tables. Live row
counts match the PRE12 baseline. The six application originals remain 146,958
bytes total and retain their previously published common SHA-256; no derived
application artifact was created by U3.

U4 and all later dependent work must not start until these U3 blockers are
resolved and the completed ticket is independently verified and published.
