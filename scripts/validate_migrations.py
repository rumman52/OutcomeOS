#!/usr/bin/env python3
"""Perform deterministic structural checks without requiring a live database."""

from pathlib import Path
import re

MIGRATIONS = Path(__file__).parents[1] / "infra" / "migrations"
NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def main() -> None:
    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        raise SystemExit("no migrations found")
    versions: list[str] = []
    for path in files:
        match = NAME.fullmatch(path.name)
        if match is None:
            raise SystemExit(f"invalid migration name: {path.name}")
        versions.append(match.group(1))
        sql = path.read_text(encoding="utf-8").strip().upper()
        if not (sql.startswith("BEGIN;") and sql.endswith("COMMIT;")):
            raise SystemExit(f"migration must be transactional: {path.name}")
    if len(versions) != len(set(versions)):
        raise SystemExit("duplicate migration version")
    print(f"validated {len(files)} migration(s)")


if __name__ == "__main__":
    main()
