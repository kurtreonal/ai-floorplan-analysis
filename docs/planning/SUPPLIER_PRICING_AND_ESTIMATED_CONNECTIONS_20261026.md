# Supplier pricing and estimated connections

The supplier workbook and six PDFs were re-read without changing the originals. Existing matching prices were retained. The Admin catalog received missing source offers, two separate Belden CAT5e/CAT6 loaded pop-up assemblies, and watertight hubs. Three bundles with contradictory connector labels remain inactive for source review. Three cable offers without a usable supplied quote remain unpriced. Existing power-outlet and switch assemblies were preserved: these seven files do not supply replacement power-device prices.

Admin defaults revision 7 exposes 69 actual conduit products across EMT, IMC, RSC and flexible families, with 31 wire pairing records. These are budgeting choices where specifications are incomplete, rather than verified conduit-fill calculations. EMT tubing fittings remain distinct from threaded IMC/RSC pipe fittings. An included IMC coupling is not charged a second time.

## Designer controls

- The conduit input displays the current product and searches only the wire's allowed products. Sizes and brands can be searched; a bare "Automatic by placement" placeholder is no longer shown.
- Product choices and explicit prices use the existing append-only item-price JSON, with project defaults and plan overrides. Other price writers preserve these settings.
- A product can be saved before its pack length is known. Missing roll length is identified explicitly and remains incomplete rather than becoming a one-metre roll or zero-cost item.
- Quantity warnings navigate to the source plan, page/job and affected wire/device. Under-floor depth uses a positive depth input; the canonical relative height remains negative for a depth below the floor.
- Connection warnings target the actual unresolved member, rather than the first path in the price group. The inspector opens the relevant placement/start/end setting, outlines it in orange, and marks the loose endpoint on the plan. The general Check wiring list no longer presents healthy edited paths as errors.
- Saving material prices preserves the connection-estimate choice unless the user explicitly changes that checkbox. A direct Use defaults for estimated pricing action is also available in the focused wire inspector.
- Under-floor routing defaults to 0 m when no individual height/elevation is recorded. Explicit overrides remain intact. Both BOM drops/rises and the 3D projection use that floor-level default.

## Estimated connections

At the user's request, `assumeConnections` was enabled for project 10219 through a new item-pricing revision. It can be disabled in Material prices.

Only already included generated routes are considered. Calculation works on a copy of the draft: existing points, junctions, saved connection states and historical estimates are not rewritten. Defaults inherit the connected network's method and recorded height, then observed placement or the plan's ceiling/floor-level assumptions. Recognized panel equipment without a supplied individual height uses an explicitly estimated 1.8 m mounting assumption. Individual device heights and offsets take priority. Unknown source scale, NTS views, explicit conflicting materials and unknown equipment dimensions are not certified by this option.

Generated quantities remain separate as **Estimated connections** and contribute to **Estimated total**. Actual connection review remains available on demand.

## Lengths, units and shared purchases

Source-centreline metres and purchase quantities are different. Rolls/lengths use explicit recorded conversions; unspecified stick length retains the existing labelled 3 m budgeting assumption. Soft liquid-tight conduit follows its quoted 5 m ordering increment. Hard liquid-tight conduit stays priced per metre despite its spool-pack information.

Shared stock is bought once per floor/product/rate. The compact BOM allocates the full purchase cost among groups by measured usage, labelled **Share of purchase**. Backend purchase totals and captured unit prices remain authoritative. Allocation uses downward rounding and a final remainder so group shares sum exactly to the purchase total. Reports still retain actual purchase quantities; no extra roll is charged to each branch.

## Plain-language settings

| Setting | Meaning |
|---|---|
| Depth below finished floor | How far below this floor the wire runs; default 0 m. |
| Height above finished floor | Distance from this floor to the wire or device. |
| Separate wires | Individual conductors; not the cores inside one cable. |
| Circuit name | The drawing's circuit label; naming alone does not join endpoints. |
| Bends and wire joins | Edit route points or detach an existing junction. |
| Measure height to | Device centre, box bottom, or its wire connection point. |
| Connection offset | How far the connection lies above/below that reference. |
| Original paper and drawing scale | Convert source-sheet distances to real metres. |
| Display/print paper | Changes page presentation without changing quantities. |
| Metres per roll/length | Physical content of one purchase unit, needed for conversion. |

## Verification

| Criterion | Status |
|---|---|
| All seven source hashes preserved | PASS |
| Real catalog conversions: roll, stick, flexible roll, soft/hard liquid-tight | PASS — manual calculations |
| Saved choices, idempotent retry, plan/project consistency, other-plan preservation | PASS — real services inside an outer rolled-back SQL transaction |
| Admin price reaches live BOM | PASS — temporary price revision rolled back |
| Warning opens the appropriate plan-area control and exact wire depth field | PASS — browser, no geometry saved |
| Estimated connection no longer blocked by assignment warning | PASS — project BOM read |
| Shared cost is positive and shares equal purchase total | PASS — database calculation and browser; example estimated group PHP 36,877.34 |
| Under-floor depth is 0 with no manual entry | PASS — browser and backend |
| New tests or full test suite | NOT RUN — user requested no tests |

Private extraction, rollback snapshots and calculation receipts are kept under the ignored `outputs/wiring-save-20261026/` folder. No database table or migration was added. Unrelated working-tree changes and the stash were left intact.
