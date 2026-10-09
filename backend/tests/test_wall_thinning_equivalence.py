"""Public synthetic proof that thinning optimizations preserve the old raster contract."""
import unittest

import cv2
import numpy as np

from app.ai.wall_detection.config import WallDetectionError
from app.ai.wall_detection.detector import _thin_connected_strokes


def reference_thinning(mask):
    """Frozen full-frame implementation, including its exact 128-round stopping rule."""
    work = np.pad((mask > 0).astype(np.uint8), 1)
    for _ in range(128):
        changed = False
        for phase in (0, 1):
            center = work[1:-1, 1:-1]
            n = (work[:-2, 1:-1], work[:-2, 2:], work[1:-1, 2:],
                 work[2:, 2:], work[2:, 1:-1], work[2:, :-2],
                 work[1:-1, :-2], work[:-2, :-2])
            neighbors = sum(n)
            transitions = sum(((n[i] == 0) & (n[(i + 1) % 8] == 1)).astype(np.uint8)
                              for i in range(8))
            if phase == 0:
                preserve = (n[0] * n[2] * n[4] == 0) & (n[2] * n[4] * n[6] == 0)
            else:
                preserve = (n[0] * n[2] * n[6] == 0) & (n[0] * n[4] * n[6] == 0)
            remove = (center == 1) & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1) & preserve
            if np.any(remove):
                center[remove] = 0
                changed = True
        if not changed:
            return work[1:-1, 1:-1] * 255
    raise WallDetectionError(
        "THINNING_BUDGET_EXCEEDED", "The wall mask exceeds the bounded thinning budget.",
    )


class WallThinningEquivalenceTests(unittest.TestCase):
    def assert_equivalent(self, mask):
        original = mask.copy()
        expected = reference_thinning(mask)
        actual = _thin_connected_strokes(mask)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(mask, original)
        self.assertEqual(actual.dtype, np.dtype(np.uint8))
        self.assertEqual(actual.shape, mask.shape)
        self.assertTrue(np.isin(actual, (0, 255)).all())

    def test_all_three_by_three_patterns(self):
        for value in range(512):
            with self.subTest(pattern=value):
                mask = np.array([(value >> bit) & 1 for bit in range(9)], np.uint8).reshape(3, 3)
                self.assert_equivalent(mask * 255)

    def test_seeded_random_density_masks(self):
        random = np.random.default_rng(92013)
        shapes = ((9, 12), (41, 35), (96, 83), (31, 127))
        for index in range(200):
            density = random.uniform(0.05, 0.98)
            with self.subTest(index=index, density=density):
                mask = (random.random(shapes[index % len(shapes)]) < density).astype(np.uint8) * 255
                self.assert_equivalent(mask)

    def test_empty_foreground_singleton_and_narrow_frames(self):
        for shape in ((1, 1), (1, 37), (37, 1), (64, 91)):
            for value in (0, 255):
                with self.subTest(shape=shape, value=value):
                    self.assert_equivalent(np.full(shape, value, dtype=np.uint8))

    def test_positive_value_normalization_and_input_preservation(self):
        mask = np.zeros((60, 90), np.uint8)
        cv2.line(mask, (0, 0), (89, 59), 1, 7)
        cv2.rectangle(mask, (8, 9), (69, 51), 1, 5)
        for value in (1, 2, 17, 201, 255):
            with self.subTest(value=value):
                self.assert_equivalent(mask * value)
        self.assert_equivalent(mask.astype(bool))
        self.assert_equivalent(np.where(mask, 3.5, -2.5).astype(np.float32))

    def test_rotated_variable_width_walls_with_openings_and_border_contacts(self):
        mask = np.zeros((160, 160), np.uint8)
        cv2.rectangle(mask, (0, 15), (139, 139), 255, 7)
        cv2.line(mask, (36, 15), (36, 139), 255, 3)
        cv2.line(mask, (36, 79), (139, 79), 255, 15)
        cv2.line(mask, (68, 18), (119, 70), 255, 11)
        mask[70:90, 30:43] = 0
        mask[70:90, 102:125] = 0
        for angle in (0, 17, 45, 90, 135):
            with self.subTest(angle=angle):
                matrix = cv2.getRotationMatrix2D((79.5, 79.5), angle, 1)
                rotated = cv2.warpAffine(mask, matrix, (160, 160), flags=cv2.INTER_NEAREST)
                self.assert_equivalent(rotated)

    def test_disconnected_stable_strokes_survive_shrinking_change_region(self):
        mask = np.zeros((180, 240), np.uint8)
        cv2.line(mask, (0, 0), (60, 0), 255, 1)
        cv2.line(mask, (239, 90), (239, 179), 255, 1)
        cv2.line(mask, (15, 120), (60, 170), 255, 1)
        cv2.rectangle(mask, (130, 10), (210, 100), 255, -1)
        self.assert_equivalent(mask)

    def test_convergence_on_round_128_is_still_accepted(self):
        mask = np.zeros((280, 340), np.uint8)
        mask[10:264, :330] = 255
        self.assert_equivalent(mask)

    def test_changes_on_round_128_still_raise_same_error_without_mutating_input(self):
        for thickness in (256, 258, 300):
            mask = np.zeros((320, 340), np.uint8)
            mask[10:10 + thickness, :330] = 255
            original = mask.copy()
            with self.subTest(thickness=thickness):
                errors = []
                for implementation in (reference_thinning, _thin_connected_strokes):
                    with self.assertRaises(WallDetectionError) as caught:
                        implementation(mask)
                    errors.append((caught.exception.code, caught.exception.message))
                    np.testing.assert_array_equal(mask, original)
                self.assertEqual(errors[0], errors[1])
                self.assertEqual(errors[1][0], "THINNING_BUDGET_EXCEEDED")
