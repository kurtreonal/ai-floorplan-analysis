import socket
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from app.ai.preprocessing import PreprocessedImage, PreprocessingParameters
from app.ai.symbol_detection.inference import (
    MAXIMUM_DETECTIONS,
    SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE,
    SymbolBoundingBox,
    SymbolCenter,
    SymbolInferenceError,
    SymbolInferenceResult,
    SymbolPrediction,
    run_processing_job_symbol_inference,
    run_symbol_inference,
)
from app.ai.symbol_detection.model_loader import (
    LoadedSymbolDetectionModel,
    SymbolClassMetadata,
    YOLOModelLoaderError,
)
from app.models import FloorPlan, ProcessingJob


class TensorLike:
    def __init__(self, value):
        self.value = np.asarray(value)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.value


class FakeBoxes:
    def __init__(self, xyxy, confidence, classes, *, tensor_like=False):
        wrapper = TensorLike if tensor_like else np.asarray
        self.xyxy = wrapper(xyxy)
        self.conf = wrapper(confidence)
        self.cls = wrapper(classes)


class FakeResult:
    def __init__(self, boxes, *, masks=None, obb=None, probs=None):
        self.boxes = boxes
        self.masks = masks
        self.obb = obb
        self.probs = probs


class FakeModel:
    def __init__(self, results=None, *, error=None):
        self.results = results
        self.error = error
        self.calls = []
        self.plot = MagicMock(side_effect=AssertionError("plot called"))
        self.save = MagicMock(side_effect=AssertionError("save called"))
        self.show = MagicMock(side_effect=AssertionError("show called"))
        self.export = MagicMock(side_effect=AssertionError("export called"))
        self.train = MagicMock(side_effect=AssertionError("train called"))
        self.track = MagicMock(side_effect=AssertionError("track called"))

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.results


