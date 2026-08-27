import json
import math
import unittest
from dataclasses import FrozenInstanceError, replace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from app.ai.preprocessing.config import PreprocessingParameters
from app.ai.preprocessing.pipeline import preprocess_image
from app.ai.wall_detection.config import (
    WallDetectionConfigurationError,
    WallDetectionParameters,
)
from app.ai.wall_detection.detector import (
    ERROR_MESSAGES,
    PixelPoint,
    WallDetectionError,
    WallLineCandidate,
    detect_wall_lines,
)


def binary_canvas(width=256, height=192):
    return np.full((height, width), 255, dtype=np.uint8)


def prototype_parameters(**overrides):
    values = {
        "hough_vote_threshold": 10,
        "minimum_line_length": 20,
        "maximum_line_gap": 3,
    }
    values.update(overrides)
    return WallDetectionParameters(**values)


def g3_result(width=64, height=48):
    rgb = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.line(rgb, (5, height // 2), (width - 6, height // 2), (0, 0, 0), 2)
    return preprocess_image(
        rgb,
        parameters=PreprocessingParameters(gaussian_blur_enabled=False),
    )


class WallDetectionConfigurationTests(unittest.TestCase):
    def assert_invalid(self, **values):
        with self.assertRaises(WallDetectionConfigurationError) as caught:
            WallDetectionParameters(**values)
        self.assertIsInstance(caught.exception, WallDetectionError)
        self.assertEqual(caught.exception.code, "INVALID_CONFIGURATION")
        self.assertEqual(str(caught.exception), ERROR_MESSAGES["INVALID_CONFIGURATION"])

    def test_defaults_are_centralized_and_frozen(self):
        parameters = WallDetectionParameters()
        self.assertEqual(parameters.canny_low_threshold, 50)
        self.assertEqual(parameters.canny_high_threshold, 200)
        self.assertEqual(parameters.canny_aperture_size, 3)
        self.assertEqual(parameters.hough_rho, 1.0)
        self.assertEqual(parameters.hough_theta_degrees, 1.0)
        self.assertEqual(parameters.hough_vote_threshold, 50)
        self.assertEqual(parameters.minimum_line_length, 50)
        self.assertEqual(parameters.maximum_line_gap, 10)
        self.assertEqual(parameters.maximum_candidates, 2000)
        with self.assertRaises(FrozenInstanceError):
            parameters.maximum_candidates = 5

    def test_valid_overrides_and_mapping_work(self):
        parameters = WallDetectionParameters.from_mapping(
            {
                "canny_low_threshold": 10,
                "canny_high_threshold": 20,
                "canny_aperture_size": 7,
                "hough_rho": 0.5,
                "hough_theta_degrees": 180,
                "hough_vote_threshold": 1,
                "minimum_line_length": 0,
                "maximum_line_gap": 0.25,
                "maximum_candidates": 1,
            }
        )
        self.assertEqual(parameters.canny_aperture_size, 7)
        self.assertEqual(parameters.maximum_line_gap, 0.25)

    def test_invalid_canny_thresholds_fail_safely(self):
        cases = (
            {"canny_low_threshold": True},
            {"canny_low_threshold": -1},
            {"canny_high_threshold": 256},
            {"canny_low_threshold": 200, "canny_high_threshold": 200},
            {"canny_low_threshold": 201, "canny_high_threshold": 200},
        )
        for values in cases:
            with self.subTest(values=values):
                self.assert_invalid(**values)

    def test_invalid_apertures_fail_safely(self):
        for value in (True, 0, 1, 4, 9):
            with self.subTest(value=value):
                self.assert_invalid(canny_aperture_size=value)

    def test_invalid_rho_and_theta_fail_safely(self):
        for name, values in (
            ("hough_rho", (True, 0, -1, float("nan"), float("inf"))),
            ("hough_theta_degrees", (True, 0, -1, 181, float("nan"), float("inf"))),
        ):
            for value in values:
                with self.subTest(name=name, value=value):
                    self.assert_invalid(**{name: value})

    def test_invalid_vote_candidate_length_and_gap_fail_safely(self):
        for name in ("hough_vote_threshold", "maximum_candidates"):
            for value in (True, 0, -1, 1.5):
                with self.subTest(name=name, value=value):
                    self.assert_invalid(**{name: value})
        for name in ("minimum_line_length", "maximum_line_gap"):
            for value in (True, -1, float("nan"), float("inf"), "10"):
                with self.subTest(name=name, value=value):
                    self.assert_invalid(**{name: value})

    def test_unknown_fields_are_rejected_without_private_values(self):
        self.assert_invalid(private_path="C:/secret/floor.png")
        with self.assertRaises(WallDetectionConfigurationError) as caught:
            WallDetectionParameters.from_mapping({"unknown": "private"})
        self.assertNotIn("private", str(caught.exception))


class WallDetectionInputTests(unittest.TestCase):
    def assert_error(self, code, callable_object):
        with self.assertRaises(WallDetectionError) as caught:
            callable_object()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), ERROR_MESSAGES[code])

    def test_valid_direct_array_and_g3_result_are_accepted(self):
        direct = binary_canvas(64, 48)
        cv2.line(direct, (5, 24), (58, 24), 0, 2)
        direct_result = detect_wall_lines(direct, parameters=prototype_parameters())
        processed_result = detect_wall_lines(g3_result(), parameters=prototype_parameters())
        self.assertEqual(direct_result.coordinate_space.width, 64)
        self.assertEqual(processed_result.coordinate_space.height, 48)
        self.assertGreater(len(direct_result.candidates), 0)
        self.assertGreater(len(processed_result.candidates), 0)

    def test_invalid_array_types_shapes_and_dtypes_fail(self):
        cases = (
            (np.empty((0, 10), dtype=np.uint8), "INVALID_DTYPE_OR_SHAPE"),
            (np.zeros((10, 10, 3), dtype=np.uint8), "INVALID_DTYPE_OR_SHAPE"),
            (np.zeros((10, 10), dtype=np.float32), "INVALID_DTYPE_OR_SHAPE"),
            (np.zeros((10, 10), dtype=bool), "INVALID_DTYPE_OR_SHAPE"),
            (np.zeros((1, 4097), dtype=np.uint8), "UNSAFE_DIMENSIONS"),
        )
        for value, code in cases:
            with self.subTest(code=code):
                self.assert_error(code, lambda item=value: detect_wall_lines(item))

    def test_nonarray_and_nonbinary_values_fail(self):
        self.assert_error("INVALID_PROCESSED_IMAGE_RESULT", lambda: detect_wall_lines([[0, 255]]))
        image = binary_canvas(4, 4)
        image[0, 0] = 127
        self.assert_error("NONBINARY_IMAGE", lambda: detect_wall_lines(image))

    def test_invalid_parameter_object_fails_safely(self):
        self.assert_error(
            "INVALID_CONFIGURATION",
            lambda: detect_wall_lines(binary_canvas(), parameters=0),
        )

    def test_mismatched_g3_dimensions_fail(self):
        processed = g3_result()
        self.assert_error(
            "INVALID_PROCESSED_IMAGE_RESULT",
            lambda: detect_wall_lines(replace(processed, width=processed.width + 1)),
        )

    def test_input_remains_byte_for_byte_unchanged(self):
        image = binary_canvas()
        cv2.line(image, (10, 10), (200, 100), 0, 2)
        before = image.tobytes()
        detect_wall_lines(image, parameters=prototype_parameters())
        self.assertEqual(image.tobytes(), before)

    def test_detector_uses_only_g3_thresholded_array(self):
        processed = g3_result()
        with patch("app.ai.wall_detection.detector.cv2.Canny", return_value=np.zeros_like(processed.thresholded)) as canny, patch(
            "app.ai.wall_detection.detector.cv2.HoughLinesP",
            return_value=None,
        ):
            detect_wall_lines(processed)
        np.testing.assert_array_equal(canny.call_args.args[0], processed.thresholded)
        self.assertFalse(np.shares_memory(canny.call_args.args[0], processed.thresholded))


