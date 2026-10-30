# Client, Admin and Designer workflow

Implemented 25 October 2026. This extends the existing session, project, canonical draft and BOM services. Frontend code remains JavaScript; no test files, dependency changes or Alembic migrations were introduced.

## Account and project flow

1. Admin → Settings → Users: create a Designer or Client with a username and password. Google never auto-creates an account or merges users by email. Existing unmanaged Designer/Client records require initial credential setup by Admin. Existing explicitly assigned Admin identities retain bootstrap access. Passwords are salted scrypt hashes (N=131072, r=8, p=1); passwords never appear in account responses. Sign-in is rate limited by address and username, with a stored account lockout. Credential writes require the application origin. Validation responses do not echo submitted credentials. Password storage follows the [OWASP password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
2. Admin → Create a project: enter the existing intake information, select the client account and assign a designer. Existing projects retain their owners and information. Admin can associate them with a client account and reassign the designer on the project page.
3. Designer → Client list → Project list → Floorplans → Workspace. Project creation and intake editing are Admin actions. Existing project ownership remains the server authorization boundary for assigned designers.
4. User settings → Sign-in methods: separate Contact email, Password and Google rows open focused dialogs. A contact email is not presented as verified or automatically linked. Confirm the current password to change credentials or connect/disconnect Google. A Google-only Admin must have signed in within five minutes before adding a password; other roles cannot self-provision initial credentials. Disconnecting the only login is blocked. OIDC state/nonce validation is retained. Account changes revoke old sessions using a server-checked revision.
5. Admin → Project → Final approval: choose a saved estimate; its captured layout versions are selected automatically. An estimate without captured layouts cannot be published. A draft BOM download is not an estimate snapshot. A review checkbox precedes publication. Immutable version references keep later designer edits and newer estimates out of the client publication.
6. Clients see only their associated projects and Admin-published snapshots. Their portal has a read-only 3D presentation and captured estimate table. Designer routes reject the CLIENT role; client publication queries check the current project association.
7. Admin → Project → Delete project: confirmation removes the project from active access by setting its existing archived status. Original uploads, layouts, estimates and other history stay stored. No filesystem deletion occurs. There is no restore UI in this checkpoint.

Five additive SQLAlchemy tables support this workflow: `local_credentials`, `linked_identities`, `account_access`, `project_assignments`, `project_publications`. The CLIENT role and these tables were provisioned through the authorized local XAMPP administrator connection. No existing tables or account/project rows were replaced. The application retains its restricted database account. The provisioning script reads the authorized local configuration without printing credentials.

Users management supports search, role filters and ten-row pagination. Edit and Delete open warning dialogs and require confirmation. Delete soft-removes access; Edit can restore it. Active project assignments prevent an incompatible role change. Administrator rows are protected from this screen; an Admin manages their own sign-in methods. Assignment selectors list enabled accounts with configured usernames and use name/username/email/ID fallback labels. They refresh after account changes. Client/project navigation is URL-driven so local tabs and the sidebar cannot disagree.

Account endpoints: GET/POST `/api/admin/accounts`, PUT/DELETE `/api/admin/accounts/{id}`. Updates/deletes require `expected_revision`; stale edits return 409. The legacy POST `/api/admin/clients` remains client-only. All management writes enforce ADMIN and the application Origin. Self-service methods: GET `/api/auth/methods`, PUT `/api/auth/credentials`, PUT `/api/auth/contact-email`, POST/DELETE `/api/auth/link-google`.

## Editor changes

- Wall devices can be dragged vertically and along the wall in 3D. Ceiling devices move on their ceiling plane. The wall magnet catches nearby surfaces within one metre in 3D; 2D uses a 28-screen-pixel catch range.
- A committed 3D move writes the source-coordinate anchor, mounting wall and centre height through the existing draft update. Individual terminal offsets remain stored. The 2D view, attached wire vertices and live backend BOM consume that same draft.
- Shared junction vertices follow a moved device. Moves that would collapse a span or independently move another attached device remain rejected.
- Fractional source positions retain four decimal places instead of rounding every move to a whole image pixel.
- Existing upload processing already queues automatically and snapshots Admin measurement defaults. The measurements action is now **Reset setup**. Outlet and switch defaults remain 0.30 m and 1.20 m above finished floor.
- Exact PDF legend identities use hash-verified source artwork in 2D and in the placement preview. Entries without source artwork retain the schematic fallback. This does not change classes or detection results.

## Wiring and purchase pricing

- Material prices starts with wire/cable, followed by an automatically selected conduit. Designers do not choose an independent conduit.
- Admin → Wire & conduit pairs stores explicit product pairs and purchase lengths in the existing application-default JSON. A pair can include a conductor count and its supported installation specification. Existing defaults remain readable. No compatibility table was added.
- A known wire selection without a configured pair leaves conduit cost incomplete. VED does not infer conduit fill from conductor cross-section or pick an arbitrary pipe. The current imported catalog has prices but no complete compatibility matrix; Admin must configure the applicable pairs before those selections can resolve automatically.
- Inspected the approved supplier review, brand compilation and supplied client-price workbooks. Supplier rows identify products, units and some explicit roll lengths, but contain no wire/conduit compatibility or circuit conductor-count table. Synthetic expected-results examples are explicitly fictional, not an engineering approval. No unverified production pairing or conductor multiplier was seeded. A cable's pair/core count is not a multiplier for purchasing individual conductors.
- Roll/length inputs display prices in their purchase units. Backend calculations retain measured metres and convert them to purchase quantities using recorded lengths. Identical products share stock per floor: 101 m across branches needs two 100 m rolls, not a new roll per branch. Subtotals and total use backend results.
- Explicit designer prices keep priority; compatible client prices retain priority over catalog defaults. Historical estimate snapshots are not rewritten. Current calculator choices remain draft calculation inputs, consistent with the existing calculator.

## Verification

- PASS: frontend production build and scoped ESLint; Python module compilation and OpenAPI generation.
- PASS: transaction-scoped local database exercise of password sign-in, Admin project assignment, assigned designer access, CLIENT mutation rejection and unpublished-draft rejection. Temporary accounts/projects were rolled back and the project count was preserved.
- PASS: direct calculation of 101 m in two branches → two 100 m rolls; exact source-legend PNG read; vertical wall drag, wall snapping and attached-wire movement.
- PASS: browser verification of the current designer's five existing projects, client grouping, dashboard charts and dark-theme readability.
- PASS: active plan 9401 backend takeoff returned 88 items and PHP 11,477.8676 accumulated pricing. The old browser tab for removed plan 9402 correctly remained unavailable; its lifecycle was not changed.
- PASS: real-XAMPP, transaction-scoped API exercise of Admin-created Designer and Client accounts, normal password sessions, nonempty assignment labels, unknown-Google rejection without insert, explicit identity linking, session revocation after edit/delete, stale-write rejection, protected Admin removal, role authorization, and preserved project/estimate records. All temporary records were rolled back; original account count was checked unchanged.
- PASS: publication API with an isolated saved canonical layout and database-price estimate snapshot: Admin publication, client scoped read, rejection before publication/without authentication/for client mutations, and unchanged published total after a newer estimate. Temporary fixture data was rolled back, not published as a real client deliverable. The live project's saved-layout/estimate prerequisites remain explicit.
- PASS: browser inspection of the new sign-in-method rows, user search, edit/delete warning dialogs (cancelled), and project creation showing the configured Designer. Screenshots are in `outputs/workflow-verification/`. No real credentials, roles or access were changed through the browser.
- NOT TESTED: real-client WebGL presentation and end-to-end Google provider linking. API verification is not a claim of a published real-client project or completed Google provider round trip.
- NOT TESTED: complete Google linking with a second account, live client password entry, every device family and all mounting edge cases. These require the user's normal account and project workflow.
- NOT CONFIGURED: catalog-wide engineering compatibility pairs. The Admin editor is available; no unverified pair mappings were seeded.
- Existing full editor-suite failures were not rerun or claimed green. No new tests were written or test suites run. Vite continues reporting the existing large-chunk warning.

Changes remain uncommitted in the existing dirty worktree. The stash, original uploads, reviewed layouts and historical estimates were not reset or deleted. This checkpoint adds no model training, detector retuning or routing regeneration.
