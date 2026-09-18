# headless-harness-bench

Benchmark comparing 6 coding-agent harnesses for the role of a **headless agent
loop driven by a control plane**: another program drives it as a child and parses,
scopes, and publishes its output. Scoring axis is *orchestratability by a control
plane*, not human-at-a-keyboard UX.

Harnesses: **omp** (Oh My Pi), **pi**, **fx** (Vercel), **opencode** (SST), **dsh**
(DeepSeek Harness), **crush** (Charmbracelet).

## TL;DR

- **Deploy-today rank (control-plane role): OMP > opencode > Pi.**
- **Capability rank: OMP ~= dsh > opencode > Pi > fx > Crush.**
- All 6 completed the golden task once wired. The order is about auth fit, structured
  output, isolation, maturity, and cost - not raw ability.
- Full reasoning + file:line citations in **[BENCHMARK.md](BENCHMARK.md)**; this
  README carries every finding as tables.

## 1. Identity + distribution

| | omp | pi | fx | opencode | dsh | crush |
|---|---|---|---|---|---|---|
| Language / runtime | TS + Rust / Bun | TS / Node 22+ | Zig (native 6 MiB) | TS / Bun | TS / Node 22+ (+Py wheel) | Go (native) |
| License | MIT | MIT | Apache-2.0 | MIT | MIT | FSL-1.1-MIT |
| OSI-open? | yes | yes | yes | yes | yes | no (MIT after 2y) |
| Version tested | 18.2.4 | 0.85.1 | 0.0.10 | 1.18.31 | 0.1.6-alpha.2 | 0.95.0 |
| Maturity | stable | stable | **experimental** | stable | **alpha, no audit** | stable |
| Stars | ~31.6k | ~106k (suspect) | new | ~208k | preview | ~28k |
| Repo | can1357/oh-my-pi | earendil-works/pi | vercel-labs/fx | sst/opencode | deepseek-ai/deepseek-harness | charmbracelet/crush |
| Install | binary (curl/brew/npm) | npm / bun-binary | curl (native) | npm/curl (bun-binary) | npm / npx / py-wheel | brew/npm (Go binary) |
| Built-in tools | 31 | 7 | ~11 | ~14 | ~30 | ~30 (+LSP ops) |
| Edit format | **hashline** | search-replace | string-replace | search-replace (+apply_patch/GPT) | search-replace | search-replace + LSP |

## 2. Tier-1 weighted scorecard (static source audit)

Category mean 0-3 x weight; total /81. Ordered by total.

| Category (weight) | OMP | dsh | opencode | Pi | fx | Crush |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| A Headless orchestratability (5) | 2.8 | 2.5 | 2.5 | 2.8 | 2.2 | 2.0 |
| B Structured observability (4) | 2.8 | 2.3 | 2.8 | 2.8 | 2.2 | 1.8 |
| C Auth & multi-provider (4) | 3.0 | 2.3 | 2.8 | 2.8 | 2.3 | 2.2 |
| D Isolation & secret hygiene (4) | 1.0 | **2.6** | 1.4 | 1.4 | 1.6 | 1.4 |
| E Cancellation & process hygiene (3) | 2.0 | 2.0 | 2.0 | 1.5 | 2.5 | 1.75 |
| F Tooling power (2) | 3.0 | 2.4 | 1.6 | 1.0 | 1.6 | 2.2 |
| G Extensibility (2) | 2.4 | **3.0** | 2.2 | 2.4 | 1.6 | 1.2 |
| H Cost & license (3) | 2.6 | 2.4 | 2.4 | 2.4 | 3.0 | 2.8 |
| **Weighted total /81** | **66.1** | **65.6** | **61.6** | **60.9** | **58.1** | **52.1** |

Absolute totals carry ~+/-3 noise; trust the tiers and the per-axis findings below.

## 3. Contract-axis capability matrix

Every axis of the headless-driver contract, per harness. "-" = absent.

