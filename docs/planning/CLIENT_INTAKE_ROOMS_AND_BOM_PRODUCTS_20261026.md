# Client intake, rooms and BOM product choices — 26 October 2026

## Delivered behaviour

- Designer and Admin navigation use **Clients**. Each client contains its projects; existing project URLs remain readable.
- Projects show **New**, **1 day ago**, or a day count through 30 days, based on creation time. Older projects retain their normal metadata without a recent badge.
- Admin account forms collect first, middle and last names separately. Middle name is optional. First/last names, phone (at least seven digits) and location are required. Legacy display names are preserved until explicitly edited; names are never guessed by splitting an existing string.
- Project phone and location are required on new intake and project-detail saves. Existing incomplete records remain readable.
- Services are independent checkboxes: new construction, renovation, electrical, data, CCTV, maintenance and Other. Existing single-service values remain readable.
- Clients can send project details and original floor-plan files to Admin, optionally choosing a preferred managed Designer. Preference does not grant access or assign the project.
- A new request is owned by the reviewing Admin until an explicit assignment. Only the assigned Designer can then open its workspace. Client access to published designs remains read-only; the submission endpoints do not expose Designer drafts.
- Client file uploads reuse the existing content validation, safe storage, source identity and cleanup services. Project and file retries have stable request IDs. A failed multi-file operation retains completed uploads.
- Multiple floors can be added at once. The floor dropdown scopes the plan table. New unnamed plans display **Pending** alongside the immutable original filename. Designers can rename floors and plans separately; no original file is renamed or overwritten. Admin and authorized Designers can download an original for review.
- Room area, perimeter and dimensions derive from the room outline and the effective source pixels-per-metre. Rectangles show their actual side dimensions, including rotated rectangles. Irregular rooms use polygon area and show individual outline lengths when selected. Invalid/self-intersecting outlines do not receive an area; unscaled rooms ask for plan measurements. View zoom and display paper do not enter the calculation.
- BOM device rows open the matching **Brand / Product** fields. Brands filter the existing compatible, priced catalogue products. Applying a product appends a material-selection revision and refreshes backend quantities/prices. It does not change historical estimates. A single available brand is explicitly explained; missing catalogue brands or prices are never invented.

## Existing storage extended

Three nullable prototype fields were provisioned using the explicitly authorized local XAMPP administrator connection:

| Existing table | Field | Contents |
| --- | --- | --- |
| `users` | `profile_details` JSON | First, middle, last name, phone and location |
| `project_assignments` | `intake_details` JSON | Selected services, preferred Designer, pending/assigned status, retry identities |
| `floor_plans` | `display_name` VARCHAR(255) | Designer-provided display name |

There remain 50 tables. No new table, migration framework or migration file was introduced. The ORM includes these fields for fresh prototype schema initialization. `create_all()` does not alter existing databases: another installation needs an administrator to add the same nullable fields. The `intake_schema` service keeps legacy reads available and gives a clear setup message if provisioning is incomplete; no request attempts privileged DDL.

New writes retain existing same-origin/session/role checks, assignment boundaries and activity logs. Password bytes are not trimmed by profile-field normalization. Profile deletion clears the structured profile while preserving authorship history.

## Contracts

- `GET /api/client/designers`: available managed Designer IDs and display names only.
- `POST /api/client/projects`: client-bound request; supplied identity/ownership fields cannot assign another Client or Designer.
- `GET /api/client/projects/{id}/files`: the signed-in Client's own submission names only.
- `POST /api/client/projects/{id}/floor-plans`: multipart file, retry UUID, optional floor ID; only that Client's pending Admin request may receive files.
- `PATCH /api/projects/{id}/floors/{floor_id}`: Designer-only name change with expected previous name.
- `PATCH /api/projects/{id}/floor-plans/{plan_id}/name`: Designer-only display-name change with expected previous name.
- `GET /api/projects/{id}/floor-plans/{plan_id}/original`: Admin/assigned-Designer original download; safe stored-path resolution, private/no-store response.
- Existing project GET/PATCH contracts include selected services and intake/preference information. The details revision includes services.
- Existing material-selection storage/API remains authoritative. Partial product updates preserve unrelated saved settings.

## Verification

No test files were added and no test suite was run.

| Criterion | Status / evidence |
| --- | --- |
| Frontend build and focused lint | PASS; production build retains the existing large-chunk notice |
| Python compilation and OpenAPI generation | PASS |
| Structured profile and request save/reload | PASS; real services within an outer rollback transaction |
| Preferred Designer and multi-service persistence | PASS; request retry returns the original request |
| Client isolation and Designer assignment | PASS; another Client is denied; unassigned request is absent from Designer projects; explicit Admin assignment grants access |
| Multiple pending floors / files | PASS; two originals, stable retry, pending names, and floor/plan renaming verified |
| Original integrity | PASS; original filename and byte content retained after renaming; generated verification files were cleaned up |
| Backend product pricing | PASS; compatible CCTV product selection appends a revision, applies its price, and preserves other settings |
| Existing data after verification | PASS; temporary database work rolled back and row counts restored; previous material-selection document restored |
| Room calculation | PASS; 400 × 300 source-pixel rectangle at 100 px/m is 4 × 3 m, 12 m², 14 m perimeter; missing scale does not produce metres |
| Live browser | PASS: Clients hierarchy, recent badges, floor selector and pending-plan table inspected in the existing Designer session. Selecting a saved room displayed 10.2 m², 3.49 × 2.92 m and 12.83 m perimeter without unsaved geometry; room measurements occupy the contextual inspector directly. |
| Client/Admin browser sign-in and submission | NOT TESTED in those role sessions; the active Designer session was retained |

Private calculation/transaction evidence: ignored `outputs/wiring-save-20261026/client-workflow-verification.json`. No production project, estimate or reviewed geometry was saved by these checks.
