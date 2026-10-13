from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.services import pdf_legend_catalog as catalog


class PdfCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "storage/training/source"
        self.directory.mkdir(parents=True)
        self.source_hash = self.write("original.pdf", b"synthetic PDF identity")
        permission_hash = self.write("source-authorization.json", json.dumps({
            "authorization_kind": "user_attested_source_permission",
            "source_sha256": self.source_hash, "allowed_purposes": ["reference_grounding"],
            "user_statement": "Use the supplied legends in the catalog",
        }).encode())
        page_hash = self.write("page.png", b"synthetic page")
        crop_hash = self.write("crop.png", b"synthetic reference crop")
        self.manifest = {
            "schema": "ved-authorized-pdf-preparation-v1", "source_sha256": self.source_hash,
            "authorization_sha256": permission_hash,
            "pages": [{"page_number": 1, "filename": "page.png", "image_sha256": page_hash}],
            "regions": [{"region_id": f"L{i:02d}", "page_number": 1, "filename": "crop.png",
                "crop_sha256": crop_hash, "source_image_sha256": page_hash,
                "source_page_id": f"{self.source_hash}:page:1", "proposed_label": "Fixture"}
                for i in range(1, 41)],
        }

    def write(self, name, content):
        (self.directory / name).write_bytes(content)
        return sha256(content).hexdigest()

    def invoke(self):
        digest = self.write("manifest.json", json.dumps(self.manifest).encode())
        with patch.object(catalog, "REPOSITORY_ROOT", self.root), \
             patch.object(catalog, "SOURCES", (("source", digest, self.source_hash, 1, 40),)):
            return catalog.approved_pdf_catalog_names()

    def test_full_catalog_keeps_equal_names_as_distinct_source_entries_without_loading_model(self):
        names = self.invoke()
        self.assertEqual(len(names), 40)
        self.assertEqual(len(set(names)), 40)
        self.assertTrue(names[0].endswith(f"[pdf-{self.source_hash[:12]}:p1:L01]"))

    def test_changed_source_page_crop_permission_and_missing_files_fail_closed(self):
        for filename in ("original.pdf", "page.png", "crop.png", "source-authorization.json"):
            with self.subTest(filename=filename):
                path = self.directory / filename
                original = path.read_bytes()
                path.write_bytes(b"altered")
                with self.assertRaises(ValueError):
                    self.invoke()
                path.write_bytes(original)
        (self.directory / "crop.png").unlink()
        with self.assertRaises(OSError):
            self.invoke()

    def test_missing_duplicate_or_wrong_page_definitions_rejected(self):
        original = json.dumps(self.manifest)
        for mutation in ("missing", "duplicate", "page", "path"):
            with self.subTest(mutation=mutation):
                self.manifest = json.loads(original)
                if mutation == "missing":
                    self.manifest["regions"].pop()
                elif mutation == "duplicate":
                    self.manifest["regions"][0] = self.manifest["regions"][1]
                elif mutation == "page":
                    self.manifest["regions"][0]["source_page_id"] = f"{self.source_hash}:page:2"
                else:
                    self.manifest["regions"][0]["filename"] = "../crop.png"
                with self.assertRaises(ValueError):
                    self.invoke()

    def test_reference_permission_required_even_with_matching_hash(self):
        self.manifest["authorization_sha256"] = self.write("source-authorization.json", json.dumps({
            "authorization_kind": "user_attested_source_permission", "source_sha256": self.source_hash,
            "allowed_purposes": ["training"], "user_statement": "training only",
        }).encode())
        with self.assertRaises(ValueError):
            self.invoke()

    def test_wiring_patterns_distinct_from_devices_and_homeruns(self):
        self.assertTrue(catalog.is_wiring_legend("Raceway conduit concealed in ceiling [pdf-76f411c60b6d:p1:L10]"))
        self.assertTrue(catalog.is_wiring_legend("Raceway conduit concealed under floor [pdf-efa570519f08:p7:L10]"))
        for name in ("Ceiling light outlet", "Homerun direct to panelboard [pdf-76f411c60b6d:p1:L16]", "Panelboard"):
            self.assertFalse(catalog.is_wiring_legend(name))
