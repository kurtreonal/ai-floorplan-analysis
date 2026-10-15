import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.automatic_wiring import (
    with_automatic_wiring, with_fixture_wall_conflicts, _near_port,
    _regular_dash_evidence, _dash_direction_evidence,
)
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo


def example(*, gap=False, wall=False):
    image = np.full((200, 320, 3), 255, np.uint8)
    payload = interpret_floor_plan_demo(image, selected_drawing=True).model_dump(mode='json')
    for index, x in enumerate((60, 260), 1):
        cv2.rectangle(image, (x - 8, 88), (x + 8, 112), (0, 0, 0), 2)
        payload['symbols']['items'].append({
            'id': f'symbol-{index:04d}', 'mapping_state': 'unknown', 'catalog_class_id': None,
            'observed_label': 'unresolved device', 'center': {'x': x, 'y': 100},
            'bounds': {'x': x - 8, 'y': 88, 'width': 16, 'height': 24},
            'orientation_degrees': None, 'evidence_refs': ['region:region-0001'], 'ambiguity': 'ambiguous',
        })
    payload['symbols']['state'] = 'completed'
    cv2.line(image, (68, 100), (252, 100), (0, 0, 0), 2)
    if gap:
        image[:, 150:170] = 255
    if wall:
        payload['walls'] = {'state': 'completed', 'items': [{
            'id': 'wall-0001', 'start': {'x': 68, 'y': 100}, 'end': {'x': 252, 'y': 100},
            'evidence_refs': ['region:region-0001'], 'ambiguity': 'ambiguous',
        }], 'truncated': False}
    return image, FloorPlanInterpretationPayload.model_validate(payload)


