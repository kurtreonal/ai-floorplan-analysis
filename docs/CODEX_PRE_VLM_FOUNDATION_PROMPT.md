# Copy/Paste Prompt for Codex — Complete Pre-VLM Foundations

Use the following prompt in the repository root.

---

You are implementing the complete PRE0-PRE12 sequence defined in
`docs/PRE_VLM_FOUNDATION_PLAN.md` for the VED Electrical Services repository.
This is a pre-migration foundation task. Do not begin U1, install/download/run a
local VLM, train a model, remove YOLO, or implement L2 or later roadmap work.

## Mandatory context review

Before planning or changing anything, read these files completely:

```text
AGENTS.md
README.md
backend/README.md
docs/ARCHITECTURE.md
docs/FUNCTIONAL_SPEC.md
docs/geometry.md
docs/LOCAL_VLM_MIGRATION_PLAN.md
docs/PRE_VLM_FOUNDATION_PLAN.md
docs/THESIS_SOURCE.md
storage/training/README.md
storage/training/reviewer-policy.md
```

Also locate and read every applicable deeper `AGENTS.md` or repository
instruction file. Treat documentation as maintained context, not unquestionable
truth. Compare every claim with the current implementation, tests, Git state,
database schema, and protected storage. Correct stale status, roadmap,
acceptance, table-count, OpenAPI-count, test-total, dependency, and architecture
claims in the ticket that makes them stale.

## Mandatory preflight

Before PRE0:

1. Fetch remote refs without merging and verify the exact commits for `main`
   and `origin/main`.
2. Record branch, status, upstreams, divergence, recent history, staged,
   unstaged, ignored, and untracked files.
3. Treat the current Markdown changes and `.gitignore` security change as
   intentional user work. Do not discard, rewrite from the old commit, stash
   away, or overwrite them.
4. Confirm the protected file
   `backend/app/services/project_service.py` has no diff and record its committed
   blob hash. The last known protected blob is
   `44e01c22ede76f30182b1056b0cb4e6fce3df96a`; verify rather than assume it.
5. Use `git ls-files` and ignore checks to confirm that private blueprints,
   electrical-reference PDFs, training exports, annotations, prompts, rendered
   pages, model weights, and checkpoints are not tracked.
6. Inspect the current 21-operation/13-table implementation rather than relying
   on those numbers after later tickets change them.
7. Inspect existing tests and dependency files before selecting any mechanism.
8. If remote main moved, an unexplained overlapping code change exists, or a
   private file is tracked, stop and report the exact blocker before mutation.

Do not print credentials, private document contents, absolute model paths,
OAuth tokens, or raw database errors. Do not open, upload, delete, publish, or
change permissions on the Roboflow project or any other hosted service. Report
the existing Roboflow URL/`CC BY 4.0` metadata concern for human verification.

## Authorization and execution model

This prompt authorizes implementation, local verification, creation of the
required PRE feature branches, commits, publication of those feature branches,
explicit non-fast-forward merges into `main`, post-merge verification, and
pushes of `main` for PRE0-PRE12 only.

Implement the sequence in order:

```text
PRE0 → PRE1 → PRE2 → PRE3 → PRE4 → PRE5 → PRE6
     → PRE7 → PRE8 → PRE9 → PRE10 → PRE11 → PRE12
```

Treat every PRE ticket as a separately bounded implementation even though this
prompt authorizes the full sequence. For each ticket:

1. Reverify that local and remote main still match the previous published
   ticket.
2. Create `feature/pre<n>-<short-name>` from that exact baseline, for example
   `feature/pre1-floor-plan-discovery`. PRE0 may create its feature branch while
   preserving the intentional current working changes.
3. State the ticket-specific acceptance criteria and inspect its owning code,
   tests, APIs, schema, storage behavior, and documentation.
4. Implement only that ticket with the smallest coherent change. Preserve
   FastAPI router → service → repository layering and JavaScript/JSX frontend.
5. Do not invent VED classes, PEC rules, scale, elevation, prices, routes, or
   private reference provenance.
6. Do not modify original uploads. Use additive tables/contracts where the
   existing prototype `create_all()` approach cannot alter an existing table.
   Never reset or recreate the live database without separate explicit user
   authorization.
7. Run focused tests, then the proportionate full regression and integrity
   checks listed below.
8. Review the complete diff and stage explicit intended paths only.
9. Commit with a descriptive conventional commit, push the feature branch, and
   verify feature/upstream divergence is `0 0`.
10. Fetch/recheck remote main, merge using an explicit non-fast-forward merge
    commit, rerun required post-merge checks on `main`, push `main`, and verify
    `origin/main...main` is `0 0`.
11. Publish a progress checkpoint using the required report format below.
12. Continue to the next PRE ticket if all gates pass. Do not ask for routine
    branch/commit/merge/push approval; this prompt already grants it.

Stop and request explicit direction only if work would require destructive live
data changes, deletion of existing uploads, external/hosted-service mutation,
new electrical-engineering assumptions, disclosure of private data, or a scope
change outside PRE0-PRE12. A difficult test or implementation is not by itself
a reason to skip a gate.

## Ticket scope

