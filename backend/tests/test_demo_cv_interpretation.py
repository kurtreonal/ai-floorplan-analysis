import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.ai.floor_plan_interpretation import (
    DemoCVError,
    DemoCVParameters,
    interpret_floor_plan_demo,
)


def synthetic_plan(width=400, height=300):
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (50, 40), (350, 260), (0, 0, 0), 5)
    cv2.line(image, (200, 40), (200, 260), (0, 0, 0), 5)
    cv2.circle(image, (110, 150), 12, (0, 0, 0), 3)
    cv2.circle(image, (280, 150), 12, (0, 0, 0), 3)
    return image


class DemoCVInterpretationTests(unittest.TestCase):
    def test_faint_walls_survive_uneven_scan_illumination(self):
        background = np.tile(np.linspace(150, 255, 600), (500, 1))
        wall_mask = np.zeros((500, 600), dtype=np.uint8)
        cv2.rectangle(wall_mask, (40, 40), (560, 460), 255, 7)
        cv2.line(wall_mask, (300, 40), (300, 460), 255, 7)
        gray = np.clip(background - (wall_mask > 0) * 45, 0, 255).astype(np.uint8)
        image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        before = image.copy()

        result = interpret_floor_plan_demo(image)

        self.assertEqual(len(result.rooms.items), 2)
        self.assertGreaterEqual(len(result.walls.items), 5)
        self.assertTrue(all(wall.ambiguity == 'ambiguous' for wall in result.walls.items))
        np.testing.assert_array_equal(image, before)

    def test_ceiling_grid_does_not_partition_room_proposals(self):
        image = synthetic_plan(400, 300)
        for x in range(70, 190, 20):
            cv2.line(image, (x, 50), (x, 250), (0, 0, 0), 1)
        for y in range(60, 250, 20):
            cv2.line(image, (60, y), (190, y), (0, 0, 0), 1)
        result = interpret_floor_plan_demo(image)
        self.assertEqual(len(result.rooms.items), 2)

    def test_room_proposals_ignore_short_wiring_dashes_and_keep_lower_page(self):
        image = synthetic_plan()
        for x in range(60, 330, 18):
            cv2.line(image, (x, 125), (x + 8, 125), (0, 0, 0), 1)
        result = interpret_floor_plan_demo(image)
        self.assertEqual(len(result.rooms.items), 2)
        self.assertGreater(max(p.y for room in result.rooms.items for p in room.boundary), 250)

    def test_room_gap_bridging_is_advisory_and_does_not_create_wiring(self):
        image = synthetic_plan()
        cv2.line(image, (200, 125), (200, 140), (255, 255, 255), 9)
        result = interpret_floor_plan_demo(image)
        self.assertGreaterEqual(len(result.rooms.items), 2)
        self.assertTrue(all(room.ambiguity == 'ambiguous' for room in result.rooms.items))
        self.assertEqual(result.observed_routes.state, 'unavailable')

    def test_real_pixels_produce_strict_review_only_candidates(self):
        result = interpret_floor_plan_demo(synthetic_plan())

        self.assertEqual(result.schema_version, 1)
        self.assertEqual(result.source_plane.width_pixels, 400)
        self.assertEqual(result.source_plane.height_pixels, 300)
        self.assertEqual(result.page.quality, "unknown")
        self.assertGreaterEqual(len(result.rooms.items), 2)
        self.assertGreaterEqual(len(result.symbols.items), 2)
        self.assertGreater(len(result.walls.items), 0)
        self.assertTrue(all(item.mapping_state == "unknown" for item in result.symbols.items))
        self.assertTrue(all(item.catalog_class_id is None for item in result.symbols.items))
        self.assertEqual(result.observed_routes.state, "unavailable")
        self.assertLess(len(result.model_dump_json().encode("utf-8")), 256 * 1024)

    def test_empty_page_is_honestly_empty_or_unknown(self):
        result = interpret_floor_plan_demo(
            np.full((240, 320, 3), 255, dtype=np.uint8)
        )

        self.assertEqual(result.rooms.state, "empty")
        self.assertEqual(result.symbols.state, "empty")
        self.assertEqual(result.walls.state, "empty")
        self.assertEqual(result.page.page_type, "unknown")

    def test_output_is_deterministic_and_input_is_unchanged(self):
        image = synthetic_plan()
        before = image.tobytes()

        first = interpret_floor_plan_demo(image).model_dump_json()
        second = interpret_floor_plan_demo(image).model_dump_json()

        self.assertEqual(first, second)
        self.assertEqual(image.tobytes(), before)

    def test_rotated_and_scaled_pixels_are_processed_without_canned_coordinates(self):
        original = synthetic_plan()
        matrix = cv2.getRotationMatrix2D((200, 150), 8, 1.0)
        rotated = cv2.warpAffine(
            original,
            matrix,
            (400, 300),
            borderValue=(255, 255, 255),
        )
        scaled = cv2.resize(original, (600, 450), interpolation=cv2.INTER_AREA)

        rotated_result = interpret_floor_plan_demo(rotated)
        scaled_result = interpret_floor_plan_demo(scaled)

        self.assertGreater(len(rotated_result.walls.items), 0)
        self.assertGreater(len(rotated_result.symbols.items), 0)
        self.assertGreater(len(scaled_result.rooms.items), 0)
        self.assertGreater(len(scaled_result.symbols.items), 0)
        self.assertNotEqual(
            scaled_result.regions[0].bounds.width,
            interpret_floor_plan_demo(original).regions[0].bounds.width,
        )

    def test_limits_are_explicit_and_report_partial_results(self):
        result = interpret_floor_plan_demo(
            synthetic_plan(),
            parameters=DemoCVParameters(
                maximum_walls=1,
                maximum_rooms=1,
                maximum_symbols=1,
            ),
        )

        self.assertEqual(result.document_state, "partial")
        self.assertTrue(
            result.walls.truncated
            or result.rooms.truncated
            or result.symbols.truncated
        )
        self.assertLessEqual(len(result.walls.items), 1)
        self.assertLessEqual(len(result.rooms.items), 1)
        self.assertLessEqual(len(result.symbols.items), 1)

    def test_invalid_inputs_and_configuration_fail_with_sanitized_errors(self):
        invalid = (
            None,
            np.zeros((0, 10, 3), dtype=np.uint8),
            np.zeros((10, 10), dtype=np.uint8),
            np.zeros((10, 10, 3), dtype=np.float32),
            np.zeros((10, 4097, 3), dtype=np.uint8),
        )
        for value in invalid:
            with self.subTest(shape=getattr(value, "shape", None)):
                with self.assertRaises(DemoCVError) as caught:
                    interpret_floor_plan_demo(value)
                self.assertNotIn("4097", str(caught.exception))
        with self.assertRaises(DemoCVError):
            DemoCVParameters(maximum_symbols=0)

    def test_opencv_failures_do_not_expose_pixel_or_path_details(self):
        with patch(
            "app.ai.floor_plan_interpretation.demo_cv.cv2.cvtColor",
            side_effect=RuntimeError("C:/private/source.png"),
        ):
            with self.assertRaises(DemoCVError) as caught:
                interpret_floor_plan_demo(synthetic_plan())
        self.assertEqual(caught.exception.code, "INFERENCE_FAILED")
        self.assertNotIn("private", str(caught.exception))

    def test_detector_has_no_filesystem_http_database_or_job_dependency(self):
        import app.ai.floor_plan_interpretation.demo_cv as module

        self.assertNotIn("Path", module.__dict__)
        self.assertNotIn("Session", module.__dict__)
        self.assertNotIn("FastAPI", module.__dict__)
        self.assertNotIn("requests", module.__dict__)


if __name__ == "__main__":
    unittest.main()
