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

K3 exposes no expected-version, ETag, conditional-write, or idempotency-key
contract. K5 checks the current layout before retrying an uncertain save, but
this does not provide atomic optimistic concurrency or idempotent POST semantics.

## Downstream mapping and non-goals

Future 3D adapters are expected to map canonical x to horizontal 3D x, explicit
floor elevation to vertical 3D y, and canonical y to horizontal 3D z. This is a
planned mapping, not an implemented renderer or proof of 2D/3D synchronization.

K5 implements canonical symbol selection, repositioning, and explicit snapshot
saving. It does not implement wall/room/route editing, symbol class/status
changes, deletion, resizing, undo/redo, Three.js rendering, routing algorithms,
quantities, estimates, or reports. The explicit floor elevation still lives in
the snapshot because `project_floors` has no elevation column.
