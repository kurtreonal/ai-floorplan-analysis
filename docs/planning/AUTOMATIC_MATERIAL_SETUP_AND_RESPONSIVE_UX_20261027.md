# Automatic materials and workspace usability — 27 October 2026

Update 28 October: floor layout defaults were removed from Add floors. Per-file layout selection now uses multiple checkboxes. See [OCR, multiple layouts and budgets](OCR_MULTIPLE_LAYOUTS_AND_BUDGET_20261028.md) for the additive follow-up.

## Designer workflow

Choose Lighting, Power or Data when adding floors or uploading a floor plan, before analysis. The floor supplies an editable upload default. A saved plan's Options menu contains its layout type and file details. The BOM displays the type rather than offering a competing selector. Legacy API clients and existing plans remain readable; a legacy plan without a type is directed to Options before starting analysis.

Layout type filters product choices and the device palette; it does not delete detections or regenerate reviewed geometry. Changing a saved plan's type preserves individual choices and historical estimates. Incompatible existing choices remain reviewable rather than being silently replaced.

New uploads capture the applicable Admin wire product, defaults revision and estimated individual-wire count in the existing append-only material-selection JSON. Lighting/power currently use the configured Phelps Dodge 3.5 mm² THHN product; data uses the configured CommScope cable. These identities come from stored Admin settings, not official prices hard-coded into React. Explicit designer choices and compatible client quotes retain their existing precedence. Later Admin changes do not silently rewrite captured selections or historical estimates.

The initial Admin planning count is three individual wires per path when the drawing/circuit supplies no count. This is an editable estimating assumption, not an electrical sizing rule. A 10 m path with three individual wires needs 30 m of wire. A complete 10 m data cable remains 10 m of cable: its internal cores/pairs are not a purchase multiplier. Existing known counts take priority over assumed counts. Applying a product without editing the prefilled count does not turn that assumption into a designer-confirmed value.

## Assistance and direct repair

The canvas help button provides a Getting started guide. Collapsed explanations in device, wiring, architecture and measurement inspectors describe paths, wire size, individual-wire counts, complete cables, conduit, purchase lengths, heights, terminals, snapping, rooms, sheet scale, ruler calibration and estimated measurements.

BOM links carry the source-bound item identity and a repair action. They select that item, scroll the workspace into view, open its editor, highlight the relevant control and explain the required change. Device links focus Brand / product. Wiring links can focus wire product, conduit product, individual-wire count, metres per roll or metres per conduit length. Existing measurement and geometry repair flows remain separate.

## Responsive layout

The material inspector uses one full-width column, compact checkboxes, readable controls, wrapped product descriptions, a sticky Close control and reachable Apply action. The device list shares the inspector's scroll instead of creating a narrow nested scroll area. Phone controls have 44 px targets and 16 px input text. Fit/zoom controls wrap at narrow widths.

Phone client lists retain Client and Open columns, with project count/status beneath the name. Project tables keep essential actions accessible; secondary information remains in Details. Saved-plan Options becomes a bounded, centered mobile popover with an explicit Close action.

## Storage and integrity

No table, migration, dependency, new test file or detector change was added. Floor defaults and source-bound plan selections reuse ItemPriceAssignment JSON and its revision/idempotency contract. Upload initialization uses the existing storage transaction hook. Project locks are acquired before floor/upload foreign-key insertion to keep lock ordering consistent with pricing saves. Original uploads, geometry, measurements and captured estimates are not rewritten by these UI controls.

Optional layout metadata extends existing floor/upload APIs. GET/PUT plan layout type uses `/api/projects/{project_id}/floor-plans/{floor_plan_id}/layout-type`, with existing project authorization and same-origin mutation checks. The inspected application has 98 OpenAPI paths and 50 mapped tables.

## Verification

- Focused ESLint and production Vite builds passed during implementation; the existing large-chunk advisory remains.
- Backend compilation/schema inspection passed. Rollback-only database checks exercised floor defaults, plan initialization, layout changes and estimate snapshot preservation; the original pricing-document hash was restored.
- Manual calculations verified 10 m × 3 individual wires = 30 m, and complete cable without an internal-core multiplier.
- Actual browser inspections covered 320/360/390 px phones, 768 px tablet, 844 × 390 landscape, 1024 px laptop and 1440 px desktop. Evidence is under `outputs/wiring-save-20261026/responsive-ux-20261027/`.
- No test files were written or test suites run. Verification did not save product edits to real plans, change real Admin prices or start a real upload/analysis job. A full new-upload-to-analysis user run remains for manual acceptance.

Manufacturer references used to distinguish individual building wire from complete multi-pair cable: [Phelps Dodge product categories](https://phelpsdodge.com.ph/product-category/infrastructure/) and [Belden cable specifications](https://catalog.belden.com/techdata/EN/BEL601_techdata.pdf). Neither reference establishes VED's assumed three-wire circuit design.
