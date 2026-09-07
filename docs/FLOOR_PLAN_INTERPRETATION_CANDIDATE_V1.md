# Floor-Plan Interpretation Candidate Contract v1

## Status and ownership

Ticket U2 freezes the advisory machine-output boundary before model selection.
The Python implementation is
`backend/app/ai/floor_plan_interpretation/candidate.py`; representative
synthetic fixtures are under `fixtures/`.

This contract is not K1 canonical geometry. It contains source-pixel evidence
that remains advisory until later authenticated human review. It creates no
database table, endpoint, model runtime, review decision, or canonical layout.

## Host envelope versus generated payload

`FloorPlanInterpretationCandidate` is the host-owned envelope. The application
supplies and verifies processing/source/page/artifact identity and hashes,
one-based page number and dimensions, model/prompt/runtime provenance,
inference settings, a timezone-aware creation time, and the only initial review
state, `needs_review`.

The model supplies only `FloorPlanInterpretationPayload`. Unknown envelope
fields are rejected, so generated JSON cannot choose host identity, hashes,
model provenance, reviewer identity, or approval state. The host binds the
validated payload to provenance only after its dimensions match exactly.

## Generated payload

Schema version 1 covers page type and quality; a top-left source-pixel plane;
overview, legend, plan-region and tile evidence with reversible transforms;
bounded OCR; scale evidence; walls, rooms, openings, symbols and panels;
optional device bounds/orientation; source-visible route segments and graph
connections; ambiguity; warnings; and explicit extraction outcomes.

`unavailable` means the area could not or did not apply. `empty` means
extraction completed and found no items. `failed` requires a bounded reason.
`partial` preserves incomplete or truncated output. These states must not be
collapsed into an empty list.

## Validation and safety rules

- Input is UTF-8 JSON limited to 256 KiB.
- Duplicate keys, non-JSON constants, unknown/missing fields, booleans used as
  numbers, and string-number coercion are rejected.
- Strings and arrays are bounded; type-prefixed IDs are unique and ordered.
- The source plane is limited to 10,000 pixels per edge and 60 megapixels.
- Geometry must remain inside the plane. Room polygons must have unique
  vertices, non-zero area and no self-intersections.
- Evidence, wall, warning and route-graph references must resolve.
- Unknown or ambiguous symbol mappings carry no catalog class ID.
- Instruction-like OCR remains untrusted evidence text and is never executed.
- Generated confidence is not calibrated probability; every envelope begins
  `needs_review`.

Validation exposes only the stable public message “The floor-plan
interpretation candidate is invalid.”

## Frozen U9 review identity

Later U9 records use `vlm:<candidate_run_id>:<kind>:<local_id>`, where kind is
`scale`, `wall`, `room`, `opening`, `symbol`, `panel`, `segment`, or
`connection`. The `vlm:` namespace cannot collide with existing `detected:`,
`manual:`, or legacy YOLO identities. U2 defines this identity; U9 owns durable
machine-run and append-only review storage.

## Frozen U11 projection boundary

| Candidate evidence | Later canonical destination |
|---|---|
| Approved source plane | Additive extension-v2 source reference |
| Approved walls and room boundaries | New immutable K1-v1 base snapshot |
| Approved openings | Additive extension-v2 openings |
| Approved matched symbols | K1-v1 class/position; optional bounds/orientation in extension v2 |
| Approved panels | Additive extension-v2 panels |
| Approved source-visible segments | K1-v1 route plus extension-v2 `observed` provenance |
| Unknown, ambiguous, rejected, or incomplete records | Candidate/review history only |

Metric conversion requires approved PRE6 scale/elevation. U11 must create the
new K1-v1 snapshot and its one-to-one extension transactionally under ADR 0001.
U2 does not implement that adapter or alter K1 v1.

## Explicit non-goals

This contract contains no Konva nodes, Three.js meshes, generated routing,
electrical sizing, cost data, model download, inference code, persistence, API
operation, or human approval mechanism.