class WallDetectionBehaviorTests(unittest.TestCase):
    def detect(self, image):
        return detect_wall_lines(image, parameters=prototype_parameters())

    def test_horizontal_line_produces_horizontal_candidate(self):
        image = binary_canvas()
        cv2.line(image, (20, 60), (220, 60), 0, 2)
        result = self.detect(image)
        self.assertTrue(any(candidate.angle_degrees == 0.0 for candidate in result.candidates))

    def test_vertical_line_produces_vertical_candidate(self):
        image = binary_canvas()
        cv2.line(image, (100, 20), (100, 170), 0, 2)
        result = self.detect(image)
        self.assertTrue(any(candidate.angle_degrees == 90.0 for candidate in result.candidates))

    def test_diagonal_line_produces_diagonal_candidate(self):
        image = binary_canvas()
        cv2.line(image, (20, 20), (170, 170), 0, 2)
        result = self.detect(image)
        self.assertTrue(any(40 <= candidate.angle_degrees <= 50 for candidate in result.candidates))

    def test_mixed_synthetic_floor_plan_lines(self):
        image = binary_canvas()
        cv2.rectangle(image, (20, 20), (220, 160), 0, 2)
        cv2.line(image, (120, 20), (120, 160), 0, 2)
        result = self.detect(image)
        angles = {candidate.angle_degrees for candidate in result.candidates}
        self.assertIn(0.0, angles)
        self.assertIn(90.0, angles)

    def test_all_white_and_all_black_are_valid_empty_results(self):
        for value in (0, 255):
            with self.subTest(value=value):
                result = detect_wall_lines(np.full((20, 30), value, dtype=np.uint8))
                self.assertEqual(result.candidates, ())
                self.assertFalse(result.truncated)

    def test_seeded_noise_is_deterministic(self):
        rng = np.random.default_rng(20260827)
        image = np.where(rng.random((96, 128)) > 0.9, 0, 255).astype(np.uint8)
        parameters = prototype_parameters(maximum_candidates=25)
        first = detect_wall_lines(image, parameters=parameters)
        second = detect_wall_lines(image, parameters=parameters)
        self.assertEqual(first, second)

    def test_hough_none_and_empty_array_return_empty_result(self):
        image = binary_canvas(20, 20)
        image[5:15, 5:15] = 0
        for output in (None, np.empty((0, 1, 4), dtype=np.int32)):
            with self.subTest(output=output), patch(
                "app.ai.wall_detection.detector.cv2.HoughLinesP",
                return_value=output,
            ):
                result = detect_wall_lines(image)
                self.assertEqual(result.candidates, ())
                self.assertFalse(result.truncated)

    def test_opencv_exceptions_are_sanitized(self):
        image = binary_canvas(20, 20)
        image[5:15, 5:15] = 0
        cases = (
            ("cv2.Canny", "EDGE_DETECTION_FAILED"),
            ("cv2.HoughLinesP", "HOUGH_DETECTION_FAILED"),
        )
        for target, code in cases:
            with self.subTest(code=code), patch(
                f"app.ai.wall_detection.detector.{target}",
                side_effect=RuntimeError("private OpenCV array detail"),
            ):
                with self.assertRaises(WallDetectionError) as caught:
                    detect_wall_lines(image)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn("private", str(caught.exception))

    def test_malformed_and_out_of_bounds_hough_results_fail_safely(self):
        image = binary_canvas(50, 40)
        image[5:15, 5:15] = 0
        cases = (
            ([1, 2, 3, 4], "MALFORMED_OPENCV_RESULT"),
            (np.array([[[1.5, 2, 3, 4]]]), "MALFORMED_OPENCV_RESULT"),
            (np.array([[[1, 2, 3]]], dtype=np.int32), "MALFORMED_OPENCV_RESULT"),
            (np.array([[[1, 2, 50, 4]]], dtype=np.int32), "INVALID_COORDINATES"),
        )
        for output, code in cases:
            with self.subTest(code=code), patch(
                "app.ai.wall_detection.detector.cv2.HoughLinesP",
                return_value=output,
            ):
                with self.assertRaises(WallDetectionError) as caught:
                    detect_wall_lines(image)
                self.assertEqual(caught.exception.code, code)


