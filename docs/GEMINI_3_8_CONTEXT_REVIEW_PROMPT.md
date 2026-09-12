# Historical Gemini handoff — superseded by Codex ownership

September 12 user amendment: Codex is now the implementation and progress owner.
Stop Gemini writes and hand off unfinished files without deleting or resetting
them. Follow `CODEX_U_VLM_MIGRATION_PROMPT.md` §0 for the live U12–U14 assignment.
Everything below is historical context, not current execution authorization;
its Gemini ownership and U5 resume instructions are superseded.

## Role and boundaries

User amendment: Gemini is now the active implementation owner. This supersedes
the earlier review-only role and Codex-only writer rule. Own scoped repository
edits, implementation, testing and Git checkpoints under the existing U-ticket
authorization. The separate ChatGPT planning chat reviews results and prepares
recommendations; the Gemini session reading this file is the implementer.
Only one agent may write the shared checkout at a time; coordinate a handoff if
another implementation task is still running. State your actual model/session.
Preserve the recovery stash unchanged. No new permissions to reset databases,
change existing credentials broadly, invent approvals or activate models arise
from this role change.

Repository: `C:\Users\kupal\Documents\ai-floorplan-analysis`.

User authorization permits U1–U14 development while datasets wait. Independent
implementation can proceed using explicit synthetic fixtures; real data,
model selection, training quality and release approval remain separate gates.
This assignment authorizes implementation, not another review-only report.
Finish U5's independently testable gaps and verification, then continue U6–U14
development under the dataset-deferred policy. Do not restart completed tickets.

## Standing continuation authorization — September 11

The user explicitly approves continuous U-ticket implementation. Do not stop
after a plan, test run, report, commit or ticket to request another "continue".
Inspect → implement → verify → publish the permitted checkpoint → start the
next dependency-ready U task. Fix in-scope failures; never bypass failed gates.
Checkpoints are progress updates, not requests for renewed planning approval.
Do not delegate execution back to an imaginary Gemini or await its report:
you are that implementation owner. Start with the first unfinished U5 work.

Record blocked data/model/release-dependent portions and continue independent
implementation using clearly labeled synthetic tests. Stop only when all
feasible authorized U work is finished, the user stops you, or no safe work
remains without missing authority/input or resolution of a conflicting writer.
Request only the specific missing decision, not blanket approval again.
This is not permission for destructive resets, new privileges, invented domain
rules, unapproved downloads or model activation. Existing safeguards still apply.

If session/tool limits interrupt execution, save a compact resume checkpoint
in the existing progress ledger: branch/commit, unfinished changes, actual test
results, pending processes and next command/task. Do not claim background work
continues after the session ends. Keep documentation ticket-scoped; no new MD files.

Latest supplied transcript ends in a review-only acknowledgment after reporting
DB provisioning and test launches. Reconcile actual accounts/grants and collect
test completion results before repeating setup or claiming PASS. Command lists
and launched suites alone are not successful verification evidence. Record the
live stash object without modifying it; do not copy conflicting historical IDs.

## 1. Establish current evidence with minimal context

- Read applicable AGENTS.md instructions, the current handoff §0 and §2 reading
  map, the latest relevant progress entry, and complete U5/U6 ticket criteria.
  Read other documentation sections only for affected contracts or commands.
- Inspect branch, HEAD, worktree, local main/upstream refs and stash identity
  read-only. Label cached remote refs as such; do not assume synchronization.
- Last planning-chat observation: main/origin-main refs `5845512`; branch
  `codex/u5-gold-metric-tooling`; implementation `af8e5ee`; HEAD `897c51f`
  adds this prompt. Preserve `stash@{0}` unchanged and record its object ID.
- Treat the earlier reported 14 focused passes, 86 combined passes/1 skip and
  MySQL 1045 diagnosis as prior evidence until independently verified. Avoid
  repeating the whole repository history.

## 2. Resolve the MySQL blocker with verified test isolation

The prior report says configured user `ved_app` is absent from the inspected
local server. Verify that the application, test process and diagnostic client
target the same server/port/database and settings source. Different environment
overrides, host-specific grants or a different server could change the diagnosis.

Inspect settings precedence, session/engine caching, test setup/teardown and
fixture cleanup. Produce the exact proposed test invocation with a process-local
verification-database override; the previous bare pytest command did not itself
select an isolated database. Existing `ved_electrical_verify` contents are not
automatically disposable. No schema creation, seed, reset or cleanup before its
ownership and effects are established.

Prefer retaining a dedicated app account and a separate scoped test connection.
Implement the least-change local test configuration using existing authorized
credentials when available. Scope a test account to the verification database;
do not give it access to development data. If new account/grant provisioning
requires unavailable operator authority, provide the exact minimal action and
continue database-independent work. Inspect required privileges and host matching.
Do not recommend persistent passwordless root application access or blanket
grants merely because a local root connection worked. Never print passwords,
complete connection URLs, secret environment files or raw credential errors.

