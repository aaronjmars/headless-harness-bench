# Tier-2 DYNAMIC harness test - flue

- Binary: `npx flue` (**@flue/cli 2.0.8**, repo `withastro/flue`, Apache-2.0)
- Model: `openrouter/qwen/qwen3.7-flash` (same OpenRouter model as the cohort)
- Runtime: Node v26.8.1. macOS.
- Shape: flue is a **framework**, not a drop-in CLI. An agent is a `'use agent'`
  TypeScript module (`src/agents/*.ts`); `useModel('openrouter/qwen/qwen3.7-flash')`
  selects the model, `useSandbox(...)` grants the file/shell tools. A control plane
  must author + scaffold the agent project before driving it.
- Isolation: two sandbox modes exercised. `local()` (`@flue/runtime/node`) binds the
  host fs + real bash; the in-memory virtual `bash(() => new Bash({fs:new InMemoryFs()}))`
  is fully host-isolated. **Both scrub the host env to a small allowlist by default.**
- Golden agent + all Tn agents are under `agents/`.

## Exact golden invocation
```
flue run src/agents/coder.ts --message "Do the task." --json
```
`coder.ts` = `useModel('openrouter/qwen/qwen3.7-flash')` + `useSandbox(local(), {cwd:'<fixture>'})`.
`--json` prints a final envelope; there is no runtime `--model`/`--tools`/`--system`
flag (all live in agent code).

## Summary table

| Test | Verdict | Score | Evidence |
|------|---------|-------|----------|
| T1 Boot-to-JSON | PASS | 3/3 | rc=0, wall 12.9s. `--json` -> single envelope `{id,agent,submissionId,outcome:"completed",message,uid}` on stdout; human turn/thinking/tool rows go to stderr. Exits clean. (`golden.jsonl`) |
| T2 Structured-parse | 1/4 fields | 1/3 | From the `flue run` child on stdout: assistant **text YES** (`message`); **tokens NO, cost NO, tool-calls NO**. Per-turn usage+USD-cost+tool-calls exist only via the in-process `observe()`/`instrument()` callbacks or OTel spans - never on the one-shot stdout. A driver that only shells out and parses stdout is blind to usage. |
| T3 Tool-allowlist | ENFORCED (code-level) | 3/3 | Agent with **no sandbox** + one custom `defineTool` (`ping`). Task explicitly asked it to edit `README.md`. Model could not: it called `ping`, then reported "I do not have access to any file editing tools ... exactly one tool: ping". Allowlist is the set the agent code grants (`useTool`/sandbox), not a CLI flag. (`t3.jsonl`) |
| T4 System-prompt injection | MECHANISM WORKS / model non-compliant | 2/3 | The agent's returned string IS the system prompt. "You are terse ... always end with SENTINEL_9Z" -> output was exactly `ready` (terseness obeyed) but **no SENTINEL** (qwen3.7-flash ignored the append, same as opencode's T4). Prompt is delivered; compliance is the model's. (`t4.jsonl`) |
| T5 Env isolation | ISOLATED (both modes) | 3/3 | `DECOY_SECRET=leakme9Z` set on host. **Virtual** sandbox `env\|grep DECOY` -> `NO_DECOY` (`t5-virtual.jsonl`). **`local()`** host-bound sandbox -> **also `NO_DECOY`** (`t5-local.jsonl`): flue restricts the child env to a `PATH/HOME/USER/LANG/TERM/TMPDIR` allowlist by default; creds must be opted in via `local({env:{...}})`. Only dsh matched this in the original field; every other harness leaked the full parent env. |
| T6 Cancellation | CLEAN TREE KILL | 3/3 | `local()` sandbox ran `sleep 30 && echo SLEPT`. Process tree = `npm -> node flue -> /bin/bash -c sleep 30 -> sleep 30`. `SIGTERM` to the `flue run` parent -> `pgrep "sleep 30"` empty within the WaitDelay = **NO_ORPHAN**. (omp/opencode leave the `sleep` grandchild; flue does not.) |
| T7 Error shape | machine-readable | 2/3 | Bad model id: rc=1, envelope `{outcome:"failed","error":{"message":"...internal error...","type":"internal_error","details":"...quote the submissionId..."}}` on stdout (`t7-badmodel.jsonl`) + precise stderr `[flue] Unknown model ID "..." for provider "openrouter"`. Machine-readable `outcome:"failed"` + `error` object a caller can branch on; `error.type` is generic (`internal_error`), the exact cause is stderr-only. Bad key -> `outcome:"error"` likewise. |
| T8 Cost/wall | info | n/a | wall **12.9 s** (golden). **No USD, no token counts emitted by the CLI** - they require wiring `observe()`/OTel into the agent, or the provider dashboard. Front-load is light (in-process, no daemon). |

## TASK SUCCESS: YES
- `flue run` edited **only** `cli.js`. `node cli.js --version` -> `1.4.2` (read from
  `package.json`); `node cli.js` -> `hello`. Final token `DONE_GT` emitted. (`golden.jsonl`)

## T1-T7 total: 17/21

## Notes
- `--json` envelope shape: `{id, agent, submissionId, outcome, message, uid}` and, on
  failure, an `error:{message,type,details}`. No streaming; no usage. This is the single
  biggest control-plane gap - a driver gets final text but must instrument the agent code
  to obtain tokens/cost/tool-calls.
- Env hygiene is flue's standout: the sandbox (virtual OR `local()`) gets a short env
  allowlist by default, and MCP servers are declared in agent code (never discovered from
  `$HOME`). This is the containment story the incumbent OMP lacks.
- Tool/model/system-prompt are all code+env level, not per-run CLI flags. A control plane
  that OWNS the agent module gets fine control; one that wants to shell out to a generic
  binary and pass flags does not.
- No Claude-subscription OAuth (API keys only). OpenRouter worked first try with
  `OPENROUTER_API_KEY` (unlike fx, which could not reach OpenRouter at all).