class WallDetectionDeterminismTests(unittest.TestCase):
    def setUp(self):
        self.image = binary_canvas(256, 192)
        self.image[5:15, 5:15] = 0
        self.unordered = np.array(
            [
                [[220, 35, 20, 35]],
                [[30, 30, 10, 10]],
                [[20, 35, 220, 35]],
                [[5, 90, 5, 10]],
                [[10, 30, 30, 10]],
            ],
            dtype=np.int32,
        )

    def mocked_result(self, lines=None, maximum_candidates=2000):
        with patch(
            "app.ai.wall_detection.detector.cv2.HoughLinesP",
            return_value=self.unordered if lines is None else lines,
        ):
            return detect_wall_lines(
                self.image,
                parameters=WallDetectionParameters(maximum_candidates=maximum_candidates),
            )

    def test_canonicalization_duplicate_removal_sorting_and_ids(self):
        result = self.mocked_result()
        endpoints = [
            (item.start.x, item.start.y, item.end.x, item.end.y)
            for item in result.candidates
        ]
        self.assertEqual(
            endpoints,
            [(5, 10, 5, 90), (10, 10, 30, 30), (30, 10, 10, 30), (20, 35, 220, 35)],
        )
        self.assertEqual([item.candidate_id for item in result.candidates], [1, 2, 3, 4])

    def test_lengths_angles_and_numeric_types_are_stable(self):
        result = self.mocked_result()
        expected = ((80.0, 90.0), (28.284271, 45.0), (28.284271, 135.0), (200.0, 0.0))
        self.assertEqual(
            tuple((item.length_pixels, item.angle_degrees) for item in result.candidates),
            expected,
        )
        for candidate in result.candidates:
            self.assertIs(type(candidate.candidate_id), int)
            self.assertIs(type(candidate.start.x), int)
            self.assertIs(type(candidate.length_pixels), float)
            self.assertIs(type(candidate.angle_degrees), float)

    def test_exact_documented_dictionary_and_json_structure(self):
        result = self.mocked_result(lines=np.array([[[220, 35, 20, 35]]], dtype=np.int32))
        expected = {
            "coordinate_space": {
                "unit": "pixel",
                "origin": "top_left",
                "x_direction": "right",
                "y_direction": "down",
                "width": 256,
                "height": 192,
            },
            "algorithm": "probabilistic_hough",
            "truncated": False,
            "candidates": [
                {
                    "candidate_id": 1,
                    "start": {"x": 20, "y": 35},
                    "end": {"x": 220, "y": 35},
                    "length_pixels": 200.0,
                    "angle_degrees": 0.0,
                }
            ],
        }
        self.assertEqual(result.to_dict(), expected)
        self.assertEqual(json.loads(json.dumps(result.to_dict())), expected)

    def test_repeated_unordered_results_are_identical(self):
        self.assertEqual(self.mocked_result(), self.mocked_result())

    def test_results_below_and_above_limit_report_truncation(self):
        below = self.mocked_result(maximum_candidates=4)
        above = self.mocked_result(maximum_candidates=2)
        self.assertFalse(below.truncated)
        self.assertEqual(len(below.candidates), 4)
        self.assertTrue(above.truncated)
        self.assertEqual(len(above.candidates), 2)
        self.assertEqual(
            tuple((item.start.x, item.start.y) for item in above.candidates),
            ((5, 10), (10, 10)),
        )

    def test_result_types_are_immutable(self):
        point = PixelPoint(1, 2)
        candidate = WallLineCandidate(1, point, PixelPoint(3, 4), math.sqrt(8), 45.0)
        with self.assertRaises(FrozenInstanceError):
            point.x = 9
        with self.assertRaises(FrozenInstanceError):
            candidate.candidate_id = 2


