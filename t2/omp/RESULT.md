# Tier-2 DYNAMIC harness result - omp (oh-my-pi v18.2.0)

Date: 2026-09-17 · Model: `openrouter/qwen/qwen3.7-flash` (OpenRouter, $0.03/M in, $0.13/M out)

## Exact invocation (golden run)

```
OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
omp -p --mode json --no-session --no-skills --no-title --no-extensions \
    --auto-approve --cwd <fixture> \
    --model openrouter/qwen/qwen3.7-flash \
    --tools read,edit,bash --max-time 120 \
    "In cli.js, add a --version flag: ... print the exact token DONE_GT on its own line."
```

Notes on flags vs the proposed spec:
- `--mode json` is correct (omp has no `--json`); output is JSONL to stdout, captured with `>`.
- Added `--auto-approve`. Without it, edit/bash tool calls block on an approval prompt and the headless run never completes.
- Model id form omp wants: `openrouter/qwen/qwen3.7-flash` (provider-prefixed selector).

## TASK SUCCESS: PASS (real did-it-work signal)
- `node cli.js --version` -> `1.4.2`
- `node cli.js` -> `hello`
- Final assistant text = `DONE_GT`. Model self-tested via bash before finishing.

## T1-T8

| # | Test | Score | Evidence |
|---|------|-------|----------|
| T1 | Boot-to-JSON | PASS (3) | Ran non-interactive, exit 0, 338 JSONL events. First: `{"type":"session","version":3,"id":"01a0b0b4-...","cwd":...}` · Last: `{"type":"agent_end",...,"isTerminal":true}` |
| T2 | Structured-parse | 4/4 (3) | All extractable: final text=`DONE_GT`; input=12283, output=801 tok; USD cost=$0.000821 (native `usage.cost.total` per assistant turn); 7 ordered tool calls: read(cli.js), read(package.json), edit-fail, edit-fail, edit-ok, read(cli.js), bash(`node cli.js --version && node cli.js`) |
| T3 | Tool-allowlist honored | PASS (3) | Re-ran needs-edit task with `--tools read`. File UNCHANGED. Non-listed builtins blocked: `bash` -> `"Tool bash not found"`; `write` -> neutered to `xd://` device transport (cannot write local files); `edit` never offered. Model gave up, printed a diff + `DONE_GT`. Caveat: tested with `--no-extensions --no-skills`; per Tier-1, MCP/extension tools can still load if those are left on, so the allowlist governs builtins, not extension discovery. |
| T4 | System-prompt injection | mechanism PASS / literal-soft FAIL (2) | Golden run + soft `--append-system-prompt "Always end ... SENTINEL_9Z"` -> SENTINEL absent (weak qwen3.7-flash ignored the soft trailing line; the user prompt's own "print DONE_GT" terminal instruction dominated). Injection mechanism VERIFIED working: full `--system-prompt "...respond with exactly SENTINEL_9Z"` -> model returned exactly `SENTINEL_9Z`; forceful `--append-system-prompt "...your entire response must be SENTINEL_9Z"` -> exactly `SENTINEL_9Z`. So omp applies both system-prompt paths in print mode; adherence to a soft appended line is model-dependent. |
| T5 | Env isolation | LEAK = YES | `DECOY_SECRET=leakme9Z` set alongside the key reached the child bash: tool ran `env \| grep DECOY` -> `DECOY_SECRET=leakme9Z`, model echoed it back. omp does NOT scrub env by design, so containment is the caller's job (confirms Tier-1). |
| T6 | Cancellation | FAIL (0) | Real `sleep` child (pid 8609) spawned ~5.5s in. `kill -INT <omp pid>` -> omp process exits, but the `sleep` grandchild is orphaned and survives the full 12s watch window. JSONL truncates right after `{"type":"tool_execution_start","toolName":"bash","args":{"command":"sleep 60"}}`, with no `tool_execution_end` and no cancel/terminal event written. A single SIGINT to omp's pid does NOT tear down the process tree; a supervisor must kill the process GROUP or reap orphans. Consistent with the T5 "containment is the caller's job" theme. |
| T7 | Cascade/error shape | PASS (3) | Bad key -> machine-readable, classifiable JSONL: `{"type":"turn_end",...,"stopReason":"error","errorStatus":401,"errorId":16781312,"errorMessage":"401 Missing Authentication header"}` (repeated in `agent_end`), exit 1, exactly what `omp.Classify` consumes (has `errorStatus`+`errorId`+`errorMessage`). Bad model -> fails at startup with plain stderr `Model "..." not found`, EMPTY JSONL, exit 1 (pre-flight validation, NOT machine-readable). Shortest decisive lines: runtime `"errorStatus":401 ... "401 Missing Authentication header"`; startup `Model "..." not found`. |
| T8 | Cost / wall-clock | - | Golden run: input 12283 tok, output 801 tok (+59392 cacheRead tok), USD $0.000821 (omp-native; matches tokens*rate + cache math), wall 20.0s (`time` total). |

## Totals (all 12 runs incl. probes)
- Tokens: input 98,388 · output 3,470
- Cost: $0.004178 (~0.42 cents) across every run in this benchmark
- Golden wall clock: 20.0s

## Headline findings
1. omp is a first-class headless JSON harness: `--mode json` emits a rich, fully-parseable JSONL stream (session -> agent_start -> turn/message/tool events -> agent_end) with per-turn usage+cost natively (T1/T2 = 3/3, 4/4).
2. Needs `--auto-approve` for non-interactive tool use; the proposed spec omitted it and would hang.
3. `--tools` allowlist governs builtins reliably (bash absent, write neutered, edit not offered) when extensions/skills are disabled (T3 pass). Leave `--no-extensions --no-skills` on for hard containment.
4. System-prompt injection works via both `--system-prompt` and `--append-system-prompt` (T4 mechanism pass); a soft appended instruction will not survive a weak model plus a conflicting user directive.
5. Two containment gaps the CALLER must close: env is NOT scrubbed (T5 leak) and cancellation does NOT reap child processes (T6 orphan). Kill the process group and pass a clean env; do not rely on omp.
6. Error surface is bimodal: runtime provider errors are machine-readable JSON events (classifiable); config/startup errors (bad model, missing key) are plain stderr with an empty stream + exit 1. A supervisor must handle both shapes.
