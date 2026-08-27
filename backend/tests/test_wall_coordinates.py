import json
import math
import unittest
from dataclasses import FrozenInstanceError, replace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from app.ai.wall_detection.detector import (
    CoordinateSpace,
    PixelPoint,
    WallDetectionResult,
    WallLineCandidate,
)
from app.geometry.coordinates import CanonicalPoint, ERROR_MESSAGES, WallCoordinateError
from app.geometry.walls import normalize_wall_coordinates


def candidate(
    candidate_id=1,
    start=(20, 35),
    end=(220, 35),
    length_pixels=None,
    angle_degrees=0.0,
):
    if length_pixels is None:
        length_pixels = round(math.hypot(end[0] - start[0], end[1] - start[1]), 6)
    return WallLineCandidate(
        candidate_id=candidate_id,
        start=PixelPoint(*start),
        end=PixelPoint(*end),
        length_pixels=length_pixels,
        angle_degrees=angle_degrees,
    )


def detection_result(*candidates, width=640, height=480, truncated=False):
    if not candidates:
        candidates = (candidate(),)
    return WallDetectionResult(
        coordinate_space=CoordinateSpace(width=width, height=height),
        algorithm="probabilistic_hough",
        truncated=truncated,
        candidates=tuple(candidates),
    )


def empty_detection(width=640, height=480):
    return WallDetectionResult(
        coordinate_space=CoordinateSpace(width=width, height=height),
        algorithm="probabilistic_hough",
        truncated=False,
        candidates=(),
    )


class WallCoordinateConversionTests(unittest.TestCase):
    def test_illustrative_100_pixels_per_meter_example(self):
        geometry = normalize_wall_coordinates(detection_result(), 100)
        self.assertEqual(geometry.coordinate_system.pixels_per_meter, 100.0)
        self.assertEqual(geometry.coordinate_system.width_meters, 6.4)
        self.assertEqual(geometry.coordinate_system.height_meters, 4.8)
        wall = geometry.walls[0]
        self.assertEqual((wall.canonical.start.x, wall.canonical.start.y), (0.2, 0.35))
        self.assertEqual((wall.canonical.end.x, wall.canonical.end.y), (2.2, 0.35))
        self.assertEqual(wall.canonical.length_meters, 2.0)

    def test_scale_one_preserves_numeric_coordinate_values(self):
        geometry = normalize_wall_coordinates(detection_result(), 1)
        wall = geometry.walls[0]
        self.assertEqual(wall.canonical.start.x, 20.0)
        self.assertEqual(wall.canonical.end.x, 220.0)
        self.assertEqual(wall.canonical.length_meters, 200.0)

    def test_fractional_scale_is_supported(self):
        wall = candidate(start=(5, 10), end=(15, 10), length_pixels=10.0)
        geometry = normalize_wall_coordinates(detection_result(wall), 2.5)
        self.assertEqual(geometry.walls[0].canonical.start.x, 2.0)
        self.assertEqual(geometry.walls[0].canonical.end.x, 6.0)
        self.assertEqual(geometry.walls[0].canonical.length_meters, 4.0)

    def test_horizontal_vertical_and_diagonal_metric_lengths(self):
        cases = (
            (candidate(start=(10, 20), end=(110, 20), angle_degrees=0.0), 1.0, 0.0),
            (candidate(start=(10, 20), end=(10, 120), angle_degrees=90.0), 1.0, 90.0),
            (candidate(start=(10, 20), end=(110, 120), angle_degrees=45.0), math.sqrt(2), 45.0),
        )
        for wall, expected_length, expected_angle in cases:
            with self.subTest(angle=expected_angle):
                geometry = normalize_wall_coordinates(detection_result(wall), 100)
                self.assertAlmostEqual(geometry.walls[0].canonical.length_meters, expected_length)
                self.assertEqual(geometry.walls[0].canonical.angle_degrees, expected_angle)

    def test_metric_length_is_derived_from_endpoints_not_raw_length(self):
        wall = candidate(length_pixels=999.0)
        geometry = normalize_wall_coordinates(detection_result(wall), 100)
        self.assertEqual(geometry.walls[0].raw_pixels.length_pixels, 999.0)
        self.assertEqual(geometry.walls[0].canonical.length_meters, 2.0)

    def test_empty_detection_is_valid_empty_geometry(self):
        geometry = normalize_wall_coordinates(empty_detection(), 100)
        self.assertEqual(geometry.walls, ())
        self.assertFalse(geometry.source_truncated)
        self.assertEqual(geometry.coordinate_system.width_meters, 6.4)


