"""Backed-up local account/profile or explicitly selected project-only reset."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

from dotenv import dotenv_values, set_key
from sqlalchemy import MetaData, Table, delete, func, inspect, select, update


ROOT = Path(__file__).resolve().parents[1]
TEST_PROVIDER = re.compile(r"(?:f[23]-test|h3-test|(?:u9|j1|j5)-[0-9a-f]{28,32})\Z")
TEST_ROLE = re.compile(r"(?:F[23]_TEST_[0-9A-F]{8}|J[15]_[0-9A-F]{20})\Z")
PROJECT_DATA_TABLES = frozenset({
    "projects", "project_floors", "floor_plans", "floor_plan_sources", "floor_plan_pages",
    "processing_jobs", "processing_job_attempts", "processing_job_cancellations", "processing_artifacts",
    "processing_drawing_selections",
    "interpretation_page_outcomes", "floor_plan_interpretation_runs", "floor_plan_interpretation_reviews",
    "walls", "detected_symbols", "detection_reviews", "detection_class_corrections", "manual_symbols",
    "layout_versions", "layout_save_requests", "page_scale_settings", "floor_elevation_settings",
    "generated_route_versions", "estimates", "estimate_items", "estimate_sources",
})


def project_deletion_order(connection):
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    if "projects" not in names:
        raise RuntimeError("Project table missing; reset refused")
    parents = {name: {fk["referred_table"] for fk in inspector.get_foreign_keys(name)} for name in names}
    selected = {"projects"}
    while True:
        expanded = selected | {name for name in names if parents[name] & selected}
        if expanded == selected:
            break
        selected = expanded
    if selected - PROJECT_DATA_TABLES or (PROJECT_DATA_TABLES & names) - selected:
        raise RuntimeError("Unreviewed or disconnected project dependency; reset refused")
    order = []
    remaining = set(selected)
    while remaining:
        leaves = sorted(name for name in remaining if not any(
            name in parents[child] for child in remaining))
        if not leaves:
            raise RuntimeError("Cyclic project references; reset refused")
        order.extend(leaves)
        remaining.difference_update(leaves)
    return order


def reset_project_data(connection, *, apply=False):
    """Clear only explicitly reviewed project-owned tables, with FKs enabled."""
    order = project_deletion_order(connection)
    metadata = MetaData()
    tables = {name: Table(name, metadata, autoload_with=connection) for name in order}
    counts = {name: connection.scalar(select(func.count()).select_from(table))
              for name, table in tables.items()}
    if apply:
        for name in order:
            connection.execute(delete(tables[name]))
        if any(connection.scalar(select(func.count()).select_from(table)) for table in tables.values()):
            raise RuntimeError("Project records remain; rolling back")
    return {"project_records_removed": counts, "total_rows_removed": sum(counts.values()),
            "projects_after": 0 if apply else counts["projects"],
            "account_and_catalog_changes": False, "filesystem_deletions": False}


def artifact_inventory():
    """Metadata-only check; no dataset or checkpoint content is opened or altered."""
    result = {}
    for relative in ("storage/training", "models"):
        directory = ROOT / relative
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file():
                    stat = path.stat()
                    result[str(path.relative_to(ROOT))] = (stat.st_size, stat.st_mtime_ns)
    return result


def original_fingerprints():
    from app.core.config import get_upload_directory
    directory = get_upload_directory() / "originals"
    result = {}
    for path in directory.rglob("*"):
        if path.is_file():
            with path.open("rb") as source:
                result[str(path)] = hashlib.file_digest(source, "sha256").hexdigest()
    return result


def referenced_ids(connection, target, *, skip_tables=()):
    """Inspect live constraints, including references outside the ORM models."""
    inspector = inspect(connection)
    metadata = MetaData()
    referenced = set()
    for name in inspector.get_table_names():
        if name in skip_tables:
            continue
        for constraint in inspector.get_foreign_keys(name):
            if constraint["referred_table"] != target:
                continue
            if constraint["referred_columns"] != ["id"]:
                raise RuntimeError("Unsupported account reference; reset refused")
            table = Table(name, metadata, autoload_with=connection, extend_existing=True)
            column = table.c[constraint["constrained_columns"][0]]
            referenced.update(connection.scalars(select(column).where(column.is_not(None))))
    return referenced


def reset_accounts(connection, *, provider, apply=False):
    metadata = MetaData()
    users = Table("users", metadata, autoload_with=connection)
    roles = Table("roles", metadata, autoload_with=connection)
    role_rows = list(connection.execute(select(roles)).mappings())
    if not {"ADMIN", "DESIGNER"}.issubset({row["name"] for row in role_rows}):
        raise RuntimeError("Core roles missing; reset refused")
    rows = list(connection.execute(select(users).with_for_update()).mappings())
    role_ids = {row["id"] for row in role_rows}
    if any(row["role_id"] not in role_ids for row in rows):
        raise RuntimeError("Invalid account role; reset refused")
    referenced = referenced_ids(connection, "users")
    removable = [row["id"] for row in rows if row["id"] not in referenced
                 and row["oauth_provider"] != provider
                 and TEST_PROVIDER.fullmatch(row["oauth_provider"])]
    retained = [row for row in rows if row["id"] not in removable]
    used_roles = {row["role_id"] for row in retained} | referenced_ids(connection, "roles", skip_tables={"users"})
    removable_roles = [row["id"] for row in role_rows
                       if row["id"] not in used_roles and TEST_ROLE.fullmatch(row["name"])]
    summary = {
        "accounts_before": len(rows), "accounts_after": len(retained),
        "profiles_reset": len(retained), "unused_test_accounts_removed": len(removable),
        "unused_test_roles_removed": len(removable_roles),
        "retained_referenced_test_accounts": sum(
            bool(TEST_PROVIDER.fullmatch(row["oauth_provider"]))
            and row["oauth_provider"] != provider for row in retained),
        "identity_and_role_mappings_preserved": True,
    }
    if apply:
        if removable:
            connection.execute(delete(users).where(users.c.id.in_(removable)))
        connection.execute(update(users).values(email=None, display_name=None, avatar_url=None))
        if removable_roles:
            connection.execute(delete(roles).where(roles.c.id.in_(removable_roles)))
    return summary


def non_account_fingerprints(connection, *, skip_tables=None):
    """Private integrity evidence: hash every unaffected table, without logging rows."""
    metadata = MetaData()
    result = {}
    for name in inspect(connection).get_table_names():
        if name in (skip_tables if skip_tables is not None else {"users", "roles"}):
            continue
        table = Table(name, metadata, autoload_with=connection)
        rows = [json.dumps(dict(row), sort_keys=True, default=str)
                for row in connection.execute(select(table)).mappings()]
        result[name] = {"rows": len(rows), "sha256": hashlib.sha256(
            "\n".join(sorted(rows)).encode()).hexdigest()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and apply the selected reset")
    parser.add_argument("--projects-only", action="store_true", help="Clear project-owned database records only; preserve accounts, sessions and datasets")
    parser.add_argument("--mysqldump", type=Path, default=Path("C:/xampp/mysql/bin/mysqldump.exe"))
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.config import get_settings
    from app.core.database import get_engine

    settings = get_settings()
    engine = get_engine()
    backup = None
    try:
        if (settings.app_env != "development" or engine.url.host not in {"localhost", "127.0.0.1"}
                or engine.url.database != "ved_electrical" or not settings.oauth_provider):
            raise RuntimeError("Unexpected target; reset refused")
        if not args.projects_only and os.environ.get("SESSION_SECRET"):
            raise RuntimeError("Session secret environment override; restart configuration must be reconciled")
        env_file = ROOT / ".env"
        values = dotenv_values(env_file)
        if not values.get("SESSION_SECRET"):
            raise RuntimeError("Private session configuration unavailable")
        if not args.apply:
            with engine.connect() as connection:
                print(json.dumps(reset_project_data(connection) if args.projects_only else
                                 reset_accounts(connection, provider=settings.oauth_provider)))
            return 0
        if not args.mysqldump.is_file():
            raise RuntimeError("Backup tool unavailable")
        backup = ROOT / "storage/reports" / (("project-reset-" if args.projects_only else "account-reset-")
                 + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        backup.mkdir(parents=True, exist_ok=False)
        dump = backup / "database.sql"
        environment = os.environ.copy()
        environment["MYSQL_PWD"] = engine.url.password or ""
        command = [str(args.mysqldump), "--protocol=tcp", "--single-transaction", "--skip-lock-tables",
                   "--hex-blob", "--default-character-set=utf8mb4", "--host=" + engine.url.host,
                   "--port=" + str(engine.url.port or 3306), "--user=" + engine.url.username,
                   "--result-file=" + str(dump), engine.url.database]
        completed = subprocess.run(command, env=environment, capture_output=True, timeout=120)
        if completed.returncode or not dump.is_file() or dump.stat().st_size == 0:
            raise RuntimeError("Backup failed; no reset performed")
        shutil.copy2(env_file, backup / "configuration.env")
        protected = artifact_inventory() if args.projects_only else None
        originals = original_fingerprints() if args.projects_only else None
        rotated = False
        try:
            with engine.begin() as connection:
                skip = set(project_deletion_order(connection)) if args.projects_only else {"users", "roles"}
                before = non_account_fingerprints(connection, skip_tables=skip)
                summary = (reset_project_data(connection, apply=True) if args.projects_only else
                           reset_accounts(connection, provider=settings.oauth_provider, apply=True))
                if before != non_account_fingerprints(connection, skip_tables=skip):
                    raise RuntimeError("Unrelated data changed; rolling back")
                if args.projects_only:
                    if protected != artifact_inventory() or originals != original_fingerprints():
                        raise RuntimeError("Protected files changed; rolling back")
                    summary.update({"dataset_model_file_metadata_unchanged": True,
                                    "protected_dataset_model_files": len(protected),
                                    "original_file_hashes_unchanged": True, "original_files_checked": len(originals)})
                else:
                    rotated = True
                    set_key(str(env_file), "SESSION_SECRET", secrets.token_urlsafe(48))
        except BaseException:
            if rotated:
                shutil.copy2(backup / "configuration.env", env_file)
            raise
        summary.update({"sessions_revoked_after_backend_restart": not args.projects_only,
                        "unrelated_table_fingerprints_unchanged": True,
                        "database_backup_sha256": hashlib.sha256(dump.read_bytes()).hexdigest()})
        (backup / "reset-result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary))
        print("Private recovery backup: " + str(backup))
        return 0
    except Exception as error:
        # Driver errors and subprocess output may contain credentials or private data.
        print("Reset stopped safely (" + type(error).__name__ + "). No credential details printed.", file=sys.stderr)
        if backup:
            print("Private recovery backup: " + str(backup), file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
