"""Unit and boundary tests for U7 multi-resolution page and context preparation."""

import math
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform,
    PixelBounds,
    PixelPoint,
    SourcePlane,
)
from app.ai.floor_plan_interpretation.preparation import (
    ArtifactPersistenceError,
    InvalidGeometryError,
    LineSegmentEvidence,
    PreparationConfig,
    PreparationError,
    PreparationResourceExhaustion,
    PreparedContext,
    PreparedRegion,
    PreparedTile,
    SymbolCandidateObservation,
    WallCandidateObservation,
    assert_isotropic_scaling,
    assess_page_signals,
    detect_legend_region,
    detect_plan_region,
    extract_auxiliary_thresholded,
    extract_line_evidence,
    extract_ocr_evidence,
    fuse_detected_symbols,
    fuse_detected_walls,
    generate_overview_region,
    generate_tiles,
    invert_affine_transform,
    load_and_orient_image,
    local_to_source_coords,
    persist_prepared_tiles,
    prepare_page_context,
    source_to_local_coords,
    transform_bounds_local_to_source,
    transform_bounds_source_to_local,
)
from app.core.database import get_engine
from app.models import FloorPlan, FloorPlanPage, FloorPlanSource, ProcessingArtifact, ProcessingJob, Project, ProjectFloor, Role, User


class CoordinateTransformationTests(TestCase):
    """Tests for reversible coordinate and bounding box math."""

    def test_invert_affine_transform_roundtrip(self) -> None:
        # Scale by 2.5, translate by (100, 200)
        tf = AffineTransform(a=2.5, b=0.0, c=0.0, d=2.5, e=100.0, f=200.0)
        inv = invert_affine_transform(tf)

        # Invert the inverse -> should match original
        inv_inv = invert_affine_transform(inv)
        self.assertAlmostEqual(float(inv_inv.a), float(tf.a), places=5)
        self.assertAlmostEqual(float(inv_inv.d), float(tf.d), places=5)
        self.assertAlmostEqual(float(inv_inv.e), float(tf.e), places=3)
        self.assertAlmostEqual(float(inv_inv.f), float(tf.f), places=3)

    def test_local_to_source_and_source_to_local_fidelity(self) -> None:
        tf = AffineTransform(a=2.0, b=0.0, c=0.0, d=2.0, e=50.0, f=75.0)
        local_pts = [(0.0, 0.0), (10.5, 20.25), (100.0, 250.0)]

        for u, v in local_pts:
            x, y = local_to_source_coords(tf, u, v)
            u_back, v_back = source_to_local_coords(tf, x, y)
            self.assertAlmostEqual(u, u_back, places=3)
            self.assertAlmostEqual(v, v_back, places=3)

    def test_transform_bounds_reversible(self) -> None:
        tf = AffineTransform(a=1.5, b=0.0, c=0.0, d=1.5, e=10.0, f=20.0)
        local_bounds = PixelBounds(x=10.0, y=15.0, width=50.0, height=80.0)

        src_bounds = transform_bounds_local_to_source(tf, local_bounds)
        self.assertAlmostEqual(src_bounds.x, 10.0 * 1.5 + 10.0, places=2)
        self.assertAlmostEqual(src_bounds.y, 15.0 * 1.5 + 20.0, places=2)
        self.assertAlmostEqual(src_bounds.width, 50.0 * 1.5, places=2)
        self.assertAlmostEqual(src_bounds.height, 80.0 * 1.5, places=2)

        recovered = transform_bounds_source_to_local(tf, src_bounds)
        self.assertAlmostEqual(recovered.x, local_bounds.x, places=2)
        self.assertAlmostEqual(recovered.y, local_bounds.y, places=2)
        self.assertAlmostEqual(recovered.width, local_bounds.width, places=2)
        self.assertAlmostEqual(recovered.height, local_bounds.height, places=2)

    def test_rejects_zero_determinant_transform(self) -> None:
        # Collinear / degenerate rows (det = 0) must be rejected by Pydantic model validator
        with self.assertRaises(ValueError):
            AffineTransform(a=2.0, b=1.0, c=4.0, d=2.0, e=0.0, f=0.0)

    def test_asymmetric_scaling_rejection(self) -> None:
        # Non-uniform scale (sx=2.0, sy=3.0) violates isotropic floor plan scale
        tf = AffineTransform(a=2.0, b=0.0, c=0.0, d=3.0, e=0.0, f=0.0)
        with self.assertRaises(InvalidGeometryError):
            assert_isotropic_scaling(tf)


