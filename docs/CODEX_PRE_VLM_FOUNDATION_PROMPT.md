# Codex execution prompt: PRE0–PRE12 foundations

Historical foundation handoff. PRE12 has a published readiness report; inspect
current evidence before resuming work. Do not restart completed tickets.
The active demo/U assignment is in CODEX_U_VLM_MIGRATION_PROMPT.md.

## Scope and authorization

When explicitly assigned for PRE work, implement PRE0–PRE12 in order using
[foundation plan §4](PRE_VLM_FOUNDATION_PLAN.md#4-foundation-tickets).
Assignment authorizes scoped local implementation/testing, separate feature
commits/pushes, non-fast-forward merges, post-merge checks and main pushes.
Each ticket remains a separate acceptance/publication unit. Stop after PRE12
and its readiness report, before U1 or any model download/training, YOLO removal
or later application epic. Merely editing this prompt authorizes no execution.

## Read only the current ticket context

1. Read all applicable AGENTS.md instructions and this short handoff.
2. Read foundation plan §§1,5,6, the complete assigned PRE ticket in §4 and
   prerequisite completion evidence. Do not reload unrelated PRE tickets.
3. Inspect owning source/tests and affected API, schema and storage contracts.
   Use relevant README/backend README command sections, ARCHITECTURE and
   FUNCTIONAL_SPEC sections; load geometry/ADR for canonical work.
4. Load local-VLM policy sections or training/reviewer documentation only for
   affected privacy, legend, authority or compatibility decisions. THESIS_SOURCE
   is historical reference unless the task explicitly concerns it.
5. Search headings first, then read selected sections completely. Refresh only
   changed sections/diffs after each ticket; expand when dependencies demand it.
   This replaces this prompt's previous blanket reread lists.

## Preflight and implementation

Follow [foundation plan §5](PRE_VLM_FOUNDATION_PLAN.md#5-required-execution-and-publication-protocol)
for branch/publication order. Inspect main/upstreams, exact HEAD, all working
changes, tests and dependency files. Preserve user work; resume matching
branches. Verify the protected project_service.py diff/blob and private-file
tracking/ignore coverage. Historical operation/table counts are not a current
baseline. Resolve unexpected overlapping edits or tracked private data first.

Keep existing architecture, originals and live rows intact; no guessed classes,
electrical rules, scale/elevation or approvals. Scope does not authorize hosted
service changes, private-data disclosure, destructive database/file operations
or later epics. Report Roboflow metadata/privacy concerns without changing that
service. Never expose credentials/tokens/private contents in output.

## Verification

Before and after each merge run proportionate checks; PRE12 runs the full gate.
Use existing environments/tooling and isolated run-owned fixtures:

- Focused/full backend, separate canonical pytest where required; affected
  frontend tests, lint and build; compilation and dependency/environment checks.
- Exact OpenAPI method/path uniqueness; modeled/live tables, constraints and
  indexes; before/after row counts; no ticket-caused critical database errors.
- Original byte sizes/hashes; derived/training/model counts and ignore/tracking;
  protected service blob/diff; Git whitespace, status/upstream/divergence.
- Default test database remains empty except documented isolated fixtures.
  Remove only proven run-owned data and state recoverability.
- Actual browser checks where required; absent runtime/data means NOT TESTED
  or BLOCKED. Do not seed approvals just to produce a demonstration.

## Checkpoint and stopping point

Use [foundation plan §6](PRE_VLM_FOUNDATION_PLAN.md#6-mandatory-progress-report-after-every-ticket)
as the complete reporting checklist. Keep one compact ticket checkpoint and
link unchanged baseline evidence instead of repeating full reports. State
every acceptance result, failures/reruns, integrity, publication and next step.
Do not relabel historical test counts as newly executed checks.

Update only affected claims in existing documents. Keep concise progress
updates during implementation/publication and explain blockers. After PRE12
publish the consolidated readiness decision and stop before a U1 branch.
