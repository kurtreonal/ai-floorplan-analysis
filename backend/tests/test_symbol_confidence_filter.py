import math
import unittest
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import patch

from app.ai.symbol_detection.confidence_filter import (
    DETECTED_STATUS,
    NEEDS_REVIEW_STATUS,
    SAFE_CONFIDENCE_FILTER_ERROR_MESSAGE,
    ClassifiedSymbolPrediction,
    SymbolConfidenceFilterError,
    SymbolConfidenceFilterResult,
    classify_symbol_predictions,
    classify_symbol_predictions_from_settings,
)
from app.ai.symbol_detection.inference import (
    MAXIMUM_DETECTIONS,
    SymbolBoundingBox,
    SymbolCenter,
    SymbolInferenceResult,
    SymbolPrediction,
)
from app.core.config import Settings


def prediction(
    confidence,
    *,
    class_id=0,
    class_name="custom-symbol",
    bounding_box=None,
    center=None,
):
    selected_box = bounding_box or SymbolBoundingBox(1.0, 2.0, 5.0, 6.0)
    selected_center = center or SymbolCenter(3.0, 4.0)
    return SymbolPrediction(
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bounding_box=selected_box,
        center=selected_center,
    )


def inference_result(predictions=(), *, limit_reached=False):
    return SymbolInferenceResult(
        image_width=20,
        image_height=10,
        predictions=tuple(predictions),
        maximum_detections=MAXIMUM_DETECTIONS,
        detection_limit_reached=limit_reached,
    )