class ImageLoadingAndNormalizationTests(TestCase):
    """Tests for image loading, orientation transposition, and alpha flattening."""

    def test_exif_orientation_transposition(self) -> None:
        # Create an image with orientation 6 (90 degrees CW)
        img = Image.new("RGB", (40, 20), color=(200, 100, 50))
        exif = Image.Exif()
        exif[274] = 6  # Rotated 90 CW
        buf = BytesIO()
        img.save(buf, format="JPEG", exif=exif)

        arr = load_and_orient_image(buf.getvalue(), min_edge=10)
        # Orientation 6 rotates 90 degrees, swapping width and height: 40x20 -> 20x40
        self.assertEqual(arr.shape[:2], (40, 20))

    def test_transparency_flattening_on_white(self) -> None:
        # Create RGBA image with semi-transparent and transparent areas
        rgba = Image.new("RGBA", (20, 20), (255, 0, 0, 0))  # Fully transparent red
        # Add opaque blue box
        for x in range(5, 15):
            for y in range(5, 15):
                rgba.putpixel((x, y), (0, 0, 255, 255))

        arr = load_and_orient_image(rgba, min_edge=10)
        self.assertEqual(arr.shape, (20, 20, 3))
        # Transparent pixels should composite to pure white (255, 255, 255)
        np.testing.assert_array_equal(arr[0, 0], [255, 255, 255])
        # Opaque blue box should remain blue (0, 0, 255)
        np.testing.assert_array_equal(arr[10, 10], [0, 0, 255])

    def test_rejects_sub_minimum_dimension(self) -> None:
        tiny = np.ones((8, 8, 3), dtype=np.uint8) * 255
        with self.assertRaises(InvalidGeometryError):
            load_and_orient_image(tiny, min_edge=16)

    def test_fails_before_memory_exhaustion_on_excessive_pixels(self) -> None:
        huge_img = Image.new("RGB", (10_000, 7_000), "white")  # 70M pixels > 60M limit
        try:
            with self.assertRaises(PreparationResourceExhaustion):
                load_and_orient_image(huge_img, max_pixels=60_000_000)
        finally:
            huge_img.close()


class MultiResolutionRegionTests(TestCase):
    """Tests for overview downsampling, plan-region, and legend detection."""

    def setUp(self) -> None:
        # Synthetic floor plan drawing: 1000 x 800 with white background and black walls
        self.img = np.ones((800, 1000, 3), dtype=np.uint8) * 255
        # Draw exterior walls
        cv2.rectangle(self.img, (100, 100), (900, 700), (0, 0, 0), thickness=4)
        # Draw interior partition
        cv2.line(self.img, (500, 100), (500, 700), (0, 0, 0), thickness=2)

    def test_overview_generation_preserves_aspect_ratio_and_bounds(self) -> None:
        overview = generate_overview_region(self.img, max_dimension=500)
        H, W = overview.image_rgb.shape[:2]
        self.assertEqual(W, 500)
        self.assertEqual(H, 400)
        self.assertEqual(overview.region.kind, "overview")
        self.assertEqual(overview.region.bounds.width, 1000.0)
        self.assertEqual(overview.region.bounds.height, 800.0)

        # Scale factor is 500 / 1000 = 0.5 -> inv_scale is 2.0
        self.assertAlmostEqual(float(overview.region.local_to_source.a), 2.0, places=4)
        self.assertAlmostEqual(float(overview.region.local_to_source.d), 2.0, places=4)

    def test_plan_region_detection_bounds_drawing(self) -> None:
        plan = detect_plan_region(self.img, margin=10)
        self.assertEqual(plan.region.kind, "plan_region")
        # Exterior walls are at [100, 100] to [900, 700]
        # With margin 10, bounds should roughly encompass x in [90, 910] and y in [90, 710]
        self.assertLessEqual(plan.region.bounds.x, 100.0)
        self.assertLessEqual(plan.region.bounds.y, 100.0)
        self.assertGreaterEqual(plan.region.bounds.x + plan.region.bounds.width, 900.0)
        self.assertGreaterEqual(plan.region.bounds.y + plan.region.bounds.height, 700.0)

    def test_legend_region_extraction_when_specified(self) -> None:
        bounds = PixelBounds(x=50.0, y=50.0, width=200.0, height=150.0)
        legend = detect_legend_region(self.img, explicit_bounds=bounds)
        self.assertIsNotNone(legend)
        self.assertEqual(legend.region.kind, "legend")
        self.assertEqual(legend.image_rgb.shape[:2], (150, 200))


