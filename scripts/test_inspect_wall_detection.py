"""Diagnostics must observe inference, not alter it or its source pixels."""
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from inspect_wall_detection import demo_cv, detector, trace_wall_evidence, interpret_historical, main


class WallEvidenceTraceTests(unittest.TestCase):
    def test_thin_vote_replay_forwards_new_paired_evidence_arguments(self):
        source = np.full((400, 500, 3), 255, dtype=np.uint8)
        for inset in (0, 6):
            cv2.rectangle(source, (40+inset, 40+inset), (460-inset, 360-inset), (0,0,0), 1)
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'storage') as directory:
            source_path = Path(directory) / 'source.png'
            output = Path(directory) / 'replay'
            cv2.imwrite(str(source_path), source)
            original = source_path.read_bytes()
            with patch('sys.argv', ['inspect_wall_detection', str(source_path), str(output), '--thin-outline-votes']), redirect_stdout(StringIO()):
                main()
            self.assertTrue((output / 'report.json').exists())
            self.assertEqual(source_path.read_bytes(), original)

    def test_historical_scope_support_is_forwarded_explicitly(self):
        source = np.full((40, 50, 3), 255, dtype=np.uint8)
        calls = []
        def scoped(image, *, selected_drawing=False):
            self.assertIs(image,source)
            calls.append(selected_drawing)
            return selected_drawing
        self.assertTrue(interpret_historical(scoped,source,selected_drawing=True))
        self.assertFalse(interpret_historical(scoped,source,selected_drawing=False))
        self.assertEqual(calls,[True,False])

    def test_pre_scope_historical_version_retains_original_signature(self):
        source = np.full((40, 50, 3), 255, dtype=np.uint8)
        before = source.copy()
        def legacy(image):
            self.assertIs(image,source)
            return 'legacy'
        self.assertEqual(interpret_historical(legacy,source,selected_drawing=True),'legacy')
        np.testing.assert_array_equal(source,before)

    def test_trace_preserves_exact_result_and_source(self):
        source = np.full((400, 500, 3), 255, dtype=np.uint8)
        for inset in (0, 6):
            cv2.rectangle(source, (40+inset, 40+inset), (460-inset, 360-inset), (0,0,0), 1)
        before = source.copy()
        expected = demo_cv.interpret_floor_plan_demo(source)
        actual, trace = trace_wall_evidence(source, demo_cv.interpret_floor_plan_demo)
        self.assertEqual(actual.model_dump(), expected.model_dump())
        np.testing.assert_array_equal(source, before)
        self.assertEqual(trace['style'], 'paired_outline')
        self.assertTrue(trace['pairs'])
        self.assertLessEqual(len(trace['segment_profiles']), 256)

    def test_segment_trace_is_bounded_and_does_not_override_rejection(self):
        source = np.full((400, 500), 255, dtype=np.uint8)
        for y in (94,100,106):
            cv2.line(source, (100,y), (130,y), 0, 1)
        before = source.copy()
        segment = (100,100,130,100,7)
        expected = detector._has_compact_parallel_bars(segment, source)

        def repeated_probe(_source):
            return [detector._has_compact_parallel_bars(segment, source) for _ in range(300)]

        actual, trace = trace_wall_evidence(source, repeated_probe)
        self.assertEqual(actual, [expected]*300)
        self.assertEqual(len(trace['segment_profiles']), 256)
        self.assertTrue(all(p['compact_rejected'] for p in trace['segment_profiles']))
        np.testing.assert_array_equal(source, before)


if __name__ == '__main__':
    unittest.main()
