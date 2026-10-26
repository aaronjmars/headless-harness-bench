#!/usr/bin/env python3
"""Persist and scrub live Tier-2 captures without assigning the human's rubric scores.

The CLI is called by the existing shell and Node launchers. Each call is independent;
file locking serializes background trial completions within one sweep.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from bench_kit import ledger, runcheck, scrub

ROOT = Path(__file__).resolve().parents[1]
ENV_PATTERNS = ("*_API_KEY", "*_TOKEN", "*_SECRET", "*_PASSWORD", "*_AUTH")
CREDENTIAL_FIELDS = re.compile(r"(?:key|token|secret|password|credential|authorization|refresh)", re.I)
PATTERN = runcheck.compile_patterns()
TRUSTED_PATTERN = runcheck.compile_patterns((r"\b401\b",))
DIAGNOSTIC = re.compile(r"^\s*(?:Error:|Caused by:|\d+:|HTTP\s+401|401\b|invalid[ _-]?api[ _-]?key|bad credentials|authentication_error|not logged in|token (?:has been|was) revoked)", re.I)


def secret_values() -> list[tuple[str, str]]:
    values = scrub.values_from_env(ENV_PATTERNS)
    # A harness can load a credential from its isolated profile instead of the env.
    # Only scoped auth/config files are read; neither their paths nor values enter the ledger.
    for name in ("PI_CODING_AGENT_DIR", "CODEX_HOME", "DSH_HOME", "TIER2_AUTH_DIR"):
        directory = os.environ.get(name)
        if not directory:
            continue
        files = (file for sub in ("", ".eve", ".fx", ".codex", "profiles") for file in (Path(directory) / sub).glob("*"))
        for file in files:
            if not file.is_file() or file.name not in ("auth.json", "oauth.json", "config.json", "settings.json", ".env"):
                continue
            if file.name == ".env":
                values.extend((value, name + "_CREDENTIAL") for value, label in scrub.values_from_file(file) if CREDENTIAL_FIELDS.search(label))
                continue
            data = json.loads(file.read_text())
            def visit(node, field=""):
                if isinstance(node, dict):
                    for key, val in node.items():
                        visit(val, key)
                elif isinstance(node, list):
                    for val in node:
                        visit(val, field)
                elif isinstance(node, str) and CREDENTIAL_FIELDS.search(field):
                    values.append((node, name + "_CREDENTIAL"))
            visit(data)
    # Values obtained from pass/OAuth but not kept in an isolated profile can be
    # supplied as exported env vars; nothing is written to an intermediate values file.
    return values


def checked_scrub(paths: list[Path], values: list[tuple[str, str]]) -> None:
    for path in paths:
        if path.exists() and path.is_file():
            path.read_bytes().decode("utf-8")
    scrub.scrub(paths, values)
    remaining = scrub.scrub(paths, values, check=True)
    if remaining.hits:
        raise RuntimeError("secret-value scrub did not clear all run files")


@contextmanager
def locked(sweep: str):
    lock = ROOT / "data" / "sweeps" / (sweep + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def evidence_error(path: Path) -> bool:
    """Check only harness-emitted top-level errors, never model text/tool output."""
    if not path.exists():
        return False
    for line in path.read_text(errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        kind = str(obj.get("type", obj.get("event", ""))).lower()
        message = obj.get("message")
        if kind in ("message_start", "message_end", "turn_end") and isinstance(message, dict):
            if message.get("role") == "assistant" and message.get("stopReason") == "error":
                if runcheck.auth_hits(str(message.get("errorMessage", "")), TRUSTED_PATTERN):
                    return True
            continue
        if kind not in ("error", "run.error", "run.failed", "provider_error", "api_error", "auth_error") and not kind.endswith(".error") and not (obj.get("status") == "failed" and obj.get("error")):
            continue
        error = obj.get("error")
        trusted = error if isinstance(error, (str, dict)) else {key: obj[key] for key in ("message", "error_class", "status_code") if key in obj}
        if runcheck.auth_hits(json.dumps(trusted), TRUSTED_PATTERN):
            return True
    return False

def trial_status(out: Path, name: str, rc: int, expected_cancel: bool = False) -> tuple[str, dict | None, str]:
    # .err is the harness's diagnostic stream, not a task transcript. Structured
    # JSONL is restricted to provider error events. A quoted target 401 in an
    # assistant/tool event is never classified as provider authentication failure.
    diagnostic = out / (name + ".err")
    diagnostic_hits = runcheck.auth_hits(
        "\n".join(line for line in diagnostic.read_text(errors="replace").splitlines() if DIAGNOSTIC.match(line)),
        PATTERN,
    ) if diagnostic.exists() else []
    capture = next((out / (name + ext) for ext in (".jsonl", ".out", ".json") if (out / (name + ext)).is_file()), None)
    auth = bool(diagnostic_hits) or (capture is not None and evidence_error(capture))
    if auth:
        return "errored", {"source": "infra", "type": "auth", "message": "provider authentication failed"}, ""
    if capture is None:
        return "errored", {"source": "infra", "type": "incomplete", "message": "missing harness capture"}, ""
    if rc != 0 and not expected_cancel:
        return "errored", {"source": "infra", "type": "process", "message": f"harness exit {rc}"}, ""
    return "skipped", None, "capture complete; pending human rubric score"


def record(args) -> bool:
    out = Path(args.out).resolve()
    if not out.is_dir():
        raise FileNotFoundError(f"missing evidence directory: {out}")
    values = secret_values()
    paths = [out / (args.name + ext) for ext in (".jsonl", ".json", ".out", ".err", ".log", ".rc")]
    # Scrub the trial immediately even if checking the harness output fails.
    try:
        status, error, note = trial_status(out, args.name, args.rc, getattr(args, "expected_cancel", False))
    finally:
        checked_scrub(paths, values)
    with locked(args.sweep):
        lp = ledger.ledger_path(ROOT, args.sweep)
        old = json.loads(lp.read_text())
        if old["status"] == "halted":
            halt = old["halted"]
        else:
            halt = None
        row = {"run_id": None, "sample_id": args.name, "subject": args.subject,
               "repeat": 1, "status": status, "score": None, "is_correct": None,
               "error": error, "note": note or None, "credential": args.credential,
               "finished_at": datetime.now(timezone.utc).isoformat()}
        rows = [*old["records"], row]
        streak = 0
        for item in sorted(rows, key=lambda r: r.get("finished_at", ""), reverse=True):
            if item.get("credential") != args.credential:
                continue
            if item.get("error", {}) and item["error"].get("type") == "auth":
                streak += 1
            else:
                break
        if streak >= 3:
            halt = f"3 consecutive provider auth failures on {args.credential}"
        ledger.write(ROOT, args.sweep, records=[row], status="halted" if halt else "running", halted=halt)
        checked_scrub([lp], values)
    if halt:
        print("sweep halted: provider authentication failures", file=sys.stderr)
    return halt is not None


def finish(args) -> bool:
    values = secret_values()
    out = Path(args.out).resolve()
    lp = ledger.ledger_path(ROOT, args.sweep)
    try:
        with locked(args.sweep):
            current = json.loads(lp.read_text())
            status = "halted" if current["status"] == "halted" else ("finished" if args.rc == 0 else "stopped")
            ledger.write(ROOT, args.sweep, status=status)
    finally:
        started = datetime.fromisoformat(json.loads(lp.read_text())["started_at"].replace("Z", "+00:00")).timestamp()
        direct = [p for p in out.iterdir() if p.is_file() and p.suffix in (".jsonl", ".json", ".out", ".err", ".log", ".rc") and p.stat().st_mtime >= started - 1]
        checked_scrub([*direct, lp], values)
    return status == "halted"


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("start")
    start.add_argument("--sweep")
    trial = sub.add_parser("trial")
    end = sub.add_parser("finish")
    for p in (trial, end):
        p.add_argument("--sweep", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--rc", type=int, required=True)
    trial.add_argument("--name", required=True)
    trial.add_argument("--subject", required=True)
    trial.add_argument("--credential", default="provider")
    trial.add_argument("--expected-cancel", action="store_true")
    args = parser.parse_args()
    if args.action == "start":
        sweep = args.sweep or datetime.now(timezone.utc).strftime("%Y-%m-%d-tier2-%H%M%S-%f")
        with locked(sweep):
            if ledger.ledger_path(ROOT, sweep).exists():
                raise ValueError("sweep id already exists")
            lp = ledger.write(ROOT, sweep, status="running")
            if ledger.ignored(ROOT, [str(lp.relative_to(ROOT))]):
                lp.unlink()
                raise ValueError("sweep ledger path is gitignored")
        print(sweep)
    elif args.action == "trial":
        if record(args):
            raise SystemExit(3)
    elif finish(args):
        raise SystemExit(3)


if __name__ == "__main__":
    main()
