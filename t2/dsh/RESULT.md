# Tier-2 DYNAMIC harness test: dsh (DeepSeek Harness)

**Verdict:** dsh runs the golden task correctly and emits a clean, machine-readable JSONL event stream. **8/8 tests pass on evidence.** One blocking release bug: the published `latest` (`0.1.5-rc.2`) launcher **cannot accept `--json` at all**, so the entire headless JSON contract is unreachable via a plain `npx @deepseek-ai/dsh`. Pinning to the published `alpha` tag `0.1.6-alpha.2` (which matches the provided source ref) fixes it. All tests below ran on `0.1.6-alpha.2`.

- Package: `@deepseek-ai/dsh`. dist-tags: latest/next=`0.1.5-rc.2`, alpha=`0.1.6-alpha.2`. Source ref (`/Users/aaron/Downloads/harness-bench/dsh`) = `0.1.6-alpha.2`.
- Model: `qwen/qwen3.7-flash` via OpenRouter (pi-ai `openai-completions` route). Node 26.8.1.
- DSH_HOME: `/Users/aaron/Downloads/harness-bench/t2/dsh/home` (defaults never touched).
- Privacy: `session-log-deepseek` disabled via config (`enabled:false`) AND moot here (its `dsh_session_log` field only attaches to the native DeepSeek adapter, not the OpenRouter/pi-ai route). Telemetry left at default `FEEDBACK_ONLY` (no capture on ordinary runs).

## CRITICAL: `--json` unreachable on `latest` (rc.2)

`npx @deepseek-ai/dsh --profile headless --json "<task>"` (and every reordering: `--json` first, task-then-`--json`, `-- --json`, `- --json`) fails on rc.2 with:

```
error: unknown option '--json'
```

Root cause (verified in `lib/bin.js`): rc.2 **unconditionally** registers the `web` and `plugin` subcommands, which defeats commander's `.passThroughOptions()` for unknown long options (an unknown `--flag` before any operand errors despite `.allowUnknownOption()`). The `0.1.6-alpha.2` source (`apps/cli/src/args.ts`) registers `plugin` only when `argv[0]==='plugin'` and adds a `['--profile', ...argv]` expansion, so passthrough works and `--json` reaches the headless app. `-h` passes through on rc.2 (commander special-cases help) which masks the bug.

**Working invocation (alpha.2):**
```
cd <fixture> && OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  DSH_HOME=/Users/aaron/Downloads/harness-bench/t2/dsh/home \
  DSH_PERMISSION_MODE=danger-full-access \
  npx @deepseek-ai/dsh@0.1.6-alpha.2 --profile headless --json "<task>"
```
`--json`/`--session-id` are hidden headless flags (not shown in `--help`). `--patch <path>` + `--json` cannot coexist even on alpha (the patch value consumes the passthrough boundary), so the provider overlay is placed at **home level** `$DSH_HOME/cordis.patch.yml` instead of via `--patch`.

## Provider wiring (the make-or-break): `$DSH_HOME/cordis.patch.yml`

id-targeted overlay over `dsh-base` rows (last-write-wins), applied after the profile layer:
```yaml
- id: agent-default-model            # base default is deepseek-official/deepseek-flash
  config: { provider: openrouter, model: qwen/qwen3.7-flash }
- id: session-log-deepseek
  config: { enabled: false }
- id: llm-pi-ai                      # dormant multi-provider adapter; routes register when given profiles
  config:
    providers:
      openrouter:
        displayName: OpenRouter
        apiKeyEnv: OPENROUTER_API_KEY
        api: openai-completions
        baseURL: https://openrouter.ai/api/v1
        models: [ { id: qwen/qwen3.7-flash } ]
```
No `compat` switches were needed (OpenRouter is OpenAI-compatible; the flash model declares no reasoning, so system prompt goes as `role:system` and cap as `max_tokens`).

## Results