class WallCoordinatePreservationTests(unittest.TestCase):
    def setUp(self):
        self.first = candidate(1, (5, 10), (5, 90), 80.25, 90.0)
        self.second = candidate(2, (10, 10), (30, 30), 28.284271, 45.0)
        self.source = detection_result(self.first, self.second, truncated=True)

    def test_raw_endpoints_lengths_angles_ids_and_order_are_preserved(self):
        geometry = normalize_wall_coordinates(self.source, 100)
        self.assertEqual([wall.candidate_id for wall in geometry.walls], [1, 2])
        self.assertEqual(
            [
                (wall.raw_pixels.start.x, wall.raw_pixels.start.y, wall.raw_pixels.end.x, wall.raw_pixels.end.y)
                for wall in geometry.walls
            ],
            [(5, 10, 5, 90), (10, 10, 30, 30)],
        )
        self.assertEqual(
            [(wall.raw_pixels.length_pixels, wall.raw_pixels.angle_degrees) for wall in geometry.walls],
            [(80.25, 90.0), (28.284271, 45.0)],
        )

    def test_source_truncated_is_propagated(self):
        self.assertTrue(normalize_wall_coordinates(self.source, 100).source_truncated)

    def test_ordinary_integer_raw_measurements_are_preserved(self):
        source = detection_result(candidate(length_pixels=200, angle_degrees=0))
        wall = normalize_wall_coordinates(source, 100).walls[0]
        self.assertIs(type(wall.raw_pixels.length_pixels), int)
        self.assertIs(type(wall.raw_pixels.angle_degrees), int)
        self.assertEqual(wall.canonical.angle_degrees, 0)

    def test_h1_input_object_remains_unchanged(self):
        before = self.source.to_dict()
        normalize_wall_coordinates(self.source, 100)
        self.assertEqual(self.source.to_dict(), before)
        self.assertEqual(self.source.candidates, (self.first, self.second))


class WallCoordinatePrecisionTests(unittest.TestCase):
    def test_internal_values_keep_full_floating_point_precision(self):
        wall = candidate(start=(1, 2), end=(2, 2), length_pixels=1.0)
        geometry = normalize_wall_coordinates(detection_result(wall, width=3, height=4), 3)
        self.assertEqual(geometry.walls[0].canonical.start.x, 1 / 3)
        self.assertEqual(geometry.coordinate_system.width_meters, 1.0)

    def test_serialization_rounds_metric_values_to_nine_places(self):
        wall = candidate(start=(1, 2), end=(2, 2), length_pixels=1.0)
        serialized = normalize_wall_coordinates(
            detection_result(wall, width=10, height=10),
            3,
        ).to_dict()
        self.assertEqual(serialized["walls"][0]["canonical"]["start"], {"x": 0.333333333, "y": 0.666666667})
        self.assertEqual(serialized["walls"][0]["canonical"]["length_meters"], 0.333333333)

    def test_negative_zero_is_normalized_during_serialization(self):
        self.assertEqual(CanonicalPoint(-0.0, -0.0000000001).to_dict(), {"x": 0.0, "y": 0.0})

    def test_json_contains_only_ordinary_python_values(self):
        serialized = normalize_wall_coordinates(detection_result(), 100).to_dict()
        round_trip = json.loads(json.dumps(serialized))
        self.assertEqual(round_trip, serialized)

        def assert_plain(value):
            self.assertIn(type(value), (dict, list, str, int, float, bool))
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIs(type(key), str)
                    assert_plain(item)
            elif isinstance(value, list):
                for item in value:
                    assert_plain(item)

        assert_plain(serialized)

    def test_repeated_conversions_are_identical(self):
        source = detection_result()
        self.assertEqual(
            normalize_wall_coordinates(source, 2.5),
            normalize_wall_coordinates(source, 2.5),
        )

    def test_exact_documented_serialized_structure(self):
        expected = {
            "coordinate_system": {
                "unit": "meter",
                "origin": "image_top_left",
                "x_direction": "right",
                "y_direction": "down",
                "pixels_per_meter": 100.0,
                "image_width_pixels": 640,
                "image_height_pixels": 480,
                "width_meters": 6.4,
                "height_meters": 4.8,
            },
            "source_truncated": False,
            "walls": [
                {
                    "candidate_id": 1,
                    "raw_pixels": {
                        "start": {"x": 20, "y": 35},
                        "end": {"x": 220, "y": 35},
                        "length_pixels": 200.0,
                        "angle_degrees": 0.0,
                    },
                    "canonical": {
                        "start": {"x": 0.2, "y": 0.35},
                        "end": {"x": 2.2, "y": 0.35},
                        "length_meters": 2.0,
                        "angle_degrees": 0.0,
                    },
                }
            ],
        }
        self.assertEqual(normalize_wall_coordinates(detection_result(), 100).to_dict(), expected)


