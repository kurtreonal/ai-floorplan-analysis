# Client workflow and workspace product editing

Implemented 27 October 2026. JavaScript/React and FastAPI/MySQL remain unchanged.
No new database tables, migrations, dependencies or test files.

## Designer and Client navigation

- One searchable Client table replaces client cards and nested project tables.
  Status filtering, sorting and a project dropdown reduce repeated navigation.
- Clients also receive a project table with published cost summaries.
- Floor-plan downloads and naming are inside Options → File details.
- The Cost estimation sidebar item is removed. Overall cost estimation is at
  the end of the project page; each plan retains its own BOM.

## Account recovery

- Recovery accepts a verified primary or backup email, never a username.
  Users without access to a verified address are directed to Admin.
- Normalized email lookup requires exactly one active, managed account.
  Unverified, unknown and shared ambiguous addresses receive a generic response.
- Account creation, Admin password reset, personal password changes and email
  recovery all require matching confirmation, enforced on both sides.
- Password validation errors omit submitted values. Existing session revocation,
  one-use email codes and invitation-only authorization remain in place.

## Products belong in the workspace

- Select a device in 2D or 3D, then choose Change brand / product. BOM product
  links open the same source-bound editor; the BOM no longer has brand controls.
- A device choice applies only to that symbol. A wiring product choice covers
  the connected network shown in the editor, with compatible Admin conduit options.
- Single-conductor products ask for the recorded circuit conductor count.
  Purchase lengths use catalogue data or an explicit pack length, never an
  invented one-metre roll or conductor multiplier.
- Plan material defaults remain a separate workspace action. Individual choices
  take priority. Inactive or incompatible products are not silently substituted.
- The existing material-selection JSON stores `itemMaterials`, bound to the
  plan's candidate run. Revision checks and idempotent requests remain intact.
  Product changes do not save unfinished geometry.
- The 3D camera focuses the mounted device from its front, using the scene's
  metre conversion. Ceiling fixtures are approached from below. User motion
  interrupts the existing transition; reduced-motion preferences remain supported.
- Device foreground rendering preserves self-occlusion, so rear housings no
  longer cover faceplates. Selection outlines omit triangle diagonals. These
  changes do not move terminals, devices, routes or walls.

## Approved Client costs

- A new Admin approval captures the exact saved proposal's project BOM alongside
  its approved layout. Missing inputs remain partial; assumptions stay estimated.
- Existing approved proposals can be published through Admin project → Client
  publication → Publish approved project BOM. This is an explicit capture of
  current quantities and prices, not a rewrite of an earlier estimate.
- Captures use append-only files under the configured `REPORT_DIR/client-bom`
  and the existing Admin activity log. Formal estimate publication still works.
  A newer explicit publication supersedes the prior presentation.
- Client reads use captured quantities, catalogue identities, purchase lengths,
  prices and currency totals. Later private product changes cannot reprice them.
- Backend project access remains authoritative. Clients see associated approved
  versions, not Designer drafts or editing endpoints.

## Verification

| Acceptance | Result | Evidence |
| --- | --- | --- |
| Client table, sorting, project dropdown and project estimate footer | PASS | Live browser inspection |
| File actions concealed under Options / File details | PASS | Live browser inspection |
| Personal password confirmation shown | PASS | Read-only settings dialog inspection |
| Email-only recovery and redacted mismatch validation | PASS | Running API/OpenAPI checks; no email sent |
| Individual product and connected-network changes | PASS | Real local database calculation, rolled back |
| Source binding and unchanged geometry | PASS | Review hash and conduit length comparison |
| Approved BOM available to the associated Client | PASS | Actual approval and Client service calls, rolled back |
| Captured prices survive later private product changes | PASS | Snapshot/service comparison, rolled back |
| 3D close-up, faceplates and product inspector | PASS | Actual WebGL browser output |
| Frontend build, focused ESLint, backend compilation, diff whitespace | PASS | Focused commands |
| Email delivery and changing a real password | NOT TESTED | No message sent or credential changed |
| Full automated suites | NOT TESTED | User requested no new tests and will test manually |

Verification screenshots and calculation receipts are in the ignored
`outputs/wiring-save-20261026/workflow-ux-20261027/` directory. Browser checks used
the existing Designer session; Client publication was verified through backend
services, not a live customer publication. Temporary database changes were rolled
back, temporary verification captures removed, and saved reviews restored.

Existing large-chunk Vite warnings remain. No unrelated worktree changes or stash
were removed. Branch: `codex/vlm-localization-experiment`; no commit made here.
The final read-only check found 50 existing database tables and 97 OpenAPI paths.