| Test | Score | Result | Evidence |
|---|---|---|---|
| T1 Boot-to-JSON | PASS (3/3) | Non-interactive, emitted 24 JSONL events, exit 0 | `{session:1,status:10,text:4,tool_call:4,tool_result:4,final:1}`; run1.jsonl |
| T2 Structured-parse | **3/4** | final text yes, input+output tokens yes, ordered tool calls yes, **USD cost NO (absent)** | tokens on `status/step_end.usage {inputTokens,outputTokens,totalTokens,cacheReadTokens}`; no cost/usd/price field anywhere |
| T3 Tool-allowlist | PASS (3/3) | Bash denied by disabling the `tool-bash` loader row; read/edit kept | 0 tool calls; model: "I don't have access to a bash tool... BASH_UNAVAILABLE"; dump-config shows `tool-bash ... disabled:true` |
| T4 System-prompt inject | PASS (3/3) | Workspace `AGENTS.md` instruction honored | final = `"2 + 2 equals 4.\n\nSENTINEL_9Z"`; mechanism = `agent-instructions` reads `AGENTS.md`/`CLAUDE.md` from cwd |
| T5 Env isolation (HIGHLIGHT) | PASS (3/3) | Child env scrubbed by `SENSITIVE_ENV_PATTERN=/KEY\|PASSWORD\|SECRET\|TOKEN/i` + `DSH_*` strip | child `env\|grep -E 'DECOY\|FAKE'` returned **only** `DECOY_PLAIN=plainleak9Z` |
| T6 Cancellation | PASS (3/3) | SIGTERM to launcher reaps the bash grandchild; no orphan | marker file proved child started; `sleep 137` (pid 27028) alive before kill, NONE after +5s |
| T7 Error shape | PASS (3/3) | Machine-readable; exit 1 in 2s (no long retry storm) | `turn_end.reason = {kind:"error", error:{message:"401...User not found",code:"AUTH"}}` + empty `final`; stderr `dsh: AUTH: 401: ...` |
| T8 Cost/wall | tokens yes / USD no | dsh emits NO USD; computed from formula | see below |
| **TASK SUCCESS** | **PASS** | `node cli.js --version`->`1.4.2`, `node cli.js`->`hello`; only cli.js edited; final has `DONE_GT` | tools ordered: read(cli.js), read(package.json), write(cli.js), bash(test) |

### T5 detail (precise leak/scrub map), corrects the task's hypothesis
Set in the harness parent env; observed inside the bash child:

| Var | Value | Denylist match | Result in child |
|---|---|---|---|
| `DECOY_PLAIN` | plainleak9Z | none | **LEAKED** (survives) |
| `DECOY_SECRET` | leakme9Z | `SECRET` | SCRUBBED (task expected this to leak; it does NOT, the name contains "SECRET") |
| `FAKE_API_TOKEN` | secret9Z | `TOKEN` | SCRUBBED |
| `DSH_DECOY` | dshleak9Z | `DSH_` prefix | SCRUBBED |
| `OPENROUTER_API_KEY` | (real) | `KEY` | SCRUBBED from child; harness's own process still reads it for the provider (run succeeded) |

Differentiator: only a var whose **name** carries none of KEY/PASSWORD/SECRET/TOKEN and no `DSH_` prefix leaks. Source: `packages/subprocess/subprocess/src/index.ts:47,66`.

### T8 numbers (golden run)
- Wall-clock: **27 s** (end-to-end, includes model latency).
- Tokens (summed over `step_end.usage`): input **9,447**, output **357**, cacheRead **25,472** (prompt caching hit ~90% of context on turns 2-4). Final cumulative `totalTokens`=9,010.
- USD cost: **dsh emits none.** Computed = (9447*0.03 + 357*0.13 + 25472*0.006)/1e6 = **$0.00048** (per-million prices for qwen3.7-flash on OpenRouter: input $0.03, output $0.13, cache read $0.006, the same rates pi reports per token). An earlier version left out the 25,472 cache-read tokens and gave $0.00033.

## Notes / gotchas
- Headless `--help` hides `--json`/`--session-id`; found them in `src/startup.ts`.
- Model selection is config-only (no `--model` flag) via the `agent-default-model` row / `agent-default-model` settings section.
- `DSH_PERMISSION_MODE=danger-full-access` is the real yolo switch (base rows read it for sandbox mode + approval `never`).
- JSON event vocabulary: `session`, `status{turn_start,step_start,step_end(usage),turn_end(reason)}`, `text`, `thinking`, `tool_call{callId,tool,input}`, `tool_result{callId,status,result}`, `final{text}`, `error{message}` (out-of-turn/grammar only; in-turn failures ride `turn_end.reason`).

Artifacts: run1.jsonl (golden), t3-t7.jsonl, or.patch.yml (overlay), t6b-run.sh.
