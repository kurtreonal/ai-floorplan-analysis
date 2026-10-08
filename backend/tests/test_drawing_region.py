import unittest
from unittest.mock import patch

import cv2
import numpy as np
from pydantic import ValidationError

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload, SourcePlane
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from app.ai.floor_plan_interpretation import demo_cv
from app.ai.floor_plan_interpretation.drawing_region import (
    DrawingRegion, interpret_drawing_region, restore_region_payload, restore_region_predictions,
)


class DrawingRegionTests(unittest.TestCase):
    def test_selected_scope_does_not_run_automatic_border_mask(self):
        with patch.object(demo_cv, '_plan_bounds', wraps=demo_cv._plan_bounds) as bounds:
            automatic = interpret_floor_plan_demo(self.crop)
            self.assertEqual(bounds.call_count, 1)
            selected = interpret_floor_plan_demo(self.crop, selected_drawing=True)
            self.assertEqual(bounds.call_count, 1)
        self.assertNotEqual(automatic.regions[0].bounds.model_dump(),
                            selected.regions[0].bounds.model_dump())
        self.assertEqual(selected.regions[0].bounds.model_dump(),
                         {'x':0,'y':0,'width':400,'height':300})

    def test_selected_scope_flag_rejects_non_boolean_values(self):
        for flag in (None, 1, 'true', np.bool_(True)):
            with self.subTest(flag=flag), self.assertRaises(demo_cv.DemoCVError) as caught:
                interpret_floor_plan_demo(self.crop, selected_drawing=flag)
            self.assertEqual(caught.exception.code, 'INVALID_CONFIGURATION')

    def test_explicit_region_keeps_perimeter_ink_at_all_four_crop_edges(self):
        source = np.full((500, 600, 3), 255, dtype=np.uint8)
        region = DrawingRegion(x=150, y=120, width=200, height=200)
        cv2.rectangle(source, (151,121), (348,318), (0,0,0), 2)
        before = source.copy()
        result = interpret_drawing_region(source, region=region)
        self.assertEqual(result.regions[0].bounds.model_dump(), region.model_dump())
        for x in (151,348):
            self.assertTrue(any(abs(w.start.x-x)<3 and abs(w.end.x-x)<3
                                and abs(w.end.y-w.start.y)>180 for w in result.walls.items))
        for y in (121,318):
            self.assertTrue(any(abs(w.start.y-y)<3 and abs(w.end.y-y)<3
                                and abs(w.end.x-w.start.x)>180 for w in result.walls.items))
        self.assertEqual(result.document_state, 'partial')
        np.testing.assert_array_equal(source,before)

    def setUp(self):
        self.crop = np.full((300, 400, 3), 255, dtype=np.uint8)
        cv2.rectangle(self.crop, (40, 40), (360, 260), (0, 0, 0), 5)
        cv2.line(self.crop, (200, 40), (200, 260), (0, 0, 0), 5)
        cv2.circle(self.crop, (110, 150), 12, (0, 0, 0), 3)
        self.region = DrawingRegion(x=90, y=160, width=400, height=300)
        self.plane = SourcePlane(width_pixels=800, height_pixels=700)

    def test_same_resolution_source_recovery_and_original_preservation(self):
        source = np.full((700, 800, 3), 255, dtype=np.uint8)
        source[160:460, 90:490] = self.crop
        # Unrelated notes outside selection cannot become region proposals.
        cv2.line(source, (40, 30), (740, 30), (0, 0, 0), 8)
        before = source.copy()
        local = interpret_floor_plan_demo(self.crop)
        result = interpret_drawing_region(source, region=self.region)
        self.assertEqual(result.source_plane, self.plane)
        self.assertEqual(result.document_state, "partial")
        self.assertEqual(len(result.walls.items), len(local.walls.items))
        self.assertGreater(len(result.walls.items), 0)
        for actual, expected in zip(result.walls.items, local.walls.items):
            self.assertEqual(actual.start.x, expected.start.x + 90)
            self.assertEqual(actual.start.y, expected.start.y + 160)
            self.assertEqual(actual.evidence_refs, expected.evidence_refs)
        for item in result.regions:
            self.assertEqual(item.local_to_source.e, 90)
            self.assertEqual(item.local_to_source.f, 160)
        self.assertIn("explicit_drawing_region", [item.code for item in result.warnings])
        np.testing.assert_array_equal(source, before)

    def test_every_spatial_collection_and_graph_survives_translation(self):
        data = interpret_floor_plan_demo(self.crop).model_dump(mode="json")
        evidence = {"evidence_refs": ["region:region-0001"], "ambiguity": "ambiguous"}
        data["ocr"] = {"state": "completed", "items": [{"id": "ocr-0001", "region_id": "region-0001",
            "bounds": {"x": 10, "y": 20, "width": 30, "height": 10}, "text": "S", "normalized_text": "S"}]}
        data["openings"] = {"state": "completed", "items": [{**evidence, "id": "opening-0001",
            "opening_type": "door", "start": {"x": 40, "y": 70}, "end": {"x": 40, "y": 90}, "wall_ref": None}]}
        data["panels"] = {"state": "completed", "items": [{**evidence, "id": "panel-0001", "label": "DB",
            "center": {"x": 50, "y": 100}, "bounds": None, "orientation_degrees": None}]}
        data["observed_routes"] = {"state": "completed", "segments": [{**evidence, "id": "segment-0001",
            "points": [{"x": 50, "y": 100}, {"x": 100, "y": 100}]}], "connections": [
            {"id": "connection-0001", "from_ref": "panel:panel-0001", "to_ref": "segment:segment-0001"}]}
        local = FloorPlanInterpretationPayload.model_validate(data)
        original = local.model_dump_json()
        result = restore_region_payload(local, region=self.region, source_plane=self.plane)
        self.assertEqual(result.ocr.items[0].bounds.x, 100)
        self.assertEqual(result.openings.items[0].start.y, 230)
        self.assertEqual(result.panels.items[0].center.y, 260)
        self.assertIsNone(result.panels.items[0].bounds)
        self.assertEqual(result.observed_routes.segments[0].points[1].x, 190)
        self.assertEqual(result.observed_routes.connections, local.observed_routes.connections)
        for actual, expected in zip(result.rooms.items, local.rooms.items):
            self.assertEqual(actual.boundary[0].x, expected.boundary[0].x + 90)
        for actual, expected in zip(result.symbols.items, local.symbols.items):
            self.assertEqual(actual.bounds.y, expected.bounds.y + 160)
            self.assertEqual(actual.mapping_state, "unknown")
        self.assertEqual(local.model_dump_json(), original)

    def test_invalid_or_mismatched_regions_fail_without_clipping(self):
        for values in ({"x": True}, {"x": 1.5}, {"x": -1}, {"width": 0}, {"height": "300"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                DrawingRegion.model_validate({**self.region.model_dump(), **values})
        with self.assertRaises(ValueError):
            interpret_drawing_region(self.crop, region=self.region)
        with self.assertRaises(ValueError):
            restore_region_payload(interpret_floor_plan_demo(self.crop),
                region=DrawingRegion(x=0, y=0, width=399, height=300), source_plane=self.plane)

    def test_mutating_interpreter_cannot_change_original(self):
        before = self.crop.copy()
        def mutate(image):
            image[:] = 255
            return interpret_floor_plan_demo(image)
        result = interpret_drawing_region(self.crop,
            region=DrawingRegion(x=0, y=0, width=400, height=300), interpreter=mutate)
        self.assertEqual(result.walls.state, "empty")
        self.assertEqual(result.document_state, "partial")
        np.testing.assert_array_equal(self.crop, before)

    def test_raw_alias_and_localization_evidence_recovered_before_proposal_attachment(self):
        observation = {"class_id": 1, "score": .6, "bbox": [10, 20, 30, 40], "tile_origin": [0, 0]}
        row = {**observation, "localization_observations": [observation],
               "equivalent_observations": [{**observation, "class_id": 2}]}
        restored = restore_region_predictions([row], region=self.region, source_plane=self.plane)[0]
        self.assertEqual(restored["bbox"], [100, 180, 120, 200])
        self.assertEqual(restored["tile_origin"], [90, 160])
        self.assertEqual(restored["equivalent_observations"][0]["bbox"], restored["bbox"])
        self.assertEqual(restored["localization_observations"][0]["tile_origin"], [90, 160])
        self.assertEqual(row["bbox"], [10, 20, 30, 40])
        self.assertEqual(restored["equivalent_observations"][0]["class_id"], 2)
        for box in ([0, 0, 401, 20], [0, 0, float("nan"), 20], [0, 0, 0, 20]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                restore_region_predictions([{**observation, "bbox": box}], region=self.region, source_plane=self.plane)

    def test_already_attached_opaque_raw_coordinate_evidence_is_rejected(self):
        data = interpret_floor_plan_demo(self.crop).model_dump(mode="json")
        data["warnings"].append({"code": "experimental_detector_score", "severity": "info", "message": "Raw tile origin (0, 0) source pixels."})
        with self.assertRaises(ValueError):
            restore_region_payload(FloorPlanInterpretationPayload.model_validate(data), region=self.region, source_plane=self.plane)

    def test_source_contract_and_selected_inference_budgets_are_separate(self):
        source = np.full((300, 6000, 3), 255, dtype=np.uint8)
        result = interpret_drawing_region(source, region=DrawingRegion(x=5500, y=0, width=400, height=300))
        self.assertEqual(result.source_plane.width_pixels, 6000)
        with self.assertRaises(ValueError):
            interpret_drawing_region(np.zeros((1, 10001, 3), dtype=np.uint8),
                                     region=DrawingRegion(x=0, y=0, width=1, height=1))
        with self.assertRaises(RuntimeError):
            interpret_drawing_region(source, region=DrawingRegion(x=0, y=0, width=5000, height=300))

    def test_scope_warning_budget_failure_never_silently_discards_evidence(self):
        data = interpret_floor_plan_demo(self.crop).model_dump(mode="json")
        data["warnings"] = [{"code": "retained_evidence", "severity": "info", "message": str(index)} for index in range(256)]
        payload = FloorPlanInterpretationPayload.model_validate(data)
        with self.assertRaisesRegex(ValueError, "warning budget"):
            restore_region_payload(payload, region=self.region, source_plane=self.plane)
        self.assertEqual(len(payload.warnings), 256)

    def test_unbounded_or_nested_raw_detector_evidence_is_rejected(self):
        row = {"class_id": 1, "score": .6, "bbox": [10, 20, 30, 40], "tile_origin": [0, 0]}
        for rows in (iter([row]), [row]*201,
                     [{**row, "localization_observations": [row]*3}],
                     [{**row, "equivalent_observations": [{**row, "equivalent_observations": [row]}]}]):
            with self.assertRaises(ValueError):
                restore_region_predictions(rows, region=self.region, source_plane=self.plane)


if __name__ == "__main__":
    unittest.main()
