# Tier-2 DYNAMIC harness result - nanocodex (gakonst/nanocodex v0.6.6)

Date: 2026-10-04 · Binary: release asset `nanocodex-aarch64-apple-darwin` (v0.6.6, commit `7fcc3e7`, SHA256 checked against the release `SHA256SUMS`), unmodified.
Model: **`xiaomi/mimo-v2.6-pro` via OpenRouter**, NOT `qwen/qwen3.7-flash` (see "Why not qwen"). T1-T7 + task success are valid harness evidence; **T8 cost/wall is not comparable** to the qwen cohort.

## EXACT INVOCATION
```
env HOME=$WORK/home CODEX_HOME=$WORK/home/.codex NANOCODEX_COMPUTER=off OPENAI_API_KEY=$OPENROUTER_API_KEY \
  nanocodex run --api-base-url https://openrouter.ai/api/v1 --responses-transport https --store-responses false \
    --websocket-warmup false --mcp-defaults false --mcp-codex-config false --rollouts false --subagents false \
    --image-generation false --web-search false --memory false \
    --model mimo-v2.6-pro --model-id-prefix xiaomi --thinking low --cwd <dir> "<task>"
```
Scripts: [`run_batch.sh`](run_batch.sh) (golden, T4, T5, T7), [`run_t6.sh`](run_t6.sh). The five `false` flags plus the isolated `HOME`/`CODEX_HOME` are needed because those loaders default **on** and read operator state (`$CODEX_HOME/config.toml` MCP servers, a public MCP catalog, rollouts, memory, macOS computer-use). `--model-id-prefix` requires `--responses-transport https`; mimo rejects `--thinking none`, so `low` is used.

## Why not qwen
1. The CLI only accepts a closed model enum (`gpt-6.1-sol`, `gpt-6-luna`, `gpt-6-astra`, `glm-5.3`, `kimi-k3`, `mimo-v2.6-pro`). `--model qwen/qwen3.7-flash` fails locally: `error: invalid value 'qwen/qwen3.7-flash' for '--model <MODEL>'`, rc=2 ([`t7_badmodel_local.err`](t7_badmodel_local.err)).
2. A local proxy that rewrites the model id ([`model_rewrite_proxy.py`](model_rewrite_proxy.py)) gets the request to qwen, but Code Mode (always on, no flag) exposes its `exec` tool as a freeform Responses `custom` tool. Alibaba, qwen's OpenRouter provider, rejects it: `'function' is a required property, expected an object - 'tools.0'` ([`qwen_blocked.jsonl`](qwen_blocked.jsonl)). Running qwen would need a source patch to Code Mode, so the run used mimo, which nanocodex supports natively and which takes the same OpenRouter key.

## T1 to T8