class OverlappingTileGridTests(TestCase):
    """Tests for tile decomposition, overlaps, and resource limit pre-checks."""

    def test_tile_generation_covers_full_image_with_overlap(self) -> None:
        img = np.ones((600, 800, 3), dtype=np.uint8) * 255
        cfg = PreparationConfig(tile_width=400, tile_height=400, tile_overlap=100)
        tiles = generate_tiles(img, cfg)

        self.assertGreater(len(tiles), 1)
        # Check that tiles have valid sequential region IDs
        for i, t in enumerate(tiles, start=4):
            self.assertEqual(t.region_id, f"region-{i:04d}")
            self.assertGreater(t.image_rgb.shape[0], 0)
            self.assertGreater(t.image_rgb.shape[1], 0)

        # Check coverage of corners: (0, 0) and (800, 600)
        first_tile = tiles[0]
        self.assertEqual(first_tile.bounds.x, 0.0)
        self.assertEqual(first_tile.bounds.y, 0.0)

        last_tile = tiles[-1]
        self.assertEqual(last_tile.bounds.x + last_tile.bounds.width, 800.0)
        self.assertEqual(last_tile.bounds.y + last_tile.bounds.height, 600.0)

    def test_rejects_invalid_overlap_or_excessive_tiles_before_allocation(self) -> None:
        img = np.ones((500, 500, 3), dtype=np.uint8) * 255

        # Overlap >= tile dimension
        with self.assertRaises(InvalidGeometryError):
            generate_tiles(img, PreparationConfig(tile_width=200, tile_height=200, tile_overlap=200))

        # Projected tiles exceed max_tiles
        with self.assertRaises(PreparationResourceExhaustion):
            generate_tiles(img, PreparationConfig(tile_width=128, tile_height=128, tile_overlap=32, max_tiles=4))


class AuxiliaryEvidenceTests(TestCase):
    """Tests for thresholded imagery, line extraction, and OCR token detection."""

    def setUp(self) -> None:
        self.img = np.ones((400, 400, 3), dtype=np.uint8) * 255
        # Horizontal line
        cv2.line(self.img, (50, 100), (350, 100), (0, 0, 0), thickness=3)
        # Vertical line
        cv2.line(self.img, (200, 50), (200, 350), (0, 0, 0), thickness=3)
        # Diagonal line
        cv2.line(self.img, (50, 50), (150, 150), (0, 0, 0), thickness=2)

    def test_extract_auxiliary_thresholded_binary(self) -> None:
        thresh = extract_auxiliary_thresholded(self.img)
        self.assertEqual(thresh.shape, (400, 400))
        unique_vals = set(np.unique(thresh))
        self.assertTrue(unique_vals.issubset({0, 255}))

    def test_extract_line_evidence_classifies_orientations(self) -> None:
        lines = extract_line_evidence(self.img, region_id="region-0001", max_lines=50)
        self.assertGreater(len(lines), 0)

        orientations = {line.orientation for line in lines}
        self.assertIn("horizontal", orientations)
        self.assertIn("vertical", orientations)


class PageSignalsAndAssessmentTests(TestCase):
    """Tests for signals, page classification, and quality assessment."""

    def test_blank_page_unsupported_with_proper_issue(self) -> None:
        blank = np.ones((500, 500, 3), dtype=np.uint8) * 255
        assessment = assess_page_signals(blank, (), ())
        self.assertEqual(assessment.quality, "unsupported")
        self.assertIn("blank-page", assessment.quality_issues)

    def test_architectural_plan_detected_when_lines_present_without_electrical(self) -> None:
        img = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (20, 20), (380, 380), (0, 0, 0), thickness=2)
        lines = tuple(
            LineSegmentEvidence(
                id=f"line-{i:04d}",
                region_id="region-0001",
                start=PixelPoint(x=10.0, y=float(i * 10)),
                end=PixelPoint(x=300.0, y=float(i * 10)),
                orientation="horizontal",
                length_pixels=290.0,
                thickness_pixels=2.0,
            )
            for i in range(1, 25)
        )
        assessment = assess_page_signals(img, (), lines)
        self.assertEqual(assessment.page_type, "architectural_plan")
        self.assertIn("missing-legend", assessment.quality_issues)
        self.assertIn("missing-scale", assessment.quality_issues)


