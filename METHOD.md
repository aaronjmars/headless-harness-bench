# METHOD

Benchmark card for headless-harness-bench. The full study (contract, criteria, scorecard
reasoning with file:line citations, Tier-2 discussion) is [BENCHMARK.md](BENCHMARK.md);
the comparison tables and rankings as of 2026-10-04 are in
[docs/2026-10-04-harness-comparison.md](docs/2026-10-04-harness-comparison.md). Every run
is a manifest under [runs/](runs/), listed in [RESULTS.md](RESULTS.md).

## 1. Goal and scope

Decide which coding-agent harness fits the role of a **headless agent loop driven by a
control plane**: another program starts it as a child, passes a prompt, tool allowlist and
system-prompt addition, parses its structured output (text, tokens, cost, tool calls,
errors), scopes its secrets and kills it on timeout. The axis is orchestratability by a
program, not human-at-a-keyboard UX and not model quality.

Subject type: harness (CLI or framework) at a pinned version. Model is held fixed where
the harness allows it. Nine harnesses: omp, pi, fx, opencode, dsh, crush, flue, eve,
nanocodex. flue and eve are frameworks (an agent project must be authored before it can be
driven); they are scored on the same axis with the scaffold held constant.

## 2. Tasks and data

Two tiers, task-set version `1-A` for both (BENCHMARK.md "Test protocol").

**Tier-1, static source audit** (dataset `tier1-rubric`): 8 weighted categories, 42 criteria,
each scored 0-3 (0 absent, 1 possible with real work, 2 supported with caveats, 3 first
class) with a file:line, flag or doc citation.

| Category | Weight | Criteria |
|---|:--:|---|
| A Headless orchestratability | 5 | A1-A6 one-shot exit, prompt from file/arg, system prompt, tool allowlist, config overlay, stdin |
| B Structured observability | 4 | B1-B6 JSON/JSONL stream, tokens, USD, tool calls, machine-readable errors, text extraction |
| C Auth & multi-provider | 4 | C1-C6 provider-agnostic, isolated cred store, subscription OAuth, API key via env, per-run swap, durable token |
| D Isolation & secret hygiene | 4 | D1-D5 env allowlist, MCP discovery scoped to cwd, no wholesale env leak, sandbox, no secrets in output |
| E Cancellation & process hygiene | 3 | E1-E4 max-time, hard cancel, process-group kill, no orphans |
| F Tooling power | 2 | F1-F5 tools, edit format, LSP, MCP transports, computer-use |
| G Extensibility | 2 | G1-G5 plugins, swappable loop, sub-agents, custom tools, custom modes |
| H Operational cost & license | 3 | H1-H5 binary vs runtime, CI weight, cross-platform, license, footprint |

**Tier-2, live run** (dataset `tier2-live-tests`): 8 tasks per harness, one attempt each.

- T1 boot-to-JSON, T2 structured-parse (fields found of 4: text, tokens, USD, ordered tool
  calls), T3 tool allowlist honored, T4 system-prompt injection, T5 env isolation (decoy
  secret in the parent env), T6 cancellation with no orphan, T7 machine-readable error
  (bad key, bad model). Each scored 0-3.
- Golden task (also gives T8): in a fixture with `package.json` 1.4.2 and `cli.js`, add a
  `--version` flag that prints the package version, edit only `cli.js`, print `DONE_GT`.
  Small, deterministic, no network.

Solvability: every harness completed the golden task once wired, which is the reference
check (`node cli.js --version` prints `1.4.2`, `node cli.js` prints `hello`).

## 3. Metrics

Tier-1 (run `2026-09-17-tier1-static-audit`):

- `weighted_total` (primary): sum over A-H of mean(criteria) x weight, 0-81, higher is
  better. Computed from the unrounded per-criterion scores, so recomputing it from the
  rounded category means differs by up to about 0.4 (the samples hold the rounded means;
  the manifest notes carry both).
- `category_mean`: unweighted mean of the 8 category means, 0-3 (a secondary view).

Tier-2 (every `tier2` run):

- `contract` (primary): mean of T1-T7, 0-3, higher is better. `contract_total` = 7 x
  `contract` = the published T1-T7 total /21.
- `task_success`: golden task passed (share).
- `golden_usd_per_1k`: USD of one golden run x 1000, lower is better. Native USD where the
  harness emits it; dsh is computed from tokens x OpenRouter list price; nanocodex is its
  own client-side estimate; null where none is emitted (fx, flue, eve).
- `golden_wall_s`: wall seconds of one golden run, lower is better. Process wall time,
  except pi 0.85.1 (agent-exec from message timestamps).
- Tokens per golden run are in `samples.jsonl` as each harness reports them. Input
  excludes cache reads, except nanocodex whose input includes them.

**Readiness gate (qualitative, not a metric).** A harness is deploy-ready for the role
only if it has (1) a stable release line, (2) had or does not need a security audit for
secret handling, and (3) a first-class structured one-shot (not daemon-only). Applied on
2026-10-04 it passes omp, opencode and pi, and gives the deploy-today rank
**omp > opencode > pi**; capability rank (score as-is) is omp ~= dsh > nanocodex >
opencode > pi > fx > crush, with flue and eve mid-pack. Reasoning:
[docs/2026-10-04-harness-comparison.md](docs/2026-10-04-harness-comparison.md) section 6 and
BENCHMARK.md "Readiness gate". These ranks are judgments over single runs, not stats-backed
verdicts; every manifest's verdict is SNAPSHOT.

## 4. Judge

No LLM judge scores the runs.

