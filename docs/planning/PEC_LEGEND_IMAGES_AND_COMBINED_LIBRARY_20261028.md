# PEC images and the combined legend library

## Behavior

The supplied PEC reference pack provides 62 device-symbol crops. Its 12 wiring patterns remain separate from the device-image selector. Crops retain their source shapes and aspect ratios; display derivatives improve contrast and are contained within 256 px. The original PDF, reference manifests and source crops are not rewritten.

Add/Edit legend now offers the current/automatic image, a supplied PEC image with preview, or a PNG/JPEG/WebP upload. Wall and ceiling variants are separately identified. Existing recorded source mappings supply automatic image matches. Two presentation defaults additionally cover the legacy single-tube fluorescent-lamp entry and conventional smoke detector; they do not change the device class, mounting settings, specifications or prices. Exact drawing artwork and explicit Admin images retain priority.

Both import actions continue to add missing definitions to the same library, with their existing 80-trained / 40-drawing response contracts. Imports now fill missing matched PEC artwork in the existing append-only `legend_artwork` storage. Already assigned images, drawing-bound images and inactive choices are retained. Repeated imports do not add another image revision when nothing is missing. No model weights or detection classes are trained or activated by these actions.

Duplicate display names, including cosmetic `(new)` / `(old)` suffixes, are consolidated into one visible entry. Original source IDs and names remain readable for saved drawings and model-to-catalog bindings. Ratings, pole/gang distinctions, mounting variants and unresolved device meanings are not merged. Conventional and unspecified smoke detectors remain separate choices, even when they share a PEC symbol.

Image changes can apply atomically to matching copies of a legend. Availability changes likewise operate on the complete matching group, with history preserved. New manual definitions reject a duplicate normalized meaning. Source suffixes are retained during edits. The Admin no longer needs to manage duplicate rows individually.

## Existing storage and API

No table, migration or dependency was added. The existing artwork upload accepts optional repeated `legend_ids` form fields. New Admin-only endpoints list reference images, apply a reference image, and change matching entries' availability. Designers can read the reference PNGs. Mutation endpoints check the existing Admin role and same-origin policy. Batch operations reject unrelated device meanings.

The inspected API has 102 paths and 50 mapped tables. The PEC registry verifies the pinned cleaned manifest, prepared manifest, original PDF, source permission and image hashes. Automatic matches use the existing pinned reconciliation manifest. No source filesystem path is returned by the reference-image API.

## Verification

| Acceptance | Status |
| --- | --- |
| All 62 device images decode within the display bounds; wiring patterns excluded | PASS |
| Both import orders combine, repeated imports preserve source records and inactive choices | PASS — rollback calculation and live Admin buttons |
| Explicit Admin image choices survive subsequent imports | PASS — rollback database check |
| Manual legend creation, PEC saves, idempotent image writes and matching-group updates | PASS — rollback database checks |
| Duplicate manual definitions rejected; different ratings, poles and unknown meanings preserved | PASS — backend checks and inline Node calculations |
| Real PEC preview and automatic smoke-detector icons | PASS — actual Admin browser output |
| Actual source-image application | PASS — 12 appended images; all 106 existing legend identities and active settings unchanged |
| Visible library consolidation | PASS — 106 source records presented as 69 entries |
| Focused ESLint, Python compilation and production build | PASS; existing build-size advisory remains |
| New picker at phone width | NOT TESTED in the live browser; existing responsive form rules and scoped containment retained |
| Full automated suites | NOT RUN; no new test files written |

Local screenshots are under `storage/previews/ui-20261028/`, including `pec-legend-picker.png`. References without an established or explicit display match remain selectable manually; an unrelated PEC image is never guessed for an unsupported device. Existing geometry, measurements, material selections, prices and estimate snapshots were not edited by this work. The existing stash and unrelated working-tree changes remain intact.