class TileDeduplicationAndFusionTests(TestCase):
    """Tests for fusing symbol candidates across overlapping tile boundaries."""

    def setUp(self) -> None:
        # Region transforms:
        # Tile 1: offset (0, 0)
        # Tile 2: offset (300, 0) - overlapping with Tile 1 from x=300 to x=400
        self.transforms = {
            "region-0004": AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0),
            "region-0005": AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=300.0, f=0.0),
        }

    def test_fuses_duplicate_symbol_in_tile_overlap(self) -> None:
        # A single physical duplex receptacle located at source plane (350, 100)
        # Observed in Tile 1 at local (350, 100)
        obs1 = SymbolCandidateObservation(
            region_id="region-0004",
            catalog_class_id=1,
            observed_label="DUPLEX",
            local_center=(350.0, 100.0),
            local_bounds=(340.0, 90.0, 20.0, 20.0),
        )
        # Observed in Tile 2 at local (50, 100) -> source x = 50 + 300 = 350
        obs2 = SymbolCandidateObservation(
            region_id="region-0005",
            catalog_class_id=1,
            observed_label="DUPLEX",
            local_center=(50.0, 100.0),
            local_bounds=(40.0, 90.0, 20.0, 20.0),
        )

        fused = fuse_detected_symbols([obs1, obs2], self.transforms, distance_threshold=15.0)

        # Should merge into 1 symbol candidate
        self.assertEqual(len(fused), 1)
        sym = fused[0]
        self.assertEqual(sym.id, "symbol-0001")
        self.assertEqual(sym.mapping_state, "matched")
        self.assertEqual(sym.catalog_class_id, 1)
        self.assertAlmostEqual(sym.center.x, 350.0, places=2)
        self.assertAlmostEqual(sym.center.y, 100.0, places=2)
        # Provenance should reference BOTH regions
        self.assertEqual(sym.evidence_refs, ("region:region-0004", "region:region-0005"))
        self.assertEqual(sym.ambiguity, "clear")

    def test_adjacent_distinct_symbols_are_not_suppressed(self) -> None:
        # Dual adjacent receptacles separated by 40px: at (320, 100) and (360, 100)
        obs1 = SymbolCandidateObservation(
            region_id="region-0004",
            catalog_class_id=1,
            observed_label="OUTLET_A",
            local_center=(320.0, 100.0),
        )
        obs2 = SymbolCandidateObservation(
            region_id="region-0004",
            catalog_class_id=1,
            observed_label="OUTLET_B",
            local_center=(360.0, 100.0),
        )

        fused = fuse_detected_symbols([obs1, obs2], self.transforms, distance_threshold=20.0)
        # Since distance (40) > threshold (20), BOTH must be preserved
        self.assertEqual(len(fused), 2)
        self.assertEqual(fused[0].id, "symbol-0001")
        self.assertEqual(fused[1].id, "symbol-0002")

    def test_conflicting_classes_marked_ambiguous(self) -> None:
        # Same location observed as Class 1 in Tile 1 and Class 2 in Tile 2
        obs1 = SymbolCandidateObservation(
            region_id="region-0004",
            catalog_class_id=1,
            observed_label="OUTLET",
            local_center=(350.0, 100.0),
        )
        obs2 = SymbolCandidateObservation(
            region_id="region-0005",
            catalog_class_id=2,
            observed_label="SWITCH",
            local_center=(50.0, 100.0),
        )

        fused = fuse_detected_symbols([obs1, obs2], self.transforms, distance_threshold=15.0)
        self.assertEqual(len(fused), 1)
        sym = fused[0]
        self.assertEqual(sym.mapping_state, "ambiguous")
        self.assertIsNone(sym.catalog_class_id)
        self.assertEqual(sym.ambiguity, "ambiguous")
        self.assertEqual(sym.evidence_refs, ("region:region-0004", "region:region-0005"))


