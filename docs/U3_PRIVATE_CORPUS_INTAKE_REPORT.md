# U3 Private Corpus Intake Report

- Ticket: U3
- Inspection date: 2026-09-07 (Asia/Manila)
- Status: BLOCKED before real intake
- Baseline: U2 merge `3f12087`

This report is sanitized. It contains no source names, paths, hashes, drawing
text, labels, reviewer identity, or private approval evidence.

## Safe implementation completed

The feature branch implements local-only intake tooling under
`backend/app/ai/floor_plan_interpretation/corpus_intake.py` and a quiet command
wrapper at `scripts/intake_vlm_corpus.py`. Synthetic tests prove:

- strict purpose-specific permission and metadata records;
- deterministic source/project/drawing-set identity and pre-label split;
- immutable SHA-256 and one-based multipage inventory;
- idempotent re-intake and changed-source conflict detection;
- exact-duplicate grouping and independent-group counting;
- perceptual near-duplicate flagging and cross-split rejection;
- related-group cross-split rejection;
- unsupported/corrupt input, traversal, absolute path, symlink, and private
  manifest-boundary rejection; and
- unchanged original bytes.

The tool writes only a private manifest beneath the explicitly supplied private
root. It prints aggregate counts, not private metadata. No database or HTTP API
is involved.

## Actual private inventory finding

The restored legacy source manifest contains four records. Two have non-empty
legacy free-text approval declarations and two do not. None has the structured
purpose permission, project/drawing-set grouping, preassigned split, quality,
or sheet classification required by U3. The six live application originals are
exact duplicates and count as one source group, not six independent examples.

Accordingly, the number of currently proven eligible independent corpus groups
is zero. No real source was passed to the new tooling and no existing private
manifest or original was changed.

## Blocking gates

1. Device encryption is not yet proven restored. The approved U1 exception
   explicitly ends before U3 ingests additional real source data.
2. Each proposed private source needs a VED-authorized, purpose-specific record
   covering its permitted use (`training`, `development_evaluation`,
   `sealed_evaluation`, or `reference_grounding`) plus local evidence.
3. Blueprint sources need project and drawing-set grouping, quality and sheet
   classification, and a split assigned before pseudo-labeling.
4. U3 must then run the real manifest locally and report independent eligible
   coverage. Insufficient independent projects remains a blocking result.

## Acceptance status

| Criterion | Status | Evidence |
|---|---|---|
| Local strict intake tooling and private manifest boundary | PASS | Synthetic implementation and tests |
| Idempotency and changed-source conflict | PASS | Synthetic tests |
| Supported/corrupt, multipage, traversal, symlink and original integrity | PASS | Synthetic tests; symlink case is platform-permission conditional |
| Exact/near duplicate and cross-split leakage controls | PASS | Synthetic tests |
| Structured permission and pre-label split enforcement | PASS | Synthetic tests |
| Real approved source intake | BLOCKED | Encryption and structured permission evidence missing |
| Actual independent eligible coverage | BLOCKED | Current proven count is zero |
| U3 completion publication and merge | BLOCKED | Real-data gates have not passed |

Verification completed with 72 focused tests passing, 1 conditional Windows
symlink test skipped, and 2 subtests passing. The full backend regression passes
700 tests with 4 skipped, 2 dependency deprecation warnings, and 504 subtests.

U4 and all later dependent work must not start until these U3 blockers are
resolved and the completed ticket is independently verified and published.
