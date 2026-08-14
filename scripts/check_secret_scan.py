"""Compare a detect-secrets scan with its reviewed baseline without printing values."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_results(path: Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("results", {})


def identity(filename: str, finding: dict[str, Any]) -> tuple[str, str, str]:
    return filename, finding["type"], finding["hashed_secret"]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_secret_scan.py BASELINE SCAN", file=sys.stderr)
        return 2

    baseline = load_results(Path(sys.argv[1]))
    scan = load_results(Path(sys.argv[2]))
    reviewed = {
        identity(filename, finding)
        for filename, findings in baseline.items()
        for finding in findings
        if finding.get("is_secret") is False
    }
    unreviewed = [
        (filename, finding)
        for filename, findings in scan.items()
        for finding in findings
        if identity(filename, finding) not in reviewed
    ]

    if not unreviewed:
        print("Secret scan passed: no unreviewed findings in Git-tracked files.")
        return 0

    print(
        "Secret scan failed with unreviewed findings (candidate values redacted):",
        file=sys.stderr,
    )
    for filename, finding in sorted(
        unreviewed, key=lambda item: (item[0], item[1]["line_number"], item[1]["type"])
    ):
        print(
            f"{filename}:{finding['line_number']}: {finding['type']}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
