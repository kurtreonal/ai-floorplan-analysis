import unittest

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.automatic_wiring import with_automatic_wiring
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

    def test_continuous_device_anchored_stroke_becomes_reviewable_not_connected(self):
        image, payload = example()
        before = image.copy(), payload.model_dump_json()
        result = with_automatic_wiring(payload, image)
        self.assertEqual(result.observed_routes.state, 'partial')
        self.assertEqual(len(result.observed_routes.segments), 1)
        self.assertEqual(result.observed_routes.connections, ())
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