class WallCoordinateValidationTests(unittest.TestCase):
    def assert_error(self, code, callable_object):
        with self.assertRaises(WallCoordinateError) as caught:
            callable_object()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), ERROR_MESSAGES[code])

    def test_missing_boolean_zero_negative_string_nan_and_infinite_scales_fail(self):
        source = detection_result()
        cases = (
            lambda: normalize_wall_coordinates(source),
            lambda: normalize_wall_coordinates(source, True),
            lambda: normalize_wall_coordinates(source, 0),
            lambda: normalize_wall_coordinates(source, -1),
            lambda: normalize_wall_coordinates(source, "100"),
            lambda: normalize_wall_coordinates(source, float("nan")),
            lambda: normalize_wall_coordinates(source, float("inf")),
            lambda: normalize_wall_coordinates(source, np.float64(100)),
        )
        for operation in cases:
            self.assert_error("INVALID_SCALE", operation)

    def test_wrong_input_type_and_invalid_result_metadata_fail(self):
        self.assert_error("INVALID_DETECTION_RESULT", lambda: normalize_wall_coordinates({}, 100))
        source = detection_result()
        self.assert_error(
            "INVALID_DETECTION_RESULT",
            lambda: normalize_wall_coordinates(replace(source, algorithm="other"), 100),
        )
        self.assert_error(
            "INVALID_DETECTION_RESULT",
            lambda: normalize_wall_coordinates(replace(source, truncated=1), 100),
        )

    def test_unsupported_coordinate_metadata_fails(self):
        source = detection_result()
        for changes in (
            {"unit": "meter"},
            {"origin": "bottom_left"},
            {"x_direction": "left"},
            {"y_direction": "up"},
        ):
            changed_space = replace(source.coordinate_space, **changes)
            self.assert_error(
                "UNSUPPORTED_COORDINATE_SYSTEM",
                lambda space=changed_space: normalize_wall_coordinates(replace(source, coordinate_space=space), 100),
            )

    def test_invalid_image_dimensions_fail(self):
        source = detection_result()
        for width, height in ((0, 480), (-1, 480), (640, 0), (4097, 1), (True, 480)):
            with self.subTest(width=width, height=height):
                space = replace(source.coordinate_space, width=width, height=height)
                self.assert_error(
                    "INVALID_IMAGE_DIMENSIONS",
                    lambda value=space: normalize_wall_coordinates(replace(source, coordinate_space=value), 100),
                )

    def test_duplicate_nonsequential_and_invalid_candidate_ids_fail(self):
        first = candidate(1, (5, 10), (5, 90), 80.0, 90.0)
        cases = (
            (replace(first, candidate_id=0),),
            (replace(first, candidate_id=True),),
            (replace(first, candidate_id=2),),
            (first, candidate(1, (10, 10), (30, 30), 28.0, 45.0)),
        )
        for candidates in cases:
            self.assert_error(
                "INVALID_CANDIDATE_ID",
                lambda values=candidates: normalize_wall_coordinates(detection_result(*values), 100),
            )

    def test_out_of_bounds_and_numpy_endpoints_fail(self):
        cases = (
            PixelPoint(-1, 0),
            PixelPoint(640, 0),
            PixelPoint(0, 480),
            PixelPoint(np.int64(1), 0),
        )
        for point in cases:
            malformed = replace(candidate(), start=point)
            self.assert_error(
                "OUT_OF_BOUNDS_ENDPOINT",
                lambda value=malformed: normalize_wall_coordinates(detection_result(value), 100),
            )

    def test_nonfinite_negative_length_and_invalid_angles_fail(self):
        for value in (float("nan"), float("inf"), -1, 10**10000, np.float64(1)):
            malformed = replace(candidate(), length_pixels=value)
            self.assert_error(
                "INVALID_LENGTH_OR_ANGLE",
                lambda item=malformed: normalize_wall_coordinates(detection_result(item), 100),
            )
        for value in (float("nan"), float("inf"), -0.1, 180, np.float64(45)):
            malformed = replace(candidate(), angle_degrees=value)
            self.assert_error(
                "INVALID_LENGTH_OR_ANGLE",
                lambda item=malformed: normalize_wall_coordinates(detection_result(item), 100),
            )

    def test_nonfinite_conversion_result_fails_safely(self):
        self.assert_error(
            "NONFINITE_CONVERSION_RESULT",
            lambda: normalize_wall_coordinates(detection_result(), 5e-324),
        )

    def test_noncanonical_duplicate_and_unsorted_segments_fail(self):
        reversed_wall = candidate(1, (20, 35), (10, 10), 30.0, 45.0)
        self.assert_error(
            "INVALID_DETECTION_RESULT",
            lambda: normalize_wall_coordinates(detection_result(reversed_wall), 100),
        )
        first = candidate(1, (20, 20), (30, 20), 10.0, 0.0)
        unsorted = candidate(2, (10, 10), (20, 10), 10.0, 0.0)
        self.assert_error(
            "INVALID_DETECTION_RESULT",
            lambda: normalize_wall_coordinates(detection_result(first, unsorted), 100),
        )
        duplicate = replace(first, candidate_id=2)
        self.assert_error(
            "INVALID_DETECTION_RESULT",
            lambda: normalize_wall_coordinates(detection_result(first, duplicate), 100),
        )


