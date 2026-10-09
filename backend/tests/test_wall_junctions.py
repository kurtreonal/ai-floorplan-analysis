import unittest

import cv2
import numpy as np

from app.ai.wall_detection.junctions import snap_observed_junctions


class ObservedWallJunctionTests(unittest.TestCase):
    def test_solid_t_junction_connects_existing_wall_without_new_geometry(self):
        ink = np.zeros((240, 320), np.uint8)
        cv2.line(ink, (30, 100), (100, 100), 255, 8)
        cv2.line(ink, (100, 30), (100, 180), 255, 8)
        before = [(30, 100, 95, 100, 8.), (100, 30, 100, 180, 8.)]
        original = ink.copy()
        result = snap_observed_junctions(before, ink, 6)
        self.assertEqual(result, [(30, 100, 100, 100, 8.), before[1]])
        self.assertEqual(before[0][2], 95)
        np.testing.assert_array_equal(ink, original)
        self.assertEqual(snap_observed_junctions(result, ink, 6), result)

    def test_hollow_t_junction_uses_both_original_mates(self):
        ink = np.zeros((240, 320), np.uint8)
        for y in (95, 104):
            cv2.line(ink, (30, y), (100, y), 255, 1)
        for x in (95, 104):
            cv2.line(ink, (x, 30), (x, 180), 255, 1)
        before = [(30, 100, 95, 100, 10.), (100, 30, 100, 180, 10.)]
        self.assertEqual(snap_observed_junctions(before, ink, 6)[0], (30, 100, 100, 100, 10.))

    def test_both_truncated_corner_ends_need_independent_original_wall_support(self):
        for hollow in (False, True):
            with self.subTest(hollow=hollow):
                ink = np.zeros((240, 320), np.uint8)
                if hollow:
                    for y in (95,104):
                        cv2.line(ink,(30,y),(104,y),255,1)
                    for x in (95,104):
                        cv2.line(ink,(x,30),(x,104),255,1)
                    thickness=10.
                else:
                    cv2.line(ink,(30,100),(100,100),255,8)
                    cv2.line(ink,(100,30),(100,100),255,8)
                    thickness=8.
                before=[(30,100,95,100,thickness),(100,30,100,95,thickness)]
                expected=[(30,100,100,100,thickness),(100,30,100,100,thickness)]
                self.assertEqual(snap_observed_junctions(before,ink,6),expected)
                ink[91:110,91:110]=0
                self.assertEqual(snap_observed_junctions(before,ink,6),before)

    def test_blank_gap_and_missing_mate_are_not_filled(self):
        for hollow in (False, True):
            ink = np.zeros((240, 320), np.uint8)
            if hollow:
                cv2.line(ink, (30, 95), (100, 95), 255, 1)
                cv2.line(ink, (95, 30), (95, 180), 255, 1)
                cv2.line(ink, (104, 30), (104, 180), 255, 1)
                thickness = 10.
            else:
                cv2.line(ink, (30, 100), (100, 100), 255, 8)
                cv2.line(ink, (100, 30), (100, 180), 255, 8)
                ink[90:111, 94:100] = 0
                thickness = 8.
            before = [(30, 100, 95, 100, thickness), (100, 30, 100, 180, thickness)]
            self.assertEqual(snap_observed_junctions(before, ink, 6), before)

    def test_two_ended_solid_corner_at_multiple_rotations_and_resolutions(self):
        for scale in (.5,1.,2.):
            for angle in (0,3,6):
                with self.subTest(scale=scale,angle=angle):
                    transform=cv2.getRotationMatrix2D((0,0),angle,scale)
                    transform[:,2]+=(30,30)
                    def point(x,y):
                        return transform @ np.array([x,y,1.])
                    ink=np.zeros((550,700),np.uint8)
                    width=12*scale
                    for start in ((30,100),(100,30)):
                        cv2.line(ink,tuple(np.rint(point(*start)).astype(int)),
                                 tuple(np.rint(point(100,100)).astype(int)),255,round(width))
                    rows=[(*point(30,100),*point(95,100),width),
                          (*point(100,30),*point(100,95),width)]
                    result=snap_observed_junctions(rows,ink,6*scale)
                    for row in result:
                        self.assertLessEqual(np.linalg.norm(np.array(row[2:4])-point(100,100)),1.)

    def test_dimension_or_wiring_stroke_cannot_anchor_extension(self):
        ink = np.zeros((240, 320), np.uint8)
        cv2.line(ink, (30, 100), (100, 100), 255, 1)
        cv2.line(ink, (100, 30), (100, 180), 255, 1)
        before = [(30, 100, 95, 100, 8.), (100, 30, 100, 180, 8.)]
        self.assertEqual(snap_observed_junctions(before, ink, 6), before)

    def test_collinear_doorway_and_distant_or_unbracketed_end_preserved(self):
        ink = np.full((240, 320), 255, np.uint8)
        cases = [ [(30, 100, 95, 100, 8.), (105, 100, 180, 100, 8.)],
                  [(30, 100, 80, 100, 8.), (100, 30, 100, 180, 8.)],
                  [(30, 100, 95, 100, 8.), (100, 125, 100, 180, 8.)] ]
        for before in cases:
            with self.subTest(before=before):
                self.assertEqual(snap_observed_junctions(before, ink, 6), before)

    def test_budget_and_empty_input_do_not_rewrite_walls(self):
        ink = np.zeros((64, 64), np.uint8)
        self.assertEqual(snap_observed_junctions([], ink, 6), [])
        rows = [(10, 10, 30, 10, 8.)] * 513
        self.assertEqual(snap_observed_junctions(rows, ink, 6), rows)

    def test_thick_hatch_block_is_not_a_linear_wall_anchor(self):
        ink = np.full((240, 320), 255, np.uint8)
        for rows in (
            [(30, 100, 95, 100, 30.), (100, 30, 100, 180, 8.)],
            [(30, 100, 95, 100, 8.), (100, 80, 100, 120, 30.)],
        ):
            with self.subTest(rows=rows):
                self.assertEqual(snap_observed_junctions(rows, ink, 6), rows)

    def test_rotation_and_resolution_preserve_supported_junctions_and_openings(self):
        # Render native-resolution strokes rather than downsampling a one-pixel
        # outline away. Coordinates and widths share the same affine transform.
        for scale in (.5, 1., 2.):
            for angle in (0, 3, 6):
                for hollow in (False, True):
                    with self.subTest(scale=scale, angle=angle, hollow=hollow):
                        transform = cv2.getRotationMatrix2D((0, 0), angle, scale)
                        transform[:, 2] += (30, 30)
                        def point(x, y):
                            return tuple(transform @ np.array([x, y, 1.]))
                        image = np.zeros((550, 700), np.uint8)
                        def line(start, end, width):
                            cv2.line(image, tuple(np.rint(point(*start)).astype(int)),
                                     tuple(np.rint(point(*end)).astype(int)), 255, width)
                        center = 99.5 if hollow else 100.
                        thickness = 9 * scale + 1 if hollow else 12 * scale
                        if hollow:
                            for y in (95, 104):
                                line((30, y), (center, y), 1)
                            for x in (95, 104):
                                line((x, 30), (x, 180), 1)
                        else:
                            line((30, center), (center, center), round(thickness))
                            line((center, 30), (center, 180), round(thickness))
                        before = [(*point(30, center), *point(center-5, center), thickness),
                                  (*point(center, 30), *point(center, 180), thickness)]
                        result = snap_observed_junctions(before, image, 6 * scale)
                        self.assertLessEqual(np.linalg.norm(np.array(result[0][2:4]) - point(center, center)), 1.)
                        # Clear a genuine opening wider than the 3x3 ink tolerance.
                        opened = image.copy()
                        polygon = np.rint([point(x,y) for x,y in ((84,88),(97,88),(97,112),(84,112))]).astype(int)
                        cv2.fillPoly(opened, [polygon], 0)
                        unchanged = snap_observed_junctions(before, opened, 6 * scale)
                        self.assertLessEqual(np.linalg.norm(np.array(unchanged[0][2:4]) - point(center-5, center)), 1.)


if __name__ == '__main__':
    unittest.main()
