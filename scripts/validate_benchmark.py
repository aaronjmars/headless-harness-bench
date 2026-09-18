#!/usr/bin/env python3
"""Validate the benchmark's published evidence without third-party packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


HARNESSES = ("omp", "pi", "fx", "opencode", "dsh", "crush", "flue", "eve")
SENSITIVE_NAMES = {
    ".env",
    "auth.json",
    "credentials.json",
    "grok-auth.json",
}


def _has_test_result(text: str, test_number: int) -> bool:
    """Return whether a Markdown table row has a populated result cell."""
    return bool(
        re.search(
            rf"^\s*\|\s*(?:\*{{1,2}})?T{test_number}\b[^|\n]*\|"
            r"\s*(?:\*{1,2})?[^|\s*]",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
    )


def _has_task_success_verdict(text: str) -> bool:
    """Return whether task success has an explicit table or heading verdict."""
    table_verdict = re.search(
        r"^\s*\|\s*(?:\*{1,2})?task[ -]success(?:\*{1,2})?\s*\|"
        r"\s*(?:\*{1,2})?[^|\s*]",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    heading_verdict = re.search(
        r"^\s*(?:#{1,6}\s*)?(?:\*{1,2})?task[ -]success(?:\*{1,2})?"
        r"\s*(?::|-)\s*(?:\*{1,2})?[^\s*]",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(table_verdict or heading_verdict)


def validate(root: Path) -> list[str]:
    """Return human-readable validation errors for a repository root."""
    errors: list[str] = []

    for name in ("README.md", "BENCHMARK.md"):
        if not (root / name).is_file():
            errors.append(f"missing required document: {name}")

    for harness in HARNESSES:
        result = root / "t2" / harness / "RESULT.md"
        if not result.is_file():
            errors.append(f"missing result report: {result.relative_to(root)}")
            continue

        text = result.read_text(encoding="utf-8")
        for test_number in range(1, 9):
            if not _has_test_result(text, test_number):
                errors.append(
                    f"{result.relative_to(root)}: missing T{test_number} result value"
                )
        if not _has_task_success_verdict(text):
            errors.append(f"{result.relative_to(root)}: missing task-success verdict")

    evidence_root = root / "t2"
    if evidence_root.is_dir():
        for path in sorted(evidence_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            normalized_name = path.name.lower()
            if normalized_name in SENSITIVE_NAMES or normalized_name.startswith(".env."):
                errors.append(f"credential-shaped file must not be published: {relative}")
            if path.stat().st_size == 0:
                # Empty captures are valid evidence for startup/cancellation failures.
                continue
            if path.suffix == ".json":
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(f"{relative}: invalid JSON ({exc})")
            elif path.suffix == ".jsonl":
                _validate_jsonl(path, relative, errors)

    return errors


def _validate_jsonl(path: Path, relative: Path, errors: list[str]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        errors.append(f"{relative}: invalid UTF-8 ({exc})")
        return

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{relative}:{line_number}: invalid JSONL ({exc.msg})")
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the script's parent repository)",
    )
    args = parser.parse_args(argv)
    errors = validate(args.root.resolve())
    if errors:
        print("benchmark validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"benchmark validation passed ({len(HARNESSES)} harnesses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