class SymbolConfidenceFilterTests(unittest.TestCase):
    def assert_error(self, code, operation):
        with self.assertRaises(SymbolConfidenceFilterError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(
            str(caught.exception),
            SAFE_CONFIDENCE_FILTER_ERROR_MESSAGE,
        )
        return caught.exception

    def test_default_configuration_threshold_is_exactly_point_five(self):
        source = inference_result((prediction(0.50), prediction(0.49)))
        result = classify_symbol_predictions_from_settings(
            source,
            settings=Settings(_env_file=None),
        )
        self.assertEqual(result.threshold, 0.50)
        self.assertEqual(
            tuple(item.status for item in result.predictions),
            (DETECTED_STATUS, NEEDS_REVIEW_STATUS),
        )

    def test_equality_is_detected_and_immediately_below_needs_review(self):
        immediately_below = math.nextafter(0.50, 0.0)
        result = classify_symbol_predictions(
            inference_result(
                (prediction(0.50), prediction(immediately_below))
            ),
            threshold=0.50,
        )
        self.assertEqual(result.predictions[0].status, DETECTED_STATUS)
        self.assertEqual(result.predictions[1].status, NEEDS_REVIEW_STATUS)

    def test_injected_configuration_changes_threshold(self):
        settings = Settings(_env_file=None, yolo_confidence_threshold=0.75)
        result = classify_symbol_predictions_from_settings(
            inference_result((prediction(0.74), prediction(0.75))),
            settings=settings,
        )
        self.assertEqual(result.threshold, 0.75)
        self.assertEqual(
            tuple(item.status for item in result.predictions),
            (NEEDS_REVIEW_STATUS, DETECTED_STATUS),
        )

    def test_zero_and_one_threshold_boundaries(self):
        cases = (
            (0.0, (0.0, 0.25, 1.0), ("detected", "detected", "detected")),
            (1.0, (0.0, 0.999, 1.0), ("needs_review", "needs_review", "detected")),
        )
        for threshold, confidences, statuses in cases:
            with self.subTest(threshold=threshold):
                result = classify_symbol_predictions(
                    inference_result(tuple(prediction(value) for value in confidences)),
                    threshold=threshold,
                )
                self.assertEqual(
                    tuple(item.status for item in result.predictions),
                    statuses,
                )

    def test_empty_inference_result_is_successful(self):
        result = classify_symbol_predictions(
            inference_result(),
            threshold=0.50,
        )
        self.assertEqual(result.predictions, ())
        self.assertEqual(result.image_width, 20)
        self.assertEqual(result.image_height, 10)
        self.assertFalse(result.detection_limit_reached)

    def test_mixed_predictions_preserve_order_identity_and_exact_data(self):
        original = (
            prediction(0.9, class_id=9, class_name="alpha"),
            prediction(0.1, class_id=3, class_name="beta"),
            prediction(0.5, class_id=7, class_name="gamma"),
        )
        result = classify_symbol_predictions(
            inference_result(original),
            threshold=0.50,
        )
        self.assertEqual(
            tuple(item.status for item in result.predictions),
            (DETECTED_STATUS, NEEDS_REVIEW_STATUS, DETECTED_STATUS),
        )
        for classified, source in zip(result.predictions, original, strict=True):
            self.assertIs(classified.prediction, source)
            self.assertEqual(classified.prediction.confidence, source.confidence)
            self.assertIs(classified.prediction.bounding_box, source.bounding_box)
            self.assertIs(classified.prediction.center, source.center)

    def test_result_contracts_are_immutable(self):
        result = classify_symbol_predictions(
            inference_result((prediction(0.8),)),
            threshold=0.50,
        )
        self.assertIsInstance(result, SymbolConfidenceFilterResult)
        self.assertIsInstance(result.predictions[0], ClassifiedSymbolPrediction)
        with self.assertRaises(FrozenInstanceError):
            result.threshold = 0.9
        with self.assertRaises(FrozenInstanceError):
            result.predictions[0].status = NEEDS_REVIEW_STATUS

    def test_detection_limit_metadata_is_preserved(self):
        predictions = tuple(prediction(0.25) for _ in range(MAXIMUM_DETECTIONS))
        source = inference_result(predictions, limit_reached=True)
        result = classify_symbol_predictions(source, threshold=0.50)
        self.assertEqual(result.maximum_detections, MAXIMUM_DETECTIONS)
        self.assertTrue(result.detection_limit_reached)
        self.assertEqual(len(result.predictions), MAXIMUM_DETECTIONS)

    def test_invalid_thresholds_fail_safely(self):
        invalid = (True, False, "0.5", None, -0.01, 1.01, math.nan, math.inf, -math.inf)
        for threshold in invalid:
            with self.subTest(threshold=threshold):
                self.assert_error(
                    "INVALID_CONFIDENCE_THRESHOLD",
                    lambda value=threshold: classify_symbol_predictions(
                        inference_result(),
                        threshold=value,
                    ),
                )

    def test_malformed_result_container_fields_fail_safely(self):
        valid = inference_result()
        invalid = (
            None,
            object(),
            replace(valid, image_width=0),
            replace(valid, image_height=4097),
            replace(valid, predictions=[]),
            replace(valid, maximum_detections=0),
            replace(valid, maximum_detections=299),
            replace(valid, detection_limit_reached=True),
            replace(valid, detection_limit_reached=1),
        )
        for source in invalid:
            with self.subTest(source=repr(source)):
                self.assert_error(
                    "INVALID_INFERENCE_RESULT",
                    lambda value=source: classify_symbol_predictions(
                        value,
                        threshold=0.50,
                    ),
                )

    def test_malformed_predictions_fail_safely(self):
        valid = prediction(0.50)
        invalid = (
            object(),
            replace(valid, class_id=-1),
            replace(valid, class_id=True),
            replace(valid, class_name=""),
            replace(valid, confidence=True),
            replace(valid, confidence=-0.1),
            replace(valid, confidence=1.1),
            replace(valid, confidence=math.nan),
            replace(valid, confidence=math.inf),
            replace(valid, bounding_box=object()),
            replace(valid, center=object()),
            replace(valid, bounding_box=SymbolBoundingBox(-1.0, 2.0, 5.0, 6.0)),
            replace(valid, bounding_box=SymbolBoundingBox(5.0, 2.0, 1.0, 6.0)),
            replace(valid, bounding_box=SymbolBoundingBox(1.0, 2.0, 21.0, 6.0)),
            replace(valid, center=SymbolCenter(2.9, 4.0)),
        )
        for item in invalid:
            with self.subTest(item=repr(item)):
                self.assert_error(
                    "INVALID_INFERENCE_RESULT",
                    lambda value=item: classify_symbol_predictions(
                        inference_result((value,)),
                        threshold=0.50,
                    ),
                )

    def test_configuration_boundary_sanitizes_missing_or_invalid_setting(self):
        for settings in (object(), SimpleNamespace(yolo_confidence_threshold="bad")):
            with self.subTest(settings=repr(settings)):
                self.assert_error(
                    "INVALID_CONFIDENCE_THRESHOLD",
                    lambda value=settings: classify_symbol_predictions_from_settings(
                        inference_result(),
                        settings=value,
                    ),
                )

    def test_pure_filter_has_no_external_or_job_side_effects(self):
        job = SimpleNamespace(status="processing", progress=60, error_message=None)
        before = vars(job).copy()
        with patch("builtins.open", side_effect=AssertionError("filesystem used")), patch(
            "app.core.database.get_engine",
            side_effect=AssertionError("database used"),
        ), patch(
            "app.ai.symbol_detection.inference.run_symbol_inference",
            side_effect=AssertionError("YOLO inference used"),
        ):
            result = classify_symbol_predictions(
                inference_result((prediction(0.2),)),
                threshold=0.50,
            )
        self.assertEqual(result.predictions[0].status, NEEDS_REVIEW_STATUS)
        self.assertEqual(vars(job), before)


if __name__ == "__main__":
    unittest.main()