Implement every ticket exactly as specified in
`docs/PRE_VLM_FOUNDATION_PLAN.md`:

- PRE0: publish documentation and privacy baseline.
- PRE1: ownership-aware floor-plan discovery API.
- PRE2: processing-job history discovery API.
- PRE3: reload-safe persisted floor-plan/job frontend.
- PRE4: immutable source hashes and explicit PDF/raster page identities.
- PRE5: durable processing-artifact manifest and J1A provenance resolution.
- PRE6: Designer-approved floor elevation and page scale evidence.
- PRE7: Admin symbol-legend management without seeding guessed classes.
- PRE8: conditional and idempotent layout saves.
- PRE9: engine-neutral job attempt, claim, lease, heartbeat, cancellation, and
  recovery controls without running any AI pipeline.
- PRE10: auditable VED AI Dataset Approver assignment authority. Do not add a
  third global OAuth/application role merely for this workflow. Admin manages
  assignments; a human with an active assignment may later approve data. A
  model or Codex can never approve its own proposal.
- PRE11: freeze the canonical compatibility decision. Keep K1 v1 readable and
  assign source-page/evidence details to candidate/review records; reserve a
  future versioned canonical extension for first-class openings, panels, and
  observed/generated route provenance. Do not invent electrical semantics.
- PRE12: run and publish the readiness gate; stop before U1.

Do not silently combine neighboring tickets because they touch similar files.
If repository evidence shows an acceptance criterion is already implemented,
prove it with tests and make only the remaining smallest change. If an
acceptance criterion conflicts with current implementation safety, document the
evidence and stop rather than weakening it.

## Required verification

Use the repository's existing commands and environment. After each ticket run
the focused suites for changed behavior. Before each merge and again after the
merge, run all proportionate checks; PRE12 must run the complete set:

- backend focused and full test discovery, including canonical pytest where it
  remains a separate command;
- frontend focused/full tests when affected;
- frontend ESLint and Vite production build when frontend or shared contracts
  are affected;
- Python compilation;
- dependency integrity and environment-template validation;
- exact OpenAPI operation count and route-method/path uniqueness;
- exact SQLAlchemy versus live MariaDB table/constraint/index match;
- default `test` database remains empty unless a documented isolated test owns
  it temporarily;
- before/after live row counts, with only ticket-authorized additive or test
  rows present;
- original upload presence, byte size, and SHA-256 equality;
- derived/model/training artifact counts and Git tracking/ignore checks;
- no critical MariaDB errors attributable to the ticket;
- `backend/app/services/project_service.py` diff and committed blob;
- `git diff --check`, status, upstreams, and divergence.

Do not claim browser verification if no connected browser/runtime or valid data
exists. Mark it `NOT TESTED` or `BLOCKED`. Do not seed production records merely
to force a browser demonstration. Remove only verified test-created data and
state exactly what was removed and whether recovery is possible.

## Documentation consistency requirement

Documentation alignment is part of every ticket, not a final cleanup. Recheck
at least:

```text
AGENTS.md
README.md
backend/README.md
docs/ARCHITECTURE.md
docs/FUNCTIONAL_SPEC.md
docs/geometry.md
docs/LOCAL_VLM_MIGRATION_PLAN.md
docs/PRE_VLM_FOUNDATION_PLAN.md
```

Preserve `docs/THESIS_SOURCE.md` as historical/reference-only unless the source
manuscript itself must be corrected. Keep implementation history distinct from
target architecture. Never claim that a PRE, U, VLM, worker, API, table, or UI
capability exists before its verification and publication gates pass.

## Progress reporting during implementation

Send concise commentary updates while working and do not leave the user without
an update during long verification. At minimum report when:

- preflight finishes;
- a ticket branch is created;
- implementation and focused tests finish;
- the feature branch is committed/pushed;
- post-merge verification begins;
- `main` is pushed;
- a blocker or cleanup issue appears.

After every ticket, post this checkpoint before starting the next:

```text
## PRE<n> progress report

Outcome:
- PASS / FAIL / BLOCKED / NOT TESTED

Publication:
- baseline commit:
- feature branch:
- feature commit:
- feature upstream/divergence:
- merge commit:
- current branch:
- origin/main...main:
- working tree:

Delivered:
- created files:
- modified files:
- behavior implemented:
- behavior intentionally not implemented:

Acceptance criteria:
- PASS/FAIL/BLOCKED/NOT TESTED — criterion 1
- ...

Verification:
- focused backend:
- full backend:
- canonical pytest:
- focused frontend:
- full frontend:
- ESLint:
- production build:
- Python compilation:
- dependency/environment checks:
- OpenAPI operations:
- SQLAlchemy/live tables:
- live row-count comparison:
- original upload hash comparison:
- derived/model/private artifact checks:
- browser/manual verification:

Documentation alignment:
- stale or contradictory claims found:
- files corrected:

Integrity and warnings:
- protected project_service.py blob/diff:
- cleanup performed and recoverability:
- warnings:

Stopping state:
- next PRE ticket:
- next ticket started: no
- blocker/authority needed: none or exact requirement
```

After PRE12, provide one consolidated readiness report covering PRE0-PRE12 and
explicitly state whether U1 may begin. Stop before creating a U1 branch.

---
