"""Validate public environment templates and prevent tracked private env files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROOT_TEMPLATE = REPOSITORY_ROOT / ".env.example"
REQUIRED_KEYS = frozenset(
    {
        "APP_ENV",
        "APP_DEBUG",
        "DATABASE_URL",
        "OAUTH_PROVIDER",
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "OAUTH_REDIRECT_URI",
        "OAUTH_DISCOVERY_URL",
        "OAUTH_SCOPES",
        "SESSION_SECRET",
        "CORS_ALLOWED_ORIGINS",
    }
)
PLACEHOLDER_KEYS = frozenset(
    {
        "DATABASE_URL",
        "OAUTH_PROVIDER",
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "OAUTH_DISCOVERY_URL",
        "SESSION_SECRET",
    }
)
PLACEHOLDER_MARKERS = ("change_me", "configure_me", "replace_me")
FORBIDDEN_CONTENT = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[oprsu]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
)


def parse_template(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path.name}:{line_number} is not KEY=VALUE syntax.")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise ValueError(f"{path.name}:{line_number} has an invalid or duplicate key.")
        values[key] = value.strip().strip('"').strip("'")
    return values


def tracked_private_environment_files() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    tracked_paths = result.stdout.decode("utf-8").split("\0")
    private_paths = []
    for raw_path in tracked_paths:
        if not raw_path:
            continue
        path = PurePosixPath(raw_path)
        name = path.name
        if name == ".env" or (
            name.startswith(".env.") and name != ".env.example"
        ):
            private_paths.append(raw_path)
    return tuple(private_paths)


def validate() -> tuple[str, ...]:
    errors: list[str] = []
    try:
        values = parse_template(ROOT_TEMPLATE)
    except (OSError, ValueError) as error:
        return (str(error),)

    missing = sorted(REQUIRED_KEYS - values.keys())
    if missing:
        errors.append(f".env.example is missing: {', '.join(missing)}")

    if values.get("APP_ENV") != "production":
        errors.append("APP_ENV must default to production in .env.example.")
    if values.get("APP_DEBUG", "").casefold() != "false":
        errors.append("APP_DEBUG must default to false in .env.example.")
    if "openid" not in values.get("OAUTH_SCOPES", "").split():
        errors.append("OAUTH_SCOPES must include openid.")

    for key in sorted(PLACEHOLDER_KEYS):
        value = values.get(key, "").casefold()
        if value and not any(marker in value for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{key} must contain an obvious public placeholder.")

    template_text = ROOT_TEMPLATE.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_CONTENT:
        if pattern.search(template_text):
            errors.append(f".env.example matches forbidden secret pattern: {pattern.pattern}")

    private_files = tracked_private_environment_files()
    if private_files:
        errors.append(
            "Private environment files are tracked: " + ", ".join(private_files)
        )
    return tuple(errors)


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Environment template validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
