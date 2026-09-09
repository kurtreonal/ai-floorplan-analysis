# Local VLM Migration Progress

This ledger separates implementation, real-data validation, human approval,
activation, and publication. A checked implementation item is not equivalent
to a trained or released model.

## Active priority: September 10 development demo

User-authorized planning change on September 9, 2026: execute the bounded
DEMO-0 through DEMO-4 track in `LOCAL_VLM_MIGRATION_PLAN.md` before resuming
the full U sequence. The current assignment is section 0 of
`CODEX_U_VLM_MIGRATION_PROMPT.md`. Target: real upload -> room/wall and symbol
proposals -> explicit review/metric approval -> shared saved geometry -> 2D
and basic 3D. Room and symbol recall targets are each >=50% on reviewed
development pages, not a confidence threshold or a release-accuracy claim.

| Checkpoint | Current status | Required evidence |
|---|---|---|
| DEMO-0 inspection and narrow plan | NOT STARTED by implementation task | Actual reusable inference, review, canonical and 3D components; readable development inputs |
| DEMO-1 local detection | NOT STARTED | Real new-upload inference; source-bound room/wall and symbol proposals |
| DEMO-2 review and persistence | NOT STARTED | Explicit corrections/approval; validated scale; safe shared canonical save/reload |
| DEMO-3 basic 2D/3D | NOT STARTED | Minimum L2-L5 rendering, known coordinates and synchronized saved edits |
| DEMO-4 demonstration and metrics | NOT TESTED | Real browser upload-to-3D run; separate room/symbol recall, precision and FP/FN |

This is a planning amendment only; no runtime, training or 3D implementation
was added in this planning task. U3 remains blocked under its original
criteria; its data decisions and sealed-test source are deferred dependencies
for the demo only. U10/U12/U14 and complete Admin annotation tooling are not
demo prerequisites. Do not relabel partially reused U/L tickets as complete,
fabricate human approvals or weaken the intake/release validators. Resume
the original sequence only after the demo handoff and further user direction.

| Ticket | Implementation | Real-data validation | Human approval | Activation | Publication | Current note |
|---|---|---|---|---|---|---|
| U1 | Complete | Native-Windows target measured | Approved operating and retention policy; temporary encryption exception recorded | Not applicable | Published to `main` at merge `8c73183` | No model selected/downloaded; U3 real-data intake and U6 acquisition remain gated on restored device encryption |
| U2 | Complete | Synthetic contract fixtures pass | Not applicable | Not applicable | Feature implementation commit `90c90bb`; merge publication pending | Strict source-pixel payload and host provenance envelope; no persistence or runtime |
| U3 | Not started | Not started | Not started | Not applicable | Not published | Depends on passing U1 |
| U4 | Not started | Not started | Not started | Not applicable | Not published | Depends on U3 and approved catalog data |
| U5 | Not started | Not started | Missing | Not applicable | Not published | Requires independent human-approved gold and thresholds |
| U6 | Not started | Not started | Not started | Not activated | Not published | Requires measured target hardware and passing U5 |
| U7 | Not started | Not started | Not applicable | Not applicable | Not published | Depends on U2 and U6 |
| U8 | Not started | Not started | Not applicable | Not activated | Not published | Depends on U2, U6, and U7 |
| U9 | Not started | Not started | Missing | Not activated | Not published | Requires actual human review decisions |
| U10 | Not started | Not started | Missing | Not activated | Not published | Requires approved training records and compute |
| U11 | Not started | Not started | Not started | Not activated | Not published | Depends on U9 durable review records |
| U12 | Not started | Not started | Not started | Not activated | Not published | Observed wiring only |
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
- Device encryption is a documented temporary exception. U3 may not ingest
  additional real source data and U6 may not acquire model artifacts until the
  exception closes.
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
- U3 has not started.