| Axis | omp | pi | fx | opencode | dsh | crush |
|---|---|---|---|---|---|---|
| Headless one-shot | `-p --mode json` | `-p --mode json` | `ask --json` (1 obj) | `run --format json` | `--profile headless --json` | `run` (PLAIN TEXT) |
| JSONL event stream | yes | yes | - (single obj) | yes | yes | - (needs `serve` SSE) |
| Token usage in output | yes | yes | yes | yes | yes | via `session show --json` |
| **USD cost in output** | yes (telemetry) | yes | **-** | yes | **-** | via `session show --json` |
| Tool-call events | yes | yes | yes | yes | yes | via `session show --json` |
| Per-run tool allowlist | `--tools` (leaky*) | `-t/-xt/-nt` exact | per-tool rules (shell-escapable) | `OPENCODE_PERMISSION` (hard-strip) | `ToolRestriction` allow/deny | config-only |
| Append-to-system-prompt | `--append-system-prompt` | `--append-system-prompt` | `--system` (replaces) | AGENTS.md / instructions | AGENTS.md / prompt section | CRUSH.md file |
| Per-run provider/model swap | yes | yes | yes (env) | yes | yes | yes |
| **Subscription OAuth via env token** | **yes** (`setup token`) | yes | - (codex/grok login) | **yes** (Claude sub) | - (grant only, no env) | - (API-key only) |
| API key via env | yes | yes | yes (named) | yes | yes | yes |
| **Child-env scrub by default** | - | - | - | - | **YES** | - |
| MCP transports | stdio/http/sse | - (extension) | stdio/http/sse | local/http/sse | stdio/http | stdio/http/sse |
| MCP `$HOME` auto-discovery leak | **yes** (needs isolated HOME) | n/a | no | no | no | no |
| Native computer-use / browser | **yes** (eval preludes) | - | - (WASM sandbox) | - (MCP) | opt-in plugin | - (MCP) |
| Wall-clock timeout | `--max-time` (soft) | - | - (no flag) | - | - | - (per-req only) |
| Programmatic API | RPC + ACP + SDK | RPC + SDK | **ACP** + SDK | HTTP+SSE + SDK + ACP | SDK + ACP | `serve` HTTP+SSE |

`*` omp `--tools` filters builtins but does not flip `restrictToolNames`, so MCP /
extensions still load unless you also isolate `$HOME` / pass `--no-extensions`.

## 4. Tier-2 live run

Golden task ("add a `--version` flag to a CLI, print DONE_GT") headless on
**`qwen/qwen3.7-flash` via OpenRouter**. **fx ran on grok-4.6** (its shipped binary
cannot reach an OpenAI-compatible endpoint), so its T8 is not comparable.

| Test (0-3) | omp | pi | opencode | dsh | crush | fx(grok) |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| T1 boot-to-JSON | 3 | 2* | 3 | 3 | 2^ | 3 |
| T2 structured-parse (fields/4) | 3 (4/4) | 3 (4/4) | 3 (4/4) | 2 (3/4) | 2 (4/4)^ | 2 (3/4) |
| T3 tool-allowlist honored | 3 | 3 | 3 | 3 | 3 | 2~ |
| T4 sys-prompt injection | 2 | 3 | 2 | 3 | 3 | 3 |
| T5 env isolation | 0 | 0 | 0 | **3** | 0 | 0 |
| T6 cancel / no orphan | 0 | 3 | 0 | 3 | 3 | 3 |
| T7 error machine-readable | 3 | 3 | 2 | 3 | 1 | 3 |
| **T1-T7 total /21** | 14 | 17 | 13 | **20** | 14 | 16 |
| **TASK SUCCESS** | yes | yes | yes | yes | yes | yes |

`*` pi hangs on qwen's reasoning stream until `--thinking off`. `^` crush `run` =
plain text; JSON needs 2-step `session show --json`. `~` fx tool-deny is
shell-escapable (model reroutes via un-denied `shell`).

### Cost + wall-clock (same task, qwen; fx excluded)

| Harness | USD | wall | input tok | output tok | context front-load |
|---|--:|--:|--:|--:|---|
| **pi** | **$0.0000347** | **6.1s** | 329 (+4427 cache) | 2 | leanest |
| dsh | $0.00033 (computed, no native USD) | 27s | 9,447 | 357 | lean |
| omp | $0.000821 (native) | 20s | 12,283 (+59k cache) | 801 | mid |
| crush | $0.00087 (via session json) | 61s | 26,325 | 10* | heavy |
| opencode | $0.001347 (native) | 28s | 24,365 | 372 | heavy |
| fx (grok, n/c) | n/a (grok sub) | 21s | 86,401 | 457 | very heavy (86k skill catalog) |

