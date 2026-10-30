# VED use case diagram

This is a new use case diagram. Work on the discarded theoretical-framework revision stopped; it was not delivered as part of this request.

## Reference and design

The current `C:/Users/kupal/Downloads/ref.pdf` contains Appendix Figure 4, a SmartSpaceAR use case diagram. Only its visual structure is reused: one system boundary, named module ovals, smaller use case ovals, human pictograms outside the boundary, and a vertical module breakdown. SmartSpaceAR features and actor roles are not copied.

The supplied VED use case PNG supplies the proposed project functions, checked against the current repository before this revision. Four modules group twenty use cases. Three full-body, solid black human pictograms replace the original stick figures. Every icon part, oval, label, boundary and connection is editable native draw.io XML; the file contains no screenshot or embedded raster image.

Admin connects only to the four module ovals, as requested. Designer and planned Client connect directly to their permitted use cases. No A/D/C circles or continuation symbols remain. Admin-specific administration and inspection cases are labeled inside the breakdown; a module association does not grant every Designer write operation inside that module. Unlabeled dashed module links show scope, while labeled, directed dashed arrows show the audited UML include/extend relationships.

## Scope and repository evidence

| Actor | Use cases |
|---|---|
| Administrator | Module-level access: sign in, inspect projects/results/layouts/routes/estimates, manage legends, assign/revoke dataset approver, import global material prices and export cost/BOM CSV. General user/role management and broader dataset administration remain planned. |
| Designer | Sign in; create/manage owned projects and upload floor plans; open/edit/save layouts; view 2D/3D; analyze floor plans; review/confirm results and optionally correct them; configure/calculate routes; preview draft BOM/costs; generate compatible saved estimates; view saved estimates and optionally export CSV. |
| Client, planned | Sign in; view an authorized saved 2D/3D layout; view a saved cost estimate. |

Client receives no upload, editing, AI review, route calculation, estimate generation, price administration, export, or report access. This preserves the user's stated restriction even though the original attached PNG also mentioned Client reports.

The route inspection reconfirmed Designer write operations and Admin/Designer reads in `projects.py`, `floor_plans.py`, `layouts.py`, `processing.py`, `detections.py`, `routing.py` and `estimates.py`. Admin catalog/price administration is in `materials.py`, legend administration in `symbol_legends.py`, and dataset-approver assignments in `dataset_approver_assignments.py`. Dataset approval authority remains separate from having an Admin role. No new application permissions or product code were implemented.

The original framework's broader user/role and dataset administration remain planned and marked with asterisks. PDF reporting is identified as planned in the note; actual export is labeled CSV. Client remains a future role. Draft 2D/3D and draft cost previews do not require final approval; a saved authoritative estimate does require compatible reviewed layouts, routes and pricing inputs. The current estimator rejects saved planning-circuit records that do not have supported estimation configuration. This artifact does not certify a working end-to-end production pipeline.

## Include and extend audit

| Relationship | Direction and meaning | Evidence |
|---|---|---|
| Upload floor plan **includes** file validation | Upload -> Validate uploaded file. Validation is mandatory for a successful upload. | `floor_plan_storage.py:158` calls `validate_floor_plan_upload` before writing originals. |
| Generate saved estimate **includes** quantity/cost calculation | Generate -> Calculate quantities/capture prices/totals. Applies to new estimate generation; an idempotent retry returns the prior result. | `estimate_service.py:81`, `:103`, `:108`, `:186` derive quantities/lengths and capture the prices used. |
| Correct detections **extends** review | Correct -> Review/confirm. Extension point: examining AI suggestions; condition: corrections are needed. Reviewing acceptable results can finish without corrections. | `DemoInterpretationPage.jsx:468` saves the editable review payload; `demo_interpretation_service.py:212` stores review revisions. |
| CSV export **extends** viewing a saved estimate/BOM | Export -> View. Extension point: saved estimate/BOM is displayed; condition: an authorized Admin/Designer chooses Download. Viewing does not automatically export. | `BOMPanel.jsx:56` implements the optional download action; `estimates.py:120` checks Admin/Designer. |

The last two are user-goal models of optional UI behavior, not a claim that one HTTP endpoint internally calls the other. Client's association with estimate viewing does not grant the export extension: its planned role is explicitly view-only.

These meanings follow the primary OMG descriptions of [Include](https://issues.omg.org/issues/UML25-421) and [Extend](https://issues.omg.org/issues/UML25-418). The reference's visual structure is reused; its business relationships and double-ended dependencies are not copied mechanically.

No include/extend arrow is added merely because one activity occurs later. Upload does not itself run the analysis service. Processing has a separate start endpoint. Review is separate from processing, viewing 3D does not run 2D editing, and generating an estimate reads a compatible stored route rather than automatically generating a new route. Existing authentication is a precondition for protected actions, not a requirement to repeat sign-in inside every operation.

## Files and validation

- `ved-use-case-diagram-2026-10-21.drawio`: single-page editable source; open in diagrams.net using File > Open From > Device.
- `ved-use-case-diagram-2026-10-21.png`: rendered preview.
- `ved-use-case-diagram-2026-10-21.svg`: vector preview.
- `diagram-data.json`: module structure, actor associations and connection geometry.
- `verification.json`: verification results and delivered-file hashes.
- `build_use_case.py`: reproducible generator.

PASS: four named modules, twenty use cases, three editable human pictograms, Admin's four associations target modules only, Client has exactly its three requested case associations, two include and two extend arrows point in the correct direction, no continuation symbols, monochrome shapes, zero unrelated-shape collisions, text-fit assertions and native XML references. The final PNG was visually checked. Line intersections are present, as in the reference; they are not junctions or additional relationships.

NOT TESTED: opening the XML in the diagrams.net editor. The native XML, IDs, source/target references, page count and vector geometry were independently checked. Application tests are outside this artifact-only task.
