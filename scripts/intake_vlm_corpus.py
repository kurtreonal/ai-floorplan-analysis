"""Build a private U3 corpus manifest without printing source metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.ai.floor_plan_interpretation import (  # noqa: E402
    CorpusIntakeError,
    CorpusIntakeRequest,
    build_private_corpus_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a private local VLM corpus manifest.")
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        raw = json.loads(arguments.requests.read_text(encoding="utf-8"))
        if type(raw) is not list:
            raise ValueError
        requests = tuple(CorpusIntakeRequest.model_validate(item) for item in raw)
        result = build_private_corpus_manifest(
            private_root=arguments.private_root,
            manifest_path=arguments.manifest,
            requests=requests,
        )
    except (CorpusIntakeError, OSError, ValueError):
        print("Private corpus intake failed validation.", file=sys.stderr)
        return 2
    print(
        f"records={result.record_count} blueprints={result.blueprint_source_count} "
        f"eligible_blueprint_sources={result.eligible_blueprint_source_count} "
        f"eligible_drawing_groups={result.eligible_blueprint_drawing_group_count} "
        f"independent_blueprint_projects={result.independent_eligible_blueprint_project_count} "
        f"references={result.reference_material_count} "
        f"eligible_references={result.eligible_reference_material_count} "
        f"exact_duplicate_groups={result.exact_duplicate_groups} "
        f"near_duplicate_pairs={result.near_duplicate_pairs} changed={str(result.changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
