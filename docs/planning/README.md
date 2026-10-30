# VED sprint planning boards

The current design follows the six sprint-board figures in C:\Users\kupal\Downloads\reference.pdf: Focus/Goal on the left, lime-green Activities and Milestone Deliverable headers, and a Status/Timeline/Team strip below.

The editable deliverable is ved-sprint-planning-board-2026-10-12.drawio. Each of the six project phases is a separate diagrams.net tab:

1. Discovery and backlog creation
2. Prototyping and architecture
3. Foundational engineering
4. AI and electrical planning integration
5. Quality assurance and optimization
6. Reporting, go-live and evaluation

The source PDF contributes only the design. VED content comes from repository requirements, implementation files and progress records. No reference-project company names, personal names, technologies, dates or claimed client approvals were copied into the plan.

Recorded foundation evidence and existing code are separated from pending human, browser, real-data, costing and production-release acceptance. The October 12-23 sprint window is proposed. Dates without repository evidence remain editable/TBD. Each Team section lists the five authors exactly as recorded in docs/THESIS_SOURCE.md: Aldrin E. Generoso, Kurt Isaiah R. Pascua, Lester C. Pajarillo, Angelo Luigi G. Matavia, and Kristian Kyle Elle P. Madridejo. Team roles and Name: TBD labels were removed. The senior paper remains the design reference and is acknowledged in each footer.

## Supporting files

- sprint-board-preview.html: all six boards in a local browser preview.
- template-sprint-1.png through template-sprint-6.png and matching SVGs: individual previews.
- template-sprints-overview.png: overview of all six boards.
- template-sprint-data.json: phase content, evidence paths, original stabilization tasks and detailed acceptance checks.
- sprint-board-verification.json: structural and rendering verification.
- build_template_sprint_board.py: current template-based generator.

The earlier Kanban draft and its generator remain available as supporting working material. Running the earlier generator would recreate the superseded three-tab design; use build_template_sprint_board.py for the current six-board design.

## Acceptance results

- PASS: six sprint boards match the reference's three-column and bottom-strip composition.
- PASS: all 190 text labels and design elements are native editable draw.io cells, not flattened screenshots.
- PASS: all five team names appear exactly once on every sprint page; roles and TBD name placeholders are removed.
- PASS: XML parses and every group parent resolves.
- PASS: text fits its bounds; all six rendered boards visually inspected.
- PASS: repository-based content separates recorded implementation from pending acceptance.
- NOT TESTED: opening the file in the diagrams.net editor.
- NOT TESTED: application regression tests during this artifact-only task. Recorded results are attributed to the repository ledger.

No application code, database records, model weights, original floor plans or source PDF were modified.