pi is ~25x cheaper and ~3x faster than the incumbent on the same task. fx injects
an 86k-token skill catalog even for a one-line edit; pi front-loads almost nothing.

## 5. Deploy blockers + gotchas (per harness)

| Harness | Blockers / gotchas found |
|---|---|
| **omp** | Orphans the bash child on a bare SIGINT (kill the process GROUP); leaks parent env to tools (scrub upstream); `--tools` does not truly lock the surface (isolate `$HOME`); `--max-time` is soft; needs `--auto-approve` headless; USD cost only when telemetry enabled. All handled by the caller today. |
| **pi** | **Hangs forever on a reasoning model** unless `--thinking off`; no built-in MCP/browser/permission gate (extension-only); no wall-clock timeout; env leaks to bash. |
| **fx** | **Shipped v0.0.10 binary cannot use OpenRouter / any OpenAI-compatible endpoint** (gateway/codex/grok only; custom-provider is source-only); `ask --json` is one object not a stream; no `--timeout`, no `--model` flag; no USD in `ask --json`; tool-deny shell-escapable; experimental. |
| **opencode** | Headless **auto-REJECTS** perms without `--auto` (silent stall); orphans bash child on kill; env leaks; no wall-clock timeout; `OPENCODE_CONFIG_CONTENT` instructions did not load (use AGENTS.md); priciest + slow on the task. |
| **dsh** | **Published `latest` (0.1.5-rc.2) rejects `--json`** - pin `0.1.6-alpha.2`; **no USD cost** in stream; subscription OAuth not consumable via an env token (fails the subscription-token-via-env requirement); uploads session-log to DeepSeek by default (`session-log-deepseek.enabled:false`); alpha, no security audit. |
| **crush** | `run` stdout is **plain text only** (structured needs the `serve` daemon or 2-step `session show --json`); **no Anthropic/Claude subscription OAuth** (API-key only); tool allowlist config-only; errors not machine-readable on `run`; `-D` isolates data only, config merges the operator's global crush.json. |

## 6. Rankings + the decisive axes

**Deploy-ready gate** = stable release + no unaudited secret-handling + a non-daemon
structured one-shot. Pass: OMP, opencode, Pi. Fail: fx (experimental), dsh (alpha +
no-audit + no env-token OAuth + broken published build), crush (structured output
is daemon-only + no Claude-sub OAuth).

Three axes decide the order:

1. **Structured one-shot output** (JSONL + USD cost from one subprocess): OMP /
   opencode / Pi have it; fx gives one object, dsh omits cost, crush needs a daemon.
2. **Subscription-OAuth via a durable env token** (a control plane runs on the Claude sub, no
   API key): OMP / opencode / Pi only. fx / dsh / crush cannot meet it.
3. **Containment**: only **dsh** scrubs child env by default; the incumbent OMP is
   the worst (env leak + foreign-MCP-from-`$HOME`). Everyone else leaks too, so
   the control plane's env-allowlist + isolated-`$HOME` + process-group-kill layer stays
   load-bearing for every harness except dsh.

**Net:** OMP remains the right incumbent. **opencode** is the one realistic swap to
head-to-head against it. **dsh** is the best-architected of the six and tops the raw
runtime test (20/21) on scrub-by-default + clean-kill - the one to track for a
post-alpha migration once it exits alpha, ships USD cost, and adds an env-token
OAuth path.

## Method

- **Tier-1**: static source audit, 8 weighted categories, 0-3 per criterion with
  file:line citations (see BENCHMARK.md).
- **Tier-2**: live golden-task run on `qwen/qwen3.7-flash` via OpenRouter (fx on
  grok-4.6), 8 runtime tests + task success, raw jsonl evidence per harness.

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

Not tracked (see `.gitignore`): the 6 harness **source clones** (re-clone from
upstream) and every per-run **auth / home / state dir** (they hold credentials).

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
