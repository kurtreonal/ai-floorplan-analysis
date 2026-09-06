# Canonical Geometry Schema v1

K1 defines the renderer-independent geometry document shared by future 2D,
3D, routing, and estimation work. One document describes one project floor in
one floor-plan coordinate plane. Version 1 is implemented by the frozen Python
contracts in `backend/app/geometry/canonical.py` and the dependency-free
JavaScript normalizer in `frontend/src/geometry/canonicalGeometry.js`.

K2 persists complete validated documents in append-only `layout_versions`
snapshots. K3 exposes current-layout retrieval and new snapshot creation at
`/api/projects/{project_id}/floors/{project_floor_id}/layouts`.
K4 consumes the current snapshot in a Konva source-pixel plane with six stable
layers; K5 repositions symbols while retaining the same geometry model.
Callers must supply floor elevation explicitly: `project_floors` has no
elevation column, and an elevation must never be inferred from a floor name or
sort order.

## PRE6 reviewed metric inputs

PRE6 stores Designer-reviewed elevation and page scale separately in append-only
`floor_elevation_settings` and `page_scale_settings` records. The newest record
for a floor/page is its current setting. Each revision records evidence notes,
the authenticated reviewer, and server creation time. Missing records or null
values are unresolved; zero elevation is an explicit valid approval.

Scale is expressed in pixels per meter for the explicitly supplied reference
image width and height. These dimensions describe the image on which the
Designer measured the reference distance. They are not inferred from DPI or PDF
paper size. `require_approved_metric_inputs` requires an approved elevation and
scale and exact reference dimensions before returning K1 adapter inputs.
Resized or cropped images require a matching approval; PRE6 does not silently
rescale measurements or introduce a transform contract.

Software input bounds are -10,000 to 10,000 meters for elevation, 0.000001 to
1,000,000 pixels per meter for scale, and integer dimensions from 1 to 100,000
pixels. These are storage/validation limits, not electrical engineering rules.
The values use at most nine decimal places in database storage. Evidence notes
are required, trimmed, and limited to 1,000 characters. The UI permits marking a
value unresolved by leaving it blank and supplying a reason.

Settings revisions never rewrite existing K1 JSON, K2 history, stored wall
coordinates, or original files. K1 documents remain complete snapshots of the
values used when created. Automatic snapshot creation remains future work.

## Document fields

| Field | Type | Requirement |
|---|---|---|
| `schema_version` | integer | Required; exactly `1` |
| `project_id` | positive safe integer | Required |
| `floor` | object | Required floor identity and datum |
| `floor.project_floor_id` | positive safe integer | Required |
| `floor.name` | string | Required, trimmed, 1–100 characters |
| `floor.sort_order` | safe integer | Required; not an elevation |
| `floor.elevation_meters` | finite number | Required; negative, zero, or positive |
| `floor_plan_id` | positive safe integer | Required source plan |
| `coordinate_system` | object | Required, as specified below |
| `walls` | array | Required, ordered; may be empty |
| `rooms` | array | Required, ordered; may be empty |
| `symbols` | array | Required, ordered; may be empty |
| `routes` | array | Required, ordered; may be empty |

Unknown object properties, missing properties, invalid arrays, Boolean numeric
values, non-finite numbers, and unsupported versions are rejected. Identifiers
must not exceed JavaScript's safe-integer maximum, `9007199254740991`; neither
runtime coerces strings or floating-point values into identifiers.

## Coordinate system and points

The coordinate object contains `unit: "meter"`,
`origin: "image_top_left"`, `x_direction: "right"`, and
`y_direction: "down"`. It also contains positive finite
`pixels_per_meter`, positive integer `image_width_pixels` and
`image_height_pixels` (each at most 4096), and positive finite
`width_meters` and `height_meters`. Metric dimensions must equal pixel
dimensions divided by `pixels_per_meter` within the nine-decimal serialization
tolerance.

A point is `{ "x": number, "y": number }` in meters. Both values are finite,
non-negative, and within the inclusive metric image bounds. Public metric
values follow H2's at-most-nine-decimal convention. Convert canonical points
back to the aligned source image with `pixel_x = x * pixels_per_meter` and
`pixel_y = y * pixels_per_meter`.

