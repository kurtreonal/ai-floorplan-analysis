"""Native outline evidence must survive upload resolution changes."""
import cv2
import numpy as np

from app.ai.wall_detection.config import WallDetectionParameters
from app.ai.wall_detection.detector import _axis_boundary_segments, detect_wall_lines


def hollow_plan(scale):
    image = np.full((400, 500), 255, dtype=np.uint8)
    cv2.rectangle(image, (40, 40), (460, 360), 0, 1)
    cv2.rectangle(image, (46, 46), (454, 354), 0, 1)
    for x in (244, 250):
        cv2.line(image, (x, 46), (x, 354), 0, 1)
    # Deliberately bolder wires and their bounded device glyphs must not take
    # over when wall outline separation exceeds a fixed pixel cutoff.
    for y in (120, 200, 280):
        cv2.line(image, (280, y), (425, y), 0, 3)
        for x in (280, 355, 425):
            cv2.rectangle(image, (x - 4, y - 12), (x + 4, y + 12), 0, 1)
    cv2.line(image, (280, 120), (280, 280), 0, 3)
    cv2.line(image, (430, 120), (430, 335), 0, 3)
    image[180:221, 240:254] = 255  # genuine two-outline door opening
    return cv2.resize(image, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_NEAREST)


def test_hollow_wall_native_resolution_preserves_walls_and_door_without_wiring():
    for scale in (1, 6):
        image = hollow_plan(scale)
        original = image.copy()
        result = detect_wall_lines(image, parameters=WallDetectionParameters(
            structural_mode=True, minimum_line_length=24 * scale,
            maximum_line_gap=6 * scale))
        walls = [(wall.start.x / scale, wall.start.y / scale,
                  wall.end.x / scale, wall.end.y / scale)
                 for wall in result.candidates]
        assert len(walls) >= 6
        partition = []
        for x1, y1, x2, y2 in walls:
            if abs(y1 - y2) <= 3:
                assert min(abs(y1 - y) for y in (43, 357)) < 10
            else:
                assert min(abs(x1 - x) for x in (43, 247, 457)) < 10
                if abs(x1 - 247) < 5 and abs(x2 - 247) < 5:
                    partition.append((y1, y2))
        assert len(partition) >= 2
        assert not any(min(a, b) < 180 and max(a, b) > 220
                       for a, b in partition)
        np.testing.assert_array_equal(image, original)


def test_dense_axis_supplement_is_bounded_and_preserves_white_openings():
    ink = np.full((600, 600), 255, dtype=np.uint8)
    # Separate native runs touch image boundaries but leave an actual opening.
    ink[:, 260:340] = 0
    original = ink.copy()
    proposals = _axis_boundary_segments(ink, 40)
    assert len(proposals) <= 256
    assert proposals == _axis_boundary_segments(ink, 40)
    assert any(x1 == 0 and x2 == 259 for x1, y1, x2, y2 in proposals
               if y1 == y2)
    assert not any(x1 < 260 and x2 >= 340 for x1, y1, x2, y2 in proposals
                   if y1 == y2)
    np.testing.assert_array_equal(ink, original)
