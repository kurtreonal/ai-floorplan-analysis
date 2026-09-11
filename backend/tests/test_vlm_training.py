"""Unit and boundary tests for VED Local LoRA/QLoRA Training & Adapter Registry (U10)."""

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from app.ai.floor_plan_interpretation.gold_evaluation import (
    CompletenessMarkers,
    GeometryTruth,
    GoldAnnotationDocument,
    ObservedWiringTruth,
    PixelPoint,
    SymbolTruth,
)
from app.ai.floor_plan_interpretation.training import (
    AdapterManifest,
    AdapterRegistry,
    AdapterRegistryError,
    BaseModelReference,
    CheckpointIncompatibilityError,
    CheckpointManager,
    GroundingCoordinate,
    GroundingSample,
    LoRAHyperparameters,
    LocalTrainingRunner,
    SealedDataLeakageError,
    TrainingBudget,
    TrainingConfig,
    TrainingDatasetManifest,
    build_training_manifest,
    format_gold_to_grounding_sample,
    normalize_coordinates_to_1000,
)


def create_sample_gold_doc(
    source_id: str,
    split: str = "train",
    width_pixels: int = 1000,
    height_pixels: int = 1000,
) -> GoldAnnotationDocument:
    doc = GoldAnnotationDocument(
        schema_version=1,
        source_id=source_id,
        source_sha256=hashlib.sha256(source_id.encode()).hexdigest(),
        page_number=1,
        width_pixels=width_pixels,
        height_pixels=height_pixels,
        sheet_type="electrical_plan",
        symbols=(
            SymbolTruth(
                symbol_id="sym_1",
                class_id=1,
                x_min=100.0,
                y_min=200.0,
                x_max=150.0,
                y_max=250.0,
            ),
        ),
        geometry=(
            GeometryTruth(
                entity_id="wall_1",
                kind="wall",
                points=(PixelPoint(x=50.0, y=50.0), PixelPoint(x=50.0, y=500.0)),
            ),
        ),
        observed_wiring=(),
        text_dimensions=(),
        completeness=CompletenessMarkers(
            symbols="complete",
            geometry="complete",
            observed_wiring="not_applicable",
            text_dimensions="not_applicable",
        ),
    )
    # Attach split dynamically for split isolation tests
    object.__setattr__(doc, "split", split)
    return doc


class VLMTrainingScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="u10_test_"))
        self.base_model = BaseModelReference(
            model_id="Qwen/Qwen2.5-VL-7B-Instruct",
            revision="main",
            model_sha256="a" * 64,
            license_name="Apache-2.0",
            context_window=4096,
            expected_resolution=(1024, 1024),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_configuration_and_hyperparameters(self):
        lora = LoRAHyperparameters(r=16, lora_alpha=32, quantization="int4")
        self.assertEqual(lora.r, 16)
        self.assertEqual(lora.lora_alpha, 32)
        self.assertEqual(lora.quantization, "int4")

        budget = TrainingBudget(
            max_steps=100,
            max_epochs=5,
            learning_rate=1e-4,
            max_vram_mb=4096,
        )
        self.assertEqual(budget.max_vram_mb, 4096)

        config = TrainingConfig(
            base_model=self.base_model,
            lora=lora,
            budget=budget,
            dataset_manifest_sha256="b" * 64,
            output_dir=str(self.temp_dir / "adapters"),
        )
        self.assertEqual(config.dataset_manifest_sha256, "b" * 64)

    def test_grounding_coordinate_normalization(self):
        # 1000x1000 source page
        coord = normalize_coordinates_to_1000(
            x=100.0, y=200.0, width=50.0, height=80.0, page_width=1000, page_height=1000
        )
        self.assertEqual(coord.xmin, 100)
        self.assertEqual(coord.ymin, 200)
        self.assertEqual(coord.xmax, 150)
        self.assertEqual(coord.ymax, 280)

        # Clamping out of bounds
        clamped = normalize_coordinates_to_1000(
            x=-50.0, y=950.0, width=100.0, height=200.0, page_width=1000, page_height=1000
        )
        self.assertEqual(clamped.xmin, 0)
        self.assertEqual(clamped.ymax, 1000)

        # Invalid reversed coordinate check
        with self.assertRaises(ValueError):
            GroundingCoordinate(ymin=500, xmin=100, ymax=200, xmax=300)

    def test_format_gold_to_grounding_sample(self):
        gold = create_sample_gold_doc("gold_01", split="train", width_pixels=1000, height_pixels=1000)
        sample = format_gold_to_grounding_sample(gold, split="train")

        self.assertEqual(sample.sample_id, "sample_gold_01_p1")
        self.assertEqual(sample.split, "train")
        self.assertEqual(sample.symbol_count, 1)
        self.assertEqual(sample.wall_count, 1)
        self.assertEqual(sample.loss_mask["mask_type"], "assistant_tokens_only")

        # Verify parsed response JSON
        payload = json.loads(sample.response_text)
        self.assertIn("symbols", payload)
        self.assertIn("walls", payload)
        self.assertEqual(len(payload["symbols"]), 1)
        self.assertEqual(payload["symbols"][0]["box"], [200, 100, 250, 150])

    def test_sealed_test_split_leakage_rejection(self):
        sealed_gold = create_sample_gold_doc("gold_sealed", split="sealed_test")

        # Single formatting rejection
        with self.assertRaises(SealedDataLeakageError):
            format_gold_to_grounding_sample(sealed_gold, split="train")

        # Manifest builder rejection
        train_gold = [create_sample_gold_doc("gold_train", split="train")]
        with self.assertRaises(SealedDataLeakageError):
            build_training_manifest(train_gold=[sealed_gold], val_gold=[])
        with self.assertRaises(SealedDataLeakageError):
            build_training_manifest(train_gold=train_gold, val_gold=[sealed_gold])

    def test_training_dataset_manifest_hash_integrity(self):
        train_docs = [create_sample_gold_doc(f"train_{i}", split="train") for i in range(3)]
        val_docs = [create_sample_gold_doc(f"val_{i}", split="development_validation") for i in range(2)]

        manifest = build_training_manifest(train_docs, val_docs)
        self.assertEqual(len(manifest.train_samples), 3)
        self.assertEqual(len(manifest.val_samples), 2)
        self.assertEqual(manifest.total_samples, 5)
        self.assertEqual(len(manifest.dataset_hash), 64)

        # Hash is deterministic
        manifest_again = build_training_manifest(train_docs, val_docs)
        self.assertEqual(manifest.dataset_hash, manifest_again.dataset_hash)

    def test_checkpoint_manager_save_and_resume_compatibility(self):
        ckpt_dir = self.temp_dir / "checkpoints"
        config = TrainingConfig(
            base_model=self.base_model,
            dataset_manifest_sha256="c" * 64,
        )
        manager = CheckpointManager(ckpt_dir, config)

        from app.ai.floor_plan_interpretation.training import ValidationMetrics

        val_metrics = ValidationMetrics(
            loss=0.35,
            symbol_precision=0.82,
            symbol_recall=0.79,
            symbol_f1=0.805,
            wall_f1=0.88,
            eval_latency_ms=15.0,
        )

        saved_meta = manager.save_checkpoint(
            step=10,
            epoch=1,
            train_loss=0.45,
            val_metrics=val_metrics,
        )
        self.assertEqual(saved_meta.step, 10)
        self.assertTrue((ckpt_dir / "ckpt_step_000010" / "metadata.json").exists())
        self.assertTrue((ckpt_dir / "ckpt_step_000010" / "adapter_model.bin").exists())

        loaded = manager.load_latest_checkpoint()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.step, 10)
        self.assertEqual(loaded.val_metrics.symbol_f1, 0.805)

    def test_checkpoint_manager_rejects_incompatible_base_model_or_dataset_on_resume(self):
        ckpt_dir = self.temp_dir / "checkpoints_incompat"
        config_original = TrainingConfig(
            base_model=self.base_model,
            dataset_manifest_sha256="d" * 64,
        )
        manager_orig = CheckpointManager(ckpt_dir, config_original)

        from app.ai.floor_plan_interpretation.training import ValidationMetrics
        manager_orig.save_checkpoint(
            step=5,
            epoch=1,
            train_loss=0.5,
            val_metrics=ValidationMetrics(loss=0.5),
        )

        # 1. Base model hash changed
        different_model = BaseModelReference(
            model_id="Qwen/Qwen2.5-VL-7B-Instruct",
            revision="main",
            model_sha256="e" * 64,  # different hash!
            license_name="Apache-2.0",
        )
        config_diff_model = TrainingConfig(
            base_model=different_model,
            dataset_manifest_sha256="d" * 64,
        )
        manager_diff_model = CheckpointManager(ckpt_dir, config_diff_model)
        with self.assertRaises(CheckpointIncompatibilityError):
            manager_diff_model.load_latest_checkpoint()

        # 2. Dataset hash changed
        config_diff_dataset = TrainingConfig(
            base_model=self.base_model,
            dataset_manifest_sha256="f" * 64,  # different dataset!
        )
        manager_diff_dataset = CheckpointManager(ckpt_dir, config_diff_dataset)
        with self.assertRaises(CheckpointIncompatibilityError):
            manager_diff_dataset.load_latest_checkpoint()

    def test_adapter_registry_enforces_inactive_status_and_no_overwrites(self):
        reg_file = self.temp_dir / "registry.json"
        registry = AdapterRegistry(reg_file)

        from app.ai.floor_plan_interpretation.training import CheckpointMetadata, ValidationMetrics

        dummy_ckpt = CheckpointMetadata(
            checkpoint_id="ckpt_step_000050",
            step=50,
            epoch=2,
            train_loss=0.25,
            val_metrics=ValidationMetrics(loss=0.3),
            base_model_sha256=self.base_model.model_sha256,
            dataset_hash="a" * 64,
            checkpoint_dir=str(self.temp_dir / "ckpt"),
        )

        adapter = AdapterManifest(
            adapter_id="ved_lora_test01",
            name="VED LoRA Test 01",
            version="v1.0",
            status="inactive",
            base_model=self.base_model,
            lora=LoRAHyperparameters(),
            dataset_hash="a" * 64,
            best_checkpoint=dummy_ckpt,
        )

        registry.register_adapter(adapter)
        self.assertEqual(len(registry.list_adapters()), 1)

        retrieved = registry.get_adapter("ved_lora_test01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status, "inactive")

        # Duplicate ID rejection
        with self.assertRaises(AdapterRegistryError):
            registry.register_adapter(adapter)

    def test_training_runner_offline_egress_and_inactive_registration(self):
        train_docs = [create_sample_gold_doc(f"train_{i}", split="train") for i in range(2)]
        val_docs = [create_sample_gold_doc(f"val_{i}", split="development_validation") for i in range(1)]
        manifest = build_training_manifest(train_docs, val_docs)

        reg_file = self.temp_dir / "runner_registry.json"
        registry = AdapterRegistry(reg_file)
        ckpt_dir = self.temp_dir / "runner_checkpoints"

        config = TrainingConfig(
            base_model=self.base_model,
            budget=TrainingBudget(max_steps=3, max_epochs=3),
            dataset_manifest_sha256=manifest.dataset_hash,
        )

        runner = LocalTrainingRunner(
            config=config,
            manifest=manifest,
            registry=registry,
            checkpoint_dir=ckpt_dir,
            is_mock=True,
        )

        adapter = runner.run(resume_if_available=False)
        self.assertEqual(adapter.status, "inactive")
        self.assertEqual(adapter.best_checkpoint.step, 3)
        self.assertTrue(adapter.best_checkpoint.val_metrics.symbol_f1 > 0.0)

        # Check in registry
        saved = registry.get_adapter(adapter.adapter_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "inactive")
        self.assertEqual(saved.provenance["steps_completed"], 3)


if __name__ == "__main__":
    unittest.main()
