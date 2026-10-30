# Workspace follow-up checkpoints

Requested 25 October 2026. Preserve the existing dirty worktree, originals, price history and stash. No new test files.

Delivery checklist:

- [x] Clean supplier-style BOM export; backend per-path measurements and group total explanation.
- [x] Persistent 2D symbol outlines; unique approved-reference matching; Admin image upload for legend artwork. Ambiguous classes still require review.
- [x] Full architecture without camera-aware cutaway; devices and routes visible through occluding surfaces, display-only.
- [x] Delete account profile, credentials, Google links and recovery channels; retain only the anonymized authorship key and history. Active Users hides removed accounts; append-only activity records the action.
- [x] Project creation, progress and project list on a separate project page, not Administration.
- [x] Shared small success/error notifications for user/Admin writes.
- [x] Primary/backup email and sign-in/recovery code implementation, expiry, limits and no code logging. Gmail authentication and a real test-message relay acceptance verified after the user replaced the App Password. Actual account enrollment/OTP inbox receipt still requires the user.
- [x] Editable provisional material pairings using catalog SKUs and explicit assumptions, not falsely verified compatibility. Saved 19 rules through Admin 108.
- [ ] Complete coverage of all device variants with current confirmed shop prices. Published 16 researched components and 18 recipes; catalog now contains 31 assemblies. Missing or incompatible variants remain visibly unpriced.
- [x] Designer draft submission and Admin approval without pretending unmeasured drafts are metric canonical layouts. Admin review geometry is read-only.
- [x] Supported homerun-to-panel routing proposals using the existing pathfinder; preserve observed geometry. Ambiguous panel references do not get guessed.
- [x] Fitting-size/material compatibility checks against stored supplier identities (3/8, 1/2, 3/4, screw/thread types).

Verification: focused builds/lint, calculation/API checks and real browser output. Record each checkpoint honestly. Email setup and external source availability are prerequisites, never mocked production success.

## Verification checkpoint — 25 October 2026

| Acceptance | Status | Evidence |
| --- | --- | --- |
| Gmail SMTP username is the configured sender address | PASS | Corrected ignored root `.env`; compared values without printing credentials. Password was not changed. |
| Restart and API health | PASS | Restarted only the verified VED Uvicorn process, hidden window; `/health` returns `ok`. OpenAPI has 88 paths. |
| Actual email authentication and SMTP relay | PASS; inbox receipt NOT TESTED | Initial AUTH failures resolved after the user replaced the App Password locally. Secure SMTP authentication succeeds and Gmail accepted one actual delivery-check email addressed only to the configured sender. No password or code printed. The initial restart left orphan workers alive; see the corrected live-server checkpoint below. Inbox/spam receipt has not been confirmed by the user. |
| Primary/backup verification, sign-in challenge, expiry and recovery | PASS for application logic; live account enrollment NOT TESTED | Inline manual checks with a mail stub and temporary database rows: code hashing, no code in API responses, primary/backup enrollment, replay rejection, five-attempt lockout, pending session restrictions, trusted HttpOnly device, backup recovery, trust revocation. Transactions rolled back. User must complete real email enrollment/OTP entry; no live authentication credential entered by the agent. |
| Account deletion | PASS | Temporary account proof removed password, linked identity, email challenges and trusted device records, anonymized profile, preserved authorship key; rolled back. No real user deleted by verification. |
| Draft submission and Admin decision | PASS | Rolled-back manual database checks for idempotent submission, current revision, approve without canonical promotion, stale-revision rejection and immutable saved review. |
| Admin draft viewing | PASS | Actual browser: no edit/save tool actions; item details disabled for mutation, selection and navigation remain available. Backend Designer role restrictions retained. |
| Legend artwork | PASS | Rolled-back database proof: JPEG normalized to PNG, append-only record, SVG/oversize rejected; no artwork proof row retained. Actual canvas symbol selection opens inspector. |
| Group and individual lengths | PASS | Browser shows 23 paths as a combined group; selecting Path 1 shows 5.25 m separately while the group stays 75.8264 m. Shared spans/drops are deduplicated in group quantities. |
| Clean BOM arithmetic | PASS | Real plan 9401, job 24366: seven grouped purchase rows export PHP26,025.77, exactly equal to backend PHP26,025.77. No source tags or calculation paragraphs in CSV. Blank unknown prices stay blank. |
| Real 3D output | PASS for visibility; broader performance NOT TESTED | Browser WebGL renders full walls with readable foreground route inspection strokes. Camera-dependent cutaway removed. Inspection strokes/material depth settings are display-only, not quantity geometry. |
| Provisional material pairing and purchase units | PASS for stored planning rules | 19 actual catalog wire SKUs paired; 305 m, 1000 m and 500 m roll annotations recognized. Unknown lengths remain unknown. No invented conductor multiplier. Engineering fill/diameter/segregation approval is NOT claimed. |
| Fitting checks | PASS | Manual comparisons reject mismatched half/three-quarter inch and compression/set-screw/thread styles, accept equivalent 1-1/4 and 1.25 inch. Catalog checked against actual Panasonic set-screw SKU descriptions. |
| Homerun route proposals | PASS for bounded algorithm | Inline calculation checks: orthogonal 160-pixel Manhattan-optimal path for an unobstructed fixture, duplicate prevention, no arbitrary panel when multiple choices. Real drawing-specific electrical approval NOT TESTED. |
| Price review workbook | PASS | Two sheets, 28 assemblies / 50 component lines, formula reconciliation to database, error scan and both rendered previews. Review copy only; editing it does not upload catalog changes automatically. |
| Frontend build and focused ESLint | PASS | Vite production build (2,238 modules) and 18 directly affected JS/JSX files. Existing large-chunk warning retained. |
| Python and whitespace checks | PASS | AST checks on 290 application/provision/import files; focused `git diff --check`. No new test files and no full test suite run. |
| Client publication | NOT TESTED | No eligible saved-estimate publication was invented or sent to a live client. Planning-draft Admin review is independent of final client publication. |

