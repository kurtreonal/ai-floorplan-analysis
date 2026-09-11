"""Build a private U5 gold manifest using database-backed PRE10 authority."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.floor_plan_interpretation import (  # noqa: E402
    ApproverAuthoritySnapshot,
    GoldEvaluationError,
    GoldManifestRequest,
    build_gold_manifest,
)
from app.core.database import DatabaseConfigurationError, get_session_factory  # noqa: E402
from app.repositories.dataset_approver_assignment_repository import list_assignments  # noqa: E402


MAX_DEFINITION_BYTES = 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an immutable private VLM gold-evaluation manifest.")
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--definition", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        private_root = args.private_root.resolve(strict=True)
        if args.private_root.is_symlink() or not private_root.is_dir() or args.definition.is_symlink():
            raise ValueError
        definition = args.definition.resolve(strict=True)
        definition.relative_to(private_root)
        if not definition.is_file() or definition.stat().st_size > MAX_DEFINITION_BYTES:
            raise ValueError
        definition_raw = definition.read_bytes()
        if len(definition_raw) > MAX_DEFINITION_BYTES:
            raise ValueError
        request = GoldManifestRequest.model_validate_json(definition_raw)
        with get_session_factory()() as session:
            authorities = tuple(
                ApproverAuthoritySnapshot(
                    assignment_id=row.id,
                    assignee_user_id=row.assignee_user_id,
                    assigned_by_user_id=row.assigned_by_user_id,
                    authority_scope=row.authority_scope,
                    active_from=row.active_from,
                    inactive_at=row.inactive_at,
                    is_active=row.active_marker is True,
                )
                for row in list_assignments(session)
            )
        result = build_gold_manifest(private_root=private_root, manifest_path=args.manifest, request=request, authorities=authorities)
    except (DatabaseConfigurationError, GoldEvaluationError, OSError, SQLAlchemyError, ValueError):
        print("Gold manifest failed validation.", file=sys.stderr)
        return 2
    print(f"revision={request.revision} records={result.record_count} eligible_development={result.eligible_development_count} eligible_sealed={result.eligible_sealed_count} changed={str(result.changed).lower()} manifest_sha256={result.manifest_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