| # | Test | Score | Evidence |
|---|------|-------|----------|
| T1 | Boot-to-JSON | **3/3** | rc=0; stdout is JSONL from the first line (`run.started`, `input.accepted`, `model.*`, `tool.call`, `tool.result`, `assistant.message`, `run.completed`). Every record has `protocol_version`, `request_id`, `seq`, `type`, `payload`. ([`golden.jsonl`](golden.jsonl)) |
| T2 | Structured-parse | **4/4 (3/3)** | One process, no second call: (1) final text `DONE_GT` in `assistant.message`; (2) tokens in `run.completed.payload.usage` (`input_tokens` 35,157 incl. `cached_input_tokens` 33,280, `output_tokens` 1,210, `reasoning_output_tokens` 420); (3) USD `cost_usd` 0.002002315 with `cost_status:"estimated_from_usage"` (client-side price table, not provider-billed); (4) ordered `tool.call`/`tool.result` (Code Mode `exec` wrapping `exec_command` and `apply_patch`). |
| T3 | Tool-allowlist | **no per-run mechanism (1/3)** | `nanocodex run --help` has no tool allowlist: only on/off toggles for `--web-search`, `--image-generation`, `--subagents`, MCP. The shell (`exec_command`) and `apply_patch` are always on. An exact tool set needs the Rust SDK (`Tools::builder()` / `.tools(...)`). Not live-tested because there is nothing to pass. |
| T4 | System-prompt injection | **PASS (3/3)** | `--instructions "...end with SENTINEL_9Z"` (replaces the whole system prompt) -> `ready` + `SENTINEL_9Z` ([`t4.jsonl`](t4.jsonl)). An `AGENTS.md` in `--cwd` with the same rule (keeps the default prompt) -> `ready` + `SENTINEL_9Z` ([`t4b.jsonl`](t4b.jsonl)). No `--append` flag; AGENTS.md is the append path. |
| T5 | Env isolation | **SCRUB BY NAME (3/3)** | Env `DECOY_SECRET=leakme9Z FAKE_API_TOKEN=secret9Z DECOY_PLAIN=plain9Z` plus a cwd `.env` with `DOTENV_PLAIN=dot9Z`; tool ran `env \| grep -E 'DECOY\|FAKE\|DOTENV'` -> output only `DECOY_PLAIN=plain9Z` and `DOTENV_PLAIN=dot9Z` ([`t5.jsonl`](t5.jsonl)). Secret-named vars and `OPENAI_API_KEY` are stripped (`env_clear` + denylist); plain names leak, as with dsh. Extra finding: the CLI auto-loads the **process cwd `.env`** (`dotenvy::dotenv()`), and its non-secret-named values reach the shell. |
| T6 | Cancellation / orphan | **ORPHAN = NO (3/3)** | Model ran `sleep 129` through the shell tool. The sleep had its own pgid (81062 != nanocodex 80839). A plain `kill -TERM <nanocodex-pid>` (not the group) -> nanocodex exited, sleep gone within 3s, and the stream ended with `run.failed` `status:"cancelled"` ([`t6.log`](t6.log), [`t6.jsonl`](t6.jsonl)). |
| T7 | Cascade/error shape | **machine-readable (3/3)** | Bad key (captured with a fake `sk-or-v1-...` key; the script now passes `not-a-real-key`, which gives 401 `Missing Authentication header` in the same shape): `model.attempt.failed` (`error_class:"https_rejected"`, `retryable:false`), `run.error` with the provider's `401 User not found.`, `run.failed`, rc=1 ([`t7_badkey.jsonl`](t7_badkey.jsonl)). Bad upstream model: same shape with `400 ... is not a valid model ID`, rc=1 ([`t7_badmodel_upstream.jsonl`](t7_badmodel_upstream.jsonl)). Only the local enum rejection is plain clap text on stderr, rc=2. |
| T8 | Cost / wall-clock | measured, **not comparable** (mimo) | Golden: wall **33.2s** (process, [`batch.log`](batch.log)), 35,157 in (33,280 cached) / 1,210 out, **$0.0020** client-estimated. Default prompt front-load ~6.3k tokens (T4b: 6,356 input for "Say the word ready."). |

## TASK SUCCESS - PASS
`apply_patch` edited only `cli.js`; the model then ran both modes itself. Verified after the run: `node cli.js --version` -> `1.4.2`, `node cli.js` -> `hello` ([`batch.log`](batch.log)).

## NOTES / GOTCHAS
- Default-on loaders that read operator state: `--mcp-codex-config` (`$CODEX_HOME/config.toml` MCP servers), `--mcp-defaults` (public MCP catalog), `--rollouts`, `--memory`, macOS computer-use (`NANOCODEX_COMPUTER=off`), and the cwd `.env`. A driver must turn each off and isolate `HOME`/`CODEX_HOME`.
- stderr carries INFO tracing with full model input/output content by default (`trace content content_kind="model.input"`). Lower `--log-filter` or discard stderr if prompts are sensitive.
- USD is computed client-side from a built-in price table per enum model, so it is only right for the six supported models.
- The OpenRouter account id in error bodies is redacted to `user_REDACTED` in the committed evidence.
- No wall-clock timeout flag; the driver must enforce one (SIGTERM cancels cleanly).
