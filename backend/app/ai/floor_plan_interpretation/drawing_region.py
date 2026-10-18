"""Explicit drawing scope, without replacing source identity or approving results.

A sheet can contain multiple views of one floor, legends and schedules. Callers
must select a region explicitly; this module neither guesses nor persists that
selection. Live job integration needs a durable, hash-bound selection first.
"""
from copy import deepcopy
from math import isfinite
from typing import Annotated

import numpy as np
from pydantic import Field, StrictInt

from app.ai.floor_plan_interpretation.candidate import (
    FloorPlanInterpretationPayload, SourcePlane, StrictCandidateModel,
)
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo, _validate_image

MAXIMUM_DETECTOR_ROWS = 200
MAXIMUM_RETAINED_OBSERVATIONS = 200


class DrawingRegion(StrictCandidateModel):
    x: Annotated[StrictInt, Field(ge=0)]
    y: Annotated[StrictInt, Field(ge=0)]
    width: Annotated[StrictInt, Field(gt=0)]
    height: Annotated[StrictInt, Field(gt=0)]

    def validate_plane(self, plane: SourcePlane) -> None:
        if self.x + self.width > plane.width_pixels or self.y + self.height > plane.height_pixels:
            raise ValueError("Drawing selection lies outside the source plane.")


def restore_region_payload(payload, *, region: DrawingRegion, source_plane: SourcePlane):
    """Translate every spatial collection; retain IDs, raw classes and evidence.

    No rescaling, clipping, approval or merging of separate floor views. The
    strict candidate validator runs again after the coordinate transformation.
    """
    region.validate_plane(source_plane)
    if (payload.source_plane.width_pixels, payload.source_plane.height_pixels) != (region.width, region.height):
        raise ValueError("Local payload does not match the selected raster.")
    if any(item.code == "experimental_detector_score" for item in payload.warnings):
        # These opaque messages embed raw boxes and claim source coordinates.
        # Recover detector observations first, then attach proposals to the
        # restored page payload. Never rewrite evidence by parsing prose.
        raise ValueError("Recover raw detector coordinates before attaching proposals.")
    if len(payload.warnings) >= 256:
        raise ValueError("No candidate warning budget remains for drawing-selection provenance.")
    result = payload.model_dump(mode="json")

    def point(value):
        return {"x": value["x"] + region.x, "y": value["y"] + region.y}

    def bounds(value):
        return None if value is None else {**value, **point(value)}

    for item in result["regions"]:
        item["bounds"] = bounds(item["bounds"])
        transform = item["local_to_source"]
        transform["e"] += region.x
        transform["f"] += region.y
    for item in result["ocr"]["items"]:
        item["bounds"] = bounds(item["bounds"])
    for name in ("walls", "openings"):
        for item in result[name]["items"]:
            item["start"], item["end"] = point(item["start"]), point(item["end"])
    for item in result["rooms"]["items"]:
        item["boundary"] = [point(value) for value in item["boundary"]]
    for name in ("symbols", "panels"):
        for item in result[name]["items"]:
            item["center"], item["bounds"] = point(item["center"]), bounds(item["bounds"])
    for item in result["observed_routes"]["segments"]:
        item["points"] = [point(value) for value in item["points"]]
    for item in result["observed_routes"]["connections"]:
        for key in ("path_anchor", "device_anchor"):
            if item.get(key) is not None:
                item[key] = point(item[key])
    result["source_plane"] = source_plane.model_dump(mode="json")
    # The rest of the sheet was not processed, not verified empty background.
    if result["document_state"] != "failed":
        result["document_state"] = "partial"
    result["warnings"].append({
        "code": "explicit_drawing_region", "severity": "warning", "entity_refs": [],
        "message": f"Only source rectangle ({region.x}, {region.y}, {region.width}, {region.height}) "
                   "was processed. Outside areas are unprocessed; all proposals still require review.",
    })
    return FloorPlanInterpretationPayload.model_validate(result)


