# VED Gantt chart

`ved-gantt-chart-2026-10-14.drawio` is one native editable canvas with two stacked tables, following the supplied manuscript's Gantt design. Task labels, status/place descriptions, month/week headers, legend and schedule cells remain editable shapes and text.

## Sources

- Schedule: `C:/Users/kupal/Downloads/VEDGantt-Chart.xlsx`, sheet `Thesis Gantt`, rows 3-42, columns A-M.
- Design: the one-page manuscript PDF supplied in Downloads. The rendered reference shows two stacked tables, boxed chart titles, month headers with W1-W4 subdivisions, colored cells, a right-hand status/description column and a compact legend.

The workbook is the source of task names, places, statuses, phases and timing. It contains 35 activities: 29 Completed and 6 Planning. Colored blank cells, not numeric dates or formulas, carry the month schedule. The manuscript supplies design only; its tasks, dates and progress were not reused.

The two tables cover January-June and July-October 2026. Each task appears once, in the panel containing its scheduled months. Documentation is divided between the two panels while retaining its source phase schedule. January-October, including empty June and July task periods, is preserved.

## Timing and source issues

The source gives month-level timing, not weekly or daily dates. Each colored source month is displayed across W1-W4 to match the reference's visual structure. A note in the chart explains this; the week cells are not independently supplied weekly deadlines.

The Phase 2 heading says August-September, while its colored source phase cells span August-October. The chart preserves the colored phase cells and omits date ranges from phase headings. Replacement characters in obvious dash positions are displayed as ASCII hyphens; source strings are retained in `source-schedule.json`. No workbook or PDF content was modified.

## Verification

- PASS: all 35 task labels, statuses and places match the source after whitespace/dash normalization, including checks against the saved XML.
- PASS: all 56 scheduled task-months become exactly 224 colored W1-W4 cells; unfilled months remain blank.
- PASS: every task appears once and source phase colors are retained in the appropriate panels.
- PASS: the saved XML parses, references valid parents and contains editable shapes/text rather than a flattened image.
- PASS: text fits; the rendered chart was visually inspected.
- PASS: source workbook and PDF hashes remain unchanged.
- NOT TESTED: import into the diagrams.net editor; independent saved-XML checks were performed.

The builder, PNG/SVG preview and verification records are supporting files. The requested deliverable is the draw.io document in Downloads.