class WallDetectionIsolationTests(unittest.TestCase):
    def test_detection_reads_and_writes_no_files(self):
        image = binary_canvas(20, 20)
        image[5:15, 5:15] = 0
        with patch("builtins.open", side_effect=AssertionError("filesystem access")):
            result = detect_wall_lines(image)
        self.assertEqual(result.algorithm, "probabilistic_hough")

    def test_detector_has_no_http_database_or_job_state_dependency(self):
        import app.ai.wall_detection.detector as detector

        source = detector.__dict__
        self.assertNotIn("Session", source)
        self.assertNotIn("ProcessingJob", source)
        self.assertNotIn("FastAPI", source)
        self.assertNotIn("Path", source)
        job = MagicMock(status="processing", progress=25)
        image = binary_canvas(20, 20)
        result = detect_wall_lines(image)
        self.assertEqual(result.candidates, ())
        self.assertEqual(job.status, "processing")
        self.assertEqual(job.progress, 25)

    def test_no_debug_preview_or_drawing_is_created(self):
        image = binary_canvas(20, 20)
        image[5:15, 5:15] = 0
        with patch.object(cv2, "line", side_effect=AssertionError("drawing")), patch.object(
            cv2,
            "imwrite",
            side_effect=AssertionError("preview"),
        ):
            detect_wall_lines(image)


if __name__ == "__main__":
    unittest.main()
