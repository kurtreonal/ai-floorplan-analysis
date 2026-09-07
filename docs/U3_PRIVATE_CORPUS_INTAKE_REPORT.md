# U3 Private Corpus Intake Report

- Ticket: U3
- Inspection dates: 2026-09-07 through 2026-09-08 (Asia/Manila)
- Status: BLOCKED before real intake
- Baseline: U2 merge `3f12087`
- Safe correction implementation: `941eb9b`

This report is sanitized. It contains no source names, paths, hashes, drawing
text, labels, reviewer identity, or private approval evidence.

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
- exact-duplicate grouping plus separate source, drawing-group, reference, and
  independent eligible blueprint-project coverage;
- perceptual near-duplicate flagging and cross-split rejection;
- related-project cross-split rejection;
- 25 MiB bounded reads before content allocation and 10,000-edge/60-megapixel
  image and PDF-render preflight limits from the U1 baseline;
- unsupported and degraded sources remain inventoried but are not eligible;
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

Accordingly, the number of currently proven independent eligible blueprint
projects is zero. Source count, drawing-group count, independent blueprint
projects, exact-duplicate clusters, and reference materials are not treated as
interchangeable coverage. No real source was passed to the new tooling and no
existing private manifest or original was changed.

## Consolidated missing real-intake fields

Legacy free-text declarations were not promoted to approved permission. The
only public identifiers below are opaque inventory IDs:

| Source | Type | Missing fields required before intake |
|---|---|---|
| `source-0001` | Blueprint | Permission status, allowed purpose, VED approver, local evidence reference, project group, drawing set, split, sheet type, quality |
| `source-0002` | Blueprint | Permission status, allowed purpose, VED approver, local evidence reference, project group, drawing set, split, sheet type, quality |
| `source-0003` | Reference | Permission status, `reference_grounding` purpose, VED approver, local evidence reference, project group, drawing set, sheet type, quality |
| `source-0004` | Reference | Permission status, `reference_grounding` purpose, VED approver, local evidence reference, project group, drawing set, sheet type, quality |

After those records exist, U3 must run the real manifest locally and report the
resulting independent eligible blueprint-project coverage. Insufficient
independent projects remains a blocking result. Degraded sources require an
explicit later quality-approval decision; unsupported sources remain inventory
only and cannot satisfy eligible coverage.

Device encryption is explicitly deferred with user acceptance as of
2026-09-08. It is not a passing control and does not block U3 intake under the
amended policy. The at-rest risk remains documented, with no approved deadline;
all other privacy and permission gates remain unchanged.

## Acceptance status

| Criterion | Status | Evidence |
|---|---|---|
| Local strict intake tooling and private manifest boundary | PASS | Synthetic implementation and tests |
| Safe incremental preservation, manifest revision, idempotency, and conflict controls | PASS | Synthetic tests preserve omitted members and reject established split rewrites |
| Bounded reads and image/PDF pre-allocation limits | PASS | Synthetic oversize source, image-edge, and PDF-render tests |
| Supported/corrupt, multipage, traversal and original integrity | PASS | Synthetic tests |
| Native Windows symlink creation case | NOT TESTED | Current account cannot create a native symlink; the same rejection branch passes with deterministic simulation |
| Exact/near duplicate, project-level split, and related-source leakage controls | PASS | Synthetic tests |
| Independent coverage dimensions and unsupported/degraded eligibility | PASS | Synthetic tests report sources, drawing groups, independent projects and references separately |
| Structured permission and pre-label split enforcement | PASS | Synthetic tests |
| Device encryption | DEFERRED | User-accepted risk; not a passing control and no longer an intake blocker |
| Real approved source intake | BLOCKED | Structured purpose permission and grouping/classification metadata are missing |
| Actual independent eligible blueprint-project coverage | BLOCKED | Current proven count is zero |
| U3 completion publication and merge | BLOCKED | Real-data gates have not passed |

The U3-specific suite passes 26 tests with one native Windows symlink test
skipped. The broader focused suite passes 182 tests with one native symlink
test skipped, two dependency deprecation warnings, and 10 subtests. After the
final scoped adjustment, the full backend regression passes 712 tests with 4
skipped, the same 2 dependency warnings, and 504 subtests.

Read-only contract and integrity reconciliation found 34 unique OpenAPI
operations and 23 modeled tables exactly matching the 23 live tables. Live row
counts match the PRE12 baseline. The six application originals remain 146,958
bytes total and retain their previously published common SHA-256; no derived
application artifact was created by U3.

U4 and all later dependent work must not start until these U3 blockers are
resolved and the completed ticket is independently verified and published.