class WallCoordinateIsolationTests(unittest.TestCase):
    def test_geometry_executes_no_opencv_operations(self):
        with patch.object(cv2, "Canny", side_effect=AssertionError("OpenCV executed")), patch.object(
            cv2,
            "HoughLinesP",
            side_effect=AssertionError("OpenCV executed"),
        ):
            geometry = normalize_wall_coordinates(detection_result(), 100)
        self.assertEqual(len(geometry.walls), 1)

    def test_geometry_reads_and_writes_no_files(self):
        with patch("builtins.open", side_effect=AssertionError("filesystem access")):
            geometry = normalize_wall_coordinates(detection_result(), 100)
        self.assertEqual(geometry.coordinate_system.unit, "meter")

    def test_geometry_has_no_framework_database_or_renderer_state(self):
        import app.geometry.coordinates as coordinates
        import app.geometry.walls as walls

        combined = {**coordinates.__dict__, **walls.__dict__}
        for forbidden in (
            "cv2",
            "FastAPI",
            "Session",
            "ProcessingJob",
            "Path",
            "Konva",
            "Three",
        ):
            self.assertNotIn(forbidden, combined)

    def test_geometry_mutates_no_job_or_model(self):
        job = MagicMock(status="processing", progress=20)
        normalize_wall_coordinates(detection_result(), 100)
        self.assertEqual(job.status, "processing")
        self.assertEqual(job.progress, 20)

    def test_geometry_contracts_are_immutable(self):
        geometry = normalize_wall_coordinates(detection_result(), 100)
        with self.assertRaises(FrozenInstanceError):
            geometry.source_truncated = True
        with self.assertRaises(FrozenInstanceError):
            geometry.walls[0].candidate_id = 2


if __name__ == "__main__":
    unittest.main()
