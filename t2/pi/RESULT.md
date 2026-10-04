# Tier-2 DYNAMIC harness test - Pi (`@earendil-works/pi-coding-agent`)

## Re-run on v1.0.2 (2026-10-04)

Same batch, same model, `@earendil-works/pi-coding-agent@1.0.2`. Scripts + raw evidence in [`v1.0.2/`](v1.0.2/). Every verdict below is unchanged; the T8 numbers in the README now come from this run.

| Test | v1.0.2 result | Evidence |
|---|---|---|
| T1 reasoning hang | still hangs with default thinking (0 JSONL lines in 120s, `timeout` rc=124); passes with `--thinking off` | `v1.0.2/probe_default_thinking.*` |
| T2 structured parse | 4/4: final `DONE_GT`, tokens + `usage.cost.total` per turn, ordered tool calls `read,read,edit,bash` | `v1.0.2/golden.jsonl` |
| T3 allowlist | `-t read` only fired `read` (26x), `fixture_t3/cli.js` unchanged, upstream "Repetitive tool calls" error | `v1.0.2/t3.jsonl` |
| T4 sysprompt | final text `ready\n\nSENTINEL_9Z` | `v1.0.2/t4.jsonl` |
| T5 env | LEAK: bash output `DECOY_SECRET=leakme9Z` | `v1.0.2/t5.jsonl` |
| T6 cancel | ORPHAN=NO: plain SIGTERM to pi killed the `sleep 129` child (own pgid) | `v1.0.2/t6.log` |
| T7 errors | 400 bad model / 401 bad key (captured with a fake `sk-or-v1-...` key; the script now passes `not-a-real-key`, which gives 401 `Missing Authentication header` in the same shape) as `stopReason:"error"` + `errorMessage`, process rc=0 | `v1.0.2/t7_*.jsonl` |
| T8 golden | 4,097 in / 310 out / 10,752 cache read, **$0.000228**, process wall **7.0s** | `v1.0.2/golden.jsonl`, `v1.0.2/batch.log` |
| TASK SUCCESS | PASS: `node cli.js --version` = `1.4.2`, `node cli.js` = `hello` | `v1.0.2/batch.log` |

The v1.0.2 wall time is the whole process (same method as the other harnesses); the 0.85.1 figure below (6.1s) was measured from message timestamps.

## First run (v0.85.1, 2026-09-17)

Date: 2026-09-17 · Binary: `pi` (node bundle) · Installed via `npm i -g @earendil-works/pi-coding-agent` (Node v26.8.1)
Model: `qwen/qwen3.7-flash` via OpenRouter · Profile isolated to `PI_CODING_AGENT_DIR=.../t2/pi/.pi`

## HEADLINE FINDING (blocks the as-specified run)
`qwen/qwen3.7-flash` is a **reasoning model** (OpenRouter/Alibaba emits `reasoning`/`reasoning_details` deltas; ~294 reasoning tokens even for "say hi"). **Pi hangs indefinitely on this reasoning stream.** The exact team-specified invocation (no thinking flag) produced **0 output**:
- Golden task, default thinking: ran **509s**, killed (SIGTERM, EXIT=143), **0 JSONL lines**.
- Trivial `-nt "Reply PING"`, default thinking: hung **>6 min**, 0 lines, single live node proc RSS ~130MB.
- Same model via direct `curl` chat completion returns in **5s**; same pi run with **`--thinking off` returns in <2s / 13 JSON lines**.

Root cause is pi's handling of the streamed reasoning payload, not the model or network. **All scored runs below add `--thinking off`** (the only config in which pi completes on this model). Pi emits events only at message boundaries (no token-delta events), so a never-completing first message = zero stdout.

## EXACT INVOCATION (scored runs)
```
OPENROUTER_API_KEY=$OPENROUTER_API_KEY PI_CODING_AGENT_DIR=.../t2/pi/.pi \
  pi -p --mode json --provider openrouter --model qwen/qwen3.7-flash --thinking off \
     -t read,edit,bash "<task>"        # run from inside the fixture dir (pi uses cwd; no --cwd flag exists)
```

## T1 to T8