class FullPageContextAndPersistenceTests(TestCase):
    """Integration tests for prepare_page_context and PRE5 artifact persistence."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.session = Session(bind=cls.connection, expire_on_commit=False)

        role = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        marker = uuid4().hex
        user = User(oauth_provider="u7-test", oauth_subject=marker, role=role)
        project = Project(owner=user, name=f"U7 {marker}")
        floor = ProjectFloor(project=project, name="Ground")
        cls.plan = FloorPlan(
            project_floor=floor,
            original_filename="plan_u7.png",
            storage_path="originals/plan_u7.png",
            mime_type="image/png",
            file_size=1024,
        )
        source = FloorPlanSource(
            floor_plan=cls.plan,
            original_sha256="c" * 64,
            pages=[FloorPlanPage(page_number=1)],
        )
        cls.job = ProcessingJob(floor_plan=cls.plan, job_type="floor_plan_analysis")
        cls.session.add_all((user, project, floor, cls.plan, source, cls.job))
        cls.session.flush()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.savepoint = self.connection.begin_nested()
        self.temp = TemporaryDirectory()
        self.processed_dir = Path(self.temp.name)

    def tearDown(self) -> None:
        self.session.expire_all()
        if self.savepoint.is_active:
            self.savepoint.rollback()
        self.temp.cleanup()

    def test_prepare_page_context_and_persist_tiles(self) -> None:
        # Create synthetic 600x500 blueprint
        img = np.ones((500, 600, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 50), (550, 450), (0, 0, 0), thickness=3)

        cfg = PreparationConfig(tile_width=300, tile_height=300, tile_overlap=50)
        context = prepare_page_context(img, page_number=1, config=cfg)

        self.assertEqual(context.page_number, 1)
        self.assertEqual(context.source_plane.width_pixels, 600)
        self.assertEqual(context.source_plane.height_pixels, 500)
        self.assertEqual(context.overview.region.kind, "overview")
        self.assertGreater(len(context.tiles), 1)

        # Persist tiles as PRE5 artifacts
        artifacts = persist_prepared_tiles(
            context,
            session=self.session,
            processing_job=self.job,
            processed_directory=self.processed_dir,
        )

        self.assertEqual(len(artifacts), len(context.tiles))
        for art in artifacts:
            self.assertEqual(art.artifact_kind, "vlm_tile")
            self.assertEqual(art.mime_type, "image/png")
            self.assertGreater(art.byte_size, 0)
            self.assertEqual(len(art.sha256), 64)
            self.assertTrue(self.processed_dir.joinpath(*art.relative_path.split("/")).is_file())

    def test_original_file_hash_unchanged(self) -> None:
        import hashlib

        # Save an original file to a separate originals directory
        orig_dir = self.processed_dir / "originals"
        orig_dir.mkdir(parents=True, exist_ok=True)
        orig_file = orig_dir / "blueprint_original.png"
        sample_img = Image.new("RGB", (400, 300), color=(240, 240, 240))
        sample_img.save(orig_file, format="PNG")
        sample_img.close()

        orig_bytes_before = orig_file.read_bytes()
        orig_hash_before = hashlib.sha256(orig_bytes_before).hexdigest()

        # Run preparation using the file path
        context = prepare_page_context(orig_file, page_number=1)
        persist_prepared_tiles(
            context,
            session=self.session,
            processing_job=self.job,
            processed_directory=self.processed_dir,
        )

        orig_bytes_after = orig_file.read_bytes()
        orig_hash_after = hashlib.sha256(orig_bytes_after).hexdigest()

        self.assertEqual(orig_bytes_before, orig_bytes_after)
        self.assertEqual(orig_hash_before, orig_hash_after)

    def test_multipage_context_distinct_pages(self) -> None:
        img1 = np.ones((300, 300, 3), dtype=np.uint8) * 255
        img2 = np.ones((400, 400, 3), dtype=np.uint8) * 255

        ctx1 = prepare_page_context(img1, page_number=1)
        ctx2 = prepare_page_context(img2, page_number=2)

        self.assertEqual(ctx1.page_number, 1)
        self.assertEqual(ctx2.page_number, 2)
        self.assertEqual(ctx1.source_plane.width_pixels, 300)
        self.assertEqual(ctx2.source_plane.width_pixels, 400)

    def test_fuse_collinear_walls(self) -> None:
        transforms = {
            "region-0004": AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0),
            "region-0005": AffineTransform(a=1.0, b=0.0, c=0.0, d=1.0, e=200.0, f=0.0),
        }
        obs1 = WallCandidateObservation(
            region_id="region-0004",
            local_start=(50.0, 100.0),
            local_end=(250.0, 100.0),
        )
        obs2 = WallCandidateObservation(
            region_id="region-0005",
            local_start=(50.0, 100.0),  # source: (250, 100)
            local_end=(150.0, 100.0),  # source: (350, 100)
        )
        walls = fuse_detected_walls([obs1, obs2], transforms)
        self.assertEqual(len(walls), 2)
        self.assertEqual(walls[0].id, "wall-0001")
        self.assertEqual(walls[1].id, "wall-0002")
        self.assertEqual(walls[0].start, PixelPoint(x=50.0, y=100.0))
        self.assertEqual(walls[0].end, PixelPoint(x=250.0, y=100.0))
        self.assertEqual(walls[1].start, PixelPoint(x=250.0, y=100.0))
        self.assertEqual(walls[1].end, PixelPoint(x=350.0, y=100.0))

