import hashlib
import os
import unittest
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from app.ai.preprocessing.config import (
    PreprocessingConfigurationError,
    PreprocessingParameters,
)
from app.ai.preprocessing.pipeline import (
    ERROR_MESSAGES,
    SAFE_PREPROCESSING_FAILURE_MESSAGE,
    PreprocessingError,
    _cleanup_outputs,
    preprocess_image,
    preprocess_normalized_image,
    preprocess_processing_job_image,
)
from app.services.image_normalization import normalize_image
from app.services.pdf_conversion import convert_pdf_page


def image_bytes(image_format="PNG", size=(20, 12), color=(240, 240, 240)):
    output = BytesIO()
    image = Image.new("RGB", size, color)
    ImageDraw.Draw(image).line((2, 2, size[0] - 3, 2), fill="black", width=1)
    image.save(output, format=image_format)
    image.close()
    return output.getvalue()


def pdf_bytes():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=36)
    writer.write(output)
    return output.getvalue()


def write_file(root, reference, content):
    destination = root.joinpath(*reference.split("/"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return destination


class PreprocessingConfigurationTests(unittest.TestCase):
    def assert_invalid(self, **values):
        with self.assertRaises(PreprocessingConfigurationError) as caught:
            PreprocessingParameters(**values)
        self.assertEqual(caught.exception.code, "INVALID_CONFIGURATION")

    def test_defaults_are_centralized_and_frozen(self):
        parameters = PreprocessingParameters()
        self.assertEqual(parameters.median_kernel_size, 3)
        self.assertTrue(parameters.gaussian_blur_enabled)
        self.assertEqual(parameters.gaussian_kernel_size, 3)
        self.assertEqual(parameters.gaussian_sigma, 0.0)
        self.assertEqual(parameters.threshold_mode, "otsu")
        self.assertEqual(parameters.fixed_threshold, 127)
        self.assertFalse(parameters.invert_binary)
        self.assertFalse(parameters.save_debug_outputs)
        with self.assertRaises(Exception):
            parameters.threshold_mode = "fixed"

    def test_valid_overrides_and_mapping_work(self):
        parameters = PreprocessingParameters.from_mapping(
            {
                "median_kernel_size": 31,
                "gaussian_blur_enabled": False,
                "gaussian_kernel_size": 5,
                "gaussian_sigma": 1.25,
                "threshold_mode": "fixed",
                "fixed_threshold": 0,
                "invert_binary": True,
                "save_debug_outputs": True,
            }
        )
        self.assertEqual(parameters.gaussian_sigma, 1.25)
        self.assertEqual(parameters.fixed_threshold, 0)

    def test_invalid_kernel_values_fail_safely(self):
        for value in (True, 0, -3, 2, 4, 33):
            with self.subTest(value=value):
                self.assert_invalid(median_kernel_size=value)
                self.assert_invalid(gaussian_kernel_size=value)

    def test_invalid_sigma_values_fail_safely(self):
        for value in (True, -0.1, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assert_invalid(gaussian_sigma=value)

    def test_invalid_threshold_values_fail_safely(self):
        for value in (True, -1, 256, 1.5):
            with self.subTest(value=value):
                self.assert_invalid(fixed_threshold=value)
        for mode in ("adaptive", None, ["otsu"]):
            self.assert_invalid(threshold_mode=mode)

    def test_non_boolean_flags_and_unknown_fields_fail_safely(self):
        for name in (
            "gaussian_blur_enabled",
            "invert_binary",
            "save_debug_outputs",
        ):
            self.assert_invalid(**{name: 1})
        self.assert_invalid(unknown_option=True)
        with self.assertRaises(PreprocessingConfigurationError):
            PreprocessingParameters.from_mapping({"surprise": 1})


class PurePreprocessingTests(unittest.TestCase):
    def test_rgb_converts_to_expected_grayscale_and_uint8(self):
        rgb = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
        result = preprocess_image(
            rgb,
            parameters=PreprocessingParameters(gaussian_blur_enabled=False),
        )
        np.testing.assert_array_equal(result.grayscale, [[76, 150, 29]])
        for stage in (result.grayscale, result.denoised, result.thresholded):
            self.assertEqual(stage.dtype, np.uint8)

    def test_every_stage_preserves_dimensions(self):
        result = preprocess_image(np.full((17, 23, 3), 180, dtype=np.uint8))
        self.assertEqual((result.width, result.height), (23, 17))
        for stage in (result.grayscale, result.denoised, result.blurred, result.thresholded):
            self.assertEqual(stage.shape, (17, 23))

    def test_median_filter_removes_isolated_noise(self):
        rgb = np.full((7, 7, 3), 255, dtype=np.uint8)
        rgb[3, 3] = 0
        result = preprocess_image(
            rgb,
            parameters=PreprocessingParameters(gaussian_blur_enabled=False),
        )
        self.assertEqual(result.grayscale[3, 3], 0)
        self.assertEqual(result.denoised[3, 3], 255)

    def test_gaussian_enabled_and_disabled_paths(self):
        rgb = np.arange(75, dtype=np.uint8).reshape(5, 5, 3)
        enabled = preprocess_image(rgb)
        disabled = preprocess_image(
            rgb,
            parameters=PreprocessingParameters(gaussian_blur_enabled=False),
        )
        self.assertTrue(enabled.gaussian_applied)
        self.assertIsNotNone(enabled.blurred)
        self.assertFalse(disabled.gaussian_applied)
        self.assertIsNone(disabled.blurred)

    def test_otsu_records_selected_threshold(self):
        rgb = np.zeros((9, 9, 3), dtype=np.uint8)
        rgb[:, 5:] = 220
        result = preprocess_image(rgb)
        self.assertEqual(result.threshold_mode, "otsu")
        self.assertGreaterEqual(result.actual_threshold, 0)
        self.assertLessEqual(result.actual_threshold, 255)

    def test_fixed_threshold_boundary_behavior(self):
        rgb = np.array([[[127] * 3, [128] * 3]], dtype=np.uint8)
        result = preprocess_image(
            rgb,
            parameters=PreprocessingParameters(
                median_kernel_size=3,
                gaussian_blur_enabled=False,
                threshold_mode="fixed",
                fixed_threshold=127,
            ),
        )
        np.testing.assert_array_equal(result.thresholded, [[0, 255]])
        self.assertEqual(result.actual_threshold, 127.0)

    def test_optional_inversion(self):
        rgb = np.array([[[0] * 3, [255] * 3]], dtype=np.uint8)
        normal = preprocess_image(
            rgb,
            parameters=PreprocessingParameters(gaussian_blur_enabled=False, threshold_mode="fixed"),
        )
        inverted = preprocess_image(
            rgb,
            parameters=PreprocessingParameters(
                gaussian_blur_enabled=False,
                threshold_mode="fixed",
                invert_binary=True,
            ),
        )
        np.testing.assert_array_equal(inverted.thresholded, 255 - normal.thresholded)

    def test_threshold_output_is_strictly_binary(self):
        rng = np.random.default_rng(42)
        result = preprocess_image(rng.integers(0, 256, (31, 19, 3), dtype=np.uint8))
        self.assertTrue(set(np.unique(result.thresholded)).issubset({0, 255}))

    def test_synthetic_line_result_is_deterministic(self):
        rgb = np.full((32, 32, 3), 255, dtype=np.uint8)
        cv2.line(rgb, (4, 16), (27, 16), (0, 0, 0), 2)
        first = preprocess_image(rgb)
        second = preprocess_image(rgb.copy())
        np.testing.assert_array_equal(first.thresholded, second.thresholded)

    def test_invalid_arrays_fail_safely(self):
        cases = (None, np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 2, 4), dtype=np.uint8), np.zeros((2, 2, 3), dtype=np.float32))
        for value in cases:
            with self.subTest(value_type=type(value)):
                with self.assertRaises(PreprocessingError) as caught:
                    preprocess_image(value)
                self.assertEqual(caught.exception.code, "INVALID_PNG_CONTENT")

    def test_stage_failures_are_sanitized(self):
        rgb = np.zeros((5, 5, 3), dtype=np.uint8)
        cases = (
            ("cv2.cvtColor", "GRAYSCALE_FAILED"),
            ("cv2.medianBlur", "DENOISING_FAILED"),
            ("cv2.GaussianBlur", "GAUSSIAN_FAILED"),
            ("cv2.threshold", "THRESHOLD_FAILED"),
        )
        for target, code in cases:
            with self.subTest(code=code), patch(
                f"app.ai.preprocessing.pipeline.{target}",
                side_effect=RuntimeError("private OpenCV detail"),
            ):
                with self.assertRaises(PreprocessingError) as caught:
                    preprocess_image(rgb)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(str(caught.exception), ERROR_MESSAGES[code])


class FilesystemPreprocessingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.uploads = self.root / "uploads"
        self.processed = self.root / "processed"
        self.png = write_file(self.uploads, "originals/plan.png", image_bytes())
        self.normalized = self.normalize(self.png, "image/png", 101)

    def tearDown(self):
        self.temporary.cleanup()

    def normalize(self, source, mime_type, job_id):
        return normalize_image(
            source_path=source,
            source_mime_type=mime_type,
            processed_directory=self.processed,
            floor_plan_id=42,
            processing_job_id=job_id,
        )

    def preprocess(self, source=None, job_id=101, parameters=None):
        return preprocess_normalized_image(
            self.normalized if source is None else source,
            processed_directory=self.processed,
            floor_plan_id=42,
            processing_job_id=job_id,
            parameters=parameters,
        )

    def assert_error(self, code, callable_object):
        with self.assertRaises(PreprocessingError) as caught:
            callable_object()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), ERROR_MESSAGES[code])

    def test_real_g2_jpeg_and_png_results(self):
        jpeg = write_file(self.uploads, "originals/plan.jpg", image_bytes("JPEG"))
        jpeg_result = self.normalize(jpeg, "image/jpeg", 102)
        for source, job_id in ((self.normalized, 101), (jpeg_result, 102)):
            with self.subTest(job_id=job_id):
                result = self.preprocess(source, job_id)
                self.assertEqual((result.width, result.height), (20, 12))
                self.assertEqual(result.source_reference, source.output_reference)

    def test_real_g1_to_g2_pdf_result(self):
        pdf = write_file(self.uploads, "originals/plan.pdf", pdf_bytes())
        g1 = convert_pdf_page(
            source_path=pdf,
            processed_directory=self.processed,
            floor_plan_id=42,
            processing_job_id=103,
        )
        g2 = self.normalize(g1.absolute_output_path, "image/png", 103)
        result = self.preprocess(g2, 103)
        self.assertEqual(result.source_reference, g2.output_reference)

    def test_id_reference_and_dimension_mismatches(self):
        self.assert_error("G2_RESULT_MISMATCH", lambda: self.preprocess(job_id=999))
        self.assert_error(
            "G2_RESULT_MISMATCH",
            lambda: self.preprocess(replace(self.normalized, normalized_width=999)),
        )
        self.assert_error(
            "G2_RESULT_MISMATCH",
            lambda: self.preprocess(replace(self.normalized, output_mime_type="image/jpeg")),
        )

    def test_traversal_absolute_and_missing_sources_fail(self):
        for reference in ("../image.png", str(self.normalized.absolute_output_path)):
            self.assert_error("G2_RESULT_MISMATCH", lambda value=reference: self.preprocess(value))
        missing = replace(self.normalized, absolute_output_path=self.root / "missing.png")
        self.assert_error("G2_RESULT_MISMATCH", lambda: self.preprocess(missing))

    def test_symlink_escape_is_rejected_where_supported(self):
        outside = write_file(self.root, "outside/image.png", image_bytes())
        source = self.normalized.absolute_output_path
        source.unlink()
        try:
            os.symlink(outside, source)
        except OSError:
            self.skipTest("File symlinks are unavailable in this environment.")
        self.assert_error("UNSAFE_SOURCE", lambda: self.preprocess())

    def test_corrupt_disguised_and_non_rgb_png_fail(self):
        source = self.normalized.absolute_output_path
        source.write_bytes(b"not png")
        self.assert_error("INVALID_PNG_CONTENT", lambda: self.preprocess())
        source.write_bytes(b"\x89PNG\r\n\x1a\ncorrupt")
        self.assert_error("DECODE_FAILED", lambda: self.preprocess())
        rgba = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        rgba.save(source, "PNG")
        rgba.close()
        self.assert_error("INVALID_PNG_CONTENT", lambda: self.preprocess())

    def test_unsafe_dimensions_are_rejected(self):
        image = Image.new("RGB", (4097, 1), "white")
        image.save(self.normalized.absolute_output_path, "PNG")
        image.close()
        self.assert_error("UNSAFE_DIMENSIONS", lambda: self.preprocess(self.normalized.output_reference))

    def test_g2_input_hash_remains_unchanged(self):
        before = hashlib.sha256(self.normalized.absolute_output_path.read_bytes()).hexdigest()
        self.preprocess()
        after = hashlib.sha256(self.normalized.absolute_output_path.read_bytes()).hexdigest()
        self.assertEqual(after, before)

    def test_debug_disabled_writes_nothing(self):
        result = self.preprocess()
        self.assertFalse((self.processed / "preprocessed").exists())
        self.assertIsNone(result.grayscale_reference)
        self.assertIsNone(result.thresholded_reference)

    def test_debug_enabled_writes_expected_single_channel_images(self):
        result = self.preprocess(parameters=PreprocessingParameters(save_debug_outputs=True))
        references = (
            result.grayscale_reference,
            result.denoised_reference,
            result.blurred_reference,
            result.thresholded_reference,
        )
        self.assertTrue(all(reference and "\\" not in reference for reference in references))
        for reference in references:
            decoded = cv2.imdecode(
                np.frombuffer(self.processed.joinpath(*reference.split("/")).read_bytes(), np.uint8),
                cv2.IMREAD_UNCHANGED,
            )
            self.assertEqual(decoded.dtype, np.uint8)
            self.assertEqual(decoded.shape, (12, 20))
        np.testing.assert_array_equal(
            cv2.imdecode(
                np.frombuffer(self.processed.joinpath(*result.thresholded_reference.split("/")).read_bytes(), np.uint8),
                cv2.IMREAD_UNCHANGED,
            ),
            result.thresholded,
        )

    def test_no_blurred_file_when_gaussian_is_disabled(self):
        result = self.preprocess(
            parameters=PreprocessingParameters(
                gaussian_blur_enabled=False,
                save_debug_outputs=True,
            )
        )
        self.assertIsNone(result.blurred_reference)
        self.assertFalse(
            (self.processed / "preprocessed/floor-plan-42/job-101/blurred.png").exists()
        )

    def test_existing_debug_file_is_never_overwritten(self):
        destination = self.processed / "preprocessed/floor-plan-42/job-101/grayscale.png"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"keep")
        self.assert_error(
            "OUTPUT_COLLISION",
            lambda: self.preprocess(parameters=PreprocessingParameters(save_debug_outputs=True)),
        )
        self.assertEqual(destination.read_bytes(), b"keep")

    def test_separate_jobs_use_separate_directories(self):
        second_source = write_file(self.uploads, "originals/second.png", image_bytes())
        second = self.normalize(second_source, "image/png", 102)
        parameters = PreprocessingParameters(save_debug_outputs=True)
        first_result = self.preprocess(parameters=parameters)
        second_result = self.preprocess(second, 102, parameters)
        self.assertNotEqual(first_result.thresholded_reference, second_result.thresholded_reference)

    def test_partial_multi_file_failure_receives_cleanup(self):
        real_encode = cv2.imencode
        calls = 0

        def fail_second(*arguments):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("private encoder detail")
            return real_encode(*arguments)

        with patch("app.ai.preprocessing.pipeline.cv2.imencode", side_effect=fail_second):
            self.assert_error(
                "OUTPUT_ENCODING_FAILED",
                lambda: self.preprocess(parameters=PreprocessingParameters(save_debug_outputs=True)),
            )
        output = self.processed / "preprocessed/floor-plan-42/job-101"
        self.assertEqual(list(output.glob("*.png")), [])

    def test_cleanup_errors_are_sanitized(self):
        path = self.root / "partial.png"
        path.write_bytes(b"partial")
        with patch.object(Path, "unlink", side_effect=OSError("private path")):
            self.assert_error("OUTPUT_CLEANUP_FAILED", lambda: _cleanup_outputs([path]))

    def test_filesystem_processing_requires_no_http_or_database(self):
        with patch.dict("sys.modules", {"fastapi": None, "pymysql": None}):
            result = self.preprocess()
        self.assertEqual(result.width, 20)


class ProcessingJobWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = write_file(self.root, "uploads/originals/plan.png", image_bytes())
        self.normalized = normalize_image(
            source_path=source,
            source_mime_type="image/png",
            processed_directory=self.root / "processed",
            floor_plan_id=42,
            processing_job_id=101,
        )
        self.session = MagicMock()
        self.job = SimpleNamespace(
            id=101,
            floor_plan_id=42,
            job_type="floor_plan_analysis",
            status="processing",
            progress=37,
            error_message=None,
        )
        self.floor_plan = SimpleNamespace(id=42)

    def tearDown(self):
        self.temporary.cleanup()

    def run_wrapper(self, **overrides):
        arguments = {
            "processing_job": self.job,
            "floor_plan": self.floor_plan,
            "normalized_source": self.normalized,
            "processed_directory": self.root / "processed",
        }
        arguments.update(overrides)
        return preprocess_processing_job_image(self.session, **arguments)

    def test_success_keeps_processing_and_progress_unchanged(self):
        result = self.run_wrapper()
        self.assertEqual(result.width, 20)
        self.assertEqual(self.job.status, "processing")
        self.assertEqual(self.job.progress, 37)
        self.session.commit.assert_not_called()

    def test_failure_stores_only_safe_message(self):
        self.normalized.absolute_output_path.write_bytes(b"private path SQL secret")
        with self.assertRaises(PreprocessingError):
            self.run_wrapper()
        self.assertEqual(self.job.status, "failed")
        self.assertEqual(self.job.error_message, SAFE_PREPROCESSING_FAILURE_MESSAGE)
        self.session.add.assert_called_once_with(self.job)
        self.session.commit.assert_called_once()

    def test_invalid_job_states_and_identity_are_not_mutated(self):
        cases = (
            {"status": "queued"},
            {"status": "completed"},
            {"job_type": "other"},
            {"floor_plan_id": 999},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                job = SimpleNamespace(**{**self.job.__dict__, **changes})
                with self.assertRaises(PreprocessingError) as caught:
                    self.run_wrapper(processing_job=job)
                self.assertEqual(caught.exception.code, "PROCESSING_JOB_INVALID")
                self.assertEqual(job.status, changes.get("status", "processing"))
        self.session.commit.assert_not_called()

    def test_failure_persistence_errors_are_sanitized_and_rolled_back(self):
        self.normalized.absolute_output_path.write_bytes(b"bad")
        self.session.commit.side_effect = RuntimeError("private SQL detail")
        with self.assertRaises(PreprocessingError) as caught:
            self.run_wrapper()
        self.assertEqual(caught.exception.code, "JOB_FAILURE_PERSISTENCE_FAILED")
        self.session.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
