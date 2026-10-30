"""Hash-bound development refinement contract, using temporary manifests only."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector


class ClassTailRefinementContractTests(TestCase):
    def manifest(self):
        return {
            'kind': 'local_development_symbol_detector_diagnostic',
            'base_sha256': 'a' * 64,
            'checkpoint_sha256': 'b' * 64,
            'dataset_manifest_sha256': 'c' * 64,
            'production_approval': False,
            'activation': False,
            'diagnostic_only': True,
            'native_positive_controls': True,
            'contrast_settings': {'positive_penalty': 16, 'ridge': 1,
                'negative_training_target': .1, 'unknown_anchor_policy': 'ignored',
                'max_abs_parameter_delta': 1},
            'invariants': {'updated_class': 58, 'trainable_scalars': 243,
                'other_state_exact': True, 'serialized_and_reloaded_other_state_exact': True},
        }

    @contextmanager
    def pinned(self, contents=None):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'run-manifest.json'
            data = self.manifest() if contents is None else contents
            path.write_text(json.dumps(data), encoding='utf-8')
            with patch.multiple(detector, REFINEMENT_MANIFEST=path,
                                REFINEMENT_MANIFEST_SHA256=sha256(path.read_bytes()).hexdigest(),
                                TRAINING_BASE_SHA256='a'*64, CHECKPOINT_SHA256='b'*64,
                                TRAINING_DATASET_SHA256='c'*64):
                yield path

    def test_valid_development_refinement_preserves_manifest_and_module_pins(self):
        previous = (detector.REFINEMENT_MANIFEST, detector.REFINEMENT_MANIFEST_SHA256,
                    detector.TRAINING_BASE_SHA256, detector.CHECKPOINT_SHA256,
                    detector.TRAINING_DATASET_SHA256)
        with self.pinned() as path:
            before = path.read_bytes()
            detector.verify_refinement_artifact()
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(previous, (detector.REFINEMENT_MANIFEST, detector.REFINEMENT_MANIFEST_SHA256,
                                   detector.TRAINING_BASE_SHA256, detector.CHECKPOINT_SHA256,
                                   detector.TRAINING_DATASET_SHA256))

    def test_refinement_bytes_or_hash_change_fails_before_contract_acceptance(self):
        with self.pinned() as path:
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'INTEGRITY_FAILED'):
                detector.verify_refinement_artifact()
        with self.pinned(), patch.object(detector, 'REFINEMENT_MANIFEST_SHA256', 'f'*64):
            with self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'INTEGRITY_FAILED'):
                detector.verify_refinement_artifact()

    def test_matching_manifest_hash_does_not_override_base_checkpoint_or_dataset_binding(self):
        for key in ('base_sha256', 'checkpoint_sha256', 'dataset_manifest_sha256'):
            data = self.manifest(); data[key] = 'f'*64
            with self.subTest(field=key), self.pinned(data):
                with self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
                    detector.verify_refinement_artifact()

    def test_development_flags_cannot_claim_production_or_automatic_activation(self):
        for key in ('production_approval', 'activation', 'diagnostic_only', 'native_positive_controls'):
            for value in (None, 'false', not self.manifest()[key]):
                data = self.manifest(); data[key] = value
                with self.subTest(field=key, value=value), self.pinned(data):
                    with self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
                        detector.verify_refinement_artifact()
        data = self.manifest(); data['kind'] = 'production_model_release'
        with self.pinned(data), self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
            detector.verify_refinement_artifact()

    def test_exact_ridge_settings_and_unknown_anchor_policy_are_required(self):
        for changes in ({'positive_penalty': 64}, {'ridge': 0}, {'negative_training_target': .5},
                        {'unknown_anchor_policy': 'background'}, {'max_abs_parameter_delta': 2},
                        {'unrecorded_setting': True}):
            data = self.manifest(); data['contrast_settings'].update(changes)
            with self.subTest(changes=changes), self.pinned(data):
                with self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
                    detector.verify_refinement_artifact()
        data = self.manifest(); data.pop('contrast_settings')
        with self.pinned(data), self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
            detector.verify_refinement_artifact()

    def test_selected_row_and_exact_serialized_state_proof_are_required(self):
        for changes in ({'updated_class': 57}, {'trainable_scalars': 244},
                        {'other_state_exact': False}, {'serialized_and_reloaded_other_state_exact': False},
                        {'other_state_exact': 'true'}, {'serialized_and_reloaded_other_state_exact': 'true'}):
            data = self.manifest(); data['invariants'].update(changes)
            with self.subTest(changes=changes), self.pinned(data):
                with self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
                    detector.verify_refinement_artifact()
        data = self.manifest(); data['invariants'].pop('serialized_and_reloaded_other_state_exact')
        with self.pinned(data), self.assertRaisesRegex(detector.shared.ExperimentalDetectorUnavailable, 'CONTRACT_INVALID'):
            detector.verify_refinement_artifact()

    def test_original_profiles_without_refinement_do_not_read_a_refinement_file(self):
        with patch.object(detector, 'REFINEMENT_MANIFEST', None), patch.object(detector.shared, '_digest') as digest:
            detector.verify_refinement_artifact()
            digest.assert_not_called()

    def test_power_profile_records_both_training_and_serving_identity_with_refinement_pin(self):
        profile = deepcopy(detector.PROFILES['power80'])
        self.assertEqual(profile['checkpoint_sha256'], '2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa')
        self.assertEqual(profile['training_dataset_sha256'], '286ebf9ec56ffda32d39f73d04f65058c2bad9e99544de6fcc26c4005ffc5470')
        self.assertEqual(profile['dataset_sha256'], '7182de3a9b8616df8d01b8a204b085f95841a40d2740f2239183b8892e763c30')
        self.assertEqual(profile['base_sha256'], 'd68595066681238fa3cfaf612a1e3f30a9b5232b1ed343bf93ced9da43b49477')
        self.assertEqual(profile['refinement_manifest_sha256'], 'b409bef77ca13c3b1c9a25791d54369045ddad4dc7fc60d00c5acd5967456476')
        self.assertEqual(profile['class_count'], 80)
        with self.pinned(), patch.object(detector, 'PROFILE', 'power80'):
            baseline = detector.configuration_sha256()
            with patch.object(detector, 'REFINEMENT_MANIFEST_SHA256', 'f'*64):
                self.assertNotEqual(detector.configuration_sha256(), baseline)
            with patch.object(detector, 'TRAINING_DATASET_SHA256', 'e'*64):
                self.assertNotEqual(detector.configuration_sha256(), baseline)
