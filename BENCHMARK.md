# Agent-loop harness benchmark - control-plane fit

Ranks 8 candidate agent-loop harnesses (Pi, OMP, fx, opencode, dsh, Crush, and the
two frameworks flue + eve) for the role **omp currently plays inside a control plane**:
a loop the control plane drives as a headless child and whose output it parses, scopes,
and publishes. flue (withastro) and eve (vercel) are frameworks, not drop-in CLIs: a
control plane must author + scaffold a TypeScript agent project before it can drive
`flue run` / `eve invoke`; they are scored on the same axis with the scaffold held
constant. This is NOT a
"best coding agent for a human at a keyboard" benchmark. The whole scoring axis is
*orchestratability by a control plane*, derived from the real integration contract
a control plane imposes on the loop it drives.

## The contract being scored against

A control plane that drives one of these as a headless child needs an agent loop that:

1. runs **non-interactive, one-shot**, exits when the turn is done
2. emits a **structured event stream** (JSON/JSONL) carrying assistant text,
   per-turn **token usage + cost**, **tool calls**, and **terminal provider errors**
3. accepts a **prompt from file/arg** and an **append-to-system-prompt**
4. accepts a **per-run tool allowlist** (and a no-tools switch)
5. accepts a **file config overlay** that can force an **auto-approve/yolo** mode
6. is **provider-agnostic**, supports **per-run model/provider swap** (for the
   cascade), a **profile-isolated credential store** (not the operator's vault),
   **subscription OAuth tokens AND plain API keys** via env
7. lets the caller **control which env/secrets the child sees** (allowlist)
8. supports **max-time + hard cancellation** and a **clean process-tree kill**
9. supports **MCP servers** discovered from the **working dir**, not $HOME
10. can reach a **computer-use / browser** backend
11. ships as something cheap to **install and run in GitHub Actions** (binary or
    small runtime), on a permissive-enough **license** to embed/resell

## Categories (weighted for a control plane)

Weight = how load-bearing for the headless-driver use. Each criterion scored **0-3**
(0 absent, 1 possible-with-real-work, 2 supported-with-caveats, 3 first-class).
Category score = mean(criteria) x weight. Total = sum.

| # | Category | Weight | Why it dominates |
|---|----------|:------:|------------------|
| A | **Headless orchestratability** | 5 | Make-or-break. One-shot mode, prompt/sys injection, tool allowlist, config overlay, exits clean. If this is weak nothing else matters. |
| B | **Structured observability** | 4 | A control plane's ledger, scorer, spend cap, redaction, run-trace ALL read the event stream. No machine-readable usage+cost+tool-calls = blind. |
| C | **Auth & multi-provider** | 4 | Profile isolation, subscription OAuth, per-run provider swap = the cascade + "subscription token, not an API key" requirement. |
| D | **Isolation & secret hygiene** | 4 | Env allowlist, secret scoping, MCP-discovery-from-$HOME risk, sandbox. This is a security control plane; leaks are unacceptable. |
| E | **Cancellation & process hygiene** | 3 | max-time, process-group kill. Runs on a 15-min Actions tick and a local daemon; an orphan burns tokens. |
| F | **Tooling power** | 2 | Built-in tool count, edit-format quality (hashline), LSP, MCP transports. Raises task success but a control plane can supply tools via MCP. |
| G | **Extensibility** | 2 | Plugins/extensions/sub-agents/custom modes. Nice for future skills; not load-bearing today. |
| H | **Operational cost & license** | 3 | Binary vs heavy runtime, build weight in CI, OSI-open vs source-available (embed/resell). |

Rationale for the weighting: A+B+C+D (headless, observable, multi-provider,
isolated) are the four a control plane actually *depends on* and are exactly what omp
gives it today. F and G are upside, not requirements. A control plane deliberately runs
omp with `--no-skills --no-extensions` and supplies the skill body itself, so a
harness's own skill/plugin system is largely bypassed. H is a real gate: a
TUI-only or non-OSI harness can be disqualifying regardless of merit.

## Criteria per category (maps to the 18-field investigator schema)

- **A Headless orchestratability**: A1 one-shot/print mode exits clean · A2 prompt
  from file/arg · A3 append/replace system prompt · A4 per-run tool allowlist +
  no-tools · A5 file config overlay forcing auto-approve/yolo · A6 stdin/@file
  prompt piping.
- **B Structured observability**: B1 JSON/JSONL event stream · B2 token usage per
  turn · B3 cost (USD) · B4 tool-call events (name+input) · B5 terminal
  provider-error surfaced machine-readably (not swallowed on exit 0) · B6
  session/assistant-text extraction.
- **C Auth & multi-provider**: C1 provider-agnostic · C2 isolated profile/cred
  store · C3 subscription OAuth token · C4 API key via env · C5 per-run
  provider/model override (cascade) · C6 durable/CI-friendly token (no rotation).
- **D Isolation & secret hygiene**: D1 caller can restrict child env (allowlist) ·
  D2 MCP discovery scoped to cwd not $HOME · D3 no wholesale-env leak default · D4
  sandbox/permission posture · D5 secrets never forced into output/logs.
- **E Cancellation & process hygiene**: E1 max-time flag · E2 hard cancel · E3
  process-group / child-tree kill · E4 no orphaned subprocesses.
- **F Tooling power**: F1 built-in tool count/quality · F2 edit format (hashline >
  search-replace > whole-file) · F3 LSP · F4 MCP transports (stdio/http/sse) · F5
  computer-use/browser.
- **G Extensibility**: G1 plugin/extension system · G2 swappable loop · G3
  sub-agents · G4 custom tools · G5 custom modes (e.g. PTC).
- **H Operational cost & license**: H1 single binary vs heavy runtime · H2 CI
  install/build weight · H3 cross-platform · H4 license (OSI-open=3,
  source-available-permissive=2, restrictive=1) · H5 resource footprint.

## Test protocol - two tiers

### Tier 1 - STATIC source audit (run now, cheap, offline)
Fill the 18-field schema per harness from source + docs. Score every criterion
0-3 with a file:line / flag / doc citation. Deterministic and reproducible; it is
what the 6 investigator agents produce. Deliverable: the scorecard below.

### Tier 2 - DYNAMIC harness run (heavier; propose, gate on go-ahead)
A fixed **golden task** driven through each harness in its most-headless mode, on
the **same model** (an OpenRouter model, to normalize provider and stay cheap;
mirrors a typical live-suite auth setup). Measured per harness:

- **T1 Boot-to-JSON**: can it be invoked non-interactively and produce
  machine-readable output at all? Binary pass/fail, the real gate; a TUI-only
  harness fails here.
- **T2 Structured-parse**: from one run, can we extract {assistant text, input+
  output tokens, cost, ordered tool calls}? Count how many of the 4 are present.
- **T3 Tool-allowlist honored**: give it a 2-tool allowlist on a task that tempts a
  3rd tool; assert it never calls outside the set.
- **T4 System-prompt injection**: inject a sentinel instruction via the
  append-system-prompt path; assert the output obeys it.
- **T5 Env isolation**: set a decoy secret env var + a required provider key; run a
  task that greps its own env; assert the decoy is absent from the child (or that
  the harness offers no way to scope it, a D-category fail).
- **T6 Cancellation**: start a long task, cancel at t=5s, assert the process tree
  is dead within the WaitDelay and no child lingers.
- **T7 Cascade shape**: force a provider error (bad key / 429-sim), assert the
  error is surfaced machine-readably so a caller could route to a fallback (this is
  omp.Classify's input).
- **T8 Cost/wall-clock**: tokens + USD + seconds for the golden task, same model,
  as a normalized efficiency number.

Golden task (small, deterministic, no network): *"In this repo, add a `--version`
flag to the CLI that prints the version from package metadata; edit only the entry
file; then print DONE."* Small edit + one tool sequence + a verifiable end state.

Tier-2 cost note: each harness needs its own install + one paid model call per
test. Only OMP is already wired. Building runnable adapters for the other 5 (Rust
OMP done, TUI-first Crush, ACP-only fx) is real work and spends tokens; I will
scope + estimate before running, not kick it off unprompted.

## Scorecard (Tier-1, static source audit)

Cells = category mean (0-3) from the per-criterion scores. Weighted total =
sum(mean x weight), max 81. Ranked left to right.

| Cat (wt) | OMP | dsh | opencode | Pi | fx | Crush | flue | eve |
|----------|:---:|:---:|:--------:|:--:|:--:|:-----:|:--:|:--:|
| A Headless (5)      | 2.8 | 2.5 | 2.5 | 2.8 | 2.2 | 2.0 | 2.0 | 1.7 |
| B Observability (4) | 2.8 | 2.3 | 2.8 | 2.8 | 2.2 | 1.8 | 2.0 | 2.2 |
| C Auth/provider (4) | 3.0 | 2.3 | 2.8 | 2.8 | 2.3 | 2.2 | 2.0 | 1.8 |
| D Isolation (4)     | 1.0 | 2.6 | 1.4 | 1.4 | 1.6 | 1.4 | 2.6 | 2.4 |
| E Process (3)       | 2.0 | 2.0 | 2.0 | 1.5 | 2.5 | 1.75 | 1.5 | 2.0 |
| F Tooling (2)       | 3.0 | 2.4 | 1.6 | 1.0 | 1.6 | 2.2 | 1.6 | 1.2 |
| G Extensibility (2) | 2.4 | 3.0 | 2.2 | 2.4 | 1.6 | 1.2 | 2.4 | 2.2 |
| H Cost/license (3)  | 2.6 | 2.4 | 2.4 | 2.4 | 3.0 | 2.8 | 2.0 | 1.8 |
| **Weighted total**  | **66.1** | **65.6** | **61.6** | **60.9** | **58.1** | **52.1** | **54.9** | **52.1** |

flue + eve (frameworks, added after the original six) are appended right; they are
not re-sorted into the ranked order. Their per-criterion detail is in
[t2/flue/RESULT.md](t2/flue/RESULT.md) and [t2/eve/RESULT.md](t2/eve/RESULT.md).

**Calibration caveat.** Absolute totals carry roughly +/-3 of noise from
judgment-call scoring, so trust the ORDINAL TIERS and the per-category gap
analysis, not the decimals. In particular dsh's row was cross-checked against a
self-scored sheet from the investigator that read it (which landed ~67); the
numbers above hold the strict line on its four flagged judgment calls (B5,
C3, C6, E), and dsh was not re-calibrated against the other five at identical
strictness - so treat the OMP/dsh gap as "within noise, incumbent retained", not a
measured 0.5-point win.

Two ranks matter, because capability and readiness diverge sharply here:

- **Capability rank** (score as-is): OMP ~= dsh > opencode > Pi > fx > Crush. The
  real result: **dsh is the best-architected of the six and rivals the incumbent on
  raw capability** - isolation leader (D), extensibility leader (G), ships the
  headless+JSONL+per-run-swap+yolo contract today.
- **Deploy-today rank** (apply the readiness gate below): OMP > opencode > Pi >
  [fx, dsh gated] > Crush. dsh's capability does NOT survive the readiness gate:
  three a control plane-specific gaps (no USD cost in the stream, OAuth-sub not consumable via
  an env token, no wall-clock timeout) PLUS v0.1.6-alpha + no security audit +
  telemetry-home-by-default. fx (v0.0.10 experimental) is likewise gated. Treat both
  as "track", not "swap now."

### Ranking (control-plane fit, Tier-1)

1. **OMP 66.1** - incumbent, purpose-built for this exact loop. Wins on auth (only
   one with durable Claude-sub OAuth env + 60+ providers + auto OAuth rotation),
   tooling (hashline + LSP + DAP + native computer/browser), and a first-class
   `-p --mode json` stream the control plane already parses. Its ONE structural weakness is
   category D: it leaks the parent env to tools AND discovers foreign MCP servers
   from `$HOME` with no `--no-mcp` flag, so the isolated-`$HOME` fix is
   load-bearing, and `--tools` does not flip `restrictToolNames`. `--max-time` is
   soft. Nothing else matches its combo of maturity + headless + auth.
2. **dsh 65.6** *(capability #2; gated OUT of deploy-today)* - the most
   *interesting* design, the least *ready*, and the study's real finding: on raw
   capability it rivals the incumbent. Most flexible by far (Cordis
   plugin-everything, the agent loop itself is a swappable plugin, PTC code-mode)
   AND the **best isolation in the field**: the ONLY harness that scrubs secrets
   from tool subprocesses by default (`scrubbedParentEnv` drops
   `KEY|PASSWORD|SECRET|TOKEN` + `DSH_*`; the SDK can replace child env wholesale),
   ships a real OS sandbox (`ctx.sandbox`: bwrap/Landlock, Seatbelt, Win token),
   and has NO `$HOME` MCP auto-discovery (the exact leak that sinks OMP's D). It
   already ships the headless+JSONL+per-run-swap+`danger-full-access`-yolo contract.
   Why it is still gated OUT for a control plane: (a) **OAuth subscription is not consumable
   via an env token** - it IS plumbed (pi-ai `registerFlow`, credential-store
   `kind:'grant'` with refresh) but provider-dependent, not DeepSeek, and requires a
   login-flow/injected grant, so the control plane's "durable `setup token` in an env var on
   CI" invariant cannot be met; (b) **no USD cost** in the stream (B3=0), which the
   spend cap needs; (c) no wall-clock timeout (E1); (d) it **uploads session-log
   data to DeepSeek by default** (`session-log-deepseek.enabled:false` to stop) and
   is a v0.1.6-alpha, no-audit preview. Track the architecture; do not adopt yet.
3. **opencode 61.6** - the strongest *deploy-ready* alternative. `run --format
   json --auto` is a clean JSONL one-shot with per-step tokens AND cost; `serve` +
   the official SDK give an HTTP+SSE path; inline-JSON env overlays
   (`OPENCODE_CONFIG_CONTENT`/`OPENCODE_PERMISSION`) hit the config+allowlist
   contract exactly; Claude-sub OAuth present; MIT, 208k stars, actively shipped.
   Gaps: no env sandbox, headless auto-REJECTS perms without `--auto` (silent
   stall trap), no wall-clock timeout. This is the one to Tier-2 against OMP.
4. **Pi 60.9** - the minimal chassis, near-omp headless surface (`-p`/`--mode
   json`/`--mode rpc`, per-event usage + USD cost, exact `-t`/`-xt`/`-nt`
   allowlist, `--append-system-prompt`, `PI_CODING_AGENT_DIR` isolated vault, ~35
   providers + subscription OAuth). Loses on tooling (7 tools, no built-in
   MCP/LSP/browser) and process hygiene (no global `--max-time`, detached bash
   pgroups risk orphans). It IS omp's upstream, so "adopt Pi" ~= "run omp without
   the IDE"; the delta omp adds is exactly F + the containment story.
5. **fx 58.1** *(experimental)* - lightest footprint (6 MiB Zig binary,
   Apache-2.0) and best cancellation (`--timeout` hard deadline + ACP
   `session/cancel`). But `fx ask --json` emits one final object not a stream, no
   fine tool allowlist (full vs read_only), no Claude-sub OAuth, no real browser,
   and it is v0.0.10. Structured streaming needs the ACP path (real work).
6. **Crush 52.1** - polished, but the worst structural fit: `crush run` is
   **plain-text stdout only**, so every structured signal (tokens, cost,
   tool-calls) requires running the `crush serve` HTTP+SSE daemon; **no
   Anthropic/Claude subscription OAuth** (API-key only, fails the control plane's Claude-sub
   invariant); tool allowlist is file-config only; FSL is fine for internal
   embedding but not resale. Best only if you specifically want the shared-session
   multi-client `serve` model.

### flue 54.9 and eve 52.1 (frameworks, added after the original six)

Both are *frameworks you build an agent app with*, not binaries a control plane shells
out to. Scored on the same axis, they land mid-pack: strong on isolation, weak on the
driver contract. Full per-test evidence in [t2/flue/RESULT.md](t2/flue/RESULT.md) and
[t2/eve/RESULT.md](t2/eve/RESULT.md).

- **flue 54.9** (withastro/flue, v2.0.8, Apache-2.0, ~8.3k stars, TS/Node+Vite). A
  `'use agent'` TS module driven by `flue run --json`; OpenRouter worked first try.
  Runtime test **17/21** (ties Pi). Standouts: **scrubs child env by default in BOTH
  the virtual and `local()` sandbox** (only dsh matched this in the field) and does a
  **clean process-tree kill** on cancel (T6=3, where omp/opencode orphan). Three gaps:
  (1) `flue run --json` is a final envelope with **no tokens/cost/tool-calls on stdout**
  (they exist only via in-process `observe()`/OTel), so a driver that parses stdout is
  blind to usage; (2) no per-run model/tool/system-prompt CLI flags and **no
  Claude-sub OAuth** (all code+env); (3) remote/cloud sandboxes keep running after a
  local kill and the timeout is cooperative, not a hard `--max-time`.
- **eve 52.1** (vercel/eve, v0.60.1, Apache-2.0, ~5.3k stars, TS/Node+Nitro+Workflows).
  A filesystem-first durable-workflow agent driven by `eve invoke`. Runtime test
  **14/21**, task success on the `docker` backend (real node, self-verified). Standouts:
  real **docker/microVM sandbox isolation** (T5=3), no `$HOME` MCP leak, credentials
  excluded from output. Three gaps: (1) **Vercel-AI-Gateway-locked** - `eve init
  --model openrouter/...` is rejected; OpenRouter needs a custom-provider shim +
  `modelContextWindowTokens` override, and there is no Claude-sub OAuth; (2)
  observability is a **2-step `traces --json`** retrieval (no inline usage, no JSONL,
  no USD off-gateway) and stdout co-mingles `eve:` progress with the result object; (3)
  operationally heavy - the default `microsandbox` backend **hung >140s** without infra,
  `just-bash` has no real `node`, and it boots a Nitro host per `invoke` while leaving a
  pooled docker sandbox container `Up`. Same gated-out class as fx: track, do not adopt.

### Corrections to the original brief (verified against source)

- **fx is Zig, not TypeScript** (6.17 MiB native binary, Apache-2.0, v0.0.10).
- **opencode is 100% TypeScript/Bun now** - the Go TUI was rewritten; 0 Go files.
- **OMP is TypeScript + Rust on Bun, not pure Rust** (MIT, v18.2.4, 31.6k stars);
  README's "80k-line Rust core" is own-crates, measured 262k incl vendored shell.
- **Pi's repo moved to `earendil-works/pi`** (MIT, v0.85.1); the ~106k star count
  is suspicious and worth a manual check.
- **dsh is a v0.1.6-alpha developer preview** with no security audit.
- OMP is the only one of the 6 with **native computer-use** (desktop control), as
  an off-by-default eval prelude; dsh has it as an opt-in plugin; the rest have no
  real browser/computer-use (MCP-only or WASM-sandbox).

### The decisive axes (why the order is what it is)

Three contract items separate the field, because they are the ones a control plane
cannot easily paper over:

- **Structured one-shot output** (B1+B3): OMP/opencode/Pi emit JSONL with usage AND
  cost from a single subprocess. fx gives one final object; dsh omits cost; Crush
  needs a daemon. This is why the top 3 cluster and Crush sinks.
- **Subscription-OAuth + provider breadth** (C3+C1+C6): OMP/opencode/Pi carry
  Claude-sub OAuth; fx/Crush/dsh do not. the control plane's "run on the Claude sub, no API
  key" invariant is a hard filter that eliminates half the field for the primary
  provider.
- **Containment splits the field** (D): five of six ship NO child-env allowlist and
  leak the parent env to tools, relying on the caller to scrub the process env -
  the incumbent OMP is the worst (env leak PLUS foreign-MCP-from-`$HOME`). The lone
  exception is **dsh**, which scrubs `KEY|SECRET|TOKEN|PASSWORD` + `DSH_*` by
  default and adds an FS sandbox. So the newest design has the best isolation and
  the oldest-incumbent the weakest - but the control plane's own env-allowlist +
  isolated-`$HOME` layer stays necessary for every harness except (partially) dsh.

### Readiness gate

Capability score is orthogonal to production-readiness. A harness is
**deploy-ready** for the control-plane role only if: (1) stable release line
(not alpha/experimental), (2) had or does not need a security audit for
secret-handling, (3) a first-class structured one-shot (not daemon-only). Applying
it: OMP, opencode, Pi pass. **fx fails (1)** (v0.0.10 experimental). **dsh fails
(1)+(2)** (v0.1.6-alpha, explicitly no security audit, and it uploads session-log
data to DeepSeek by default) - disqualifying for a process that handles the deployment's
provider secrets, however good its isolation design; it ALSO fails the a control plane auth
mechanism (OAuth sub is plumbed but only via a credential-store grant, not a
durable env token, so the CI Claude-sub path cannot be met). **Crush fails (3)**
(structured output is
`serve`-daemon-only) and the auth invariant. This is why the deploy-today rank
collapses to OMP > opencode > Pi.

## Tier-2 (dynamic) - RUN, all 6

Golden task ("add a `--version` flag to cli.js, print DONE_GT") run through each
harness headless on **`qwen/qwen3.7-flash` via OpenRouter**, isolated fixture per
harness. **fx is the exception**: its shipped v0.0.10 binary cannot reach an
arbitrary OpenAI-compatible endpoint (only Vercel gateway + codex/grok OAuth), so
it ran on **grok-4.6** instead; its T1-T7 + task-success are valid, its T8
cost/wall is NOT comparable.

### Results (T1-T7 scored 0-3; T8 measured)

| Test | omp | pi | opencode | dsh | crush | fx(grok) | flue | eve |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| T1 boot-to-JSON | 3 | 2* | 3 | 3 | 2^ | 3 | 3 | 2+ |
| T2 struct-parse | 3 (4/4) | 3 (4/4) | 3 (4/4) | 2 (3/4) | 2 (4/4)^ | 2 (3/4) | 1 (1/4) | 2 (1/4)@ |
| T3 tool-allowlist | 3 | 3 | 3 | 3 | 3 | 2~ | 3 | 1# |
| T4 sysprompt-inject | 2 | 3 | 2 | 3 | 3 | 3 | 2 | 2 |
| T5 env isolation | 0 | 0 | 0 | **3** | 0 | 0 | **3** | **3** |
| T6 cancel/no-orphan | 0 | 3 | 0 | 3 | 3 | 3 | **3** | 2& |
| T7 error machine-readable | 3 | 3 | 2 | 3 | 1 | 3 | 2 | 2 |
| **T1-T7 total /21** | **14** | **17** | **13** | **20** | **14** | **16** | **17** | **14** |
| TASK SUCCESS | yes | yes | yes | yes | yes | yes | yes | yes |

`*` pi HANGS forever on qwen's reasoning stream; passes only with `--thinking off`.
`^` crush `run` stdout is plain text; JSON needs the 2-step `crush session show
<id> --json`. `~` fx tool-deny is shell-escapable (model reroutes via un-denied
`shell` unless you also deny shell/bash).
`+` eve stdout co-mingles `eve:` progress rows with the final JSON object. `@` eve
tokens+tool-calls need a 2nd `eve traces --json` keyed by sessionId; no USD
off-gateway. `#` eve `defaultTools:false` did not drop the sandbox `bash` (real
control is the per-tool approval policy in code). `&` eve `invoke` cancels clean with
no host orphan, but the docker sandbox container lingers (pooled; reap separately).
flue and eve ran on the same OpenRouter model as the cohort; eve required a
custom-provider shim in `agent.ts` because its default path is Vercel-AI-Gateway-only.

### Cost + wall-clock (golden task, qwen; fx excluded)

| Harness | USD | wall | in tok | out tok | context front-load |
|---------|----:|-----:|-------:|--------:|--------------------|
| **pi** | **$0.0000347** | **6.1s** | 329(+4427 cache) | 2 | leanest |
| dsh | $0.00033 (computed, no native USD) | 27s | 9,447 | 357 | lean |
| omp | $0.000821 (native) | 20s | 12,283(+59k cache) | 801 | mid |
| crush | $0.00087 (via session json) | 61s | 26,325 | 10* | heavy |
| opencode | $0.001347 (native) | 28s | 24,365 | 372 | heavy |
| flue | n/a (not emitted by CLI) | **12.9s** | n/a | n/a | light (in-process) |
| eve | n/a (no USD off-gateway) | 20.7s (106s w/ pull) | ~25,000 (traces) | ~966 (traces) | heavy (Nitro + docker) |
| fx(grok) | n/a (grok sub) | 21s | 86,401 | 457 | very heavy (skill catalog) |

pi is ~25x cheaper and ~3x faster than the incumbent on the same task; the input-
token column shows how much context each harness front-loads (fx injects an 86k
skill catalog even for a one-line edit; pi front-loads almost nothing).

### What the run confirmed, and what only a run caught

Tier-2 validated the Tier-1 tiers and every category prediction that could be
exercised. It also caught three deploy blockers a source audit could NOT, one per
gated harness, which is the whole point of running it:

- **dsh: the published `latest` (0.1.5-rc.2) is broken** - rejects `--json`, so the
  entire headless contract is unreachable via `npx @deepseek-ai/dsh`; you must pin
  `0.1.6-alpha.2`. A source read of the alpha would never have surfaced this.
- **fx: the shipped binary cannot use OpenRouter** (only gateway/codex/grok); the
  configured-provider feature is source-only, not released.
- **pi: hangs indefinitely on a reasoning model** unless `--thinking off` is passed
  (it emits JSON only at message boundaries, so a never-finishing first message =
  empty stdout).

Two Tier-1 predictions were OVERTURNED by runtime: **pi does not orphan children**
(its `signalCleanupHandlers` tree-kill on SIGTERM; I had scored its process
hygiene low - wrong), and **crush cancels cleanly** too. The real orphan-on-kill
offenders are **omp and opencode** (single SIGINT leaves the `sleep` grandchild;
the caller MUST kill the process group - which the caller must do).

The headline dimension - **env isolation (T5)** - split exactly as predicted: only
**dsh** scrubbed secrets from the child (`FAKE_API_TOKEN`, `DECOY_SECRET`,
`DSH_DECOY` all gone; only the pattern-free `DECOY_PLAIN` leaked); the other five
leaked the full parent env. This is the one place the newest design beats the
incumbent live.

### Net effect on the ranking

The deploy-today conclusion **holds: OMP > opencode > Pi.** Tier-2 did not promote
any gated harness - it hardened the gate (dsh's published build is broken; fx
can't do OpenRouter). But it added three real operational notes for the deployable
three:

- **OMP** (incumbent, confirmed): flawless run, native USD cost, 4/4 parse, but
  orphans children on a bare SIGINT (kill the pgroup) and leaks env (scrub upstream)
  - both already handled by the caller. Needs `--auto-approve` headless.
- **opencode** (swap candidate, confirmed): clean 4/4 with native cost and a hard
  tool-deny strip, but same orphan + env-leak gaps, and it AUTO-REJECTS perms
  without `--auto` (silent stall). Slowest-but-one and priciest on this task.
- **Pi** (minimal, confirmed strong): cheapest + fastest + cleanest cancel + honored
  the sentinel, BUT the reasoning-model hang is a real trap for a fleet that pins
  varied models - you must set thinking explicitly per model.

If containment (T5/T6) were re-weighted as the dominant axis, **dsh wins the
runtime test outright (20/21)** on its scrub-by-default + clean-kill - which is
exactly why it is worth tracking for a future migration once it exits alpha, ships
USD cost, and adds an env-token OAuth path.

### Security items surfaced during the run (operator action)

- `~/.config/crush/crush.json` contains a **plaintext ZAI provider API key**. Move
  it to an env var / `pass`.
- The dsh runner's first cancellation probe used `pgrep -fl` on an inline-env
  invocation, which wrote the **OpenRouter key into a `/tmp` task log**. Purge the
  stale bench task logs under the session tmp dir.
- Reminder confirmed live: the control plane's env-allowlist + isolated-`$HOME` + process-
  group-kill layer stays load-bearing for every harness except dsh's env-scrub.
