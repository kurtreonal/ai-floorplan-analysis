"""Development template locator contract; synthetic pixels, no private corpus needed."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from app.ai.floor_plan_interpretation.experimental_pull_station import (
    ExperimentalLocatorUnavailable, SOURCE_SHA256, THRESHOLD, TEMPLATES,
    configuration_sha256, locate, source_digest, with_pull_station_proposals,
)


class ExperimentalPullStationTests(TestCase):
    def test_frozen_identity_and_threshold(self):
        self.assertEqual(THRESHOLD, 0.60)
        self.assertEqual(len(TEMPLATES), 2)
        self.assertEqual(len(configuration_sha256()), 64)
        with TemporaryDirectory() as directory:
            source = Path(directory) / "wrong.jpg"
            source.write_bytes(b"different")
            with self.assertRaises(ExperimentalLocatorUnavailable):
                source_digest(source)
            self.assertEqual(source.read_bytes(), b"different")

    def test_native_pixel_proposal_and_immutable_page(self):
        rng = np.random.default_rng(17)
        template_page = np.full((3264, 2164), 255, dtype=np.uint8)
        patch_a = rng.integers(30, 220, size=(28, 28), dtype=np.uint8)
        patch_b = rng.integers(30, 220, size=(29, 28), dtype=np.uint8)
        x0, y0, x1, y1 = TEMPLATES[0][1]
        template_page[y0:y1, x0:x1] = patch_a
        x0, y0, x1, y1 = TEMPLATES[1][1]
        template_page[y0:y1, x0:x1] = patch_b
        target = np.full((200, 200, 3), 255, dtype=np.uint8)
        target[61:89, 41:69] = cv2.cvtColor(patch_a, cv2.COLOR_GRAY2RGB)
        original = target.copy()
        with patch("app.ai.floor_plan_interpretation.experimental_pull_station.source_digest", return_value=SOURCE_SHA256), \
             patch("app.ai.floor_plan_interpretation.experimental_pull_station.cv2.imread", return_value=template_page):
            matches = locate(target, Path("synthetic.jpg"))
        self.assertTrue(any(item["bbox"] == (41, 61, 69, 89) for item in matches))
        np.testing.assert_array_equal(target, original)
        payload = with_pull_station_proposals(interpret_floor_plan_demo(target), matches)
        self.assertIsInstance(payload, FloorPlanInterpretationPayload)
        self.assertEqual(len(payload.symbols.items), len(matches))
        self.assertTrue(all(item.mapping_state == "unknown" and item.catalog_class_id is None
                            for item in payload.symbols.items))
        self.assertTrue(all(item.evidence_refs == ("region:region-0002",)
                            for item in payload.symbols.items))
        self.assertEqual(payload.regions[-1].bounds.width, 200)
        self.assertTrue(any("not calibrated confidence" in warning.message for warning in payload.warnings))

    def test_excludes_unbounded_or_invalid_images(self):
        with patch("app.ai.floor_plan_interpretation.experimental_pull_station.source_digest", return_value=SOURCE_SHA256):
            with self.assertRaises(ExperimentalLocatorUnavailable):
                locate(np.zeros((4097, 20, 3), dtype=np.uint8), Path("synthetic.jpg"))
