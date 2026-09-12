"""Run backend tests only against the empty, restricted verification database."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def main():
    root = Path(__file__).resolve().parents[1]
    engine = None
    try:
        values = dotenv_values(root / ".env")
        url = make_url(os.environ.get("TEST_DATABASE_URL") or values.get("TEST_DATABASE_URL") or "")
        if (url.drivername != "mysql+pymysql" or url.username != "ved_test"
                or url.database != "ved_electrical_verify"
                or url.host not in ("localhost", "127.0.0.1")):
            raise ValueError("Unexpected verification target")
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as connection:
            grants = [row.split(" TO ")[0] for row in connection.execute(text("SHOW GRANTS")).scalars()]
            allowed = {"GRANT USAGE ON *.*", "GRANT ALL PRIVILEGES ON `ved_electrical_verify`.*"}
            if not grants or not set(grants).issubset(allowed):
                raise ValueError("Test credentials are not restricted")
            tables = inspect(connection).get_table_names()
            for name in tables:
                quoted = engine.dialect.identifier_preparer.quote(name)
                count = connection.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one()
                if name != "roles" and count:
                    raise ValueError("Verification database contains existing records")
            roles = connection.execute(text("SELECT name FROM roles ORDER BY name")).scalars().all()
            if roles != ["ADMIN", "DESIGNER"]:
                raise ValueError("Expected seeded roles missing")
    except Exception:
        print("Isolation preflight failed; no tests started. Check the private test configuration and database contents.", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()

    with tempfile.TemporaryDirectory(prefix="ved-verification-") as directory:
        environment = os.environ.copy()
        environment["DATABASE_URL"] = url.render_as_string(hide_password=False)
        environment["AUTO_START_DEMO_WORKER"] = "false"
        for name in ("UPLOAD_DIR", "PROCESSED_DIR", "DETECTION_DIR", "PREVIEW_DIR", "REPORT_DIR"):
            environment[name] = str(Path(directory) / name.lower())
        print("Isolation preflight passed: restricted verification account, empty data tables, temporary storage.", flush=True)
        return subprocess.call(
            [sys.executable, "-m", "pytest", *(sys.argv[1:] or ["-q"])],
            cwd=root / "backend", env=environment,
        )


if __name__ == "__main__":
    raise SystemExit(main())
