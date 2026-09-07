# Local VLM Migration Progress

This ledger separates implementation, real-data validation, human approval,
activation, and publication. A checked implementation item is not equivalent
to a trained or released model.

| Ticket | Implementation | Real-data validation | Human approval | Activation | Publication | Current note |
|---|---|---|---|---|---|---|
| U1 | In progress | Development machine measured | Partial | Not applicable | Authorized WIP checkpoint; not a completion release | Target machine and proposed numeric budgets/retention remain blocked |
| U2 | Not started | Not started | Not applicable | Not applicable | Not published | Depends on passing U1 |
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
  This exception does not mark U1 complete, approve pending budgets, authorize
  U2, or merge the incomplete ticket into main. Actual publication IDs are
  recorded in the post-push report and private device handoff.
- The device-migration Markdown, credentials, database backup and private files
  remain local-only and excluded from this publication.
- No model, adapter, inference dependency, API operation, database table, or
  application behavior has been added.
- U2 has not started.
