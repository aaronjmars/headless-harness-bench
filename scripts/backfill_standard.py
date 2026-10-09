#!/usr/bin/env python3
"""Write the bench standard files (runs/<id>/manifest.json + samples.jsonl) for every run.

Bench standard: aaronjmars/bench-kit v0.2.0, STANDARD.md sections 4 and 5.

    python scripts/backfill_standard.py            # write runs/*/manifest.json + samples.jsonl
    python scripts/backfill_standard.py --check    # fail if the committed files drift from this script
    bench-kit stats && bench-kit render && bench-kit lint

The per-test scores are human judgments taken from t2/<harness>/RESULT.md and the
published tables (now in docs/2026-10-04-harness-comparison.md). The golden-task tokens
and cost are recomputed from the raw evidence under t2/ wherever it was committed, and
checked against the published numbers; a mismatch stops the script.

Fields owned by bench-kit stats (evaluation_results for computed metrics, errors.n/of/by_source,
token_usage) are kept from the existing manifest, so rerun bench-kit stats after this script.
Stdlib only, like scripts/validate_benchmark.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "aaronjmars/headless-harness-bench"
BENCH = "headless-harness-bench"
TASKSET = "1-A"
TESTS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
TEST_NAMES = {
    "T1": "Boot-to-JSON",
    "T2": "Structured-parse",
    "T3": "Tool-allowlist honored",
    "T4": "System-prompt injection",
    "T5": "Env isolation",
    "T6": "Cancel / no orphan",
    "T7": "Error machine-readable",
    "golden": "Golden task (task success + T8 cost and wall time)",
}
STATS_OWNED = ("evaluation_results", "errors", "token_usage")
QWEN = {"id": "qwen/qwen3.7-flash", "developer": "alibaba", "inference_platform": "openrouter"}

# --------------------------------------------------------------------------- raw evidence readers


def jsonl(path: str) -> list[dict]:
    return [json.loads(x) for x in (ROOT / path).read_text().splitlines() if x.strip()]


def usage_pi_style(path: str) -> dict:
    """omp and pi: usage per assistant message_end, summed over turns."""
    t = {"input_tokens": 0, "output_tokens": 0, "input_tokens_cache_read": 0, "usd": 0.0}
    for e in jsonl(path):
        m = e.get("message") or {}
        if e.get("type") == "message_end" and m.get("role") == "assistant" and m.get("usage"):
            u = m["usage"]
            t["input_tokens"] += u.get("input") or 0
            t["output_tokens"] += u.get("output") or 0
            t["input_tokens_cache_read"] += u.get("cacheRead") or 0
            t["usd"] += (u.get("cost") or {}).get("total") or 0
    return t


def usage_opencode(path: str) -> dict:
    t = {"input_tokens": 0, "output_tokens": 0, "input_tokens_cache_read": 0, "reasoning_tokens": 0, "usd": 0.0}
    for e in jsonl(path):
        if e.get("type") == "step_finish":
            p = e["part"]
            tk = p.get("tokens") or {}
            t["input_tokens"] += tk.get("input") or 0
            t["output_tokens"] += tk.get("output") or 0
            t["reasoning_tokens"] += tk.get("reasoning") or 0
            t["input_tokens_cache_read"] += (tk.get("cache") or {}).get("read") or 0
            t["usd"] += p.get("cost") or 0
    return t


# OpenRouter list prices for qwen/qwen3.7-flash, USD per million tokens (as quoted in t2/dsh/RESULT.md)
QWEN_PRICE = {"input": 0.03, "output": 0.13, "cache_read": 0.006}


def usage_dsh(path: str) -> dict:
    t = {"input_tokens": 0, "output_tokens": 0, "input_tokens_cache_read": 0}
    for e in jsonl(path):
        if e.get("type") == "status" and e.get("phase") == "step_end":
            u = e.get("usage") or {}
            t["input_tokens"] += u.get("inputTokens") or 0
            t["output_tokens"] += u.get("outputTokens") or 0
            t["input_tokens_cache_read"] += u.get("cacheReadTokens") or 0
    t["usd"] = (
        t["input_tokens"] * QWEN_PRICE["input"]
        + t["output_tokens"] * QWEN_PRICE["output"]
        + t["input_tokens_cache_read"] * QWEN_PRICE["cache_read"]
    ) / 1e6
    return t


def usage_nanocodex(path: str) -> dict:
    p = next(e["payload"] for e in jsonl(path) if e.get("type") == "run.completed")
    u = p["usage"]
    return {
        "input_tokens": u["input_tokens"],
        "output_tokens": u["output_tokens"],
        "input_tokens_cache_read": u["cached_input_tokens"],
        "reasoning_tokens": u["reasoning_output_tokens"],
        "usd": float(p["cost_usd"]),
    }


def usage_fx(path: str) -> dict:
    u = json.loads((ROOT / path).read_text())["usage"]
    return {"input_tokens": u["input_tokens"], "output_tokens": u["output_tokens"], "usd": None}


def usage_eve(path: str) -> dict:
    a = json.loads((ROOT / path).read_text())[0]["spans"][0]["attributes"]
    return {"input_tokens": a["agent.usage.input_tokens"], "output_tokens": a["agent.usage.output_tokens"], "usd": None}


def check(label: str, got, want, places: int | None = None):
    ok = got == want if places is None else round(got, places) == round(want, places)
    if not ok:
        raise SystemExit(f"{label}: raw evidence gives {got}, published {want}")


# --------------------------------------------------------------------------- golden rows


def golden(h: str, **kw) -> dict:
    """Golden row inputs. usage = recomputed dict or None; published = numbers the docs print."""
    return {"harness": h, **kw}


def golden_omp():
    u = usage_pi_style("t2/omp/golden.jsonl")
    check("omp input", u["input_tokens"], 12283)
    check("omp output", u["output_tokens"], 801)
    check("omp cache read", u["input_tokens_cache_read"], 59392)
    check("omp usd", u["usd"], 0.000821, 6)
    return golden("omp", usage=u, wall_s=20.0, wall_method="process wall (time total)",
                  cost_source="omp native usage.cost.total, summed over assistant turns",
                  evidence=["t2/omp/golden.jsonl"])


def golden_pi_085():
    u = usage_pi_style("t2/pi/golden2.jsonl")
    check("pi 0.85.1 input", u["input_tokens"], 5154)
    check("pi 0.85.1 output", u["output_tokens"], 289)
    check("pi 0.85.1 cache read", u["input_tokens_cache_read"], 11776)
    check("pi 0.85.1 usd", u["usd"], 0.000263, 6)
    return golden("pi", usage=u, wall_s=6.1,
                  wall_method="agent-exec from message timestamps, excludes process boot (not the same method as the others)",
                  cost_source="pi native usage.cost.total, summed over assistant turns (t2/pi/analyze.py)",
                  evidence=["t2/pi/golden2.jsonl", "t2/pi/golden.jsonl (default thinking, hung, 0 events)"])


def golden_pi_102():
    u = usage_pi_style("t2/pi/v1.0.2/golden.jsonl")
    check("pi 1.0.2 input", u["input_tokens"], 4097)
    check("pi 1.0.2 output", u["output_tokens"], 310)
    check("pi 1.0.2 cache read", u["input_tokens_cache_read"], 10752)
    check("pi 1.0.2 usd", u["usd"], 0.000228, 6)
    return golden("pi", usage=u, wall_s=7.034, wall_method="process wall (t2/pi/v1.0.2/batch.log)",
                  cost_source="pi native usage.cost.total, summed over assistant turns",
                  evidence=["t2/pi/v1.0.2/golden.jsonl", "t2/pi/v1.0.2/batch.log"])


def golden_opencode():
    u = usage_opencode("t2/opencode/t1_run.jsonl")
    check("opencode input", u["input_tokens"], 24365)
    check("opencode output", u["output_tokens"], 372)
    check("opencode reasoning", u["reasoning_tokens"], 106)
    check("opencode usd", u["usd"], 0.001347, 6)
    return golden("opencode", usage=u, wall_s=28.35, wall_method="process wall",
                  cost_source="opencode native step_finish cost, summed over steps",
                  evidence=["t2/opencode/t1_run.jsonl"])


def golden_dsh():
    u = usage_dsh("t2/dsh/run1.jsonl")
    check("dsh input", u["input_tokens"], 9447)
    check("dsh output", u["output_tokens"], 357)
    check("dsh cache read", u["input_tokens_cache_read"], 25472)
    check("dsh usd", u["usd"], 0.00048, 5)
    return golden("dsh", usage=u, wall_s=27.0, wall_method="process wall, end to end",
                  cost_source="not emitted by dsh; computed from summed step_end usage x OpenRouter list prices",
                  evidence=["t2/dsh/run1.jsonl"])


def golden_crush():
    # crush run stdout is plain text; the session show --json capture was not committed.
    u = {"input_tokens": 26325, "output_tokens": 10, "usd": 0.00087278}
    return golden("crush", usage=u, wall_s=61.0, wall_method="process wall",
                  cost_source="crush session show --json meta.cost (published value; raw capture not committed)",
                  evidence=["t2/crush/RESULT.md"], raw_kept=False,
                  note="output tokens look last-turn only (session meta completion_tokens), treat as approximate")


def golden_fx():
    u = usage_fx("t2/fx/runA.json")
    check("fx input", u["input_tokens"], 86401)
    check("fx output", u["output_tokens"], 457)
    return golden("fx", usage=u, wall_s=21.0, wall_method="process wall",
                  cost_source="not emitted by fx ask --json; grok subscription, no per-token USD",
                  evidence=["t2/fx/runA.json"])


def golden_flue():
    return golden("flue", usage=None, wall_s=12.9, wall_method="process wall",
                  cost_source="not emitted by flue run --json (needs observe() or OTel in the agent)",
                  evidence=["t2/flue/golden.jsonl"])


def golden_eve():
    u = usage_eve("t2/eve/golden-trace.json")
    check("eve input", u["input_tokens"], 21896)
    check("eve output", u["output_tokens"], 831)
    return golden("eve", usage=u, wall_s=20.7, wall_method="process wall, steady state (106 s with the one-time docker image pull)",
                  cost_source="no USD off the Vercel AI Gateway; tokens from eve traces --json",
                  evidence=["t2/eve/golden-docker.out", "t2/eve/golden-trace.json"],
                  note="golden-trace.json is from an earlier golden session, not the golden-docker.out session")


def golden_nanocodex():
    u = usage_nanocodex("t2/nanocodex/golden.jsonl")
    check("nanocodex input", u["input_tokens"], 35157)
    check("nanocodex cached", u["input_tokens_cache_read"], 33280)
    check("nanocodex output", u["output_tokens"], 1210)
    check("nanocodex usd", u["usd"], 0.0020, 4)
    return golden("nanocodex", usage=u, wall_s=33.2, wall_method="process wall (t2/nanocodex/batch.log)",
                  cost_source="nanocodex cost_usd, client-estimated from its built-in price table",
                  evidence=["t2/nanocodex/golden.jsonl", "t2/nanocodex/batch.log"], input_includes_cache=True)


# --------------------------------------------------------------------------- per-test scores (0-3)
# (score, short finding, evidence files). Source: t2/<harness>/RESULT.md and the published Tier-2 table.

T2_SCORES = {
    "omp": {
        "T1": (3, "non-interactive, exit 0, 338 JSONL events", ["t2/omp/golden.jsonl"]),
        "T2": (3, "4/4 fields: text, tokens, native USD, ordered tool calls", ["t2/omp/golden.jsonl"]),
        "T3": (3, "--tools read: bash not found, write neutered, edit not offered (with --no-extensions --no-skills)", ["t2/omp/t3.jsonl"]),
        "T4": (2, "mechanism works (--system-prompt, forceful --append-system-prompt); soft appended sentinel ignored by the model", ["t2/omp/t4.jsonl", "t2/omp/t4force.jsonl", "t2/omp/t4appforce.jsonl", "t2/omp/t4iso.jsonl"]),
        "T5": (0, "DECOY_SECRET reached the bash child", ["t2/omp/t5.jsonl"]),
        "T6": (0, "SIGINT to omp leaves the sleep grandchild orphaned", ["t2/omp/t6.jsonl", "t2/omp/t6.err"]),
        "T7": (3, "runtime 401 as typed JSON (errorStatus, errorId); bad model is plain stderr at startup", ["t2/omp/t7key.jsonl", "t2/omp/t7model.jsonl"]),
    },
    "pi@0.85.1": {
        "T1": (2, "hangs on qwen's reasoning stream with default thinking; passes with --thinking off", ["t2/pi/golden.jsonl", "t2/pi/probe.jsonl", "t2/pi/probe_nothink.jsonl", "t2/pi/golden2.jsonl"]),
        "T2": (3, "4/4 fields: text, tokens, native USD, ordered tool calls", ["t2/pi/golden2.jsonl"]),
        "T3": (3, "-t read: only read fired, file unchanged", ["t2/pi/t3.jsonl"]),
        "T4": (3, "--append-system-prompt sentinel present", ["t2/pi/t4.jsonl"]),
        "T5": (0, "DECOY_SECRET reached the bash child", ["t2/pi/t5.jsonl"]),
        "T6": (3, "plain SIGTERM killed the sleep child, no orphan", ["t2/pi/t6.log", "t2/pi/t6b.log", "t2/pi/t6c.log"]),
        "T7": (3, "400 bad model / 401 bad key as stopReason error + errorMessage (process exits 0)", ["t2/pi/t7_badmodel.jsonl", "t2/pi/t7_badkey.jsonl", "t2/pi/t7_badkey2.jsonl"]),
    },
    "pi@1.0.2": {
        "T1": (2, "still hangs with default thinking (0 lines in 120 s); passes with --thinking off", ["t2/pi/v1.0.2/probe_default_thinking.jsonl", "t2/pi/v1.0.2/golden.jsonl"]),
        "T2": (3, "4/4 fields: text, tokens, native USD, ordered tool calls", ["t2/pi/v1.0.2/golden.jsonl"]),
        "T3": (3, "-t read: only read fired (26x), file unchanged", ["t2/pi/v1.0.2/t3.jsonl"]),
        "T4": (3, "--append-system-prompt sentinel present", ["t2/pi/v1.0.2/t4.jsonl"]),
        "T5": (0, "DECOY_SECRET reached the bash child", ["t2/pi/v1.0.2/t5.jsonl"]),
        "T6": (3, "plain SIGTERM killed the sleep child, no orphan", ["t2/pi/v1.0.2/t6.log"]),
        "T7": (3, "400 / 401 as stopReason error + errorMessage (process exits 0)", ["t2/pi/v1.0.2/t7_badmodel.jsonl", "t2/pi/v1.0.2/t7_badkey.jsonl"]),
    },
    "opencode": {
        "T1": (3, "exit 0, 17 JSONL lines", ["t2/opencode/t1_run.jsonl"]),
        "T2": (3, "4/4 fields: text, per-step tokens, per-step USD, tool calls", ["t2/opencode/t1_run.jsonl"]),
        "T3": (3, "OPENCODE_PERMISSION bash deny removes bash from the tool set", ["t2/opencode/t3/run.jsonl"]),
        "T4": (2, "AGENTS.md instruction delivered but ignored by the model; OPENCODE_CONFIG_CONTENT instructions did not load", ["t2/opencode/t4/run.jsonl", "t2/opencode/t4b/run.jsonl"]),
        "T5": (0, "DECOY_SECRET reached the bash child", ["t2/opencode/t5/run.jsonl"]),
        "T6": (0, "SIGTERM leaves the sleep child running", ["t2/opencode/t6/run.jsonl", "t2/opencode/t6/run2.jsonl", "t2/opencode/t6/run3.jsonl"]),
        "T7": (2, "one structured error event, but an opaque UnknownError message", ["t2/opencode/t7/run.jsonl"]),
    },
    "dsh": {
        "T1": (3, "exit 0, 24 JSONL events (pinned 0.1.6-alpha.2; published latest rejects --json)", ["t2/dsh/run1.jsonl"]),
        "T2": (2, "3/4 fields: no USD cost in the stream", ["t2/dsh/run1.jsonl"]),
        "T3": (3, "bash disabled via the tool-bash loader row", ["t2/dsh/t3.jsonl"]),
        "T4": (3, "workspace AGENTS.md sentinel honored", ["t2/dsh/t4.jsonl"]),
        "T5": (3, "secret-named vars scrubbed; only DECOY_PLAIN leaked", ["t2/dsh/t5.jsonl"]),
        "T6": (3, "SIGTERM reaps the bash grandchild, no orphan", ["t2/dsh/t6.jsonl", "t2/dsh/t6b-run.sh"]),
        "T7": (3, "turn_end.reason kind error with code AUTH, exit 1", ["t2/dsh/t7.jsonl"]),
    },
    "crush": {
        "T1": (2, "run stdout is plain text; JSON only via a second session show --json call", ["t2/crush/RESULT.md"]),
        "T2": (2, "4/4 fields, but only in 2 steps (session show --json)", ["t2/crush/RESULT.md"]),
        "T3": (3, "options.disabled_tools bash: tool not found", ["t2/crush/t3/crush.json"]),
        "T4": (3, "forceful CRUSH.md sentinel present", ["t2/crush/t4/CRUSH.md", "t2/crush/t4b/CRUSH.md"]),
        "T5": (0, "DECOY_SECRET reached the bash child", ["t2/crush/t5/crush.json"]),
        "T6": (3, "kill -INT reaps the sleep child, no orphan", ["t2/crush/RESULT.md"]),
        "T7": (1, "errors are styled free text on stderr; only the exit code is routable", ["t2/crush/RESULT.md"]),
    },
    "fx": {
        "T1": (3, "ask --json emits one final JSON object", ["t2/fx/runA.json"]),
        "T2": (2, "3/4 fields: no USD cost in ask --json", ["t2/fx/runA.json"]),
        "T3": (2, "per-tool deny works but a partial denylist is escapable via shell", ["t2/fx/runT3.json", "t2/fx/runT3b.json"]),
        "T4": (3, "--system sentinel present (replaces the base prompt)", ["t2/fx/runT4.json"]),
        "T5": (0, "DECOY_SECRET reached the shell tool", ["t2/fx/runT5.json"]),
        "T6": (3, "no --timeout flag; external SIGKILL left no orphan", ["t2/fx/t6.js"]),
        "T7": (3, "typed errors: MissingCredentials, auth_failure, upstream 502 with exit_code", ["t2/fx/runT7.json"]),
    },
    "flue": {
        "T1": (3, "flue run --json prints one envelope, exit 0", ["t2/flue/golden.jsonl"]),
        "T2": (1, "1/4 fields: text only; no tokens, cost or tool calls on stdout", ["t2/flue/golden.jsonl"]),
        "T3": (3, "agent code grants the tool set; model could not edit", ["t2/flue/t3.jsonl", "t2/flue/agents/t3.ts"]),
        "T4": (2, "system prompt delivered; sentinel ignored by the model", ["t2/flue/t4.jsonl"]),
        "T5": (3, "host env scrubbed to an allowlist in both virtual and local() sandboxes", ["t2/flue/t5-virtual.jsonl", "t2/flue/t5-local.jsonl"]),
        "T6": (3, "SIGTERM to flue run: clean process-tree kill", ["t2/flue/RESULT.md", "t2/flue/agents/t6.ts"]),
        "T7": (2, "outcome failed + error object, but a generic internal_error type", ["t2/flue/t7-badmodel.jsonl"]),
    },
    "eve": {
        "T1": (2, "eve: progress rows and the final JSON object share stdout", ["t2/eve/golden-docker.out"]),
        "T2": (2, "1/4 fields inline; tokens and tool calls only via a second traces --json call; no USD", ["t2/eve/golden-docker.out", "t2/eve/golden-trace.json"]),
        "T3": (1, "defaultTools false did not drop the sandbox bash", ["t2/eve/t3.out"]),
        "T4": (2, "instructions.md delivered; sentinel ignored by the model", ["t2/eve/t4.out"]),
        "T5": (3, "docker sandbox cannot see the host env", ["t2/eve/t5.out"]),
        "T6": (2, "original capture: no host orphan but the pooled sandbox container stayed up (t6.out does not show a cancel)", ["t2/eve/t6.out"]),
        "T7": (2, "status failed + exit 1; cause is a raw stack on stderr", ["t2/eve/t7key.out"]),
    },
    "nanocodex": {
        "T1": (3, "JSONL from the first line, exit 0", ["t2/nanocodex/golden.jsonl"]),
        "T2": (3, "4/4 fields in one process (USD is client-estimated)", ["t2/nanocodex/golden.jsonl"]),
        "T3": (1, "no per-run tool allowlist (scored from run --help, nothing to pass live)", ["t2/nanocodex/RESULT.md"]),
        "T4": (3, "--instructions and AGENTS.md both put the sentinel in the answer", ["t2/nanocodex/t4.jsonl", "t2/nanocodex/t4b.jsonl"]),
        "T5": (3, "secret-named vars scrubbed; a plain name and the cwd .env leak", ["t2/nanocodex/t5.jsonl"]),
        "T6": (3, "plain SIGTERM: no orphan, stream ends with status cancelled", ["t2/nanocodex/t6.log", "t2/nanocodex/t6.jsonl"]),
        "T7": (3, "model.attempt.failed, run.error, run.failed with error_class, rc 1", ["t2/nanocodex/t7_badkey.jsonl", "t2/nanocodex/t7_badmodel_upstream.jsonl"]),
    },
}
EVE_T6_RERUN = (2, "re-run: SIGTERM leaves no host orphan and removes the container, but invoke reports a resumable running status and exits after ~15 s",
                ["t2/eve/run_t6.sh", "t2/eve/t6-rerun.log", "t2/eve/t6-rerun.out"])
# Published T1-T7 totals /21
PUBLISHED_T2_TOTAL = {"omp": 14, "pi@0.85.1": 17, "pi@1.0.2": 17, "opencode": 13, "dsh": 20, "crush": 14,
                      "fx": 16, "flue": 17, "eve": 14, "nanocodex": 19}

# --------------------------------------------------------------------------- Tier-1 (static source audit)

CATEGORIES = [
    ("A", "Headless orchestratability", 5), ("B", "Structured observability", 4), ("C", "Auth & multi-provider", 4),
    ("D", "Isolation & secret hygiene", 4), ("E", "Cancellation & process hygiene", 3), ("F", "Tooling power", 2),
    ("G", "Extensibility", 2), ("H", "Operational cost & license", 3),
]
# category means (0-3) as published, then the published weighted total /81 (from unrounded per-criterion scores)
TIER1 = {
    "omp": ([2.8, 2.8, 3.0, 1.0, 2.0, 3.0, 2.4, 2.6], 66.1),
    "dsh": ([2.5, 2.3, 2.3, 2.6, 2.0, 2.4, 3.0, 2.4], 65.6),
    "opencode": ([2.5, 2.8, 2.8, 1.4, 2.0, 1.6, 2.2, 2.4], 61.6),
    "pi": ([2.8, 2.8, 2.8, 1.4, 1.5, 1.0, 2.4, 2.4], 60.9),
    "fx": ([2.2, 2.2, 2.3, 1.6, 2.0, 1.6, 1.6, 3.0], 56.6),
    "crush": ([2.0, 1.8, 2.2, 1.4, 1.75, 2.2, 1.2, 2.8], 52.1),
    "flue": ([2.0, 2.0, 2.0, 2.6, 1.5, 1.6, 2.4, 2.0], 54.9),
    "eve": ([1.7, 2.2, 1.8, 2.4, 2.0, 1.2, 2.2, 1.8], 52.1),
    "nanocodex": ([2.2, 2.8, 2.2, 1.8, 2.5, 1.8, 2.8, 2.6], 62.5),
}
# per-criterion scores, only written down for nanocodex (BENCHMARK.md)
NANOCODEX_CRITERIA = {"A": [3, 3, 2, 1, 3, 1], "B": [3, 3, 2, 3, 3, 3], "C": [1, 3, 2, 3, 2, 2], "D": [2, 1, 2, 2, 2],
                      "E": [1, 3, 3, 3], "F": [2, 2, 0, 2, 3], "G": [2, 3, 3, 3, 3], "H": [3, 2, 3, 3, 2]}
TIER1_SUBJECTS = [
    # name, harness, audited version, added on, repo
    ("omp@18.2.4", "omp", "18.2.4", "2026-09-17", "can1357/oh-my-pi"),
    ("dsh@0.1.6-alpha.2", "dsh", "0.1.6-alpha.2", "2026-09-17", "deepseek-ai/deepseek-harness"),
    ("opencode@1.18.31", "opencode", "1.18.31", "2026-09-17", "sst/opencode"),
    ("pi@0.85.1", "pi", "0.85.1", "2026-09-17", "earendil-works/pi"),
    ("fx@0.0.10", "fx", "0.0.10", "2026-09-17", "vercel-labs/fx"),
    ("crush@0.95.0", "crush", "0.95.0", "2026-09-17", "charmbracelet/crush"),
    ("flue@2.0.8", "flue", "2.0.8", "2026-09-18", "withastro/flue"),
    ("eve@0.60.1", "eve", "0.60.1", "2026-09-18", "vercel/eve"),
    ("nanocodex@0.6.6", "nanocodex", "0.6.6", "2026-10-04", "gakonst/nanocodex"),
]

# --------------------------------------------------------------------------- shared manifest parts

T2_METRICS = {
    "contract": {
        "metric_name": "Driver-contract test score (T1-T7 mean)", "metric_unit": "points (0-3)", "lower_is_better": False,
        "score_type": "continuous", "min_score": 0, "max_score": 3,
        "evaluation_description": "Mean of the seven runtime tests T1-T7, each scored 0-3 by the operator against the raw evidence. x7 = the published T1-T7 total /21.",
        "metric_parameters": {"from": "score"},
    },
    "contract_total": {
        "metric_name": "T1-T7 total", "metric_unit": "points (0-21)", "lower_is_better": False,
        "score_type": "continuous", "min_score": 0, "max_score": 21,
        "evaluation_description": "Sum of T1-T7 as published (= 7 x contract). Checked against the samples by scripts/backfill_standard.py.",
        "metric_parameters": {"from": "external"},
    },
    "task_success": {
        "metric_name": "Golden task success", "metric_unit": "share", "lower_is_better": False, "score_type": "binary",
        "min_score": 0, "max_score": 1,
        "evaluation_description": "Golden task: add a --version flag to cli.js, print DONE_GT. Success = node cli.js --version prints 1.4.2, node cli.js prints hello, only cli.js changed.",
        "metric_parameters": {"from": "is_correct"},
    },
    "golden_usd_per_1k": {
        "metric_name": "Golden task cost per 1,000 runs (T8)", "metric_unit": "USD per 1,000 runs", "lower_is_better": True,
        "score_type": "continuous", "min_score": 0, "max_score": None,
        "evaluation_description": "USD of one golden run x 1000, from the golden row cost_usd. Null where the harness emits no USD.",
        "metric_parameters": {"from": "external"},
    },
    "golden_wall_s": {
        "metric_name": "Golden task wall time (T8)", "metric_unit": "seconds", "lower_is_better": True,
        "score_type": "continuous", "min_score": 0, "max_score": None,
        "evaluation_description": "Wall time of one golden run, from the golden row latency_ms. Method per row in samples metadata.",
        "metric_parameters": {"from": "external"},
    },
}


def t2_subject(name, harness, version, model=QWEN, gen=None, note=None):
    s = {"name": name, "model_info": dict(model), "harness": {"name": harness, "version": version}}
    if gen:
        s["generation_args"] = gen
    if note:
        s["config_note"] = note
    return s


GEN = {
    "omp": {"flags": "-p --mode json --no-session --no-skills --no-title --no-extensions --auto-approve --max-time 120"},
    "pi": {"flags": "-p --mode json --provider openrouter --thinking off"},
    "opencode": {"flags": "run --format json --auto"},
    "dsh": {"flags": "--profile headless --json", "permission_mode": "danger-full-access"},
    "crush": {"flags": "run -q -D <data dir>", "auto_approve": "permissions.allowed_tools"},
    "fx": {"flags": "ask --json --yolo --no-save"},
    "flue": {"flags": "run <agent> --json", "sandbox": "local()"},
    "eve": {"flags": "invoke", "sandbox_backend": "docker", "provider": "createOpenAICompatible shim to OpenRouter"},
    "nanocodex": {"flags": "run --mcp-defaults false --mcp-codex-config false --rollouts false --subagents false --image-generation false --web-search false --memory false", "thinking": "low"},
}


def row(sample_id: str, subject: str, score, finding: str, evidence: list[str], **meta) -> dict:
    return {
        "sample_id": sample_id,
        "subject": subject,
        "repeat": 1,
        "evaluation": {"score": score, "is_correct": None},
        "error": None,
        "metadata": {"test": TEST_NAMES[sample_id], "finding": finding, "evidence": evidence, **meta},
    }


def golden_row(subject: str, g: dict, success: bool = True) -> dict:
    u = g.get("usage")
    tu = None
    if u:
        tu = {k: u[k] for k in ("input_tokens", "output_tokens", "input_tokens_cache_read", "reasoning_tokens") if k in u}
    meta = {"test": TEST_NAMES["golden"], "finding": "task success" if success else "task failed",
            "evidence": g["evidence"], "wall_method": g["wall_method"], "cost_source": g["cost_source"]}
    if u and g.get("input_includes_cache"):
        meta["input_tokens_include_cache"] = True
    if g.get("note"):
        meta["note"] = g["note"]
    if g.get("raw_kept") is False:
        meta["raw_kept"] = False
    usd = u.get("usd") if u else None
    return {
        "sample_id": "golden",
        "subject": subject,
        "repeat": 1,
        "evaluation": {"score": None, "is_correct": success},
        "token_usage": tu,
        "performance": {"latency_ms": round(g["wall_s"] * 1000)},
        "cost_usd": None if usd is None else round(usd, 9),
        "error": None,
        "metadata": meta,
    }


def t2_rows(subject: str, key: str, g: dict, overrides: dict | None = None, carried: dict | None = None) -> list[dict]:
    rows = []
    total = 0
    for t in TESTS:
        sc, finding, ev = (overrides or {}).get(t) or T2_SCORES[key][t]
        extra = (carried or {}).get(t) or {}
        rows.append(row(t, subject, sc, finding, ev, **extra))
        total += sc
    check(f"{key} T1-T7 total", total, PUBLISHED_T2_TOTAL[key])
    gr = golden_row(subject, g)
    if carried and "golden" in carried:
        gr["metadata"].update(carried["golden"])
    rows.append(gr)
    return rows


def external_results(rows: list[dict]) -> dict:
    """contract_total, golden_usd_per_1k and golden_wall_s per subject, from the rows."""
    out: dict = {}
    for s in dict.fromkeys(r["subject"] for r in rows):
        mine = [r for r in rows if r["subject"] == s]
        total = sum(r["evaluation"]["score"] for r in mine if r["sample_id"] in TESTS)
        g = next(r for r in mine if r["sample_id"] == "golden")
        usd = g["cost_usd"]
        res = {
            "contract_total": {"score": total},
            "golden_usd_per_1k": {"score": None if usd is None else round(usd * 1000, 4)},
            "golden_wall_s": {"score": round(g["performance"]["latency_ms"] / 1000, 3)},
        }
        if usd is None:
            res["golden_usd_per_1k"]["note"] = g["metadata"]["cost_source"]
        out[s] = res
    return out


def base(run_id: str, started: str, commit: str, question: str, title: str, **kw) -> dict:
    m = {
        "schema_version": "bench-manifest/1",
        "id": run_id,
        "bench": BENCH,
        "question": question,
        "title": title,
        "started_at": started,
        "finished_at": kw.pop("finished_at", None),
        "revision": {"repo": REPO, "commit": commit, "dirty": None},
        "command": kw.pop("command", None),
        "setup": kw.pop("setup", "standard"),
        "setup_notes": kw.pop("setup_notes", None),
        "env": kw.pop("env", None),
        "eval_library": {"name": BENCH, "version": commit},
        "interaction_type": "agentic",
    }
    m.update(kw)
    return m


def t2_manifest(run_id, started, commit, question, title, subjects, rows, *, cost, summary, raw, writeup,
                setup="standard", setup_notes=None, env=None, superseded_by=None, compared_with=None,
                corrections=None, command=None, n_completed=8, status="complete"):
    m = base(run_id, started, commit, question, title, setup=setup, setup_notes=setup_notes, command=command,
             env=env or {"host": "macOS, Node 26.8.1", "fixture": "isolated fixture per harness (package.json 1.4.2 + cli.js)"})
    m.update({
        "source_data": {"dataset_name": "tier2-live-tests", "source_type": "url",
                        "url": [f"https://github.com/{REPO}/blob/main/BENCHMARK.md"],
                        "version": TASKSET, "n_planned": 8, "n_completed": n_completed, "split": None},
        "subjects": subjects,
        "repeats": {"planned": 1, "completed": 1, "aggregation": "mean"},
        "llm_scoring": None,
        "metric_config": T2_METRICS,
        "primary_metric": "contract",
        "evaluation_results": external_results(rows),
        "comparisons": [],
        "errors": {"n": 0, "of": len(rows), "counted_as": "zero",
                   "note": "Harness failures are test results (scored 0-3), not errors."},
        "cost": cost,
        "seconds": None,
        "decision_rule": None,
        "verdict": "SNAPSHOT",
        "status": status,
        "summary": summary,
        "compared_with": compared_with or [],
        "raw": raw,
        "writeup": writeup,
        "superseded_by": superseded_by,
        "corrections": corrections or [],
    })
    return m


QWEN_COST = {"basis": "api", "prices_as_of": None}
AUTHOR = "Aaron Elijah Mars"


def corr(date, reason, field=None, old=None, new=None):
    c = {"date": date, "author": AUTHOR, "reason": reason}
    if field is not None:
        c.update({"field": field, "old": old, "new": new})
    return c


# --------------------------------------------------------------------------- runs


def run_tier1() -> tuple[dict, list[dict]]:
    rid = "2026-09-17-tier1-static-audit"
    rows = []
    subjects = []
    results = {}
    for name, h, ver, added, repo in TIER1_SUBJECTS:
        means, total = TIER1[h]
        recomputed = sum(x * w for x, (_, _, w) in zip(means, CATEGORIES, strict=True))
        if abs(recomputed - total) > 0.45:
            raise SystemExit(f"tier1 {h}: rounded category means give {recomputed:.2f}, published {total}")
        for (cid, cname, w), mean in zip(CATEGORIES, means, strict=True):
            meta = {"category": cname, "weight": w, "weighted_points": round(mean * w, 3), "added_on": added}
            if h == "nanocodex":
                meta["criteria"] = NANOCODEX_CRITERIA[cid]
            rows.append({"sample_id": cid, "subject": name, "repeat": 1,
                         "evaluation": {"score": mean, "is_correct": None}, "error": None, "metadata": meta})
        if h == "nanocodex":
            exact = sum(sum(v) / len(v) * w for (cid, _, w), v in
                        zip(CATEGORIES, NANOCODEX_CRITERIA.values(), strict=True))
            check("nanocodex tier1 from criteria", round(exact, 1), total)
        subjects.append({"name": name, "harness": {"name": h, "version": ver},
                         "config_note": f"source audit of {repo}"})
        results[name] = {"weighted_total": {
            "score": total,
            "note": f"published total from unrounded per-criterion scores; sum of the rounded category means is {recomputed:.2f}. Judgment noise about +/-3.",
        }}
    m = base(
        rid, "2026-09-17", "e9899e5",
        "How well does each harness fit the headless agent-loop role a control plane drives, by static source audit?",
        "Tier-1 static source audit, 9 harnesses, weighted /81",
        finished_at="2026-10-04",
        command="static source and docs audit per harness (no model calls by the harness); see BENCHMARK.md",
        setup="standard",
        env={"method": "static source + docs audit by investigator agents, reviewed by the operator; every criterion scored 0-3 with a file:line, flag or doc citation",
             "revision_note": "first six harnesses in e9899e5 (2026-09-17), flue and eve in c8d50b3 (2026-09-18), fx correction in 61429fa and nanocodex in 57cec99 (both 2026-10-04)"},
    )
    m.update({
        "headline": True,
        "source_data": {"dataset_name": "tier1-rubric", "source_type": "url",
                        "url": [f"https://github.com/{REPO}/blob/main/BENCHMARK.md"],
                        "version": TASKSET, "n_planned": 8, "n_completed": 8,
                        "split": "8 weighted categories (A-H), 42 criteria"},
        "subjects": subjects,
        "repeats": {"planned": 1, "completed": 1, "aggregation": "mean"},
        "llm_scoring": None,
        "metric_config": {
            "weighted_total": {
                "metric_name": "Weighted total", "metric_unit": "points (0-81)", "lower_is_better": False,
                "score_type": "continuous", "min_score": 0, "max_score": 81,
                "evaluation_description": "Sum over categories A-H of mean(criteria 0-3) x weight (5,4,4,4,3,2,2,3). Static source audit, one pass. Judgment noise about +/-3; trust tiers, not decimals.",
                "metric_parameters": {"from": "external"},
            },
            "category_mean": {
                "metric_name": "Unweighted category mean", "metric_unit": "points (0-3)", "lower_is_better": False,
                "score_type": "continuous", "min_score": 0, "max_score": 3,
                "evaluation_description": "Mean of the 8 published (rounded) category means, unweighted. A secondary view; the weighted total is the published score.",
                "metric_parameters": {"from": "score"},
            },
        },
        "primary_metric": "weighted_total",
        "evaluation_results": results,
        "comparisons": [],
        "errors": {"n": 0, "of": len(rows), "counted_as": "zero", "note": None},
        "cost": {"usd": None, "basis": "none", "note": "static audit; the investigators' model spend was not recorded"},
        "seconds": None,
        "decision_rule": None,
        "verdict": "SNAPSHOT",
        "status": "complete",
        "summary": ("Totals /81: omp 66.1, dsh 65.6, nanocodex 62.5, opencode 61.6, pi 60.9, fx 56.6, flue 54.9, crush 52.1, eve 52.1. "
                    "Noise is about +/-3 (single static pass, judgment calls), so read tiers, not decimals: the omp/dsh gap is within noise. "
                    "Capability and deploy readiness diverge; the readiness gate and rankings are in docs/2026-10-04-harness-comparison.md and BENCHMARK.md."),
        "compared_with": [],
        "raw": {"kept": True, "location": "BENCHMARK.md (criteria, scorecard, nanocodex per-criterion scores)",
                "reason": "per-criterion scores for the first eight harnesses were not written down, only category means"},
        "writeup": "docs/2026-10-04-harness-comparison.md",
        "superseded_by": None,
        "corrections": [
            corr("2026-10-04", "The Tier-2 live run found no --timeout flag on the shipped fx 0.0.10 binary, so E1 max-time drops 3 -> 1 and category E 2.5 -> 2.0 (commit 61429fa). Rank unchanged.",
                 "evaluation_results.fx@0.0.10.weighted_total.score", 58.1, 56.6),
        ],
    })
    return m, rows


def run_qwen_0917() -> tuple[dict, list[dict]]:
    rid = "2026-09-17-tier2-qwen"
    spec = [("omp@18.2.0+qwen3.7-flash", "omp", "omp", "18.2.0", golden_omp()),
            ("pi@0.85.1+qwen3.7-flash", "pi@0.85.1", "pi", "0.85.1", golden_pi_085()),
            ("opencode@1.18.30+qwen3.7-flash", "opencode", "opencode", "1.18.30", golden_opencode()),
            ("dsh@0.1.6-alpha.2+qwen3.7-flash", "dsh", "dsh", "0.1.6-alpha.2", golden_dsh()),
            ("crush@0.95.0+qwen3.7-flash", "crush", "crush", "0.95.0", golden_crush())]
    rows, subjects = [], []
    for name, key, h, ver, g in spec:
        rows += t2_rows(name, key, g)
        subjects.append(t2_subject(name, h, ver, gen=GEN[h]))
    m = t2_manifest(
        rid, "2026-09-17", "e9899e5",
        "Do the harnesses honor the headless driver contract live, and what does the golden task cost, on one shared model?",
        "Tier-2 live run, 5 CLIs on qwen3.7-flash", subjects, rows,
        cost={"usd": None, **QWEN_COST, "prices_as_of": "2026-09-17",
              "note": "whole-run spend not recorded for every harness; golden-task USD is in golden_usd_per_1k (omp spent $0.004178 over all 12 of its runs)"},
        summary=("T1-T7 /21: dsh 20, pi 17, omp 14, crush 14, opencode 13. All five passed the golden task. "
                 "Env isolation (T5) splits the field: only dsh scrubbed secret-named vars. omp and opencode orphan the child on a single signal (T6). "
                 "pi hangs on the reasoning model unless --thinking off. Golden cost per run: pi $0.000263, dsh $0.00048 (computed), omp $0.000821, crush $0.00087, opencode $0.001347."),
        raw={"kept": True, "location": "t2/omp/, t2/pi/, t2/opencode/, t2/dsh/, t2/crush/",
             "reason": "crush: run stdout is plain text and the session show --json captures were not committed; only its configs and RESULT.md are kept"},
        writeup="BENCHMARK.md",
        compared_with=[{"id": "2026-10-04-tier2-pi-1.0.2", "differs": "pi re-run on 1.0.2; same verdicts, golden wall measured as process time instead of message timestamps"}],
        corrections=[
            corr("2026-10-04", "t2/pi/analyze.py kept only the last assistant turn's usage; summing all turns gives the real golden numbers (commit 61429fa). Published pi was ~25x cheaper than omp, really ~3x.",
                 "samples golden pi@0.85.1 tokens in/out and cost_usd", "329 / 2 tokens, $0.0000347", "5154 / 289 tokens, $0.000263"),
            corr("2026-10-04", "The computed dsh cost left out the 25,472 cache-read tokens (commit 61429fa).",
                 "samples golden dsh cost_usd", 0.00033, 0.00048),
            corr("2026-10-04", "t2/crush/RESULT.md aligned with the shared rubric the published table already used (2-step structured output = 2, free-text errors = 1). The table and totals did not change.",
                 "t2/crush/RESULT.md T2 / T7", "3 / ~2", "2 / 1"),
        ],
        command="per-harness invocations in t2/<harness>/RESULT.md; OPENROUTER_API_KEY from the environment",
    )
    return m, rows


def run_fx() -> tuple[dict, list[dict]]:
    rid = "2026-09-17-tier2-fx-grok"
    name = "fx@0.0.10+grok-4.6"
    rows = t2_rows(name, "fx", golden_fx())
    subj = [t2_subject(name, "fx", "0.0.10", model={"id": "grok-4.6", "developer": "xai", "inference_platform": "xai (Grok subscription via fx)"}, gen=GEN["fx"])]
    m = t2_manifest(
        rid, "2026-09-17", "e9899e5",
        "Does fx honor the headless driver contract live?",
        "Tier-2 live run, fx on grok-4.6 (not comparable)", subj, rows,
        setup="custom",
        setup_notes="Ran on grok-4.6, not the cohort's qwen/qwen3.7-flash: the shipped fx 0.0.10 binary cannot reach OpenRouter or any OpenAI-compatible endpoint. T1-T7 and task success are valid harness evidence; T8 cost and wall time are not comparable and fx is excluded from any comparison.",
        cost={"usd": None, "basis": "subscription", "prices_as_of": None, "note": "Grok subscription; fx emits no per-token USD"},
        summary="T1-T7 16/21, golden task passed on grok-4.6. One final JSON object rather than a stream, no USD, no --timeout or --model flag; per-tool deny is escapable via shell. Not comparable with the qwen runs.",
        raw={"kept": True, "location": "t2/fx/"},
        writeup="t2/fx/RESULT.md",
        command="HOME=<isolated> fx ask --json --yolo --no-save \"<task>\" (see t2/fx/RESULT.md)",
    )
    return m, rows


def run_flue() -> tuple[dict, list[dict]]:
    rid = "2026-09-18-tier2-flue"
    name = "flue@2.0.8+qwen3.7-flash"
    rows = t2_rows(name, "flue", golden_flue())
    subj = [t2_subject(name, "flue", "2.0.8", gen=GEN["flue"])]
    m = t2_manifest(
        rid, "2026-09-18", "c8d50b3",
        "Does the flue framework honor the headless driver contract live, on the cohort's model?",
        "Tier-2 live run, flue (framework) on qwen3.7-flash", subj, rows,
        env={"host": "macOS, Node 26.8.1", "fixture": "isolated fixture", "shape": "framework: agent authored as a TypeScript module under t2/flue/agents/, driven by flue run"},
        cost={"usd": None, **QWEN_COST, "prices_as_of": "2026-09-18", "note": "flue emits no tokens or USD on stdout"},
        summary="T1-T7 17/21, golden task passed in 12.9 s. Scrubs child env by default in both sandbox modes and kills the process tree cleanly, but --json carries no tokens, cost or tool calls.",
        raw={"kept": True, "location": "t2/flue/"},
        writeup="t2/flue/RESULT.md",
        command="flue run src/agents/coder.ts --message \"Do the task.\" --json",
    )
    return m, rows


EVE_ENV = {"host": "macOS, Node 26.8.1, Docker 29.4.0", "fixture": "isolated eve project per test",
           "shape": "framework: agent project under t2/eve/agent/, OpenRouter reached through a createOpenAICompatible shim, docker sandbox backend"}


def run_eve() -> tuple[dict, list[dict]]:
    rid = "2026-09-18-tier2-eve"
    name = "eve@0.60.1+qwen3.7-flash"
    rows = t2_rows(name, "eve", golden_eve())
    subj = [t2_subject(name, "eve", "0.60.1", gen=GEN["eve"])]
    m = t2_manifest(
        rid, "2026-09-18", "c8d50b3",
        "Does the eve framework honor the headless driver contract live, on the cohort's model?",
        "Tier-2 live run, eve (framework) on qwen3.7-flash", subj, rows,
        env=EVE_ENV,
        cost={"usd": None, **QWEN_COST, "prices_as_of": "2026-09-18", "note": "no USD off the Vercel AI Gateway"},
        summary="T1-T7 14/21, golden task passed on the docker backend. Real sandbox isolation (T5 3) but a 2-step trace for usage, chatter on stdout and no per-tool allowlist flag. The T6 evidence here is superseded by the 2026-10-04 re-run (score unchanged at 2).",
        raw={"kept": True, "location": "t2/eve/"},
        writeup="t2/eve/RESULT.md",
        superseded_by="2026-10-04-tier2-eve-t6-rerun",
        corrections=[
            corr("2026-10-04", "Trace tokens re-read from golden-trace.json (commit 61429fa); the trace is from an earlier golden session, not the golden-docker.out session.",
                 "samples golden eve tokens in/out", "~25,000 / ~966", "21,896 / 831"),
            corr("2026-10-04", "T6 evidence superseded: t6.out does not show a cancel and the lingering container did not reproduce. The re-run 2026-10-04-tier2-eve-t6-rerun keeps the score at 2 for a different reason (slow teardown, running status).",
                 "samples T6 eve finding", "container stays up after SIGTERM", "no orphan, container removed, ~15 s teardown"),
        ],
        command="eve invoke \"<task>\" (see t2/eve/RESULT.md)",
    )
    return m, rows


def run_eve_rerun() -> tuple[dict, list[dict]]:
    rid = "2026-10-04-tier2-eve-t6-rerun"
    name = "eve@0.60.1+qwen3.7-flash"
    carried = {t: {"carried_from": "2026-09-18-tier2-eve"} for t in TESTS if t != "T6"}
    carried["golden"] = {"carried_from": "2026-09-18-tier2-eve"}
    rows = t2_rows(name, "eve", golden_eve(), overrides={"T6": EVE_T6_RERUN}, carried=carried)
    subj = [t2_subject(name, "eve", "0.60.1", gen=GEN["eve"])]
    m = t2_manifest(
        rid, "2026-10-04", "57d9725",
        "Does eve leave an orphan or a sandbox container behind on SIGTERM (T6 re-run)?",
        "eve T6 cancellation re-run (other tests carried from 2026-09-18)", subj, rows,
        setup_notes="Only T6 was re-run (fresh project, docker backend, model ran sleep 120, SIGTERM to eve invoke). T1-T5, T7 and the golden row are carried unchanged from 2026-09-18-tier2-eve so this run holds the full current eve record; carried rows say so in metadata.",
        env=EVE_ENV,
        cost={"usd": None, **QWEN_COST, "prices_as_of": "2026-10-04", "note": "single T6 call; no USD off the Vercel AI Gateway"},
        summary="Only T6 was re-run; T1-T5, T7 and the golden row are carried unchanged from 2026-09-18-tier2-eve (marked carried_from in samples) so this run is the full current eve record. T6 stays 2: SIGTERM leaves no host orphan and the container is removed, but invoke prints a resumable running status and exits only after ~15 s. eve total unchanged at 14/21.",
        raw={"kept": True, "location": "t2/eve/run_t6.sh, t2/eve/t6-rerun.log, t2/eve/t6-rerun.out"},
        writeup="t2/eve/RESULT.md",
        compared_with=[{"id": "2026-09-18-tier2-eve", "differs": "T6 re-run with real cancel evidence; other rows carried"}],
        command="t2/eve/run_t6.sh",
    )
    return m, rows


def run_pi_102() -> tuple[dict, list[dict]]:
    rid = "2026-10-04-tier2-pi-1.0.2"
    name = "pi@1.0.2+qwen3.7-flash"
    rows = t2_rows(name, "pi@1.0.2", golden_pi_102())
    subj = [t2_subject(name, "pi", "1.0.2", gen=GEN["pi"])]
    m = t2_manifest(
        rid, "2026-10-04", "fc9468f",
        "Do pi's Tier-2 verdicts hold on pi 1.0.2?",
        "Tier-2 re-run, pi 1.0.2 on qwen3.7-flash", subj, rows,
        cost={"usd": None, **QWEN_COST, "prices_as_of": "2026-10-04", "note": "golden-task USD is in golden_usd_per_1k; batch total not recorded"},
        summary="Every verdict unchanged from 0.85.1: T1-T7 17/21, still hangs on the reasoning model without --thinking off. Golden: 4,097 in / 310 out / 10,752 cache read, $0.000228, 7.0 s process wall (about 3.6x cheaper and 2.9x faster than omp on the same task).",
        raw={"kept": True, "location": "t2/pi/v1.0.2/"},
        writeup="t2/pi/RESULT.md",
        compared_with=[{"id": "2026-09-17-tier2-qwen", "differs": "pi 0.85.1 -> 1.0.2; golden wall now process time (0.85.1 used message timestamps)"}],
        command="t2/pi/v1.0.2/run_batch.sh",
    )
    return m, rows


def run_nanocodex() -> tuple[dict, list[dict]]:
    rid = "2026-10-04-tier2-nanocodex-mimo"
    name = "nanocodex@0.6.6+mimo-v2.6-pro"
    rows = t2_rows(name, "nanocodex", golden_nanocodex())
    subj = [t2_subject(name, "nanocodex", "0.6.6",
                       model={"id": "xiaomi/mimo-v2.6-pro", "developer": "xiaomi", "inference_platform": "openrouter"},
                       gen=GEN["nanocodex"], note="release binary nanocodex-aarch64-apple-darwin, commit 7fcc3e7, SHA256 checked")]
    m = t2_manifest(
        rid, "2026-10-04", "57cec99",
        "Does nanocodex honor the headless driver contract live?",
        "Tier-2 live run, nanocodex on mimo-v2.6-pro (not comparable)", subj, rows,
        setup="custom",
        setup_notes="Ran on xiaomi/mimo-v2.6-pro, not qwen/qwen3.7-flash: nanocodex only accepts a closed model list, and with a model-rewrite proxy qwen's provider rejects its always-on Code Mode custom tool (t2/nanocodex/qwen_blocked.jsonl). T1-T7 and task success are valid harness evidence; T8 is not comparable and nanocodex is excluded from any comparison. T3 was scored from run --help (no allowlist to pass).",
        env={"host": "macOS", "fixture": "isolated HOME and CODEX_HOME, NANOCODEX_COMPUTER=off"},
        cost={"usd": None, "basis": "api", "prices_as_of": "2026-10-04", "note": "golden USD is client-estimated by nanocodex; batch total not recorded"},
        summary="T1-T7 19/21, golden task passed. One-process JSONL with tokens, estimated USD and typed errors, secret-name env scrub and a clean cancel; no per-run tool allowlist and default-on loaders read operator state. Not comparable with the qwen runs.",
        raw={"kept": True, "location": "t2/nanocodex/"},
        writeup="t2/nanocodex/RESULT.md",
        command="t2/nanocodex/run_batch.sh and t2/nanocodex/run_t6.sh",
    )
    return m, rows


RUNS = [run_tier1, run_qwen_0917, run_fx, run_flue, run_eve, run_eve_rerun, run_pi_102, run_nanocodex]


def dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def merged(new: dict, old: dict | None) -> dict:
    """Keep stats-owned fields from the committed manifest (bench-kit stats refills them)."""
    if not old:
        return new
    out = dict(new)
    for k in STATS_OWNED:
        if k == "evaluation_results":
            er = {s: dict(v) for s, v in (old.get(k) or {}).items()}
            for s, metrics in (new.get(k) or {}).items():
                er.setdefault(s, {}).update(metrics)
            out[k] = er
        elif k == "errors":
            out[k] = {**new[k], **{x: old[k][x] for x in ("n", "of", "by_source") if x in (old.get(k) or {})}}
        elif k in old:
            out[k] = old[k]
    return out


def strip_stats(m: dict) -> dict:
    m = json.loads(json.dumps(m))
    m.pop("token_usage", None)
    for x in ("n", "of", "by_source"):
        (m.get("errors") or {}).pop(x, None)
    cfg = m.get("metric_config") or {}
    for s in (m.get("evaluation_results") or {}).values():
        for mid in list(s):
            if (cfg.get(mid, {}).get("metric_parameters") or {}).get("from", "external") != "external":
                s.pop(mid)
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare with the committed files instead of writing")
    a = ap.parse_args(argv)
    drift = []
    for fn in RUNS:
        m, rows = fn()
        d = ROOT / "runs" / m["id"]
        mp, sp = d / "manifest.json", d / "samples.jsonl"
        old = json.loads(mp.read_text()) if mp.exists() else None
        samples = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        if a.check:
            if not sp.exists() or sp.read_text() != samples:
                drift.append(str(sp.relative_to(ROOT)))
            if old is None or strip_stats(old) != strip_stats(m):
                drift.append(str(mp.relative_to(ROOT)))
            continue
        d.mkdir(parents=True, exist_ok=True)
        sp.write_text(samples)
        mp.write_text(dump(merged(m, old)))
        print(f"wrote {mp.relative_to(ROOT)} + samples.jsonl ({len(rows)} rows)")
    if drift:
        print("out of date (run scripts/backfill_standard.py, then bench-kit stats):", *drift, sep="\n- ", file=sys.stderr)
        return 1
    if a.check:
        print(f"standard files match ({len(RUNS)} runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