### Price provenance and limits

- Import attribution: Admin 108, as authorized. Existing supplier material identities/prices were not overwritten. Shipping and installation excluded.
- Published shop hardware quotes and historical dealer SRPs are distinguished in stored recipe references and the Excel component/source detail. Historical Firefly/Ecolum SRPs and cached MC-31 pack pricing are not represented as current checkout/stock confirmations.
- Wireless keypad/vibration and a Koten panel enclosure/board choice are non-default where the source system or breaker ratings are unresolved. No generic panel is silently replaced with an arbitrary rated board.
- Lazada/TikTok pages without a verified selected variant price were not imported as prices; shipping fees were not mistaken for product prices.
- Remaining exact protection/rating variants (including weatherproof/floor receptacles, certain luminaires and panel equipment) are incomplete rather than zero-cost complete. A sourced 20A GFCI option was added below; it never substitutes a conflicting rating.

### State and handoff

- Branch remains `codex/vlm-localization-experiment`, HEAD `a823ce5`. No commit or push: live account enrollment and complete variant coverage remain unverified, and unrelated detector/editor work is present in the shared dirty tree.
- The existing stash `stash@{0}` / `bb78854` remains intact. Originals, reviewed geometry and historical estimate snapshots were not rewritten by these checks. No live project was approved, published, deleted or implicitly saved during browser verification.
- Database now has 50 tables. Provisioning was additive using the existing SQLAlchemy definitions and the authorized XAMPP administrator configuration; no Alembic migration or table deletion.
- Browser warnings observed: existing Konva layer-count warning, Three.js Clock/PCFSoftShadowMap deprecations and graphics-driver precision warnings. No claim of a green full editor suite or 500-device performance benchmark.
- Deliverable: `outputs/workspace-followup-20261025/VED-device-pricing-review.xlsx`. Browser proof images and generation inputs remain in the same task output folder. Secrets are excluded.

## Follow-up checkpoint — live email readiness and purchase-unit labels

### Email root cause and correction

The browser was still served by old Windows Uvicorn workers. The virtual-environment Python launcher added an extra process layer: launcher, base-Python reloader, then spawned worker. Stopping only the launcher and its immediate child left workers alive with inherited listening sockets. Windows socket enumeration attributed those sockets to already-exited owners, so that PID alone did not identify the active worker.

Verified the exact old worker command lines, backend working directory and parent IDs before terminating only the three stale VED workers. Started the replacement launcher (PID43464) hidden with the explicit root `.env` and `--reload --reload-dir app`. Future restarts must inspect and stop the entire verified descendant tree, not arbitrary port-owner IDs. No other application process was targeted.

