# Grouped wiring heights and Admin / Client UX

## Scope

This change adds grouped height editing, catalog-item creation, device-specific assembly naming guidance, direct legend management and responsive Admin / Client views. Existing measurement standards, material compatibility rules, drawing geometry and publication permissions remain authoritative.

## Wiring heights

`WireHeightEditor.jsx` offers the selected path and joined segments, the source-bound BOM group, all paths with the selected placement, or all ceiling / under-floor paths in the current draft. BOM dropdown selection determines whether the repair action supplies a group or a specific path. Joined segments remain together and the editor reports the actual affected count.

Ceiling / above-floor height and depth below floor use separate fields. Under-floor depth starts at 0 m. The ceiling suggestion comes from the existing effective plan settings. “Only fill missing heights” preserves explicit relative and absolute heights by default. Clearing it allows deliberate replacement. Device mounting heights, circuits, terminal offsets and XY path coordinates are not changed.

Applying heights creates one undoable draft edit and uses the existing BOM preview refresh. Save changes is still required for persistence. No implicit geometry save or new measurement API was introduced.

## Catalog and assembly contracts

Admin can add a product from Current catalog. `POST /api/admin/materials` accepts `code`, `name`, `category`, `unit`, `unit_price`, `currency` and optional `meters_per_unit`. A roll or length requires its supplier-stated purchase length; other units reject that field. Purchase lengths use the existing parsable product-name convention, without a schema change. The service creates the material and appends its first price revision atomically, with normal audit records.

An identical retry returns the existing item. A conflicting item code gives corrective guidance. Admin authorization and same-origin mutation checks apply. Existing estimates retain their captured prices. A new catalog item does not invent compatibility: Admin uses Device assemblies or Wire & conduit to include it in the appropriate choices.

The assembly listing adds optional `name_examples`. Device selection fills an untouched suggested name; custom names remain editable. A mismatched name is identified beside the name field and focused after rejection. For example, “duplex” describes an outlet; a selected two-gang switch should use a name such as “2-gang switch.” Existing device-type validation remains enforced.

## Admin and Client presentation

- Admin sections remain visible in a responsive navigation grid. Catalog search, category filters and 40-item pagination avoid rendering the complete price list at once.
- Device legends load immediately when their section opens. Name, image, status and edit actions appear together. Existing alias artwork is tried before showing a separate missing-image indicator. Missing artwork does not imply an unknown device class.
- Catalog and assembly forms preserve failed inputs and use relevant field guidance. Purchase-unit labels follow piece, metre, length or roll.
- Client projects use one searchable, sortable table with clear stages, read-only budget and backend-published estimates. Phone rows retain status and financial information beneath the project name. Pending designs explain when viewing becomes available.
- Client submission is a focused view with Back to projects. Approved layouts remain read-only. No draft access or new publication authority was granted.
- Admin table scroll containers establish their own positioning boundary. This prevents absolutely positioned screen-reader labels from expanding the phone document width while keeping wide tables locally scrollable.

## Verification

| Criterion | Result |
| --- | --- |
| Focused ESLint for the changed UI/API/route modules | PASS |
| Production Vite build | PASS; existing large-chunk advisory remains |
| Python compilation and OpenAPI contract | PASS; 98 paths, 50 mapped tables |
| Grouped / selected-network heights, custom-height preservation, zero depth, invalid-depth rejection, unchanged XY geometry and circuits | PASS; inline Node calculations |
| Absolute heights retained unless replacement is selected | PASS; inline Node calculation |
| Catalog creation, supplier purchase length, duplicate protection, repeat save and Admin-only service access | PASS; real local database transaction rolled back |
| Specific assembly-name rejection, all suggested names and valid assembly save | PASS; real local database transaction rolled back |
| Live grouped-height controls and source-group selection | PASS; authenticated Designer browser |
| Live catalog form, direct legend listing, two-gang name suggestion and Admin navigation | PASS; authenticated Admin browser |
| Phone / tablet layouts | PASS; actual app at 320, 390 and 768 px, plus desktop. Root document widths matched phone/tablet viewports after the overflow fix |
| Client status filtering and opening an existing approved layout | PASS; authenticated Client browser |
| Live published monetary total on the available Client project | NOT TESTED; its approved layout has no published estimate snapshot. No estimate was invented |
| Live business-data saves through the new UI | NOT TESTED; forms were inspected without submitting real catalog or project changes. Catalog / assembly persistence paths were checked in rollback transactions |
| Full automated suites | NOT RUN; no new test files were written |

The temporary responsive-review page was removed before the production build. Local screenshot proof is stored under `storage/previews/ui-20261028/`. Original uploads, saved layouts and historical estimate snapshots were not rewritten. The existing stash and unrelated working-tree changes were retained. No table, migration, dependency or official price constant was added.
