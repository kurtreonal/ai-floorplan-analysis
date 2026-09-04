import argparse

from sqlalchemy.orm import Session

from app.core.config import get_max_upload_size_bytes, get_upload_directory
from app.core.database import get_engine
from app.repositories.floor_plan_source_repository import (
    list_floor_plans_with_source_identity,
)
from app.services.source_identity import (
    SourceIdentityError,
    persist_source_identity,
    verify_existing_floor_plan_source,
)


def backfill_floor_plan_sources(database_session: Session, *, apply: bool) -> int:
    upload_directory = get_upload_directory()
    max_file_size_bytes = get_max_upload_size_bytes()
    created = 0
    try:
        for floor_plan in list_floor_plans_with_source_identity(database_session):
            verified = verify_existing_floor_plan_source(
                floor_plan=floor_plan,
                upload_directory=upload_directory,
                max_file_size_bytes=max_file_size_bytes,
            )
            source = floor_plan.source_manifest
            if source is None:
                persist_source_identity(
                    database_session,
                    floor_plan=floor_plan,
                    identity=verified,
                )
                created += 1
                continue
            page_numbers = [page.page_number for page in source.pages]
            if (
                source.original_sha256 != verified.original_sha256
                or page_numbers != list(range(1, verified.page_count + 1))
            ):
                raise SourceIdentityError(
                    f"Floor plan {floor_plan.id} has conflicting source identity."
                )
        if apply:
            database_session.commit()
        else:
            database_session.rollback()
    except Exception:
        database_session.rollback()
        raise
    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify originals and backfill immutable floor-plan source/page identity."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit verified missing identities; default is a rollback-only dry run.",
    )
    arguments = parser.parse_args()
    with Session(get_engine(), expire_on_commit=False) as database_session:
        created = backfill_floor_plan_sources(database_session, apply=arguments.apply)
    mode = "applied" if arguments.apply else "verified (dry run)"
    print(f"Source identity {mode}: {created} missing floor-plan record(s).")


if __name__ == "__main__":
    main()