The authenticated live browser GET `/api/auth/emails` now returns `delivery_available: true` and an empty `delivery_missing_settings` list. Reopening Manage emails shows an enabled **Send verification code** action without the setup warning. The endpoint is non-cacheable; the dialog re-fetches readiness on every open and offers a refresh action when delivery is unavailable. Readiness checks unwrap secret settings before validating nonempty values, without exposing their contents.

| Acceptance | Status | Evidence |
| --- | --- | --- |
| Live email configuration loaded | PASS | Actual authenticated browser API response and Settings dialog. Screenshot: `outputs/workspace-followup-20261025/email-delivery-ready.png`. |
| Actual primary/backup enrollment and inbox OTP receipt | NOT TESTED | User must submit their own VED password where required and enter their received code. No real authentication channel or credential changed by the agent. |
| Per-roll input uses a per-roll amount | PASS | Rendered React component checks: PHP12/m becomes PHP3,660 per recorded 305m roll; legacy PHP15/m becomes PHP4,575; selected catalog/saved overrides retain their purchase-unit amounts; unknown purchase length leaves the amount blank. |
| Backend purchase arithmetic and client-price precedence | PASS | Inline calculation: 200m + 115m, 305m rolls at an edited PHP4,000 gives two rolls/PHP8,000 per floor. With no override, client PHP12/m remains PHP3,780. No new test file. |
| Additional supplier assemblies | PASS | Dry run rolled back, then authorized Admin108 publication added three components and three recipes, replacing no existing price. Database totals: Royu WD933 GFCI with box allowance PHP1,234.50; Panasonic WEG2164 voice outlet/plate/box PHP639.50; Fumaco pull box/cover PHP360. Conflicting 10A GFCI rating rejected. |
| Updated review workbook | PASS | 31 assemblies / 55 component lines, all formulas reconciled to database totals. Error scan clean, both sheets rendered, exported workbook re-imported; temporary component-price change propagated to the assembly total and was restored in memory without exporting the temporary change. Native Excel app behavior NOT TESTED. |
| Focused verification | PASS | Vite production build: 2,238 modules. Focused ESLint on email UI, auth request module and manual BOM settings. AST parse: 288 application Python files. Focused whitespace check clean. Existing large bundle warning remains. No new test files; full suite not run. |

### Remaining catalog coverage

The current active-legend audit finds 13 source entries across eight device types without a compatible priced recipe. These are not counted as completed coverage:

- Three circuit-breaker descriptions, including NEMA-3R and air circuit breaker: required load/rating/enclosure and interruption specifications are missing. No arbitrary breaker rating selected.
- Duplex floor-mounted data outlet: a compatible two-data-port floor assembly and selected variant quote remain unconfirmed. Power or telephone floor boxes are not equivalent.
- 200mm recessed downlight: manufacturer/seller dimensional descriptions do not agree on body versus cutout sizes. For example, SmartLED's 20W model is 228mm overall/203mm cutout, not an exact 200mm body. Omni's seller inch description conflicts with the catalog diagram. No false exact match imported.
- Weatherproof grounded duplex 10A 250V: priced 20A/220V GFCI sets are not equivalent; a compatible Panasonic cover and complete plate/box recipe still need confirmation without counting the plate twice.
- Two fan-controller entries: marketplace category prices exist, but exact selected model/motor compatibility are unverified. A light dimmer is not substituted for a motor controller.
- Fire alarm panel: a Shopee four-zone panel offer exists, but the system/model and compatibility remain unconfirmed. A generic panel is not a complete compatible alarm system.
- Three motion-detector entries: wired low-voltage security detectors must not silently become mains lighting sensors or wireless accessories. No confirmed PH selected-variant quote found for the supported wired model.
- Troffer: housing-only quotes are not complete luminaires. One lamp seller page gives contradictory 1198mm/588mm and 18W/9W specifications, so it was not combined with a guessed housing.

Sources and limitations remain in quote JSON/recipe references. No shipping, foreign-currency quotes, unselected variant starting prices or marketplace shipping fees were imported. Editable wire/conduit planning rules remain assumptions, not a professional fill/segregation approval.

Branch/HEAD and stash remain unchanged. No commit or push: complete variant coverage and live account enrollment remain open. Existing unrelated work, originals, reviewed edits and captured historical estimates were preserved.

## Follow-up checkpoint — actionable catalog coverage and current price download

