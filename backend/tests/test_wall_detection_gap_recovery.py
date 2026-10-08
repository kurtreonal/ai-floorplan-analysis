"""Recover original paired ink without projecting through actual openings."""
import cv2
import numpy as np
import pytest
from unittest.mock import patch

from app.ai.wall_detection.config import WallDetectionParameters
from app.ai.wall_detection.detector import (
    _bracketed_pair_hypotheses, _outlined_wall_evidence,
    _recover_bracketed_paired_gaps, detect_wall_lines,
)


def fixture(scale=1, angle=0, opening=None):
    ink = np.zeros((500,500),dtype=np.uint8)
    for x in (240,260):
        cv2.line(ink,(x,40),(x,460),255,2)
    if opening == 'door':
        ink[200:241,235:266] = 0
    elif opening == 'single_mate':
        ink[200:241,238:243] = 0
    rotation = cv2.getRotationMatrix2D((250,250),angle,1)
    ink = cv2.warpAffine(ink,rotation,(500,500),flags=cv2.INTER_NEAREST)
    ink = cv2.resize(ink,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)

    def point(x,y):
        return tuple(np.rint((rotation @ np.array([x,y,1]))*scale).astype(int))

    segments = [(*point(250,40),*point(250,150),21*scale),
                (*point(250,330),*point(250,460),21*scale),
                (*point(380,80),*point(380,400),10*scale)]
    pairs = [((point(250,170),point(250,300)),21*scale)]
    return ink,segments,pairs


@pytest.mark.parametrize('scale,angle',[(1,0),(2,0),(6,0),(1,6),(2,6)])
def test_recovers_only_bracketed_band_and_preserves_unrelated_geometry(scale,angle):
    ink,segments,pairs = fixture(scale,angle)
    original = ink.copy()
    result = _recover_bracketed_paired_gaps(segments,pairs,ink,24*scale)
    assert len(result)==2
    assert segments[2] in result
    assert (*segments[0][:2],*segments[1][2:4],21*scale) in result
    np.testing.assert_array_equal(ink,original)


@pytest.mark.parametrize('opening',['door','single_mate'])
def test_missing_mates_stop_recovery_even_when_hypothesis_brackets_gap(opening):
    ink,segments,pairs = fixture(opening=opening)
    assert _recover_bracketed_paired_gaps(segments,pairs,ink,24)==segments
    assert _recover_bracketed_paired_gaps(segments,[],ink,24)==segments


def test_pairs_cannot_seed_walls_extend_unbracketed_ends_or_join_width_mismatch():
    ink,segments,pairs = fixture()
    assert _recover_bracketed_paired_gaps([],pairs,ink,24)==[]
    assert _recover_bracketed_paired_gaps(segments[:1],pairs,ink,24)==segments[:1]
    wires = [(a,b,c,d,3) for a,b,c,d,_ in segments]
    assert _recover_bracketed_paired_gaps(wires,pairs,ink,24)==wires
    assert _recover_bracketed_paired_gaps(segments,pairs*513,ink,24) is segments


def test_filled_wire_between_same_width_fragments_lacks_white_cavity():
    ink,segments,pairs = fixture()
    cv2.rectangle(ink,(240,150),(260,330),255,-1)
    assert _recover_bracketed_paired_gaps(segments,pairs,ink,24)==segments
    assert _recover_bracketed_paired_gaps(segments,[],ink,24)==segments


def test_endpoint_hypotheses_recover_missing_hough_pair_and_remain_bounded():
    ink,segments,_ = fixture()
    assert len(_recover_bracketed_paired_gaps(segments,[],ink,24))==2
    oversized = segments*171
    assert _recover_bracketed_paired_gaps(oversized,[],ink,24) is oversized
    hypotheses = _bracketed_pair_hypotheses(segments*10,24,200,5)
    assert len(hypotheses)==5
    assert all(0<=v<500 for (a,b),_ in hypotheses for point in (a,b) for v in point)


def test_single_direction_outline_style_recovers_without_reseeding_votes():
    ink,segments,_ = fixture()
    cv2.rectangle(ink,(240,40),(260,150),255,-1)
    cv2.rectangle(ink,(240,330),(260,460),255,-1)
    for y in (180,250,310):
        cv2.line(ink,(300,y),(440,y),255,3)
    parameters = WallDetectionParameters(structural_mode=True,minimum_line_length=24,maximum_line_gap=6)
    assert _outlined_wall_evidence(ink,parameters) is None
    image = cv2.bitwise_not(ink)
    hough = cv2.HoughLinesP
    votes = []
    def capture(raster,*args,**kwargs):
        votes.append(raster.copy())
        return hough(raster,*args,**kwargs)
    with patch('app.ai.wall_detection.detector.cv2.HoughLinesP',side_effect=capture):
        with patch('app.ai.wall_detection.detector._recover_bracketed_paired_gaps',side_effect=lambda s,*_,**__:s):
            baseline = detect_wall_lines(image,parameters=parameters)
        recovered = detect_wall_lines(image,parameters=parameters)
    assert len(votes)%2==0
    half = len(votes)//2
    for before,after in zip(votes[:half],votes[half:]):
        np.testing.assert_array_equal(before,after)
    assert not any(w.start.y<150 and w.end.y>330 for w in baseline.candidates)
    assert any(abs(w.start.x-250)<3 and abs(w.end.x-250)<3
               and w.start.y<150 and w.end.y>330 for w in recovered.candidates)


def test_rejected_compact_fragment_cannot_become_a_longer_wall_anchor():
    ink,_,_ = fixture()
    cv2.rectangle(ink,(240,40),(260,150),255,-1)
    cv2.rectangle(ink,(240,330),(260,460),255,-1)
    image = cv2.bitwise_not(ink)
    # Exercise the established compact-symbol gate independently of its glyph
    # classifier: the first fragment is excluded, so it cannot anchor recovery.
    def reject_compact(segment,_image):
        return min(segment[1],segment[3])<160 and max(segment[1],segment[3])<180
    with patch('app.ai.wall_detection.detector._has_compact_parallel_bars',side_effect=reject_compact):
        result = detect_wall_lines(image,parameters=WallDetectionParameters(
            structural_mode=True,minimum_line_length=24,maximum_line_gap=6))
    assert not any(w.start.y<150 and w.end.y>330 for w in result.candidates)


def test_rejected_long_merge_preserves_both_previously_accepted_anchors():
    ink,segments,pairs = fixture()
    def reject_long(segment):
        return abs(segment[3]-segment[1])<400
    assert all(reject_long(segment) for segment in segments)
    result = _recover_bracketed_paired_gaps(segments,pairs,ink,24,accept_merge=reject_long)
    assert result==segments
