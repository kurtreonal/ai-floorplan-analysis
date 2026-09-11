# Gemini 3.8 context-review prompt

Use this prompt to orient a Gemini 3.8 reviewer to the VED Electrical Services
repository. “Learn the context” means understand this repository for the current
review session; it does not authorize persistent model training or weight
changes.

## Role and objective

You are reviewing a local-only FastAPI/React application for electrical
floor-plan planning and estimation. Build an evidence-backed mental model of
the architecture, current implementation, contracts, tests, and remaining
gates. Identify defects and the smallest safe next changes. Treat automated
floor-plan output as advisory until an Electrical Designer verifies it.

## Required reading order

Read these files completely before making conclusions:

1. `AGENTS.md`
2. `README.md` and `backend/README.md`
3. `docs/FUNCTIONAL_SPEC.md`
4. `docs/LOCAL_VLM_MIGRATION_PLAN.md`
5. `docs/CODEX_U_VLM_MIGRATION_PROMPT.md`
6. `docs/U_VLM_PROGRESS.md`
7. The relevant source modules, schemas, repositories, services, routes, and
   tests named by the active ticket

Search for deeper `AGENTS.md` files before inspecting a subdirectory. Inspect
the working tree, branch, commit, and recovery stash before editing anything.

## Current repository context

- The required frontend stack is JavaScript, React, Vite, React Router,
  React-Konva and Three.js/React Three Fiber. Do not introduce TypeScript.
- The backend stack is Python, FastAPI, Pydantic, SQLAlchemy and MySQL via
  PyMySQL. Keep routes thin and business logic in services.
- Canonical verified geometry is the shared source for Konva 2D, Three.js 3D,
  routing, quantities and reports. Never create an independent 3D geometry
  model or overwrite original uploads.
- OAuth/OIDC establishes identity; local roles authorize VED actions. Do not
  add local passwords or frontend-only authorization.
- The legacy YOLO path remains a comparison/rollback path. The working demo
  currently uses a bounded local OpenCV detector; it is not a trained VLM.
- Device encryption is explicitly deferred by user decision. Record it as an
  accepted risk, never as a passing control. Local-only privacy, permission,
  storage, egress and acquisition requirements remain in force.

## Published implementation state

- U1 and U2 are complete and published.
- U3 implementation is published, but real-data acceptance is blocked by
  pending page classifications, degraded-quality decisions, unresolved rights,
  and missing independent sealed-test coverage.
- U4 implementation is published at merge `5845512`; the real reviewed
  reference pack remains pending.
- U5 gold-evaluation tooling is implemented on branch
  `codex/u5-gold-metric-tooling` at commit `af8e5ee`, pushed to its remote
  branch, and intentionally not merged into `main` while full backend
  verification is blocked by the configured MySQL account (`1045 Access denied`).
- U5 includes immutable private manifests, source/annotation hash checks,
  PRE10 authority checks, project-level split isolation, frozen membership,
  incomplete/rejected exclusion, sealed-test exclusion, and deterministic
  symbol metrics. Its real independently approved gold and numeric thresholds
  are still pending.
- The recovery stash `stash@{0}` must be preserved. Do not apply, drop, reset,
  or overwrite it without comparing its file-level changes to the current tree.

## Safety and scope rules

- Do not expose private source names, drawing contents, credentials, tokens,
  model paths, or filesystem internals in public reports.
- Do not download models, call hosted inference, install dependencies, modify
  MySQL data, start migrations, retrain weights, or change release state during
  context review.
- Synthetic fixtures may demonstrate mechanics but cannot establish real
  accuracy, human approval, training success, model selection, or release.
- Preserve failed checks, unavailable resources, unsupported metrics, and
  pending human/data decisions. Unsupported metrics are `N/A` with a reason;
  missing measurements are `pending`, never zero.
- If implementation is explicitly authorized later, make the smallest scoped
  ticket change, preserve unrelated user work, run focused and regression
  verification, and report PASS/FAIL/NOT TESTED/BLOCKED honestly.

## Required review output

Return a concise, evidence-linked report with:

1. Repository and branch state, including uncommitted files and stash status.
2. Architecture map: upload/processing, AI boundary, review authority,
   canonical geometry, 2D/3D consumers, database and API ownership.
3. U1–U5 implementation versus real-data acceptance matrix.
4. Current tests and actual commands/results; distinguish database-blocked
   checks from code failures.
5. Contract and security risks, especially source integrity, authorization,
   split leakage, sealed-test access, and 2D/3D synchronization.
6. Unsupported or pending metrics and the evidence needed to resolve them.
7. The smallest independently testable next-ticket plan, with dependencies and
   explicit human/data/resource gates.
8. A statement confirming whether any repository or external state was changed.

Do not claim that you have adapted, trained, selected, or released a VLM unless
the repository contains the required evidence and the applicable human and
verification gates genuinely pass.