def processed_image(width=8, height=6):
    thresholded = np.zeros((height, width), dtype=np.uint8)
    thresholded[:, width // 2 :] = 255
    grayscale = thresholded.copy()
    return PreprocessedImage(
        width=width,
        height=height,
        grayscale=grayscale,
        denoised=grayscale.copy(),
        blurred=None,
        thresholded=thresholded,
        gaussian_applied=False,
        threshold_mode="fixed",
        actual_threshold=127.0,
        inverted=False,
        parameters=PreprocessingParameters(
            threshold_mode="fixed",
            fixed_threshold=127,
        ),
    )


def loaded_model(model, classes=None, task="detect"):
    return LoadedSymbolDetectionModel(
        model=model,
        classes=classes
        if classes is not None
        else (
            SymbolClassMetadata(0, "outlet"),
            SymbolClassMetadata(1, "switch"),
        ),
        task=task,
        _resolved_path=Path("private-test-model.pt"),
    )


def one_result(
    *,
    xyxy=((1.0, 1.0, 5.0, 3.0),),
    confidence=(0.3123456789,),
    classes=(0.0,),
    tensor_like=False,
):
    return [
        FakeResult(
            FakeBoxes(
                xyxy,
                confidence,
                classes,
                tensor_like=tensor_like,
            )
        )
    ]


class SymbolInferenceTests(unittest.TestCase):
    def assert_error(self, code, operation):
        with self.assertRaises(SymbolInferenceError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(
            str(caught.exception),
            SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE,
        )
        return caught.exception

    def test_valid_g3_image_is_copied_to_three_channels_with_exact_arguments(self):
        source = processed_image()
        original = source.thresholded.copy()
        model = FakeModel(one_result())

        result = run_symbol_inference(source, loaded_model(model))

        self.assertEqual(len(model.calls), 1)
        arguments = model.calls[0]
        self.assertEqual(
            set(arguments),
            {"source", "conf", "max_det", "verbose", "save", "stream"},
        )
        self.assertEqual(arguments["conf"], 0.0)
        self.assertEqual(arguments["max_det"], 300)
        self.assertIs(arguments["verbose"], False)
        self.assertIs(arguments["save"], False)
        self.assertIs(arguments["stream"], False)
        inference_image = arguments["source"]
        self.assertEqual(inference_image.shape, (source.height, source.width, 3))
        self.assertEqual(inference_image.dtype, np.uint8)
        self.assertTrue(inference_image.flags.c_contiguous)
        for channel in range(3):
            np.testing.assert_array_equal(inference_image[:, :, channel], original)
        self.assertFalse(np.shares_memory(inference_image, source.thresholded))
        inference_image[0, 0, 0] = 255
        np.testing.assert_array_equal(source.thresholded, original)
        self.assertEqual(result.image_width, source.width)
        self.assertEqual(result.image_height, source.height)

    def test_valid_detection_preserves_confidence_and_uses_immutable_schema(self):
        confidence = 0.123456789123
        result = run_symbol_inference(
            processed_image(),
            loaded_model(FakeModel(one_result(confidence=(confidence,)))),
        )
        self.assertIsInstance(result, SymbolInferenceResult)
        self.assertEqual(
            result.predictions,
            (
                SymbolPrediction(
                    class_id=0,
                    class_name="outlet",
                    confidence=confidence,
                    bounding_box=SymbolBoundingBox(1.0, 1.0, 5.0, 3.0),
                    center=SymbolCenter(3.0, 2.0),
                ),
            ),
        )
        self.assertLess(result.predictions[0].confidence, 0.50)
        with self.assertRaises(FrozenInstanceError):
            result.image_width = 99

    def test_dynamic_classes_and_model_order_are_preserved(self):
        model = FakeModel(
            one_result(
                xyxy=((2, 1, 4, 5), (0, 0, 2, 2)),
                confidence=(0.8, 0.7),
                classes=(1, 0),
            )
        )
        result = run_symbol_inference(processed_image(), loaded_model(model))
        self.assertEqual(
            tuple((item.class_id, item.class_name) for item in result.predictions),
            ((1, "switch"), (0, "outlet")),
        )
        self.assertEqual(result.predictions[0].center, SymbolCenter(3.0, 3.0))
        self.assertEqual(result.predictions[1].center, SymbolCenter(1.0, 1.0))

    def test_boxes_none_empty_list_and_empty_arrays_are_successful(self):
        cases = (
            [FakeResult(None)],
            [FakeResult([])],
            one_result(xyxy=np.empty((0, 4)), confidence=(), classes=()),
        )
        for raw_results in cases:
            with self.subTest(shape=repr(raw_results)):
                result = run_symbol_inference(
                    processed_image(),
                    loaded_model(FakeModel(raw_results)),
                )
                self.assertEqual(result.predictions, ())
                self.assertFalse(result.detection_limit_reached)
                self.assertEqual(result.maximum_detections, 300)

    def test_exactly_maximum_detections_reports_limit(self):
        boxes = np.tile(np.array([[0.0, 0.0, 1.0, 1.0]]), (300, 1))
        result = run_symbol_inference(
            processed_image(),
            loaded_model(
                FakeModel(
                    one_result(
                        xyxy=boxes,
                        confidence=np.full(300, 0.1),
                        classes=np.zeros(300),
                    )
                )
            ),
        )
        self.assertEqual(len(result.predictions), MAXIMUM_DETECTIONS)
        self.assertTrue(result.detection_limit_reached)

    def test_tensor_like_outputs_are_supported_without_torch_coupling(self):
        result = run_symbol_inference(
            processed_image(),
            loaded_model(FakeModel(one_result(tensor_like=True))),
        )
        self.assertEqual(result.predictions[0].class_name, "outlet")

    def test_invalid_processed_images_are_rejected_before_prediction(self):
        valid = processed_image()
        invalid_arrays = (
            replace(valid, thresholded=[[0, 255]]),
            replace(valid, thresholded=valid.thresholded.astype(np.float32)),
            replace(valid, thresholded=valid.thresholded[:, :, np.newaxis]),
            replace(valid, thresholded=valid.thresholded[:-1]),
            replace(valid, thresholded=np.full_like(valid.thresholded, 128)),
            replace(valid, width=4097, thresholded=np.zeros((6, 4097), dtype=np.uint8)),
            replace(valid, width=0, thresholded=np.empty((6, 0), dtype=np.uint8)),
        )
        for value in (None, object(), *invalid_arrays):
            with self.subTest(value=type(value).__name__):
                model = FakeModel(one_result())
                self.assert_error(
                    "INVALID_PROCESSED_IMAGE",
                    lambda item=value: run_symbol_inference(
                        item,
                        loaded_model(model),
                    ),
                )
                self.assertEqual(model.calls, [])

    def test_invalid_loaded_models_are_rejected_before_prediction(self):
        valid_model = FakeModel(one_result())
        invalid_models = (
            None,
            object(),
            loaded_model(object()),
            loaded_model(valid_model, classes=()),
            loaded_model(valid_model, classes=(SymbolClassMetadata(0, "outlet"),) * 2),
            loaded_model(valid_model, task="segment"),
        )
        for value in invalid_models:
            with self.subTest(value=repr(value)):
                self.assert_error(
                    "INVALID_LOADED_MODEL",
                    lambda item=value: run_symbol_inference(processed_image(), item),
                )

    def test_zero_or_multiple_results_are_rejected(self):
        for raw_results in ([], one_result() * 2, None, object()):
            with self.subTest(raw_results=repr(raw_results)):
                self.assert_error(
                    "INVALID_RESULT_COUNT",
                    lambda value=raw_results: run_symbol_inference(
                        processed_image(),
                        loaded_model(FakeModel(value)),
                    ),
                )

    def test_masks_obb_and_classification_outputs_are_rejected(self):
        for field in ("masks", "obb", "probs"):
            with self.subTest(field=field):
                result = FakeResult(None)
                setattr(result, field, object())
                self.assert_error(
                    "INVALID_BOX_OUTPUT",
                    lambda value=result: run_symbol_inference(
                        processed_image(),
                        loaded_model(FakeModel([value])),
                    ),
                )

    def test_malformed_shapes_and_mismatched_counts_are_rejected(self):
        cases = (
            ("INVALID_BOX_OUTPUT", ((1, 2, 3),), (0.5,), (0,)),
            ("INVALID_BOX_OUTPUT", ((1, 2, 3, 4),), (0.5, 0.6), (0,)),
            ("INVALID_CONFIDENCE", ((1, 2, 3, 4),), ((0.5,),), (0,)),
            ("INVALID_CLASS_OUTPUT", ((1, 2, 3, 4),), (0.5,), ((0,),)),
        )
        for code, xyxy, confidence, classes in cases:
            with self.subTest(code=code):
                self.assert_error(
                    code,
                    lambda: run_symbol_inference(
                        processed_image(),
                        loaded_model(
                            FakeModel(
                                one_result(
                                    xyxy=xyxy,
                                    confidence=confidence,
                                    classes=classes,
                                )
                            )
                        ),
                    ),
                )

    def test_invalid_classes_confidences_and_coordinates_are_rejected(self):
        cases = (
            ("UNKNOWN_MODEL_CLASS", ((1, 1, 2, 2),), (0.5,), (9,)),
            ("INVALID_CLASS_OUTPUT", ((1, 1, 2, 2),), (0.5,), (0.5,)),
            ("INVALID_CLASS_OUTPUT", ((1, 1, 2, 2),), (0.5,), (np.nan,)),
            ("INVALID_CONFIDENCE", ((1, 1, 2, 2),), (-0.1,), (0,)),
            ("INVALID_CONFIDENCE", ((1, 1, 2, 2),), (1.1,), (0,)),
            ("INVALID_CONFIDENCE", ((1, 1, 2, 2),), (np.inf,), (0,)),
            ("INVALID_COORDINATES", ((np.nan, 1, 2, 2),), (0.5,), (0,)),
            ("INVALID_COORDINATES", ((-1, 1, 2, 2),), (0.5,), (0,)),
            ("INVALID_COORDINATES", ((1, 1, 9, 2),), (0.5,), (0,)),
            ("INVALID_COORDINATES", ((2, 1, 1, 2),), (0.5,), (0,)),
            ("INVALID_COORDINATES", ((1, 2, 2, 1),), (0.5,), (0,)),
            ("INVALID_COORDINATES", ((1, 1, 1, 2),), (0.5,), (0,)),
            ("INVALID_COORDINATES", ((1, 1, 2, 1),), (0.5,), (0,)),
        )
        for code, xyxy, confidence, classes in cases:
            with self.subTest(code=code, values=(xyxy, confidence, classes)):
                self.assert_error(
                    code,
                    lambda: run_symbol_inference(
                        processed_image(),
                        loaded_model(
                            FakeModel(
                                one_result(
                                    xyxy=xyxy,
                                    confidence=confidence,
                                    classes=classes,
                                )
                            )
                        ),
                    ),
                )

    def test_more_than_maximum_detections_is_rejected(self):
        boxes = np.tile(np.array([[0.0, 0.0, 1.0, 1.0]]), (301, 1))
        self.assert_error(
            "INVALID_BOX_OUTPUT",
            lambda: run_symbol_inference(
                processed_image(),
                loaded_model(
                    FakeModel(
                        one_result(
                            xyxy=boxes,
                            confidence=np.full(301, 0.1),
                            classes=np.zeros(301),
                        )
                    )
                ),
            ),
        )

    def test_raw_model_errors_are_sanitized(self):
        private_detail = r"C:\Users\private\model.pt CUDA failure"
        error = self.assert_error(
            "INFERENCE_FAILED",
            lambda: run_symbol_inference(
                processed_image(),
                loaded_model(FakeModel(error=RuntimeError(private_detail))),
            ),
        )
        self.assertNotIn(private_detail, str(error))

    def test_inference_uses_no_network_or_output_methods(self):
        model = FakeModel(one_result())
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network used"),
        ), patch("urllib.request.urlopen", side_effect=AssertionError("download used")):
            run_symbol_inference(processed_image(), loaded_model(model))
        for method in (
            model.plot,
            model.save,
            model.show,
            model.export,
            model.train,
            model.track,
        ):
            method.assert_not_called()

    def test_pure_inference_does_not_access_mysql(self):
        with patch(
            "app.core.database.get_engine",
            side_effect=AssertionError("database used"),
        ):
            result = run_symbol_inference(
                processed_image(),
                loaded_model(FakeModel(one_result())),
            )
        self.assertEqual(len(result.predictions), 1)

    def test_application_confidence_setting_is_not_read(self):
        with patch(
            "app.core.config.get_settings",
            side_effect=AssertionError("YOLO_CONFIDENCE_THRESHOLD was read"),
        ):
            result = run_symbol_inference(
                processed_image(),
                loaded_model(FakeModel(one_result(confidence=(0.01,)))),
            )
        self.assertEqual(result.predictions[0].confidence, 0.01)


class ProcessingJobSymbolInferenceTests(unittest.TestCase):
    def setUp(self):
        self.floor_plan = FloorPlan(
            id=10,
            project_floor_id=3,
            original_filename="plan.png",
            storage_path="originals/plan.png",
            mime_type="image/png",
            file_size=100,
            processing_status="processing",
        )
        self.job = ProcessingJob(
            id=20,
            floor_plan_id=10,
            job_type="floor_plan_analysis",
            status="processing",
            progress=55,
            error_message=None,
        )
        self.image = processed_image()
        self.model = loaded_model(FakeModel(one_result()))
        self.session = MagicMock()

    def assert_error(self, code, operation):
        with self.assertRaises(SymbolInferenceError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE)

    def execute(self):
        return run_processing_job_symbol_inference(
            self.session,
            processing_job=self.job,
            floor_plan=self.floor_plan,
            processed_image=self.image,
            loaded_model=self.model,
        )

    def test_success_leaves_job_state_unchanged_and_writes_nothing(self):
        before = (self.job.status, self.job.progress, self.job.error_message)
        result = self.execute()
        self.assertEqual(len(result.predictions), 1)
        self.assertEqual(
            (self.job.status, self.job.progress, self.job.error_message),
            before,
        )
        self.session.add.assert_not_called()
        self.session.commit.assert_not_called()
        self.session.rollback.assert_not_called()

    def test_prediction_failure_persists_only_safe_failure_state(self):
        self.model = loaded_model(
            FakeModel(error=RuntimeError(r"C:\private\model.pt CUDA details"))
        )
        self.assert_error("INFERENCE_FAILED", self.execute)
        self.assertEqual(self.job.status, "failed")
        self.assertEqual(
            self.job.error_message,
            SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE,
        )
        self.assertEqual(self.job.progress, 55)
        self.session.add.assert_called_once_with(self.job)
        self.session.commit.assert_called_once_with()

    def test_model_loader_failure_persists_safe_failure(self):
        def failing_loader():
            raise YOLOModelLoaderError("model_file_missing")

        self.assert_error(
            "INVALID_LOADED_MODEL",
            lambda: run_processing_job_symbol_inference(
                self.session,
                processing_job=self.job,
                floor_plan=self.floor_plan,
                processed_image=self.image,
                model_loader=failing_loader,
            ),
        )
        self.assertEqual(self.job.status, "failed")
        self.assertEqual(self.job.error_message, SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE)
        self.session.commit.assert_called_once_with()

    def test_unexpected_model_loader_failure_is_sanitized_and_persisted(self):
        def failing_loader():
            raise RuntimeError(r"C:\private\weights.pt device details")

        self.assert_error(
            "INVALID_LOADED_MODEL",
            lambda: run_processing_job_symbol_inference(
                self.session,
                processing_job=self.job,
                floor_plan=self.floor_plan,
                processed_image=self.image,
                model_loader=failing_loader,
            ),
        )
        self.assertEqual(self.job.status, "failed")
        self.assertEqual(self.job.error_message, SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE)
        self.session.commit.assert_called_once_with()

    def test_result_conversion_failure_persists_safe_failure(self):
        self.model = loaded_model(
            FakeModel(one_result(classes=(99,)))
        )
        self.assert_error("UNKNOWN_MODEL_CLASS", self.execute)
        self.assertEqual(self.job.status, "failed")
        self.assertEqual(self.job.error_message, SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE)
        self.session.commit.assert_called_once_with()

    def test_failure_persistence_error_rolls_back_and_is_sanitized(self):
        self.model = loaded_model(FakeModel(error=RuntimeError("private failure")))
        self.session.commit.side_effect = RuntimeError("private SQL failure")
        self.assert_error("JOB_FAILURE_PERSISTENCE_FAILED", self.execute)
        self.session.rollback.assert_called_once_with()

    def test_invalid_job_contract_does_not_mutate_or_call_dependencies(self):
        cases = (
            ("id", 0),
            ("floor_plan_id", 99),
            ("job_type", "other"),
            ("status", "queued"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                job = ProcessingJob(
                    id=20,
                    floor_plan_id=10,
                    job_type="floor_plan_analysis",
                    status="processing",
                    progress=55,
                    error_message=None,
                )
                setattr(job, field, value)
                session = MagicMock()
                model_loader = MagicMock(return_value=self.model)
                self.assert_error(
                    "PROCESSING_JOB_INVALID",
                    lambda: run_processing_job_symbol_inference(
                        session,
                        processing_job=job,
                        floor_plan=self.floor_plan,
                        processed_image=self.image,
                        model_loader=model_loader,
                    ),
                )
                self.assertNotEqual(job.status, "failed")
                session.add.assert_not_called()
                session.commit.assert_not_called()
                session.rollback.assert_not_called()
                model_loader.assert_not_called()

    def test_invalid_floor_plan_object_does_not_mutate_job(self):
        self.assert_error(
            "PROCESSING_JOB_INVALID",
            lambda: run_processing_job_symbol_inference(
                self.session,
                processing_job=self.job,
                floor_plan=object(),
                processed_image=self.image,
                loaded_model=self.model,
            ),
        )
        self.assertEqual(self.job.status, "processing")
        self.session.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
