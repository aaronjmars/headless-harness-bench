# Tier-2 DYNAMIC harness test - Crush (Charmbracelet)

- Harness: `crush` **v0.95.0** (installed via `npm i -g @charmland/crush`; postinstall downloads the Go binary on first run).
- Model: `qwen/qwen3.7-flash` via OpenRouter (custom OpenAI-type provider `orx` in `crush.json`).
- Fixture: `/Users/aaron/Downloads/harness-bench/t2/crush/fixture` (package.json v1.4.2 + cli.js).
- Data dir: `-D .../t2/crush/.crush`. Config isolation: `CRUSH_GLOBAL_CONFIG` + `CRUSH_GLOBAL_DATA` (see caveat 1).

## HEADLINE FINDING - plain-text `run` vs structured `session --json`
- `crush run` stdout is **PLAIN TEXT** (with `-q`, only the final assistant message). There is **no `--json`/`--output-format` flag on `run`.
- Structured output is a **separate, 2-step path**: run the task, then `crush session show <id> --json`. That JSON carries `meta` (cost, prompt/completion/total tokens) **and** the full message transcript (`parts[]` with ordered `tool_call` name+input and `tool_result` content). `crush session list --json` lists ids. A third path exists: `crush server` (unix-socket or TCP via `-H`) exposes an HTTP+SSE API.
- So: **not boot-to-JSON in one shot, but fully machine-readable via `session show --json` after the run.**

## Results

| Test | Verdict | Evidence |
|---|---|---|
| T1 Boot-to-JSON | run=TEXT (fail) / session --json=PASS (~2/3) | `crush run -q` gives literal `DONE_GT`, no JSON. `crush session show <id> --json` gives full JSON. `session --help`: "Agents can use --json". |
| T2 Structured-parse | **4/4 fields, 2-step (2/3)** | All 4 fields exist, but only via a second `crush session show <id> --json` call (`run` stdout is plain text), so scored 2/3, the same 2-step rule as eve's `traces --json`. From `session show --json`: final text `"DONE_GT"`; `prompt_tokens=26325`, `completion_tokens=10`, `total_tokens=26335`; `cost=0.00087278`; ordered tool_calls `glob,glob,view,view,edit,bash` (each with input + tool_result). |
| T3 Tool-allowlist | **PASS (3/3)** | Mechanism = `options.disabled_tools:["bash"]` (config-only, no per-run flag). Model *attempted* bash; runtime returned `tool not found: bash. Available tools: agent, ... (bash absent)`. `echo T3_RAN` never ran. |
| T4 System-prompt injection | **PASS (3/3)** | Mechanism = `CRUSH.md` context file in cwd (also `AGENTS.md`/`CLAUDE.md`/`.cursorrules` per `defaultContextPaths`, source-confirmed). No `--append` flag. Forceful CRUSH.md gave output ending `SENTINEL_9Z`. (Weak default phrasing was ignored by qwen; file still loads.) |
| T5 Env isolation | **LEAK (0/3)** | `DECOY_SECRET=leakme9Z` + task `env \| grep DECOY` gave bash output `DECOY_SECRET=leakme9Z`. Bash tool inherits the **full parent env**. No isolation. |
| T6 Cancellation | **PASS (3/3)** | Task ran `/bin/sleep 60` (real child pid, PPID=crush worker). `kill -INT` the `crush run` client reaped the child sleep, worker exited, stderr `Context canceled.` No orphan. (run's worker is a child of the client, not the persistent `crush server`.) |
| T7 Cascade/error shape | text-only (1/3) | Bad key (isolated): exit 1, stderr styled text `Agent processing failed: ... unauthorized: Missing Authentication header.` Bad model: exit 1, `Failed to override models: large model "orx/nonexistent-model-zzz" not found.` **Not machine-readable on `run`**: only the exit code is routable; the cause is styled free text, so scored 1/3 (eve gets 2/3 for a JSON `status` field, omp/pi/dsh/fx get 3/3 for typed JSON errors). No Claude-subscription OAuth (API-key only). See caveat 3 (silent cross-provider fallback). |
| T8 Cost/wall-clock | measured | Golden `crush run`: **wall=61s**, cost=**$0.00087278**, prompt=26325, completion=10 (partial; see caveat 4), total=26335. Source = `session show --json` meta. |
| **TASK SUCCESS** | **PASS** | `node cli.js --version` gives `1.4.2`; `node cli.js` gives `hello`; only cli.js edited (package.json untouched). |

## Exact invocations
```
# Golden task (headless, auto-approved via permissions.allowed_tools):
cd fixture && OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  crush run -q -D ./.crush "<golden task prompt>"

# Structured output (2-step):
crush session list --json -D ./.crush
crush session show <id> --json -D ./.crush     # meta.cost, meta.*_tokens, messages[].parts[]

# Full config isolation from operator ~/.config/crush:
export CRUSH_GLOBAL_CONFIG=/tmp/iso/config CRUSH_GLOBAL_DATA=/tmp/iso/data
```
`crush.json`: custom provider `orx` (type `openai`, base_url `https://openrouter.ai/api/v1`, api_key `$OPENROUTER_API_KEY`, model `qwen/qwen3.7-flash` w/ cost metadata) + `models.large`/`models.small` pointing at orx + `permissions.allowed_tools` (headless auto-approve, no prompts) + `options.disabled_tools` for T3.

## Caveats / gotchas
1. **`-D` isolates DATA only, NOT config.** Crush merges the operator's global `~/.config/crush/crush.json`. This contaminated the first bad-key run (it silently succeeded via a globally-configured alternate provider). True isolation needs `CRUSH_GLOBAL_CONFIG` + `CRUSH_GLOBAL_DATA`.
2. **Security note for Aaron:** `~/.config/crush/crush.json` stores a provider **API key in plaintext** (ZAI). Value not reprinted here.
3. **Silent cross-provider fallback:** with multiple providers offering the same model id (global config present), a bad key on the selected provider fell through to another provider serving `qwen/qwen3.7-flash` and answered normally. With an isolated single-provider config, a bad key is a hard 401.
4. **`completion_tokens` in session meta looks last-turn-only** (10 for golden, 51 for T3); `prompt_tokens`/`total_tokens` are reliable; treat output-token count as approximate. Cost figure appears consistent.
5. Model `qwen/qwen3.7-flash` is **not in crush's bundled openrouter catalog**, so it was defined (with cost_per_1m) in a custom provider for cost tracking.
6. Headless auto-approve = `permissions.allowed_tools` (config array); no per-run allow flag besides `--yolo`. Worked with zero hung prompts.