def restore_region_predictions(predictions, *, region: DrawingRegion, source_plane: SourcePlane):
    """Recover fused and original observation boxes BEFORE attaching proposals."""
    region.validate_plane(source_plane)
    if type(predictions) not in (list, tuple) or len(predictions) > MAXIMUM_DETECTOR_ROWS:
        raise ValueError("Detector predictions exceed the bounded collection contract.")

    def restore(row, *, observation=False):
        allowed = {"class_id", "bbox", "score", "tile_origin", "clipped_tile_edges",
                   "tile_size", "inference_rotation_ccw"}
        if not observation:
            allowed |= {"localization_observations", "equivalent_observations", "orientation_assessment"}
        if type(row) is not dict or not set(row) <= allowed:
            raise ValueError("Unsupported or recursive detector observation.")
        box = row.get("bbox")
        if (type(box) not in (list, tuple) or len(box) != 4
                or not all(type(value) in (int, float) and isfinite(value) for value in box)
                or not 0 <= box[0] < box[2] <= region.width
                or not 0 <= box[1] < box[3] <= region.height):
            raise ValueError("Detector box lies outside its selected raster.")
        if type(row.get("class_id")) is not int or row["class_id"] < 0:
            raise ValueError("Invalid raw detector class identity.")
        if type(row.get("score")) not in (int, float) or not isfinite(row["score"]) or not 0 <= row["score"] <= 1:
            raise ValueError("Invalid raw detector score.")
        if 'tile_size' in row and (type(row['tile_size']) is not int or not 224 <= row['tile_size'] <= 512):
            raise ValueError('Invalid detector tile size.')
        if 'inference_rotation_ccw' in row and (type(row['inference_rotation_ccw']) is not int
                or row['inference_rotation_ccw'] not in (90, 180, 270)):
            raise ValueError('Invalid detector rotation.')
        if 'orientation_assessment' in row:
            assessment = row['orientation_assessment']
            if (type(assessment) is not dict or set(assessment) != {
                    'selected_turn', 'agreement_ranks', 'agreed_counts', 'orientation_resolved',
                    'retained_counts', 'truncated_views'}
                    or type(assessment['selected_turn']) is not int or not 0 <= assessment['selected_turn'] <= 3
                    or type(assessment['orientation_resolved']) is not bool):
                raise ValueError('Invalid bounded orientation assessment.')
            for key in ('agreement_ranks', 'agreed_counts', 'retained_counts', 'truncated_views'):
                values = assessment[key]
                if type(values) not in (list, tuple) or len(values) != 4:
                    raise ValueError('Invalid orientation view count.')
                for value in values:
                    valid = (type(value) is bool if key == 'truncated_views' else
                             type(value) in (int, float) and isfinite(value) and 0 <= value <= MAXIMUM_DETECTOR_ROWS
                             if key == 'agreement_ranks' else
                             type(value) is int and 0 <= value <= MAXIMUM_DETECTOR_ROWS)
                    if not valid:
                        raise ValueError('Invalid orientation observation value.')
        if "tile_origin" in row:
            origin = row["tile_origin"]
            if (type(origin) not in (list, tuple) or len(origin) != 2
                    or not all(type(value) in (int, float) and isfinite(value) for value in origin)
                    or not 0 <= origin[0] < region.width or not 0 <= origin[1] < region.height):
                raise ValueError("Detector tile origin lies outside its selected raster.")
        if "clipped_tile_edges" in row and (type(row["clipped_tile_edges"]) not in (list, tuple)
                or len(row["clipped_tile_edges"]) > 4
                or any(value not in ("left", "right", "top", "bottom") for value in row["clipped_tile_edges"])):
            raise ValueError("Invalid clipped detector edges.")
        retained = {}
        for key in ("localization_observations", "equivalent_observations"):
            if key in row:
                maximum = 2 if key == "localization_observations" else MAXIMUM_RETAINED_OBSERVATIONS
                if type(row[key]) not in (list, tuple) or len(row[key]) > maximum:
                    raise ValueError("Raw detector observations exceed the bounded collection contract.")
                retained[key] = [restore(value, observation=True) for value in row[key]]
        # Copy only after shape, depth and sizes are bounded.
        result = deepcopy({key: value for key, value in row.items() if key not in retained})
        result.update(retained)
        result["bbox"] = [box[0] + region.x, box[1] + region.y, box[2] + region.x, box[3] + region.y]
        if "tile_origin" in row:
            result["tile_origin"] = [origin[0] + region.x, origin[1] + region.y]
        return result

    return tuple(restore(row) for row in predictions)


def interpret_drawing_region(source_rgb, *, region: DrawingRegion, interpreter=None):
    """Run an existing interpreter on a copied selection at unchanged resolution."""
    if (not isinstance(source_rgb, np.ndarray) or source_rgb.dtype != np.uint8
            or source_rgb.ndim != 3 or source_rgb.shape[2] != 3):
        raise ValueError("Selected source must be a uint8 RGB raster.")
    source = source_rgb
    height, width = source.shape[:2]
    plane = SourcePlane(width_pixels=width, height_pixels=height)
    region.validate_plane(plane)
    view = _validate_image(source[region.y:region.y + region.height, region.x:region.x + region.width])
    crop = np.array(view, copy=True)
    selected = interpreter or interpret_floor_plan_demo
    payload = (selected(crop, selected_drawing=True) if selected is interpret_floor_plan_demo
               else selected(crop))
    return restore_region_payload(payload, region=region, source_plane=plane)