| # | Test | Score | Evidence |
|---|------|-------|----------|
| T1 | Boot-to-JSON | **as-specified FAIL / with `--thinking off` PASS** | Default spec: 0 JSONL in 509s (hang). With `--thinking off`: 101 well-formed JSONL events, `stopReason:"stop"`, final `DONE_GT`. Event stream: `session, agent_start, turn_start, message_start/end, message_update, tool_execution_start/update/end, turn_end, agent_end, agent_settled`. |
| T2 | Structured-parse | **4/4** | From golden JSONL: (1) final text `"DONE_GT"`; (2) tokens `usage.input`/`output`/`totalTokens` per assistant turn, summed over the 4 turns = 5154/289/**17219** (+11776 cacheRead); (3) USD `usage.cost.total` summed = **2.628e-04**; (4) ordered tool calls via `tool_execution_start` + message `toolCall.name`: `read -> read -> edit -> bash`. Also `stopReason`, per-tool `toolResults[].isError`. |
| T3 | Tool-allowlist honored | **PASS (3/3)** | Re-run with `-t read` on the edit task: **only `read` calls fired (23x), zero edit/write/bash**. `fixture_t3/cli.js` **unchanged** (`console.log("hello")`). Model text: "Let me write the updated cli.js" but had no edit tool; looped reads until Alibaba upstream aborted (`stopReason:"error"`, "Repetitive tool calls detected"). Exact allowlist enforced client-side. |
| T4 | System-prompt injection | **PASS** | `--append-system-prompt "...SENTINEL_9Z..."` -> final text = `"ready\n\nSENTINEL_9Z"`. Sentinel present. |
| T5 | Env isolation | **LEAK = YES** | `DECOY_SECRET=leakme9Z` + bash `env | grep DECOY` -> toolResult text `"DECOY_SECRET=leakme9Z\n"`. Pi's bash tool inherits the full parent environment; secrets leak into tool subprocesses. |
| T6 | Cancellation / orphan | **ORPHAN = NO (plain kill suffices)** | Model ran `sleep 129` via bash tool. Child sleep (pid 17167) is in its **own process group** (pgid 17166 != pi pgid 17037, `same_group=no`), pi is its ancestor. A **plain `kill -TERM <pi-pid>`** (not the group) killed the sleep within 3s -> no orphan. Pi's `signalCleanupHandlers` (print-mode.ts) dispose the runtime + child tree on SIGTERM. **Tree-kill NOT required.** |
| T7 | Cascade/error shape | **machine-readable** | Bad model id (good key): `message_end` assistant `stopReason:"error"`, `errorMessage='400: {"message":"qwen/this-model-does-not-exist-9z is not a valid model ID","code":400}'`, `agent_end.willRetry=false`. Bad key: `stopReason:"error"`, `errorMessage='401: {"message":"User not found.","code":401}'`, `willRetry=false`. Both fail **fast**. Note: pi process **exits 0** even on error in `--mode json` (error surfaced via `stopReason`, not exit code; text mode exits 1). |
| T8 | Cost / wall-clock | see below | Golden (summed over 4 assistant turns): in/out/total tokens **5154/289/17219**, cost **$2.63e-04** (`usage.cost.total`, incl. cacheRead 11776 tok), agent-exec **~6.1s** (session event to last message_end timestamp; excludes process boot). |

## TASK SUCCESS - PASS
Golden edit landed correctly (`edit` toolResult: "Successfully replaced 1 block(s)"). Verified by running the file:
- `node cli.js --version` -> **`1.4.2`** OK
- `node cli.js` -> **`hello`** OK
Edited `cli.js` reads `package.json` version via `fs.readFileSync(path.join(__dirname,'package.json'))`. Only `cli.js` changed.

## TOTALS (scored runs, `--thinking off`)
| run | tokens (total) | cost USD | agent-exec | outcome |
|-----|----|----|----|----|
| golden (read,edit,bash) | 17219 | 2.63e-04 | 6.1s | stop, DONE_GT, task OK |
| T3 (read-only) | 98241 (23 read turns) | 1.15e-03 | 33.1s | error (repetitive reads; no edit) |
| T4 (sysprompt) | 484 | 1.53e-05 | <1s | stop, SENTINEL present |
| T5 (env) | 6847 | 1.34e-04 | 1.7s | stop, decoy leaked |
| T7 badmodel | 0 | 0 | <1s | error 400, willRetry=false |
| T7 badkey | 0 | 0 | <1s | error 401, willRetry=false |
Cost source = pi's own `usage.cost.total`, reported per assistant message and summed across turns (`analyze.py`). An earlier version of `analyze.py` kept only the last turn's usage, which under-reported golden at 329/2/4427 tokens and $3.47e-05. Model is cheap; dominant cost was cacheRead in golden.

## NOTES / GOTCHAS
- No `--cwd` flag; pi uses process cwd - run from inside the fixture.
- `--mode json` writes each event via `writeRawStdout` at **message boundaries only** (no token deltas); a hung/never-completing message = empty stdout until exit (mid-run files look empty even when alive).
- Tool names are exact: `read, edit, write, bash`. Allowlist `-t`, denylist `-xt`, `-nt/--no-tools`, `-nbt` all present.
- First run seeds `.pi/{auth.json,models-store.json,sessions/}` (startup network op; `--offline` to skip).
- `--thinking` levels: off, minimal, low, medium, high, xhigh, max.
