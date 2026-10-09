# headless-harness-bench: scorecard, live tests and rankings (as of 2026-10-04)

This is the repo README as it stood on 2026-10-04 (last changed in #7), moved here unchanged
when the repo adopted the bench standard on 2026-10-09 (only relative links were fixed). The
machine-readable records are in [../runs/](../runs/) and [../RESULTS.md](../RESULTS.md); the
benchmark card is [../METHOD.md](../METHOD.md).

Benchmark comparing 9 coding-agent harnesses for the role of a **headless agent
loop driven by a control plane**: another program drives it as a child and parses,
scopes, and publishes its output. Scoring axis is *orchestratability by a control
plane*, not human-at-a-keyboard UX.

Harnesses: **omp** (Oh My Pi), **pi**, **fx** (Vercel), **opencode** (SST), **dsh**
(DeepSeek Harness), **crush** (Charmbracelet), **flue** (Astro), **eve** (Vercel),
**nanocodex** (gakonst, a Rust reimplementation of Codex).

> **flue + eve are frameworks, not drop-in CLIs.** Unlike the first six (invoke a
> binary, pass flags), a control plane must first author + scaffold a TypeScript
> agent project, then drive `flue run` / `eve invoke`. They are scored on the same
> headless-driver axis, with the scaffold held constant across both.

## TL;DR

- **Deploy-today rank (control-plane role): OMP > opencode > Pi.**
- **Capability rank: OMP ~= dsh > nanocodex > opencode > Pi > fx > Crush.**
- **flue + eve (frameworks) land mid-pack on Tier-1 (54.9 / 52.1 of 81)**: both bring
  best-in-class secret hygiene (env-scrub / sandbox isolation, no `$HOME` MCP leak) but
  lose on the driver contract - no per-turn JSONL on stdout, no per-run CLI overrides,
  no Claude-sub OAuth. Neither is a deploy-today swap; both are worth tracking.
- **nanocodex (added 2026-10-04) scores 62.5 / 81 and 19/21 live**, the best driver
  contract of the CLIs (one-process JSONL with tokens, USD and typed errors, env scrub,
  clean cancel), but it fails the deploy gate: pre-1.0, a closed model list that
  cannot run the cohort's qwen model, no per-run tool allowlist, and default-on
  loaders that read `$CODEX_HOME` MCP config and the cwd `.env`.
- All 9 completed the golden task once wired. The order is about auth fit, structured
  output, isolation, maturity, and cost - not raw ability.
- Full reasoning + file:line citations in **[BENCHMARK.md](../BENCHMARK.md)**; this
  README carries every finding as tables.

## 1. Identity + distribution

| | omp | pi | fx | opencode | dsh | crush | flue | eve | nanocodex |
|---|---|---|---|---|---|---|---|---|---|
| Language / runtime | TS + Rust / Bun | TS / Node 22+ | Zig (native 6 MiB) | TS / Bun | TS / Node 22+ (+Py wheel) | Go (native) | TS / Node 22+ (Vite) | TS / Node (Nitro) | Rust (native, 92 MB) |
| License | MIT | MIT | Apache-2.0 | MIT | MIT | FSL-1.1-MIT | Apache-2.0 | Apache-2.0 | Apache-2.0 / MIT |
| OSI-open? | yes | yes | yes | yes | yes | no (MIT after 2y) | yes | yes | yes |
| Version tested | 18.2.4 (live run: 18.2.0) | 1.0.2 (first run: 0.85.1) | 0.0.10 | 1.18.31 (live run: 1.18.30) | 0.1.6-alpha.2 | 0.95.0 | 2.0.8 (@flue/cli) | 0.60.1 | 0.6.6 |
| Maturity | stable | stable | **experimental** | stable | **alpha, no audit** | stable | stable (2.x) | **preview / beta** | pre-1.0, fast-moving |
| Stars | ~31.6k | ~106k (suspect) | new | ~208k | preview | ~28k | ~8.3k | ~5.3k | ~550 |
| Repo | can1357/oh-my-pi | earendil-works/pi | vercel-labs/fx | sst/opencode | deepseek-ai/deepseek-harness | charmbracelet/crush | withastro/flue | vercel/eve | gakonst/nanocodex |
| Install | binary (curl/brew/npm) | npm / bun-binary | curl (native) | npm/curl (bun-binary) | npm / npx / py-wheel | brew/npm (Go binary) | npm (@flue/cli) | npm (eve) | release binary (curl/npm/cargo) |
| Built-in tools | 31 | 7 | ~11 | ~14 | ~30 | ~30 (+LSP ops) | 6 (via sandbox) | ~14 | 5 + Code Mode (+web/image/subagents) |
| Edit format | **hashline** | search-replace | string-replace | search-replace (+apply_patch/GPT) | search-replace | search-replace + LSP | search-replace (edit) | **whole-file** (write_file) | `apply_patch` (grammar) |
| Shape | CLI | CLI | CLI | CLI | CLI | CLI | **framework** | **framework** | CLI |

## 2. Tier-1 weighted scorecard (static source audit)

Category mean 0-3 x weight; total /81. Roughly ordered by total (flue/eve/nanocodex appended).

| Category (weight) | OMP | dsh | opencode | Pi | fx | Crush | flue | eve | nanocodex |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A Headless orchestratability (5) | 2.8 | 2.5 | 2.5 | 2.8 | 2.2 | 2.0 | 2.0 | 1.7 | 2.2 |
| B Structured observability (4) | 2.8 | 2.3 | 2.8 | 2.8 | 2.2 | 1.8 | 2.0 | 2.2 | 2.8 |
| C Auth & multi-provider (4) | 3.0 | 2.3 | 2.8 | 2.8 | 2.3 | 2.2 | 2.0 | 1.8 | 2.2 |
| D Isolation & secret hygiene (4) | 1.0 | **2.6** | 1.4 | 1.4 | 1.6 | 1.4 | **2.6** | 2.4 | 1.8 |
| E Cancellation & process hygiene (3) | 2.0 | 2.0 | 2.0 | 1.5 | 2.0 | 1.75 | 1.5 | 2.0 | 2.5 |
| F Tooling power (2) | 3.0 | 2.4 | 1.6 | 1.0 | 1.6 | 2.2 | 1.6 | 1.2 | 1.8 |
| G Extensibility (2) | 2.4 | **3.0** | 2.2 | 2.4 | 1.6 | 1.2 | 2.4 | 2.2 | 2.8 |
| H Cost & license (3) | 2.6 | 2.4 | 2.4 | 2.4 | 3.0 | 2.8 | 2.0 | 1.8 | 2.6 |
| **Weighted total /81** | **66.1** | **65.6** | **61.6** | **60.9** | **56.6** | **52.1** | **54.9** | **52.1** | **62.5** |

Absolute totals carry ~+/-3 noise; trust the tiers and the per-axis findings below.
Totals come from the unrounded per-criterion scores, so recomputing them from the
rounded category means shown here can differ by up to ~0.4.

## 3. Contract-axis capability matrix

Every axis of the headless-driver contract, per harness. "-" = absent.

| Axis | omp | pi | fx | opencode | dsh | crush | flue | eve | nanocodex |
|---|---|---|---|---|---|---|---|---|---|
| Headless one-shot | `-p --mode json` | `-p --mode json` | `ask --json` (1 obj) | `run --format json` | `--profile headless --json` | `run` (PLAIN TEXT) | `run --json` (1 obj) | `invoke` (1 obj + chatter) | `run` (JSONL) |
| JSONL event stream | yes | yes | - (single obj) | yes | yes | - (needs `serve` SSE) | - (final envelope) | - (final obj; HTTP `/stream`) | yes |
| Token usage in output | yes | yes | yes | yes | yes | via `session show --json` | - (`observe()`/OTel only) | via `traces --json` (2-step) | yes |
| **USD cost in output** | yes (telemetry) | yes | **-** | yes | **-** | via `session show --json` | **-** | **-** (gateway-only) | yes (client-estimated) |
| Tool-call events | yes | yes | yes | yes | yes | via `session show --json` | - (`observe()`/OTel only) | via `traces --json` | yes |
| Per-run tool allowlist | `--tools` (leaky*) | `-t/-xt/-nt` exact | per-tool rules (shell-escapable) | `OPENCODE_PERMISSION` (hard-strip) | `ToolRestriction` allow/deny | config-only | code (`useTool`/sandbox) | approval-policy in code | - (on/off toggles for extras only) |
| Append-to-system-prompt | `--append-system-prompt` | `--append-system-prompt` | `--system` (replaces) | AGENTS.md / instructions | AGENTS.md / prompt section | CRUSH.md file | return string / `useInstruction` | instructions.md | AGENTS.md (`--instructions` replaces) |
| Per-run provider/model swap | yes | yes | yes (env) | yes | yes | yes | code (`useModel`) | `eve set` (persistent) | yes, closed model list |
| **Subscription OAuth via env token** | **yes** (`setup token`) | yes | - (codex/grok login) | **yes** (Claude sub) | - (grant only, no env) | - (API-key only) | - (API-key only) | - (gateway/API-key) | `CODEX_ACCESS_TOKEN` (ChatGPT Business/Enterprise only) |
| API key via env | yes | yes | yes (named) | yes | yes | yes | yes | yes | yes |
| **Child-env scrub by default** | - | - | - | - | **YES** | - | **YES** (allowlist) | **YES** (sandbox) | **YES** (secret-name denylist) |
| MCP transports | stdio/http/sse | - (extension) | stdio/http/sse | local/http/sse | stdio/http | stdio/http/sse | http/sse | http/sse | stdio/http |
| MCP `$HOME` auto-discovery leak | **yes** (needs isolated HOME) | n/a | no | no | no | no | no | no | **yes** (`$CODEX_HOME` + public catalog, default on) |
| Native computer-use / browser | **yes** (eval preludes) | - | - (WASM sandbox) | - (MCP) | opt-in plugin | - (MCP) | - (CF Computer remote) | - (web_fetch only) | yes (macOS, default on) |
| Wall-clock timeout | `--max-time` (soft) | - | - (no flag) | - | - | - (per-req only) | - (cooperative) | - (no invoke flag) | - |
| Programmatic API | RPC + ACP + SDK | RPC + SDK | **ACP** + SDK | HTTP+SSE + SDK + ACP | SDK + ACP | `serve` HTTP+SSE | HTTP + SDK | HTTP+SSE + ACP + SDK | SDK (Rust/npm/Py) + HTTP |

`*` omp `--tools` filters builtins but does not flip `restrictToolNames`, so MCP /
extensions still load unless you also isolate `$HOME` / pass `--no-extensions`.

## 4. Tier-2 live run

Golden task ("add a `--version` flag to a CLI, print DONE_GT") headless on
**`qwen/qwen3.7-flash` via OpenRouter**. **fx ran on grok-4.6** (its shipped binary
cannot reach an OpenAI-compatible endpoint), so its T8 is not comparable. **flue and
eve ran on the same OpenRouter model** (eve via a custom-provider shim - its default
path is Vercel-AI-Gateway-only, same class as fx). **nanocodex ran on
`xiaomi/mimo-v2.6-pro`** via OpenRouter: it rejects qwen (closed model list) and qwen's
provider rejects its freeform Code Mode tool, so its T8 is not comparable either.

| Test (0-3) | omp | pi | opencode | dsh | crush | fx(grok) | flue | eve | nanocodex(mimo) |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| T1 boot-to-JSON | 3 | 2* | 3 | 3 | 2^ | 3 | 3 | 2+ | 3 |
| T2 structured-parse (fields/4) | 3 (4/4) | 3 (4/4) | 3 (4/4) | 2 (3/4) | 2 (4/4)^ | 2 (3/4) | 1 (1/4) | 2 (1/4 inline)@ | 3 (4/4) |
| T3 tool-allowlist honored | 3 | 3 | 3 | 3 | 3 | 2~ | 3 | 1# | 1% |
| T4 sys-prompt injection | 2 | 3 | 2 | 3 | 3 | 3 | 2 | 2 | 3 |
| T5 env isolation | 0 | 0 | 0 | **3** | 0 | 0 | **3** | **3** | **3**$ |
| T6 cancel / no orphan | 0 | 3 | 0 | 3 | 3 | 3 | **3** | 2& | 3 |
| T7 error machine-readable | 3 | 3 | 2 | 3 | 1 | 3 | 2 | 2 | 3 |
| **T1-T7 total /21** | 14 | 17 | 13 | **20** | 14 | 16 | **17** | 14 | 19 |
| **TASK SUCCESS** | yes | yes | yes | yes | yes | yes | yes | yes | yes |

`*` pi hangs on qwen's reasoning stream until `--thinking off`. `^` crush `run` =
plain text; JSON needs 2-step `session show --json`. `~` fx tool-deny is
shell-escapable (model reroutes via un-denied `shell`).
`+` eve stdout co-mingles `eve:` progress rows with the final JSON object (strip to
the trailing object). `@` eve tokens+tool-calls need a 2nd `traces --json` keyed by
sessionId; no USD off-gateway. `#` eve `defaultTools:false` did not drop the sandbox
`bash`; per-tool control is the approval-policy in code, not a flag. `&` eve SIGTERM leaves
no orphan (host or container) and removes the container, but `invoke` lives ~14s more
while it tears down and reports `status:"running"` (resumable), not a cancel. flue's `local()` scrubs host env by default (T5) and does a clean
process-tree kill (T6); its `--json` carries no tokens/cost/tool-calls (T2).
`%` nanocodex has no per-run tool allowlist (only on/off toggles for web search, image
generation, subagents; the shell + patch tools are always on). `$` nanocodex scrubs
secret-named vars (`DECOY_SECRET`, `FAKE_API_TOKEN` gone) but a plain-named var and the
cwd `.env` (auto-loaded) still reach the shell, the same pattern as dsh.

### Cost + wall-clock (same task, qwen; fx and nanocodex not comparable)

| Harness | USD | wall | input tok | output tok | context front-load |
|---|--:|--:|--:|--:|---|
| **pi** | **$0.000228** | **7.0s** | 4,097 (+10.8k cache) | 310 | leanest |
| dsh | $0.00048 (computed, no native USD) | 27s | 9,447 (+25k cache) | 357 | lean |
| omp | $0.000821 (native) | 20s | 12,283 (+59k cache) | 801 | mid |
| crush | $0.00087 (via session json) | 61s | 26,325 | 10* | heavy |
| opencode | $0.001347 (native) | 28s | 24,365 | 372 | heavy |
| flue | n/a (not emitted by CLI) | **12.9s** | not emitted | not emitted | light (in-process) |
| eve | n/a (no USD off-gateway) | 20.7s (106s w/ image pull) | 21,896 (via traces) | 831 (via traces) | heavy (Nitro host + docker) |
| fx (grok, n/c) | n/a (grok sub) | 21s | 86,401 | 457 | very heavy (86k skill catalog) |
| nanocodex (mimo, n/c) | $0.0020 (client-estimated) | 33s | 35,157 (incl. 33.3k cache) | 1,210 | mid (~6k-token prompt) |

pi is ~3.5x cheaper and ~3x faster than the incumbent on the same task. fx injects
an 86k-token skill catalog even for a one-line edit; pi front-loads almost nothing.
flue emits no usage on stdout at all (instrument the agent to get it); eve's tokens
come only from a 2nd `traces --json` call and it carries no USD off the gateway.

## 5. Deploy blockers + gotchas (per harness)

| Harness | Blockers / gotchas found |
|---|---|
| **omp** | Orphans the bash child on a bare SIGINT (kill the process GROUP); leaks parent env to tools (scrub upstream); `--tools` does not truly lock the surface (isolate `$HOME`); `--max-time` is soft; needs `--auto-approve` headless; USD cost only when telemetry enabled. All handled by the caller today. |
| **pi** | **Hangs forever on a reasoning model** unless `--thinking off`; no built-in MCP/browser/permission gate (extension-only); no wall-clock timeout; env leaks to bash. |
| **fx** | **Shipped v0.0.10 binary cannot use OpenRouter / any OpenAI-compatible endpoint** (gateway/codex/grok only; custom-provider is source-only); `ask --json` is one object not a stream; no `--timeout`, no `--model` flag; no USD in `ask --json`; tool-deny shell-escapable; experimental. |
| **opencode** | Headless **auto-REJECTS** perms without `--auto` (silent stall); orphans bash child on kill; env leaks; no wall-clock timeout; `OPENCODE_CONFIG_CONTENT` instructions did not load (use AGENTS.md); priciest + slow on the task. |
| **dsh** | **Published `latest` (0.1.5-rc.2) rejects `--json`** - pin `0.1.6-alpha.2`; **no USD cost** in stream; subscription OAuth not consumable via an env token (fails the subscription-token-via-env requirement); uploads session-log to DeepSeek by default (`session-log-deepseek.enabled:false`); alpha, no security audit. |
| **crush** | `run` stdout is **plain text only** (structured needs the `serve` daemon or 2-step `session show --json`); **no Anthropic/Claude subscription OAuth** (API-key only); tool allowlist config-only; errors not machine-readable on `run`; `-D` isolates data only, config merges the operator's global crush.json. |
| **flue** | **Framework, not a CLI** - must author + scaffold a TS agent project first; `flue run --json` = a final envelope only (**no tokens/cost/tool-calls on stdout**; instrument `observe()`/OTel in the agent); no per-run model/tool/system-prompt flags (all code+env); **no Claude-sub OAuth**; remote (cloud) sandboxes keep running after a local kill; timeout is cooperative, not a hard `--max-time`. Wins: env-scrub by default in BOTH sandbox modes, clean `local()` process-tree kill, OpenRouter works first try. |
| **eve** | **Framework, not a CLI**; **Vercel-AI-Gateway-locked** - `eve init --model openrouter/...` is rejected; OpenRouter needs a custom-provider shim in `agent.ts` + a `modelContextWindowTokens` override; the **default `microsandbox` backend hung >140s** without infra and `just-bash` has no real `node` (use the `docker` backend); observability is 2-step (`traces --json`), **no USD off-gateway**; stdout co-mingles `eve:` progress with the result object; no per-run overrides on `invoke`; boots a Nitro host per call; on SIGTERM `invoke` prints a resumable `status:"running"` object and takes ~14s to tear the docker sandbox down before exiting. Wins: real docker/microVM sandbox isolation, no `$HOME` MCP leak, credentials excluded from `invoke` output. |
| **nanocodex** | **Closed model list** rejects `qwen/qwen3.7-flash`, and its always-on Code Mode sends a freeform `custom` tool that Alibaba (qwen's OpenRouter provider) rejects, so it ran on `xiaomi/mimo-v2.6-pro` (T8 not comparable); no per-run tool allowlist; `--instructions` replaces the system prompt (append = AGENTS.md); no wall-clock timeout; **default-on loaders read operator state**: `$CODEX_HOME` MCP servers, a public MCP catalog, the cwd `.env`, and computer-use on macOS (turn each off, isolate `HOME`/`CODEX_HOME`); INFO traces with full model input go to stderr; USD is estimated from a built-in price table. Wins: one-process JSONL with tokens + USD + typed errors, secret-name env scrub, clean cancel with a `cancelled` terminal event. |

## 6. Rankings + the decisive axes

**Deploy-ready gate** = stable release + no unaudited secret-handling + a non-daemon
structured one-shot. Pass: OMP, opencode, Pi. Fail: fx (experimental), dsh (alpha +
no-audit + no env-token OAuth + broken published build), crush (structured output
is daemon-only + no Claude-sub OAuth), nanocodex (pre-1.0 + closed model list + no
per-run tool allowlist + subscription env token for ChatGPT Business/Enterprise only).

Three axes decide the order:

1. **Structured one-shot output** (JSONL + USD cost from one subprocess): OMP /
   opencode / Pi / nanocodex have it (nanocodex's USD is client-estimated); fx gives
   one object, dsh omits cost, crush needs a daemon.
2. **Subscription-OAuth via a durable env token** (a control plane runs on the Claude sub, no
   API key): OMP / opencode / Pi only. fx / dsh / crush cannot meet it; nanocodex only
   for ChatGPT Business/Enterprise (`CODEX_ACCESS_TOKEN`).
3. **Containment**: of the seven CLIs only **dsh** and **nanocodex** scrub child env by
   default (both by secret-like name, so plain names still leak); the incumbent OMP is
   the worst (env leak + foreign-MCP-from-`$HOME`), and nanocodex shares its default-on
   `$CODEX_HOME` MCP loading. The other CLIs leak too, so the control plane's
   env-allowlist + isolated-`$HOME` + process-group-kill layer stays load-bearing for
   every CLI, partially even for dsh and nanocodex. The two
   frameworks also isolate (flue scrubs env, eve runs a docker sandbox).

**Net:** OMP remains the right incumbent. **opencode** is the one realistic swap to
head-to-head against it. **dsh** is the best-architected of the six and tops the raw
runtime test (20/21) on scrub-by-default + clean-kill - the one to track for a
post-alpha migration once it exits alpha, ships USD cost, and adds an env-token
OAuth path.

**flue and eve** are a different animal: frameworks you build an agent app with, not
binaries you shell out to. Both fail the deploy-ready gate for the generic-driver role
(no per-turn JSONL on stdout, no per-run CLI overrides, no Claude-sub OAuth; eve is
gateway-locked and daemon-shaped) - but both ship the isolation story the CLI field
mostly lacks (flue scrubs child env by default in every sandbox mode; eve runs real
docker/microVM sandboxes), and flue matches Pi's 17/21 on the runtime test. They fit a
control plane that OWNS and instruments the agent codebase, not one that drives a
generic child. Track flue for its secret hygiene; treat eve as gateway-first.

**nanocodex** (added 2026-10-04) is the strongest new CLI: 62.5/81 static (3rd) and
19/21 live (2nd, behind dsh). It ships the cleanest driver contract in the field - one
process, JSONL with tokens + USD + typed `run.error`/`run.failed` events, secret-name
env scrub, and a clean cancel that ends the stream with a `cancelled` status. It fails
the deploy-ready gate on four counts: pre-1.0 and fast-moving; a **closed model list**
(it cannot run the cohort's qwen model at all, and its always-on Code Mode tool breaks
on qwen's provider); no per-run tool allowlist; and **default-on loaders that read
operator state** (`$CODEX_HOME` MCP servers, a public MCP catalog, the cwd `.env`,
macOS computer-use), so a control plane must pass five `false` flags and isolate
`HOME`/`CODEX_HOME`. Subscription auth is ChatGPT Business/Enterprise only via env.
Track it as the reference for what a driver-friendly output contract looks like.

## Method

- **Tier-1**: static source audit, 8 weighted categories, 0-3 per criterion with
  file:line citations (see BENCHMARK.md).
- **Tier-2**: live golden-task run on `qwen/qwen3.7-flash` via OpenRouter (fx on
  grok-4.6, nanocodex on mimo-v2.6-pro; eve via a custom-provider shim on the same
  OpenRouter model), 8 runtime
  tests + task success, raw jsonl/out evidence per harness.

## Layout

```
BENCHMARK.md        full study: contract, Tier-1 scorecard + reasoning, Tier-2 results
README.md           this file - every finding as comparison tables
t2/<harness>/
  RESULT.md         that harness's Tier-2 writeup (8 tests + task success)
  *.jsonl / *.err   raw run evidence (event streams, stderr)
  *.sh / *.js / *.py  runner scripts used
  *.yml             provider/config overlays used (e.g. dsh cordis patch)
```

Not tracked (see `.gitignore`): the harness **source clones** (re-clone from
upstream) and every per-run **auth / home / state dir** (they hold credentials).
flue/eve are frameworks, so their evidence also includes the authored `agents/` /
`agent/` project files used to drive the run.

## Reproduce

Install the harness (or `npx`/curl per its docs) and export `OPENROUTER_API_KEY`
in your environment (pull it from your own secret store; never commit it). Each
`t2/<harness>/RESULT.md` has the exact invocation + runner scripts.

Before publishing changed evidence, run:

```bash
python scripts/validate_benchmark.py
python -m unittest discover -s tests -v
```

The validator checks that every harness has a complete T1-T8 report and task
verdict, parses each non-empty JSON/JSONL capture, and rejects credential-shaped
files under `t2/`. Empty captures remain valid because some startup and
cancellation failures intentionally produce no structured output.