Verify before/after development-data integrity beyond row counts where records
could be changed; unchanged counts do not prove unchanged contents. Deliver the
implemented fix, isolation evidence and any genuinely missing operator input.
Connection success alone does not prove test isolation.

## 3. Audit U5 against its actual acceptance criteria

Inspect:
- `backend/app/ai/floor_plan_interpretation/gold_evaluation.py`
- `backend/tests/test_gold_evaluation.py`
- `scripts/build_vlm_gold_manifest.py` (root scripts directory)
- Relevant U2 schema, U3 identity/splits, U4 reference pack and PRE10 authority.

Prioritize:
- Annotation/source hash binding, tampering, immutable revisions and re-import.
- Approver identity, annotation-author independence, scope, decision-time
  authority and stale/revoked approvals. Assignment creator and annotation
  author are distinct concepts; a single field comparison is not sufficient
  evidence that all required independence checks exist.
- Project/revision/crop grouping, duplicates and sealed-test exclusion. Check
  whether development loading reads sealed image/label contents before filtering.
- Completeness across all required layers; partially labeled regions must not
  silently become background negatives or fully approved gold.
- One-to-one symbol matching, wrong classes, duplicates, empty predictions/truth,
  absent classes, IoU boundaries, units, deterministic ties and aggregation.
- CLI path/hash validation, conflict/retry handling and output privacy.

Distinguish **not applicable** (outside a declared supported evaluation scope),
**not implemented** (required calculation missing), and **pending evidence**
(calculation exists but real inputs are unavailable). Missing required room,
wall, opening, panel, scale or wiring evaluators cannot become N/A solely to
declare U5 complete. Map each metric to its requirement and implementation.
Implement required missing evaluators with synthetic known-answer tests where
the contract is defined. Keep unimplemented requirements explicit; do not mark
the entire U5 implementation complete while required calculations are absent.
Do not defer calculable geometry metrics merely because real datasets wait.

Inspect test side effects, then run focused and required regression checks in
the verified isolated environment. Report commands actually run separately from
proposed commands, and preserve failed attempts rather than relabeling them.

## 4. Implement U6 and continue independent U7–U14 work

Reuse existing modules; define the smallest necessary interfaces and acceptance
tests before editing. Implement versioned experiment
configuration; U2 validation; U5 development-only loading; provider adapters;
bounded execution; latency/memory measurements; reproducible results and failures.

- A loopback URL alone does not prove the model process has no network egress.
- Recheck U1 hardware/resources; do not assume current GPU availability, model
  fit or CPU fallback compatibility from an old inventory.
- Keep fake-provider tests distinct from actual image inference and selection.
- Compare available OpenCV/YOLO baselines honestly. Missing usable YOLO weights
  means unavailable comparison, not measured zero performance.
- A Python socket guard alone cannot establish process/subprocess egress isolation.
  Implement and verify appropriate boundaries; disclose unverified guarantees.
- Model/license/runtime compatibility and real-data selection stay pending when
  evidence is absent. Acquisition/dependencies follow U1 budgets and existing
  authorization; no hosted inference, implicit downloads or automatic training.
- After each passing implementation checkpoint continue the next independent
  authorized U ticket. Keep real-data/training/release acceptance pending until
  evidence exists; stop only dependent work at an actual unresolved gate.

## 5. Verification, publication and planning-chat checkpoint

Return a concise report, normally at most 700 words unless evidence needs more:

1. Current baseline and what you actually inspected or ran.
2. Findings: severity, exact file/line, evidence, impact, smallest fix and test.
   Distinguish confirmed defects from hypotheses and missing evidence.
3. U5 matrix: implementation / verification / real-data acceptance / publication.
4. Execution sequence: resolve scoped test connection → verify isolation → focused
   and required regressions → checkpoint → recheck main → non-fast-forward merge
   when gates pass → post-merge verification → push. Never push before that check.
5. Independent U6 work that can proceed, plus exact dependent gates.
6. Files/configuration/database changes, commit/merge IDs, upstream state,
   integrity and unchanged stash identity. Required post-merge regressions must
   precede pushing main; one focused sanity check is not a substitute.

Preserve JavaScript/React/Konva/Three.js, FastAPI/MySQL, canonical compatibility,
original files, existing approvals and the local-only boundary. Encryption
remains explicitly deferred, not PASS. Update affected existing planning files
concisely; create no new Markdown reports. Report each criterion as PASS, FAIL,
NOT TESTED or BLOCKED with evidence and the next concrete implementation step.
