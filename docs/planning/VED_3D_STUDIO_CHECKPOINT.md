# VED 3D Studio implementation checkpoint

## UX revision — 25 October 2026

- Fixed inspector docking regression: a wrapper had broken the direct-child layout selectors. Inspector is again a direct workspace child and is omitted in Showcase.
- One navigation scheme: left-drag orbit, right-drag look, middle-drag pan, wheel zoom, focused WASD/arrows movement, Q/E vertical movement. Drawing keeps its existing reserved gestures. No Orbit/Free Fly toggle.
- Consolidated toolbar, separate right-hand editing panel, contextual visual card, compact navigation help, improved floor/background contrast and low-intensity Three.js studio reflections.
- Focus selection now uses the resolved device mounting position rather than its floor anchor.
- Added a licensed premade Kenney ceiling housing, adapted in Blender into a representative troffer with inset diffuser (6,264 bytes). Source/license and adaptations are recorded under `frontend/public/studio-devices/premade-v1`; generator is `scripts/prepare_studio_premade.py`. No unrelated furniture is inserted.
- PASS: production build; scoped lint; 118 existing focused viewer checks. No new test files. Existing checks adjusted for the intentional removal of the navigation toggle.
- PASS: real browser plan 9402 inspector placement, left-drag orbit, focused keyboard movement and premade fixture WebGL rendering in the synthetic harness. Screenshot: `outputs/studio-verification/studio-redesign.png`.
- NOT TESTED: direct browser reproduction on plan 9383 from the user's screenshot; the shared docking cause was reproduced and repaired on plan 9402. Full editor suite and new performance benchmark were not rerun for this revision. Earlier limitations below still apply.
- No canonical geometry, prices, database schema or historical estimates changed by this revision. No project save performed during browser checks.

## Implemented

- Shared draft/saved Three.js renderer: warm architectural materials, one shadow key light, geometry framing, quiet platform, hidden grid, Full/Cutaway/X-ray walls.
- Design/Showcase, animated camera presets, visibility controls, selected-device backend pricing, draft-network isolation, local PNG export and adaptive DPR.
- Showcase hides draft editing panels and blocks geometry editing, undo/redo and saving. No implicit draft save.
- Twelve newly authored Blender variants: simplex/duplex outlets and data, 1/2/3-gang switches, single/twin linear lighting, dome/bullet CCTV and panel.
- Existing rejected DeviceMeshCatalog is not imported or activated. Missing models retain procedural devices.
- Optional backend product identity metadata; no price recalculation in the renderer. Client products are not falsely assigned the default VED product identity.

## Asset authoring

Blender 4.5.9 LTS portable was installed with user authorization from the official Blender distribution; archive checksum verified. Executable:
`C:/Users/kupal/AppData/Local/Programs/Blender-4.5.9/blender-4.5.9-windows-x64/blender.exe`.

Run `blender --background --python scripts/author_studio_devices.py` to regenerate. Sources are in `outputs/studio-assets`; exports and versioned manifest are in `frontend/public/studio-devices/v1`.

All models are **representative**, not verified Panasonic/Hikvision product replicas. They use original generated geometry, no third-party meshes/textures. Manifest dimensions are nominal illustrative dimensions; the loader fits the existing device envelope without moving authoritative anchors or terminals. No manufacturer certification or exact dimensions are claimed. Each export is below 250 KB with at most three materials and no textures.

## Verification

| Criterion | Status | Evidence |
|---|---|---|
| Production build | PASS | Vite build, 2214 modules; large-chunk warning remains |
| Focused viewer checks | PASS | 118 existing checks, 23 files; Viewer3DPage suite excluded |
| Backend BOM regression | PASS | 35 existing checks in test_draft_bom.py |
| Scoped lint | PASS | Viewer changes, routing tube, draft page/preview, BOM panel, preferences; rejected unused catalogue excluded |
| Real WebGL | PASS | Plan 9402 rendered in IAB; isometric, Top, X-ray, cutaway, shadows and device selection inspected |
| Backend price inspector | PASS | Selected twin lamp shows client FableVolt product, PHP 750/piece |
| Visual-only cost integrity | PASS | Plan 9402 remains 50.845 m; PHP 16,386.27 partial estimated total; no unsaved geometry |
| Showcase editing guard | PASS | Edit panels hidden, Save/Undo/Redo disabled; same live scene retained |
| Local image export | PASS | Downloads/VED-studio.png, 1905 x 1080, project/planning/estimated footer |
| 1080p performance | PASS | 500 devices/200 routes, 12-second camera orbit: 77.8 animation FPS, renderer sample 80.1 FPS |
| All variants browser close-up / anchor comparison | NOT TESTED | Generated assets validated by export budgets; exhaustive visual comparison still needed |
| Saved-layout end-to-end workflow | NOT TESTED | Uses shared renderer, but full saved-layout browser workflow not repeated |

Benchmark machine: AMD Ryzen 7 7435HS, NVIDIA GeForce RTX 3050 Laptop GPU, Windows, IAB Chrome 155. Canvas CSS and backing size verified at 1920 x 1080. Temporary viewport override restored and benchmark tab closed. Manual development harness: `frontend/studio-benchmark.html`; it does not read/write project data.

## Remaining acceptance gaps

- Focus currently isolates an existing draft network; circuit-first isolation and dimming unrelated devices are not complete.
- Saved-layout outer controls retain legacy controls; price details are explicitly unavailable where no authoritative BOM is supplied.
- Exact product-reference models and exhaustive per-variant visual/terminal comparisons remain outstanding. Current models are honest family representatives.
- Full viewer suite is not green: the earlier broader run reported eight failures in Viewer3DPage.test.jsx around legacy/collapsed controls. Six lint errors also remain in the rejected unused DeviceMeshCatalog.jsx. These are not included in focused PASS claims.

## Integrity and handoff

No new test files, tables or migrations. Existing tests were adjusted for intentional visual changes. No project geometry or historical estimates were saved by verification; originals and stash were not altered. Changes remain uncommitted in the existing dirty worktree. Detection, routing regeneration and measurement changes remain outside this checkpoint.

Screenshot: `outputs/studio-verification/showcase.png`.
