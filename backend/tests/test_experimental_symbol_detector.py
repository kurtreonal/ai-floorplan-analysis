"""Development trained-symbol proposal contract; synthetic data only."""

from hashlib import sha256
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import numpy as np

from app.ai.floor_plan_interpretation import experimental_symbol_detector as detector
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo


class _FakeModel:
    def predict(self, tiles, **kwargs):
        assert kwargs["classes"] == [0, 1, 2, 3]
        return [SimpleNamespace(boxes=[SimpleNamespace(
            xyxy=np.array([[10, 20, 30, 40]], dtype=float),
            cls=np.array([3]), conf=np.array([.7]))]) for _ in tiles]


class _FakeLinkedModel:
    def predict(self, tiles, **kwargs):
        assert kwargs["classes"] == [0, 1, 2, 3, 4]
        return [SimpleNamespace(boxes=[SimpleNamespace(
            xyxy=np.array([[10, 20, 30, 40]], dtype=float),
            cls=np.array([4]), conf=np.array([.7]))]) for _ in tiles]


class ExperimentalSymbolDetectorTests(TestCase):
    def test_native_context_tile_size_is_local_to_call_and_seam_guard_uses_actual_size(self):
        catalog={'model':_FakeModel(),'classes':detector.CLASSES,'threshold':.50,
                 'tile_size':320,'tile_stride':160,'box_fusion':True}
        before=(detector.TILE_SIZE,detector.TILE_STRIDE)
        rows,_=detector.locate(np.full((500,600,3),255,np.uint8),catalog=catalog)
        assert all(row['tile_size']==320 for row in rows)
        assert (detector.TILE_SIZE,detector.TILE_STRIDE)==before
        fragment={'class_id':3,'bbox':(300,20,320,40),'tile_origin':(0,0),
                  'tile_size':320,'clipped_tile_edges':('right',)}
        complete={'class_id':3,'bbox':(300,20,324,40)}
        assert not detector._covered_tile_fragment(fragment,complete)
        complete['bbox']=(300,20,330,40)
        assert detector._covered_tile_fragment(fragment,complete)

    def test_owned_source_and_batch_images_close_on_success_and_prediction_failure(self):
        create_source = detector.Image.fromarray
        for fail in (False, True):
            owned = []

            def tracked_source(pixels):
                source = create_source(pixels)
                crop = source.crop
                owned.append(source)

                def tracked_crop(box):
                    tile = crop(box)
                    owned.append(tile)
                    return tile

                source.crop = tracked_crop
                return source

            model = _FakeModel()
            if fail:
                model.predict = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('prediction failed'))
            with self.subTest(fail=fail), patch.object(detector, 'verify_artifacts'), \
                    patch.object(detector, '_model', return_value=model), \
                    patch.object(detector.Image, 'fromarray', side_effect=tracked_source):
                pixels = np.full((300,300,3), 255, dtype=np.uint8)
                if fail:
                    with self.assertRaises(RuntimeError): detector.locate(pixels)
                else:
                    detector.locate(pixels)
                self.assertGreater(len(owned), 1)
                for image in owned:
                    with self.assertRaises(ValueError): image.getpixel((0,0))

    def test_integrity_and_reference_rights_fence(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "weights.pt"
            checkpoint.write_bytes(b"checkpoint")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "required_loss": "positive_and_local_negative_only", "context_mode": "full_partial",
                "reference_rights_exclusions": {"sheet_ids": ["sheet-51", "sheet-52"]},
                "classes": [{"id": index} for index in range(4)],
            }))
            with patch.object(detector, "CHECKPOINT", checkpoint), \
                 patch.object(detector, "CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "DATASET_MANIFEST", manifest), \
                 patch.object(detector, "DATASET_SHA256", sha256(manifest.read_bytes()).hexdigest()):
                detector.verify_artifacts()
                checkpoint.write_bytes(b"tampered")
                with self.assertRaises(detector.ExperimentalDetectorUnavailable):
                    detector.verify_artifacts()
            self.assertEqual(len(detector.configuration_sha256()), 64)

    def test_source_pixel_tiling_preserves_image_and_candidates_remain_unresolved(self):
        image = np.full((300, 300, 3), 255, dtype=np.uint8)
        original = image.copy()
        with patch.object(detector, "verify_artifacts"), patch.object(detector, "_model", return_value=_FakeModel()):
            candidates, truncated = detector.locate(image)
        self.assertFalse(truncated)
        self.assertEqual(len(candidates), 4)
        self.assertIn((54.0, 64.0, 74.0, 84.0), [row["bbox"] for row in candidates])
        np.testing.assert_array_equal(image, original)
        payload = detector.with_trained_symbol_proposals(interpret_floor_plan_demo(image), candidates)
        self.assertIsInstance(payload, FloorPlanInterpretationPayload)
        self.assertEqual(len(payload.symbols.items), 4)
        self.assertTrue(all(item.mapping_state == "unknown" and item.catalog_class_id is None
                            for item in payload.symbols.items))
        self.assertEqual(payload.symbols.items[0].observed_label, "Troffer lights")
        self.assertTrue(any("not calibrated" in warning.message for warning in payload.warnings))

    def test_linked_classes_are_pinned_and_remain_unresolved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "weights.pt"
            checkpoint.write_bytes(b"linked checkpoint")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "required_loss": "positive_and_local_negative_only", "context_mode": "full_partial",
                "reference_rights_exclusions": {"sheet_ids": ["sheet-51", "sheet-52"]},
                "classes": [{"id": index, "legend_entry": value[1]}
                            for index, value in detector.LINKED_CLASSES.items()],
            }))
            with patch.object(detector, "LINKED_CHECKPOINT", checkpoint), \
                 patch.object(detector, "LINKED_CHECKPOINT_SHA256", sha256(checkpoint.read_bytes()).hexdigest()), \
                 patch.object(detector, "LINKED_DATASET_MANIFEST", manifest), \
                 patch.object(detector, "LINKED_DATASET_SHA256", sha256(manifest.read_bytes()).hexdigest()):
                detector.verify_linked_artifacts()
                data = json.loads(manifest.read_text())
                data["classes"][0]["legend_entry"] = "wrong-class"
                manifest.write_text(json.dumps(data))
                with self.assertRaises(detector.ExperimentalDetectorUnavailable):
                    detector.verify_linked_artifacts()
        image = np.full((300, 300, 3), 255, dtype=np.uint8)
        with patch.object(detector, "verify_linked_artifacts"), \
             patch.object(detector, "_linked_model", return_value=_FakeLinkedModel()):
            candidates, truncated = detector.locate(image, linked=True)
        payload = detector.with_trained_symbol_proposals(
            interpret_floor_plan_demo(image), candidates, truncated, linked=True)
        self.assertEqual(payload.symbols.items[0].observed_label, "Troffer lights")
        self.assertTrue(all(item.mapping_state == "unknown" for item in payload.symbols.items))
        self.assertTrue(any("five linked legend IDs" in warning.message for warning in payload.warnings))
        self.assertNotEqual(detector.configuration_sha256(), detector.linked_configuration_sha256())

    def test_fusion_keeps_distinct_nearby_symbols_and_capped_result_is_partial(self):
        rows = [{"bbox": (0, 0, 20, 20), "class_id": 3, "score": .9, "tile_origin": (0, 0)},
                {"bbox": (1, 0, 21, 20), "class_id": 3, "score": .8, "tile_origin": (0, 0)},
                {"bbox": (21, 0, 41, 20), "class_id": 3, "score": .7, "tile_origin": (0, 0)}]
        self.assertEqual(len(detector.fuse(rows)), 2)
        payload = detector.with_trained_symbol_proposals(
            interpret_floor_plan_demo(np.full((100, 100, 3), 255, dtype=np.uint8)),
            detector.fuse(rows), truncated=True)
        self.assertEqual(payload.symbols.state, "partial")
        self.assertTrue(payload.symbols.truncated)

    def test_box_fusion_weights_two_raw_boxes_and_preserves_identity_and_provenance(self):
        rows = [
            {"bbox": (20, 20, 40, 40), "class_id": 1, "score": .9,
             "tile_origin": (0, 0)},
            {"bbox": (24, 20, 44, 40), "class_id": 1, "score": .6,
             "tile_origin": (10, 0)},
        ]
        original = deepcopy(rows)
        fused = detector.fuse(rows, box_fusion=True)
        self.assertEqual(len(fused), 1)
        winner = fused[0]
        np.testing.assert_allclose(winner["bbox"], (21.6, 20, 41.6, 40))
        self.assertEqual(winner["score"], .9)
        self.assertEqual(winner["class_id"], 1)
        self.assertEqual(winner["tile_origin"], (0, 0))
        self.assertEqual(winner["localization_observations"], tuple(original))
        self.assertEqual(rows, original)
        payload = detector.with_trained_symbol_proposals(
            interpret_floor_plan_demo(np.full((100, 100, 3), 255, dtype=np.uint8)),
            fused, catalog={"classes": {1: ("Outlet", "test:outlet")},
                            "dataset_sha256": "a" * 64})
        symbol = payload.symbols.items[0]
        self.assertEqual(symbol.training_legend.model_class_id, 1)
        self.assertEqual(symbol.training_legend.legend_entry, "test:outlet")
        self.assertEqual(symbol.mapping_state, "unknown")
        warning = next(item for item in payload.warnings
                       if item.code == "experimental_detector_score")
        raw = warning.message.split("original boxes/scores/origins: ", 1)[1]
        self.assertEqual(json.loads(raw), json.loads(json.dumps(original)))
        self.assertEqual(warning.entity_refs, ("symbol:symbol-0001",))

    def test_box_fusion_third_observation_does_not_repeatedly_drift_coordinates(self):
        rows = [
            {"bbox": (20, 20, 40, 40), "class_id": 1, "score": .9,
             "tile_origin": (0, 0)},
            {"bbox": (24, 20, 44, 40), "class_id": 1, "score": .6,
             "tile_origin": (10, 0)},
            {"bbox": (25, 20, 45, 40), "class_id": 1, "score": .5,
             "tile_origin": (15, 0)},
        ]
        original = deepcopy(rows)
        fused = detector.fuse(list(reversed(rows)), box_fusion=True)
        self.assertEqual(len(fused), 1)
        np.testing.assert_allclose(fused[0]["bbox"], (21.6, 20, 41.6, 40))
        self.assertEqual(fused[0]["localization_observations"], tuple(original[:2]))
        self.assertEqual(rows, original)

    def test_box_fusion_keeps_different_class_legends_and_adjacent_outlets(self):
        rows = [
            {"bbox": (20, 20, 40, 40), "class_id": 1, "score": .9,
             "tile_origin": (0, 0)},
            {"bbox": (20, 20, 40, 40), "class_id": 2, "score": .8,
             "tile_origin": (10, 0)},
            {"bbox": (41, 20, 61, 40), "class_id": 1, "score": .7,
             "tile_origin": (10, 0)},
        ]
        original = deepcopy(rows)
        fused = detector.fuse(rows, nested=True, box_fusion=True,
                              class_groups={1: "test:outlet", 2: "test:other-outlet"})
        self.assertEqual(fused, original)
        self.assertEqual(rows, original)

    def test_seam_fragment_requires_same_class_complete_observation_across_edge(self):
        fragment = {"bbox": (100, 100, 108, 120), "class_id": 1, "score": .9,
                    "tile_origin": (100, 0), "clipped_tile_edges": ("left",)}
        complete = {"bbox": (90, 100, 110, 120), "class_id": 1, "score": .8,
                    "tile_origin": (0, 0)}
        original = deepcopy([fragment, complete])
        self.assertEqual(detector.fuse([fragment, complete], box_fusion=True), [complete])
        self.assertEqual([fragment, complete], original)
        for changes in (
            {"class_id": 2},
            {"bbox": (99, 100, 115, 120)},  # Overlap alone is not seam evidence.
            {"bbox": (90, 115, 110, 135)},  # Crosses seam but barely covers fragment.
            {"clipped_tile_edges": ("right",)},  # Another fragment is not complete.
        ):
            with self.subTest(changes=changes):
                other = {**complete, **changes}
                self.assertFalse(detector._covered_tile_fragment(fragment, other))

    def test_isolated_seam_fragment_remains_reviewable(self):
        fragment = {"bbox": (100, 100, 108, 120), "class_id": 1, "score": .7,
                    "tile_origin": (100, 0), "clipped_tile_edges": ("left",)}
        original = deepcopy(fragment)
        self.assertEqual(detector.fuse([fragment], box_fusion=True), [original])
        self.assertEqual(fragment, original)

    def test_broad_neighbor_crossing_seam_does_not_suppress_small_fragment(self):
        fragment = {"bbox": (250, 100, 256, 120), "class_id": 1, "score": .7,
                    "tile_origin": (0, 0), "clipped_tile_edges": ("right",)}
        complete = {"bbox": (200, 95, 265, 125), "class_id": 1, "score": .9,
                    "tile_origin": (0, 0)}
        original = deepcopy([fragment, complete])
        self.assertFalse(detector._covered_tile_fragment(fragment, complete))
        self.assertEqual(detector.fuse([fragment, complete], nested=True, box_fusion=True),
                         [complete, fragment])
        self.assertEqual([fragment, complete], original)

    def test_seam_fragment_coverage_handles_each_internal_edge(self):
        cases = (
            ("left", (100, 120, 108, 140), (90, 120, 110, 140)),
            ("top", (120, 100, 140, 108), (120, 90, 140, 110)),
            ("right", (348, 120, 356, 140), (346, 120, 366, 140)),
            ("bottom", (120, 348, 140, 356), (120, 346, 140, 366)),
        )
        for edge, fragment_box, complete_box in cases:
            with self.subTest(edge=edge):
                fragment = {"bbox": fragment_box, "class_id": 1, "score": .9,
                            "tile_origin": (100, 100), "clipped_tile_edges": (edge,)}
                complete = {"bbox": complete_box, "class_id": 1, "score": .8,
                            "tile_origin": (0, 0)}
                self.assertTrue(detector._covered_tile_fragment(fragment, complete))
                self.assertEqual(detector.fuse([fragment, complete], box_fusion=True), [complete])

    def test_locate_marks_internal_tile_seams_but_not_physical_page_edges(self):
        class EdgeModel:
            def predict(self, tiles, **kwargs):
                return [SimpleNamespace(boxes=[SimpleNamespace(
                    xyxy=np.array([[0, 0, 256, 256]], dtype=float),
                    cls=np.array([1]), conf=np.array([.7]))]) for _ in tiles]

        catalog = {"model": EdgeModel(), "classes": {1: ("Outlet", "test:outlet")},
                   "threshold": .25, "box_fusion": True}
        with patch.object(detector, "fuse", side_effect=lambda rows, **kwargs: rows):
            rows, truncated = detector.locate(
                np.full((300, 300, 3), 255, dtype=np.uint8), catalog=catalog)
        edges = {row["tile_origin"]: row["clipped_tile_edges"] for row in rows}
        self.assertFalse(truncated)
        self.assertEqual(edges, {(0, 0): ("right", "bottom"),
                                 (44, 0): ("left", "bottom"),
                                 (0, 44): ("top", "right"),
                                 (44, 44): ("left", "top")})

    def test_zero_score_box_fusion_preserves_finite_winning_box(self):
        rows = [{"bbox": (20, 20, 40, 40), "class_id": 1, "score": 0,
                 "tile_origin": (0, 0)},
                {"bbox": (24, 20, 44, 40), "class_id": 1, "score": 0,
                 "tile_origin": (10, 0)}]
        original = deepcopy(rows)
        fused = detector.fuse(rows, box_fusion=True)
        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]["bbox"], original[0]["bbox"])
        self.assertEqual(fused[0]["score"], 0)
        self.assertTrue(np.isfinite(fused[0]["bbox"]).all())
        self.assertEqual(fused[0]["localization_observations"], tuple(original))
        self.assertEqual(rows, original)
