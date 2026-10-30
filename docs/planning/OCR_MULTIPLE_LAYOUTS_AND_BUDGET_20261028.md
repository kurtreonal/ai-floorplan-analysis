# Additive OCR, multiple layout types and project budgets

## Workflow

Add floors is an always-visible form with floor name and count. It no longer asks for a default layout. Select one or more Lighting, Power and Data checkboxes for each uploaded file. The same controls are available for Client-endorsed files and in saved floor-plan Options. At least one selection is required by the UI before a new upload starts analysis.

The existing single-value API remains readable. New multi-value selections reuse the append-only material-selection JSON. Catalogue/palette filters use the union of selected types. On mixed sheets, connected lighting/power and data networks receive their own snapshotted Admin wire defaults rather than one product being applied indiscriminately. Unknown network families remain unresolved. Reviewed geometry, per-item choices, approved prices, conduit rules, conductor-count assumptions and measurement standards are preserved.

## Background OCR

The CV worker adds real OCR words and dimension/scale evidence to the existing candidate envelope. Local VLM page preparation also receives actual words instead of simulated `SYM_` tokens. No OCR panel or result overlay was added.

Recognition is offline. Windows uses its installed Windows.Media.Ocr language engine through Windows PowerShell 5; an already-installed Tesseract CLI is also supported. No model download, Python dependency, global execution-policy change or software installation is required on the verification machine. Other hosts need one of those local engines; unavailable OCR leaves existing detection operational.

OCR-only derivatives remove ruling lines and include enlarged text regions and bounded overlapping views. Subprocess work is time bounded, temporary derivatives are discarded, and coordinates map back to source pixels, including selected-region offsets. Numeric words receive priority, and each CV view contributes at most 256 words so eight views fit the existing candidate envelope. Original images and detector inputs are untouched. The OCR version is included in processing configuration provenance.

Printed numbers and line associations are evidence, not calibration. Explicit units are required for a dimension scale proposal; bare numbers remain unknown. Multiple labels on one chain are not each assigned the full chain span. OCR does not change existing source scale, ruler calibration, PDF dimensions, height presets or BOM measurement precedence. Faint/conflicting readings are never silently promoted to measured lengths.

**Known limitation:** the supplied small, blurred crop did not yield a reliable reading of the full overall dimension with the installed engine. Some shorter numeric labels were recognized. Its overall label and supplied span sum also disagree. No building length was forced from this sample. Clearer source scans or another installed supported OCR engine may improve recognition.

Microsoft reference: [OcrEngine.RecognizeAsync and its SoftwareBitmap input](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.recognizeasync?view=winrt-26100).

## Budget

Admin project creation and Client project submission require an allocated PHP budget. Client supplies the initial amount and cannot subsequently edit it. Admin can change it through project details or assignment. Assignment requires an existing or entered budget. Server-side permissions, validation, optimistic revision checks and same-value retry handling protect these operations.

Budget is stored in existing project-assignment intake JSON as an exact decimal string. Legacy projects without a budget remain readable and must receive one before assignment. No new column, table or migration was added.

The overall project BOM compares backend totals with the budget, showing remaining funds or the over-budget amount. Incomplete totals are labelled as priced subtotals. Client comparisons use the Admin-published captured estimate, never private designer drafts. Historical quantities/prices remain unchanged; the comparison uses the current allocated budget. Foreign currencies are not silently converted to PHP, and an unavailable estimate is not treated as zero.

## Verification

- **PASS:** focused ESLint, Vite production build and Python compilation during implementation. The existing large-chunk build advisory remains.
- **PASS:** OpenAPI generation: 98 paths, 50 existing mapped tables. The live server exposes required budgets for Admin creation and Client submission.
- **PASS:** rollback-only MySQL checks for mandatory budget, Admin-only edits, Client submission retries, assignment, exact over/under-budget arithmetic and persisted mixed-layout defaults. Temporary records were rolled back.
- **PASS:** existing focused rollback checks for per-device/network products, frozen captured prices, source bindings and reviewed-geometry preservation.
- **PASS:** actual local OCR produced valid candidate evidence without changing original bytes or geometry. Full headline recognition on the supplied crop remains limited as described above.
- **PASS:** actual Designer browser view shows always-visible Add floors and simultaneous Lighting/Data checkbox selection. No file or project edits were saved during browser inspection.
- **NOT TESTED:** a complete new upload/analysis job, Client endorsement upload, and Admin/Client browser approval flows. No test files were added and no test suites were run.