- Tier-1: investigator agents read each harness's source and docs and filled the
  criteria with citations; the operator reviewed and set the final scores. The
  investigators' model was not recorded. dsh's row was cross-checked against the
  investigator's own self-scored sheet (about 67, against 65.6 at the stricter line).
- Tier-2: the operator scored each test 0-3 against the raw evidence under `t2/`, with one
  shared rubric. No second rater. One rubric drift was caught and fixed on 2026-10-04
  (crush T2/T7 in its RESULT.md).

## 5. Baselines

None run. omp, the incumbent in the role, is the reference point for every comparison in
the write-ups. There is no do-nothing or oracle harness; the golden task's end-state check
is the ceiling.

## 6. Noise band

- Tier-1: about **+/-3** on the weighted total, from judgment-call scoring in a single
  static pass (BENCHMARK.md "Calibration caveat"). Not measured by an A/A run. Read tiers,
  not decimals; the omp/dsh gap (0.5) is within noise.
- Tier-2: not measured. No A/A run (same harness, version and model twice) exists. Two
  re-runs give a hint only: pi 0.85.1 -> 1.0.2 (2026-10-04, a different version) kept
  every verdict and moved the golden cost from $0.000263 to $0.000228; the eve T6 re-run
  kept the score but showed different behavior from the original capture. The golden cost
  and wall time are single samples on one macOS machine.

## 7. Fairness and leak register

- Same model for 7 of 9 harnesses: `qwen/qwen3.7-flash` via OpenRouter. fx ran on
  grok-4.6 (its shipped binary cannot reach OpenRouter) and nanocodex on
  `xiaomi/mimo-v2.6-pro` (closed model list, and qwen's provider rejects its Code Mode
  tool). Those two runs are `setup: custom`, their T8 is not comparable and they are
  excluded from any comparison.
- Each harness ran in its own fixture, and its state was isolated where the harness
  allows it (`PI_CODING_AGENT_DIR`, XDG dirs for opencode, `DSH_HOME`, crush `-D`, an
  isolated `HOME` for fx and nanocodex), so the operator's own state was not reused. omp
  was run with `--no-session --no-skills --no-extensions`. One leak was caught: crush merged
  the operator's global config into the first bad-key run, which silently succeeded via
  another provider; the scored T7 re-ran with `CRUSH_GLOBAL_CONFIG` + `CRUSH_GLOBAL_DATA`
  isolated.
- Harness-specific flags needed to run headless at all were used and are recorded per
  subject (`generation_args`): omp `--auto-approve`, opencode `--auto`, pi
  `--thinking off`, dsh pinned to 0.1.6-alpha.2 + `danger-full-access`, crush
  `permissions.allowed_tools`, eve custom-provider shim + docker backend, nanocodex five
  `false` loader flags + isolated `HOME`/`CODEX_HOME`.
- T4 uses each harness's own system-prompt channel (flag, AGENTS.md, CRUSH.md,
  instructions.md, agent code), and T3 its own allowlist mechanism; the score is about
  whether the mechanism works for a driver.
- T5 decoys differ slightly: dsh and nanocodex runs added plain-named and token-named
  decoys (and a cwd `.env` for nanocodex) to map the scrub rule.
- No ground truth can leak: the tests are capability probes, and the golden task's
  answer is checked by running the file.

## 8. Known flaws and their estimated impact

- One attempt per test per harness, one operator scoring. Any 1-point difference on a
  test, and any T1-T7 total gap of a few points, can flip on a re-run.
- Tier-1 per-criterion scores were written down only for nanocodex; the other eight
  survive as category means, so their totals cannot be recomputed exactly (up to 0.4).
- Versions differ between tiers: omp audited 18.2.4 but run on 18.2.0, opencode audited
  1.18.31 but run on 1.18.30.
- crush raw output was not committed (plain-text stdout plus an uncommitted
  `session show --json` capture); its numbers come from its RESULT.md. Its output tokens
  look last-turn only.
- eve's golden tokens come from a trace of an earlier golden session, not the
  `golden-docker.out` session.
- flue's T6 has no committed log; nanocodex's T3 was scored from `--help`, not a live run.
- Costs are not on one basis: native USD, list-price computed (dsh), client-estimated
  (nanocodex), or absent.
- Star counts and maturity labels are as of the audit date; pi's ~106k is flagged as
  suspicious.

## 9. Out of scope

- Not a ranking of coding agents for humans, and not a ranking of models.
- Do not compare fx or nanocodex T8 cost or wall time with the qwen runs.
- Do not quote a Tier-1 decimal gap under about 3 points, or a single-run Tier-2 cost, as
  a measured win.
- Not a security audit of any harness.

## 10. Changelog

### [1-A] - 2026-09-17
- Tier-1 rubric (8 weighted categories, 42 criteria, 0-3) and Tier-2 tests (T1-T7 scored
  0-3, T8 cost and wall, golden task). First six harnesses: omp, dsh, opencode, pi, fx,
  crush. Runs `2026-09-17-tier1-static-audit`, `2026-09-17-tier2-qwen`,
  `2026-09-17-tier2-fx-grok`.
- 2026-09-18: flue and eve added on the same rubric and tests (`2026-09-18-tier2-flue`,
  `2026-09-18-tier2-eve`).
- 2026-10-04: published numbers corrected against the raw evidence (pi usage summed over
  turns, dsh cost with cache reads, eve trace tokens, crush RESULT.md aligned to the
  shared rubric, fx E1 without `--timeout`), each recorded as a manifest correction. pi
  re-run on 1.0.2, nanocodex added, eve T6 re-run. No rubric or test change, so the
  version stays 1-A.
- 2026-10-09: backfilled to the bench standard (bench-kit v0.2.0): one manifest and
  samples file per run, generated RESULTS.md and runs/INDEX.md.