## Walls

Each wall has positive `id`; nullable positive `source_candidate_id` and
`processing_job_id`; `status` of `detected` or `verified`; `start` and `end`
points; non-negative `length_meters`; finite `angle_degrees` in `[0, 180)`;
and nullable `thickness_meters` and `height_meters`. Supplied thickness and
height must be positive finite numbers. Unknown values remain `null`—K1 does
not invent architectural defaults.

Length is recomputed from the canonical endpoints and contradictory input is
rejected. The K1 adapter preserves H2 wall order, metric endpoints, angle, and
candidate provenance; raw pixels are not duplicated as competing geometry.

## Rooms

A room contains positive `id`, nullable trimmed `name`, and ordered `boundary`
points. A boundary has at least three points and no adjacent duplicates. The
serializer omits a repeated closing point; consumers close the polygon from
the last point to the first. K1 does not discover rooms or calculate area.

## Symbols

A symbol contains canonical string `id`, `source_type`, positive
`source_record_id`, positive `processing_job_id`, `status`, `class`, and
`position`. Detected records use `id: "detected:<source_record_id>"`,
`source_type: "detected"`, and `status: "confirmed"`. Manual records use
`id: "manual:<source_record_id>"`, `source_type: "manual"`, and
`status: "manually_added"`. `class` contains a non-negative safe-integer `id`
and a trimmed 1–255 character `name`.

The adapter consumes J5 `AuthoritativeSymbolCandidate` values in their existing
order. It validates plan, job, and image dimensions and converts source centers
with `x = center_x_pixels / pixels_per_meter` and the equivalent y formula.
For confirmed detections, J5 already supplies J4's authoritative corrected
class when present. K1 uses that class without altering the original AI class,
confidence, or append-only correction records. Pending and deleted detections
are not valid canonical symbols.

## Routes

A route contains positive `id` and ordered `points`. A populated route has at
least two points. Each point contains positive `project_floor_id`, bounded
canonical `x` and `y`, and finite absolute `elevation_meters`; elevation may be
negative, zero, or positive. K1 defines representation only—it does not select
panels, find paths, calculate length, or define wire/conduit rules.

## Ordering, validation, and errors

Array order is authoritative and serialization is deterministic. Empty geometry
collections are valid. Python returns immutable frozen objects and JavaScript
returns a fresh deeply frozen value. Invalid Python documents raise
`CanonicalGeometryError`; invalid JavaScript documents raise `TypeError`. Both
expose only the stable message `The canonical geometry document is invalid.`
and perform no database, filesystem, or HTTP side effects.

## K2 snapshot persistence

Each snapshot references its project, project floor, and source floor plan,
stores schema version `1`, the complete canonical JSON document, a positive
per-floor sequential version, a nullable current marker, and a server-created
timestamp. Saving locks the project-floor row, validates all three identities,
sets the former current marker to `NULL`, and inserts the new snapshot as
`TRUE` in one transaction. A unique floor/version constraint and a unique
floor/current constraint enforce version and current-marker integrity. Older
documents are never updated or deleted when a new snapshot is saved or an older
version is selected as current.

Reads reconstruct the immutable K1 contract and reject corrupt or
identity-inconsistent stored JSON with a sanitized service error. History reads
return ordered metadata without rewriting geometry. K2 does not write any
floor-plan or derived-image file.

## K3 layout API

`GET` returns the current snapshot metadata and complete canonical geometry to
the owning Designer or an Admin. `POST` is owning-Designer-only and accepts one
complete strict K1 document; it validates path and persisted-floor identity and
delegates append-only version creation to K2. The API does not expose history or
current-version selection and does not write original or derived floor-plan
files.

## K4 read-only Konva mapping

K4 maps canonical meters back to the aligned source plane using
`pixel_x = x * pixels_per_meter` and `pixel_y = y * pixels_per_meter`.
Responsive fitting changes only the Konva stage scale. Blueprint, walls, rooms,
symbols, wiring/conduit route previews, and selection/editing UI remain six
separate always-mounted layers. The last layer is empty in K4 and contains no
persisted geometry. Visibility controls set layer presentation only; the frozen
canonical arrays, ordering, and values remain unchanged.

