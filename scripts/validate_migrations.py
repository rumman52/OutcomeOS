"""Validate basic Alembic migration hygiene for local checks."""

from __future__ import annotations

import ast
from pathlib import Path

MIGRATIONS_DIR = Path("apps/api/migrations/versions")


def _constant_string(module: ast.Module, name: str) -> str | None:
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = statement.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value
    return None


def _function_names(module: ast.Module) -> set[str]:
    return {statement.name for statement in module.body if isinstance(statement, ast.FunctionDef)}


def main() -> int:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.py"))
    if not migration_files:
        raise SystemExit(f"No Alembic migration files found in {MIGRATIONS_DIR}")

    revisions: dict[str, Path] = {}
    for path in migration_files:
        module = ast.parse(path.read_text(), filename=str(path))
        revision = _constant_string(module, "revision")
        if revision is None:
            raise SystemExit(f"{path} is missing a string revision identifier")
        if revision in revisions:
            raise SystemExit(f"Duplicate Alembic revision {revision!r}: {revisions[revision]} and {path}")
        revisions[revision] = path

        functions = _function_names(module)
        missing = {"upgrade", "downgrade"} - functions
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise SystemExit(f"{path} is missing required migration function(s): {missing_list}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
