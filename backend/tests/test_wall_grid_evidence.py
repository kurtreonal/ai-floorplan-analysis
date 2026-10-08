"""Database-independent ceiling evidence regressions; no source-specific rules."""
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.ai.wall_detection.config import WallDetectionParameters
from app.ai.wall_detection.detector import detect_wall_lines, _has_compact_parallel_bars
from app.ai.wall_detection import detector


def outlined_ceiling_plan(*, troffer_bars=False, scale=1):
    image = np.full((400,500),255,dtype=np.uint8)
    for inset in (0,6):
        cv2.rectangle(image,(40+inset,40+inset),(460-inset,360-inset),0,1)
    for x in range(80,441,40):
        cv2.line(image,(x,46),(x,354),0,1)
    for y in range(80,341,40):
        cv2.line(image,(46,y),(454,y),0,1)
    # An actual double-outline partition, not another ceiling-grid member.
    for x in (220,226):
        cv2.line(image,(x,46),(x,354),0,1)
    if troffer_bars:
        for x,y in ((120,120),(280,200),(360,280)):
            for offset in (-6,0,6):
                cv2.line(image,(x-25,y+offset),(x+25,y+offset),0,1)
    return cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)


class CeilingGridEvidenceTests(unittest.TestCase):
    def test_compact_five_bar_fixture_keeps_one_pixel_scan_companions(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                image = np.full((1000, 1000), 255, dtype=np.uint8)
                for y, width in ((170,3),(182,1),(194,16),(210,2),(220,3)):
                    cv2.line(image, (100,y), (198,y), 0, width)
                image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before = image.copy()
                self.assertTrue(_has_compact_parallel_bars(
                    tuple(value*scale for value in (100,200,198,200,34)), image))
                np.testing.assert_array_equal(image,before)

    def test_compact_five_bar_fixture_does_not_depend_on_ten_percent_page_cutoff(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                image = np.full((1000, 1000), 255, dtype=np.uint8)
                for y, width in ((177,3),(188,2),(200,17),(212,2),(223,3)):
                    cv2.line(image, (100,y), (240,y), 0, width)
                image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before = image.copy()
                self.assertTrue(_has_compact_parallel_bars(
                    tuple(value*scale for value in (100,200,240,200,42)), image))
                self.assertFalse(_has_compact_parallel_bars(
                    tuple(value*scale for value in (100,200,240,200,12)), image),
                    'A long narrow partition is not a compact fixture body.')
                np.testing.assert_array_equal(image,before)

    def test_sparse_outline_votes_are_unchanged(self):
        ink = cv2.bitwise_not(outlined_ceiling_plan())
        before = ink.copy()
        with patch.object(cv2, 'HoughLinesP', wraps=cv2.HoughLinesP) as vote:
            evidence = detector._outlined_wall_evidence(ink, WallDetectionParameters(
                structural_mode=True,minimum_line_length=24,maximum_line_gap=6))
        self.assertIsNotNone(evidence)
        self.assertEqual(vote.call_count, 1)
        np.testing.assert_array_equal(vote.call_args.args[0], before)
        np.testing.assert_array_equal(ink, before)

    def test_dense_outline_retry_uses_boundaries_but_original_pixel_evidence(self):
        ink = cv2.bitwise_not(outlined_ceiling_plan())
        before = ink.copy()
        hough = cv2.HoughLinesP
        calls = []
        def dense_votes(raster, *args, **kwargs):
            calls.append(raster.copy())
            if len(calls) == 1:
                return np.array([[[40+i%10,40+i//10,460-i//10,40+i//10]]
                                 for i in range(260)],dtype=np.int32)
            return hough(raster,*args,**kwargs)
        with patch.object(cv2, 'HoughLinesP', side_effect=dense_votes):
            evidence = detector._outlined_wall_evidence(ink, WallDetectionParameters(
                structural_mode=True,minimum_line_length=24,maximum_line_gap=6))
        self.assertIsNotNone(evidence)
        self.assertEqual(len(calls), 2)
        np.testing.assert_array_equal(calls[0], before)
        self.assertLess(np.count_nonzero(calls[1]), np.count_nonzero(before))
        np.testing.assert_array_equal(ink, before)

    def detect(self,image,scale):
        result = detect_wall_lines(image,parameters=WallDetectionParameters(
            structural_mode=True,minimum_line_length=24*scale,maximum_line_gap=6*scale))
        return [tuple(value/scale for value in (wall.start.x,wall.start.y,wall.end.x,wall.end.y))
                for wall in result.candidates]

    def assert_real_structure(self,segments):
        self.assertTrue(any(abs(a-223)<3 and abs(c-223)<3 and b<55 and d>345
                            for a,b,c,d in segments),'The real full-height partition must survive.')
        for y in (43,357):
            self.assertTrue(any(abs(b-y)<4 and abs(d-y)<4 and min(a,c)<55 and max(a,c)>445
                                for a,b,c,d in segments),'Outlined horizontal perimeter must survive.')
        for x in (43,457):
            self.assertTrue(any(abs(a-x)<4 and abs(c-x)<4 and min(b,d)<55 and max(b,d)>345
                                for a,b,c,d in segments),'Outlined vertical perimeter must survive.')

    def test_fine_crossing_ceiling_grid_keeps_perimeter_and_real_partition(self):
        for scale in (1,2):
            with self.subTest(scale=scale):
                image = outlined_ceiling_plan(scale=scale)
                before = image.copy()
                segments = self.detect(image,scale)
                self.assert_real_structure(segments)
                self.assertEqual(len(segments),5)
                np.testing.assert_array_equal(image,before)

    def test_five_thin_parallel_wires_do_not_become_one_thick_wall(self):
        for scale, pitch in ((1,3),(1,6),(2,3),(2,6)):
            with self.subTest(scale=scale,pitch=pitch):
                image = np.full((400,500),255,dtype=np.uint8)
                for inset in (0,6):
                    cv2.rectangle(image,(40+inset,40+inset),(460-inset,360-inset),0,1)
                for x in (220,226):
                    cv2.line(image,(x,46),(x,354),0,1)
                cv2.line(image,(170,46),(170,354),0,7)
                for offset in (-2*pitch,-pitch,0,pitch,2*pitch):
                    cv2.line(image,(260,160+offset),(380,160+offset),0,1)
                image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before = image.copy()
                segments = self.detect(image,scale)
                self.assert_real_structure(segments)
                self.assertTrue(any(abs(a-170)<3 and abs(c-170)<3 and b<55 and d>345
                                    for a,b,c,d in segments),'A real solid partition must survive.')
                np.testing.assert_array_equal(image,before)
                false_wires = [(a,b,c,d) for a,b,c,d in segments
                               if min(a,c)>240 and max(a,c)<400 and min(b,d)>130 and max(b,d)<190]
                self.assertEqual(false_wires,[],
                    'Five separate thin wire strokes must not form a filled structural wall.')

    def test_compact_bar_guard_rejects_three_equal_thin_bars(self):
        for scale in (1,2):
            with self.subTest(scale=scale):
                image = np.full((400,500),255,dtype=np.uint8)
                for y in (94,100,106):
                    cv2.line(image,(100,y),(130,y),0,1)
                image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before = image.copy()
                rejected = _has_compact_parallel_bars(tuple(value*scale for value in (100,100,130,100,7)),image)
                np.testing.assert_array_equal(image,before)
                self.assertTrue(rejected,'Three compact equal thin bars are fixture evidence.')

    def test_compact_bar_guard_preserves_short_double_outline_and_solid_walls(self):
        for scale in (1,2):
            for kind in ('outlined','solid'):
                with self.subTest(scale=scale,kind=kind):
                    image = np.full((400,500),255,dtype=np.uint8)
                    if kind=='outlined':
                        for y in (97,103):
                            cv2.line(image,(100,y),(130,y),0,1)
                    else:
                        cv2.line(image,(100,100),(130,100),0,7)
                    image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                    before = image.copy()
                    self.assertFalse(_has_compact_parallel_bars(
                        tuple(value*scale for value in (100,100,130,100,7)),image))
                    np.testing.assert_array_equal(image,before)

    def test_compact_bold_fixture_with_one_thin_outline_each_side(self):
        for scale in (1,2):
            with self.subTest(scale=scale):
                image = np.full((1000,1000),255,dtype=np.uint8)
                cv2.rectangle(image,(100,191),(180,210),0,-1)
                for y in (187,214):
                    cv2.line(image,(100,y),(180,y),0,2)
                image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before = image.copy()
                self.assertTrue(_has_compact_parallel_bars(
                    tuple(value*scale for value in (100,200,180,200,30)),image))
                self.assertFalse(_has_compact_parallel_bars(
                    tuple(value*scale for value in (100,200,500,200,30)),image))
                np.testing.assert_array_equal(image,before)

    def test_compact_three_thin_troffer_bars_do_not_seed_interior_walls(self):
        for scale in (1,2):
            with self.subTest(scale=scale):
                image = outlined_ceiling_plan(troffer_bars=True,scale=scale)
                before = image.copy()
                segments = self.detect(image,scale)
                self.assert_real_structure(segments)
                false_interior = [(a,b,c,d) for a,b,c,d in segments
                    if 60<min(a,c) and max(a,c)<440 and 60<min(b,d) and max(b,d)<340
                    and not (abs(a-223)<3 and abs(c-223)<3)]
                self.assertEqual(false_interior,[],
                    'Compact repeated fixture bars are not structural partitions.')
                np.testing.assert_array_equal(image,before)