class AutomaticWiringTests(unittest.TestCase):
    def test_three_repeated_furniture_fragments_are_insufficient_dash_evidence(self):
        for scale in (1,2,3):
            with self.subTest(scale=scale):
                three=np.tile(np.r_[np.ones(10*scale,bool),np.zeros(6*scale,bool)],3)
                four=np.tile(np.r_[np.ones(10*scale,bool),np.zeros(6*scale,bool)],4)
                self.assertFalse(_regular_dash_evidence(three,24*scale))
                self.assertTrue(_regular_dash_evidence(four,24*scale))

    def test_periodic_prefix_cannot_license_a_long_continuous_furniture_tail(self):
        for scale in (1,2,3):
            with self.subTest(scale=scale):
                tail=np.r_[np.tile(np.r_[np.ones(10*scale,bool),np.zeros(6*scale,bool)],3),np.ones(100*scale,bool)]
                clipped=np.r_[np.ones(3*scale,bool),np.zeros(6*scale,bool),
                    np.tile(np.r_[np.ones(10*scale,bool),np.zeros(6*scale,bool)],3),np.ones(2*scale,bool)]
                self.assertFalse(_regular_dash_evidence(tail,24*scale))
                self.assertTrue(_regular_dash_evidence(clipped,24*scale))

    def test_periodic_crossing_ink_does_not_supply_axial_dashes_at_rotated_scales(self):
        for scale in (1,2):
            for angle in (0,45,90):
                with self.subTest(scale=scale,angle=angle):
                    radians=np.deg2rad(angle)
                    axis=np.array([np.cos(radians),np.sin(radians)])
                    normal=np.array([-axis[1],axis[0]])
                    a=np.array([150.,150.])*scale
                    samples=np.tile(np.r_[np.ones(12*scale,bool),np.zeros(8*scale,bool)],5)
                    b=a+axis*(len(samples)-1)
                    axial=np.zeros((400*scale,400*scale),np.uint8)
                    crossing=axial.copy()
                    for start in range(0,len(samples),20*scale):
                        first=a+axis*start; last=first+axis*(12*scale-1)
                        center=(first+last)/2
                        cv2.line(axial,tuple(np.rint(first).astype(int)),tuple(np.rint(last).astype(int)),255,2*scale)
                        cv2.line(crossing,tuple(np.rint(center-normal*12*scale).astype(int)),
                                 tuple(np.rint(center+normal*12*scale).astype(int)),255,2*scale)
                    self.assertTrue(_dash_direction_evidence(a,b,samples,axial))
                    self.assertFalse(_dash_direction_evidence(a,b,samples,crossing))

    def test_dashed_corner_keeps_unsupported_gap_and_observed_endpoints(self):
        image,payload=example();image[:]=255
        value=payload.model_dump(mode='json')
        value['symbols']['items'][1].update(center={'x':220,'y':190},
                                           bounds={'x':212,'y':182,'width':16,'height':16})
        payload=FloorPlanInterpretationPayload.model_validate(value)
        for x in range(69,213,20):
            cv2.line(image,(x,100),(min(x+12,212),100),(0,0,0),2)
        for y in range(108,182,16):
            cv2.line(image,(220,y),(220,min(y+8,181)),(0,0,0),2)
        result=with_automatic_wiring(payload,image)
        self.assertGreaterEqual(len(result.observed_routes.segments),2)
        self.assertFalse(any(p.x==220 and p.y==100 for s in result.observed_routes.segments for p in s.points))
        self.assertFalse(any(c.to_ref.startswith('segment:') for c in result.observed_routes.connections))

    def test_solid_arm_does_not_become_dashed_when_grouped_with_dashed_arm(self):
        image,payload=example()
        value=payload.model_dump(mode='json')
        extra=dict(value['symbols']['items'][0])
        extra.update(id='symbol-0003',center={'x':100,'y':190},
                     bounds={'x':92,'y':182,'width':16,'height':16})
        value['symbols']['items'].append(extra)
        payload=FloorPlanInterpretationPayload.model_validate(value)
        for y in range(107,182,20):
            cv2.line(image,(100,y),(100,min(y+12,181)),(0,0,0),2)
        rows=np.array([[[74,100,247,100]],[[100,107,100,177]]],np.int32)
        with patch('app.ai.floor_plan_interpretation.automatic_wiring.cv2.HoughLinesP',return_value=rows):
            result=with_automatic_wiring(payload,image)
        self.assertEqual({s.line_style for s in result.observed_routes.segments},{'solid','dashed'})

    def test_hatch_crossings_between_device_boxes_are_not_observed_dashes(self):
        image,payload=example();image[:]=255
        for x in range(65,265,20):
            cv2.line(image,(x-16,84),(x+16,116),(0,0,0),2)
        rows=np.array([[[74,100,247,100]]],np.int32)
        with patch('app.ai.floor_plan_interpretation.automatic_wiring.cv2.HoughLinesP',return_value=rows):
            result=with_automatic_wiring(payload,image)
        self.assertFalse(result.observed_routes.segments)
        self.assertFalse(result.observed_routes.connections)

    def test_crossing_strokes_remain_separate_without_junction_connections(self):
        image,payload=example()
        value=payload.model_dump(mode='json')
        for i,y in enumerate((30,180),3):
            extra=dict(value['symbols']['items'][0])
            extra.update(id=f'symbol-{i:04d}',center={'x':160,'y':y},
                         bounds={'x':152,'y':y-8,'width':16,'height':16})
            value['symbols']['items'].append(extra)
        cv2.line(image,(160,38),(160,172),(0,0,0),2)
        payload=FloorPlanInterpretationPayload.model_validate(value)
        rows=np.array([[[74,100,247,100]],[[160,42,160,168]]],np.int32)
        with patch('app.ai.floor_plan_interpretation.automatic_wiring.cv2.HoughLinesP',return_value=rows):
            result=with_automatic_wiring(payload,image)
        self.assertEqual(len(result.observed_routes.segments),2)
        self.assertEqual(len(result.observed_routes.connections),4)
        self.assertTrue(all(c.to_ref.startswith('symbol:') for c in result.observed_routes.connections))

    def test_fixture_ports_reject_nearby_grid_tips_but_keep_centre_axes(self):
        _,payload=example()
        value=payload.model_dump()
        value['symbols']['items'][0]['bounds'].update(y=60,height=80)
        symbol=FloorPlanInterpretationPayload.model_validate(value).symbols.items[0]
        assert _near_port((72,100),symbol,(1,0),12)
        assert not _near_port((72,70),symbol,(1,0),12)
        assert _near_port((60,146),symbol,(0,1),12)

    def test_only_unverified_wall_through_multiple_ceiling_fixture_cores_is_conflicting(self):
        _,payload=example(wall=True)
        value=payload.model_dump()
        value['walls']['items'][0]['start']['x']=20
        value['walls']['items'][0]['end']['x']=300
        for item in value['symbols']['items']:
            item['observed_label']='Troffer lights'
        payload=FloorPlanInterpretationPayload.model_validate(value)
        before=payload.model_dump_json()
        result=with_fixture_wall_conflicts(payload)
        assert not result.walls.items and result.walls.state=='partial'
        assert result.symbols==payload.symbols
        assert 'wall-0001' in result.warnings[-1].message
        assert payload.model_dump_json()==before
        value['symbols']['items'][1]['observed_label']='Wall switch'
        single=FloorPlanInterpretationPayload.model_validate(value)
        assert with_fixture_wall_conflicts(single)==single
        value['symbols']['items'][0]['observed_label']='Wall switch'
        value['symbols']['items'][1]['observed_label']='Wall switch'
        wall_devices=FloorPlanInterpretationPayload.model_validate(value)
        assert with_fixture_wall_conflicts(wall_devices)==wall_devices

    def test_ceiling_grid_near_long_fixture_tips_does_not_become_a_parallel_branch(self):
        image,payload=example()
        value=payload.model_dump(mode='json')
        for item in value['symbols']['items']:
            item['bounds'].update(y=60,height=80)
        payload=FloorPlanInterpretationPayload.model_validate(value)
        cv2.line(image,(69,70),(251,70),(0,0,0),2)
        result=with_automatic_wiring(payload,image)
        self.assertTrue(result.observed_routes.segments)
        self.assertTrue(all(abs(p.y-100)<8 for w in result.observed_routes.segments for p in w.points))

    def test_large_valid_page_skips_only_wiring_without_failing_scan(self):
        _, payload = example()
        value = payload.model_dump()
        value['source_plane'] = {'width_pixels': 4096, 'height_pixels': 4096}
        large = FloorPlanInterpretationPayload.model_validate(value)
        image = np.full((4096, 4096, 3), 255, np.uint8)
        result = with_automatic_wiring(large, image)
        self.assertEqual(result.walls, large.walls)
        self.assertEqual(result.symbols, large.symbols)
        self.assertEqual(result.observed_routes, large.observed_routes)
        self.assertIn('automatic_wiring_budget', [warning.code for warning in result.warnings])

    def test_continuous_device_anchored_stroke_has_source_proposals_without_approval(self):
        image, payload = example()
        before = image.copy(), payload.model_dump_json()
        result = with_automatic_wiring(payload, image)
        self.assertEqual(result.observed_routes.state, 'partial')
        self.assertEqual(len(result.observed_routes.segments), 1)
        self.assertEqual(len(result.observed_routes.connections), 2)
        self.assertTrue(all(c.evidence_kind=='symbol_occlusion' for c in result.observed_routes.connections))
        segment = result.observed_routes.segments[0]
        self.assertEqual(segment.ambiguity, 'ambiguous')
        self.assertEqual(segment.route_kind, 'observed')
        self.assertEqual(segment.evidence_refs, ('region:region-0001',))
        self.assertGreater(segment.points[0].x, 68)
        self.assertLess(segment.points[-1].x, 252)
        self.assertEqual(payload.model_dump_json(), before[1])
        np.testing.assert_array_equal(image, before[0])
        self.assertEqual(result.walls, payload.walls)
        self.assertEqual(result.symbols, payload.symbols)
        self.assertEqual(with_automatic_wiring(payload, image), result)

    def test_gap_is_never_invented_as_a_connection(self):
        image, payload = example(gap=True)
        result = with_automatic_wiring(payload, image)
        self.assertFalse(result.observed_routes.segments)
        self.assertEqual(result.observed_routes.state, 'partial')

    def test_regular_visible_dashes_are_partial_observations_not_circuit_design(self):
        image,payload = example()
        image[96:105,69:252] = 255
        for x in range(69,252,20):
            cv2.line(image,(x,100),(min(x+12,251),100),(0,0,0),1)
        before = image.copy()
        result = with_automatic_wiring(payload,image)
        self.assertTrue(result.observed_routes.segments)
        self.assertEqual(result.observed_routes.state,'partial')
        self.assertEqual(len(result.observed_routes.connections),2)
        self.assertTrue(all(c.to_ref.startswith('symbol:') for c in result.observed_routes.connections))
        self.assertIn('regular_dashed_wiring',[w.code for w in result.warnings])
        self.assertEqual(result.walls,payload.walls)
        np.testing.assert_array_equal(image,before)

    def test_irregular_missing_spans_do_not_become_dashed_wiring(self):
        image,payload = example()
        for a,b in ((100,105),(140,160),(180,188)):
            image[96:105,a:b] = 255
        self.assertFalse(with_automatic_wiring(payload,image).observed_routes.segments)

    def test_dashed_bend_is_preserved_without_replacing_it_with_a_generated_shortcut(self):
        image,payload=example()
        image[:]=255
        value=payload.model_dump(mode='json')
        value['symbols']['items'][1].update(center={'x':220,'y':160},
                                           bounds={'x':212,'y':152,'width':16,'height':16})
        payload=FloorPlanInterpretationPayload.model_validate(value)
        for x in range(69,221,20):
            cv2.line(image,(x,100),(min(x+12,220),100),(0,0,0),2)
        for y in range(100,153,14):
            cv2.line(image,(220,y),(220,min(y+7,152)),(0,0,0),2)
        result=with_automatic_wiring(payload,image)
        self.assertGreaterEqual(len(result.observed_routes.segments),2)
        self.assertTrue(any(any(p.x>210 and p.y>140 for p in w.points) for w in result.observed_routes.segments))
        self.assertTrue(all(w.line_style=='dashed' for w in result.observed_routes.segments))

    def test_one_ended_repeated_dashes_remain_partial_and_do_not_become_a_circuit(self):
        image,payload=example()
        image[:]=255
        for x in range(69,170,20):
            cv2.line(image,(x,100),(x+12,100),(0,0,0),2)
        result=with_automatic_wiring(payload,image)
        self.assertTrue(result.observed_routes.segments)
        self.assertTrue(all(w.line_style=='dashed' for w in result.observed_routes.segments))
        self.assertTrue(all(max(p.x for p in w.points)<190 for w in result.observed_routes.segments))
        self.assertEqual(len(result.observed_routes.connections),1)
        self.assertEqual(result.observed_routes.connections[0].to_ref,'symbol:symbol-0001')
        # Two strokes could be hatch/text fragments, not a repeated route.
        image[:]=255
        for x in (69,89):
            cv2.line(image,(x,100),(x+12,100),(0,0,0),2)
        self.assertFalse(with_automatic_wiring(payload,image).observed_routes.segments)

    def test_drawn_dashes_parallel_to_a_wall_are_not_replaced_by_wall_border_ink(self):
        image,payload=example(wall=True)
        image[96:105,69:252]=255
        for x in range(69,252,20):
            cv2.line(image,(x,100),(min(x+12,251),100),(0,0,0),2)
        result=with_automatic_wiring(payload,image)
        self.assertTrue(result.observed_routes.segments)
        self.assertTrue(all(w.line_style=='dashed' for w in result.observed_routes.segments))
        self.assertEqual(result.walls,payload.walls)

    def test_known_parallel_wall_is_not_emitted_as_wiring(self):
        image, payload = example(wall=True)
        self.assertFalse(with_automatic_wiring(payload, image).observed_routes.segments)

    def test_unanchored_text_and_lines_cannot_create_wire(self):
        image, payload = example()
        image[80:120] = 255
        cv2.line(image, (20, 30), (300, 30), (0, 0, 0), 2)
        cv2.putText(image, 'PLAN 123', (20, 170), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 0), 2)
        self.assertFalse(with_automatic_wiring(payload, image).observed_routes.segments)

    def test_one_device_cannot_connect_to_itself_and_source_scope_is_respected(self):
        image, payload = example()
        value = payload.model_dump()
        value['symbols']['items'] = value['symbols']['items'][:1]
        one = FloorPlanInterpretationPayload.model_validate(value)
        self.assertIs(with_automatic_wiring(one, image), one)
        value = payload.model_dump()
        value['regions'][0]['bounds']['height'] = 50
        scoped = FloorPlanInterpretationPayload.model_validate(value)
        self.assertFalse(with_automatic_wiring(scoped, image).observed_routes.segments)

    def test_existing_observations_are_preserved_and_invalid_source_rejected(self):
        image, payload = example()
        observed = with_automatic_wiring(payload, image)
        self.assertIs(with_automatic_wiring(observed, image), observed)
        for bad in (image[:-1], image.astype(float), image[:, :, 0], None):
            with self.subTest(source=type(bad)), self.assertRaises(ValueError):
                with_automatic_wiring(payload, bad)
        for cap in (0, 513, True, 1.5):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                with_automatic_wiring(payload, image, maximum_segments=cap)


if __name__ == '__main__':
    unittest.main()