- Added read-only coverage to the existing Admin assembly GET contract. It uses the same protected specification/default resolver as the draft BOM, with no new table. Active source aliases remain separate backend entries and are grouped only for display.
- Admin now sees **Device pricing coverage**, with separate reasons for a missing product, a missing component price, a product/specification choice, or incomplete components. Add assembly pre-fills the existing legend description/type, marks it as assumed, collapses the list and brings the form into view. This does not create a detection class or save a recipe implicitly. Existing/new recipes can retain/edit their source links.
- Added Admin **Download price list** and an authenticated `/api/admin/material-assemblies/price-list.csv` GET endpoint. Simple columns: Category, Product name, Brand, Item number, Specification, Unit, Unit price, Currency. It exports backend quotes, not a new frontend calculation. Source tags/diagnostic paragraphs stay out; unavailable prices remain blank. CSV formula injection is escaped. Project BOM and historical estimate exports retain their existing behavior.
- Published three further sourced components/recipes under the authorized Admin108 after a rolled-back dry run. Catalog now contains **34 assemblies**. No prior product price was replaced, and no shipping was added:
  - Panasonic WEG8981P plastic cover: exact Kaizen variant 43256154652803, PHP950, confirmed through public variant data (the metal cover is a different PHP1,525 variant). With the existing approved grounded 10A/250V duplex set/plate and VED utility-box allowance, the weatherproof recipe is PHP1,467.50. Mounting, sealing and box fit remain explicitly incomplete.
  - Fumaco TT00475 recessed 12 x 24 inch troffer: manufacturer variant 46745074893033, PHP978, explicitly sold with one 8W daylight LED lamp. This is not a housing-only price.
  - Royu RWF60/2XRWX3 gold two-port floor data outlet: Electx selected variant 41494208643147, PHP1,875. No CAT6 performance claim invented.

### Verification

| Acceptance | Status | Evidence |
| --- | --- | --- |
| Current quote/default matching | PASS | Database prices reconcile to PHP1,467.50/PHP978/PHP1,875. All three appear as compatible designer choices and resolve for their supported generic legends. Explicit CAT6 floor data and 2 x 18W troffer requests reject these conflicting substitutes. |
| Live Admin coverage and form | PASS | Actual browser shows 15 distinct descriptions needing attention, grouped from 26 source entries. Confirmed Add assembly pre-fills the 200mm downlight name/type and assumed flag. Canceled without saving. No source class was modified. |
| Price download and authorization | PASS | Real authenticated Admin browser download succeeded with a small success notification. All 34 exported prices reconcile to database values; source-tag removal, blank unknown prices and CSV formula escaping checked. Isolated Designer request returns 403. |
| Current drawing access | PASS | Plan9401/job24366 opened in 2D and actual WebGL 3D as read-only Admin. Full architecture and foreground route presentation remain available. No draft geometry or saved review was changed. AX includes the canvas fallback text even when actual WebGL renders; screenshot/shader logs confirm the rendered result. |
| Build/lint/syntax | PASS | Focused ESLint on AdminAssemblies and materialPrices; Vite build 2,238 modules; AST parse of 288 application files; focused whitespace check. No new test files. Full suite not run. |
| API availability | PASS | Running `/health` is `ok`; 89 OpenAPI paths including the new Admin price-list route. No schema/table change. |

The earlier 31-assembly Excel review is retained as that checkpoint's review copy; the new live Admin CSV is the current 34-assembly export. The PDF/Excel originals were not rewritten. Remaining **missing products** cover ten active source entries across five device types: circuit breakers, the exact 200mm downlight, fan controller, fire panel and motion detector. Other attention rows already have prices but need a compatible system/rating choice or component confirmation. These are not zero-cost completed estimates.

Browser proof: `outputs/workspace-followup-20261025/admin-price-coverage.png` (download success and coverage); `current-plan-3d-check.png` (actual drawing). The current plan browser tab remains available; temporary catalog verification tab was closed. Live email enrollment/OTP receipt still belongs to the user. No real account/password/role/project was changed during verification.

The first inline authorization check stalled under restricted Windows socket permissions; its exact two-process launcher tree was verified and stopped. The same isolated check succeeded with approved local permissions. Uvicorn was not stopped. Existing Starlette TestClient/httpx deprecation and large-bundle warnings remain; no dependency was installed to suppress them. Branch HEAD `a823ce5` and stash `bb78854` are preserved. No commit or push while unresolved coverage and unrelated shared edits remain.
