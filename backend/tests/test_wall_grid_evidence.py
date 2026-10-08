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
    def test_second_corner_recovery_wave_requires_an_independent_anchor(self):
        top = (((40, 40), (460, 40)), 7.)
        left = (((40, 40), (40, 360)), 7.)
        right = (((460, 40), (460, 360)), 7.)
        bottom = (((40, 360), (460, 360)), 7.)
        stub = (((40, 40), (40, 75)), 7.)
        for pending in ([top, left], [left, top]):
            with self.subTest(order=pending[0]):
                self.assertEqual(detector._recover_junction_backed_bands(
                    pending, [right, bottom], 80, 24), [],
                    'Mutually unsupported corner bands cannot approve each other.')
                self.assertEqual(detector._recover_junction_backed_bands(
                    pending, [right, bottom, stub], 80, 24), [top, left])
        self.assertEqual(detector._recover_junction_backed_bands(
            [top, left], [right, bottom, stub]*172, 80, 24), [])

    def test_annotated_fluorescent_boxes_do_not_seed_walls_in_outline_pipeline(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                image = np.full((400, 500), 255, dtype=np.uint8)
                for inset in (0, 6):
                    cv2.rectangle(image, (40+inset, 40+inset), (460-inset, 360-inset), 0, 1)
                for x in (220, 226):
                    cv2.line(image, (x, 46), (x, 354), 0, 1)
                for x, y in ((120, 130), (330, 210)):
                    cv2.rectangle(image, (x-5, y), (x+5, y+48), 0, 1)
                    cv2.putText(image, '2', (x-4, y+17), cv2.FONT_HERSHEY_SIMPLEX, .28, 0, 1)
                    cv2.line(image, (x-40, y+16), (x+40, y+16), 0, 1)
                image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                before = image.copy()
                segments = self.detect(image, scale)
                self.assert_real_structure(segments)
                self.assertFalse(any(abs(a-x)<8 and abs(c-x)<8 and min(b,d)>y-10
                    and max(b,d)<y+60 for a,b,c,d in segments for x,y in ((120,130),(330,210))))
                np.testing.assert_array_equal(image, before)

    def test_compact_annotated_outline_is_not_wall_evidence(self):
        for scale, angle in ((1, 0), (2, 0), (1, 90), (1, 6), (2, 6)):
            with self.subTest(scale=scale, angle=angle):
                image = np.full((400, 500), 255, dtype=np.uint8)
                cv2.rectangle(image, (245, 160), (255, 208), 0, 1)
                cv2.putText(image, '2', (246, 177), cv2.FONT_HERSHEY_SIMPLEX, .28, 0, 1)
                cv2.line(image, (180, 176), (320, 176), 0, 1)
                rotation = cv2.getRotationMatrix2D((250, 200), angle, 1)
                image = cv2.warpAffine(image, rotation, (500, 400), flags=cv2.INTER_NEAREST, borderValue=255)
                image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                endpoints = [rotation @ np.array([250, y, 1]) * scale for y in (160, 208)]
                segment = (*endpoints[0], *endpoints[1], 12*scale)
                before = image.copy()
                self.assertTrue(detector._has_compact_annotated_outline(segment, image))
                np.testing.assert_array_equal(image, before)

    def test_boxed_glyph_guard_preserves_unannotated_and_crossed_hollow_walls(self):
        for scale, angle in ((1, 0), (2, 0), (1, 6), (2, 6)):
            for kind in ('plain', 'two_wire_crossings', 'open_ends', 'long_partition'):
                with self.subTest(scale=scale, angle=angle, kind=kind):
                    image = np.full((400, 500), 255, dtype=np.uint8)
                    end = 320 if kind == 'long_partition' else 208
                    if kind == 'open_ends':
                        for x in (245, 255):
                            cv2.line(image, (x, 160), (x, end), 0, 1)
                    else:
                        cv2.rectangle(image, (245, 160), (255, end), 0, 1)
                    if kind == 'two_wire_crossings':
                        for y in (176, 190):
                            cv2.line(image, (180, y), (320, y), 0, 1)
                    if kind in ('open_ends', 'long_partition'):
                        cv2.putText(image, '2', (246, 177), cv2.FONT_HERSHEY_SIMPLEX, .28, 0, 1)
                    rotation = cv2.getRotationMatrix2D((250, 200), angle, 1)
                    image = cv2.warpAffine(image, rotation, (500, 400), flags=cv2.INTER_NEAREST, borderValue=255)
                    image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                    endpoints = [rotation @ np.array([250, y, 1])*scale for y in (160, end)]
                    before = image.copy()
                    self.assertFalse(detector._has_compact_annotated_outline(
                        (*endpoints[0], *endpoints[1], 12*scale), image))
                    np.testing.assert_array_equal(image, before)

    def test_late_recovery_preserves_unrelated_segments_and_skips_existing_band(self):
        fragment = (43, 140, 43, 200, 7.)
        parallel = (55, 140, 55, 200, 7.)
        transverse = (43, 200, 180, 200, 7.)
        unrelated = (280, 140, 280, 173, 3.)
        segments = [fragment, parallel, transverse, unrelated]
        band = (((43, 40), (43, 360)), 7.)
        recovered = detector._add_verified_outline_bands(segments, [band])
        self.assertEqual(recovered, [parallel, transverse, unrelated, (43, 40, 43, 360, 7.)])
        self.assertEqual(segments, [fragment, parallel, transverse, unrelated])
        self.assertEqual(detector._add_verified_outline_bands(recovered, [band]), recovered)
        reverse = (((43, 360), (43, 40)), 7.)
        self.assertEqual(detector._add_verified_outline_bands(recovered, [reverse]), recovered)

    def test_junction_recovery_does_not_change_mask_width_or_original_votes(self):
        image = np.full((400, 500), 255, dtype=np.uint8)
        for inset in (0, 6):
            cv2.rectangle(image, (40+inset, 40+inset), (460-inset, 360-inset), 0, 1)
        for y in range(46, 349, 30):
            cv2.line(image, (43, y), (43, min(y+20, 354)), 0, 1)
        ink = cv2.bitwise_not(image)
        before = ink.copy()
        parameters = WallDetectionParameters(
            structural_mode=True, minimum_line_length=24, maximum_line_gap=6)
        with patch.object(detector, '_has_two_observed_wall_junctions', return_value=False):
            without = detector._outlined_wall_evidence(ink, parameters)
        with_recovery = detector._outlined_wall_evidence(ink, parameters)
        self.assertTrue(with_recovery[4])
        self.assertFalse(without[4])
        np.testing.assert_array_equal(with_recovery[0], without[0])
        self.assertEqual(with_recovery[1:4], without[1:4])
        np.testing.assert_array_equal(ink, before)

    def test_short_ambiguous_glyph_is_not_grown_into_a_long_wall(self):
        image=np.full((400,500),255,dtype=np.uint8)
        for inset in (0,6):
            cv2.rectangle(image,(40+inset,40+inset),(460-inset,360-inset),0,1)
        for x in (280,286):
            cv2.line(image,(x,140),(x,173),0,1)
        cv2.line(image,(283,140),(283,160),0,1)
        before=image.copy()
        with patch.object(detector,'_extend_observed_pair',wraps=detector._extend_observed_pair) as grow:
            self.detect(image,1)
        for call in grow.call_args_list:
            (start,end),_=call.args[0]
            self.assertGreaterEqual(np.linalg.norm(np.subtract(end,start)),56,
                'Only already-long observed bands may grow; a compact glyph cannot become wall evidence.')
        np.testing.assert_array_equal(image,before)

    def test_junction_recovery_requires_both_endpoint_supports_and_bounded_pool(self):
        pair=(((40,40),(40,360)),7)
        top=(((40,40),(460,40)),7)
        bottom=(((40,360),(460,360)),7)
        middle=(((40,200),(460,200)),7)
        parallel=(((46,40),(46,360)),7)
        self.assertTrue(detector._has_two_observed_wall_junctions(pair,[top,bottom],80))
        for supports in ([],[top],[bottom],[middle],[top,middle],[top,parallel], [top,bottom]*257):
            with self.subTest(supports=len(supports)):
                self.assertFalse(detector._has_two_observed_wall_junctions(pair,supports,80))
        self.assertFalse(detector._has_two_observed_wall_junctions(pair,[top,bottom],400))
        short_top=(((30,40),(70,40)),7)
        short_bottom=(((30,360),(70,360)),7)
        self.assertFalse(detector._has_two_observed_wall_junctions(pair,[short_top,short_bottom],80))
        self.assertTrue(detector._has_two_observed_wall_junctions(
            pair,[short_top,short_bottom],80,minimum_support_span=24))

    def test_observed_pair_extension_stops_at_opening_without_changing_pixels(self):
        for scale in (1,2):
            with self.subTest(scale=scale):
                ink=np.zeros((400,500),dtype=np.uint8)
                for x in (100,106):
                    cv2.line(ink,(x,60),(x,330),255,1)
                ink[180:220,95:112]=0
                ink=cv2.resize(ink,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before=ink.copy()
                nearby=cv2.dilate(ink,np.ones((3,3),dtype=np.uint8))
                pair=(((103*scale,100*scale),(103*scale,160*scale)),6*scale+1)
                (start,end),width=detector._extend_observed_pair(pair,nearby)
                self.assertLessEqual(end[1]/scale,181)
                self.assertGreaterEqual(end[1]/scale,178)
                self.assertLessEqual(start[1]/scale,61)
                self.assertEqual(width,6*scale+1)
                np.testing.assert_array_equal(ink,before)

    def test_center_lane_recovery_does_not_accept_unjoined_or_continuous_wire_bundles(self):
        for scale in (1,2):
            for kind in ('unjoined_intermittent','joined_continuous'):
                with self.subTest(scale=scale,kind=kind):
                    image=np.full((400,500),255,dtype=np.uint8)
                    for inset in (0,6):
                        cv2.rectangle(image,(40+inset,40+inset),(460-inset,360-inset),0,1)
                    low,high=(70,330) if kind=='unjoined_intermittent' else (46,354)
                    for x in (110,122):
                        cv2.line(image,(x,low),(x,high),0,1)
                    if kind=='joined_continuous':
                        cv2.line(image,(116,low),(116,high),0,1)
                    else:
                        for y in range(low,high,30):
                            cv2.line(image,(116,y),(116,min(y+20,high)),0,1)
                    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                    before=image.copy()
                    segments=self.detect(image,scale)
                    self.assertFalse(any(100<a<135 and 100<c<135 for a,b,c,d in segments),
                        'No second junction, or no intermittent cavity: keep wiring out of wall proposals.')
                    np.testing.assert_array_equal(image,before)

    def test_center_hatched_outline_keeps_observed_perimeter_junctions(self):
        for scale, angle in ((1,0),(2,0),(1,6),(2,6)):
            with self.subTest(scale=scale,angle=angle):
                image = np.full((400,500),255,dtype=np.uint8)
                for inset in (0,6):
                    cv2.rectangle(image,(40+inset,40+inset),(460-inset,360-inset),0,1)
                # A center construction/hatch stroke occupies most of the band
                # center, while original pixels retain sustained white cavities.
                for y in range(46,349,30):
                    cv2.line(image,(43,y),(43,min(y+20,354)),0,1)
                rotation = cv2.getRotationMatrix2D((250,200),angle,1)
                image = cv2.warpAffine(image,rotation,(500,400),flags=cv2.INTER_NEAREST,borderValue=255)
                image = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
                before=image.copy()
                result=detect_wall_lines(image,parameters=WallDetectionParameters(
                    structural_mode=True,minimum_line_length=24*scale,maximum_line_gap=6*scale))
                inverse=cv2.invertAffineTransform(rotation)
                endpoints=[(inverse @ np.array([wall.start.x/scale,wall.start.y/scale,1]),
                            inverse @ np.array([wall.end.x/scale,wall.end.y/scale,1]))
                           for wall in result.candidates]
                self.assertTrue(any(max(abs(a[0]-43),abs(b[0]-43))<4
                    and min(a[1],b[1])<55 and max(a[1],b[1])>345 for a,b in endpoints),
                    'Observed white cavities and both wall junctions must retain the full boundary.')
                np.testing.assert_array_equal(image,before)

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
