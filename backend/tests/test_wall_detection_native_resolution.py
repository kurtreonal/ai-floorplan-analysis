"""Native outline evidence must survive upload resolution changes."""
import cv2
import numpy as np

from app.ai.wall_detection.config import WallDetectionParameters
from app.ai.wall_detection.detector import _axis_boundary_segments, _has_repeated_band_ties, _has_tied_axis_band, detect_wall_lines


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


def test_subdivided_hollow_band_requires_distributed_original_ties_not_end_caps():
    for scale in (1, 3):
        ink = np.zeros((400,500),dtype=np.uint8)
        for y in (100,106,112):
            cv2.line(ink,(40,y),(460,y),255,1)
        pair = (((40*scale,106*scale),(460*scale,106*scale)),13*scale)
        def qualifies():
            raster = cv2.resize(ink,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
            before = raster.copy()
            answer = _has_repeated_band_ties(pair,raster,24*scale)
            np.testing.assert_array_equal(raster,before)
            return answer
        assert not qualifies()  # plain three-wire bundle
        for x in (40,460):
            cv2.line(ink,(x,100),(x,112),255,1)
        assert not qualifies()  # closed long bundle/glyph: only two caps
        cv2.line(ink,(250,100),(250,112),255,1)
        assert qualifies()
        # Clustered crossings do not establish a distributed wall band.
        ink[:,250] = 0
        for x in (48,56,64):
            cv2.line(ink,(x,100),(x,112),255,1)
        assert not qualifies()


def test_balanced_voting_requires_tied_bands_in_both_directions():
    ink = np.zeros((400,500),dtype=np.uint8)
    for y in (100,106,112):
        cv2.line(ink,(40,y),(460,y),255,1)
    for x in (40,250,460):
        cv2.line(ink,(x,100),(x,112),255,1)
    assert not _has_tied_axis_band(_axis_boundary_segments(ink,24),ink,24)
    for x in (300,306,312):
        cv2.line(ink,(x,40),(x,360),255,1)
    for y in (40,200,360):
        cv2.line(ink,(300,y),(312,y),255,1)
    assert _has_tied_axis_band(_axis_boundary_segments(ink,24),ink,24)


def test_cross_tied_hollow_perimeter_is_complete_without_frame_or_circuit_walls():
    for scale in (1,2):
        ink = np.zeros((400,500),dtype=np.uint8)
        for inset in (0,6,12):
            cv2.rectangle(ink,(40+inset,40+inset),(460-inset,360-inset),255,1)
        for x in (100,250,400):
            for top,bottom in ((40,52),(348,360)):
                cv2.line(ink,(x,top),(x,bottom),255,1)
        for y in (80,200,320):
            for left,right in ((40,52),(448,460)):
                cv2.line(ink,(left,y),(right,y),255,1)
        # Detached parallel page rules bracket the joined building network.
        for y in (10,16,380,386):
            cv2.line(ink,(20,y),(480,y),255,1)
        for y in (120,200,280):
            for x in range(90,400,35):
                cv2.line(ink,(x,y),(x+20,y),255,3)
        image = cv2.bitwise_not(cv2.resize(ink,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST))
        before = image.copy()
        result = detect_wall_lines(image,parameters=WallDetectionParameters(
            structural_mode=True,minimum_line_length=24*scale,maximum_line_gap=6*scale))
        walls = [(np.array([w.start.x,w.start.y])/scale,np.array([w.end.x,w.end.y])/scale) for w in result.candidates]
        def distance(point,a,b):
            delta = b-a
            t = np.clip(np.dot(point-a,delta)/np.dot(delta,delta),0,1)
            return np.linalg.norm(point-a-t*delta)
        references = [((46,46),(454,46)),((46,354),(454,354)),((46,46),(46,354)),((454,46),(454,354))]
        for a,b in references:
            points = np.linspace(a,b,100)
            assert np.mean([min(distance(p,c,d) for c,d in walls)<10 for p in points])>=.95
        assert all(30<=a[1]<=370 and 30<=b[1]<=370 for a,b in walls), (scale,[(a.tolist(),b.tolist()) for a,b in walls])
        assert not any(abs(a[1]-b[1])<3 and 110<a[1]<290 for a,b in walls)
        np.testing.assert_array_equal(image,before)
