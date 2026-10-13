"""Pinned authored definitions for catalog use, independent of model activation.

The owner's catalog instruction authorizes local catalog availability, not
human review of assistant boxes, calibrated detection, or production promotion.
"""
from hashlib import sha256
import json
import re

from app.core.config import REPOSITORY_ROOT
from app.schemas.symbol_legend import SymbolLegendWrite


SOURCES = (
    ("pdf-source-20261004-efa570519f08-v3",
     "41d23c6e6d477508e17068901d4018234fa0e7df84976b83dcb3a0676280bb9a",
     "efa570519f08bc3596d443fcc63c96ddd6bf73039bcba7ed3e52881d0943d9af", 7, 16),
    ("pdf-source-20261004-76f411c60b6d-v3",
     "305a464ef9e907785dbc3b5712be5c9418f1d614c677f230ca6506c698030963",
     "76f411c60b6d3a7b0d4c1d89b8cadb0de1fd54a58573aae706fe6fa07113c868", 1, 24),
)


def is_wiring_legend(name: str) -> bool:
    # Authored line patterns describe observed wiring, never a point device.
    return name.startswith(("Raceway conduit concealed in ceiling [pdf-",
                            "Raceway conduit concealed under floor [pdf-"))


def _verified_file(directory, filename, expected, limit):
    path = directory / filename
    if path.parent != directory or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("Invalid catalog artifact")
    content = path.read_bytes()
    if sha256(content).hexdigest() != expected:
        raise ValueError("Catalog artifact changed")
    return content


def approved_pdf_catalog_names():
    """Fail closed on changed/missing sources; do not require trained weights."""
    names = []
    for folder, manifest_hash, source_hash, page_number, count in SOURCES:
        directory = REPOSITORY_ROOT / "storage/training" / folder
        manifest = json.loads(_verified_file(directory, "manifest.json", manifest_hash, 256_000))
        if manifest["schema"] != "ved-authorized-pdf-preparation-v1" or manifest["source_sha256"] != source_hash:
            raise ValueError("Source identity differs")
        permission = json.loads(_verified_file(directory, "source-authorization.json",
                                              manifest["authorization_sha256"], 64_000))
        if (permission.get("authorization_kind") != "user_attested_source_permission"
                or permission.get("source_sha256") != source_hash
                or "reference_grounding" not in permission.get("allowed_purposes", [])
                or not permission.get("user_statement")):
            raise ValueError("Reference permission unavailable")
        _verified_file(directory, "original.pdf", source_hash, 25 * 1024 * 1024)
        entries = [r for r in manifest["regions"] if re.fullmatch(r"L\d{2}", r["region_id"])]
        if len(entries) != count or {r["region_id"] for r in entries} != {f"L{i:02d}" for i in range(1, count + 1)}:
            raise ValueError("Incomplete authored catalog")
        page = next(p for p in manifest["pages"] if p["page_number"] == page_number)
        _verified_file(directory, page["filename"], page["image_sha256"], 100 * 1024 * 1024)
        for row in sorted(entries, key=lambda r: r["region_id"]):
            if (row["page_number"] != page_number
                    or row["source_page_id"] != f"{source_hash}:page:{page_number}"
                    or row["source_image_sha256"] != page["image_sha256"]):
                raise ValueError("Legend source page differs")
            _verified_file(directory, row["filename"], row["crop_sha256"], 5 * 1024 * 1024)
            entry = f"pdf-{source_hash[:12]}:p{page_number}:{row['region_id']}"
            names.append(SymbolLegendWrite(class_id=0,
                         name=f"{row['proposed_label']} [{entry}]", is_active=True).name)
    if len(names) != 40 or len(set(names)) != 40:
        raise ValueError("Catalog identities differ")
    return tuple(names)
