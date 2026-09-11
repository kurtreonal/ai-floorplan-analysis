"""Build a private U4 legend/reference pack from the active local catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.ai.floor_plan_interpretation import (  # noqa: E402
    CatalogLegendSnapshot,
    LegendReferencePackError,
    LegendReferencePackRequest,
    build_legend_reference_pack,
)
from app.core.database import (  # noqa: E402
    DatabaseConfigurationError,
    get_session_factory,
)
from app.services.symbol_legend_service import (  # noqa: E402
    SymbolLegendServiceError,
    retrieve_all_symbol_legends,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an immutable private VLM legend/reference pack."
    )
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--definition", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    arguments = parser.parse_args()

    try:
        private_root = arguments.private_root.resolve(strict=True)
        if arguments.private_root.is_symlink() or not private_root.is_dir():
            raise ValueError
        if arguments.definition.is_symlink():
            raise ValueError
        definition = arguments.definition.resolve(strict=True)
        definition.relative_to(private_root)
        if not definition.is_file() or definition.stat().st_size > 1024 * 1024:
            raise ValueError
        request = LegendReferencePackRequest.model_validate_json(
            definition.read_text(encoding="utf-8")
        )
        with get_session_factory()() as database_session:
            catalog = tuple(
                CatalogLegendSnapshot(
                    id=record.id,
                    class_id=record.class_id,
                    name=record.name,
                    is_active=record.is_active,
                )
                for record in retrieve_all_symbol_legends(database_session)
            )
        result = build_legend_reference_pack(
            private_root=private_root,
            manifest_path=arguments.manifest,
            request=request,
            catalog=catalog,
        )
    except (
        DatabaseConfigurationError,
        LegendReferencePackError,
        OSError,
        SQLAlchemyError,
        SymbolLegendServiceError,
        ValueError,
    ):
        print("Legend/reference pack failed validation.", file=sys.stderr)
        return 2

    print(
        f"version={request.version} classes={result.class_count} "
        f"glyphs={result.glyph_count} mappings={result.drawing_mapping_count} "
        f"unknown={result.unknown_glyph_count} changed={str(result.changed).lower()} "
        f"manifest_sha256={result.manifest_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