K4 may request the existing J1A review image only when all non-null wall and
symbol `processing_job_id` values resolve to exactly one positive safe ID. Its
decoded dimensions must exactly equal `image_width_pixels` and
`image_height_pixels`. Otherwise a neutral blueprint layer remains mounted and
the UI reports that the reference is unavailable. Source-less or mixed-source
snapshots require a later explicit blueprint-source contract for guaranteed
aligned-image display.

## K5 canonical symbol movement

K5 makes confirmed detected and manually added symbols selectable. An owning
Designer may drag a symbol in the Konva source plane or enter bounded X/Y meter
coordinates in an accessible inspector. Source pixels are converted back with
`x = pixel_x / pixels_per_meter` and `y = pixel_y / pixels_per_meter`, then the
complete document is normalized. The authoritative value remains
`geometry.symbols[*].position` in meters; Konva always derives its displayed
node from that field, and future 3D must consume the same field.

K5 preserves symbol IDs, class, status, source and processing provenance,
ordering, and all unrelated floor, coordinate, wall, room, symbol, and route
data. Walls, rooms, routes, scale, floor identity, elevation, classification,
review state, deletion, resizing, and rotation remain non-editable. Each
successful save posts the complete K1 document through K3 and creates a new
append-only K2 version. Cancel restores the last server snapshot without a
POST.

PRE8 wraps K3 saves in an expected-version and client UUIDv4 contract. The
service locks the floor, rejects stale writes, and records successful request
identities so identical retries return the original snapshot. K5 preserves the
same request identity across its uncertain-result check and retry.

## Accepted local-VLM adapter boundary

PRE11 freezes the compatibility policy in
`decisions/0001-canonical-geometry-compatibility.md`. This version-1 contract
and existing K2 snapshots remain native and readable without rewrite.
Candidate/review records own source document, page, region, raw evidence, and
human-decision provenance. An additive canonical extension version 2 is
reserved, but not implemented,
for approved source-plane references, first-class openings and panels, optional
symbol orientation/bounds, and observed/generated route provenance. U2 must
define compatible candidate data; U11 owns any extension dispatcher, exact
version-2 extension validators, additive persistence, adapter, and new
append-only version-1 base snapshots.

The local multimodal migration does not change K1 into a model-output schema.
The VLM will produce a separate, source-pixel
`FloorPlanInterpretationCandidate` with page/model/prompt/adapter provenance,
scale evidence, OCR, walls, rooms, symbols, panels, observed routes,
ambiguities, and warnings. That document must pass strict application
validation and VED review before a deterministic adapter can create K1 values.

The adapter may convert coordinates to meters only from explicitly approved
scale evidence. It must preserve the original candidate and human-decision
history instead of overwriting machine output. Only approved candidates enter
K2 snapshots. Raw VLM text, tile-local coordinates, token probabilities,
Konva nodes, and Three.js meshes are never canonical geometry.

Routes visibly traced from the uploaded drawing are `observed` evidence. Future
A* routes are `generated` geometry with separate algorithm/rule provenance. A
page with no visible wiring contributes no observed route; the VLM must not
design or infer one merely to populate `routes`. U2/U11 must implement the
accepted PRE11 ownership and versioning policy without changing K1 v1 in place.

## Downstream mapping and non-goals

L1 provides only a protected empty Three.js/React Three Fiber scene. It does not
request K1/K2/K3 layout data or render any canonical floor, wall, opening,
symbol, or route. Its grid and axes are orientation helpers rather than project
geometry.

Future L2+ adapters are expected to map canonical x to horizontal 3D x, explicit
floor elevation to vertical 3D y, and canonical y to horizontal 3D z. This is a
planned mapping, not an implemented canonical renderer or proof of 2D/3D
synchronization. Top/perspective switching also remains future viewer work.

K5 implements canonical symbol selection, repositioning, and explicit snapshot
saving. It does not implement wall/room/route editing, symbol class/status
changes, deletion, resizing, undo/redo, canonical Three.js rendering, routing algorithms,
quantities, estimates, or reports. The explicit floor elevation still lives in
the snapshot because `project_floors` has no elevation column.
