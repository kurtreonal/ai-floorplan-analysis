# Workspace integration and publication — 30 October 2026

## Current workflow

- Admin-managed username/password accounts with optional linked Google sign-in;
  unknown Google identities cannot create accounts. Recovery emails and
  sign-in verification use the configured SMTP service.
- Admin creates client/project information, assigns Designers and reviews saved
  proposals with comments. Clients see published layouts and estimates.
- Designer navigation groups assigned projects by client, with floor upload,
  layout types, synchronized 2D/3D editing, measurements and backend BOM pricing.
- Approved material catalogues, assemblies, wire/conduit pairings and purchase
  lengths drive pricing; product choices are available in workspace inspectors.
- Source-aware measurement, explicitly labelled estimates, routing heights,
  source wiring and separate panel-route proposals share the canonical data.
- 3D Studio uses the fresh representative asset library, direct device focus,
  Design/Showcase controls and local image export. Asset provenance is recorded
  in the runtime manifests and attribution files.

## Preservation-first reset

Admin settings → Workspace data now archives active projects and retains the
signed-in Admin plus a selected Designer. Other accounts lose password, Google,
recovery-email and trusted-device access. Unreferenced identity rows are removed;
anonymous disabled author keys remain where saved history still needs them.

The reset has a five-minute cancellation period and requires a successful local
database backup. All account deletions respect recovery-email foreign-key order.
No project files are moved or deleted. Database changes and completion are one
transaction; interruption rolls back unfinished changes. Fingerprints enforce
preservation of project content, BOM/history, settings and the material/legend
catalogues. No new table or schema migration is introduced.

The authorized local cleanup was completed before repository synchronization.
All 30 floorplan records, 53 original files and 41 protected database tables
passed preservation checks. Only the selected two accounts remain active;
all eight projects were removed from active lists through archiving.

## Repository contents

Publish application code, reproducible tooling, documentation, existing checks,
optimized runtime models and their licences. Keep environment secrets, database
backups, private drawings, model checkpoints, downloaded authoring packs,
supplier-pricing inspection output and verification screenshots local and ignored.
The unused legacy GLB catalogue is not part of the active device implementation.

Local database contents are not deployed or synchronized by a Git push. A fresh
installation still requires its own environment configuration, MySQL schema,
managed accounts, approved catalogue data and separately provisioned model files.

## Verification

- Frontend production build: PASS, with existing large-chunk warnings.
- Full frontend lint: PASS after removing the unused legacy catalogue from source.
- Python compilation of backend application and scripts: PASS.
- Live reset completion, retained accounts and protected-data fingerprints: PASS.
- Previously reproduced 2D wire-selection crash and related BOM topology issues:
  corrected and manually verified in the browser before this publication.
- No new tests written for this synchronization. A full test-suite run is not
  claimed; existing test changes from prior work are preserved.
- Browser verification of the revised reset dialog: NOT TESTED in this session;
  browser-control tools were unavailable. Its API and worker were verified live.

Outputs remain planning/estimation results. Source observations, generated
proposals, estimated dimensions and professional approval remain distinct.
