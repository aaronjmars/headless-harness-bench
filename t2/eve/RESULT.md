# Tier-2 DYNAMIC harness test - eve

- Binary: `eve` (**eve 0.60.1**, repo `vercel/eve`, Apache-2.0)
- Model: `openrouter/qwen/qwen3.7-flash` (same OpenRouter model as the cohort)
- Runtime: Node v26.8.1. macOS. Docker 29.4.0 for the sandbox backend.
- Shape: eve is a **durable-workflow framework**, not a drop-in CLI. An agent is a
  project: `agents/main/agent/agent.ts` (`defineAgent({model})`) + `instructions.md`
  (the system prompt) + an optional `sandbox/`. A control plane must scaffold the
  project before driving `eve invoke`.
- **Provider note (like fx):** `eve` is built on the Vercel AI Gateway. `eve init
  --model openrouter/...` is REJECTED ("not in the AI Gateway model catalog"). To run
  on the cohort's OpenRouter model, the gateway was bypassed by authoring a custom
  provider in `agent.ts` (`createOpenAICompatible({baseURL:"https://openrouter.ai/api/v1"})`)
  plus `modelContextWindowTokens` to skip the gateway context-window lookup. This is the
  only way to reach OpenRouter; the shipped default path is gateway/API-key only.
- Sandbox backend matters: the DEFAULT `microsandbox` (microVM) **hung >140s** trying to
  boot infra that was not installed. `just-bash` (in-memory) runs but has **no real
  `node`**. The golden below used the `docker` backend (real Linux + node).

## Exact golden invocation
```
eve invoke "<task>"          # OPENROUTER_API_KEY in env; agent.ts routes to OpenRouter
```
No `--model` / `--system` / `--tools` / `--max-time` on `invoke`; all live in files/config.
`--stream-json` does NOT exist on eve (that is amp) - `invoke` emits ONE final object.

## Summary table

| Test | Verdict | Score | Evidence |
|------|---------|-------|----------|
| T1 Boot-to-JSON | PASS w/ caveat | 2/3 | rc=0. `eve invoke` prints human `eve: opening sandbox ...` progress rows AND then the final object `{status:"ready",outcome:{status:"completed",message},resume:{session:{sessionId}}}` **on the same stdout stream**. A driver must strip the `eve:` chatter and take the trailing JSON. Exits clean; durable session state persists on disk for `--resume`. (`golden-docker.out`) |
| T2 Structured-parse | 1/4 inline, 3/4 in 2 steps | 2/3 | `invoke` stdout: assistant **text YES** (`outcome.message`); tokens/cost/tool-calls **NO**. A second `eve traces --json` keyed by `sessionId` yields tokens (`agent.usage.input_tokens/output_tokens`, ~25k in / ~966 out) and ordered tool calls (`read_file,write_file,bash`) - but **no USD cost** off-gateway. (`golden-trace.json`) |
| T3 Tool-allowlist | NOT gated by naive config | 1/3 | `defineAgent({defaultTools:false})` did NOT drop the shell tool - the attached sandbox re-adds `bash`, and the run called it (message = "bash", 1 tool_use). eve's real per-tool control is the approval-policy (`auto/always/never/once`) in code, not a per-run allowlist flag. (`t3.out`) |
| T4 System-prompt injection | MECHANISM WORKS / model non-compliant | 2/3 | Sentinel added to `instructions.md` ("end with SENTINEL_9Z"); output was exactly `ready` (system prompt in effect) but **no SENTINEL** (qwen3.7-flash ignored it, same as flue/opencode). (`t4.out`) |
| T5 Env isolation | ISOLATED | 3/3 | `DECOY_SECRET=leakme9Z` on host; docker sandbox `env\|grep DECOY \|\| echo NO_DECOY` -> **`NO_DECOY`**, zero `leakme9Z` in output. The container cannot see the host env (it also could not see host `/tmp/eve2`). Best-in-class containment, matching dsh. (`t5.out`) |
| T6 Cancellation | invoke clean; container lingers | 2/3 | docker sandbox ran `sleep 30`. `SIGTERM` to `eve invoke` -> **no host orphan**, invoke exits; but the `ghcr.io/vercel/eve` **container stays `Up`** (same id before + after). It is a pooled/reusable sandbox, not a per-call orphan - but it outlives the driver and must be reaped separately (`docker rm`). (`t6.out`) |
| T7 Error shape | machine-readable status | 2/3 | Bad key -> top-level `status:"failed"` + exit 1 (`t7key.out`); the granular auth cause is a raw JS stack on **stderr**, not a typed field in the JSON. Routable on `status`+exit code; no provider-error taxonomy. |
| T8 Cost/wall | info | n/a | wall **20.7 s** steady (one-time docker image pull = 106 s). tokens via `traces`; **no USD** off-gateway. Boots a Nitro host per `invoke` (cold-start); a driver doing many one-shots should run `eve dev`/`start` once and drive `eve invoke --url`. |

## TASK SUCCESS: YES
- On the `docker` backend the agent edited **only** `cli.js`, then ran (in-container)
  `node cli.js --version` -> `1.4.2` and `node cli.js` -> `hello` (both exit 0),
  self-verified, printed `DONE_GT`. (`golden-docker.out`) The `write_file` tool call is
  in `golden-trace.json`. (On `just-bash`, the edit was made correctly but self-verify
  was impossible - no `node` in that backend.)

## T1-T7 total: 14/21

## Notes
- Auth is Vercel-gateway/API-key centric: no OpenRouter out of the box (custom-provider
  shim required), no Claude-subscription OAuth.
- Standout strengths: real sandboxes (docker/microVM/just-bash) with host-env isolation,
  egress allowlists, per-tool approval policies, project-scoped discovery (no `$HOME`
  MCP leak), and credentials excluded from `invoke` output by design.
- Frictions for a headless driver: observability is a 2-step trace retrieval (no inline
  usage, no JSONL stream); stdout co-mingles `eve:` progress with the result object; no
  per-run overrides on `invoke`; a Nitro host + (with docker) a lingering sandbox
  container per driver.
- `agent/`, `golden-trace.json`, and per-test `*.out` captures are included.
